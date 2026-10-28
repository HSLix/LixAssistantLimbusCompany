"""保存当前 Agent 连接设置；命名密钥独立使用 Windows 当前用户 DPAPI。"""

from __future__ import annotations

import ctypes
import getpass
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading
from copy import deepcopy
from urllib.parse import urlsplit

from .runtime import atomic_write_json


FIELDS = ("provider", "base_url", "model", "max_requests", "secret_name", "output_limit",
          "thinking", "reasoning_effort")
DEFAULTS = {"provider": "llama.cpp", "base_url": "http://localhost:12138/v1", "model": None,
            "max_requests": 20, "secret_name": None, "output_limit": "server_default",
            "thinking": False, "reasoning_effort": "high"}
PROVIDERS = {"llama.cpp", "deepseek"}
SETTINGS_LOCK = threading.RLock()


def provider_defaults(provider: str) -> dict:
    """仅为 DeepSeek 提供固定模型与默认推理选项，保留本地服务原行为。"""
    return ({"base_url": "https://api.deepseek.com", "model": "deepseek-flash", "thinking": True,
             "reasoning_effort": "high"} if provider == "deepseek" else
            {key: DEFAULTS[key] for key in ("base_url", "model", "thinking", "reasoning_effort")})


def validate_settings(value: dict, *, for_use: bool = True) -> dict:
    """保存时只检查结构；使用前检查连接内容，不补路径或联网。"""
    if not isinstance(value, dict) or value.keys() - set(FIELDS) - {"provider_secrets"}:
        raise ValueError("Invalid Agent settings fields")
    provider = value.get("provider", "llama.cpp")
    if provider not in PROVIDERS:
        raise ValueError("仅支持 llama.cpp 或 deepseek provider")
    result = {**DEFAULTS, **provider_defaults(provider), **value}
    if result["output_limit"] != "server_default":
        raise ValueError("单次输出上限当前仅支持使用服务端默认值")
    address = result["base_url"]
    if not isinstance(address, str):
        raise ValueError("base-url must be a complete HTTP(S) API base URL")
    if for_use:
        parsed = urlsplit(address)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.query or parsed.fragment):
            raise ValueError("base-url must be a complete HTTP(S) API base URL without credentials, query or fragment")
    if type(result["max_requests"]) is not int or result["max_requests"] < 2:
        raise ValueError("max-requests must be at least 2; reset the request limit")
    for field in ("model", "secret_name"):
        if result[field] is not None and (not isinstance(result[field], str) or
                ((for_use or field == "secret_name") and not result[field].strip())):
            raise ValueError(f"{field} must be a non-empty string or null")
    if type(result["thinking"]) is not bool or result["reasoning_effort"] not in {"low", "high", "max"}:
        raise ValueError("Invalid thinking switch or reasoning effort")
    if provider == "deepseek" and result["model"] != "deepseek-flash":
        raise ValueError("DeepSeek 当前仅支持 deepseek-flash")
    secrets = value.get("provider_secrets", {})
    if (not isinstance(secrets, dict) or secrets.keys() - PROVIDERS or
            any(not isinstance(name, str) or not name.strip() for name in secrets.values())):
        raise ValueError("Invalid provider secret references")
    result["provider_secrets"] = dict(secrets)
    if result["secret_name"]:
        result["provider_secrets"][provider] = result["secret_name"]
    return result


def settings_document(data_root: Path, overrides: dict | None = None) -> dict:
    """旧配置只在成功保存时迁移，保留所有已保存的凭据引用。"""
    path = data_root / "agent-settings.json"
    saved = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not isinstance(saved, dict):
        raise ValueError("Agent settings must be a JSON object")
    if "profiles" not in saved:
        repair = overrides or {}
        if repair.get("provider", saved.get("provider", "llama.cpp")) != saved.get("provider", "llama.cpp"):
            repair = {}
        legacy = validate_settings({**saved, **repair}, for_use=False)
        profiles = {}
        for provider in PROVIDERS:
            value = legacy if provider == legacy["provider"] else validate_settings({
                "provider": provider, "secret_name": legacy["provider_secrets"].get(provider)})
            profiles[provider] = {field: value[field] for field in FIELDS}
        return {"profiles": profiles, "provider_secrets": legacy["provider_secrets"],
                "user_provider": legacy["provider"], "developer_provider": legacy["provider"],
                "user_enabled": False}
    if (not isinstance(saved["profiles"], dict) or set(saved["profiles"]) != PROVIDERS or
            any(saved.get(side + "_provider") not in PROVIDERS for side in ("user", "developer")) or
            type(saved.get("user_enabled")) is not bool):
        raise ValueError("Invalid shared Agent settings")
    for provider, profile in saved["profiles"].items():
        if not isinstance(profile, dict) or profile.get("provider") != provider:
            raise ValueError("Invalid provider profile")
        validate_settings({**profile, "provider_secrets": saved.get("provider_secrets", {})}, for_use=False)
    return {name: saved[name] for name in ("profiles", "provider_secrets", "user_provider",
                                          "developer_provider", "user_enabled")}


def load_settings(data_root: Path, overrides: dict | None = None, *, side="developer", for_use=True) -> dict:
    """两侧分别选用 provider；CLI 临时覆盖不写回共享设置。"""
    with SETTINGS_LOCK:
        overrides = dict(overrides or {})
        document = settings_document(data_root, overrides)
        provider = overrides.get("provider", document[side + "_provider"])
        if provider not in PROVIDERS:
            raise ValueError("仅支持 llama.cpp 或 deepseek provider")
        return validate_settings({**document["profiles"][provider],
                                  "provider_secrets": document["provider_secrets"], **overrides}, for_use=for_use)


def configuration_complete(value: dict, *, temporary_keys=None) -> bool:
    """只判断选用配置的本地完整性，不解密凭据或测试服务连接。"""
    try:
        value = validate_settings(value)
    except ValueError:
        return False
    return bool(value["model"] and (value["provider"] != "deepseek" or value["secret_name"]
                                  or (temporary_keys or {}).get("deepseek")))


def _save_document(data_root: Path, document: dict) -> None:
    # 平面视图保留 Developer 有效字段，供现有 CLI/诊断消费者读取。
    selected = document["profiles"][document["developer_provider"]]
    atomic_write_json(data_root / "agent-settings.json", {**selected, **document})


def save_selection(data_root: Path, side: str, provider: str, *, enabled=None) -> None:
    """仅保存一侧选用项与 User 开关，不覆盖共享连接内容。"""
    if side not in {"user", "developer"} or provider not in PROVIDERS:
        raise ValueError("Invalid Agent selection")
    if enabled is not None and (side != "user" or type(enabled) is not bool):
        raise ValueError("Invalid User Agent switch")
    with SETTINGS_LOCK:
        document = settings_document(data_root)
        document[side + "_provider"] = provider
        if enabled is not None:
            document["user_enabled"] = enabled
        _save_document(data_root, document)


def settings_snapshot(args, data_root: Path, *, temporary_keys=None, key=None) -> tuple[dict, str]:
    """与保存/删除凭据互斥，一次固定设置与实际认证，不在轮次中重读。"""
    with SETTINGS_LOCK:
        value = effective_settings(args, data_root)
        actual = key if key is not None else (temporary_keys or {}).get(value["provider"])
        if actual is None:
            actual = resolve_key(args, value, data_root)
        return deepcopy(value), actual


def effective_settings(args, data_root: Path) -> dict:
    """CLI 非空值覆盖已保存设置，本次快照不回写。"""
    overrides = {field: getattr(args, field) for field in FIELDS if getattr(args, field, None) is not None}
    return load_settings(data_root, overrides)


def dpapi(data: bytes, *, decrypt: bool = False) -> bytes:
    """仅由当前 Windows 用户保护或解密；禁止弹出系统认证交互，不支持跨机迁移。"""
    if sys.platform != "win32":
        raise ValueError("Persistent secrets require Windows DPAPI; use --ask-api-key on this platform")
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source = Blob(len(data), buffer)
    output = Blob()
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise OSError(f"Windows DPAPI {'decrypt' if decrypt else 'encrypt'} failed ({ctypes.get_last_error()})")
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        kernel.LocalFree(output.data)


def secret_path(data_root: Path, name: str) -> Path:
    """名称映射为固定哈希文件名，密钥名称不能成为文件路径。"""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Secret name must not be empty")
    return data_root / "secrets" / (hashlib.sha256(name.encode()).hexdigest() + ".dpapi")


def save_secret(data_root: Path, name: str, value: str) -> None:
    """先加密再原子替换；磁盘上不写入明文密钥。"""
    path = secret_path(data_root, name)
    if not value:
        raise ValueError("Secret must not be empty")
    encrypted = dpapi(value.encode("utf-8"))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encrypted)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def resolve_key(args, settings: dict, data_root: Path) -> str:
    """临时输入优先；命名密钥缺失或解密失败直接停止，不回退认证方式。"""
    if args.ask_api_key:
        return getpass.getpass("API key（无需认证时留空）: ") or "lalc-no-key"
    name = settings["secret_name"]
    if name is None:
        return "lalc-no-key"
    if sys.platform != "win32":
        raise ValueError("Persistent secrets require Windows DPAPI; use --ask-api-key")
    return dpapi(secret_path(data_root, name).read_bytes(), decrypt=True).decode("utf-8")


def save_settings(data_root: Path, values: dict, *, secret: str = "", clear: bool = False,
                  side="developer", temporary_keys=None) -> dict:
    """原子保存一套配置；空密钥保留，明确清除不影响活动认证快照。"""
    with SETTINGS_LOCK:
        document = settings_document(data_root, values)
        value = load_settings(data_root, values, side=side, for_use=False)
        previous = value["secret_name"]
        if clear:
            value["secret_name"] = None
        elif secret and sys.platform == "win32":
            import uuid
            value["secret_name"] = "developer-" + str(uuid.uuid4())
            save_secret(data_root, value["secret_name"], secret)
        if value["secret_name"]:
            value["provider_secrets"][value["provider"]] = value["secret_name"]
        else:
            value["provider_secrets"].pop(value["provider"], None)
        document["profiles"][value["provider"]] = {field: value[field] for field in FIELDS}
        document["provider_secrets"] = value["provider_secrets"]
        document[side + "_provider"] = value["provider"]
        _save_document(data_root, document)
        if temporary_keys is not None:
            if clear:
                temporary_keys.pop(value["provider"], None)
            elif secret and sys.platform != "win32":
                temporary_keys[value["provider"]] = secret
        if clear and previous and previous not in value["provider_secrets"].values():
            secret_path(data_root, previous).unlink(missing_ok=True)
        return value


def settings_command(args, data_root: Path) -> int:
    """查看或显式保存当前设置；密钥只从终端输入，不回显或接受明文参数。"""
    try:
        if args.command == "secret-set":
            if sys.platform != "win32":
                raise ValueError("Persistent secrets require Windows DPAPI")
            save_secret(data_root, args.name, getpass.getpass("Secret: "))
            print("Secret saved with Windows DPAPI.")
        else:
            value = effective_settings(args, data_root)
            if args.clear_secret or any(getattr(args, field, None) is not None for field in FIELDS):
                value = save_settings(data_root, value, clear=args.clear_secret)
            print(json.dumps(value, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, UnicodeError) as error:
        print(f"Agent configuration failed: {error}")
        return 1
