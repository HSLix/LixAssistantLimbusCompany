"""覆盖 Automation Plan 预检、顺序执行、取消及 Workflow Run Ledger。

在项目根目录运行：
UV_CACHE_DIR=.generated/uv-cache uv run --frozen pytest -q tests/test_plan.py
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import lalc.__main__ as cli
from lalc.application import ApplicationService
from lalc.manifest import ManifestManager


TASK = '''"""Plan test Task."""
from lalc import task_workflow

@task_workflow
def execute(ctx, *, value: int) -> int:
    return ctx.call("flows.double", value=value)

'''
SUB = '''"""Plan test Subworkflow."""
from lalc import sub_workflow

@sub_workflow
def execute(ctx, *, value: int) -> int:
    return ctx.call("steps.double", value=value)
'''
STEP = '''"""Plan test Step."""
from lalc import ExecutionFailure, step
calls = 0

@step
def execute(ctx, *, value: int) -> int:
    global calls
    calls += 1
    if value < 0:
        raise ExecutionFailure("negative value")
    if calls == 1:
        raise ExecutionFailure("observe again")
    return value * 2
'''


def _publish(
    root: Path, manager: ManifestManager | None = None,
    *, task_source: str = TASK, step_source: str = STEP,
) -> ManifestManager:
    candidate = root / f"candidate-{len(list(root.glob('candidate-*')))}"
    candidate.mkdir(parents=True)
    for name, source in {"task.py": task_source, "sub.py": SUB, "step.py": step_source}.items():
        (candidate / name).write_text(source, encoding="utf-8")
    (candidate / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "components": {
            "tasks.double": {"source_path": "task.py"},
            "flows.double": {"source_path": "sub.py"},
            "steps.double": {"source_path": "step.py"},
        },
        "recovery_rules": {}, "trusted_actions": {}, "assets": {},
    }), encoding="utf-8")
    manager = manager or ManifestManager(root)
    published = manager.publish(candidate / "manifest.json")
    assert published.ok, published.errors
    assert manager.set_default(published.loaded.manifest_id).ok
    return manager


def _finished(service: ApplicationService, run_id: int) -> dict:
    return service.wait_for(lambda state: state["run_id"] == run_id and state["phase"] == "finished")


def test_plan_continues_after_item_failure_and_ledger_counts_unique_events(tmp_path: Path, monkeypatch, capsys) -> None:
    manager = _publish(tmp_path)
    path = tmp_path / "plan.json"
    path.write_text(json.dumps({"items": [
        {"task": "tasks.double", "inputs": {"value": 1}},
        {"task": "tasks.double", "inputs": {"value": -1}},
        {"task": "tasks.double", "inputs": {"value": 2}},
    ]}), encoding="utf-8")
    monkeypatch.setattr(cli, "default_data_root", lambda: tmp_path)

    assert cli.main(["run-plan", str(path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "completed"
    assert [item["result"] for item in result["items"]] == ["success", "failure", "success"]
    assert result["items"][1]["failure_code"] == "execution_failed"
    assert {item["run_id"] for item in result["items"]} == {1}

    service = ApplicationService(tmp_path, manifest_manager=manager)
    saved = json.loads((tmp_path / "ledger" / "1.json").read_text(encoding="utf-8"))
    tasks = [record for record in saved["records"] if record["workflow_kind"] == "task"]
    subs = [record for record in saved["records"] if record["workflow_kind"] == "sub"]
    assert [record["result"] for record in tasks] == ["success", "failure", "success"]
    assert [record["result"] for record in subs] == ["success", "failure", "success"]
    assert tasks[0]["step_reinvocations"] == subs[0]["step_reinvocations"] == 1
    assert service.application_event_totals()["step_reinvocations"] == 2
    health = service.workflow_health()[manager.default.components["tasks.double"].component_id]
    assert health["strict_success_rate"] == 2 / 3
    assert health["agent_assisted_completion_rate"] == 0
    trace = [json.loads(line) for line in (tmp_path / "traces" / "1.jsonl").read_text(encoding="utf-8").splitlines()]
    started = [event for event in trace if event["event"] == "component_started" and event["role"] == "task_workflow"]
    assert len(started) == 3
    assert not any(event["event"].startswith("verification_") for event in trace)


def test_invalid_plan_reports_all_errors_before_any_task(tmp_path: Path) -> None:
    manager = _publish(tmp_path)
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps({"items": [
        {"task": "tasks.missing", "inputs": {}},
        {"task": "steps.double", "inputs": {"value": 1}},
        {"task": "tasks.double", "inputs": {"value": True}},
    ]}), encoding="utf-8")
    service = ApplicationService(tmp_path, manifest_manager=manager)

    state = _finished(service, service.start_plan(path))

    assert state["result"]["status"] == "interrupted"
    assert state["result"]["reason"] == "invalid_plan"
    assert {error["index"] for error in state["result"]["errors"]} == {0, 1, 2}
    assert not any(event["event"] == "component_started" for event in state["trace"])
    assert not (tmp_path / "ledger" / "1.json").exists()


def test_cancellation_stops_plan_and_skips_later_item(tmp_path: Path, monkeypatch) -> None:
    manager = _publish(tmp_path)
    entered, release = threading.Event(), threading.Event()
    original = manager.default.components["steps.double"].module.execute

    def blocking(ctx, *, value: int) -> int:
        entered.set()
        release.wait()
        return original(ctx, value=value)

    blocking.__lalc_role__ = "step"
    monkeypatch.setattr(manager.default.components["steps.double"].module, "execute", blocking)
    path = tmp_path / "plan.json"
    path.write_text(json.dumps({"items": [
        {"task": "tasks.double", "inputs": {"value": 1}},
        {"task": "tasks.double", "inputs": {"value": 2}},
    ]}), encoding="utf-8")
    service = ApplicationService(tmp_path, manifest_manager=manager)

    run_id = service.start_plan(path)
    assert entered.wait(2)
    service.stop()
    release.set()
    state = _finished(service, run_id)

    assert state["result"]["status"] == "interrupted"
    assert state["result"]["reason"] == "user_cancelled"
    assert len(state["result"]["items"]) == 1
    assert state["result"]["items"][0]["failure_code"] == "user_cancelled"
    records = service.ledger_records()
    assert len([record for record in records if record["workflow_kind"] == "task"]) == 1


def test_later_item_uses_current_working_manifest(tmp_path: Path) -> None:
    broken = '''"""Interrupting Step."""
from lalc import ExecutionFailure, step

@step
def execute(ctx, *, value: int) -> int:
    raise ExecutionFailure("cannot continue")
'''
    replacement = '''"""Replacement Step."""
from lalc import step

@step
def execute(ctx, *, value: int) -> int:
    return value * 2
'''
    new_task = TASK.replace("value: int) -> int:", "value: int, extra: int) -> int:").replace(
        "value: int) -> bool:", "value: int, extra: int) -> bool:"
    )
    manager = _publish(tmp_path, step_source=broken)
    first_id = manager.default.manifest_id
    _publish(tmp_path, manager, task_source=new_task, step_source=replacement)
    second_id = manager.default.manifest_id
    choices = iter([second_id])
    service = ApplicationService(
        tmp_path, manifest_manager=manager,
        recovery_choice=lambda *_: next(choices, None),
    )
    path = tmp_path / "plan.json"
    path.write_text(json.dumps({"items": [
        {"task": "tasks.double", "inputs": {"value": 1}},
        {"task": "tasks.double", "inputs": {"value": 2}},
    ]}), encoding="utf-8")

    state = _finished(service, service.start_plan(path, manifest_id=first_id))

    assert state["result"]["status"] == "completed"
    assert [item["result"] for item in state["result"]["items"]] == ["success", "failure"]
    assert state["result"]["items"][1]["failure_code"] == "working_manifest_incompatible"
    assert state["working_manifest_id"] == second_id
    tasks = [record for record in service.ledger_records() if record["workflow_kind"] == "task"]
    assert [record["manifest_id"] for record in tasks] == [first_id, second_id]


def test_ledger_write_failure_interrupts_plan(tmp_path: Path, monkeypatch) -> None:
    from lalc.ledger import LedgerWriteError, WorkflowRunLedger

    manager = _publish(tmp_path)
    path = tmp_path / "plan.json"
    path.write_text(json.dumps({"items": [
        {"task": "tasks.double", "inputs": {"value": 1}},
        {"task": "tasks.double", "inputs": {"value": 2}},
    ]}), encoding="utf-8")
    def fail_save(self) -> None:
        raise LedgerWriteError("disk full")

    monkeypatch.setattr(WorkflowRunLedger, "_save", fail_save)
    service = ApplicationService(tmp_path, manifest_manager=manager)

    state = _finished(service, service.start_plan(path))

    assert state["result"]["status"] == "interrupted"
    assert state["result"]["reason"] == "ledger_write_failed"
    assert state["result"]["items"] == []
    assert [event["event"] for event in state["trace"]].count("component_started") == 1
    assert not any(event["event"] == "component_started" and event["role"] == "step"
                   for event in state["trace"])
    assert manager.default.components["steps.double"].module.calls == 0


def test_cancellation_between_items_creates_no_next_task_record(tmp_path: Path) -> None:
    manager = _publish(tmp_path)
    path = tmp_path / "plan.json"
    path.write_text(json.dumps({"items": [
        {"task": "tasks.double", "inputs": {"value": 1}},
        {"task": "tasks.double", "inputs": {"value": 2}},
    ]}), encoding="utf-8")
    service = ApplicationService(tmp_path, manifest_manager=manager)
    emit = service._emit

    def stop_after_first(event: str, fields: dict) -> None:
        emit(event, fields)
        if event == "plan_item_finished" and fields["index"] == 0:
            service.stop()

    service._emit = stop_after_first
    state = _finished(service, service.start_plan(path))

    assert state["result"]["reason"] == "user_cancelled"
    assert len(state["result"]["items"]) == 1
    assert state["result"]["items"][0]["result"] == "success"
    assert len([record for record in service.ledger_records() if record["workflow_kind"] == "task"]) == 1


def test_direct_task_and_subworkflow_also_write_ledger(tmp_path: Path) -> None:
    manager = _publish(tmp_path)
    service = ApplicationService(tmp_path, manifest_manager=manager)

    first = _finished(service, service.start("tasks.double", {"value": 1}))
    assert first["result"]["status"] == "success"
    second = _finished(service, service.start("flows.double", {"value": 2}))
    assert second["result"]["status"] == "success"
    direct = service.ledger_records()

    assert len(direct) == 1
    assert direct[0]["workflow_kind"] == "sub"
    assert direct[0]["result"] == "success"
    assert (tmp_path / "ledger" / "1.json").exists()


def test_agent_invocation_is_attributed_to_both_spans_but_counted_once(tmp_path: Path) -> None:
    from lalc.ledger import WorkflowRunLedger, application_event_totals, workflow_health

    ledger = WorkflowRunLedger(tmp_path, 1)
    task = {"event": "component_started", "role": "task_workflow", "run_id": 1,
            "call_id": 1, "parent_call_id": None, "logical_name": "tasks.run",
            "component_id": "task-id", "manifest_id": "manifest-id", "inputs": {},
            "recorded_at": "2026-10-03T00:00:00+00:00"}
    sub = {**task, "role": "sub_workflow", "call_id": 2, "parent_call_id": 1,
           "logical_name": "flows.run", "component_id": "sub-id"}
    ledger.observe(task)
    ledger.observe(sub)
    ledger.observe({"event": "agent_invoked", "recorded_at": "2026-10-03T00:00:01+00:00"})
    ledger.observe({**sub, "event": "component_returned", "duration_ms": 1000})
    ledger.finish_task({**task, "ended_at": "2026-10-03T00:00:02+00:00"},
                       {"status": "success"}, 2000)

    assert [record["agent_invocations"] for record in ledger.records] == [1, 1]
    assert application_event_totals(tmp_path)["agent_invocations"] == 1
    assert workflow_health(tmp_path)["task-id"]["agent_assisted_completion_rate"] == 1
