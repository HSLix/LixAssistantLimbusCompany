"""覆盖统一调用异常、移除旧 Task 回调、两层错误提示与后台统一收尾。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen UV_CACHE_DIR=.generated/uv-cache uv run --frozen pytest -q tests/test_error_handling.py
"""

from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from lalc.application import ApplicationService, StartError
from lalc.manifest import ManifestManager
from lalc.errors import FATAL_MESSAGE, configure_logging, result_diagnostics
from test_workflow import _publish, _finished, STEP_SOURCE, CONTROL_SOURCE, TASK_SOURCE


@pytest.mark.parametrize("callback", ["condition", "verify"])
def test_task_callbacks_are_rejected_with_step_migration_message(tmp_path: Path, callback: str) -> None:
    from test_manifest import _write_candidate, SOURCES
    sources = dict(SOURCES)
    sources["task.py"] += f'\ndef {callback}(ctx) -> bool:\n    return True\n'
    manager = ManifestManager(tmp_path / "formal")
    candidate = _write_candidate(tmp_path / "candidate", sources=sources)
    result = manager.publish(candidate)
    assert not result.ok
    assert any(error.code == f"{callback}_forbidden" and "Step" in error.message
               for error in result.errors)


@pytest.mark.parametrize("phase", ["condition", "execute", "action"])
@pytest.mark.parametrize("error_name", ["OSError", "ExecutionFailure"])
def test_all_step_calls_record_failures_then_share_one_recovery(
    tmp_path: Path, phase: str, error_name: str,
) -> None:
    """原始错误和已归一错误都应记录，只有 Step 包装层重新调用一次。"""

    body = f'''calls = 0

def check_once():
    global calls
    calls += 1
    if calls == 1:
        raise {error_name}("original failure") from ValueError("original cause")
'''
    step = STEP_SOURCE.replace('from lalc import step', 'from lalc import step, ExecutionFailure')
    action = CONTROL_SOURCE
    if phase == "condition":
        step += '\n' + body + '\ndef condition(ctx, *, team: str) -> bool:\n    check_once()\n    return True\n'
    elif phase == "execute":
        step += '\n' + body
        step = step.replace('    return ctx.action(', '    check_once()\n    return ctx.action(')
    else:
        action = action.replace('\ndef execute', '\nfrom lalc import ExecutionFailure\n\ndef execute') + '\n' + body
        action = action.replace('    return {"team": team}', '    check_once()\n    return {"team": team}')
    manager = _publish(tmp_path, step_source=step, control_source=action)
    service = ApplicationService(tmp_path, manifest_manager=manager)
    state = _finished(service, service.start("tasks.rotate_teams", {"teams": ["alpha"], "runs": 1}))
    assert state["result"]["output"] == ["alpha"]
    failed_event = {"condition": "condition_failed", "execute": "component_failed", "action": "trusted_action_failed"}[phase]
    failed = [e for e in state["trace"] if e["event"] == failed_event]
    assert any(f"{error_name}: original failure" in e["traceback"] and "ValueError: original cause" in e["traceback"]
               for e in failed)
    assert sum(e["event"] == "step_reinvocation_started" for e in state["trace"]) == 1
    assert sum(e["event"] == "component_started" and e["role"] == "task_workflow"
               for e in state["trace"]) == 1


def test_cleanup_failure_finishes_run_preserves_task_error_and_blocks_restart(tmp_path: Path, caplog) -> None:
    manager = _publish(tmp_path, task_source=TASK_SOURCE.replace('    used = []', '    raise OSError("task failed")\n    used = []'))
    service = ApplicationService(tmp_path, manifest_manager=manager)
    def close():
        raise OSError("cleanup failed") from ValueError("cleanup cause")
    execute = manager.default.components["tasks.rotate_teams"].module.execute
    def with_session(ctx, *, teams: list[str], runs: int = 2) -> list[str]:
        service._input_session = SimpleNamespace(close=close)
        return execute(ctx, teams=teams, runs=runs)
    with_session.__lalc_role__ = "task_workflow"
    manager.default.components["tasks.rotate_teams"].module.execute = with_session
    with caplog.at_level(logging.ERROR):
        state = _finished(service, service.start("tasks.rotate_teams", {"teams": ["alpha"]}))
    assert state["result"]["fatal"] is True
    details = result_diagnostics(state["result"])
    assert "OSError: task failed" in details
    assert "OSError: cleanup failed" in details
    assert "ValueError: cleanup cause" in details
    assert "Input session cleanup failed" in caplog.text
    with pytest.raises(StartError, match="cannot continue"):
        service.start("tasks.rotate_teams", {"teams": ["alpha"]})


@pytest.mark.parametrize("error_type", [RuntimeError, SystemExit])
def test_unhandled_worker_error_reaches_fatal_result(tmp_path: Path, monkeypatch, error_type) -> None:
    manager = _publish(tmp_path)
    service = ApplicationService(tmp_path, manifest_manager=manager)
    def fail(*args):
        raise error_type("unhandled worker bug") from OSError("worker cause")
    monkeypatch.setattr(service, "_run", fail)
    state = _finished(service, service.start("tasks.rotate_teams", {"teams": ["alpha"]}))
    assert state["result"]["fatal"]
    assert "OSError: worker cause" in result_diagnostics(state["result"])


def test_gui_interaction_logs_error_and_dialog_copies_original_traceback(tmp_path: Path, caplog) -> None:
    from PySide6.QtWidgets import QApplication, QPushButton
    from lalc.gui import ErrorDialog, MainWindow
    app = QApplication.instance() or QApplication([])
    service = ApplicationService(tmp_path)
    window = MainWindow(service)
    def fail():
        raise OSError("interaction failed") from ValueError("interaction cause")
    with caplog.at_level(logging.ERROR):
        window._interact(fail)
    dialog = window.findChild(ErrorDialog)
    assert dialog is not None
    copy = next(button for button in dialog.findChildren(QPushButton) if "Copy error" in button.text())
    copy.click()
    assert "OSError: interaction failed" in app.clipboard().text()
    assert "ValueError: interaction cause" in app.clipboard().text()
    assert "interaction cause" in caplog.text
    assert dialog.details.isReadOnly()
    window.close()
    app.processEvents()


def test_gui_fatal_error_shows_bilingual_copyable_message_and_exits(tmp_path: Path, monkeypatch) -> None:
    from PySide6.QtWidgets import QApplication
    from lalc.gui import ErrorDialog, MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow(ApplicationService(tmp_path))
    notices, exits = [], []
    monkeypatch.setattr(ErrorDialog, "exec", lambda dialog: notices.append((dialog.windowTitle(), dialog.details.toPlainText())))
    monkeypatch.setattr(app, "exit", exits.append)
    window.fatal_error("OSError: original fatal error")
    window.fatal_error("duplicate")
    assert len(notices) == 1 and "Fatal error" in notices[0][0]
    assert notices[0][1] == "OSError: original fatal error"
    assert "无法继续运行" in FATAL_MESSAGE and "cannot continue" in FATAL_MESSAGE
    assert exits == [1] and not window.isEnabled()
    window.close()


@pytest.mark.parametrize("dialog_failure", [None, "exec", "import"])
def test_fatal_report_always_exits_gui_event_loop(monkeypatch, capsys, dialog_failure) -> None:
    """错误框正常关闭、显示失败或导入失败时，真实事件循环均以失败码退出。"""

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QWidget
    from lalc.gui import ErrorDialog
    from lalc.lifecycle import ApplicationLifecycle

    app = QApplication.instance() or QApplication([])
    window = QWidget()
    window.show()
    lifecycle = ApplicationLifecycle()
    if dialog_failure == "import":
        monkeypatch.setitem(sys.modules, "lalc.gui", None)
    else:
        def show(dialog):
            if dialog_failure == "exec":
                raise RuntimeError("fatal dialog unavailable")
            return 0
        monkeypatch.setattr(ErrorDialog, "exec", show)

    timed_out = []
    watchdog = QTimer()
    watchdog.setSingleShot(True)
    def stop_hung_test():
        timed_out.append(True)
        app.quit()
    watchdog.timeout.connect(stop_hung_test)
    watchdog.start(1000)
    QTimer.singleShot(0, lambda: lifecycle.present_fatal("OSError: original fatal error"))
    try:
        exit_code = app.exec()
    finally:
        watchdog.stop()
        window.close()
    assert not timed_out
    assert exit_code == 1
    assert lifecycle.failed
    if dialog_failure:
        report = capsys.readouterr().err
        assert FATAL_MESSAGE in report
        assert "OSError: original fatal error" in report


def test_gui_outer_hooks_forward_main_and_thread_errors_then_restore(tmp_path: Path, monkeypatch) -> None:
    # 本测试只验证生命周期错误出口；真实跨进程通道由 test_user_gui 覆盖。
    monkeypatch.setattr("lalc.gui_instance.GuiInstance.listen", lambda *_: None)
    from PySide6.QtWidgets import QApplication
    import lalc.gui as gui
    app = QApplication.instance() or QApplication([])
    previous = (sys.excepthook, threading.excepthook)
    received = []
    monkeypatch.setattr(gui, "default_data_root", lambda: tmp_path)
    monkeypatch.setattr("lalc.application.default_data_root", lambda: tmp_path)
    def receive(self, details):
        self.lifecycle.pending_details = ""
        received.append(details)
    monkeypatch.setattr(gui.MainWindow, "fatal_error", receive)
    def run():
        for hook in (sys.excepthook, lambda kind, error, tb: threading.excepthook(
                SimpleNamespace(exc_type=kind, exc_value=error, exc_traceback=tb))):
            try:
                raise RuntimeError("outer failure") from OSError("outer cause")
            except RuntimeError as error:
                hook(type(error), error, error.__traceback__)
        app.processEvents()
        for widget in app.topLevelWidgets():
            widget.close()
        return 1
    monkeypatch.setattr(app, "exec", run)
    assert gui.run_gui() == 1
    assert len(received) == 2
    assert all("OSError: outer cause" in detail and "RuntimeError: outer failure" in detail for detail in received)
    assert (sys.excepthook, threading.excepthook) == previous
    assert "outer failure" in (tmp_path / "logs" / "lalc.log").read_text(encoding="utf-8")


def test_business_verification_in_step_recovers_without_replaying_task(tmp_path: Path) -> None:
    """结果核验是 Step 的普通业务代码；失败走同一恢复路径。"""

    step = STEP_SOURCE.replace('from lalc import step', 'from lalc import ExecutionFailure, step').replace(
        '    return ctx.action("fake_control", team=team)["team"]',
        '    result = ctx.action("fake_control", team=team)["team"]\n'
        '    if result != team:\n        raise ExecutionFailure("unexpected_result", "team mismatch")\n'
        '    return result',
    )
    action = CONTROL_SOURCE + '\ncalls = 0\n'
    action = action.replace('    return {"team": team}',
                            '    global calls\n    calls += 1\n    return {"team": "wrong" if calls == 1 else team}')
    manager = _publish(tmp_path, step_source=step, control_source=action)
    service = ApplicationService(tmp_path, manifest_manager=manager)
    state = _finished(service, service.start("tasks.rotate_teams", {"teams": ["alpha"], "runs": 1}))
    assert state["result"]["output"] == ["alpha"]
    assert manager.actions["fake_control"].execute.__globals__["calls"] == 2
    assert sum(event["event"] == "component_started" and event["role"] == "task_workflow"
               for event in state["trace"]) == 1
    assert any(event["event"] == "step_interrupted" and "team mismatch" in event["failure_message"]
               for event in state["trace"])


@pytest.mark.parametrize("plan", [False, True])
def test_gui_user_cancellation_is_not_an_error_dialog(tmp_path: Path, monkeypatch, plan: bool) -> None:
    from PySide6.QtWidgets import QApplication
    from lalc.gui import MainWindow, ErrorDialog
    app = QApplication.instance() or QApplication([])
    service = ApplicationService(tmp_path)
    window = MainWindow(service)
    dialogs = []
    monkeypatch.setattr(ErrorDialog, "open", lambda dialog: dialogs.append(dialog))
    state = service.state
    cancelled = {"status": "failure", "failure_code": "user_cancelled", "failure_message": "cancelled"}
    if plan:
        cancelled = {"status": "interrupted", "reason": "user_cancelled", "items": [
            {"result": "failure", "failure_code": "user_cancelled", "failure_message": "cancelled"}]}
    state.update(phase="finished", run_id=1, result=cancelled)
    window.render_state(state)
    assert not dialogs
    window.close()
    app.processEvents()


def test_unhandled_completion_error_still_publishes_terminal_fatal_result(tmp_path: Path, monkeypatch) -> None:
    manager = _publish(tmp_path)
    service = ApplicationService(tmp_path, manifest_manager=manager)
    def fail(result):
        raise OSError("completion failed")
    monkeypatch.setattr(service, "_complete", fail)
    state = _finished(service, service.start("tasks.rotate_teams", {"teams": ["alpha"], "runs": 1}))
    assert state["result"]["fatal"]
    assert state["result"]["previous_result"]["output"] == ["alpha"]
    assert "OSError: completion failed" in result_diagnostics(state["result"])


def test_gui_completed_task_failure_is_reported_once(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication
    from lalc.gui import GuiCoordinator
    from lalc.lifecycle import ApplicationLifecycle
    app = QApplication.instance() or QApplication([])
    service = ApplicationService(tmp_path)
    owner = GuiCoordinator(service, ApplicationLifecycle())
    window = owner.open_window()
    notices = []
    monkeypatch.setattr(window.notifications, "notify", lambda *args: notices.append(args))
    window.owns_run = True
    state = {**service.state, "phase": "finished", "run_id": 1, "result": {
        "status": "interrupted", "reason": "execution_failed",
        "traceback": "OSError: original execution error"}}
    window.render_state(state)
    window.render_state(state)
    assert len(notices) == 1 and "OSError: original execution error" in notices[0][1]
    window.close()
    app.processEvents()


def test_error_payload_has_only_failure_message_and_full_traceback(tmp_path: Path) -> None:
    import json
    step = STEP_SOURCE.replace('    return ctx.action("fake_control", team=team)["team"]',
                               '    raise OSError("native fault") from ValueError("root cause")')
    manager = _publish(tmp_path, step_source=step)
    service = ApplicationService(tmp_path, manifest_manager=manager)
    state = _finished(service, service.start("tasks.rotate_teams", {"teams": ["alpha"]}))
    serialized = json.dumps(state, ensure_ascii=False)
    assert '"exception_type"' not in serialized
    assert '"exception_message"' not in serialized
    assert state["result"]["failure_message"] == "native fault"
    assert "ValueError: root cause" in state["result"]["traceback"]
    assert "OSError: native fault" in state["result"]["traceback"]
    persisted = (tmp_path / "traces" / "1.jsonl").read_text(encoding="utf-8")
    assert '"exception_type"' not in persisted and '"exception_message"' not in persisted


@pytest.mark.parametrize("failure_at", ["cleanup", "worker", "completion"])
def test_plan_fatal_result_keeps_plan_status_items_and_original_result(tmp_path: Path, monkeypatch, failure_at) -> None:
    import json
    manager = _publish(tmp_path)
    service = ApplicationService(tmp_path, manifest_manager=manager)
    if failure_at == "worker":
        def fail(*args):
            raise RuntimeError("plan worker failed")
        monkeypatch.setattr(service, "_run", fail)
    elif failure_at == "completion":
        def fail(result):
            raise RuntimeError("plan completion failed")
        monkeypatch.setattr(service, "_complete", fail)
    else:
        def close():
            raise OSError("plan cleanup failed") from ValueError("cleanup cause")
        def execute(ctx, *, teams: list[str], runs: int = 2) -> list[str]:
            service._input_session = SimpleNamespace(close=close)
            return teams
        execute.__lalc_role__ = "task_workflow"
        manager.default.components["tasks.rotate_teams"].module.execute = execute
    state = _finished(service, service.start_plan())
    result = state["result"]
    assert result["fatal"] and result["status"] == "interrupted"
    assert result["reason"] == "fatal_error" and "failure_code" not in result
    assert isinstance(result["items"], list)
    if failure_at != "worker":
        assert result["previous_result"]["status"] == "completed"
        assert result["items"] == result["previous_result"]["items"]
        assert len(result["items"]) == 1 and result["items"][0]["result"] == "success"
    else:
        assert result["previous_result"] == {} and result["items"] == []


def test_main_gui_bootstrap_failure_uses_lifecycle_report(tmp_path: Path, monkeypatch) -> None:
    import lalc.__main__ as cli
    import lalc.gui as gui
    from lalc.lifecycle import ApplicationLifecycle
    monkeypatch.setattr("lalc.application.default_data_root", lambda: tmp_path)
    original = sys.excepthook, threading.excepthook
    reports = []
    def fail(lifecycle):
        raise RuntimeError("GUI startup failed") from OSError("bootstrap cause")
    monkeypatch.setattr(gui, "run_gui", fail)
    monkeypatch.setattr(ApplicationLifecycle, "present_fatal", lambda self, details: reports.append(details))
    assert cli.main([]) == 1
    assert "OSError: bootstrap cause" in reports[0] and "RuntimeError: GUI startup failed" in reports[0]
    assert (sys.excepthook, threading.excepthook) == original
    assert "bootstrap cause" in (tmp_path / "logs" / "lalc.log").read_text(encoding="utf-8")


def test_gui_import_failure_falls_back_to_bilingual_report(tmp_path: Path, monkeypatch, capsys) -> None:
    import lalc.__main__ as cli
    monkeypatch.setattr("lalc.application.default_data_root", lambda: tmp_path)
    monkeypatch.setitem(sys.modules, "lalc.gui", None)
    assert cli.main([]) == 1
    report = capsys.readouterr().err
    assert "无法继续运行" in report and "cannot continue" in report
    assert "ModuleNotFoundError" in report and "lalc.gui" in report


def test_lifecycle_normal_gui_exit_restores_hooks(tmp_path: Path) -> None:
    from lalc.lifecycle import run_application
    original = sys.excepthook, threading.excepthook
    assert run_application(lambda owner: 0, data_root=tmp_path) == 0
    assert (sys.excepthook, threading.excepthook) == original


def test_unhandled_background_thread_reports_fatal_on_gui_thread(tmp_path: Path, monkeypatch) -> None:
    # 本测试只验证生命周期错误出口；真实跨进程通道由 test_user_gui 覆盖。
    monkeypatch.setattr("lalc.gui_instance.GuiInstance.listen", lambda *_: None)
    from PySide6.QtWidgets import QApplication
    import lalc.gui as gui
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr("lalc.application.default_data_root", lambda: tmp_path)
    monkeypatch.setattr(gui, "default_data_root", lambda: tmp_path)
    main_thread = threading.get_ident()
    reports = []
    monkeypatch.setattr(gui.ErrorDialog, "exec", lambda dialog: reports.append(
        (threading.get_ident(), dialog.details.toPlainText())))
    def run():
        def fail():
            raise RuntimeError("background failure") from OSError("thread cause")
        worker = threading.Thread(target=fail)
        worker.start()
        worker.join()
        app.processEvents()
        for widget in app.topLevelWidgets():
            widget.close()
        return 0
    monkeypatch.setattr(app, "exec", run)
    assert gui.run_gui() == 1
    assert len(reports) == 1 and reports[0][0] == main_thread
    assert "RuntimeError: background failure" in reports[0][1]
    assert "OSError: thread cause" in reports[0][1]


@pytest.mark.parametrize("startup_error", [False, True])
def test_lifecycle_always_performs_shutdown_before_exit(tmp_path: Path, monkeypatch, startup_error) -> None:
    from lalc.lifecycle import ApplicationLifecycle, run_application
    events = []
    monkeypatch.setattr(ApplicationLifecycle, "present_fatal", lambda self, details: events.append("fatal"))
    def start(owner):
        owner.shutdown = lambda: events.append("shutdown")
        if startup_error:
            raise RuntimeError("startup failed")
        return 0
    assert run_application(start, data_root=tmp_path) == (1 if startup_error else 0)
    assert "shutdown" in events


def test_shutdown_error_changes_normal_exit_to_fatal(tmp_path: Path, monkeypatch) -> None:
    from lalc.lifecycle import ApplicationLifecycle, run_application
    reports = []
    def present(self, details):
        self.pending_details = ""
        reports.append(details)
    monkeypatch.setattr(ApplicationLifecycle, "present_fatal", present)
    def start(owner):
        def shutdown():
            raise OSError("application shutdown failed")
        owner.shutdown = shutdown
        return 0
    assert run_application(start, data_root=tmp_path) == 1
    assert "OSError: application shutdown failed" in reports[0]
