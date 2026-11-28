"""前台输入所有权、长动作释放和输入恢复。"""

from __future__ import annotations

import json
import math
import threading
import time
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Callable

from .application_settings import DEFAULT_IDLE_SECONDS
from .focused import FocusedAutomationSession, WindowError
from .runtime import GameProcessExited, InputReleaseFailure, UserInterruption, RunGate, _exception_fields


@dataclass(frozen=True)
class InputActivity:
    """钩子可观察的输入详情，可按相同来源和动作计数。"""

    kind: str
    source: str
    action: str = ""
    vk: int | None = None
    scan_code: int | None = None
    extended: bool = False
    wheel_delta: int | None = None

    def describe(self, backend: Any) -> str:
        text = f"{self.source}{self.kind}{self.action}"
        if self.vk is not None:
            name = backend.key_name(self) if hasattr(backend, "key_name") else None
            text = f"{self.source}{self.kind} {name + ' ' if name else ''}{self.action}"
            text += f"（VK 0x{self.vk:02X}，扫描码 0x{self.scan_code:02X}"
            text += "，扩展键）" if self.extended else "）"
        if self.wheel_delta is not None:
            text += f"（{self.wheel_delta:+d}）"
        return text


class PhysicalInputMonitor:
    """记录输入计时和诊断，钩子回调无需写日志或处理界面。"""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.generation = 0
        self.started_at = self.last_input = time.monotonic()
        self.takeover: tuple[InputActivity, tuple[int, int] | None] | None = None
        self.activities: Counter[InputActivity] | None = None
        self.last_activity_kind = ""
        self.target_hwnd: int | None = None
        self.pause_requested = False
        self.error: BaseException | None = None

    def record(self, kind: str, injected: bool, *, takeover: bool = True, pause: bool = False,
               detail: InputActivity | None = None, client_point: tuple[int, int] | None = None) -> None:
        if injected:
            return
        activity = detail if detail is not None else InputActivity(kind, "")
        with self.lock:
            self.last_input = time.monotonic()
            self.last_activity_kind = kind
            if takeover or pause:
                self.generation += 1
                if self.takeover is None:
                    self.takeover = activity, client_point
            if pause:
                self.pause_requested = True
            if self.activities is not None:
                self.activities[activity] += 1

    def snapshot(
        self, *, acknowledge: bool = False,
    ) -> tuple[int, float, tuple[InputActivity, tuple[int, int] | None] | None]:
        with self.lock:
            if self.error is not None:
                raise RuntimeError("Input monitor failed.") from self.error
            if acknowledge:
                self.takeover = None
            return self.generation, self.last_input, self.takeover

    def acknowledge_if_current(self, generation: int, last_input: float) -> bool:
        """只在空闲检查后代次和时间都未变化时接受接管。"""
        with self.lock:
            if self.error is not None or (generation, last_input) != (self.generation, self.last_input):
                return False
            self.takeover = None
            return True


class _IdleWaitLog:
    """将等待中的活动与会话计时合并成每秒一条运行日志。"""

    def __init__(self, session: InputSession, waiting_for: str) -> None:
        self.session = session
        self.waiting_for = waiting_for
        self.session_activity = time.monotonic()
        self.next_log = self.session_activity + 1
        self.events: Counter[InputActivity] = Counter()
        with session.monitor.lock:
            self.previous_events = session.monitor.activities
            session.monitor.activities = self.events

    def update(self, duration: float, idle_since: float, *, closing: bool = False) -> None:
        now = time.monotonic()
        if now < self.next_log and not closing:
            return
        self.next_log = now + 1
        idle = self.session.session_idle_seconds()
        monitor = self.session.monitor
        with monitor.lock:
            activity, kind = monitor.last_input, monitor.last_activity_kind
            events = list(self.events.items())
            self.events.clear()
            if closing:
                monitor.activities = self.previous_events
        now = time.monotonic()
        idle_since = max(idle_since, activity)
        elapsed_idle = now - idle_since
        if idle is not None:
            elapsed_idle = min(elapsed_idle, idle)
        remaining = math.ceil(max(0, duration - elapsed_idle))
        source = kind if events else None
        # Windows 会话计时是近似值，排除计时器粒度造成的波动。
        unknown = False
        if idle is not None and now - idle > self.session_activity + 0.05:
            self.session_activity = now - idle
            unknown = self.session_activity > activity + 0.05
        details = [event.describe(self.session.backend) + (f" ×{count}" if count > 1 else "")
                   for event, count in events]
        if unknown:
            source = source or "Windows 会话"
            details.append("来源未知（Windows 会话活动）")
        if details:
            prefix = "等待期间检测到输入。" if closing else f"检测到输入，重新计时，剩余 {remaining} 秒。"
            message = prefix + "｜".join(details)
        elif closing:
            return
        elif remaining:
            message = f"等待键鼠空闲，还剩 {remaining} 秒。"
        else:
            self.session.log_wait_for_release(self.waiting_for, remaining_seconds=0)
            return
        self.session.log_input_wait(message, waiting_for=self.waiting_for, remaining_seconds=remaining,
                                    activity_source=source,
                                    input_activity=[{**asdict(event), "count": count} for event, count in events],
                                    session_activity_unknown=unknown)


class InputSession:
    """在运行线程注入输入并负责唯一的释放；物理接管只中断，不重放。"""

    QUIET_SECONDS = 0.3
    ACTIVITY_SECONDS = DEFAULT_IDLE_SECONDS
    POLL_SECONDS = 0.012
    KEYS = {"esc": 0x1B, "p": 0x50, "enter": 0x0D}

    def __init__(self, window: FocusedAutomationSession, backend: Any, gate: RunGate,
                 emit: Callable[[str, dict[str, Any]], None], *, process_id: int | None = None,
                 idle_seconds: int | None = None) -> None:
        self.window, self.backend, self.gate, self.emit = window, backend, gate, emit
        if idle_seconds is not None:
            self.ACTIVITY_SECONDS = idle_seconds
        self.monitor = backend.monitor
        self.cursor_interrupted_at: float | None = None
        self.paused = False
        self.failed = False
        self.holding = False
        self.focus_wait_seconds = 0.0
        self.resume_focus = False
        self.focus_checkpoint: Callable[[], None] | None = None
        try:
            self.owned_generation = self.monitor.snapshot(acknowledge=True)[0]
            self.process = window.platform.open_game_process(window.process_id if process_id is None else process_id)
        except BaseException:
            backend.close()
            raise
        window.before_capture = self.park_cursor
        window.before_check = self.ensure_foreground
        self.monitor.target_hwnd = window.hwnd

    def check_ownership(self) -> None:
        """无窗口过渡期仍检查输入所有权、暂停、取消和释放失败。"""

        if self.failed:
            raise InputReleaseFailure("Input session was disabled after release failure.")
        if self.gate.stopped:
            raise UserInterruption
        generation, _, takeover = self.monitor.snapshot()
        if self.monitor.pause_requested:
            self._interrupt("全局快捷键请求暂停。", "pause")
        if generation != self.owned_generation:
            self._interrupt("检测到用户输入，当前 Step 已中断。", "physical_input", takeover=takeover)
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
                   original: Exception | None = None, *,
                   takeover: tuple[InputActivity, tuple[int, int] | None] | None = None) -> None:
        first = not self.paused
        self.paused = True
        self.window.image = None
        self.window.size = None
        if first:
            fields = {}
            if takeover is not None:
                activity, point = takeover
                detail = activity.describe(self.backend)
                fields["input_activity"] = asdict(activity)
                if point is not None:
                    detail += f"，游戏客户区坐标 ({point[0]}, {point[1]})"
                    fields["client_point"] = point
                reason = f"检测到{detail}，当前 Step 已中断。"
            self.emit("input_takeover", {"reason": reason, "source": source, "outcome": "unknown", **fields})
            if takeover is not None:
                self.log_input_wait(reason, level="warning", **fields)
        if source == "cursor_position":
            self.cursor_interrupted_at = time.monotonic()
        intent = "takeover" if source in {"physical_input", "cursor_position"} else "pause"
        if original is not None:
            raise UserInterruption(reason, reason=intent) from original
        raise UserInterruption(reason, reason=intent)

    def focus_window(self, hwnd: int, *, process_id: int, after_takeover: bool = False,
                     checkpoint: Callable[[], None] | None = None,
                     immediate_since: float | None = None, focus_lost_at: float | None = None) -> None:
        """每次置前尝试都经过同一个可取消的空闲检查。"""
        self.monitor.target_hwnd = hwnd
        activity_at_check = None
        requested = False

        def check():
            nonlocal immediate_since, activity_at_check
            immediate_since, activity_at_check = self.wait_for_activity(
                hwnd, process_id, after_takeover=after_takeover, immediate_since=immediate_since,
                focus_lost_at=focus_lost_at,
            )
            if checkpoint is not None:
                checkpoint()

        def first_attempt(foreground, accepted):
            nonlocal requested
            requested = True
            message = ("已请求游戏置前，等待 Windows 确认。" if accepted else
                       "Windows 未能将游戏置前，仍在等待，也可手动切回游戏。")
            self.log_input_wait(message, outcome="focus_requested", target_hwnd=hwnd,
                                foreground_hwnd=foreground, set_foreground_result=accepted)

        def still_idle():
            return (not self.gate.stopped and not self.gate.paused and not self.monitor.pause_requested
                    and (immediate_since is not None or self.session_idle_for(self.ACTIVITY_SECONDS))
                    and self.monitor.snapshot()[1] == activity_at_check)

        def fallback(foreground):
            accepted = self.window.platform.try_attached_focus(hwnd, process_id, foreground, still_idle)
            self.log_input_wait("已尝试通过前台输入队列切回游戏。", outcome="focus_fallback",
                                target_hwnd=hwnd, foreground_hwnd=foreground, set_foreground_result=accepted)
            return accepted

        self.window.platform.focus(hwnd, checkpoint=check, max_attempts=None, on_first_attempt=first_attempt,
                                   fallback=fallback)
        if requested:
            self.log_input_wait("已确认游戏窗口回到前台。", outcome="focus_confirmed", target_hwnd=hwnd)

    def log_input_wait(self, message: str, **fields: Any) -> None:
        self.emit("component_log", {"logical_name": "input.focus", "role": "trusted_action",
                  "phase": "execute", "level": "info", "message": message, **fields})

    def log_wait_for_release(self, waiting_for: str, **fields: Any) -> None:
        """记录仍在阻挡输入的键，供正常运行日志和 Trace 显示。"""
        read_key = getattr(self.backend, "first_pressed_key", None)
        key = read_key() if read_key is not None else None
        message = (f"等待按键或鼠标按钮松开，当前阻塞 VK 0x{key:02X}。" if key is not None else
                   "正在确认按键或鼠标按钮已松开。")
        self.log_input_wait(message, waiting_for=waiting_for, blocking_vk=key, **fields)

    def session_idle_seconds(self) -> float | None:
        """查询 Windows 会话的空闲时间，平台未提供时返回空值。"""
        read_idle = getattr(self.backend, "session_idle_seconds", None)
        return read_idle() if read_idle is not None else None

    def session_idle_for(self, duration: float) -> bool:
        """钩子计时到期后，再确认当前桌面会话没有更近的输入。"""
        idle = self.session_idle_seconds()
        return idle is None or idle >= duration

    def wait_for_activity(self, hwnd: int, process_id: int, *, after_takeover: bool = False,
                          immediate_since: float | None = None,
                          focus_lost_at: float | None = None) -> tuple[float | None, float]:
        """键鼠活动延后下次聚焦，显式恢复只豁免该次操作前的活动。"""
        started = time.monotonic()
        progress = None
        idle_since = started if focus_lost_at is None else focus_lost_at
        outcome = "interrupted"
        paused_seconds = 0.0

        try:
            while True:
                if self.focus_checkpoint is not None:
                    checkpoint_started = time.monotonic()
                    self.focus_checkpoint()
                    paused_seconds += time.monotonic() - checkpoint_started
                else:
                    self.check_ownership()
                if process_id == self.process.pid and self.process.exited():
                    raise GameProcessExited()
                info = self.window.platform.window_info(hwnd)
                if not info["valid"]:
                    raise WindowError("Target Window disappeared while waiting for user activity.")
                if info["process_id"] != process_id:
                    raise WindowError("Target Window process changed.")
                if not info["visible"] or (not info["minimized"] and (info["width"] <= 0 or info["height"] <= 0)):
                    raise WindowError("Target Window is hidden or has an empty client area.")
                foreground = info["foreground"] and not info["minimized"]
                # 点击其他窗口的回调可能先于前台切换，空闲计时不依赖当时的前台。
                _, activity, _ = self.monitor.snapshot()
                if self.resume_focus:
                    self.resume_focus = False
                    immediate_since = activity
                if immediate_since == activity:
                    outcome = "manual_resume"
                    return immediate_since, activity
                if foreground and not after_takeover:
                    outcome = "foreground"
                    return None, activity
                idle_since = activity if focus_lost_at is None else max(activity, focus_lost_at)
                if (time.monotonic() - idle_since >= self.ACTIVITY_SECONDS and not self.backend.any_pressed()
                        and self.session_idle_for(self.ACTIVITY_SECONDS)):
                    if self.monitor.snapshot()[1] == activity:
                        outcome = "idle"
                        return None, activity
                if progress is None:
                    progress = _IdleWaitLog(self, "focus")
                    self.log_input_wait(f"等待键鼠连续空闲 {self.ACTIVITY_SECONDS:g} 秒后聚焦游戏。",
                                        idle_seconds=self.ACTIVITY_SECONDS)
                else:
                    progress.update(self.ACTIVITY_SECONDS, idle_since)
                time.sleep(self.POLL_SECONDS)
        finally:
            if progress is not None:
                duration = time.monotonic() - started
                self.focus_wait_seconds += max(0.0, duration - paused_seconds)
                progress.update(self.ACTIVITY_SECONDS, idle_since, closing=True)
                reason = {"idle": "键鼠已空闲，可以请求游戏置前", "foreground": "游戏已在前台",
                          "manual_resume": "用户手动恢复", "interrupted": "暂停、取消或窗口异常"}[outcome]
                self.log_input_wait(f"游戏焦点等待结束，实际等待 {duration:.1f} 秒：{reason}。",
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
            # 每次失焦单独计时，上一次已经等满的空闲期不能用于新一轮置前。
            self.focus_window(hwnd, process_id=self.window.process_id, focus_lost_at=time.monotonic())
            self.check_ownership()
            if had_image:
                self.window.capture()
        else:
            self.resume_focus = False

    def park_cursor(self) -> bool:
        """受控重试三次归位；仅移动失败降级，接管和窗口异常仍传播。"""
        attempts = []
        for _ in range(3):
            self.check(record=False)
            hwnd = self.window.hwnd
            before = self.window.platform.cursor_position(hwnd)
            if not before["inside"]:
                return True
            while self.backend.any_pressed():
                self.check(record=False)
                time.sleep(self.POLL_SECONDS)
            self.check(record=False)
            diagnostics = {}
            reason = "Cursor remained inside the game after injected movement."
            try:
                diagnostics = self.backend.park_cursor(hwnd) or {}
            except (WindowError, OSError) as error:
                reason = str(error)
            self.check(record=False)
            immediate = self.window.platform.cursor_position(hwnd)
            # 留出游戏及远程输入处理移动和重绘悬停状态的时间。
            self._wait(0.1)
            after = self.window.platform.cursor_position(hwnd)
            if not immediate["inside"] and after["inside"]:
                reason = "Cursor returned inside the game during the settle wait."
            attempts.append({"before": before, "immediate": immediate, "after": after, "reason": reason, **diagnostics})
            if not after["inside"]:
                return True
        self.emit("component_log", {
            "level": "warning", "logical_name": "observe.capture_screen",
            "message": "Cannot park cursor after 3 attempts; continuing capture with possible hover/occlusion. "
                       + json.dumps(attempts, ensure_ascii=False),
        })
        return False

    def wait_after_takeover(self) -> None:
        """动作释放后等待全局物理输入安静，即使游戏还在前台。"""
        started = time.monotonic()
        cursor_interrupted_at = self.cursor_interrupted_at
        self.cursor_interrupted_at = None
        reason = "滚轮位置不符，" if cursor_interrupted_at is not None else "用户接管后，"
        self.log_input_wait(f"{reason}等待键鼠连续空闲 {self.ACTIVITY_SECONDS:g} 秒再自动恢复。",
                            waiting_for="takeover", idle_seconds=self.ACTIVITY_SECONDS)
        self.owned_generation = self.wait_quiet(self.ACTIVITY_SECONDS, since=cursor_interrupted_at)
        self.paused = False
        self.log_input_wait("键鼠已连续空闲，开始恢复前检查。", waiting_for="takeover", outcome="idle",
                            duration_seconds=time.monotonic() - started)

    def prepare_resume(self, *, automatic=False) -> None:
        """确认输入释放并刷新游戏画面；自动恢复须先满足完整空闲窗口。"""
        if automatic:
            self.wait_after_takeover()
        else:
            with self.monitor.lock:
                self.monitor.pause_requested = False
            self.owned_generation = self.wait_quiet()
            self.paused = False
        self.check_ownership()
        self.resume_focus = not automatic
        if self.process.exited():
            self.window.image = None
            self.window.size = None
            raise GameProcessExited()
        assert self.window.hwnd is not None
        self.focus_window(self.window.hwnd, process_id=self.window.process_id, after_takeover=automatic)
        self.window.capture()
        self.check_ownership()
        if self.backend.any_pressed():
            raise WindowError("恢复检查期间仍有用户输入，请再次恢复。")

    def wait_quiet(self, seconds: float | None = None, *, since: float | None = None) -> int:
        """等待物理输入释放且安静，供普通恢复与重启过渡期共用。"""
        duration = self.QUIET_SECONDS if seconds is None else seconds
        progress = None
        idle_since = time.monotonic() if since is None else since
        try:
            while True:
                if self.gate.stopped:
                    raise UserInterruption
                generation, last, _ = self.monitor.snapshot()
                if self.monitor.pause_requested:
                    self._interrupt("全局快捷键请求暂停。", "pause")
                if self.gate.paused:
                    self._interrupt("自动化已暂停。", "pause")
                idle_since = last if since is None else max(last, since)
                if (time.monotonic() - idle_since >= duration and not self.backend.any_pressed()
                        and (seconds is None or self.session_idle_for(duration))):
                    # 查询实际按住状态期间也可能有键鼠输入。
                    if self.monitor.acknowledge_if_current(generation, last):
                        break
                if seconds is not None:
                    if progress is None:
                        progress = _IdleWaitLog(self, "takeover")
                    else:
                        progress.update(duration, idle_since)
                time.sleep(self.POLL_SECONDS)
        finally:
            if progress is not None:
                progress.update(duration, idle_since, closing=True)
        self.emit("input_quiet", {"quiet_seconds": duration})
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
        """固定输入动作；所有参数先验证，持有型输入在 finally 中释放。"""

        self.check()
        next_wait_log = time.monotonic()
        while self.backend.any_pressed():
            self.check(record=False)
            now = time.monotonic()
            if now >= next_wait_log:
                self.log_wait_for_release(operation)
                next_wait_log = now + 1
            time.sleep(self.POLL_SECONDS)
        self.check()
        if operation == "wait":
            self._wait(self._duration(arguments["seconds"]))
        elif operation == "key_press":
            key = arguments["key"].lower()
            if key not in self.KEYS:
                raise ValueError("Supported keys: esc, p, enter.")
            self._key(self.KEYS[key])
        elif operation == "scroll":
            direction, steps = arguments["direction"], arguments["steps"]
            if direction not in ("up", "down"):
                raise ValueError("Scroll direction must be up or down.")
            if type(steps) is not int or not 1 <= steps <= 10:
                raise ValueError("Scroll steps must be an integer between 1 and 10.")
            self._scroll(arguments["x"], arguments["y"], direction, steps)
        elif operation in {"click", "drag"}:
            start = self._point(arguments["x"], arguments["y"])
            end = self._point(arguments["end_x"], arguments["end_y"]) if operation == "drag" else start
            duration = self._duration(arguments["seconds"]) if operation == "drag" else 0.08
            self._touch(start, end, duration, operation)
        else:
            raise ValueError(f"Unknown control operation: {operation}")

    def _scroll(self, x: int, y: int, direction: str, steps: int) -> None:
        """逐格检查焦点与光标；失焦中断，不重新聚焦后续滚。"""
        self.holding = True
        try:
            self.check()
            self.backend.move_cursor(*self._point(x, y))
            # 留出游戏和远程输入处理移动、更新悬停区域的时间。
            self._wait(0.2)
            for index in range(steps):
                if index:
                    self._wait(0.2)
                self.check()
                self._point(x, y)
                position = self.window.platform.cursor_position(self.window.hwnd)
                if abs(position["x"] - x) > 2 or abs(position["y"] - y) > 2:
                    self._interrupt("滚轮目标处的鼠标位置已改变或未到达。", "cursor_position")
                self.backend.wheel(120 if direction == "up" else -120)
                self.check()
        finally:
            self.holding = False

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
