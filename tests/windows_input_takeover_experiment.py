"""Manual Windows experiment for distinguishing user input from injected input.

Run from a Windows terminal at the repository root:

    uv run python tests/windows_input_takeover_experiment.py

This is intentionally not a pytest test. It installs read-only low-level input
hooks, opens its own harmless target window, and guides the developer through
physical input, SendInput, synthetic touch, and an interrupted touch drag.
"""

from __future__ import annotations

import ctypes
import sys
import threading
import time
from collections import Counter
from ctypes import wintypes
from dataclasses import dataclass


if sys.platform != "win32":
    raise SystemExit("This manual experiment must be run on Windows.")


WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
HC_ACTION = 0
WM_QUIT = 0x0012
WM_MOUSEMOVE = 0x0200
LLMHF_INJECTED = 0x00000001
LLKHF_INJECTED = 0x00000010
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
VK_F24 = 0x87
WS_OVERLAPPEDWINDOW = 0x00CF0000
WS_VISIBLE = 0x10000000

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
OUR_INPUT_MARKER = 0x4C414C43

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
LRESULT = ctypes.c_ssize_t
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", wintypes.POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUT_VALUE(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("value",)
    _fields_ = [("type", wintypes.DWORD), ("value", INPUT_VALUE)]


class POINTER_INFO(ctypes.Structure):
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
    _fields_ = [("touchInfo", POINTER_TOUCH_INFO)]


class POINTER_TYPE_INFO(ctypes.Structure):
    _anonymous_ = ("value",)
    _fields_ = [("type", ctypes.c_uint32), ("value", POINTER_TYPE_VALUE)]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
        ("lPrivate", wintypes.DWORD),
    ]


@dataclass(frozen=True)
class ObservedInput:
    phase: str
    kind: str
    injected: bool
    message: int
    detail: int
    observed_at: float


events: list[ObservedInput] = []
events_lock = threading.Lock()
current_phase = "idle"
takeover = threading.Event()
takeover_at: float | None = None


def configure_apis() -> None:
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE
    kernel32.GetCurrentThreadId.argtypes = []
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD
    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HWND,
        ctypes.c_void_p,
        wintypes.HINSTANCE,
        ctypes.c_void_p,
    ]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.DestroyWindow.restype = wintypes.BOOL
    user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    user32.ClientToScreen.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.PostThreadMessageW.argtypes = [
        wintypes.DWORD,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    user32.PostThreadMessageW.restype = wintypes.BOOL
    user32.GetMessageW.argtypes = [
        ctypes.POINTER(MSG),
        wintypes.HWND,
        wintypes.UINT,
        wintypes.UINT,
    ]
    user32.GetMessageW.restype = wintypes.BOOL
    user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
    user32.TranslateMessage.restype = wintypes.BOOL
    user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
    user32.DispatchMessageW.restype = LRESULT
    user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
    user32.MapVirtualKeyW.restype = wintypes.UINT
    user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
    user32.SetWindowsHookExW.restype = wintypes.HHOOK
    user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
    user32.CallNextHookEx.restype = LRESULT
    user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
    user32.UnhookWindowsHookEx.restype = wintypes.BOOL
    user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    user32.SendInput.restype = wintypes.UINT
    user32.CreateSyntheticPointerDevice.argtypes = [ctypes.c_uint32, wintypes.ULONG, ctypes.c_uint32]
    user32.CreateSyntheticPointerDevice.restype = ctypes.c_void_p
    user32.InjectSyntheticPointerInput.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(POINTER_TYPE_INFO),
        ctypes.c_uint32,
    ]
    user32.InjectSyntheticPointerInput.restype = wintypes.BOOL
    user32.DestroySyntheticPointerDevice.argtypes = [ctypes.c_void_p]
    user32.DestroySyntheticPointerDevice.restype = None


def record(kind: str, injected: bool, message: int, detail: int) -> None:
    global takeover_at
    observed_at = time.perf_counter()
    with events_lock:
        events.append(
            ObservedInput(current_phase, kind, injected, message, detail, observed_at)
        )
    if current_phase == "overlap" and not injected and not takeover.is_set():
        takeover_at = observed_at
        takeover.set()


@HOOKPROC
def mouse_hook(code: int, message: int, data: int) -> int:
    if code == HC_ACTION:
        item = ctypes.cast(data, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
        record("mouse", bool(item.flags & LLMHF_INJECTED), message, item.flags)
    return user32.CallNextHookEx(None, code, message, data)


@HOOKPROC
def keyboard_hook(code: int, message: int, data: int) -> int:
    if code == HC_ACTION:
        item = ctypes.cast(data, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        record("keyboard", bool(item.flags & LLKHF_INJECTED), message, item.vkCode)
    return user32.CallNextHookEx(None, code, message, data)


def set_phase(name: str) -> None:
    global current_phase, takeover_at
    takeover.clear()
    takeover_at = None
    current_phase = name


def phase_events(name: str) -> list[ObservedInput]:
    with events_lock:
        return [item for item in events if item.phase == name]


def wait_for_enter(message: str) -> None:
    set_phase("idle")
    input(f"\n{message}\n按 Enter 开始... ")
    time.sleep(0.25)


def countdown(seconds: int) -> None:
    for remaining in range(seconds, 0, -1):
        print(f"  {remaining}...", flush=True)
        time.sleep(1)


def send_f24() -> None:
    inputs = (INPUT * 2)()
    for index, flags in enumerate((0, KEYEVENTF_KEYUP)):
        inputs[index].type = INPUT_KEYBOARD
        inputs[index].ki = KEYBDINPUT(
            VK_F24,
            user32.MapVirtualKeyW(VK_F24, 0),
            flags,
            0,
            OUR_INPUT_MARKER,
        )
    if user32.SendInput(2, inputs, ctypes.sizeof(INPUT)) != 2:
        raise ctypes.WinError(ctypes.get_last_error())


def touch_info(x: int, y: int, flags: int) -> POINTER_TYPE_INFO:
    info = POINTER_TYPE_INFO()
    info.type = PT_TOUCH
    info.touchInfo.pointerInfo.pointerType = PT_TOUCH
    info.touchInfo.pointerInfo.pointerId = 1
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


def inject_touch(device: int, x: int, y: int, flags: int) -> None:
    info = touch_info(x, y, flags)
    if not user32.InjectSyntheticPointerInput(device, ctypes.byref(info), 1):
        raise ctypes.WinError(ctypes.get_last_error())


def client_point(hwnd: int, x: int, y: int) -> tuple[int, int]:
    point = wintypes.POINT(x, y)
    if not user32.ClientToScreen(hwnd, ctypes.byref(point)):
        raise ctypes.WinError(ctypes.get_last_error())
    return point.x, point.y


def create_touch_device() -> int:
    device = user32.CreateSyntheticPointerDevice(PT_TOUCH, 1, POINTER_FEEDBACK_NONE)
    if not device:
        raise ctypes.WinError(ctypes.get_last_error())
    return device


def synthetic_touch_click(hwnd: int) -> None:
    device = create_touch_device()
    x, y = client_point(hwnd, 320, 130)
    down = POINTER_FLAG_DOWN | POINTER_FLAG_INRANGE | POINTER_FLAG_INCONTACT | POINTER_FLAG_CONFIDENCE
    try:
        inject_touch(device, x, y, down)
        time.sleep(0.08)
        inject_touch(device, x, y, POINTER_FLAG_UP)
    finally:
        user32.DestroySyntheticPointerDevice(device)


def synthetic_touch_drag(hwnd: int, duration: float = 2.5) -> tuple[bool, float | None]:
    device = create_touch_device()
    start = client_point(hwnd, 100, 130)
    end = client_point(hwnd, 540, 130)
    current = start
    contact_down = False
    released_at: float | None = None
    down = POINTER_FLAG_DOWN | POINTER_FLAG_INRANGE | POINTER_FLAG_INCONTACT | POINTER_FLAG_CONFIDENCE
    update = POINTER_FLAG_UPDATE | POINTER_FLAG_INRANGE | POINTER_FLAG_INCONTACT | POINTER_FLAG_CONFIDENCE
    started = time.perf_counter()
    try:
        inject_touch(device, *start, down)
        contact_down = True
        while time.perf_counter() - started < duration and not takeover.is_set():
            ratio = min(1.0, (time.perf_counter() - started) / duration)
            current = (
                round(start[0] + (end[0] - start[0]) * ratio),
                round(start[1] + (end[1] - start[1]) * ratio),
            )
            inject_touch(device, *current, update)
            time.sleep(0.012)
    finally:
        if contact_down:
            inject_touch(device, *current, POINTER_FLAG_UP)
            released_at = time.perf_counter()
        user32.DestroySyntheticPointerDevice(device)
    latency_ms = None
    if takeover_at is not None and released_at is not None:
        latency_ms = (released_at - takeover_at) * 1000
    return takeover.is_set(), latency_ms


def summarize(name: str) -> Counter[tuple[str, str]]:
    counts = Counter(
        (item.kind, "injected" if item.injected else "physical")
        for item in phase_events(name)
    )
    print(
        "  "
        + ", ".join(
            f"{kind}/{source}={counts[kind, source]}"
            for kind in ("mouse", "keyboard")
            for source in ("physical", "injected")
        )
    )
    return counts


def run_guided_experiment(hwnd: int, message_thread_id: int) -> None:
    try:
        print(
            "LALC 用户接管检测实验\n"
            "- 不会屏蔽任何输入。\n"
            "- 合成触摸只发送到新打开的实验窗口。\n"
            "- 随时可在终端按 Ctrl+C 结束。\n"
        )

        wait_for_enter("步骤 1/4：接下来 4 秒内，请移动物理鼠标，并按一下 A 键。")
        set_phase("physical")
        countdown(4)
        physical = summarize("physical")

        wait_for_enter("步骤 2/4：程序将自动注入一次 F24 按下和抬起；请不要碰键鼠。")
        set_phase("send_input")
        send_f24()
        time.sleep(0.5)
        injected_key = summarize("send_input")

        wait_for_enter("步骤 3/4：程序将在实验窗口中央注入一次合成触摸；请不要碰键鼠。")
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.3)
        set_phase("touch")
        synthetic_touch_click(hwnd)
        time.sleep(0.5)
        touch = summarize("touch")

        wait_for_enter(
            "步骤 4/4：倒计时后程序开始 2.5 秒合成拖拽。"
            "请在拖拽开始后持续移动物理鼠标。"
        )
        countdown(3)
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.3)
        set_phase("overlap")
        aborted, latency_ms = synthetic_touch_drag(hwnd)
        time.sleep(0.3)
        overlap = summarize("overlap")

        print("\n=== 结果 ===")
        checks = {
            "物理鼠标可识别": physical["mouse", "physical"] > 0,
            "物理键盘可识别": physical["keyboard", "physical"] > 0,
            "SendInput 未伪装成物理键盘": (
                injected_key["keyboard", "injected"] > 0
                and injected_key["keyboard", "physical"] == 0
            ),
            "合成触摸未伪装成物理鼠标": touch["mouse", "physical"] == 0,
            "拖拽期间检测到用户接管并释放": aborted,
        }
        for label, passed in checks.items():
            print(f"[{'PASS' if passed else 'FAIL'}] {label}")
        if latency_ms is not None:
            print(f"接管事件到触点释放：{latency_ms:.1f} ms")
        if overlap["mouse", "physical"] == 0:
            print("[提示] 最后一步没有观察到物理鼠标事件；请重跑并在拖拽期间移动鼠标。")
        print(
            "\n结论：只有全部 PASS，低级输入钩子才足以支持本机的"
            "“用户接管后中止长动作”实验；否则不要据此实现自动恢复。"
        )
    except (EOFError, KeyboardInterrupt):
        print("\n实验已取消。")
    except BaseException as error:
        print(f"\n实验失败：{type(error).__name__}: {error}")
    finally:
        set_phase("idle")
        user32.PostThreadMessageW(message_thread_id, WM_QUIT, 0, 0)


def main() -> int:
    configure_apis()
    instance = kernel32.GetModuleHandleW(None)
    hwnd = user32.CreateWindowExW(
        0,
        "STATIC",
        "LALC Input Takeover Experiment - synthetic touch target",
        WS_OVERLAPPEDWINDOW | WS_VISIBLE,
        160,
        160,
        680,
        330,
        None,
        None,
        instance,
        None,
    )
    if not hwnd:
        raise ctypes.WinError(ctypes.get_last_error())

    mouse = user32.SetWindowsHookExW(WH_MOUSE_LL, mouse_hook, instance, 0)
    keyboard = user32.SetWindowsHookExW(WH_KEYBOARD_LL, keyboard_hook, instance, 0)
    if not mouse or not keyboard:
        error_code = ctypes.get_last_error()
        if mouse:
            user32.UnhookWindowsHookEx(mouse)
        if keyboard:
            user32.UnhookWindowsHookEx(keyboard)
        user32.DestroyWindow(hwnd)
        raise ctypes.WinError(error_code)

    message_thread_id = kernel32.GetCurrentThreadId()
    worker = threading.Thread(
        target=run_guided_experiment,
        args=(hwnd, message_thread_id),
        name="guided-input-experiment",
        daemon=True,
    )
    worker.start()
    message = MSG()
    try:
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))
    finally:
        user32.UnhookWindowsHookEx(mouse)
        user32.UnhookWindowsHookEx(keyboard)
        user32.DestroyWindow(hwnd)
    worker.join(2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
