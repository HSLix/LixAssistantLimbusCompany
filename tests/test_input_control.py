"""覆盖前台输入、接管释放、手动 Step 重入、条件失败与 Plan 终止。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen UV_CACHE_DIR=.generated/uv-cache uv run --frozen pytest -q tests/test_input_control.py
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from lalc.application import ApplicationService
from lalc.control import InputSession, PhysicalInputMonitor
from lalc.focused import FocusedAutomationSession
from lalc.manifest import ManifestManager
from lalc.runtime import InputReleaseFailure, UserInterruption, RunGate


FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "focused-control"


class FakeInput:
    """记录注入顺序，并在长动作中制造一次真实用户接管。"""

    def __init__(self) -> None:
        self.monitor = PhysicalInputMonitor()
        self.events = []
        self.takeovers = 0
        self.fail_release = False
        self.closed = False
        self.pressed = False
        self.on_down = lambda: None

    def any_pressed(self) -> bool:
        return self.pressed

    def client_point(self, hwnd, x, y):
        return x + 10, y + 20

    def create_touch(self):
        self.events.append("create")
        return 1

    def touch(self, device, x, y, phase):
        self.events.append((phase, x, y))
        if phase == "up" and self.fail_release:
            raise OSError(5, "touch release denied")
        self.monitor.record("mouse", True)
        if phase == "down":
            self.on_down()
        if phase == "down" and self.takeovers:
            self.takeovers -= 1
            self.monitor.record("鼠标", False)

    def destroy_touch(self, device):
        self.events.append("destroy")

    def key(self, key, up):
        self.events.append(("key", key, up))
        self.monitor.record("keyboard", True)
        if not up:
            self.on_down()
            if self.takeovers:
                self.takeovers -= 1
                self.monitor.record("键盘", False)
        elif self.fail_release:
            raise OSError(5, "key release denied")

    def close(self):
        self.closed = True


class FakeWindow:
    """复用应用服务的真实会话，仅替换 Windows 窗口和输入 API。"""

    def __init__(self) -> None:
        self.backend = FakeInput()
        self.focus_calls = 0
        self.captures = 0
        self.foreground = False
        self.ready = True
        self.capture_error = False
        self.width = 600
        self.height = 300

    def find_windows(self):
        return [42]

    def focus(self, hwnd):
        self.focus_calls += 1
        self.foreground = True

    def window_info(self, hwnd):
        return {"hwnd": hwnd, "process_id": 7, "valid": True, "visible": True,
                "minimized": False, "foreground": self.foreground,
                "title": "LimbusCompany", "width": self.width, "height": self.height}

    def capture(self, hwnd, width, height):
        self.captures += 1
        if self.capture_error:
            raise OSError(5, "capture denied")
        return bytes(width * height * 4)

    def create_input_backend(self):
        return self.backend


@pytest.fixture(autouse=True)
def fast_quiet(monkeypatch):
    monkeypatch.setattr(InputSession, "QUIET_SECONDS", 0.001)


def service_for(tmp_path: Path, *, condition: str = ""):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "assets.json").write_text("{}", encoding="utf-8")
    for path in FIXTURE.glob("*.py"):
        (candidate / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    step = (candidate / "steps.control.py").read_text(encoding="utf-8")
    step += condition
    (candidate / "steps.control.py").write_text(step, encoding="utf-8")
    task = '''"""证明调用者只在当前 Step 正常返回后继续。"""
from lalc import task_workflow

@task_workflow
def execute(ctx, *, operation: str = "drag") -> str:
    ctx.call("steps.control", operation=operation, seconds=0.03)
    return "finished"

'''
    (candidate / "task.py").write_text(task, encoding="utf-8")
    manifest = json.loads((FIXTURE / "manifest.json").read_text(encoding="utf-8"))
    manifest["components"]["tasks.control"] = {"source_path": "task.py"}
    (candidate / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    manager = ManifestManager(tmp_path)
    published = manager.publish(candidate / "manifest.json")
    assert published.ok, published.errors
    assert manager.set_default(published.loaded.manifest_id).ok
    window = FakeWindow()
    service = ApplicationService(tmp_path, manifest_manager=manager, window_platform=window)
    return service, window


def wait_state(service, predicate):
    """超时暴露卡住的暂停路径，避免测试无限等待。"""

    with service._condition:
        assert service._condition.wait_for(lambda: predicate(service.state), timeout=3), service.state
    return service.state


def finished(service):
    return wait_state(service, lambda state: state["phase"] == "finished")


def paused(service, count=1):
    return wait_state(service, lambda state: state["paused"] and not state["resume_pending"] and
                      sum(event["event"] == "paused_by_user" for event in state["trace"]) >= count)


@pytest.mark.parametrize("key,code", [("esc", 27), ("p", 80), ("enter", 13)])
def test_supported_keys_use_down_up_and_do_not_misclassify_injection(tmp_path, key, code):
    service, window = service_for(tmp_path)
    service.start("steps.control", {"key": key})
    state = finished(service)
    assert state["result"]["status"] == "success"
    assert window.backend.events == [("key", code, False), ("key", code, True)]
    assert window.backend.closed
    assert not any(event["event"] == "paused_by_user" for event in state["trace"])


@pytest.mark.parametrize("operation", ["drag", "click", "key_press"])
def test_takeover_releases_once_then_reenters_same_step_manually(tmp_path, operation):
    service, window = service_for(tmp_path)
    window.backend.takeovers = 1
    service.start("tasks.control", {"operation": operation})
    state = paused(service)
    assert state["pause_info"]["logical_name"] == "steps.control"
    assert not state["pause_info"]["has_condition"]
    assert not any(event["event"] == "verification_started" for event in state["trace"])
    assert sum(event["event"] == "input_released" for event in state["trace"]) == 1
    assert window.focus_calls == 1
    interrupted = next(event for event in state["trace"] if event["event"] == "step_interrupted")
    assert interrupted["outcome"] == "unknown"
    assert "UserInterruption" in interrupted["traceback"]
    service.resume()
    state = finished(service)
    assert state["result"]["output"] == "finished"
    assert window.focus_calls == 2
    assert sum(event["event"] == "input_released" for event in state["trace"]) == 2
    assert not any(event["event"] == "recovery_rule_started" for event in state["trace"])
    steps = [event for event in state["trace"] if event["event"] == "component_started" and event["role"] == "step"]
    assert len(steps) == 2 and steps[0]["parent_call_id"] == steps[1]["parent_call_id"]


def test_repeated_takeover_requires_separate_resume(tmp_path):
    service, window = service_for(tmp_path)
    window.backend.takeovers = 2
    service.start("tasks.control", {})
    paused(service)
    service.resume()
    paused(service, 2)
    service.resume()
    assert finished(service)["result"]["status"] == "success"


@pytest.mark.parametrize("problem", ["false", "error"])
def test_resume_condition_failure_stays_paused_without_new_input(tmp_path, monkeypatch, problem):
    service, window = service_for(tmp_path, condition='''
def condition(ctx, *, operation: str = "key_press", key: str = "esc", x: int = 100,
              y: int = 100, end_x: int = 300, end_y: int = 100, seconds: float = 2.5) -> bool:
    return True
''')

    def check(ctx, *, operation: str = "key_press", key: str = "esc", x: int = 100,
              y: int = 100, end_x: int = 300, end_y: int = 100, seconds: float = 2.5) -> bool:
        if not window.ready and problem == "error":
            raise OSError(5, "condition observation denied")
        return window.ready

    monkeypatch.setattr(service.manifest_manager.default.components["steps.control"].module, "condition", check)
    window.backend.takeovers = 1
    service.start("tasks.control", {})
    paused(service)
    window.ready = False
    service.resume()
    state = paused(service, 2)
    assert len([e for e in window.backend.events if isinstance(e, tuple) and e[0] == "down"]) == 1
    rejected = next(event for event in state["trace"] if event["event"] == "input_resume_rejected")
    assert "Traceback" in rejected["traceback"]
    if problem == "error":
        assert "condition observation denied" in rejected["traceback"]
    window.ready = True
    service.resume()
    assert finished(service)["result"]["status"] == "success"


def test_release_failure_ends_plan_without_resume_or_later_task(tmp_path):
    service, window = service_for(tmp_path)
    window.backend.takeovers = 1
    window.backend.fail_release = True
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"items": [{"task": "tasks.control", "inputs": {}}] * 2}), encoding="utf-8")
    service.start_plan(plan)
    state = finished(service)
    assert state["result"]["reason"] == "input_release_failed"
    assert len(state["result"]["items"]) == 1
    failed = next(event for event in state["trace"] if event["event"] == "plan_item_finished")["result"]
    assert failed["failure_code"] == "input_release_failed"
    assert "touch release denied" in failed["traceback"]
    assert "UserInterruption" in failed["traceback"]
    assert not any(event["event"] in {"safe_task_termination", "input_released", "paused_by_user"} for event in state["trace"])
    assert len([e for e in window.backend.events if isinstance(e, tuple) and e[0] == "up"]) == 1
    assert window.backend.closed
    service.resume()
    assert service.state["phase"] == "finished"


def test_wait_observes_takeover_and_can_be_cancelled(tmp_path, monkeypatch):
    service, window = service_for(tmp_path)
    entered = threading.Event()
    original_wait = InputSession._wait

    def wait(self, duration, update=None):
        entered.set()
        window.backend.monitor.record("键盘", False)
        original_wait(self, duration, update)

    monkeypatch.setattr(InputSession, "_wait", wait)
    service.start("tasks.control", {"operation": "wait"})
    assert entered.wait(2)
    paused(service)
    service.stop()
    assert finished(service)["result"]["failure_code"] == "user_cancelled"


def test_quiet_resume_waits_for_released_input_without_another_resume(tmp_path, monkeypatch):
    service, window = service_for(tmp_path)
    window.backend.takeovers = 1
    service.start("tasks.control", {})
    paused(service)
    window.backend.pressed = True
    waiting = threading.Event()

    def any_pressed():
        if window.backend.pressed:
            waiting.set()
        return window.backend.pressed

    monkeypatch.setattr(window.backend, "any_pressed", any_pressed)
    service.resume()
    assert waiting.wait(2)
    assert service.state["resume_pending"]
    assert window.focus_calls == 1
    window.backend.pressed = False
    assert finished(service)["result"]["status"] == "success"


def test_focus_loss_pauses_without_automatic_refocus_and_clears_image():
    window = FakeWindow()
    events = []
    focused = FocusedAutomationSession(window, lambda event, fields: events.append(event))
    focused.capture()
    session = InputSession(focused, window.backend, RunGate(), lambda event, fields: events.append(event))
    window.foreground = False
    with pytest.raises(UserInterruption):
        session.execute("key_press", {"key": "esc"})
    assert focused.image is None and window.focus_calls == 1
    assert not window.backend.events


def test_cancellation_during_held_key_releases_once():
    window = FakeWindow()
    focused = FocusedAutomationSession(window, lambda event, fields: None)
    focused.connect()
    gate = RunGate()
    session = InputSession(focused, window.backend, gate, lambda event, fields: None)
    window.backend.on_down = gate.stop
    with pytest.raises(UserInterruption):
        session.execute("key_press", {"key": "p"})
    assert window.backend.events == [("key", 80, False), ("key", 80, True)]


def test_step_controls_screenshot_timing_and_invalid_coordinates_never_inject():
    window = FakeWindow()
    focused = FocusedAutomationSession(window, lambda event, fields: None)
    focused.capture()
    session = InputSession(focused, window.backend, RunGate(), lambda event, fields: None)
    session.execute("key_press", {"key": "p"})
    session.execute("key_press", {"key": "enter"})
    assert window.captures == 1 and focused.image is not None
    before = len(window.backend.events)
    with pytest.raises(ValueError):
        session.execute("click", {"x": -1, "y": 0})
    assert len(window.backend.events) == before


def test_monitor_distinguishes_injected_events_and_preserves_listener_failure():
    monitor = PhysicalInputMonitor()
    monitor.record("keyboard", True)
    assert monitor.snapshot()[0] == 0
    monitor.record("mouse", False)
    assert monitor.snapshot()[0] == 1
    monitor.error = OSError(5, "hook failed")
    with pytest.raises(RuntimeError) as caught:
        monitor.snapshot()
    assert isinstance(caught.value.__cause__, OSError)


def test_cli_requires_explicit_manual_resume(tmp_path, monkeypatch, capsys):
    import lalc.__main__ as cli

    service, window = service_for(tmp_path)
    window.backend.takeovers = 1
    monkeypatch.setattr(cli, "default_data_root", lambda: tmp_path)
    monkeypatch.setattr(cli, "ApplicationService", lambda *args, **kwargs: service)
    requested = []

    def answer(prompt):
        requested.append(prompt)
        assert service.state["paused"]
        return "r"

    monkeypatch.setattr("builtins.input", answer)
    assert cli.main(["run", "tasks.control"]) == 0
    output = capsys.readouterr()
    assert len(requested) == 1
    assert json.loads(output.out)["output"] == "finished"
    assert "自动化已暂停" in output.err


def test_cli_release_failure_shows_full_original_stack(tmp_path, monkeypatch, capsys):
    import lalc.__main__ as cli

    service, window = service_for(tmp_path)
    window.backend.takeovers = 1
    window.backend.fail_release = True
    monkeypatch.setattr(cli, "default_data_root", lambda: tmp_path)
    monkeypatch.setattr(cli, "ApplicationService", lambda *args, **kwargs: service)
    assert cli.main(["run", "tasks.control"]) == 1
    output = capsys.readouterr()
    assert json.loads(output.out)["failure_code"] == "input_release_failed"
    assert "Traceback (most recent call last):" in output.err
    assert "touch release denied" in output.err
    assert "UserInterruption" in output.err


def test_gui_notice_comes_forward_once_and_displays_original_traceback(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from lalc.gui import MainWindow

    app = QApplication.instance() or QApplication([])
    service, _ = service_for(tmp_path)
    window = MainWindow(service)
    calls = []
    monkeypatch.setattr(window, "activateWindow", lambda: calls.append("activate"))
    monkeypatch.setattr(window, "raise_", lambda: calls.append("raise"))
    state = service.state
    state.update(phase="running", paused=True, pause_info={
        "reason": "检测到用户接管", "description": "请回到邮箱页面", "has_condition": False,
        "traceback": "Traceback (most recent call last):\n  original_function\nOSError: denied\n",
    })
    window.render_state(state)
    window.render_state(state)
    state["resume_pending"] = True
    window.render_state(state)
    assert calls == ["raise", "activate"]
    assert "请回到邮箱页面" in window.pause_notice.text()
    assert "从头执行" in window.pause_notice.text()
    assert "\n  original_function\n" in window.trace.toPlainText()
    assert not window.pause_button.isEnabled()
    window.close()


def test_observe_action_cannot_bypass_control_role(tmp_path, monkeypatch):
    service, window = service_for(tmp_path)

    def bypass(ctx, *, save: bool = False) -> dict[str, int | str]:
        ctx.control_input("key_press", key="p")
        return {}

    from types import MappingProxyType
    from lalc.actions import TrustedAction
    manager = service.manifest_manager
    manager.actions = MappingProxyType({**manager.actions, "observe.capture_screen": TrustedAction(bypass, "observe")})
    service.start("steps.control", {})
    result = finished(service)["result"]
    assert result["status"] == "failure"
    assert "control Trusted Action" in result["failure_message"]
    assert not window.backend.events


def test_key_release_failure_is_terminal_and_keeps_original_exception():
    window = FakeWindow()
    focused = FocusedAutomationSession(window, lambda event, fields: None)
    focused.connect()
    window.backend.takeovers = 1
    window.backend.fail_release = True
    session = InputSession(focused, window.backend, RunGate(), lambda event, fields: None)
    with pytest.raises(InputReleaseFailure) as caught:
        session.execute("key_press", {"key": "enter"})
    assert isinstance(caught.value.__cause__, OSError)
    assert window.backend.events == [("key", 13, False), ("key", 13, True)]
    with pytest.raises(InputReleaseFailure):
        session.execute("key_press", {"key": "enter"})
    assert len(window.backend.events) == 2


def test_failed_resume_capture_remains_paused_with_original_traceback(tmp_path):
    service, window = service_for(tmp_path)
    window.backend.takeovers = 1
    service.start("tasks.control", {})
    paused(service)
    window.capture_error = True
    service.resume()
    state = paused(service, 2)
    assert "capture denied" in state["pause_info"]["traceback"]
    assert len([e for e in window.backend.events if isinstance(e, tuple) and e[0] == "down"]) == 1
    window.capture_error = False
    service.resume()
    assert finished(service)["result"]["status"] == "success"


def test_takeover_between_steps_pauses_pending_observation_without_replaying_step(tmp_path, monkeypatch):
    from lalc import task_workflow

    service, window = service_for(tmp_path)
    task = service.manifest_manager.default.components["tasks.control"].module

    @task_workflow
    def execute(ctx, *, operation: str = "drag") -> str:
        ctx.call("steps.control", operation=operation, seconds=0.01)
        ctx.action("observe.capture_screen")
        return "finished"

    monkeypatch.setattr(task, "execute", execute)
    emit = service._emit

    def record(event, fields):
        emit(event, fields)
        if event == "component_returned" and fields.get("role") == "step":
            window.backend.monitor.record("鼠标", False)

    monkeypatch.setattr(service, "_emit", record)
    service.start("tasks.control", {})
    state = paused(service)
    assert state["pause_info"]["restart_step"] is False
    service.resume()
    state = finished(service)
    assert state["result"]["output"] == "finished"
    assert sum(event["event"] == "component_started" and event.get("role") == "step"
               for event in state["trace"]) == 1


def test_takeover_during_first_observation_prevents_first_control(tmp_path, monkeypatch):
    service, window = service_for(tmp_path)
    capture = window.capture
    first = True

    def observe(hwnd, width, height):
        nonlocal first
        if first:
            first = False
            window.backend.monitor.record("鼠标", False)
        return capture(hwnd, width, height)

    monkeypatch.setattr(window, "capture", observe)
    service.start("tasks.control", {})
    paused(service)
    assert window.backend.events == []
    service.resume()
    assert finished(service)["result"]["status"] == "success"


@pytest.mark.parametrize("problem", ["focus", "takeover"])
@pytest.mark.parametrize("plan", [False, True])
def test_workflow_observation_interruption_waits_for_resume_without_cancelling(tmp_path, monkeypatch, problem, plan):
    """观察动作内部发生暂停或接管时保留 Workflow 帧，仅重新观察，不重放 Step。"""

    from lalc import task_workflow
    service, window = service_for(tmp_path)
    window.backend.takeovers = 0
    entries = []
    @task_workflow
    def execute(ctx, *, operation: str = "drag") -> str:
        entries.append("entered")
        ctx.action("observe.capture_screen")
        return "finished"
    monkeypatch.setattr(service.manifest_manager.default.components["tasks.control"].module, "execute", execute)
    capture = window.capture
    first = True
    def observe(hwnd, width, height):
        nonlocal first
        if first:
            first = False
            if problem == "focus":
                window.foreground = False
            else:
                window.backend.monitor.record("鼠标", False)
                window.foreground = False
        return capture(hwnd, width, height)
    monkeypatch.setattr(window, "capture", observe)
    if plan:
        path = tmp_path / "plan.json"
        path.write_text(json.dumps({"items": [{"task": "tasks.control", "inputs": {}}]}), encoding="utf-8")
        service.start_plan(path)
    else:
        service.start("tasks.control", {})
    state = paused(service)
    assert state["pause_info"]["restart_step"] is False
    assert state["result"] is None and not service._gate.stopped
    service.resume()
    state = finished(service)
    if plan:
        assert state["result"]["status"] == "completed"
        assert state["result"]["items"][0]["result"] == "success"
    else:
        assert state["result"]["output"] == "finished"
    assert entries == ["entered"]
    attempts = [event["call_id"] for event in state["trace"] if event["event"] == "trusted_action_started"]
    assert len(attempts) == 2 and len(set(attempts)) == 2
    assert window.backend.events == []


def test_application_shutdown_waits_for_input_release(tmp_path, monkeypatch):
    """正常应用退出也必须等待运行线程的输入释放，不直接放弃后台线程。"""

    service, window = service_for(tmp_path)
    window.backend.takeovers = 0
    pressed, release = threading.Event(), threading.Event()
    def on_down():
        pressed.set()
        release.wait()
    window.backend.on_down = on_down
    service.start("tasks.control", {"operation": "key_press"})
    assert pressed.wait(2)
    waiting = threading.Thread(target=service.shutdown)
    waiting.start()
    release.set()
    waiting.join(2)
    assert not waiting.is_alive() and not service._thread.is_alive()
    assert service.state["result"]["failure_code"] == "user_cancelled"
    assert window.backend.events.count(("key", 0x1B, True)) == 1
    assert window.backend.closed
