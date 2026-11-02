"""只读发现 Steam 安装并观测游戏版本；任何观测失败均不阻止 Agent。"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import threading

from .process_lock import ProcessLock
from .runtime import atomic_write_json


APP_ID = "1973530"
SETTINGS = "game-version-settings.json"
_unity_lock = threading.Lock()
_KNOWN_LAYOUT = "3febd5a63d2343745880f2e8c18d97e3978b0c03f13ce9dccb3d7155b3ae7bd4"


def parse_vdf(text):
    """解析 Steam 使用的引号键值及嵌套表，拒绝截断、重复键和额外内容。"""
    tokens, end = [], 0
    for match in re.finditer(r'\s+|//[^\r\n]*|"(?:\\.|[^"\\])*"|[{}]', text):
        if match.start() != end:
            raise ValueError("Invalid Steam VDF syntax")
        token, end = match.group(), match.end()
        if not token.isspace() and not token.startswith("//"):
            tokens.append(token)
    if end != len(text):
        raise ValueError("Truncated Steam VDF")
    position = 0

    def string(token):
        if not token.startswith('"'):
            raise ValueError("Expected a quoted Steam VDF string")
        return re.sub(r'\\([\\"])', r'\1', token[1:-1])

    def table(depth=0, nested=False):
        nonlocal position
        if depth > 32:
            raise ValueError("Steam VDF nesting is too deep")
        result = {}
        while position < len(tokens):
            token = tokens[position]
            position += 1
            if token == "}":
                if nested:
                    return result
                raise ValueError("Unexpected Steam VDF closing brace")
            key = string(token).lower()
            if key in result or position == len(tokens):
                raise ValueError("Duplicate or incomplete Steam VDF field")
            value = tokens[position]
            position += 1
            result[key] = table(depth + 1, True) if value == "{" else string(value)
        if nested:
            raise ValueError("Unclosed Steam VDF table")
        return result

    return table()


def _vdf(path):
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("Steam metadata exceeds 4 MiB")
    return parse_vdf(path.read_text(encoding="utf-8-sig"))


def load_steam_root(data_root):
    """读取人工设置与自动缓存共用的 Steam 客户端地址，不自动修复坏文件。"""
    path = Path(data_root) / SETTINGS
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(value, dict) or set(value) != {"steam_root"}
            or not isinstance(value["steam_root"], str) or not value["steam_root"]):
        raise ValueError("Invalid Steam directory settings")
    return value["steam_root"]


def installation(steam_root):
    """从客户端库配置定位唯一的 Limbus 安装，不接受库目录冒充客户端目录。"""
    root = Path(steam_root).resolve(strict=True)
    if not (root / "steam.exe").is_file():
        raise ValueError("Select the Steam client directory containing steam.exe")
    libraries = {root}
    config = root / "steamapps/libraryfolders.vdf"
    if config.exists():
        folders = _vdf(config).get("libraryfolders")
        if not isinstance(folders, dict):
            raise ValueError("Invalid Steam library configuration")
        for key, value in folders.items():
            if key.isdecimal():
                address = value.get("path") if isinstance(value, dict) else value
                if not isinstance(address, str) or not Path(address).is_absolute():
                    raise ValueError("Invalid Steam library path")
                libraries.add(Path(address).resolve())
    found = {}
    for library in sorted(libraries):
        manifest = library / "steamapps" / f"appmanifest_{APP_ID}.acf"
        if not manifest.is_file():
            continue
        app = _vdf(manifest).get("appstate")
        if not isinstance(app, dict) or app.get("appid") != APP_ID:
            raise ValueError("Steam manifest has an unexpected App ID")
        name = app.get("installdir")
        if (not isinstance(name, str) or name in {"", ".", ".."}
                or any(c in name for c in "/\\:")):
            raise ValueError("Invalid Limbus installation directory")
        game = (library / "steamapps/common" / name).resolve()
        if not game.is_relative_to((library / "steamapps/common").resolve()):
            raise ValueError("Limbus installation escapes the Steam library")
        if game.is_dir():
            found[game] = manifest
    if len(found) != 1:
        raise ValueError("Expected exactly one Limbus installation in this Steam client")
    game, manifest = next(iter(found.items()))
    return root, game, manifest


def save_steam_root(data_root, address):
    """人工设置先验证安装及至少一个可读 ID，失败不替换旧设置。"""
    root, game, manifest = installation(address)
    game_version, build_id, errors = _identifiers(game, manifest)
    if game_version is None and build_id is None:
        raise ValueError("Neither version identifier is readable: " + json.dumps(errors, ensure_ascii=False))
    _save_root(data_root, root)
    return str(root)


def _save_root(data_root, root):
    with ProcessLock("game-version-settings:" + str(Path(data_root).resolve())):
        atomic_write_json(Path(data_root) / SETTINGS, {"steam_root": str(root)})


def discover_steam_roots():
    """仅查注册表、常见位置及磁盘第一级目录，不递归扫描整盘。"""
    if sys.platform != "win32":
        return []
    import ctypes
    import os
    import winreg
    candidates = set()
    for hive, key, field in (
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
    ):
        try:
            with winreg.OpenKey(hive, key) as handle:
                candidates.add(Path(winreg.QueryValueEx(handle, field)[0]))
        except OSError:
            pass
    for variable in ("ProgramFiles(x86)", "ProgramFiles"):
        if os.environ.get(variable):
            candidates.add(Path(os.environ[variable]) / "Steam")
    # 按阶段枚举后统一去重、验证，不能因为先找到一个就隐藏其他有效安装。
    drives = ctypes.windll.kernel32.GetLogicalDrives()
    for number in range(26):
        if drives & (1 << number):
            drive = Path(f"{chr(65 + number)}:/")
            try:
                candidates.update(path for path in drive.iterdir() if path.is_dir())
            except OSError:
                continue
    return sorted(candidates)


def read_game_version(path):
    """解析 PlayerSettings；仅对已验证布局允许已知的四字节尾部差异。"""
    import UnityPy
    from UnityPy.helpers import TypeTreeHelper
    with _unity_lock:
        objects = [obj for obj in UnityPy.load(str(path)).objects if obj.type.name == "PlayerSettings"]
        if len(objects) != 1:
            raise ValueError("Expected one PlayerSettings object")
        obj = objects[0]
        # Python reader 才能报告实际消费的字节；临时切换后恢复第三方全局配置。
        boost = getattr(TypeTreeHelper, "read_typetree_boost")
        try:
            setattr(TypeTreeHelper, "read_typetree_boost", None)
            settings = obj.read_typetree(check_read=False)
        finally:
            setattr(TypeTreeHelper, "read_typetree_boost", boost)
        unread = obj.byte_start + obj.byte_size - obj.reader.Position
        if unread:
            signature = hashlib.sha256(obj.dump_typetree_structure().encode()).hexdigest()
            if (unread != 4 or UnityPy.__version__ != "1.25.4"
                    or obj.assets_file.unity_version != "6000.3.12f1"
                    or obj.assets_file.header.version != 22 or signature != _KNOWN_LAYOUT):
                raise ValueError(f"Unsupported PlayerSettings layout ({unread} unread bytes)")
        if (settings.get("companyName"), settings.get("productName")) != ("ProjectMoon", "LimbusCompany"):
            raise ValueError("PlayerSettings is not LimbusCompany")
        version = settings.get("bundleVersion")
        if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+[A-Za-z0-9.+-]*", version):
            raise ValueError("Invalid PlayerSettings.bundleVersion")
        return version


def _identifiers(game, manifest):
    game_version, build_id, errors = None, None, []
    for field in ("steam_build_id", "game_version"):
        try:
            if field == "steam_build_id":
                value = _vdf(manifest)["appstate"].get("buildid")
                if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{0,19}", value):
                    raise ValueError("Invalid Steam Build ID")
                build_id = value
            else:
                game_version = read_game_version(game / "LimbusCompany_Data/globalgamemanagers")
        except Exception as error:
            errors.append({"field": field, "type": type(error).__name__, "message": str(error)})
    return game_version, build_id, errors


def observe_game_version(data_root):
    """独立取得两个 ID；任何发现或解析故障变成观测诊断，不启动游戏。"""
    result = {"game_version": None, "steam_build_id": None,
              "observed_at": datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z"), "errors": []}
    if sys.platform != "win32":
        result["errors"].append({"field": "installation", "message": "Game version observation requires Windows"})
        return result
    config_valid = True
    try:
        try:
            saved = load_steam_root(data_root)
        except Exception as error:
            config_valid, saved = False, None
            result["errors"].append({"field": "settings", "message": str(error)})
        selected = None
        if saved:
            try:
                selected = installation(saved)
            except Exception as error:
                result["errors"].append({"field": "cached_directory", "message": str(error)})
        if selected is None:
            matches = {}
            for candidate in discover_steam_roots():
                try:
                    value = installation(candidate)
                    matches[value[0]] = value
                except (OSError, ValueError, KeyError, TypeError):
                    continue
            if len(matches) != 1:
                raise ValueError("Steam installation missing or ambiguous. Set the Steam client directory in User GUI General Settings.")
            selected = next(iter(matches.values()))
        root, game, manifest = selected
        version, build, errors = _identifiers(game, manifest)
        result.update(game_version=version, steam_build_id=build)
        result["errors"].extend(errors)
        if config_valid and (version or build) and saved != str(root):
            _save_root(data_root, root)
    except Exception as error:
        result["errors"].append({"field": "installation", "type": type(error).__name__, "message": str(error)})
    return result
