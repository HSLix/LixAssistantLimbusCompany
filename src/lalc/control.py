"""前台输入所有权、长动作释放和用户手动恢复。"""

from __future__ import annotations

import math
import threading
import time
from typing import Any, Callable

from .focused import FocusedAutomationSession, WindowError
from .runtime import InputReleaseFailure, UserInterruption, RunGate, _exception_fields


class PhysicalInputMonitor:
    """只记录物理输入代次；回调不写 Trace、不注入或屏蔽用户输入。"""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.generation = 0
        self.last_input = time.monotonic()
        self.kind = ""
        self.error: BaseException | None = None

    def record(self, kind: str, injected: bool) -> None:
        if injected:
            return
        with self.lock:
            self.generation += 1
            self.last_input = time.monotonic()
            self.kind = kind

    def snapshot(self) -> tuple[int, float, str]:
        with self.lock:
            if self.error is not None:
                raise RuntimeError("Input monitor failed.") from self.error
            return self.generation, self.last_input, self.kind


class InputSession:
    """在运行线程注入输入并负责唯一的释放；物理接管只中断，不重放。"""

    QUIET_SECONDS = 0.3
    POLL_SECONDS = 0.012
    KEYS = {"esc": 0x1B, "p": 0x50, "enter": 0x0D}

    def __init__(self, window: FocusedAutomationSession, backend: Any, gate: RunGate,
                 emit: Callable[[str, dict[str, Any]], None]) -> None:
        self.window, self.backend, self.gate, self.emit = window, backend, gate, emit
        self.monitor = backend.monitor
        self.owned_generation = self.monitor.snapshot()[0]
        self.paused = False
        self.failed = False

    def check(self, *, record: bool = True) -> None:
        """不抢焦点；所有权或窗口失效时丢弃图像，交给 Step 等待用户。"""

        if self.failed:
            raise InputReleaseFailure("Input session was disabled after release failure.")
        if self.gate.stopped:
            raise UserInterruption
        generation, _, kind = self.monitor.snapshot()
        if generation != self.owned_generation:
            self._interrupt(f"检测到用户{kind}输入，当前 Step 已中断。", "physical_input")
        if self.paused or self.gate.paused:
            self._interrupt("自动化已暂停，当前 Step 将在手动恢复后重新进入。", "pause")
        try:
            self.window.check(record=record)
        except WindowError as error:
            self._interrupt(str(error), "window_invalid", error)

    def _interrupt(self, reason: str, source: str,
                   original: Exception | None = None) -> None:
        first = not self.paused
        self.paused = True
        self.window.image = None
        self.window.size = None
        if first:
            self.emit("input_takeover", {"reason": reason, "source": source, "outcome": "unknown"})
        intent = "takeover" if source == "physical_input" else "pause"
        if original is not None:
            raise UserInterruption(reason, reason=intent) from original
        raise UserInterruption(reason, reason=intent)

    def prepare_resume(self) -> None:
        """安静且无按住的物理输入后只聚焦一次；失败仍需再次手动恢复。"""

        while True:
            if self.gate.stopped:
                raise UserInterruption
            generation, last, _ = self.monitor.snapshot()
            if time.monotonic() - last >= self.QUIET_SECONDS and not self.backend.any_pressed():
                break
            time.sleep(self.POLL_SECONDS)
        self.emit("input_quiet", {"quiet_seconds": self.QUIET_SECONDS})
        assert self.window.hwnd is not None
        self.window.platform.focus(self.window.hwnd)
        self.window.capture()
        if self.monitor.snapshot()[0] != generation or self.backend.any_pressed():
            raise WindowError("恢复检查期间仍有用户输入，请再次恢复。")
        self.owned_generation = generation
        self.paused = False

    def _wait(self, duration: float, update: Callable[[float], None] | None = None) -> None:
        started = time.monotonic()
        while True:
            self.check(record=False)
            elapsed = time.monotonic() - started
            if elapsed >= duration:
                return
            if update is not None:
                update(elapsed / duration)
            time.sleep(min(self.POLL_SECONDS, duration - elapsed))

    @staticmethod
    def _duration(value: Any) -> float:
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 60:
            raise ValueError("Input duration must be between 0 and 60 seconds.")
        return float(value)

    def _point(self, x: int, y: int) -> tuple[int, int]:
        info = self.window.check()
        if type(x) is not int or type(y) is not int or not (0 <= x < info["width"] and 0 <= y < info["height"]):
            raise ValueError("Input point is outside the Target Window client area.")
        return self.backend.client_point(info["hwnd"], x, y)

    def execute(self, operation: str, arguments: dict[str, Any]) -> None:
        """固定四个动作；所有参数先验证，再注入，并在 finally 中释放。"""

        self.check()
        if self.backend.any_pressed():
            self._interrupt("用户仍按住输入，请释放后再恢复。", "physical_input")
        if operation == "wait":
            self._wait(self._duration(arguments["seconds"]))
        elif operation == "key_press":
            key = arguments["key"].lower()
            if key not in self.KEYS:
                raise ValueError("Supported keys: esc, p, enter.")
            self._key(self.KEYS[key])
        elif operation in {"click", "drag"}:
            start = self._point(arguments["x"], arguments["y"])
            end = self._point(arguments["end_x"], arguments["end_y"]) if operation == "drag" else start
            duration = self._duration(arguments["seconds"]) if operation == "drag" else 0.08
            self._touch(start, end, duration, operation)
        else:
            raise ValueError(f"Unknown control operation: {operation}")

    def _release(self, release: Callable[[], None], kind: str) -> None:
        """只尝试释放一次；失败永久禁用会话，保留原始异常轨迹。"""

        try:
            release()
        except Exception as error:
            self.failed = True
            self.emit("input_release_failed", {"kind": kind, **_exception_fields(error)})
            raise InputReleaseFailure(f"无法确认{kind}输入已释放；本次运行已终止。") from error
        self.emit("input_released", {"kind": kind})

    def _key(self, virtual_key: int) -> None:
        held = False
        try:
            self.check()
            self.backend.key(virtual_key, False)
            held = True
            self.emit("input_pressed", {"kind": "key", "virtual_key": virtual_key})
            self._wait(0.05)
        finally:
            if held:
                self._release(lambda: self.backend.key(virtual_key, True), "key")

    def _touch(self, start: tuple[int, int], end: tuple[int, int], duration: float, operation: str) -> None:
        device = self.backend.create_touch()
        current = start
        held = False

        def move(ratio: float) -> None:
            nonlocal current
            current = tuple(round(a + (b - a) * ratio) for a, b in zip(start, end))
            self.backend.touch(device, *current, "move")

        try:
            self.check()
            self.backend.touch(device, *start, "down")
            held = True
            self.emit("input_pressed", {"kind": "touch", "operation": operation})
            self._wait(duration, move if operation == "drag" else None)
            if operation == "drag":
                self.check()
                current = end
                self.backend.touch(device, *end, "move")
        finally:
            try:
                if held:
                    self._release(lambda: self.backend.touch(device, *current, "up"), "touch")
            finally:
                self.backend.destroy_touch(device)

    def close(self) -> None:
        """运行结束时卸载只读钩子；长动作的释放已由各自 finally 完成。"""

        self.backend.close()
