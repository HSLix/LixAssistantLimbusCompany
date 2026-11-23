"""覆盖滚轮参数、逐格中断、正式分发和 Win32 注入。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_scroll_action.py
"""

import ctypes
from types import SimpleNamespace

import pytest

from lalc import step
from lalc.actions import scroll
from lalc.control import InputSession
from lalc.focused import FocusedAutomationSession, WindowError
from lalc.runtime import RunGate, UserInterruption
from lalc.windows_input import INPUT, WindowsInputBackend
from test_input_control import FakeWindow, finished, service_for


def install_scroll_backend(monkeypatch, window):
    """模拟鼠标位置及滚轮回调，不安装系统钩子。"""
    cursor = {"x": -1, "y": -1, "inside": False}

    def move(x, y):
        window.backend.events.append(("move", x, y))
        cursor.update(x=x - 10, y=y - 20, inside=True)

    def wheel(delta):
        window.backend.events.append(("wheel", delta))
        window.backend.monitor.record("鼠标", True)
        window.backend.on_down()

    monkeypatch.setattr(window.backend, "move_cursor", move, raising=False)
    monkeypatch.setattr(window.backend, "wheel", wheel, raising=False)
    monkeypatch.setattr(window.backend, "park_cursor",
                        lambda hwnd: cursor.update(x=-1, y=-1, inside=False), raising=False)
    monkeypatch.setattr(window, "cursor_position", lambda hwnd: dict(cursor))
    return cursor


@pytest.fixture
def scrolling(monkeypatch):
    window = FakeWindow()
    cursor = install_scroll_backend(monkeypatch, window)
    focused = FocusedAutomationSession(window, lambda *_: None)
    focused.connect()
    gate = RunGate()
    session = InputSession(focused, window.backend, gate, lambda *_: None)
    waits = []

    def wait(seconds):
        waits.append(seconds)
        session.check()

    monkeypatch.setattr(session, "_wait", wait)
    yield session, window, cursor, gate, waits
    session.close()


@pytest.mark.parametrize("direction,steps,delta", [("up", 1, 120), ("down", 3, -120), ("up", 10, 120)])
def test_scroll_moves_then_sends_ticks_with_fixed_gaps(scrolling, direction, steps, delta):
    session, window, cursor, _, waits = scrolling
    session.execute("scroll", dict(x=100, y=100, direction=direction, steps=steps))
    assert window.backend.events == [("move", 110, 120)] + [("wheel", delta)] * steps
    assert waits == [0.2] * steps  # 首次等待移动稳定，随后只在相邻格之间等待。
    assert cursor == dict(x=100, y=100, inside=True)
    assert not session.holding and not session.paused


@pytest.mark.parametrize("invalid", [
    dict(steps=0), dict(steps=11), dict(steps=True), dict(steps=1.5),
    dict(direction="UP"), dict(direction="left"), dict(direction=[]),
    dict(x=-1), dict(x=600), dict(y=300), dict(x=True), dict(y=1.5),
])
def test_scroll_rejects_invalid_parameters_before_moving(scrolling, invalid):
    session, window, *_ = scrolling
    with pytest.raises(ValueError):
        session.execute("scroll", dict(dict(x=100, y=100, direction="up", steps=1), **invalid))
    assert window.backend.events == []


@pytest.mark.parametrize("stop", ["takeover", "cancel", "pause", "focus", "cursor", "failure"])
def test_scroll_stops_after_first_tick(scrolling, stop):
    session, window, cursor, gate, _ = scrolling

    def interrupt():
        if stop == "takeover":
            window.backend.monitor.record("鼠标", False)
        elif stop == "cancel":
            gate.stop()
        elif stop == "pause":
            gate.pause()
        elif stop == "focus":
            window.foreground = False
        elif stop == "cursor":
            cursor["x"] += 20
        else:
            raise OSError("wheel rejected")

    window.backend.on_down = interrupt
    with pytest.raises(OSError if stop == "failure" else UserInterruption):
        session.execute("scroll", dict(x=100, y=100, direction="down", steps=3))
    assert window.backend.events == [("move", 110, 120), ("wheel", -120)]
    assert not session.holding
    assert window.focus_calls == 1


def test_cursor_movement_failure_prevents_wheel(scrolling, monkeypatch):
    session, window, *_ = scrolling
    monkeypatch.setattr(window.backend, "move_cursor", lambda *args: None)
    with pytest.raises(UserInterruption):
        session.execute("scroll", dict(x=100, y=100, direction="down", steps=1))
    assert window.backend.events == []
    assert not session.holding


@pytest.mark.parametrize("arguments", [dict(centerxy=(1, 2), x=1), dict(x=1), dict()])
def test_scroll_coordinate_forms_are_exclusive(arguments):
    with pytest.raises(ValueError):
        scroll(None, direction="down", **arguments)


@pytest.mark.parametrize("use_center", [False, True])
def test_registered_action_runs_through_executor_with_trace(tmp_path, monkeypatch, use_center):
    service, window = service_for(tmp_path)
    install_scroll_backend(monkeypatch, window)
    monkeypatch.setattr(InputSession, "_wait", lambda self, seconds: self.check())

    @step
    def execute(ctx) -> None:
        ctx.action("observe.capture_screen")
        if use_center:
            ctx.action("control.scroll", centerxy=(100, 100), direction="down")
        else:
            ctx.action("control.scroll", x=100, y=100, direction="down")

    monkeypatch.setattr(service.manifest_manager.default.components["steps.control"].module, "execute", execute)
    service.start("steps.control", {})
    state = finished(service)
    assert state["result"]["status"] == "success", state["result"]
    assert window.backend.events == [("move", 110, 120), ("wheel", -120)]
    action = next(event for event in state["trace"]
                  if event["event"] == "trusted_action_returned" and event["logical_name"] == "control.scroll")
    assert action["classification"] == "control"
    assert action["inputs"]["steps"] == 1
    assert "debug_image" in action
    assert window.backend.closed


def test_partial_scroll_reenters_step_after_automatic_wait(tmp_path, monkeypatch):
    service, window = service_for(tmp_path)
    install_scroll_backend(monkeypatch, window)
    monkeypatch.setattr(InputSession, "_wait", lambda self, seconds: self.check())
    monkeypatch.setattr(InputSession, "ACTIVITY_SECONDS", 0)

    def take_over_once():
        window.backend.monitor.record("鼠标", False)
        window.backend.on_down = lambda: None

    window.backend.on_down = take_over_once

    @step
    def execute(ctx) -> None:
        ctx.action("observe.capture_screen")
        ctx.action("control.scroll", x=100, y=100, direction="up", steps=3)

    monkeypatch.setattr(service.manifest_manager.default.components["steps.control"].module, "execute", execute)
    service.start("steps.control", {})
    state = finished(service)
    assert state["result"]["status"] == "success", state["result"]
    assert any(row.get("waiting_for") == "takeover" for row in state["trace"])
    # 已发送的一格保留，恢复后按既有语义重入 Step，重新发送三格。
    assert window.backend.events.count(("wheel", 120)) == 4
    assert sum(event["event"] == "trusted_action_interrupted" and
               event["logical_name"] == "control.scroll" for event in state["trace"]) == 1


def test_native_scroll_movement_and_signed_wheel_data(monkeypatch):
    monkeypatch.setattr(ctypes, "set_last_error", lambda _: None, raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 5, raising=False)
    backend = WindowsInputBackend.__new__(WindowsInputBackend)
    events = []

    def send(count, pointer, size):
        item = ctypes.cast(pointer, ctypes.POINTER(INPUT)).contents
        events.append((item.type, item.mi.dx, item.mi.dy, item.mi.mouseData,
                       item.mi.dwFlags, item.mi.dwExtraInfo, size))
        return 1

    backend.user32 = SimpleNamespace(SendInput=send, GetSystemMetrics=lambda index: {
        76: -1920, 77: 0, 78: 3840, 79: 1080}[index])
    backend.move_cursor(-960, 350)
    backend.wheel(120)
    backend.wheel(-120)
    assert events == [
        (0, round(960 * 65535 / 3839), round(350 * 65535 / 1079), 0, 0xC001, 0x4C414C43, ctypes.sizeof(INPUT)),
        (0, 0, 0, 120, 0x0800, 0x4C414C43, ctypes.sizeof(INPUT)),
        (0, 0, 0, 0xFFFFFF88, 0x0800, 0x4C414C43, ctypes.sizeof(INPUT)),
    ]
    with pytest.raises(WindowError):
        backend.move_cursor(-1921, 350)
    assert len(events) == 3
    backend.user32.SendInput = lambda *_: 0
    with pytest.raises(OSError, match="Wheel SendInput failed"):
        backend.wheel(120)
    with pytest.raises(OSError, match="Cursor SendInput failed"):
        backend.move_cursor(0, 0)
