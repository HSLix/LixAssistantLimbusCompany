"""覆盖游戏接管过滤、全局热键、十秒空闲、立即恢复及长动作失焦释放。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_input_activity.py
"""

from ctypes import wintypes
from types import SimpleNamespace

import pytest

from lalc import control, run_logs
from lalc.control import InputSession
from lalc.focused import FocusedAutomationSession, WindowsWindowPlatform
from lalc.runtime import RunGate, UserInterruption
from lalc.windows_input import WindowsInputBackend
from test_input_control import FakeWindow, service_for, finished, paused


class Clock:
    """以可控时钟验证十秒等待，不消耗实际时间。"""

    def __init__(self):
        self.now = 100.0
        self.on_sleep = lambda: None

    def sleep(self, seconds):
        self.now += seconds
        self.on_sleep()


@pytest.fixture
def session(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(control.time, "monotonic", lambda: clock.now)
    monkeypatch.setattr(control.time, "sleep", clock.sleep)
    window = FakeWindow()
    events = []
    focused = FocusedAutomationSession(window, lambda *args: None)
    focused.capture()
    inputs = InputSession(focused, window.backend, RunGate(), lambda e, f: events.append({"event": e, **f}))
    inputs.POLL_SECONDS = 1
    yield SimpleNamespace(inputs=inputs, window=window, clock=clock, events=events)
    inputs.close()


def test_other_activity_restarts_ten_seconds_and_logs_visible_info(session):
    env = session
    env.window.foreground = False
    def activity():
        if env.clock.now == 105:
            env.inputs.monitor.record("鼠标", False, takeover=False)
        if env.clock.now == 114:
            env.inputs.monitor.record("键盘", False, takeover=False)
    env.clock.on_sleep = activity
    env.inputs.check()
    assert env.clock.now == 124
    assert env.window.focus_calls == 2
    assert env.events[-1]["event"] != "input_takeover"
    logs = [e for e in env.events if e["event"] == "component_log"]
    assert len(logs) == 2
    assert logs[-1]["duration_seconds"] == 24
    assert logs[-1]["outcome"] == "idle"


def test_each_focus_loss_gets_a_fresh_idle_window_after_confirmation(session):
    """两次失焦分别等待，后续输入仍能延长各自的等待。"""
    env = session
    env.clock.now = 120
    env.window.foreground = False
    env.inputs.check()
    assert env.clock.now == 130
    assert env.window.focus_calls == 2

    env.clock.now = 131
    env.window.foreground = False

    def activity():
        assert env.window.focus_calls == 2
        if env.clock.now == 139:
            env.inputs.monitor.record("鼠标", False, takeover=False)

    env.clock.on_sleep = activity
    env.inputs.check()
    assert env.clock.now == 149
    assert env.window.focus_calls == 3


@pytest.mark.parametrize("end", ["foreground", "cancel", "replaced"])
def test_run_focus_retries_keep_waiting_after_ten_failures_and_reset_on_input(session, monkeypatch, end):
    """复用正式聚焦重试，覆盖拒绝置前、途中输入和取消。"""
    env = session
    env.window.foreground = False
    platform = WindowsWindowPlatform.__new__(WindowsWindowPlatform)
    platform.checkpoint = None
    requests, activity = [], []
    window_info = env.window.window_info

    def info(hwnd):
        state = window_info(hwnd)
        if end == "replaced" and len(requests) >= 11:
            state["process_id"] += 1
        return state

    def attempt(hwnd):
        requests.append(env.clock.now)
        if len(requests) == 12 and end == "foreground":
            env.window.foreground = True
        return False

    def tick():
        if not activity and requests and env.clock.now >= requests[0] + 0.2:
            activity.append(env.clock.now)
            env.inputs.monitor.record("键盘", False, takeover=False)
        elif len(activity) == 1 and env.clock.now >= activity[0] + 8:
            activity.append(env.clock.now)
            env.inputs.monitor.record("鼠标", False, takeover=False)
        if end == "cancel" and len(requests) == 11:
            env.inputs.gate.stop()

    platform.user32 = SimpleNamespace(
        GetForegroundWindow=lambda: 42 if env.window.foreground else 99,
        IsWindow=lambda hwnd: True,
        IsIconic=lambda hwnd: False,
        ShowWindowAsync=lambda hwnd, command: None,
        SetForegroundWindow=attempt,
    )
    attached = []
    def fallback(hwnd, pid, foreground, still_idle):
        assert still_idle()
        attached.append((hwnd, pid, foreground))
        return attempt(hwnd)

    env.clock.on_sleep = tick
    monkeypatch.setattr(env.window, "window_info", info)
    monkeypatch.setattr(env.window, "focus", platform.focus)
    monkeypatch.setattr(env.window, "try_attached_focus", fallback, raising=False)
    if end == "foreground":
        env.inputs.check()
        assert env.window.foreground
    else:
        with pytest.raises(UserInterruption) as caught:
            env.inputs.check()
        assert caught.value.reason == ("cancel" if end == "cancel" else "pause")
    assert len(requests) == (12 if end == "foreground" else 11)
    assert attached == [(42, 7, 99)] * 2
    assert requests[1] >= activity[-1] + 10
    assert env.inputs.paused is (end == "replaced")
    requested = [row for row in env.events if row.get("outcome") == "focus_requested"]
    assert len(requested) == 1 and requested[0]["set_foreground_result"] is False
    assert any(row.get("outcome") == "focus_confirmed" for row in env.events) == (end == "foreground")


def test_foreground_takeover_wait_keeps_resetting_with_mouse_and_keyboard(session):
    env = session
    env.inputs.monitor.record("鼠标", False)
    with pytest.raises(UserInterruption, match="中断") as caught:
        env.inputs.check()
    assert caught.value.reason == "takeover"
    def activity():
        assert env.window.focus_calls == 1
        if env.clock.now in range(109, 182, 9):
            kind = "键盘" if (env.clock.now - 100) % 2 else "鼠标"
            env.inputs.monitor.record(kind, False, takeover=kind == "键盘")
        if env.clock.now == 190:
            env.inputs.monitor.record("injected", True)
    env.clock.on_sleep = activity
    env.inputs.prepare_resume(automatic=True)
    assert env.clock.now == 191
    assert env.window.focus_calls == 2
    assert not env.inputs.paused


def test_explicit_pause_interrupts_takeover_wait(session):
    env = session
    env.clock.on_sleep = env.inputs.gate.pause
    with pytest.raises(UserInterruption) as caught:
        env.inputs.prepare_resume(automatic=True)
    assert caught.value.reason == "pause"
    assert env.window.focus_calls == 1


def test_return_to_game_finishes_wait_early(session):
    env = session
    env.window.foreground = False
    env.clock.on_sleep = lambda: setattr(env.window, "foreground", True)
    env.inputs.check()
    assert env.clock.now == 101
    assert env.events[-1]["outcome"] == "foreground"


@pytest.mark.parametrize("hotkey", [False, True])
def test_cancel_and_global_pause_interrupt_activity_wait(session, hotkey):
    env = session
    env.window.foreground = False
    def interrupt():
        if hotkey:
            env.inputs.monitor.record("键盘", False, takeover=False, pause=True)
        else:
            env.inputs.gate.stop()
    env.clock.on_sleep = interrupt
    with pytest.raises(UserInterruption) as caught:
        env.inputs.check()
    assert caught.value.reason == ("pause" if hotkey else "cancel")
    assert env.window.focus_calls == 1
    assert any(e.get("outcome") == "interrupted" for e in env.events)


def test_resume_immediately_focuses_after_release(session):
    env = session
    env.window.foreground = False
    env.inputs.paused = True
    env.inputs.monitor.pause_requested = True
    env.inputs.prepare_resume()
    assert env.clock.now < 102
    assert env.window.focus_calls == 2
    assert not env.inputs.paused
    assert not any(e["event"] == "component_log" for e in env.events)


def test_long_action_releases_before_any_focus_wait(session):
    env = session
    env.window.backend.on_down = lambda: setattr(env.window, "foreground", False)
    with pytest.raises(UserInterruption) as caught:
        env.inputs.execute("key_press", {"key": "esc"})
    assert caught.value.reason == "focus"
    assert env.window.backend.events == [("key", 0x1B, False), ("key", 0x1B, True)]
    assert env.clock.now == 100
    assert not env.inputs.holding
    env.inputs.check()
    assert env.clock.now == 110


def native_backend():
    """只替换 Win32 查询，直接验证正式钩子事件处理。"""
    backend = object.__new__(WindowsInputBackend)
    from lalc.control import PhysicalInputMonitor
    backend.monitor = PhysicalInputMonitor()
    backend.monitor.target_hwnd = 42
    backend._physical_keys = set()
    def client(hwnd, point):
        return True
    def rect(hwnd, value):
        value._obj.left, value._obj.top = 0, 0
        value._obj.right, value._obj.bottom = 600, 300
        return True
    backend.user32 = SimpleNamespace(GetForegroundWindow=lambda: 42,
                                    ScreenToClient=client, GetClientRect=rect,
                                    WindowFromPoint=lambda point: 42, GetAncestor=lambda hwnd, flag: hwnd)
    return backend


def test_click_that_switches_foreground_delays_refocus_from_the_click(session):
    """鼠标回调先看到旧前台，点击其他窗口也必须计入聚焦等待。"""
    env = session
    backend = native_backend()
    backend.monitor = env.inputs.monitor
    backend.user32.WindowFromPoint = lambda point: 99
    env.clock.now = 120
    backend._mouse_event(0x201, SimpleNamespace(flags=0, pt=wintypes.POINT(100, 100)))
    assert backend.monitor.snapshot()[:2] == (0, 120)
    env.window.foreground = False

    def during_wait():
        assert env.window.focus_calls == 1
        if env.clock.now == 125:
            backend._mouse_event(0x200, SimpleNamespace(flags=1, pt=wintypes.POINT(100, 100)))

    env.clock.on_sleep = during_wait
    env.inputs.check()
    assert env.clock.now == 130
    assert env.window.focus_calls == 2
    assert not env.inputs.paused


@pytest.mark.parametrize("message,x,foreground,expected", [
    (0x200, 100, 42, False), (0x201, 100, 42, True),
    (0x202, 100, 42, False), (0x20A, 100, 42, True),
    (0x20E, 100, 42, True), (0x201, 600, 42, False),
    (0x201, 100, 99, False), (0x20A, 100, 99, False),
])
def test_mouse_filter_uses_event_type_client_area_and_foreground(message, x, foreground, expected):
    backend = native_backend()
    backend.user32.GetForegroundWindow = lambda: foreground
    backend._mouse_event(message, SimpleNamespace(flags=0, pt=wintypes.POINT(x, 100)))
    assert backend.monitor.snapshot()[0] == int(expected)
    backend._mouse_event(message, SimpleNamespace(flags=1, pt=wintypes.POINT(x, 100)))
    assert backend.monitor.snapshot()[0] == int(expected)


def test_keyboard_and_global_hotkey_ignore_injected_keys():
    backend = native_backend()
    backend._keyboard_event(0x100, SimpleNamespace(flags=0, vkCode=0x41))
    assert backend.monitor.snapshot()[0] == 1
    backend._keyboard_event(0x101, SimpleNamespace(flags=0, vkCode=0x41))
    assert backend.monitor.snapshot()[0] == 1
    backend.user32.GetForegroundWindow = lambda: 99
    for key in (0xA2, 0xA4, 0x50):
        backend._keyboard_event(0x100, SimpleNamespace(flags=0x10, vkCode=key))
    assert not backend.monitor.pause_requested
    for key in (0xA2, 0xA4, 0x50):
        backend._keyboard_event(0x100, SimpleNamespace(flags=0, vkCode=key))
    assert backend.monitor.pause_requested
    assert backend.monitor.snapshot()[0] == 2


def test_focus_loss_during_drag_reenters_step_without_manual_resume(tmp_path, monkeypatch):
    monkeypatch.setattr(InputSession, "ACTIVITY_SECONDS", 0)
    service, window = service_for(tmp_path)
    window.backend.takeovers = 0
    def blur_once():
        window.foreground = False
        window.backend.on_down = lambda: None
    window.backend.on_down = blur_once
    service.start("tasks.control", {})
    state = finished(service)
    assert state["result"]["status"] == "success"
    assert sum(e["event"] == "input_released" for e in state["trace"]) == 2
    assert not any(e["event"] == "paused_by_user" for e in state["trace"])
    assert any(e.get("reason") == "focus" for e in state["trace"])


def test_first_start_listens_before_immediate_focus_and_manual_resume_skips_idle(tmp_path, monkeypatch):
    service, window = service_for(tmp_path)
    monkeypatch.setattr(InputSession, "ACTIVITY_SECONDS", 999)
    monkeypatch.setattr(InputSession, "QUIET_SECONDS", 0)
    order = []
    create = window.create_input_backend
    focus = window.focus
    def listen():
        order.append("listen")
        return create()
    def activate(hwnd, **kwargs):
        order.append("focus")
        focus(hwnd, **kwargs)
    monkeypatch.setattr(window, "create_input_backend", listen)
    monkeypatch.setattr(window, "focus", activate)
    window.backend.pause_on_next_input()
    service.start("tasks.control", {})
    paused(service)
    assert order == ["listen", "focus"]
    window.foreground = False
    service.resume()
    state = finished(service)
    assert state["result"]["status"] == "success"
    assert order == ["listen", "focus", "focus"]


@pytest.mark.parametrize("stop", [False, True])
def test_plan_startup_waits_on_activity_and_retries_focus_beyond_ten_attempts(tmp_path, monkeypatch, stop):
    """启动置前失败也可等待与取消，确认前台前不执行 Plan。"""
    service, window = service_for(tmp_path)
    clock = Clock()
    monkeypatch.setattr(control.time, "monotonic", lambda: clock.now)
    monkeypatch.setattr(control.time, "sleep", clock.sleep)
    monkeypatch.setattr(InputSession, "ACTIVITY_SECONDS", 10)
    window.foreground = False
    platform = WindowsWindowPlatform.__new__(WindowsWindowPlatform)
    platform.checkpoint = lambda: getattr(window, "checkpoint", lambda: None)()
    attempts, activity = [], []

    def attempt(hwnd):
        attempts.append(clock.now)
        if len(attempts) == 12:
            window.foreground = True
        return False

    def tick():
        if attempts and not activity:
            activity.append(clock.now)
            window.backend.monitor.record("鼠标", False, takeover=False)
        if stop and activity and clock.now >= activity[0] + 2:
            service.stop()

    platform.user32 = SimpleNamespace(
        GetForegroundWindow=lambda: 42 if window.foreground else 99, IsWindow=lambda hwnd: True,
        IsIconic=lambda hwnd: False, SetForegroundWindow=attempt,
    )
    clock.on_sleep = tick
    monkeypatch.setattr(window, "focus", platform.focus)
    monkeypatch.setattr(window, "try_attached_focus",
                        lambda hwnd, pid, foreground, still_idle: attempt(hwnd), raising=False)
    service.start_plan(use_saved_config=False)
    state = finished(service)
    if stop:
        assert state["result"]["failure_code"] == "user_cancelled"
        assert len(attempts) == 1
        assert not any(row["event"] == "component_started" for row in state["trace"])
    else:
        assert state["result"]["status"] == "completed"
        assert len(attempts) == 12 and attempts[1] >= activity[0] + 10
        connected = next(row for row in state["trace"] if row["event"] == "target_window_connected")
        started = next(row for row in state["trace"] if row["event"] == "component_started")
        assert connected["sequence"] < started["sequence"]
    assert window.backend.closed


def test_wait_log_is_readable_in_default_info_view(session, tmp_path):
    import json
    env = session
    env.window.foreground = False
    env.inputs.check()
    directory = tmp_path / "traces"
    directory.mkdir()
    (directory / "1.jsonl").write_text("".join(json.dumps(e) + "\n" for e in env.events), encoding="utf-8")
    boundary = run_logs.snapshot(tmp_path, 1)
    result = run_logs.read_page(tmp_path, 1, boundary, levels={"info"})
    assert len(result["rows"]) == 2
    assert any("等待" in row["text"] for row in result["rows"])


def test_minimized_game_waits_before_restore(session, monkeypatch):
    env = session
    original_info = env.window.window_info
    original_focus = env.window.focus
    minimized = [True]
    def info(hwnd):
        return {**original_info(hwnd), "minimized": minimized[0]}
    def focus(hwnd, *, checkpoint, max_attempts, on_first_attempt, fallback):
        checkpoint()
        assert env.clock.now == 110
        minimized[0] = False
        original_focus(hwnd)
    monkeypatch.setattr(env.window, "window_info", info)
    monkeypatch.setattr(env.window, "focus", focus)
    env.window.foreground = False
    env.inputs.check()
    assert not minimized[0]
    assert not env.inputs.paused


def test_other_application_held_input_delays_focus_without_takeover(session):
    env = session
    env.window.foreground = False
    env.window.backend.pressed = True
    def release():
        if env.clock.now == 112:
            env.window.backend.pressed = False
    env.clock.on_sleep = release
    env.inputs.check()
    assert env.clock.now == 112
    assert not env.inputs.paused


def test_resume_from_gate_checkpoint_also_skips_idle(tmp_path, monkeypatch):
    import threading
    from lalc import task_workflow
    service, window = service_for(tmp_path)
    monkeypatch.setattr(InputSession, "ACTIVITY_SECONDS", 999)
    entered, proceed = threading.Event(), threading.Event()
    @task_workflow
    def execute(ctx, *, operation: str = "drag") -> str:
        entered.set()
        assert proceed.wait(2)
        ctx.action("observe.wait", seconds=0.001)
        return "finished"
    monkeypatch.setattr(service.manifest_manager.default.components["tasks.control"].module, "execute", execute)
    service.start("tasks.control", {})
    assert entered.wait(2)
    service.pause()
    window.foreground = False
    proceed.set()
    service.resume()
    assert finished(service)["result"]["status"] == "success"
    assert window.focus_calls == 2


def test_global_hotkey_works_while_first_focus_is_pending(tmp_path, monkeypatch):
    import threading
    service, window = service_for(tmp_path)
    window.backend.takeovers = 0
    waiting = threading.Event()
    focus = window.focus
    def first_focus(hwnd, **kwargs):
        if not waiting.is_set():
            window.backend.monitor.record("键盘", False, takeover=False, pause=True)
            waiting.set()
            kwargs["checkpoint"]()
        focus(hwnd, **kwargs)
    monkeypatch.setattr(window, "focus", first_focus)
    service.start("tasks.control", {})
    assert waiting.wait(2)
    state = service.wait_for(lambda current: current["paused"])
    assert state["paused"]
    service.resume()
    assert finished(service)["result"]["status"] == "success"


def test_evidence_path_follows_refreshed_observation_after_focus_wait(tmp_path, monkeypatch):
    from lalc import task_workflow
    service, window = service_for(tmp_path)
    monkeypatch.setattr(InputSession, "ACTIVITY_SECONDS", 0)
    @task_workflow
    def execute(ctx, *, operation: str = "drag") -> dict[str, int | str]:
        return ctx.action("observe.capture_screen", save=True)
    monkeypatch.setattr(service.manifest_manager.default.components["tasks.control"].module, "execute", execute)
    original_save = FocusedAutomationSession.save
    def blur_once(session, path, *, evidence_id=None):
        window.foreground = False
        monkeypatch.setattr(FocusedAutomationSession, "save", original_save)
        return original_save(session, path, evidence_id=evidence_id)
    monkeypatch.setattr(FocusedAutomationSession, "save", blur_once)
    service.start("tasks.control", {})
    state = finished(service)
    assert state["result"]["status"] == "success", state["result"]
    result = state["result"]["output"]
    assert result["observation"] == 2
    assert result["evidence_path"].endswith("/2.avif")
    assert [p.name for p in (tmp_path / "evidence" / str(state["run_id"])).iterdir()] == ["2.avif"]


def test_ocr_retries_if_focus_wait_refreshes_source_image(tmp_path, monkeypatch):
    from lalc.application import ApplicationService
    service = ApplicationService(tmp_path)
    window = FakeWindow()
    focused = FocusedAutomationSession(window, lambda *args: None)
    focused.capture()
    inputs = InputSession(focused, window.backend, RunGate(), lambda *args: None)
    monkeypatch.setattr(InputSession, "ACTIVITY_SECONDS", 0)
    service._focused_session = focused
    service._input_session = inputs
    calls = []
    def recognize(image, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            window.foreground = False
        return {"items": [len(calls)]}
    from types import SimpleNamespace
    # 使用独立替身，避免在共享实例上恢复绑定方法后遮蔽其他测试的类替身。
    service.ocr_service = SimpleNamespace(recognize=recognize)
    try:
        assert service._ocr() == {"observation": 2, "items": [2]}
        assert len(calls) == 2
    finally:
        inputs.close()


def test_mouse_over_another_window_does_not_take_over_foreground_game():
    backend = native_backend()
    backend.user32.WindowFromPoint = lambda point: 99
    backend._mouse_event(0x201, SimpleNamespace(flags=0, pt=wintypes.POINT(100, 100)))
    assert backend.monitor.snapshot()[0] == 0


def test_hotkey_during_manual_resume_keeps_run_paused(tmp_path, monkeypatch):
    service, window = service_for(tmp_path)
    monkeypatch.setattr(InputSession, "QUIET_SECONDS", 0)
    window.backend.pause_on_next_input()
    service.start("tasks.control", {})
    paused(service)
    original = window.backend.any_pressed
    def pause_once():
        window.backend.monitor.record("键盘", False, takeover=False, pause=True)
        monkeypatch.setattr(window.backend, "any_pressed", original)
        return False
    monkeypatch.setattr(window.backend, "any_pressed", pause_once)
    service.resume()
    state = paused(service, 2)
    assert state["result"] is None
    service.resume()
    assert finished(service)["result"]["status"] == "success"
