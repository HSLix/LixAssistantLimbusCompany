"""前台输入所有权、长动作释放和用户手动恢复。"""

from __future__ import annotations

import math
import threading
import time
from typing import Any, Callable

from .focused import FocusedAutomationSession, WindowError
from .runtime import GameProcessExited, InputReleaseFailure, UserInterruption, RunGate, _exception_fields


class PhysicalInputMonitor:
    """只记录物理输入代次；回调不写 Trace、不注入或屏蔽用户输入。"""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.generation = 0
        self.last_input = time.monotonic()
        self.kind = ""
        self.last_other_activity = time.monotonic()
        self.target_hwnd: int | None = None
        self.pause_requested = False
        self.error: BaseException | None = None

    def record(self, kind: str, injected: bool, *, takeover: bool = True,
               other_application: bool = False, pause: bool = False) -> None:
        if injected:
            return
        with self.lock:
            self.last_input = time.monotonic()
            if other_application:
                self.last_other_activity = self.last_input
            if takeover or pause:
                self.generation += 1
                self.kind = kind
            if pause:
                self.pause_requested = True

    def snapshot(self) -> tuple[int, float, str]:
        with self.lock:
            if self.error is not None:
                raise RuntimeError("Input monitor failed.") from self.error
            return self.generation, self.last_input, self.kind


class InputSession:
    """在运行线程注入输入并负责唯一的释放；物理接管只中断，不重放。"""

    QUIET_SECONDS = 0.3
    ACTIVITY_SECONDS = 10.0
    POLL_SECONDS = 0.012
    KEYS = {"esc": 0x1B, "p": 0x50, "enter": 0x0D}

    def __init__(self, window: FocusedAutomationSession, backend: Any, gate: RunGate,
                 emit: Callable[[str, dict[str, Any]], None]) -> None:
        self.window, self.backend, self.gate, self.emit = window, backend, gate, emit
        self.monitor = backend.monitor
        self.owned_generation = self.monitor.snapshot()[0]
        self.paused = False
        self.failed = False
        self.holding = False
        self.focus_wait_seconds = 0.0
        self.resume_focus = False
        self.focus_checkpoint: Callable[[], None] | None = None
        window.before_capture = self.park_cursor
        window.before_check = self.ensure_foreground
        window.before_focus = self.before_focus
        self.monitor.target_hwnd = window.hwnd
        try:
            self.process = window.platform.open_game_process(window.process_id)
        except BaseException:
            backend.close()
            raise

    def check_ownership(self) -> None:
        """无窗口过渡期仍检查输入所有权、暂停、取消和释放失败。"""

        if self.failed:
            raise InputReleaseFailure("Input session was disabled after release failure.")
        if self.gate.stopped:
            raise UserInterruption
        generation, _, kind = self.monitor.snapshot()
        if self.monitor.pause_requested:
            self._interrupt("全局快捷键请求暂停。", "pause")
        if generation != self.owned_generation:
            self._interrupt(f"检测到用户{kind}输入，当前 Step 已中断。", "physical_input")
        if self.paused or self.gate.paused:
            self._interrupt("自动化已暂停，当前 Step 将在手动恢复后重新进入。", "pause")

    def check(self, *, record: bool = True) -> None:
        """先保留用户控制权；仅确认进程退出交内置规则，其余窗口异常等待人工。"""
        self.check_ownership()
        if self.process.exited():
            self.window.image = None
            self.window.size = None
            raise GameProcessExited()
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

    def before_focus(self, hwnd: int) -> None:
        """重启绑定也在真正还原、聚焦前遵守用户活动等待。"""
        self.monitor.target_hwnd = hwnd
        if not self.resume_focus:
            self.wait_for_activity(hwnd)
        self.resume_focus = False

    def wait_for_activity(self, hwnd: int) -> None:
        """其他应用连续空闲后才取焦点；等待日志复用用户可见 Info 记录。"""
        started = time.monotonic()
        waiting = False
        outcome = "interrupted"
        paused_seconds = 0.0

        def log(message: str, **fields: Any) -> None:
            self.emit("component_log", {"logical_name": "input.focus", "role": "trusted_action",
                      "phase": "execute", "level": "info", "message": message, **fields})
        try:
            while True:
                if self.focus_checkpoint is not None:
                    checkpoint_started = time.monotonic()
                    self.focus_checkpoint()
                    paused_seconds += time.monotonic() - checkpoint_started
                else:
                    self.check_ownership()
                if self.resume_focus:
                    outcome = "manual_resume"
                    return
                if hwnd == self.window.hwnd and self.process.exited():
                    raise GameProcessExited()
                info = self.window.platform.window_info(hwnd)
                if not info["valid"]:
                    raise WindowError("Target Window disappeared while waiting for user activity.")
                foreground = info["foreground"] and not info["minimized"]
                with self.monitor.lock:
                    last = self.monitor.last_other_activity
                if foreground or (time.monotonic() - last >= self.ACTIVITY_SECONDS
                                  and not self.backend.any_pressed()):
                    outcome = "foreground" if foreground else "idle"
                    return
                if not waiting:
                    waiting = True
                    log("等待其他应用连续空闲 10 秒后聚焦游戏。", idle_seconds=self.ACTIVITY_SECONDS)
                time.sleep(self.POLL_SECONDS)
        finally:
            if waiting:
                duration = time.monotonic() - started
                self.focus_wait_seconds += max(0.0, duration - paused_seconds)
                reason = {"idle": "其他应用已空闲", "foreground": "游戏已在前台",
                          "manual_resume": "用户手动恢复", "interrupted": "暂停、取消或窗口异常"}[outcome]
                log(f"游戏焦点等待结束，实际等待 {duration:.1f} 秒：{reason}。",
                    duration_seconds=duration, outcome=outcome)

    def ensure_foreground(self) -> None:
        """失焦先让出控制；已开始的长动作必须先释放，再由 Step 边界重入。"""
        self.check_ownership()
        if self.process.exited():
            raise GameProcessExited()
        hwnd = self.window.hwnd
        if hwnd is None:
            return
        info = self.window.platform.window_info(hwnd)
        if (not info["valid"] or info["process_id"] != self.window.process_id
                or not info["visible"] or info["width"] <= 0 or info["height"] <= 0):
            return
        if not info["foreground"] or info["minimized"]:
            self.window.focus_revision += 1
            had_image = self.window.image is not None
            self.window.image = None
            self.window.size = None
            if self.holding:
                raise UserInterruption("输入途中游戏失焦，释放后重新执行当前 Step。", reason="focus")
            self.before_focus(hwnd)
            self.window.platform.focus(hwnd)
            self.check_ownership()
            if had_image:
                self.window.capture()
        else:
            self.resume_focus = False

    def park_cursor(self) -> None:
        """只在拥有前台控制权时移开鼠标，移动前后响应接管并等待悬停画面刷新。"""
        self.check(record=False)
        hwnd = self.window.hwnd
        if not self.window.platform.cursor_position(hwnd)["inside"]:
            return
        while self.backend.any_pressed():
            self.check(record=False)
            time.sleep(self.POLL_SECONDS)
        self.check(record=False)
        self.backend.park_cursor(hwnd)
        self.check(record=False)
        # 留出游戏处理鼠标离开和重绘悬停状态的时间。
        self._wait(0.1)
        if self.window.platform.cursor_position(hwnd)["inside"]:
            raise WindowError("Cannot park cursor outside the game; move or resize the game window.")

    def prepare_resume(self) -> None:
        """明确恢复仅等待输入释放，不等待十秒；恢复后首次聚焦享有例外。"""
        with self.monitor.lock:
            self.monitor.pause_requested = False
        generation = self.wait_quiet()
        self.owned_generation = generation
        self.paused = False
        self.resume_focus = True
        if self.process.exited():
            self.window.image = None
            self.window.size = None
            raise GameProcessExited()
        assert self.window.hwnd is not None
        self.before_focus(self.window.hwnd)
        self.window.platform.focus(self.window.hwnd)
        self.window.capture()
        self.check_ownership()
        if self.backend.any_pressed():
            raise WindowError("恢复检查期间仍有用户输入，请再次恢复。")

    def wait_quiet(self) -> int:
        """等待物理输入释放且安静，供普通恢复与重启过渡期共用。"""
        while True:
            if self.gate.stopped:
                raise UserInterruption
            generation, last, _ = self.monitor.snapshot()
            if self.monitor.pause_requested:
                self._interrupt("全局快捷键请求暂停。", "pause")
            if time.monotonic() - last >= self.QUIET_SECONDS and not self.backend.any_pressed():
                break
            time.sleep(self.POLL_SECONDS)
        self.emit("input_quiet", {"quiet_seconds": self.QUIET_SECONDS})
        return generation

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
        while self.backend.any_pressed():
            self.check()
            time.sleep(self.POLL_SECONDS)
        self.check()
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
            self.holding = True
            self.emit("input_pressed", {"kind": "key", "virtual_key": virtual_key})
            self._wait(0.05)
        finally:
            self.holding = False
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
            self.holding = True
            self.emit("input_pressed", {"kind": "touch", "operation": operation})
            self._wait(duration, move if operation == "drag" else None)
            if operation == "drag":
                self.check()
                current = end
                self.backend.touch(device, *end, "move")
        finally:
            self.holding = False
            try:
                if held:
                    self._release(lambda: self.backend.touch(device, *current, "up"), "touch")
            finally:
                self.backend.destroy_touch(device)

    def close(self) -> None:
        """运行结束时卸载只读钩子；长动作的释放已由各自 finally 完成。"""

        try:
            self.backend.close()
        finally:
            self.process.close()
