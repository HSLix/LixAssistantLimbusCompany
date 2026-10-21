"""Windows 只读输入钩子、前台按键与无光标合成触摸。"""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes

from .control import PhysicalInputMonitor

# INPUT 必须包含完整 union；只声明键盘成员会使 Win32 拒绝其尺寸。
class MSLLHOOKSTRUCT(ctypes.Structure):
    """Windows 鼠标钩子记录，保留注入标志与指针宽度。"""

    _fields_ = [
        ("pt", wintypes.POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    """Windows 键盘钩子记录，用注入标志区分物理输入。"""

    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class KEYBDINPUT(ctypes.Structure):
    """SendInput 键盘成员，包含虚拟键和抬起标志。"""

    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class MOUSEINPUT(ctypes.Structure):
    """维持 INPUT union 所需的鼠标成员布局。"""

    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class HARDWAREINPUT(ctypes.Structure):
    """维持 INPUT union 所需的硬件成员布局。"""

    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUT_VALUE(ctypes.Union):
    """完整 Windows INPUT union，保证原生调用的结构尺寸。"""

    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    """SendInput 接收的带类型输入结构。"""

    _anonymous_ = ("value",)
    _fields_ = [("type", wintypes.DWORD), ("value", INPUT_VALUE)]


class POINTER_INFO(ctypes.Structure):
    """合成触摸使用的指针位置、状态和原生身份。"""

    _fields_ = [
        ("pointerType", ctypes.c_uint32),
        ("pointerId", ctypes.c_uint32),
        ("frameId", ctypes.c_uint32),
        ("pointerFlags", ctypes.c_uint32),
        ("sourceDevice", ctypes.c_void_p),
        ("hwndTarget", ctypes.c_void_p),
        ("ptPixelLocation", wintypes.POINT),
        ("ptHimetricLocation", wintypes.POINT),
        ("ptPixelLocationRaw", wintypes.POINT),
        ("ptHimetricLocationRaw", wintypes.POINT),
        ("dwTime", wintypes.DWORD),
        ("historyCount", ctypes.c_uint32),
        ("InputData", ctypes.c_int32),
        ("dwKeyStates", wintypes.DWORD),
        ("PerformanceCount", ctypes.c_uint64),
        ("ButtonChangeType", ctypes.c_uint32),
    ]


class POINTER_TOUCH_INFO(ctypes.Structure):
    """合成触摸的接触区域、方向与压力布局。"""

    _fields_ = [
        ("pointerInfo", POINTER_INFO),
        ("touchFlags", ctypes.c_uint32),
        ("touchMask", ctypes.c_uint32),
        ("rcContact", wintypes.RECT),
        ("rcContactRaw", wintypes.RECT),
        ("orientation", ctypes.c_uint32),
        ("pressure", ctypes.c_uint32),
    ]


class POINTER_TYPE_VALUE(ctypes.Union):
    """合成触摸所需的原生指针类型 union。"""

    _fields_ = [("touchInfo", POINTER_TOUCH_INFO)]


class POINTER_TYPE_INFO(ctypes.Structure):
    """InjectSyntheticPointerInput 接收的带类型结构。"""

    _anonymous_ = ("value",)
    _fields_ = [("type", ctypes.c_uint32), ("value", POINTER_TYPE_VALUE)]


class MSG(ctypes.Structure):
    """钩子线程消息循环接收的 Windows 消息布局。"""

    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
        ("lPrivate", wintypes.DWORD),
    ]


class WindowsInputBackend:
    """将原生输入封装在一个 Run 的资源生命周期内，钩子永远放行输入。"""

    def __init__(self, platform) -> None:
        self.platform = platform
        self.user32, self.kernel32 = platform.user32, platform.kernel32
        self.monitor = PhysicalInputMonitor()
        self._thread_id = 0
        self._ready = threading.Event()
        self._closing = False
        self._configure()
        self._thread = threading.Thread(target=self._listen, name="lalc-input-monitor", daemon=True)
        self._thread.start()
        try:
            while not self._ready.wait(0.02):
                if self.platform.checkpoint is not None:
                    self.platform.checkpoint()
        except BaseException:
            self.close()
            raise
        self.monitor.snapshot()

    def _configure(self) -> None:
        u, k = self.user32, self.kernel32
        self._hook_type = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        signatures = {
            "SetWindowsHookExW": ([ctypes.c_int, self._hook_type, wintypes.HINSTANCE, wintypes.DWORD], wintypes.HHOOK),
            "CallNextHookEx": ([wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM], ctypes.c_ssize_t),
            "UnhookWindowsHookEx": ([wintypes.HHOOK], wintypes.BOOL),
            "GetMessageW": ([ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT], ctypes.c_int),
            "PeekMessageW": ([ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT], wintypes.BOOL),
            "PostThreadMessageW": ([wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM], wintypes.BOOL),
            "GetAsyncKeyState": ([ctypes.c_int], wintypes.SHORT),
            "MapVirtualKeyW": ([wintypes.UINT, wintypes.UINT], wintypes.UINT),
            "SendInput": ([wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int], wintypes.UINT),
            "CreateSyntheticPointerDevice": ([ctypes.c_uint32, wintypes.ULONG, ctypes.c_uint32], ctypes.c_void_p),
            "InjectSyntheticPointerInput": ([ctypes.c_void_p, ctypes.POINTER(POINTER_TYPE_INFO), ctypes.c_uint32], wintypes.BOOL),
            "DestroySyntheticPointerDevice": ([ctypes.c_void_p], None),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(u, name)
            function.argtypes, function.restype = arguments, result
        k.GetModuleHandleW.argtypes, k.GetModuleHandleW.restype = [wintypes.LPCWSTR], wintypes.HMODULE
        k.GetCurrentThreadId.argtypes, k.GetCurrentThreadId.restype = [], wintypes.DWORD

    def _listen(self) -> None:
        """独立消息循环内只记录输入；慢速 Trace/界面处理留在运行线程。"""

        hooks = []

        def mouse(code, message, data):
            if code == 0:
                event = ctypes.cast(data, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                self.monitor.record("鼠标", bool(event.flags & 0x1))
            return self.user32.CallNextHookEx(None, code, message, data)

        def keyboard(code, message, data):
            if code == 0:
                event = ctypes.cast(data, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                self.monitor.record("键盘", bool(event.flags & 0x10))
            return self.user32.CallNextHookEx(None, code, message, data)

        # 回调对象必须保留到卸载，防止 ctypes 回调地址被回收。
        callbacks = [self._hook_type(mouse), self._hook_type(keyboard)]
        try:
            self._thread_id = self.kernel32.GetCurrentThreadId()
            message = MSG()
            self.user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 0)
            module = self.kernel32.GetModuleHandleW(None)
            for kind, callback in zip((14, 13), callbacks):
                hook = self.user32.SetWindowsHookExW(kind, callback, module, 0)
                if not hook:
                    raise ctypes.WinError(ctypes.get_last_error())
                hooks.append(hook)
            self._ready.set()
            while not self._closing:
                result = self.user32.GetMessageW(ctypes.byref(message), None, 0, 0)
                if result == -1:
                    raise ctypes.WinError(ctypes.get_last_error())
                if result == 0:
                    if not self._closing:
                        raise RuntimeError("Input monitor message loop exited unexpectedly.")
                    break
        except BaseException as error:
            with self.monitor.lock:
                self.monitor.error = error
        finally:
            for hook in hooks:
                self.user32.UnhookWindowsHookEx(hook)
            self._ready.set()

    def any_pressed(self) -> bool:
        """避免用户仍按住按键、修饰键或鼠标时恢复自动化。"""

        return any(self.user32.GetAsyncKeyState(key) & 0x8000 for key in range(1, 256))

    def client_point(self, hwnd: int, x: int, y: int) -> tuple[int, int]:
        return self.platform.client_to_screen(hwnd, x, y)

    def key(self, virtual_key: int, up: bool) -> None:
        item = INPUT()
        item.type = 1
        item.ki = KEYBDINPUT(virtual_key, self.user32.MapVirtualKeyW(virtual_key, 0),
                           0x2 if up else 0, 0, 0x4C414C43)
        ctypes.set_last_error(0)
        if self.user32.SendInput(1, ctypes.byref(item), ctypes.sizeof(INPUT)) != 1:
            raise ctypes.WinError(ctypes.get_last_error())

    def create_touch(self) -> int:
        device = self.user32.CreateSyntheticPointerDevice(2, 1, 3)
        if not device:
            raise ctypes.WinError(ctypes.get_last_error())
        return device

    def touch(self, device: int, x: int, y: int, phase: str) -> None:
        info = POINTER_TYPE_INFO()
        info.type = 2
        touch = info.touchInfo
        touch.pointerInfo.pointerType = 2
        touch.pointerInfo.pointerId = 1
        touch.pointerInfo.pointerFlags = {"down": 0x10000 | 0x2 | 0x4 | 0x4000,
                                          "move": 0x20000 | 0x2 | 0x4 | 0x4000,
                                          "up": 0x40000}[phase]
        touch.pointerInfo.ptPixelLocation = wintypes.POINT(x, y)
        touch.touchMask = 0x1 | 0x2 | 0x4
        touch.rcContact = touch.rcContactRaw = wintypes.RECT(x - 2, y - 2, x + 2, y + 2)
        touch.orientation, touch.pressure = 90, 32000
        if not self.user32.InjectSyntheticPointerInput(device, ctypes.byref(info), 1):
            raise ctypes.WinError(ctypes.get_last_error())

    def destroy_touch(self, device: int) -> None:
        self.user32.DestroySyntheticPointerDevice(device)

    def close(self) -> None:
        self._closing = True
        if self._thread_id:
            self.user32.PostThreadMessageW(self._thread_id, 0x12, 0, 0)
        self._thread.join()
