"""覆盖游戏接管过滤、输入诊断日志、全局热键、空闲恢复及失焦释放。

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
from lalc.windows_input import INPUT_EXTRA_INFO, KBDLLHOOKSTRUCT, MSLLHOOKSTRUCT, WindowsInputBackend
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
    assert logs[-1]["duration_seconds"] == 24
    assert logs[-1]["outcome"] == "idle"
    progress = [e for e in logs if "remaining_seconds" in e]
    assert len(progress) == 23
    assert [e["remaining_seconds"] for e in progress[:4]] == [9, 8, 7, 6]
    assert [(e["activity_source"], e["remaining_seconds"]) for e in progress if e["activity_source"]] == [
        ("鼠标", 10), ("键盘", 10),
    ]


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
    env.inputs.POLL_SECONDS = 0.25
    backend = native_backend()
    backend.monitor = env.inputs.monitor
    backend.user32.GetForegroundWindow = lambda: 99

    def return_to_game():
        backend._mouse_event(0x202, MSLLHOOKSTRUCT(pt=wintypes.POINT(100, 80)))
        env.window.foreground = True

    env.clock.on_sleep = return_to_game
    env.inputs.check()
    assert env.clock.now == 100.25
    assert env.events[-1]["outcome"] == "foreground"
    assert "物理鼠标左键松开" in env.events[-2]["message"]
    assert env.inputs.monitor.activities is None


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


def test_first_takeover_keeps_mouse_action_and_client_point(session, tmp_path):
    """同一轮多个接管事件只立即记录最初的动作，且可在历史日志搜索。"""
    import json

    env = session
    backend = native_backend()
    backend.monitor = env.inputs.monitor
    backend._mouse_event(0x20A, MSLLHOOKSTRUCT(pt=wintypes.POINT(100, 80), mouseData=0xFF880000))
    backend._keyboard_event(0x100, KBDLLHOOKSTRUCT(vkCode=0x41, scanCode=0x1E))
    with pytest.raises(UserInterruption, match="物理鼠标滚轮向下"):
        env.inputs.check()
    assert [row["event"] for row in env.events[-2:]] == ["input_takeover", "component_log"]
    log = env.events[-1]
    assert log["input_activity"]["wheel_delta"] == -120
    assert log["client_point"] == (100, 80)
    assert "游戏客户区坐标 (100, 80)" in log["message"]
    assert run_logs.is_live_log(log)
    traces = tmp_path / "traces"
    traces.mkdir()
    (traces / "1.jsonl").write_text(json.dumps(log, ensure_ascii=False) + "\n", encoding="utf-8")
    boundary = run_logs.snapshot(tmp_path, 1)
    matches = run_logs.read_page(tmp_path, 1, boundary, levels={"warning"}, keyword="滚轮向下")
    assert [row["text"] for row in matches["rows"]] == [log["message"]]


@pytest.mark.parametrize("waiting_for", ["focus", "takeover"])
def test_wait_groups_identical_events_without_covering_other_actions(session, monkeypatch, waiting_for):
    """置前与恢复等待合并同类事件，保留不同动作和来源。"""
    env = session
    backend = native_backend()
    backend.monitor = env.inputs.monitor
    backend.user32.GetForegroundWindow = lambda: 99
    monkeypatch.setattr(env.window.backend, "key_name", backend.key_name, raising=False)
    monkeypatch.setattr(env.window.backend, "session_idle_seconds",
                        lambda: env.clock.now - backend.monitor.last_input, raising=False)

    def activity():
        if env.clock.now != 102:
            return
        backend._keyboard_event(0x100, KBDLLHOOKSTRUCT(vkCode=0x41, scanCode=0x1E))
        backend._keyboard_event(0x101, KBDLLHOOKSTRUCT(vkCode=0x41, scanCode=0x1E))
        backend._keyboard_event(0x100, KBDLLHOOKSTRUCT(vkCode=0x41, scanCode=0x1E, flags=0x10))
        backend._keyboard_event(0x100, KBDLLHOOKSTRUCT(vkCode=0x42, flags=0x10, dwExtraInfo=INPUT_EXTRA_INFO))
        for x in range(3):
            backend._mouse_event(0x200, MSLLHOOKSTRUCT(pt=wintypes.POINT(x, 0)))
        backend._mouse_event(0x20C, MSLLHOOKSTRUCT(flags=1, mouseData=2 << 16))
        backend._mouse_event(0x20E, MSLLHOOKSTRUCT(flags=1, mouseData=120 << 16))

    env.clock.on_sleep = activity
    if waiting_for == "focus":
        env.window.foreground = False
        env.inputs.check()
    else:
        env.inputs.wait_after_takeover()

    updates = [row for row in env.events if row.get("input_activity")]
    assert len(updates) == 1
    log = updates[0]
    assert (log["waiting_for"], log["remaining_seconds"]) == (waiting_for, 10)
    assert [(entry["source"], entry["action"], entry["count"]) for entry in log["input_activity"]] == [
        ("物理", "按下", 1), ("物理", "松开", 1), ("外部注入", "按下", 1),
        ("物理", "移动", 3), ("外部注入", "侧键 2 松开", 1), ("外部注入", "滚轮向右", 1),
    ]
    assert "A 按下（VK 0x41，扫描码 0x1E）" in log["message"]
    assert "物理鼠标移动 ×3" in log["message"]
    assert "滚轮向右（+120）" in log["message"]
    assert not log["session_activity_unknown"]
    assert "client_point" not in log
    assert env.inputs.monitor.activities is None


def test_windows_key_name_uses_extended_scan_code():
    backend = native_backend()
    seen = []

    def key_name(flags, name, size):
        seen.append(flags)
        name.value = "Right Ctrl"
        return len(name.value)

    backend.user32.GetKeyNameTextW = key_name
    backend._keyboard_event(0x100, KBDLLHOOKSTRUCT(vkCode=0xA3, scanCode=0x1D, flags=0x01))
    detail, _ = backend.monitor.snapshot()[2]
    assert detail.describe(backend) == "物理键盘 Right Ctrl 按下（VK 0xA3，扫描码 0x1D，扩展键）"
    assert seen == [0x011D0000]


def test_click_that_switches_foreground_delays_refocus_from_the_click(session):
    """鼠标回调先看到旧前台，点击其他窗口也必须计入聚焦等待。"""
    env = session
    backend = native_backend()
    backend.monitor = env.inputs.monitor
    backend.user32.WindowFromPoint = lambda point: 99
    env.clock.now = 120
    backend._mouse_event(0x201, MSLLHOOKSTRUCT(flags=0, pt=wintypes.POINT(100, 100)))
    assert backend.monitor.snapshot()[:2] == (0, 120)
    env.window.foreground = False

    def during_wait():
        assert env.window.focus_calls == 1
        if env.clock.now == 125:
            backend._mouse_event(0x200, MSLLHOOKSTRUCT(flags=1, dwExtraInfo=INPUT_EXTRA_INFO))

    env.clock.on_sleep = during_wait
    env.inputs.check()
    assert env.clock.now == 130
    assert env.window.focus_calls == 2
    assert not env.inputs.paused


@pytest.mark.parametrize("takeover", [False, True])
def test_external_injected_mouse_and_keyboard_reset_idle_wait(session, takeover):
    """远程或辅助输入延长等待，本程序有标记的动作不更新钩子计时。"""
    env = session
    backend = native_backend()
    backend.monitor = env.inputs.monitor
    env.clock.now = 120
    if takeover:
        env.inputs.monitor.record("鼠标", False)
    else:
        env.window.foreground = False

    def activity():
        assert env.window.focus_calls == 1
        if env.clock.now == 126:
            backend._mouse_event(0x200, MSLLHOOKSTRUCT(flags=1, dwExtraInfo=0))
        if env.clock.now == 133:
            backend._keyboard_event(0x100, KBDLLHOOKSTRUCT(flags=0x10, vkCode=0x41, dwExtraInfo=0))
        if env.clock.now == 140:
            backend._mouse_event(0x200, MSLLHOOKSTRUCT(flags=1, dwExtraInfo=INPUT_EXTRA_INFO))
            backend._keyboard_event(0x100, KBDLLHOOKSTRUCT(flags=0x10, vkCode=0x41, dwExtraInfo=INPUT_EXTRA_INFO))

    env.clock.on_sleep = activity
    if takeover:
        env.inputs.prepare_resume(automatic=True)
    else:
        env.inputs.check()
    assert env.clock.now == 143
    assert backend.monitor.snapshot()[0] == (1 if takeover else 0)
    assert not backend.monitor.pause_requested


@pytest.mark.parametrize("takeover", [False, True])
def test_windows_idle_clock_covers_events_not_received_by_the_hooks(session, monkeypatch, takeover):
    """钩子漏报期间仍等到 Windows 会话确认连续空闲十秒。"""
    env = session
    env.clock.now = 120
    if takeover:
        env.inputs.monitor.record("鼠标", False)
    else:
        env.window.foreground = False
    last_activity = [120]
    monkeypatch.setattr(env.window.backend, "session_idle_seconds", lambda: env.clock.now - last_activity[0],
                        raising=False)

    def activity():
        assert env.window.focus_calls == 1
        if env.clock.now in {126, 134}:
            last_activity[0] = env.clock.now

    env.clock.on_sleep = activity
    if takeover:
        env.inputs.prepare_resume(automatic=True)
    else:
        env.inputs.check()
    assert env.clock.now == 144
    resets = [e for e in env.events if e.get("activity_source") == "Windows 会话"]
    assert [e["remaining_seconds"] for e in resets] == [10, 10]
    assert {e["waiting_for"] for e in resets} == {"takeover" if takeover else "focus"}
    assert all(e["session_activity_unknown"] and "来源未知" in e["message"] for e in resets)


def test_windows_idle_clock_handles_tick_counter_wrap():
    backend = native_backend()
    def last_input(info):
        info._obj.dwTime = 0xFFFFFF00
        return True
    backend.user32.GetLastInputInfo = last_input
    backend.kernel32 = SimpleNamespace(GetTickCount=lambda: 0x100)
    assert backend.session_idle_seconds() == 0.512


def test_unobserved_oem_jump_does_not_block_other_keys_or_physical_press():
    backend = native_backend()
    pressed = {0xEA}
    backend.user32.GetAsyncKeyState = lambda key: -32768 if key in pressed else 0
    assert not backend.any_pressed()

    event = KBDLLHOOKSTRUCT(flags=0, vkCode=0xEA)
    backend._keyboard_event(0x100, event)
    assert backend.first_pressed_key() == 0xEA
    backend._keyboard_event(0x101, event)
    assert not backend.any_pressed()

    for key in (0x01, 0x05, 0x10, 0x11, 0x12, 0x41, 0xF6):
        pressed.add(key)
        assert backend.first_pressed_key() == key
        pressed.remove(key)


@pytest.mark.parametrize("message,x,foreground,expected", [
    (0x200, 100, 42, False), (0x201, 100, 42, True),
    (0x202, 100, 42, False), (0x20A, 100, 42, True),
    (0x20E, 100, 42, True), (0x201, 600, 42, False),
    (0x201, 100, 99, False), (0x20A, 100, 99, False),
])
def test_mouse_filter_uses_event_type_client_area_and_foreground(message, x, foreground, expected):
    backend = native_backend()
    backend.user32.GetForegroundWindow = lambda: foreground
    backend._mouse_event(message, MSLLHOOKSTRUCT(flags=0, pt=wintypes.POINT(x, 100)))
    assert backend.monitor.snapshot()[0] == int(expected)
    backend._mouse_event(message, MSLLHOOKSTRUCT(flags=1, dwExtraInfo=INPUT_EXTRA_INFO))
    assert backend.monitor.snapshot()[0] == int(expected)


def test_keyboard_and_global_hotkey_ignore_injected_keys():
    backend = native_backend()
    backend._keyboard_event(0x100, KBDLLHOOKSTRUCT(flags=0, vkCode=0x41))
    assert backend.monitor.snapshot()[0] == 1
    backend._keyboard_event(0x101, KBDLLHOOKSTRUCT(flags=0, vkCode=0x41))
    assert backend.monitor.snapshot()[0] == 1
    backend.user32.GetForegroundWindow = lambda: 99
    for key in (0xA2, 0xA4, 0x50):
        backend._keyboard_event(0x100, KBDLLHOOKSTRUCT(flags=0x10, vkCode=key, dwExtraInfo=0))
    assert not backend.monitor.pause_requested
    for key in (0xA2, 0xA4, 0x50):
        backend._keyboard_event(0x100, KBDLLHOOKSTRUCT(flags=0, vkCode=key))
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
    assert len(result["rows"]) == 11
    assert any("还剩 9 秒" in row["text"] for row in result["rows"])


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


def test_other_application_held_input_delays_focus_without_takeover(session, monkeypatch):
    env = session
    env.window.foreground = False
    env.window.backend.pressed = True
    monkeypatch.setattr(env.window.backend, "first_pressed_key", lambda: 0x11, raising=False)
    def release():
        if env.clock.now == 112:
            env.window.backend.pressed = False
    env.clock.on_sleep = release
    env.inputs.check()
    assert env.clock.now == 112
    assert not env.inputs.paused
    blocked = [e for e in env.events if e.get("blocking_vk") == 0x11]
    assert [e["remaining_seconds"] for e in blocked] == [0, 0]


def test_click_logs_blocking_key_once_per_second_until_release(session, monkeypatch):
    env = session
    env.window.foreground = True
    env.clock.now = 128
    env.inputs.POLL_SECONDS = 0.25
    backend = native_backend()
    backend.user32.GetAsyncKeyState = lambda key: -32768 if key == 0x41 and env.clock.now < 131 else 0
    monkeypatch.setattr(env.window.backend, "first_pressed_key", backend.first_pressed_key, raising=False)
    monkeypatch.setattr(env.window.backend, "any_pressed", backend.any_pressed)
    # 浮点时钟替身也必须能越过点击保持时间的最后一个轮询点。
    monkeypatch.setattr(control.time, "sleep", lambda seconds: env.clock.sleep(max(seconds, 0.000001)))
    logs = []

    def record(event, fields):
        if event == "component_log" and fields.get("waiting_for") == "click":
            logs.append((env.clock.now, fields["blocking_vk"]))
        env.events.append({"event": event, **fields})

    env.inputs.emit = record
    env.inputs.execute("click", {"x": 100, "y": 100, "centerxy": None})
    assert logs == [(128, 0x41), (129, 0x41), (130, 0x41)]
    assert [event["event"] for event in env.events if event["event"].startswith("input_")] == [
        "input_pressed", "input_released",
    ]


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
    backend._mouse_event(0x201, MSLLHOOKSTRUCT(flags=0, pt=wintypes.POINT(100, 100)))
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
