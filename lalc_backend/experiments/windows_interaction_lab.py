"""Standalone Win32 interaction experiments for the Limbus Company window.

This module deliberately stays separate from ``input_handler``.  It exists to
measure what the Unity player accepts while visible but not necessarily focused.
All mouse coordinates passed to window messages are client-area coordinates.
"""

from __future__ import annotations

import argparse
import ctypes
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import win32api
import win32con
import win32gui
import win32ui
from PIL import Image


DEFAULT_WINDOW_TITLE = "LimbusCompany"
DEFAULT_WINDOW_CLASS = "UnityWndClass"
PW_CLIENTONLY = 0x00000001
PW_RENDERFULLCONTENT = 0x00000002
SUPPORTED_KEYS = {
    "esc": win32con.VK_ESCAPE,
    "p": ord("P"),
    "enter": win32con.VK_RETURN,
}
DELIVERY_MODES = ("post", "send")
DEFAULT_SEND_TIMEOUT_MS = 1000

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.PrintWindow.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
_user32.PrintWindow.restype = ctypes.c_bool


class InteractionLabError(RuntimeError):
    """Raised when a Win32 experiment cannot be performed."""


@dataclass(frozen=True)
class MousePosition:
    """A cursor sample in both screen and target-client coordinates."""

    screen_x: int
    screen_y: int
    client_x: int
    client_y: int
    inside_client: bool


def enable_per_monitor_dpi_awareness() -> None:
    """Request physical-pixel coordinates for the current process.

    Windows only permits setting process DPI awareness once.  A failure here
    commonly means an embedding process already selected a mode, so the lab
    continues and reports the coordinates it receives from Windows.
    """

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        pass


def find_target_window(
    title: str = DEFAULT_WINDOW_TITLE,
    window_class: str = DEFAULT_WINDOW_CLASS,
) -> int:
    """Return the target Unity window handle or raise a descriptive error."""

    hwnd = win32gui.FindWindow(window_class, title)
    if not hwnd or not win32gui.IsWindow(hwnd):
        raise InteractionLabError(
            f"未找到目标窗口（class={window_class!r}, title={title!r}）"
        )
    return hwnd


def _require_window(hwnd: int) -> None:
    if not hwnd or not win32gui.IsWindow(hwnd):
        raise InteractionLabError(f"窗口句柄无效：{hwnd}")


def _client_size(hwnd: int) -> tuple[int, int]:
    _require_window(hwnd)
    if win32gui.IsIconic(hwnd):
        raise InteractionLabError(
            "目标窗口已最小化；当前实验只支持未最小化窗口（允许失焦或被遮挡）"
        )
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    width = right - left
    height = bottom - top
    if width <= 0 or height <= 0:
        raise InteractionLabError(f"客户区尺寸无效：{width}x{height}")
    return width, height


def _client_lparam(hwnd: int, x: int, y: int) -> int:
    width, height = _client_size(hwnd)
    x = int(x)
    y = int(y)
    if not (0 <= x < width and 0 <= y < height):
        raise InteractionLabError(
            f"客户区坐标 ({x}, {y}) 超出范围 0..{width - 1}, 0..{height - 1}"
        )
    return win32api.MAKELONG(x, y)


def _dispatch_message(
    hwnd: int,
    message: int,
    wparam: int,
    lparam: int,
    delivery: str,
    timeout_ms: int,
) -> None:
    """Deliver one message asynchronously (post) or synchronously (send)."""

    if delivery not in DELIVERY_MODES:
        raise ValueError(f"delivery 必须是 {', '.join(DELIVERY_MODES)}")
    if timeout_ms <= 0:
        raise ValueError("timeout_ms 必须大于 0")

    if delivery == "post":
        win32gui.PostMessage(hwnd, message, wparam, lparam)
        return

    flags = win32con.SMTO_ABORTIFHUNG | win32con.SMTO_BLOCK
    try:
        win32gui.SendMessageTimeout(
            hwnd, message, wparam, lparam, flags, timeout_ms
        )
    except win32gui.error as exc:
        raise InteractionLabError(
            f"SendMessageTimeout 失败或超时（message=0x{message:04X}）"
        ) from exc


def capture_background(hwnd: int, save_path: str | Path | None = None) -> Image.Image:
    """Capture the target client area with PrintWindow.

    The call does not focus, restore, move, or resize the target.  Whether a
    minimized Unity player supplies a fresh frame is intentionally left for the
    experiment to establish.
    """

    width, height = _client_size(hwnd)
    window_dc = None
    source_dc = None
    memory_dc = None
    bitmap = None

    try:
        window_dc = win32gui.GetWindowDC(hwnd)
        if not window_dc:
            raise InteractionLabError("GetWindowDC 失败")

        source_dc = win32ui.CreateDCFromHandle(window_dc)
        memory_dc = source_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(source_dc, width, height)
        memory_dc.SelectObject(bitmap)

        flags = PW_CLIENTONLY | PW_RENDERFULLCONTENT
        if not _user32.PrintWindow(hwnd, memory_dc.GetSafeHdc(), flags):
            error_code = ctypes.get_last_error()
            raise InteractionLabError(f"PrintWindow 失败，Win32 error={error_code}")

        bitmap_info = bitmap.GetInfo()
        bitmap_bits = bitmap.GetBitmapBits(True)
        image = Image.frombuffer(
            "RGB",
            (bitmap_info["bmWidth"], bitmap_info["bmHeight"]),
            bitmap_bits,
            "raw",
            "BGRX",
            0,
            1,
        ).copy()

        if save_path is not None:
            output = Path(save_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            image.save(output)
        return image
    finally:
        if bitmap is not None:
            try:
                win32gui.DeleteObject(bitmap.GetHandle())
            except Exception:
                pass
        if memory_dc is not None:
            try:
                memory_dc.DeleteDC()
            except Exception:
                pass
        if source_dc is not None:
            try:
                source_dc.DeleteDC()
            except Exception:
                pass
        if window_dc is not None:
            try:
                win32gui.ReleaseDC(hwnd, window_dc)
            except Exception:
                pass


def background_click(
    hwnd: int,
    x: int,
    y: int,
    hold_seconds: float = 0.05,
    delivery: str = "post",
    timeout_ms: int = DEFAULT_SEND_TIMEOUT_MS,
) -> None:
    """Deliver a client-relative left click without moving the physical cursor."""

    if hold_seconds < 0:
        raise ValueError("hold_seconds 不能为负数")
    position = _client_lparam(hwnd, x, y)
    _dispatch_message(hwnd, win32con.WM_MOUSEMOVE, 0, position, delivery, timeout_ms)
    _dispatch_message(
        hwnd,
        win32con.WM_LBUTTONDOWN,
        win32con.MK_LBUTTON,
        position,
        delivery,
        timeout_ms,
    )
    try:
        time.sleep(hold_seconds)
    finally:
        _dispatch_message(
            hwnd, win32con.WM_LBUTTONUP, 0, position, delivery, timeout_ms
        )


def background_long_press(
    hwnd: int,
    x: int,
    y: int,
    duration: float,
    delivery: str = "post",
    timeout_ms: int = DEFAULT_SEND_TIMEOUT_MS,
) -> None:
    """Hold the left mouse button at a client coordinate for ``duration``."""

    if duration <= 0:
        raise ValueError("duration 必须大于 0")
    position = _client_lparam(hwnd, x, y)
    _dispatch_message(hwnd, win32con.WM_MOUSEMOVE, 0, position, delivery, timeout_ms)
    _dispatch_message(
        hwnd,
        win32con.WM_LBUTTONDOWN,
        win32con.MK_LBUTTON,
        position,
        delivery,
        timeout_ms,
    )
    try:
        time.sleep(duration)
    finally:
        _dispatch_message(
            hwnd, win32con.WM_LBUTTONUP, 0, position, delivery, timeout_ms
        )


def background_drag(
    hwnd: int,
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    duration: float = 0.5,
    steps: int = 30,
    delivery: str = "post",
    timeout_ms: int = DEFAULT_SEND_TIMEOUT_MS,
) -> None:
    """Post a smooth client-relative left-button drag."""

    if duration <= 0:
        raise ValueError("duration 必须大于 0")
    if steps < 1:
        raise ValueError("steps 必须至少为 1")

    start = _client_lparam(hwnd, start_x, start_y)
    _client_lparam(hwnd, end_x, end_y)
    _dispatch_message(hwnd, win32con.WM_MOUSEMOVE, 0, start, delivery, timeout_ms)
    _dispatch_message(
        hwnd,
        win32con.WM_LBUTTONDOWN,
        win32con.MK_LBUTTON,
        start,
        delivery,
        timeout_ms,
    )

    try:
        step_delay = duration / steps
        for index in range(1, steps + 1):
            ratio = index / steps
            x = round(start_x + (end_x - start_x) * ratio)
            y = round(start_y + (end_y - start_y) * ratio)
            position = _client_lparam(hwnd, x, y)
            _dispatch_message(
                hwnd,
                win32con.WM_MOUSEMOVE,
                win32con.MK_LBUTTON,
                position,
                delivery,
                timeout_ms,
            )
            time.sleep(step_delay)
    finally:
        end = _client_lparam(hwnd, end_x, end_y)
        _dispatch_message(
            hwnd, win32con.WM_LBUTTONUP, 0, end, delivery, timeout_ms
        )


def _virtual_key(key: str) -> int:
    normalized = key.casefold()
    try:
        return SUPPORTED_KEYS[normalized]
    except KeyError as exc:
        allowed = ", ".join(SUPPORTED_KEYS)
        raise ValueError(f"不支持按键 {key!r}；允许：{allowed}") from exc


def _keyboard_lparam(vk_code: int, key_up: bool) -> int:
    scan_code = win32api.MapVirtualKey(vk_code, 0)
    value = 1 | (scan_code << 16)
    if key_up:
        value |= (1 << 30) | (1 << 31)
    return value


def background_key_down(
    hwnd: int,
    key: str,
    delivery: str = "post",
    timeout_ms: int = DEFAULT_SEND_TIMEOUT_MS,
) -> None:
    """Deliver a key-down message for esc, p, or enter."""

    _require_window(hwnd)
    vk_code = _virtual_key(key)
    _dispatch_message(
        hwnd,
        win32con.WM_KEYDOWN,
        vk_code,
        _keyboard_lparam(vk_code, key_up=False),
        delivery,
        timeout_ms,
    )


def background_key_up(
    hwnd: int,
    key: str,
    delivery: str = "post",
    timeout_ms: int = DEFAULT_SEND_TIMEOUT_MS,
) -> None:
    """Deliver a key-up message for esc, p, or enter."""

    _require_window(hwnd)
    vk_code = _virtual_key(key)
    _dispatch_message(
        hwnd,
        win32con.WM_KEYUP,
        vk_code,
        _keyboard_lparam(vk_code, key_up=True),
        delivery,
        timeout_ms,
    )


def background_key_press(
    hwnd: int,
    key: str,
    hold_seconds: float = 0.05,
    delivery: str = "post",
    timeout_ms: int = DEFAULT_SEND_TIMEOUT_MS,
) -> None:
    """Post a complete key press while keeping down/up separately callable."""

    if hold_seconds < 0:
        raise ValueError("hold_seconds 不能为负数")
    background_key_down(hwnd, key, delivery, timeout_ms)
    try:
        time.sleep(hold_seconds)
    finally:
        background_key_up(hwnd, key, delivery, timeout_ms)


def get_mouse_position(hwnd: int) -> MousePosition:
    """Sample the cursor and convert its screen position to client coordinates."""

    _require_window(hwnd)
    if win32gui.IsIconic(hwnd):
        raise InteractionLabError("实时坐标检测要求游戏窗口没有最小化")

    screen_x, screen_y = win32api.GetCursorPos()
    client_x, client_y = win32gui.ScreenToClient(hwnd, (screen_x, screen_y))
    width, height = _client_size(hwnd)
    return MousePosition(
        screen_x=screen_x,
        screen_y=screen_y,
        client_x=client_x,
        client_y=client_y,
        inside_client=0 <= client_x < width and 0 <= client_y < height,
    )


def monitor_mouse_position(hwnd: int, interval: float = 0.05) -> Iterator[MousePosition]:
    """Yield live mouse samples until the caller stops iteration."""

    if interval <= 0:
        raise ValueError("interval 必须大于 0")
    while True:
        yield get_mouse_position(hwnd)
        time.sleep(interval)


class WindowsInteractionLab:
    """Convenient object API over the independently callable lab functions."""

    def __init__(
        self,
        title: str = DEFAULT_WINDOW_TITLE,
        window_class: str = DEFAULT_WINDOW_CLASS,
    ) -> None:
        enable_per_monitor_dpi_awareness()
        self.title = title
        self.window_class = window_class
        self.hwnd = find_target_window(title, window_class)

    @property
    def minimized(self) -> bool:
        _require_window(self.hwnd)
        return bool(win32gui.IsIconic(self.hwnd))

    @property
    def foreground(self) -> bool:
        _require_window(self.hwnd)
        return win32gui.GetForegroundWindow() == self.hwnd

    @property
    def client_size(self) -> tuple[int, int]:
        return _client_size(self.hwnd)

    def screenshot(self, save_path: str | Path | None = None) -> Image.Image:
        return capture_background(self.hwnd, save_path)

    def click(
        self,
        x: int,
        y: int,
        hold_seconds: float = 0.05,
        delivery: str = "post",
        timeout_ms: int = DEFAULT_SEND_TIMEOUT_MS,
    ) -> None:
        background_click(self.hwnd, x, y, hold_seconds, delivery, timeout_ms)

    def long_press(
        self,
        x: int,
        y: int,
        duration: float,
        delivery: str = "post",
        timeout_ms: int = DEFAULT_SEND_TIMEOUT_MS,
    ) -> None:
        background_long_press(self.hwnd, x, y, duration, delivery, timeout_ms)

    def drag(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration: float = 0.5,
        steps: int = 30,
        delivery: str = "post",
        timeout_ms: int = DEFAULT_SEND_TIMEOUT_MS,
    ) -> None:
        background_drag(
            self.hwnd,
            start_x,
            start_y,
            end_x,
            end_y,
            duration,
            steps,
            delivery,
            timeout_ms,
        )

    def key_down(
        self,
        key: str,
        delivery: str = "post",
        timeout_ms: int = DEFAULT_SEND_TIMEOUT_MS,
    ) -> None:
        background_key_down(self.hwnd, key, delivery, timeout_ms)

    def key_up(
        self,
        key: str,
        delivery: str = "post",
        timeout_ms: int = DEFAULT_SEND_TIMEOUT_MS,
    ) -> None:
        background_key_up(self.hwnd, key, delivery, timeout_ms)

    def key_press(
        self,
        key: str,
        hold_seconds: float = 0.05,
        delivery: str = "post",
        timeout_ms: int = DEFAULT_SEND_TIMEOUT_MS,
    ) -> None:
        background_key_press(self.hwnd, key, hold_seconds, delivery, timeout_ms)

    def mouse_position(self) -> MousePosition:
        return get_mouse_position(self.hwnd)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Limbus Company Windows 交互实验")
    parser.add_argument("--title", default=DEFAULT_WINDOW_TITLE)
    parser.add_argument("--window-class", default=DEFAULT_WINDOW_CLASS)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("info", help="显示窗口句柄、尺寸和最小化状态")

    screenshot = subparsers.add_parser("screenshot", help="后台截图")
    screenshot.add_argument("--output", default="interaction-lab-screenshot.png")

    def add_delivery_options(command_parser: argparse.ArgumentParser) -> None:
        command_parser.add_argument(
            "--delivery",
            choices=DELIVERY_MODES,
            default="post",
            help="post=异步入队；send=同步直达窗口过程",
        )
        command_parser.add_argument(
            "--timeout-ms", type=int, default=DEFAULT_SEND_TIMEOUT_MS
        )

    click = subparsers.add_parser("click", help="后台点击")
    click.add_argument("x", type=int)
    click.add_argument("y", type=int)
    click.add_argument("--hold", type=float, default=0.05)
    add_delivery_options(click)

    long_press = subparsers.add_parser("long-press", help="后台长按")
    long_press.add_argument("x", type=int)
    long_press.add_argument("y", type=int)
    long_press.add_argument("--duration", type=float, required=True)
    add_delivery_options(long_press)

    drag = subparsers.add_parser("drag", help="后台拖动")
    drag.add_argument("start_x", type=int)
    drag.add_argument("start_y", type=int)
    drag.add_argument("end_x", type=int)
    drag.add_argument("end_y", type=int)
    drag.add_argument("--duration", type=float, default=0.5)
    drag.add_argument("--steps", type=int, default=30)
    add_delivery_options(drag)

    for name in ("key-down", "key-up", "key-press"):
        key_parser = subparsers.add_parser(name, help=f"后台 {name}")
        key_parser.add_argument("key", choices=tuple(SUPPORTED_KEYS))
        if name == "key-press":
            key_parser.add_argument("--hold", type=float, default=0.05)
        add_delivery_options(key_parser)

    monitor = subparsers.add_parser("mouse-position", help="实时显示鼠标客户区坐标")
    monitor.add_argument("--interval", type=float, default=0.05)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    lab = WindowsInteractionLab(args.title, args.window_class)

    if args.command == "info":
        client = "unavailable" if lab.minimized else "x".join(map(str, lab.client_size))
        print(
            f"hwnd={lab.hwnd} client={client} minimized={lab.minimized} "
            f"foreground={lab.foreground}"
        )
    elif args.command == "screenshot":
        image = lab.screenshot(args.output)
        print(
            f"截图已保存：{Path(args.output).resolve()} size={image.size} "
            f"minimized={lab.minimized}"
        )
    elif args.command == "click":
        lab.click(
            args.x, args.y, args.hold, args.delivery, args.timeout_ms
        )
    elif args.command == "long-press":
        lab.long_press(
            args.x, args.y, args.duration, args.delivery, args.timeout_ms
        )
    elif args.command == "drag":
        lab.drag(
            args.start_x,
            args.start_y,
            args.end_x,
            args.end_y,
            args.duration,
            args.steps,
            args.delivery,
            args.timeout_ms,
        )
    elif args.command == "key-down":
        lab.key_down(args.key, args.delivery, args.timeout_ms)
    elif args.command == "key-up":
        lab.key_up(args.key, args.delivery, args.timeout_ms)
    elif args.command == "key-press":
        lab.key_press(args.key, args.hold, args.delivery, args.timeout_ms)
    elif args.command == "mouse-position":
        print("按 Ctrl+C 停止")
        try:
            for sample in monitor_mouse_position(lab.hwnd, args.interval):
                print(
                    "\r"
                    f"client=({sample.client_x:5d}, {sample.client_y:5d}) "
                    f"screen=({sample.screen_x:5d}, {sample.screen_y:5d}) "
                    f"inside={sample.inside_client}",
                    end="",
                    flush=True,
                )
        except KeyboardInterrupt:
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
