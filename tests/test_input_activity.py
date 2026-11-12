"""覆盖游戏接管过滤、全局热键、十秒空闲、立即恢复及长动作失焦释放。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_input_activity.py
"""

from ctypes import wintypes
from types import SimpleNamespace

import pytest

from lalc import control, run_logs
from lalc.control import InputSession
from lalc.focused import FocusedAutomationSession
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
            env.inputs.monitor.record("鼠标", False, takeover=False, other_application=True)
    env.clock.on_sleep = activity
    env.inputs.check()
    assert env.clock.now == 115
    assert env.window.focus_calls == 2
    assert env.events[-1]["event"] != "input_takeover"
    logs = [e for e in env.events if e["event"] == "component_log"]
    assert len(logs) == 2
    assert logs[-1]["duration_seconds"] == 15
    assert logs[-1]["outcome"] == "idle"


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
    def activate(hwnd):
        order.append("focus")
        focus(hwnd)
    monkeypatch.setattr(window, "create_input_backend", listen)
    monkeypatch.setattr(window, "focus", activate)
    window.backend.takeovers = 1
    service.start("tasks.control", {})
    paused(service)
    assert order == ["listen", "focus"]
    window.foreground = False
    service.resume()
    state = finished(service)
    assert state["result"]["status"] == "success"
    assert order == ["listen", "focus", "focus"]


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
    def focus(hwnd):
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
    def first_focus(hwnd):
        if not waiting.is_set():
            window.backend.monitor.record("键盘", False, takeover=False, pause=True)
            waiting.set()
            window.checkpoint()
        focus(hwnd)
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
    assert result["evidence_path"].endswith("/2.png")
    assert [p.name for p in (tmp_path / "evidence" / str(state["run_id"])).iterdir()] == ["2.png"]


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
    window.backend.takeovers = 1
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
