"""保存当前 Agent 连接设置；命名密钥独立使用 Windows 当前用户 DPAPI。"""

from __future__ import annotations

import ctypes
import getpass
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlsplit

from .runtime import atomic_write_json


FIELDS = ("base_url", "model", "max_requests", "secret_name")
DEFAULTS = {"base_url": "http://localhost:12138/v1", "model": None,
            "max_requests": 20, "secret_name": None}


def validate_settings(value: dict) -> dict:
    """校验已保存或本次合并的设置，不补写 API 路径，也不要求保存时模型已可用。"""
    if not isinstance(value, dict) or value.keys() - set(FIELDS):
        raise ValueError("Invalid Agent settings fields")
    result = {**DEFAULTS, **value}
    address = result["base_url"]
    if not isinstance(address, str):
        raise ValueError("base-url must be a complete HTTP(S) API base URL")
    parsed = urlsplit(address)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment):
        raise ValueError("base-url must be a complete HTTP(S) API base URL without credentials, query or fragment")
    if type(result["max_requests"]) is not int or result["max_requests"] < 2:
        raise ValueError("max-requests must be at least 2; reset the request limit")
    for field in ("model", "secret_name"):
        if result[field] is not None and (not isinstance(result[field], str) or not result[field].strip()):
            raise ValueError(f"{field} must be a non-empty string or null")
    return result


def load_settings(data_root: Path, overrides: dict | None = None) -> dict:
    """只读当前设置；不存在时采用缺省值，损坏配置不会静默回退。"""
    path = data_root / "agent-settings.json"
    saved = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not isinstance(saved, dict):
        raise ValueError("Agent settings must be a JSON object")
    return validate_settings({**saved, **(overrides or {})})


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
            if args.clear_secret:
                value["secret_name"] = None
            if args.clear_secret or any(getattr(args, field) is not None for field in FIELDS):
                atomic_write_json(data_root / "agent-settings.json", value)
            print(json.dumps(value, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, UnicodeError) as error:
        print(f"Agent configuration failed: {error}")
        return 1
