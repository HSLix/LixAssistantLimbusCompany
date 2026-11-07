"""覆盖游戏重启、内置崩溃恢复、所有权、次数限制与用户可见日志；不启动真实进程。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen UV_CACHE_DIR=.generated/uv-cache uv run --frozen pytest -q tests/test_game_restart.py
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from lalc.application import ApplicationService
from lalc.control import InputSession
from lalc.focused import FocusedAutomationSession, WindowError, WindowsGameProcess
from lalc.game_restart import restart_game
from lalc.manifest import ManifestManager
from lalc.runtime import EnvironmentFailure, GameProcessExited, InputReleaseFailure, RunGate, UserInterruption
from lalc import game_restart, run_logs
from test_game_version import steam_install
from test_input_control import FakeProcess, FakeWindow
from test_recovery import _publish, _rule


class RestartWindow(FakeWindow):
    """按进程与窗口身份模拟关闭、启动和聚焦，不替换正式运行链。"""

    def __init__(self, executable):
        super().__init__()
        self.executable = executable
        self.processes = {7: FakeProcess(7, executable)}
        self.windows = {42: 7}
        self.normal_close = True
        self.creates_window = True
        self.launch_error = False
        self.launches = 0
        self.closes = 0
        self.on_start = lambda: None
        self.on_capture = lambda: None

    def open_game_process(self, pid):
        return self.processes[pid]

    def find_windows(self):
        return [hwnd for hwnd, pid in self.windows.items() if not self.processes[pid].dead]

    def window_info(self, hwnd):
        info = super().window_info(hwnd)
        info.update(valid=hwnd in self.find_windows(), process_id=self.windows.get(hwnd, 0))
        return info

    def focus(self, hwnd, *, checkpoint=None):
        if checkpoint:
            checkpoint()
        super().focus(hwnd)

    def request_close(self, hwnd, pid):
        assert self.windows[hwnd] == pid
        self.closes += 1
        if self.normal_close:
            self.processes[pid].dead = True

    def start_game(self, executable):
        assert executable == self.executable
        assert all(process.dead for process in self.processes.values())
        if self.launch_error:
            raise OSError("launch denied")
        self.launches += 1
        pid = 7 + self.launches
        self.processes[pid] = FakeProcess(pid, executable)
        if self.creates_window:
            self.windows[42 + self.launches] = pid
        self.on_start()
        return SimpleNamespace(pid=pid, poll=lambda: None)

    def capture(self, hwnd, width, height):
        self.on_capture()
        return super().capture(hwnd, width, height)


@pytest.fixture
def environment(tmp_path, monkeypatch):
    root = tmp_path / "Steam"
    game, _ = steam_install(root, tmp_path / "OtherLibrary")
    executable = game / "LimbusCompany.exe"
    executable.touch()
    data = tmp_path / "data"
    data.mkdir()
    (data / "game-version-settings.json").write_text(json.dumps({"steam_root": str(root)}))
    platform = RestartWindow(executable)
    events = []
    emit = lambda event, fields: events.append({"event": event, **fields})
    window = FocusedAutomationSession(platform, emit)
    window.connect()
    inputs = InputSession(window, platform.backend, RunGate(), emit)
    monkeypatch.setattr(InputSession, "QUIET_SECONDS", 0)
    monkeypatch.setattr(InputSession, "ACTIVITY_SECONDS", 0)
    monkeypatch.setattr(game_restart, "CLOSE_SECONDS", 0.01)
    monkeypatch.setattr(game_restart, "TERMINATE_SECONDS", 0.01)
    monkeypatch.setattr(game_restart, "START_SECONDS", 0.02)
    monkeypatch.setattr(game_restart, "POLL_SECONDS", 0.001)
    yield SimpleNamespace(root=data, platform=platform, inputs=inputs, events=events)
    inputs.close()


@pytest.mark.parametrize("graceful", [True, False])
def test_restart_closes_only_original_then_binds_and_discards_old_image(environment, graceful):
    env = environment
    env.platform.normal_close = graceful
    env.inputs.window.capture()
    old = env.inputs.process
    restart_game(env.root, env.inputs)
    assert old.dead and old.closed
    assert env.platform.closes == env.platform.launches == 1
    assert env.inputs.window.hwnd == 43 and env.inputs.window.process_id == 8
    assert env.inputs.process.pid == 8
    assert env.inputs.window.image is env.inputs.window.size is env.inputs.window.captured_at is None
    env.inputs.check()
    env.inputs.window.capture()
    assert env.inputs.window.observation == 2
    messages = [e["message"] for e in env.events if e["event"] == "component_log"]
    assert any("等待原游戏进程退出" in m for m in messages)
    assert any("启动游戏应用" in m for m in messages)
    assert any("正在置前并重新绑定" in m for m in messages)
    assert any("重启完成" in m for m in messages)
    assert any("强制终止原游戏" in m for m in messages) is (not graceful)


@pytest.mark.parametrize("problem", ["missing_settings", "missing_exe", "wrong_install", "multiple", "unknown_window"])
def test_invalid_launch_target_has_no_destructive_side_effect(environment, problem):
    env = environment
    if problem == "missing_settings":
        (env.root / "game-version-settings.json").unlink()
    elif problem == "missing_exe":
        env.platform.executable.unlink()
    elif problem == "wrong_install":
        env.inputs.process.path = Path("another/LimbusCompany.exe")
    elif problem == "multiple":
        env.platform.windows[99] = 7
    else:
        env.platform.windows = {99: 7}
    with pytest.raises(EnvironmentFailure, match="Steam|LimbusCompany|match|Ambiguous"):
        restart_game(env.root, env.inputs)
    assert env.platform.launches == env.platform.closes == 0
    assert not env.inputs.process.dead
    assert env.events[-1]["level"] == "error"


@pytest.mark.parametrize("problem", ["terminate_timeout", "no_window", "focus_timeout", "launch_error"])
def test_restart_failure_is_terminal_and_logged(environment, problem, monkeypatch):
    env = environment
    if problem == "terminate_timeout":
        env.platform.normal_close = False
        monkeypatch.setattr(env.inputs.process, "terminate", lambda: None)
    elif problem == "no_window":
        env.platform.creates_window = False
    elif problem == "focus_timeout":
        def focus(hwnd, *, checkpoint=None):
            while True:
                checkpoint()
        monkeypatch.setattr(env.platform, "focus", focus)
    else:
        env.platform.launch_error = True
    with pytest.raises(EnvironmentFailure) as failure:
        restart_game(env.root, env.inputs)
    assert failure.value.code == "game_restart_failed"
    assert env.platform.launches == (0 if problem in {"terminate_timeout", "launch_error"} else 1)
    assert env.events[-1]["level"] == "error"


@pytest.mark.parametrize("intent", ["pause", "takeover", "cancel"])
def test_interruption_after_launch_never_launches_twice(environment, intent):
    env = environment
    if intent == "pause":
        env.platform.on_start = env.inputs.gate.pause
    elif intent == "takeover":
        env.platform.on_start = lambda: env.inputs.monitor.record("鼠标", False)
    else:
        env.platform.on_start = env.inputs.gate.stop
    emit = env.inputs.emit

    def resume(event, fields):
        emit(event, fields)
        if event == "paused_by_user":
            env.inputs.gate.resume()
    env.inputs.emit = resume
    if intent == "cancel":
        with pytest.raises(UserInterruption):
            restart_game(env.root, env.inputs)
        assert "取消" in env.events[-1]["message"]
    else:
        restart_game(env.root, env.inputs)
        assert any(e["event"] == "paused_by_user" for e in env.events)
        env.inputs.check()
    assert env.platform.launches == 1


def test_process_exit_is_distinct_from_user_takeover_and_release_failure(environment):
    inputs = environment.inputs
    inputs.process.dead = True
    with pytest.raises(GameProcessExited):
        inputs.check()
    inputs.monitor.record("鼠标", False)
    with pytest.raises(UserInterruption):
        inputs.check()
    inputs.failed = True
    with pytest.raises(InputReleaseFailure):
        inputs.check()


@pytest.mark.parametrize("repeat_crash", [False, True])
def test_builtin_recovery_preserves_callers_limits_restarts_and_writes_visible_logs(environment, repeat_crash):
    env = environment
    manager = ManifestManager(env.root)
    source = '''"""观察游戏并返回。"""
from lalc import step
@step
def execute(ctx, *, value: int) -> str:
    ctx.action("observe.capture_screen")
    return f"step-old:{value}"
'''
    task = '''"""保留局部进度。"""
from lalc import task_workflow
@task_workflow
def execute(ctx, *, value: int) -> list[str]:
    ctx.log("已完成前序业务")
    before = "retained"
    result = ctx.call("steps.break", value=value)
    return [before, result]
'''
    identity = _publish(env.root, manager, step_source=source, task_source=task,
                        rules={"business": _rule('raise AssertionError("must not inspect a missing window")')})
    calls = []

    def crash():
        calls.append(1)
        if len(calls) == 1 or repeat_crash:
            env.platform.processes[max(env.platform.processes)].dead = True
    env.platform.on_capture = crash
    service = ApplicationService(env.root, manifest_manager=manager, window_platform=env.platform)
    service.start("tasks.run", {"value": 9}, manifest_id=identity)
    state = service.wait_for(lambda state: state["phase"] == "finished")
    assert state["phase"] == "finished", state
    result = state["result"]
    assert result["status"] == ("failure" if repeat_crash else "success")
    if repeat_crash:
        assert result["failure_code"] == "game_restart_limit"
    else:
        assert result["output"] == ["retained", "step-old:9"]
    assert env.platform.launches == 1
    trace = state["trace"]
    assert sum(e["event"] == "component_log" and e["message"] == "已完成前序业务" for e in trace) == 1
    assert not any(e["event"] == "recovery_rule_started" and e["logical_name"] == "business" for e in trace)
    assert any(e["event"] == "recovery_rule_returned" and e["phase"] == "recover"
               and e["logical_name"] == "builtin.game_crash" for e in trace)
    action = next(e for e in trace if e["event"] == "trusted_action_returned"
                  and e["logical_name"] == "control.restart_game")
    assert action["classification"] == "control"
    page = run_logs.read_page(env.root, state["run_id"], run_logs.snapshot(env.root, state["run_id"]),
                              keyword="游戏", limit=100)
    assert any("启动游戏应用" in row["text"] for row in page["rows"])
    assert any("重启完成" in row["text"] for row in page["rows"])
    assert all(process.closed for process in env.platform.processes.values())


def test_restart_action_is_available_to_step_and_forbidden_in_task(environment):
    env = environment
    manager = ManifestManager(env.root)
    source = '''"""显式重启游戏。"""
from lalc import step
@step
def execute(ctx, *, value: int) -> str:
    ctx.action("control.restart_game")
    return "restarted"
'''
    identity = _publish(env.root, manager, step_source=source)
    service = ApplicationService(env.root, manifest_manager=manager, window_platform=env.platform)
    service.start("steps.break", {"value": 1}, manifest_id=identity)
    assert service.wait_for(lambda state: state["phase"] == "finished")["result"]["status"] == "success"
    assert env.platform.launches == 1

    bad_task = '''"""Task 不得直接控制。"""
from lalc import task_workflow
@task_workflow
def execute(ctx, *, value: int) -> list[str]:
    ctx.action("control.restart_game")
    return []
'''
    with pytest.raises(AssertionError):
        _publish(env.root, manager, step_source=source, task_source=bad_task)
    assert env.platform.launches == 1


@pytest.mark.parametrize("failure", ["second_crash", "launch_error", "detection_error"])
def test_unrecoverable_game_exit_ends_entire_plan(environment, failure):
    env = environment
    source = '''"""触发进程退出。"""
from lalc import step
@step
def execute(ctx, *, value: int) -> str:
    ctx.action("observe.capture_screen")
    return "observed"
'''
    manager = ManifestManager(env.root)
    identity = _publish(env.root, manager, step_source=source)
    env.platform.on_capture = lambda: setattr(env.platform.processes[max(env.platform.processes)], "dead", True)
    env.platform.launch_error = failure == "launch_error"
    if failure == "detection_error":
        checks = []
        def exited():
            checks.append(1)
            if len(checks) == 1:
                return True
            raise OSError("cannot inspect original process")
        env.platform.processes[7].exited = exited
    service = ApplicationService(env.root, manifest_manager=manager, window_platform=env.platform)
    service.start_plan(manifest_id=identity)
    result = service.wait_for(lambda state: state["phase"] == "finished")["result"]
    assert result["status"] == "interrupted"
    assert result["failure_code"] == ("game_restart_limit" if failure == "second_crash" else "game_restart_failed")
    assert len(result["items"]) == 1
    assert result["items"][0]["status"] == "failure"
    assert env.platform.launches == (1 if failure == "second_crash" else 0)


def test_explicit_restart_does_not_consume_automatic_budget(environment):
    env = environment
    source = '''"""分别测试显式重启与观察。"""
from lalc import step
@step
def execute(ctx, *, value: int) -> str:
    if value == 0:
        ctx.action("control.restart_game")
    else:
        ctx.action("observe.capture_screen")
    return "done"
'''
    task = '''"""先显式重启，再观察运行中的崩溃。"""
from lalc import task_workflow
@task_workflow
def execute(ctx, *, value: int) -> list[str]:
    first = ctx.call("steps.break", value=0)
    second = ctx.call("steps.break", value=1)
    return [first, second]
'''
    manager = ManifestManager(env.root)
    identity = _publish(env.root, manager, step_source=source, task_source=task)
    def crash_once():
        env.platform.on_capture = lambda: None
        env.platform.processes[max(env.platform.processes)].dead = True
    env.platform.on_capture = crash_once
    service = ApplicationService(env.root, manifest_manager=manager, window_platform=env.platform)
    service.start("tasks.run", {"value": 1}, manifest_id=identity)
    state = service.wait_for(lambda state: state["phase"] == "finished")
    assert state["result"]["output"] == ["done", "done"]
    assert env.platform.launches == 2
    assert sum(e["event"] == "recovery_rule_returned" and e["phase"] == "recover" for e in state["trace"]) == 1
    assert sum(e["event"] == "step_reinvocation_returned" for e in state["trace"]) == 1


def test_user_takeover_requires_resume_before_crash_recovery(environment):
    env = environment
    source = '''"""接管时发生进程退出。"""
from lalc import step
@step
def execute(ctx, *, value: int) -> str:
    ctx.action("observe.capture_screen")
    return "done"
'''
    manager = ManifestManager(env.root)
    identity = _publish(env.root, manager, step_source=source)
    def takeover_and_crash():
        env.platform.on_capture = lambda: None
        env.platform.backend.monitor.record("鼠标", False)
        env.platform.processes[7].dead = True
    env.platform.on_capture = takeover_and_crash
    service = ApplicationService(env.root, manifest_manager=manager, window_platform=env.platform)
    service.start("steps.break", {"value": 1}, manifest_id=identity)
    state = service.wait_for(lambda state: state["pause_info"] is not None or state["phase"] == "finished")
    assert state["paused"] and env.platform.launches == 0
    service.resume()
    result = service.wait_for(lambda state: state["phase"] == "finished")["result"]
    assert result["status"] == "success"
    assert env.platform.launches == 1


def test_win32_process_uses_retained_handle_and_waits_for_async_termination(tmp_path):
    calls = []
    state = {"wait": 258}
    executable = tmp_path / "LimbusCompany.exe"
    def query(handle, flags, buffer, length):
        assert handle == 101
        buffer.value = str(executable)
        return True
    kernel = SimpleNamespace(
        OpenProcess=lambda rights, inherit, pid: calls.append(("open", rights, pid)) or 101,
        QueryFullProcessImageNameW=query,
        WaitForSingleObject=lambda handle, timeout: calls.append(("wait", handle, timeout)) or state["wait"],
        TerminateProcess=lambda handle, code: calls.append(("terminate", handle, code)) or True,
        CloseHandle=lambda handle: calls.append(("close", handle)),
    )
    process = WindowsGameProcess(SimpleNamespace(kernel32=kernel, EXECUTABLE="limbuscompany.exe"), 7)
    assert process.path == executable
    process.terminate()
    assert not process.exited()
    state["wait"] = 0
    assert process.exited()
    process.terminate()
    process.close()
    process.close()
    assert calls[0] == ("open", 0x101001, 7)
    assert calls.count(("terminate", 101, 1)) == calls.count(("close", 101)) == 1
    with pytest.raises(WindowError, match="not Limbus"):
        WindowsGameProcess(SimpleNamespace(kernel32=kernel, EXECUTABLE="another.exe"), 7)
    assert calls.count(("close", 101)) == 2


def test_user_activity_wait_does_not_consume_restart_timeout(environment, monkeypatch):
    from test_input_activity import Clock
    from lalc import control
    env = environment
    clock = Clock()
    monkeypatch.setattr(control.time, "monotonic", lambda: clock.now)
    monkeypatch.setattr(control.time, "sleep", clock.sleep)
    env.inputs.POLL_SECONDS = 1
    env.inputs.ACTIVITY_SECONDS = 10
    def start():
        env.platform.foreground = False
        env.inputs.monitor.record("鼠标", False, takeover=False, other_application=True)
    env.platform.on_start = start
    restart_game(env.root, env.inputs)
    assert env.platform.launches == 1
    assert clock.now == 110
    assert env.inputs.focus_wait_seconds == 10
    assert any(e.get("outcome") == "idle" for e in env.events)


def test_pause_during_focus_activity_wait_resumes_without_relaunch(environment, monkeypatch):
    import threading
    env = environment
    env.inputs.ACTIVITY_SECONDS = 999
    env.inputs.POLL_SECONDS = 0.001
    waiting = threading.Event()
    original_emit = env.inputs.emit
    def emit(event, fields):
        original_emit(event, fields)
        if event == "component_log" and fields.get("message", "").startswith("等待其他应用"):
            env.inputs.monitor.record("键盘", False, takeover=False, pause=True)
        if event == "paused_by_user":
            waiting.set()
    monkeypatch.setattr(env.inputs, "emit", emit)
    env.platform.on_start = lambda: setattr(env.platform, "foreground", False)
    errors = []
    def run():
        try:
            restart_game(env.root, env.inputs)
        except BaseException as error:
            errors.append(error)
    worker = threading.Thread(target=run)
    worker.start()
    try:
        assert waiting.wait(2)
        env.inputs.gate.resume()
        worker.join(2)
        assert not worker.is_alive()
        assert not errors
        assert env.platform.launches == 1
        assert any(e.get("outcome") == "manual_resume" for e in env.events)
    finally:
        env.inputs.gate.stop()
        worker.join(2)
