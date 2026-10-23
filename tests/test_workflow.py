"""覆盖正式异步入口、Task/Subworkflow/Step、Trace、失败闭环与启动错误详情。

在项目根目录运行：
UV_CACHE_DIR=.generated/uv-cache uv run --frozen pytest -q tests/test_workflow.py
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
import pytest

from lalc.application import ApplicationService, StartError
from lalc.manifest import ManifestManager


TASK_SOURCE = '''"""Deterministic test Task Workflow."""
from lalc import task_workflow

@task_workflow
def execute(ctx, *, teams: list[str], runs: int = 2) -> list[str]:
    used = []
    while ctx.action("fake_observe", completed=len(used), target=runs):
        used.append(ctx.call("flows.run_once", teams=teams, index=len(used)))
    return used

'''

SUB_SOURCE = '''"""Deterministic test Subworkflow."""
from lalc import sub_workflow

@sub_workflow
def execute(ctx, *, teams: list[str], index: int) -> str:
    team = teams[index % len(teams)]
    teams.append("callee-only")
    return ctx.call("steps.run_team", team=team)
'''

STEP_SOURCE = '''"""Deterministic test Step."""
from lalc import step

@step
def execute(ctx, *, team: str) -> str:
    return ctx.action("fake_control", team=team)["team"]
'''

OBSERVE_SOURCE = '''"""Deterministic fake observation."""
def execute(ctx, *, completed: int, target: int) -> bool:
    return completed < target
'''

CONTROL_SOURCE = '''"""Deterministic fake control."""
def execute(ctx, *, team: str) -> dict[str, str]:
    return {"team": team}
'''

def _publish(
    root: Path,
    *,
    manager: ManifestManager | None = None,
    task_source: str = TASK_SOURCE,
    sub_source: str = SUB_SOURCE,
    step_source: str = STEP_SOURCE,
    control_source: str = CONTROL_SOURCE,
) -> ManifestManager:
    candidate = root / f"candidate-{len(list(root.glob('candidate-*')))}"
    candidate.mkdir(parents=True)
    sources = {
        "task.py": task_source,
        "sub.py": sub_source,
        "step.py": step_source,
    }
    for name, source in sources.items():
        (candidate / name).write_text(source, encoding="utf-8")
    manifest = {
        "schema_version": 2,
        "components": {
            "tasks.rotate_teams": {"source_path": "task.py"},
            "flows.run_once": {"source_path": "sub.py"},
            "steps.run_team": {"source_path": "step.py"},
        },
        "recovery_rules": {},
    }
    path = candidate / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    if manager is None:
        manager = ManifestManager(root)
        from runtime_support import register_sources
        register_sources(manager, {"fake_observe": (OBSERVE_SOURCE, "observe"), "fake_control": (control_source, "control")})
    result = manager.publish(path)
    assert result.ok, result.errors
    assert manager.set_default(result.loaded.manifest_id).ok
    return manager


def _finished(service: ApplicationService, run_id: int) -> dict[str, Any]:
    return service.wait_for(
        lambda state: state["run_id"] == run_id and state["phase"] == "finished"
    )


def test_complete_task_uses_real_manifest_executor_and_persists_trace(tmp_path: Path) -> None:
    manager = _publish(tmp_path)
    service = ApplicationService(tmp_path, manifest_manager=manager)
    teams = ["one", "two"]

    run_id = service.start("tasks.rotate_teams", {"teams": teams, "runs": 3})
    teams.append("caller-only")
    state = _finished(service, run_id)

    assert run_id == 1
    assert state["result"] == {
        "status": "success",
        "logical_name": "tasks.rotate_teams",
        "component_id": manager.default.components["tasks.rotate_teams"].component_id,
        "role": "task_workflow",
        "output": ["one", "two", "one"],
    }
    assert teams == ["one", "two", "caller-only"]
    assert [event["sequence"] for event in state["trace"]] == list(
        range(1, len(state["trace"]) + 1)
    )
    assert {event["run_id"] for event in state["trace"]} == {run_id}
    assert all(event["recorded_at"].endswith("+00:00") for event in state["trace"])
    started = [event for event in state["trace"] if event["event"] == "component_started"]
    assert [event["logical_name"] for event in started[:3]] == [
        "tasks.rotate_teams",
        "flows.run_once",
        "steps.run_team",
    ]
    sub_call = next(event for event in started if event["logical_name"] == "flows.run_once")
    assert sub_call["inputs"]["teams"] == ["one", "two"]
    step_call = next(event for event in started if event["logical_name"] == "steps.run_team")
    assert step_call["parent_call_id"] == sub_call["call_id"]
    action = next(event for event in state["trace"] if event["event"] == "trusted_action_started")
    assert action["classification"] in {"observe", "control"}
    assert "component_id" not in action
    assert not any(event["event"].startswith("verification_") for event in state["trace"])
    persisted = [
        json.loads(line)
        for line in (tmp_path / "traces" / f"{run_id}.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert persisted == state["trace"]

    second = ApplicationService(tmp_path, manifest_manager=manager)
    assert second.start("steps.run_team", {"team": "three"}) == 2
    assert _finished(second, 2)["result"]["output"] == "three"


def test_direct_subworkflow_and_step_are_ordinary_runs(tmp_path: Path) -> None:
    manager = _publish(tmp_path)
    service = ApplicationService(tmp_path, manifest_manager=manager)

    sub_run = service.start("flows.run_once", {"teams": ["a", "b"], "index": 1})
    sub_result = _finished(service, sub_run)["result"]
    step_run = service.start("steps.run_team", {"team": "c"})
    step_result = _finished(service, step_run)["result"]

    assert sub_result["role"] == "sub_workflow"
    assert sub_result["output"] == "b"
    assert step_result["role"] == "step"
    assert step_result["output"] == "c"


def test_start_rejection_has_no_run_or_state_change(tmp_path: Path) -> None:
    empty_service = ApplicationService(tmp_path / "empty")
    with pytest.raises(StartError) as missing_manifest:
        empty_service.start("tasks.rotate_teams", {})
    assert missing_manifest.value.code == "default_manifest_unavailable"

    manager = _publish(tmp_path / "formal")
    service = ApplicationService(tmp_path / "formal", manifest_manager=manager)
    before = service.state
    with pytest.raises(StartError) as missing_entry:
        service.start("tasks.missing", {})
    assert missing_entry.value.code == "entry_not_found"
    with pytest.raises(StartError) as invalid_inputs:
        service.start("tasks.rotate_teams", {"teams": ["one"], "runs": True})
    assert invalid_inputs.value.code == "inputs_invalid"
    assert service.state == before
    assert not (tmp_path / "formal" / "run-sequence.json").exists()


def test_invalid_root_is_terminal_without_replaying_workflow(tmp_path: Path) -> None:
    """根结果格式错误只报错；业务正确性应由显式 Step 检查。"""

    source = TASK_SOURCE.replace("    return used", "    return [1]")
    manager = _publish(tmp_path, task_source=source)
    service = ApplicationService(tmp_path, manifest_manager=manager)
    state = _finished(service, service.start("tasks.rotate_teams", {"teams": ["one"], "runs": 1}))
    assert state["result"]["failure_code"] == "invalid_output"
    events = [event["event"] for event in state["trace"]]
    assert not any("agent" in event or "verification" in event for event in events)
    assert sum(event["event"] == "component_started" and event["role"] == "task_workflow"
               for event in state["trace"]) == 1


def test_manifest_snapshot_pause_resume_and_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = _publish(tmp_path)
    first_manifest_id = manager.default.manifest_id
    service = ApplicationService(tmp_path, manifest_manager=manager)
    observe_entered = threading.Event()
    observe_release = threading.Event()
    original_observe = manager.actions["fake_observe"].execute

    def blocking_observe(ctx, *, completed: int, target: int) -> bool:
        observe_entered.set()
        observe_release.wait()
        return original_observe(ctx, completed=completed, target=target)

    from types import MappingProxyType
    from lalc.actions import TrustedAction
    manager.actions = MappingProxyType({**manager.actions, "fake_observe": TrustedAction(blocking_observe, "observe")})

    first_run = service.start("tasks.rotate_teams", {"teams": ["old"], "runs": 1})
    observe_entered.wait()
    service.pause()
    service.pause()
    second_task = TASK_SOURCE.replace("    return used\n", "    return [f\"new:{item}\" for item in used]\n").replace(
        "    return result == [teams[index % len(teams)] for index in range(runs)]\n",
        "    return result == [f\"new:{teams[index % len(teams)]}\" for index in range(runs)]\n",
    )
    manager = _publish(tmp_path, manager=manager, task_source=second_task)
    second_manifest_id = manager.default.manifest_id
    assert second_manifest_id != first_manifest_id
    observe_release.set()
    assert service.state["paused"] is True
    service.resume()
    service.resume()
    first = _finished(service, first_run)

    assert first["base_manifest_id"] == first_manifest_id
    assert first["default_manifest_id"] == second_manifest_id
    assert first["result"]["output"] == ["old"]
    events = [event["event"] for event in first["trace"]]
    assert events.count("run_paused") == 1
    assert events.count("run_resumed") == 1

    second_service = ApplicationService(tmp_path, manifest_manager=manager)
    second_run = second_service.start("tasks.rotate_teams", {"teams": ["old"], "runs": 1})
    assert _finished(second_service, second_run)["result"]["output"] == ["new:old"]

    observe_entered.clear()
    observe_release.clear()
    cancelled_run = second_service.start("tasks.rotate_teams", {"teams": ["old"], "runs": 1})
    observe_entered.wait()
    second_service.stop()
    second_service.stop()
    observe_release.set()
    cancelled = _finished(second_service, cancelled_run)
    assert cancelled["result"]["failure_code"] == "user_cancelled"
    assert [event["event"] for event in cancelled["trace"]].count("run_cancel_requested") == 1


def test_float_accepts_integer_but_other_coercions_remain_rejected(tmp_path: Path) -> None:
    float_step = '''"""Float normalization Step."""
from lalc import step

@step
def execute(ctx, *, value: float) -> float:
    return value
'''
    manager = _publish(tmp_path, step_source=float_step)
    service = ApplicationService(tmp_path, manifest_manager=manager)

    run_id = service.start("steps.run_team", {"value": 1})
    assert _finished(service, run_id)["result"]["output"] == 1.0
    with pytest.raises(StartError):
        service.start("steps.run_team", {"value": True})
    with pytest.raises(StartError):
        service.start("steps.run_team", {"value": float("nan")})


def test_gui_start_error_exposes_original_traceback(tmp_path: Path, monkeypatch) -> None:
    """启动被拒绝时，界面的错误详情保留底层异常与源码调用位置。"""

    from PySide6.QtWidgets import QApplication
    from lalc.gui import MainWindow, ErrorDialog

    app = QApplication.instance() or QApplication([])
    service = ApplicationService(tmp_path)

    def reject(*args, **kwargs):
        raise StartError("manifest_unavailable", "cannot start") from OSError("native startup failure")

    notices = []
    monkeypatch.setattr(service, "start", reject)
    monkeypatch.setattr(ErrorDialog, "open", lambda notice: notices.append(notice.details.toPlainText()))
    window = MainWindow(service)
    window._start()
    assert "OSError: native startup failure" in notices[0]
    assert "in reject" in notices[0]
    assert "StartError: cannot start" in notices[0]
    window.close()
    app.processEvents()


@pytest.mark.parametrize("outcome", ["success", "failure", "cancel", "takeover"])
def test_every_executed_trusted_action_records_inputs_result_and_elapsed(tmp_path: Path, outcome: str) -> None:
    """统一分派器为成功、失败和用户中断记录参数、真实结果及单次耗时。"""

    body = {
        "success": 'return {"team": team}',
        "failure": 'raise OSError("action failed") from ValueError("root cause")',
        "cancel": 'raise UserInterruption()',
        "takeover": 'raise UserInterruption("physical input", reason="takeover")',
    }[outcome]
    source = f'''"""测试统一动作日志。"""
from lalc import UserInterruption
def execute(ctx, *, team: str) -> dict[str, str]:
    {body}
'''
    manager = _publish(tmp_path, control_source=source)
    service = ApplicationService(tmp_path, manifest_manager=manager)
    run_id = service.start("steps.run_team", {"team": "alpha"})
    if outcome == "takeover":
        service.wait_for(lambda s: s["pause_info"] is not None)
        service.stop()
    state = _finished(service, run_id)
    events = [json.loads(line) for line in (tmp_path / "traces" / f"{run_id}.jsonl").read_text(encoding="utf-8").splitlines()]
    closing_name = "trusted_action_returned" if outcome == "success" else (
        "trusted_action_failed" if outcome == "failure" else "trusted_action_interrupted"
    )
    started = [event for event in events if event["event"] == "trusted_action_started"]
    closed = {event["call_id"]: event for event in events if event["event"] == closing_name}
    assert started
    assert len(started) == len(closed)
    for event in started:
        result = closed[event["call_id"]]
        assert result["inputs"] == event["inputs"] == {"team": "alpha"}
        assert result["parent_call_id"] == event["parent_call_id"]
        assert result["duration_ms"] >= 0
        if outcome == "success":
            assert result["return_value"] == {"team": "alpha"}
        elif outcome == "failure":
            assert "ValueError: root cause" in result["traceback"]
            assert "OSError: action failed" in result["traceback"]
        else:
            assert result["reason"] == outcome
            assert "return_value" not in result
    if outcome in {"cancel", "takeover"}:
        assert state["result"]["failure_code"] == "user_cancelled"
        assert not any(event["event"] == "step_reinvocation_started" for event in events)

