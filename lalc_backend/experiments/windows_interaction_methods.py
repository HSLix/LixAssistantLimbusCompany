"""Experimental Windows input methods that go beyond plain window messages.

The functions in this module intentionally remain independent from the normal
input pipeline.  They are designed for one-variable-at-a-time experiments on a
visible, non-minimized Unity window that does not own foreground focus.
"""

from __future__ import annotations

import ctypes
import os
import threading
import time
from ctypes import wintypes

import win32api
import win32con
import win32gui


DEFAULT_TIMEOUT_MS = 1000
TOUCH_TICK_SECONDS = 0.012

PT_TOUCH = 2
POINTER_FEEDBACK_NONE = 3
POINTER_FLAG_INRANGE = 0x00000002
POINTER_FLAG_INCONTACT = 0x00000004
POINTER_FLAG_CONFIDENCE = 0x00004000
POINTER_FLAG_DOWN = 0x00010000
POINTER_FLAG_UPDATE = 0x00020000
POINTER_FLAG_UP = 0x00040000
TOUCH_MASK_CONTACTAREA = 0x00000001
TOUCH_MASK_ORIENTATION = 0x00000002
TOUCH_MASK_PRESSURE = 0x00000004
WM_POINTERUPDATE = 0x0245
WM_POINTERDOWN = 0x0246
WM_POINTERUP = 0x0247

_cursor_lock = threading.RLock()
_managed_key_lock = threading.RLock()
_user32 = ctypes.WinDLL("user32", use_last_error=True)


class ExperimentalInputError(RuntimeError):
    """Raised when an experimental input operation cannot be completed safely."""


class _POINTER_INFO(ctypes.Structure):
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


class _POINTER_TOUCH_INFO(ctypes.Structure):
    _fields_ = [
        ("pointerInfo", _POINTER_INFO),
        ("touchFlags", ctypes.c_uint32),
        ("touchMask", ctypes.c_uint32),
        ("rcContact", wintypes.RECT),
        ("rcContactRaw", wintypes.RECT),
        ("orientation", ctypes.c_uint32),
        ("pressure", ctypes.c_uint32),
    ]


class _POINTER_TYPE_INFO(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_uint32),
        ("touchInfo", _POINTER_TOUCH_INFO),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", _MOUSEINPUT),
        ("ki", _KEYBDINPUT),
        ("hi", _HARDWAREINPUT),
    ]


class _INPUT(ctypes.Structure):
    _anonymous_ = ("value",)
    _fields_ = [("type", wintypes.DWORD), ("value", _INPUT_UNION)]


class _MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", wintypes.UINT),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_ssize_t),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
        ("lPrivate", wintypes.DWORD),
    ]


def _require_client_point(hwnd: int, x: int, y: int) -> tuple[int, int]:
    if not hwnd or not win32gui.IsWindow(hwnd):
        raise ExperimentalInputError(f"窗口句柄无效：{hwnd}")
    if win32gui.IsIconic(hwnd):
        raise ExperimentalInputError("目标窗口已最小化")
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    x, y = int(x), int(y)
    if not (left <= x < right and top <= y < bottom):
        raise ExperimentalInputError(
            f"客户区坐标 ({x}, {y}) 超出范围 0..{right - 1}, 0..{bottom - 1}"
        )
    return x, y


def _send_message(
    hwnd: int,
    message: int,
    wparam: int = 0,
    lparam: int = 0,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> None:
    if timeout_ms <= 0:
        raise ValueError("timeout_ms 必须大于 0")
    flags = win32con.SMTO_ABORTIFHUNG | win32con.SMTO_BLOCK
    try:
        win32gui.SendMessageTimeout(
            hwnd, message, wparam, lparam, flags, timeout_ms
        )
    except win32gui.error as exc:
        raise ExperimentalInputError(
            f"同步窗口消息失败或超时（message=0x{message:04X}）"
        ) from exc


def _activate_hint(hwnd: int, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> None:
    _send_message(hwnd, win32con.WM_ACTIVATE, win32con.WA_ACTIVE, 0, timeout_ms)
    time.sleep(0.01)


def _deactivate_hint(hwnd: int, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> None:
    _send_message(hwnd, win32con.WM_ACTIVATE, win32con.WA_INACTIVE, 0, timeout_ms)


def _client_to_screen(hwnd: int, x: int, y: int) -> tuple[int, int]:
    _require_client_point(hwnd, x, y)
    return tuple(map(int, win32gui.ClientToScreen(hwnd, (x, y))))


def activate_cursor_click(
    hwnd: int,
    x: int,
    y: int,
    hold_seconds: float = 0.05,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> None:
    """Click using a fake activation hint and a briefly aligned real cursor."""

    if hold_seconds < 0:
        raise ValueError("hold_seconds 不能为负数")
    position = win32api.MAKELONG(*_require_client_point(hwnd, x, y))
    screen = _client_to_screen(hwnd, x, y)

    with _cursor_lock:
        original = win32api.GetCursorPos()
        _activate_hint(hwnd, timeout_ms)
        try:
            win32api.SetCursorPos(screen)
            time.sleep(0.01)
            _send_message(hwnd, win32con.WM_MOUSEMOVE, 0, position, timeout_ms)
            _send_message(
                hwnd,
                win32con.WM_LBUTTONDOWN,
                win32con.MK_LBUTTON,
                position,
                timeout_ms,
            )
            time.sleep(hold_seconds)
            _send_message(hwnd, win32con.WM_LBUTTONUP, 0, position, timeout_ms)
            time.sleep(0.02)
        finally:
            win32api.SetCursorPos(original)
            _deactivate_hint(hwnd, timeout_ms)


def activate_cursor_long_press(
    hwnd: int,
    x: int,
    y: int,
    duration: float,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> None:
    if duration <= 0:
        raise ValueError("duration 必须大于 0")
    activate_cursor_click(hwnd, x, y, duration, timeout_ms)


def activate_cursor_drag(
    hwnd: int,
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    duration: float = 0.5,
    steps: int = 30,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> None:
    """Drag while keeping the physical cursor aligned with every message point."""

    if duration <= 0:
        raise ValueError("duration 必须大于 0")
    if steps < 1:
        raise ValueError("steps 必须至少为 1")
    _require_client_point(hwnd, start_x, start_y)
    _require_client_point(hwnd, end_x, end_y)

    with _cursor_lock:
        original = win32api.GetCursorPos()
        _activate_hint(hwnd, timeout_ms)
        last_position = win32api.MAKELONG(start_x, start_y)
        try:
            win32api.SetCursorPos(_client_to_screen(hwnd, start_x, start_y))
            time.sleep(0.01)
            _send_message(hwnd, win32con.WM_MOUSEMOVE, 0, last_position, timeout_ms)
            _send_message(
                hwnd,
                win32con.WM_LBUTTONDOWN,
                win32con.MK_LBUTTON,
                last_position,
                timeout_ms,
            )
            delay = duration / steps
            for index in range(1, steps + 1):
                ratio = index / steps
                x = round(start_x + (end_x - start_x) * ratio)
                y = round(start_y + (end_y - start_y) * ratio)
                last_position = win32api.MAKELONG(x, y)
                win32api.SetCursorPos(_client_to_screen(hwnd, x, y))
                _send_message(
                    hwnd,
                    win32con.WM_MOUSEMOVE,
                    win32con.MK_LBUTTON,
                    last_position,
                    timeout_ms,
                )
                time.sleep(delay)
        finally:
            try:
                _send_message(
                    hwnd, win32con.WM_LBUTTONUP, 0, last_position, timeout_ms
                )
                time.sleep(0.02)
            finally:
                win32api.SetCursorPos(original)
                _deactivate_hint(hwnd, timeout_ms)


def _configure_keyboard_api() -> None:
    _user32.RegisterHotKey.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        wintypes.UINT,
        wintypes.UINT,
    ]
    _user32.RegisterHotKey.restype = wintypes.BOOL
    _user32.UnregisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int]
    _user32.UnregisterHotKey.restype = wintypes.BOOL
    _user32.SendInput.argtypes = [
        wintypes.UINT,
        ctypes.POINTER(_INPUT),
        ctypes.c_int,
    ]
    _user32.SendInput.restype = wintypes.UINT
    _user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    _user32.GetAsyncKeyState.restype = ctypes.c_short
    _user32.PeekMessageW.argtypes = [
        ctypes.POINTER(_MSG),
        ctypes.c_void_p,
        wintypes.UINT,
        wintypes.UINT,
        wintypes.UINT,
    ]
    _user32.PeekMessageW.restype = wintypes.BOOL


def _is_key_pressed(vk_code: int) -> bool:
    return bool(_user32.GetAsyncKeyState(vk_code) & 0x8000)


def _send_input_key(vk_code: int, key_up: bool) -> None:
    event = _INPUT()
    event.type = 1  # INPUT_KEYBOARD
    event.ki.wVk = vk_code
    event.ki.wScan = win32api.MapVirtualKey(vk_code, 0)
    event.ki.dwFlags = win32con.KEYEVENTF_KEYUP if key_up else 0
    if _user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(_INPUT)) != 1:
        raise ExperimentalInputError(
            f"SendInput 失败，Win32 error={ctypes.get_last_error()}"
        )


def _remove_hotkey_messages(hotkey_id: int) -> None:
    message = _MSG()
    while _user32.PeekMessageW(
        ctypes.byref(message), None, win32con.WM_HOTKEY, win32con.WM_HOTKEY, 1
    ):
        pass


def managed_key_press(
    hwnd: int,
    vk_code: int,
    hold_seconds: float = 0.05,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> None:
    """Expose a real global key state while swallowing the corresponding hotkey."""

    if hold_seconds < 0:
        raise ValueError("hold_seconds 不能为负数")
    if not 0 < vk_code <= 0xFF:
        raise ValueError("vk_code 必须是 1..255")
    _require_client_point(hwnd, 0, 0)

    with _managed_key_lock:
        _configure_keyboard_api()
        if _is_key_pressed(vk_code):
            raise ExperimentalInputError(
                "目标按键当前已被用户按住，取消实验"
            )

        message = _MSG()
        _user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 0)
        hotkey_id = 0x4C00 + vk_code
        if not _user32.RegisterHotKey(None, hotkey_id, 0, vk_code):
            raise ExperimentalInputError(
                "无法注册临时全局热键；"
                "为避免按键进入当前前台程序，已取消实验"
            )

        key_is_down = False
        try:
            _activate_hint(hwnd, timeout_ms)
            _send_input_key(vk_code, key_up=False)
            key_is_down = True

            deadline = time.monotonic() + 0.2
            while not _is_key_pressed(vk_code) and time.monotonic() < deadline:
                time.sleep(0.001)
            if not _is_key_pressed(vk_code):
                raise ExperimentalInputError(
                    "系统异步键状态没有进入按下状态"
                )

            time.sleep(hold_seconds)
        finally:
            try:
                if key_is_down:
                    _send_input_key(vk_code, key_up=True)
                    deadline = time.monotonic() + 0.2
                    while _is_key_pressed(vk_code) and time.monotonic() < deadline:
                        time.sleep(0.001)
            finally:
                _remove_hotkey_messages(hotkey_id)
                _user32.UnregisterHotKey(None, hotkey_id)
                _deactivate_hint(hwnd, timeout_ms)

        if _is_key_pressed(vk_code):
            raise ExperimentalInputError(
                "按键抬起状态校验失败；请手动按下并松开该键"
            )


def _configure_touch_api() -> tuple[object, object, object]:
    try:
        create = _user32.CreateSyntheticPointerDevice
        inject = _user32.InjectSyntheticPointerInput
        destroy = _user32.DestroySyntheticPointerDevice
    except AttributeError as exc:
        raise ExperimentalInputError(
            "系统不支持合成触摸；需要 Windows 10 1809 或更高版本"
        ) from exc

    create.argtypes = [ctypes.c_uint32, wintypes.ULONG, ctypes.c_uint32]
    create.restype = ctypes.c_void_p
    inject.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(_POINTER_TYPE_INFO),
        ctypes.c_uint32,
    ]
    inject.restype = wintypes.BOOL
    destroy.argtypes = [ctypes.c_void_p]
    destroy.restype = None
    return create, inject, destroy


def _make_touch_info(
    pointer_id: int, x: int, y: int, flags: int
) -> _POINTER_TYPE_INFO:
    info = _POINTER_TYPE_INFO()
    info.type = PT_TOUCH
    info.touchInfo.pointerInfo.pointerType = PT_TOUCH
    info.touchInfo.pointerInfo.pointerId = pointer_id
    info.touchInfo.pointerInfo.pointerFlags = flags
    info.touchInfo.pointerInfo.ptPixelLocation = wintypes.POINT(x, y)
    info.touchInfo.touchMask = (
        TOUCH_MASK_CONTACTAREA | TOUCH_MASK_ORIENTATION | TOUCH_MASK_PRESSURE
    )
    info.touchInfo.rcContact = wintypes.RECT(x - 2, y - 2, x + 2, y + 2)
    info.touchInfo.rcContactRaw = info.touchInfo.rcContact
    info.touchInfo.orientation = 90
    info.touchInfo.pressure = 32000
    return info


def _touch_flags(kind: str) -> int:
    if kind == "down":
        return (
            POINTER_FLAG_DOWN
            | POINTER_FLAG_INRANGE
            | POINTER_FLAG_INCONTACT
            | POINTER_FLAG_CONFIDENCE
        )
    if kind == "update":
        return (
            POINTER_FLAG_UPDATE
            | POINTER_FLAG_INRANGE
            | POINTER_FLAG_INCONTACT
            | POINTER_FLAG_CONFIDENCE
        )
    if kind == "up":
        return POINTER_FLAG_UP
    raise ValueError(f"未知触摸状态：{kind}")


def _window_owns_point(hwnd: int, screen_x: int, screen_y: int) -> bool:
    hit = win32gui.WindowFromPoint((screen_x, screen_y))
    if not hit:
        return False
    root = win32gui.GetAncestor(hit, win32con.GA_ROOT)
    return hit == hwnd or root == hwnd or win32gui.IsChild(hwnd, hit)


def _assert_touch_path_visible(
    hwnd: int, start: tuple[int, int], end: tuple[int, int]
) -> None:
    for index in range(11):
        ratio = index / 10
        client_x = round(start[0] + (end[0] - start[0]) * ratio)
        client_y = round(start[1] + (end[1] - start[1]) * ratio)
        screen_x, screen_y = _client_to_screen(hwnd, client_x, client_y)
        if not _window_owns_point(hwnd, screen_x, screen_y):
            raise ExperimentalInputError(
                "合成触摸目标点被其他窗口遮挡；"
                "安全版不会把输入发送给遮挡窗口。"
                "请先在游戏可见但未聚焦的状态测试"
            )


def _anchor_origin(hwnd: int) -> tuple[int, int]:
    left = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
    top = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
    right = left + win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
    bottom = top + win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
    candidates = (
        (left + 8, top + 8),
        (right - 12, top + 8),
        (left + 8, bottom - 12),
        (right - 12, bottom - 12),
    )
    window = win32gui.GetWindowRect(hwnd)
    for x, y in candidates:
        overlaps_target = (
            x < window[2]
            and x + 4 > window[0]
            and y < window[3]
            and y + 4 > window[1]
        )
        if not overlaps_target:
            return x, y
    return candidates[0]


def _inject_touch_frame(
    inject: object, device: int, infos: list[_POINTER_TYPE_INFO]
) -> None:
    frame_type = _POINTER_TYPE_INFO * len(infos)
    frame = frame_type(*infos)
    if not inject(device, frame, len(infos)):
        raise ExperimentalInputError(
            "InjectSyntheticPointerInput 失败，"
            f"Win32 error={ctypes.get_last_error()}"
        )


def _run_anchored_touch(
    hwnd: int,
    start: tuple[int, int],
    end: tuple[int, int],
    duration: float,
) -> None:
    create, inject, destroy = _configure_touch_api()
    class_name = f"LalcTouchAnchor_{os.getpid()}_{threading.get_ident()}"
    instance = win32api.GetModuleHandle(None)
    pointer_messages = {WM_POINTERUPDATE, WM_POINTERDOWN, WM_POINTERUP}

    def anchor_window_proc(window: int, message: int, wparam: int, lparam: int) -> int:
        if message in pointer_messages:
            return 0
        return win32gui.DefWindowProc(window, message, wparam, lparam)

    wc = win32gui.WNDCLASS()
    wc.hInstance = instance
    wc.lpszClassName = class_name
    wc.lpfnWndProc = anchor_window_proc
    win32gui.RegisterClass(wc)

    anchor = 0
    device = 0
    anchor_down = False
    target_down = False
    target_screen = _client_to_screen(hwnd, *start)
    anchor_x, anchor_y = _anchor_origin(hwnd)
    anchor_point = (anchor_x + 2, anchor_y + 2)

    try:
        exstyle = (
            win32con.WS_EX_NOACTIVATE
            | win32con.WS_EX_TOOLWINDOW
            | win32con.WS_EX_TOPMOST
            | win32con.WS_EX_LAYERED
        )
        anchor = win32gui.CreateWindowEx(
            exstyle,
            class_name,
            "",
            win32con.WS_POPUP,
            anchor_x,
            anchor_y,
            4,
            4,
            0,
            0,
            instance,
            None,
        )
        win32gui.SetLayeredWindowAttributes(anchor, 0, 1, win32con.LWA_ALPHA)
        win32gui.ShowWindow(anchor, win32con.SW_SHOWNOACTIVATE)
        win32gui.PumpWaitingMessages()

        device = create(PT_TOUCH, 2, POINTER_FEEDBACK_NONE)
        if not device:
            raise ExperimentalInputError(
                "CreateSyntheticPointerDevice 失败，"
                f"Win32 error={ctypes.get_last_error()}"
            )

        _inject_touch_frame(
            inject,
            device,
            [_make_touch_info(1, *anchor_point, _touch_flags("down"))],
        )
        anchor_down = True
        win32gui.PumpWaitingMessages()
        time.sleep(TOUCH_TICK_SECONDS)

        _inject_touch_frame(
            inject,
            device,
            [
                _make_touch_info(1, *anchor_point, _touch_flags("update")),
                _make_touch_info(2, *target_screen, _touch_flags("down")),
            ],
        )
        target_down = True
        started = time.monotonic()

        while True:
            elapsed = time.monotonic() - started
            if elapsed >= duration:
                break
            ratio = min(1.0, elapsed / duration) if duration else 1.0
            client_x = round(start[0] + (end[0] - start[0]) * ratio)
            client_y = round(start[1] + (end[1] - start[1]) * ratio)
            target_screen = _client_to_screen(hwnd, client_x, client_y)
            _inject_touch_frame(
                inject,
                device,
                [
                    _make_touch_info(1, *anchor_point, _touch_flags("update")),
                    _make_touch_info(2, *target_screen, _touch_flags("update")),
                ],
            )
            win32gui.PumpWaitingMessages()
            time.sleep(TOUCH_TICK_SECONDS)

        target_screen = _client_to_screen(hwnd, *end)
        _inject_touch_frame(
            inject,
            device,
            [
                _make_touch_info(1, *anchor_point, _touch_flags("update")),
                _make_touch_info(2, *target_screen, _touch_flags("up")),
            ],
        )
        target_down = False
        time.sleep(TOUCH_TICK_SECONDS)
        _inject_touch_frame(
            inject,
            device,
            [_make_touch_info(1, *anchor_point, _touch_flags("up"))],
        )
        anchor_down = False
        win32gui.PumpWaitingMessages()
    finally:
        if device and target_down:
            try:
                _inject_touch_frame(
                    inject,
                    device,
                    [
                        _make_touch_info(1, *anchor_point, _touch_flags("update")),
                        _make_touch_info(2, *target_screen, _touch_flags("up")),
                    ],
                )
            except Exception:
                pass
        if device and anchor_down:
            try:
                _inject_touch_frame(
                    inject,
                    device,
                    [_make_touch_info(1, *anchor_point, _touch_flags("up"))],
                )
            except Exception:
                pass
        if device:
            destroy(device)
        if anchor:
            win32gui.DestroyWindow(anchor)
        try:
            win32gui.UnregisterClass(class_name, instance)
        except win32gui.error:
            pass


def anchored_touch_drag(
    hwnd: int,
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    duration: float = 0.5,
) -> None:
    """Inject a pure touch gesture without moving the cursor or foreground."""

    if duration <= 0:
        raise ValueError("duration 必须大于 0")
    start = _require_client_point(hwnd, start_x, start_y)
    end = _require_client_point(hwnd, end_x, end_y)
    _assert_touch_path_visible(hwnd, start, end)

    errors: list[BaseException] = []

    def run() -> None:
        try:
            _run_anchored_touch(hwnd, start, end, duration)
        except BaseException as exc:
            errors.append(exc)

    worker = threading.Thread(target=run, name="lalc-anchored-touch")
    worker.start()
    worker.join()
    if errors:
        raise errors[0]


def anchored_touch_click(
    hwnd: int, x: int, y: int, hold_seconds: float = 0.05
) -> None:
    if hold_seconds <= 0:
        raise ValueError("hold_seconds 必须大于 0")
    anchored_touch_drag(hwnd, x, y, x, y, hold_seconds)


def anchored_touch_long_press(
    hwnd: int, x: int, y: int, duration: float
) -> None:
    anchored_touch_click(hwnd, x, y, duration)
