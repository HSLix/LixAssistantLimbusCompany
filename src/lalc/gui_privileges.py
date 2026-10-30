"""Windows GUI 启动前请求管理员权限，不影响 CLI 或其他平台。"""

from __future__ import annotations

import ctypes
from pathlib import Path
import subprocess
import sys


def ensure_gui_privileges() -> int | None:
    """已提权时继续；否则重启并结束原进程，拒绝或失败时双语提示。"""
    if sys.platform != "win32":
        return None
    shell = ctypes.windll.shell32
    try:
        if shell.IsUserAnAdmin():
            return None
        arguments = sys.argv[1:] if getattr(sys, "frozen", False) else sys.orig_argv[1:]
        # ShellExecute 的返回值是指针宽度，不能使用 ctypes 默认的 32 位 int。
        shell.ShellExecuteW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
                                       ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_int]
        shell.ShellExecuteW.restype = ctypes.c_void_p
        result = shell.ShellExecuteW(None, "runas", sys.executable,
                                    subprocess.list2cmdline(arguments), str(Path.cwd()), 1)
        if result and result > 32:
            return 0
    except OSError:
        pass
    ctypes.windll.user32.MessageBoxW(
        None,
        "需要管理员权限才能启动 LALC。请重新启动并允许管理员权限请求。\n\n"
        "LALC requires administrator privileges to start. Please restart and allow the administrator permission request.",
        "LALC — 需要管理员权限 / Administrator privileges required",
        0x10,
    )
    return 1
