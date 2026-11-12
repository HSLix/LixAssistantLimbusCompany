"""覆盖截图鼠标归位、接管恢复、重试及 Win32 注入坐标。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_capture_cursor.py
"""

import ctypes
from types import SimpleNamespace

import pytest

from lalc.control import InputSession
from lalc.focused import FocusedAutomationSession, WindowError
from lalc.runtime import RunGate, UserInterruption
from lalc.windows_input import INPUT, WindowsInputBackend
from test_input_control import FakeWindow, finished, paused, service_for


def cursor_window(monkeypatch, window):
    """记录鼠标内外状态与移动次数，保留真实输入所有权实现。"""
    state = {"inside": True, "moves": 0}
    monkeypatch.setattr(window, "cursor_position", lambda hwnd: dict(state))

    def move(hwnd):
        state["moves"] += 1
        state["inside"] = False

    monkeypatch.setattr(window.backend, "park_cursor", move, raising=False)
    return state


def test_capture_parks_only_inside_and_can_be_disabled(monkeypatch):
    window = FakeWindow()
    cursor = cursor_window(monkeypatch, window)
    session = FocusedAutomationSession(window, lambda *args: None)
    session.capture(auto_park_cursor=False)
    assert cursor["moves"] == 0
    session.capture()
    assert cursor["moves"] == 1
    assert window.backend.closed
    assert session.before_check is session.before_capture is None
    session.capture()
    assert cursor["moves"] == 1
    with pytest.raises(ValueError, match="bool"):
        session.capture(auto_park_cursor=1)


@pytest.mark.parametrize("waiting", [False, True])
def test_takeover_or_activity_wait_never_moves_cursor(monkeypatch, waiting):
    window = FakeWindow()
    cursor = cursor_window(monkeypatch, window)
    session = FocusedAutomationSession(window, lambda *args: None)
    session.connect()
    inputs = InputSession(session, window.backend, RunGate(), lambda *args: None)
    try:
        if waiting:
            window.foreground = False
            def interrupt_wait(*args):
                assert cursor["moves"] == window.captures == 0
                window.backend.monitor.record("鼠标", False)
                inputs.check_ownership()
            monkeypatch.setattr(inputs, "wait_for_activity", interrupt_wait)
        else:
            window.backend.monitor.record("鼠标", False)
        with pytest.raises(UserInterruption):
            session.capture()
        assert cursor["moves"] == window.captures == 0
        assert session.image is None
    finally:
        inputs.close()


def test_takeover_during_parking_resumes_with_fresh_position(tmp_path, monkeypatch):
    from lalc import task_workflow
    service, window = service_for(tmp_path)
    cursor = cursor_window(monkeypatch, window)
    move = window.backend.park_cursor

    def interrupted_move(hwnd):
        move(hwnd)
        if cursor["moves"] == 1:
            window.backend.monitor.record("鼠标", False)
            cursor["inside"] = True

    monkeypatch.setattr(window.backend, "park_cursor", interrupted_move)
    @task_workflow
    def execute(ctx, *, operation: str = "drag") -> dict[str, int | str]:
        return ctx.action("observe.capture_screen")
    monkeypatch.setattr(service.manifest_manager.default.components["tasks.control"].module, "execute", execute)
    service.start("tasks.control", {})
    paused(service)
    assert cursor["moves"] == 1 and window.captures == 0
    assert service._focused_session.image is None
    service.resume()
    state = finished(service)
    assert state["result"]["status"] == "success", state["result"]
    assert cursor["moves"] == 2 and not cursor["inside"]


def test_mouse_reentering_during_capture_discards_frame(monkeypatch):
    window = FakeWindow()
    cursor = cursor_window(monkeypatch, window)
    capture = window.capture
    def reenter(hwnd, width, height):
        if window.captures == 0:
            cursor["inside"] = True
        return capture(hwnd, width, height)
    monkeypatch.setattr(window, "capture", reenter)
    session = FocusedAutomationSession(window, lambda *args: None)
    assert session.capture()["observation"] == 1
    assert window.captures == cursor["moves"] == 2


def test_parking_failure_never_exposes_image(monkeypatch):
    window = FakeWindow()
    cursor_window(monkeypatch, window)
    monkeypatch.setattr(window.backend, "park_cursor", lambda hwnd: None)
    session = FocusedAutomationSession(window, lambda *args: None)
    with pytest.raises(WindowError, match="Cannot park"):
        session.capture()
    assert window.captures == 0 and session.image is None
    assert window.backend.closed


def test_native_parking_uses_virtual_desktop_and_injected_move():
    backend = WindowsInputBackend.__new__(WindowsInputBackend)
    sent = []
    def rect(hwnd, pointer):
        pointer._obj.right, pointer._obj.bottom = -100, 200
        return 1
    def send(count, pointer, size):
        value = ctypes.cast(pointer, ctypes.POINTER(INPUT)).contents
        sent.append((value.mi.dx, value.mi.dy, value.mi.dwFlags, size))
        return 1
    backend.user32 = SimpleNamespace(GetWindowRect=rect, SendInput=send,
        GetSystemMetrics=lambda i: {76: -1920, 77: 0, 78: 3840, 79: 1080}[i])
    backend.park_cursor(42)
    assert sent == [(round(1828 * 65535 / 3839), round(208 * 65535 / 1079),
                     0xC001, ctypes.sizeof(INPUT))]
    backend.user32.GetSystemMetrics = lambda i: {76: -1920, 77: 0, 78: 1820, 79: 1080}[i]
    with pytest.raises(WindowError, match="No desktop space"):
        backend.park_cursor(42)
    assert len(sent) == 1


def test_action_can_disable_automatic_parking(tmp_path, monkeypatch):
    from lalc import task_workflow
    service, window = service_for(tmp_path)
    cursor = cursor_window(monkeypatch, window)
    @task_workflow
    def execute(ctx, *, operation: str = "drag") -> dict[str, int | str]:
        return ctx.action("observe.capture_screen", auto_park_cursor=False)
    monkeypatch.setattr(service.manifest_manager.default.components["tasks.control"].module, "execute", execute)
    service.start("tasks.control", {})
    state = finished(service)
    assert state["result"]["status"] == "success", state["result"]
    assert window.captures == 1 and cursor["moves"] == 0
