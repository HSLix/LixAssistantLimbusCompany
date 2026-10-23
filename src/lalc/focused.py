"""Windows 前台窗口观察与本次运行的内存截图。"""

from __future__ import annotations

import ctypes
import struct
import time
import zlib
from ctypes import wintypes
from pathlib import Path
from typing import Any, Callable


class WindowError(RuntimeError):
    """目标窗口、焦点或截图不满足安全观察条件。"""


class FocusedAutomationSession:
    """只持有一个目标窗口及其最新有效截图。"""

    def __init__(self, platform: Any, emit: Callable[[str, dict[str, Any]], None]) -> None:
        self.platform = platform
        self.emit = emit
        self.hwnd: int | None = None
        self.process_id: int | None = None
        self.image: bytes | None = None
        self.size: tuple[int, int] | None = None
        self.observation = 0

    def connect(self) -> dict[str, Any]:
        """唯一匹配后只恢复并置前一次，随后核验真实前台状态。"""

        matches = self.platform.find_windows()
        if len(matches) != 1:
            raise WindowError(f"Expected one Limbus Company window, found {len(matches)}.")
        hwnd = matches[0]
        self.platform.focus(hwnd)
        info = self.platform.window_info(hwnd)
        self._require_window(info)
        self.hwnd = hwnd
        self.process_id = info["process_id"]
        self.emit("target_window_connected", info)
        return info

    def check(self, *, record: bool = True) -> dict[str, Any]:
        """重新核验句柄和焦点，任何失效都会丢弃旧截图。"""

        if self.hwnd is None:
            return self.connect()
        info = self.platform.window_info(self.hwnd)
        try:
            self._require_window(info)
            if info["process_id"] != self.process_id:
                raise WindowError("Target Window process changed.")
            if self.size is not None and (info["width"], info["height"]) != self.size:
                raise WindowError("Target Window client area changed since capture.")
        except WindowError as error:
            self.image = None
            self.size = None
            self.emit("target_window_invalid", {"reason": str(error), "hwnd": self.hwnd})
            raise
        if record:
            self.emit("target_window_checked", info)
        return info

    @staticmethod
    def _require_window(info: dict[str, Any]) -> None:
        if not info["valid"] or not info["visible"] or info["minimized"]:
            raise WindowError("Target Window is unavailable or minimized.")
        if info["width"] <= 0 or info["height"] <= 0:
            raise WindowError("Target Window client area is empty.")
        if not info["foreground"]:
            raise WindowError(
                f"Target Window is not foreground. target_hwnd={info['hwnd']}, "
                f"foreground_hwnd={info.get('foreground_hwnd', 'unavailable')}, "
                f"title={info['title']!r}."
            )

    def capture(self) -> dict[str, int]:
        """取得客户区原始图像；失败不沿用旧图。"""

        self.image = None
        self.size = None
        try:
            info = self.check()
            pixels = self.platform.capture(info["hwnd"], info["width"], info["height"])
            if type(pixels) is not bytes or len(pixels) != info["width"] * info["height"] * 4:
                raise WindowError("Captured image has an invalid size.")
            # PrintWindow 期间也可能丢失焦点，复核后才公开本次图像。
            current = self.check()
            if (current["width"], current["height"]) != (info["width"], info["height"]):
                raise WindowError("Target Window client area changed during capture.")
        except Exception as error:
            self.emit("screenshot_refresh_failed", {"reason": str(error)})
            raise
        self.image = pixels
        self.size = (info["width"], info["height"])
        self.observation += 1
        result = {"observation": self.observation, "width": info["width"], "height": info["height"]}
        self.emit("screenshot_refreshed", result)
        return result

    def save(self, path: Path, *, evidence_id: str | None = None) -> dict[str, Any]:
        """将当前有效截图保存为 PNG，不再调用截图 API。"""

        self.check()
        if self.image is None or self.size is None:
            raise WindowError("No current screenshot to save.")
        width, height = self.size
        rgb = bytearray(width * height * 3)
        rgb[0::3], rgb[1::3], rgb[2::3] = self.image[2::4], self.image[1::4], self.image[0::4]
        row_size = width * 3
        pixels = b"".join(b"\0" + rgb[start:start + row_size] for start in range(0, len(rgb), row_size))

        def chunk(kind: bytes, data: bytes) -> bytes:
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

        png = (b"\x89PNG\r\n\x1a\n"
               + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
               + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b""))
        path.parent.mkdir(parents=True, exist_ok=True)
        result = {"observation": self.observation, "path": str(path), "width": width, "height": height}
        if evidence_id is not None:
            result["evidence_id"] = evidence_id
        try:
            path.write_bytes(png)
            self.emit("screenshot_saved", result)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return result


class WindowsWindowPlatform:
    """用 Win32 查找 Unity 游戏窗口并抓取客户区像素。"""

    TITLE = "LimbusCompany"
    CLASS = "UnityWndClass"
    EXECUTABLE = "limbuscompany.exe"

    def create_input_backend(self):
        """延迟建立只读输入监测；纯连接诊断不安装输入钩子。"""

        from .windows_input import WindowsInputBackend

        return WindowsInputBackend(self)

    def __init__(self, *, checkpoint: Callable[[], None] | None = None) -> None:
        self.checkpoint = checkpoint
        if not hasattr(ctypes, "WinDLL"):
            raise WindowError("Windows observation is available only on Windows.")
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._configure()
        self._dpi_awareness()

    def _configure(self) -> None:
        u, g, k = self.user32, self.gdi32, self.kernel32
        u.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM), wintypes.LPARAM]
        u.EnumWindows.restype = wintypes.BOOL
        u.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        u.GetClassNameW.restype = ctypes.c_int
        u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        u.GetWindowTextW.restype = ctypes.c_int
        u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        u.GetWindowThreadProcessId.restype = wintypes.DWORD
        for name in ("IsWindow", "IsWindowVisible", "IsIconic"):
            getattr(u, name).argtypes = [wintypes.HWND]
            getattr(u, name).restype = wintypes.BOOL
        u.GetForegroundWindow.restype = wintypes.HWND
        u.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        u.GetClientRect.restype = wintypes.BOOL
        u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        u.ShowWindow.restype = wintypes.BOOL
        u.SetForegroundWindow.argtypes = [wintypes.HWND]
        u.SetForegroundWindow.restype = wintypes.BOOL
        u.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        u.ClientToScreen.restype = wintypes.BOOL
        u.ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        u.ScreenToClient.restype = wintypes.BOOL
        u.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        u.GetCursorPos.restype = wintypes.BOOL
        u.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
        u.PrintWindow.restype = wintypes.BOOL
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.OpenProcess.restype = wintypes.HANDLE
        k.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        k.QueryFullProcessImageNameW.restype = wintypes.BOOL
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        k.CloseHandle.restype = wintypes.BOOL
        g.CreateCompatibleDC.argtypes = [wintypes.HDC]
        g.CreateCompatibleDC.restype = wintypes.HDC
        g.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD]
        g.CreateDIBSection.restype = wintypes.HBITMAP
        g.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
        g.SelectObject.restype = wintypes.HGDIOBJ
        g.DeleteObject.argtypes = [wintypes.HGDIOBJ]
        g.DeleteObject.restype = wintypes.BOOL
        g.DeleteDC.argtypes = [wintypes.HDC]
        g.DeleteDC.restype = wintypes.BOOL
        g.GdiFlush.restype = wintypes.BOOL

    def _dpi_awareness(self) -> None:
        try:
            self.user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
            self.user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
            self.user32.GetThreadDpiAwarenessContext.restype = ctypes.c_void_p
            self.user32.GetAwarenessFromDpiAwarenessContext.argtypes = [ctypes.c_void_p]
            self.user32.GetAwarenessFromDpiAwarenessContext.restype = ctypes.c_int
            self.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
            current = self.user32.GetThreadDpiAwarenessContext()
            if self.user32.GetAwarenessFromDpiAwarenessContext(current) != 2:
                raise WindowError("Per-Monitor DPI awareness is required.")
        except AttributeError as error:
            raise WindowError("Per-Monitor DPI awareness is unavailable.") from error

    def _text(self, hwnd: int, function: Any) -> str:
        buffer = ctypes.create_unicode_buffer(512)
        function(hwnd, buffer, len(buffer))
        return buffer.value

    def _process_path(self, pid: int) -> str:
        handle = self.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return ""
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            length = wintypes.DWORD(len(buffer))
            if not self.kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)):
                return ""
            return buffer.value
        finally:
            self.kernel32.CloseHandle(handle)

    def _identity(self, hwnd: int) -> tuple[str, str, int, str]:
        pid = wintypes.DWORD()
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return (
            self._text(hwnd, self.user32.GetWindowTextW),
            self._text(hwnd, self.user32.GetClassNameW),
            pid.value,
            self._process_path(pid.value),
        )

    def find_windows(self) -> list[int]:
        matches: list[int] = []
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def visit(hwnd: int, unused: int) -> bool:
            title, window_class, _, process_path = self._identity(hwnd)
            if title == self.TITLE and window_class == self.CLASS and Path(process_path).name.lower() == self.EXECUTABLE:
                matches.append(hwnd)
            return True

        callback = callback_type(visit)
        if not self.user32.EnumWindows(callback, 0):
            raise WindowError("Unable to enumerate Windows desktop windows.")
        return matches

    def window_info(self, hwnd: int) -> dict[str, Any]:
        valid = bool(self.user32.IsWindow(hwnd))
        title, window_class, pid, process_path = self._identity(hwnd) if valid else ("", "", 0, "")
        rect = wintypes.RECT()
        client_ok = valid and bool(self.user32.GetClientRect(hwnd, ctypes.byref(rect)))
        width = rect.right - rect.left if client_ok else 0
        height = rect.bottom - rect.top if client_ok else 0
        identity_ok = title == self.TITLE and window_class == self.CLASS and Path(process_path).name.lower() == self.EXECUTABLE
        foreground_hwnd = self.user32.GetForegroundWindow()
        return {
            "hwnd": int(hwnd), "process_id": pid, "process_path": process_path,
            "title": title, "class": window_class, "valid": valid and identity_ok,
            "visible": bool(self.user32.IsWindowVisible(hwnd)) if valid else False,
            "minimized": bool(self.user32.IsIconic(hwnd)) if valid else False,
            "foreground": foreground_hwnd == hwnd, "foreground_hwnd": foreground_hwnd,
            "width": width, "height": height,
        }

    def focus(self, hwnd: int) -> None:
        """只请求置前一次，等待异步激活；不以等待时长报错，允许用户取消。"""

        if self.user32.GetForegroundWindow() == hwnd:
            return
        if self.user32.IsIconic(hwnd):
            self.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        self.user32.SetForegroundWindow(hwnd)
        # 跨线程激活可能尚未完成；等待真实焦点，不重复抢占前台。
        while True:
            if self.checkpoint is not None:
                self.checkpoint()
            foreground_hwnd = self.user32.GetForegroundWindow()
            if foreground_hwnd == hwnd:
                return
            if not self.user32.IsWindow(hwnd):
                raise WindowError(f"Target Window disappeared while waiting for foreground: target_hwnd={hwnd}.")
            time.sleep(0.02)

    def cursor_position(self, hwnd: int) -> dict[str, Any]:
        """只读转换物理鼠标坐标，不要求或改变前台焦点。"""
        point = wintypes.POINT()
        if not self.user32.GetCursorPos(ctypes.byref(point)) or not self.user32.ScreenToClient(hwnd, ctypes.byref(point)):
            raise WindowError("Cannot read client cursor position") from ctypes.WinError(ctypes.get_last_error())
        info = self.window_info(hwnd)
        return {"x": point.x, "y": point.y,
                "inside": 0 <= point.x < info["width"] and 0 <= point.y < info["height"]}

    def client_to_screen(self, hwnd: int, x: int, y: int) -> tuple[int, int]:
        info = self.window_info(hwnd)
        FocusedAutomationSession._require_window(info)
        if not 0 <= x < info["width"] or not 0 <= y < info["height"]:
            raise WindowError("Client coordinates are outside the Target Window.")
        point = wintypes.POINT(x, y)
        if not self.user32.ClientToScreen(hwnd, ctypes.byref(point)):
            raise WindowError("ClientToScreen failed.") from ctypes.WinError(ctypes.get_last_error())
        return point.x, point.y

    def capture(self, hwnd: int, width: int, height: int) -> bytes:
        """PrintWindow 到顶部为第一行的 32 位 DIB，返回 BGRA 像素。"""

        class BitmapInfoHeader(ctypes.Structure):
            _fields_ = [
                ("size", wintypes.DWORD), ("width", ctypes.c_long), ("height", ctypes.c_long),
                ("planes", wintypes.WORD), ("bit_count", wintypes.WORD),
                ("compression", wintypes.DWORD), ("image_size", wintypes.DWORD),
                ("x_pixels_per_meter", ctypes.c_long), ("y_pixels_per_meter", ctypes.c_long),
                ("colors_used", wintypes.DWORD), ("colors_important", wintypes.DWORD),
            ]

        header = BitmapInfoHeader(40, width, -height, 1, 32, 0, width * height * 4, 0, 0, 0, 0)
        dc = self.gdi32.CreateCompatibleDC(None)
        if not dc:
            raise WindowError("CreateCompatibleDC failed.")
        bitmap = None
        previous = None
        try:
            pixels = ctypes.c_void_p()
            bitmap = self.gdi32.CreateDIBSection(None, ctypes.byref(header), 0, ctypes.byref(pixels), None, 0)
            if not bitmap or not pixels.value:
                raise WindowError("CreateDIBSection failed.")
            previous = self.gdi32.SelectObject(dc, bitmap)
            if not previous:
                raise WindowError("SelectObject failed.")
            if not self.user32.PrintWindow(hwnd, dc, 0x00000003):
                raise WindowError("PrintWindow failed.")
            if not self.gdi32.GdiFlush():
                raise WindowError("GdiFlush failed.")
            return ctypes.string_at(pixels, width * height * 4)
        finally:
            if previous:
                self.gdi32.SelectObject(dc, previous)
            if bitmap:
                self.gdi32.DeleteObject(bitmap)
            self.gdi32.DeleteDC(dc)
