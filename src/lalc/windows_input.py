"""Windows 只读输入钩子、前台按键、滚轮与无光标合成触摸。"""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes

from .control import InputActivity, PhysicalInputMonitor
from .focused import WindowError

INPUT_EXTRA_INFO = 0x4C414C43
VK_OEM_JUMP = 0xEA
MOUSE_ACTIONS = {
    0x200: "移动",
    0x201: "左键按下", 0x202: "左键松开", 0x203: "左键双击",
    0x204: "右键按下", 0x205: "右键松开", 0x206: "右键双击",
    0x207: "中键按下", 0x208: "中键松开", 0x209: "中键双击",
}


class LASTINPUTINFO(ctypes.Structure):
    """Windows 会话最近一次输入的计时值。"""

    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


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
        self._physical_keys: set[int] = set()
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
            "GetLastInputInfo": ([ctypes.POINTER(LASTINPUTINFO)], wintypes.BOOL),
            "WindowFromPoint": ([wintypes.POINT], wintypes.HWND),
            "GetAncestor": ([wintypes.HWND, wintypes.UINT], wintypes.HWND),
            "MapVirtualKeyW": ([wintypes.UINT, wintypes.UINT], wintypes.UINT),
            "GetKeyNameTextW": ([wintypes.LONG, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int),
            "SendInput": ([wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int], wintypes.UINT),
            "GetClipCursor": ([ctypes.POINTER(wintypes.RECT)], wintypes.BOOL),
            "GetSystemMetrics": ([ctypes.c_int], ctypes.c_int),
            "CreateSyntheticPointerDevice": ([ctypes.c_uint32, wintypes.ULONG, ctypes.c_uint32], ctypes.c_void_p),
            "InjectSyntheticPointerInput": ([ctypes.c_void_p, ctypes.POINTER(POINTER_TYPE_INFO), ctypes.c_uint32], wintypes.BOOL),
            "DestroySyntheticPointerDevice": ([ctypes.c_void_p], None),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(u, name)
            function.argtypes, function.restype = arguments, result
        k.GetModuleHandleW.argtypes, k.GetModuleHandleW.restype = [wintypes.LPCWSTR], wintypes.HMODULE
        k.GetCurrentThreadId.argtypes, k.GetCurrentThreadId.restype = [], wintypes.DWORD
        k.GetTickCount.argtypes, k.GetTickCount.restype = [], wintypes.DWORD

    def _listen(self) -> None:
        """独立消息循环内只记录输入；慢速 Trace/界面处理留在运行线程。"""

        hooks = []

        def mouse(code, message, data):
            if code == 0:
                try:
                    self._mouse_event(message, ctypes.cast(data, ctypes.POINTER(MSLLHOOKSTRUCT)).contents)
                except BaseException as error:
                    with self.monitor.lock:
                        self.monitor.error = error
            return self.user32.CallNextHookEx(None, code, message, data)

        def keyboard(code, message, data):
            if code == 0:
                try:
                    self._keyboard_event(message, ctypes.cast(data, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents)
                except BaseException as error:
                    with self.monitor.lock:
                        self.monitor.error = error
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

    def _mouse_event(self, message: int, event: MSLLHOOKSTRUCT) -> None:
        """仅前台游戏客户区的按钮按下和滚轮构成接管，移动仅记录活动。"""
        injected = bool(event.flags & 0x1)
        if injected and event.dwExtraInfo == INPUT_EXTRA_INFO:
            return
        hwnd = self.monitor.target_hwnd
        foreground = not injected and bool(hwnd and self.user32.GetForegroundWindow() == hwnd)
        client_point = None
        if foreground and message in {0x201, 0x204, 0x207, 0x20B, 0x20A, 0x20E}:
            point = wintypes.POINT(event.pt.x, event.pt.y)
            rect = wintypes.RECT()
            if not self.user32.ScreenToClient(hwnd, ctypes.byref(point)) or not self.user32.GetClientRect(hwnd, ctypes.byref(rect)):
                raise ctypes.WinError(ctypes.get_last_error())
            hit = self.user32.WindowFromPoint(event.pt)
            if (self.user32.GetAncestor(hit, 2) == hwnd
                    and rect.left <= point.x < rect.right and rect.top <= point.y < rect.bottom):
                client_point = (point.x, point.y)
        delta = None
        if message in {0x20A, 0x20E}:
            delta = ctypes.c_int16(event.mouseData >> 16).value
            if message == 0x20A:
                action = "滚轮向上" if delta > 0 else "滚轮向下" if delta < 0 else "垂直滚轮"
            else:
                action = "滚轮向右" if delta > 0 else "滚轮向左" if delta < 0 else "水平滚轮"
        elif message in {0x20B, 0x20C, 0x20D}:
            button = event.mouseData >> 16
            action = f"侧键 {button} " + {0x20B: "按下", 0x20C: "松开", 0x20D: "双击"}[message]
        else:
            action = MOUSE_ACTIONS.get(message, f"消息 0x{message:04X}")
        detail = InputActivity("鼠标", "外部注入" if injected else "物理", action, wheel_delta=delta)
        self.monitor.record("鼠标", False, takeover=client_point is not None,
                            detail=detail, client_point=client_point)

    def _keyboard_event(self, message: int, event: KBDLLHOOKSTRUCT) -> None:
        """物理按键按前台判定；Ctrl Alt P 不依赖游戏焦点且只暂停。"""
        injected = bool(event.flags & 0x10)
        down = message in {0x100, 0x104}
        if injected and event.dwExtraInfo == INPUT_EXTRA_INFO:
            return
        detail = InputActivity("键盘", "外部注入" if injected else "物理", "按下" if down else "松开",
                               event.vkCode, event.scanCode, bool(event.flags & 0x01))
        if injected:
            self.monitor.record("键盘", False, takeover=False, detail=detail)
            return
        if down:
            self._physical_keys.add(event.vkCode)
        else:
            self._physical_keys.discard(event.vkCode)
        hotkey = (down and event.vkCode == 0x50
                  and bool(self._physical_keys & {0x11, 0xA2, 0xA3})
                  and bool(self._physical_keys & {0x12, 0xA4, 0xA5}))
        foreground = bool(self.monitor.target_hwnd and
                          self.user32.GetForegroundWindow() == self.monitor.target_hwnd)
        self.monitor.record("键盘", False, takeover=down and foreground and not hotkey, pause=hotkey, detail=detail)

    def key_name(self, event: InputActivity) -> str:
        """用钩子的扫描码和扩展位查询 Windows 键名，保留原始键码供比对。"""
        vk = event.vk
        if vk is not None and (0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A):
            return chr(vk)
        if not event.scan_code:
            return ""
        name = ctypes.create_unicode_buffer(128)
        flags = ((event.scan_code & 0xFF) << 16) | (int(event.extended) << 24)
        if self.user32.GetKeyNameTextW(flags, name, len(name)):
            return name.value
        return ""

    def session_idle_seconds(self) -> float | None:
        """会话计时补足钩子漏报，按 GetTickCount 的 32 位时间计算。"""
        last = LASTINPUTINFO(cbSize=ctypes.sizeof(LASTINPUTINFO))
        if not self.user32.GetLastInputInfo(ctypes.byref(last)):
            return None
        return ((self.kernel32.GetTickCount() - last.dwTime) & 0xFFFFFFFF) / 1000

    def any_pressed(self) -> bool:
        """避免用户仍按住按键、修饰键或鼠标时恢复自动化。"""

        return self.first_pressed_key() is not None

    def first_pressed_key(self) -> int | None:
        """返回首个阻塞输入的虚拟键，供等待日志定位。"""
        for key in range(1, 256):
            # #344 的 OEM 键可能仅残留异步按下位；钩子确认的物理按下仍生效。
            if key == VK_OEM_JUMP and key not in self._physical_keys:
                continue
            if self.user32.GetAsyncKeyState(key) & 0x8000:
                return key
        return None

    def client_point(self, hwnd: int, x: int, y: int) -> tuple[int, int]:
        return self.platform.client_to_screen(hwnd, x, y)

    def park_cursor(self, hwnd: int) -> dict:
        """向窗口右下角外侧发送带注入标志的绝对移动，不触发自身物理接管。"""
        rect = wintypes.RECT()
        if not self.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            raise ctypes.WinError(ctypes.get_last_error())
        left, top, width, height = (self.user32.GetSystemMetrics(i) for i in (76, 77, 78, 79))
        x, y = rect.right + 8, rect.bottom + 8
        clip = wintypes.RECT()
        clipped = self.user32.GetClipCursor(ctypes.byref(clip))
        diagnostics = {"target_screen": [x, y],
                       "window_rect": [rect.left, rect.top, rect.right, rect.bottom],
                       "virtual_desktop": [left, top, width, height],
                       "cursor_clip": [clip.left, clip.top, clip.right, clip.bottom] if clipped else None}
        if width <= 1 or height <= 1 or not (left <= x < left + width and top <= y < top + height):
            from .focused import WindowError
            raise WindowError(f"No desktop space beyond the game's bottom-right corner: {diagnostics}")
        item = INPUT()
        item.type = 0
        item.mi = MOUSEINPUT(round((x - left) * 65535 / (width - 1)),
                             round((y - top) * 65535 / (height - 1)), 0,
                             0x0001 | 0x8000 | 0x4000, 0, INPUT_EXTRA_INFO)
        ctypes.set_last_error(0)
        if self.user32.SendInput(1, ctypes.byref(item), ctypes.sizeof(INPUT)) != 1:
            raise OSError(f"SendInput failed: winerror={ctypes.get_last_error()}, {diagnostics}")
        return diagnostics

    def move_cursor(self, x: int, y: int) -> None:
        """按虚拟桌面物理像素移动鼠标；拒绝屏幕外位置。"""
        left, top, width, height = (self.user32.GetSystemMetrics(i) for i in (76, 77, 78, 79))
        if width <= 1 or height <= 1 or not (left <= x < left + width and top <= y < top + height):
            raise WindowError("Cursor target is outside the virtual desktop.")
        item = INPUT()
        item.type = 0
        item.mi = MOUSEINPUT(round((x - left) * 65535 / (width - 1)),
                             round((y - top) * 65535 / (height - 1)), 0,
                             0x0001 | 0x8000 | 0x4000, 0, INPUT_EXTRA_INFO)
        ctypes.set_last_error(0)
        if self.user32.SendInput(1, ctypes.byref(item), ctypes.sizeof(INPUT)) != 1:
            raise OSError(f"Cursor SendInput failed: winerror={ctypes.get_last_error()}")

    def wheel(self, delta: int) -> None:
        """发送一格垂直滚轮输入；负值以 DWORD 补码传递。"""
        item = INPUT()
        item.type = 0
        item.mi = MOUSEINPUT(0, 0, delta & 0xFFFFFFFF, 0x0800, 0, INPUT_EXTRA_INFO)
        ctypes.set_last_error(0)
        if self.user32.SendInput(1, ctypes.byref(item), ctypes.sizeof(INPUT)) != 1:
            raise OSError(f"Wheel SendInput failed: winerror={ctypes.get_last_error()}")

    def key(self, virtual_key: int, up: bool) -> None:
        item = INPUT()
        item.type = 1
        item.ki = KEYBDINPUT(virtual_key, self.user32.MapVirtualKeyW(virtual_key, 0),
                           0x2 if up else 0, 0, INPUT_EXTRA_INFO)
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
