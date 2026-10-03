"""覆盖 Step 恢复、异常终止和完整 Working Manifest 切换。

在项目根目录运行：
UV_CACHE_DIR=.generated/uv-cache uv run --frozen pytest -q tests/test_recovery.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import lalc.application as application_module
from lalc.application import ApplicationService
from lalc.manifest import ManifestManager


TASK = '''"""Recovery task."""
from lalc import task_workflow

@task_workflow
def execute(ctx, *, value: int) -> list[str]:
    first = ctx.call("steps.break", value=value)
    second = ctx.call("flows.next", value=value)
    return ["task-old", first, second]

def verify(ctx, result: list[str], *, value: int) -> bool:
    return len(result) == 3
'''
SUB = '''"""Recovery subworkflow."""
from lalc import sub_workflow

@sub_workflow
def execute(ctx, *, value: int) -> str:
    return "sub-old"
'''
STEP = '''"""Interrupting Step {nonce}."""
from lalc import ExecutionInterruption, step
calls = 0

@step
def execute(ctx, *, value: int) -> str:
    global calls
    calls += 1
    if calls == 1:
        raise ExecutionInterruption("state unknown")
    return f"step-old:{value}"
'''
NEW_STEP = '''"""Replacement Step."""
from lalc import step

@step
def execute(ctx, *, value: int) -> str:
    return f"step-new:{value}"
'''
FAIL_STEP = '''"""Still interrupting Step."""
from lalc import ExecutionInterruption, step

@step
def execute(ctx, *, value: int) -> str:
    raise ExecutionInterruption("still broken")
'''
LATER_FAIL_STEP = '''"""Step that fails at its next new call."""
from lalc import ExecutionInterruption, step
calls = 0

@step
def execute(ctx, *, value: int) -> str:
    global calls
    calls += 1
    if calls == 2:
        raise ExecutionInterruption("later failure")
    return f"step-new:{value}"
'''


def _publish(
    root: Path, manager: ManifestManager, *, step_source: str,
    task_source: str = TASK, sub_source: str = SUB,
    rules: dict[str, str] | None = None,
) -> str:
    folder = root / f"candidate-{len(list(root.glob('candidate-*')))}"
    folder.mkdir()
    sources = {"task.py": task_source, "sub.py": sub_source, "step.py": step_source}
    sources.update({f"{name}.py": source for name, source in (rules or {}).items()})
    for name, source in sources.items():
        (folder / name).write_text(source, encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "components": {
            "tasks.run": {"source_path": "task.py"},
            "flows.next": {"source_path": "sub.py"},
            "steps.break": {"source_path": "step.py"},
        },
        "recovery_rules": {
            name: {"source_path": f"{name}.py"} for name in (rules or {})
        },
        "trusted_actions": {},
        "assets": {},
    }
    path = folder / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    result = manager.publish(path)
    assert result.ok, result.errors
    return result.loaded.manifest_id


def _rule(detect: str, recover: str = "return None") -> str:
    return f'''"""Recovery rule."""
def detect(ctx) -> bool:
    {detect}

def recover(ctx) -> None:
    {recover}
'''


def _finish(service: ApplicationService, run_id: int) -> dict[str, Any]:
    return service.wait_for(lambda state: state["run_id"] == run_id and state["phase"] == "finished")


@pytest.mark.parametrize(
    ("rules", "success", "expected"),
    [
        ({}, True, "step_reinvocation_returned"),
        ({"one": _rule("return True")}, True, "recovery_rule_returned"),
        ({"two": _rule("return True"), "one": _rule("return True")}, False, "execution_anomaly"),
        ({"one": _rule('raise RuntimeError("detect boom")'), "two": _rule("return True")}, False, "recovery_rule_failed"),
        ({"one": _rule("return True", "return 1")}, False, "execution_anomaly"),
        ({"one": _rule("return True", 'raise RuntimeError("recover boom")')}, False, "recovery_rule_failed"),
    ],
)
def test_rule_paths_keep_workflow_frame_and_stop_safely(
    tmp_path: Path, rules: dict[str, str], success: bool, expected: str,
) -> None:
    manager = ManifestManager(tmp_path)
    manifest_id = _publish(tmp_path, manager, step_source=STEP.replace("{nonce}", tmp_path.name), rules=rules)
    assert manager.set_default(manifest_id).ok
    service = ApplicationService(tmp_path, manifest_manager=manager)

    state = _finish(service, service.start("tasks.run", {"value": 7}))

    events = [event["event"] for event in state["trace"]]
    assert expected in events
    detections = [
        event["logical_name"] for event in state["trace"]
        if event["event"] == "recovery_rule_started" and event["phase"] == "detect"
    ]
    assert detections == sorted(detections)
    if "two" in rules and "detect boom" in rules["one"]:
        assert detections == ["one"]
    if success:
        assert state["result"]["output"] == ["task-old", "step-old:7", "sub-old"]
        assert "safe_task_termination" not in events
    else:
        assert state["result"]["failure_code"] == "execution_anomaly"
        assert events.count("safe_task_termination") == 1
        assert "component_started" not in events[events.index("execution_anomaly"):]
    assert json.loads((tmp_path / "runs" / "1.json").read_text())["working_manifest_id"] == manifest_id


def test_whole_manifest_switch_changes_later_calls_but_not_entered_task(tmp_path: Path) -> None:
    manager = ManifestManager(tmp_path)
    rules = {"blocking": _rule('raise RuntimeError("needs repair")')}
    base = _publish(tmp_path, manager, step_source=STEP.replace("{nonce}", tmp_path.name), rules=rules)
    revised_task = TASK.replace('"task-old"', '"task-new"')
    revised_sub = SUB.replace('"sub-old"', '"sub-new"')
    replacement = _publish(tmp_path, manager, step_source=NEW_STEP, task_source=revised_task, sub_source=revised_sub, rules=rules)
    assert manager.set_default(base).ok
    service = ApplicationService(tmp_path, manifest_manager=manager, recovery_choice=lambda *_: replacement)

    state = _finish(service, service.start("tasks.run", {"value": 4}))

    assert state["result"]["output"] == ["task-old", "step-new:4", "sub-new"]
    assert state["base_manifest_id"] == base
    assert state["working_manifest_id"] == replacement
    assert state["attempted_manifest_ids"] == [base, replacement]
    persisted = json.loads((tmp_path / "runs" / "1.json").read_text())
    assert persisted == {
        "base_manifest_id": base,
        "working_manifest_id": replacement,
        "attempted_manifest_ids": [base, replacement],
    }
    sub = next(event for event in state["trace"] if event["event"] == "component_started" and event["logical_name"] == "flows.next")
    assert sub["manifest_id"] == replacement
    assert [event["manifest_id"] for event in state["trace"] if event["event"] == "working_manifest_selected"] == [replacement]


def test_failed_selected_step_remains_history_then_prior_manifest_can_succeed(tmp_path: Path) -> None:
    manager = ManifestManager(tmp_path)
    rules = {"blocking": _rule('raise RuntimeError("needs repair")')}
    base = _publish(tmp_path, manager, step_source=STEP.replace("{nonce}", tmp_path.name), rules=rules)
    failed = _publish(tmp_path, manager, step_source=FAIL_STEP, rules=rules)
    assert manager.set_default(base).ok
    choices = iter([failed, base])
    service = ApplicationService(tmp_path, manifest_manager=manager, recovery_choice=lambda *_: next(choices))

    state = _finish(service, service.start("tasks.run", {"value": 5}))

    assert state["result"]["output"] == ["task-old", "step-old:5", "sub-old"]
    assert state["working_manifest_id"] == base
    assert state["attempted_manifest_ids"] == [base, failed]
    assert [event["manifest_id"] for event in state["trace"] if event["event"] == "working_manifest_selected"] == [failed, base]


def test_later_step_failure_keeps_selected_manifest(tmp_path: Path) -> None:
    manager = ManifestManager(tmp_path)
    rules = {"blocking": _rule('raise RuntimeError("needs repair")')}
    base = _publish(tmp_path, manager, step_source=STEP.replace("{nonce}", tmp_path.name), rules=rules)
    later_sub = SUB.replace('return "sub-old"', 'return ctx.call("steps.break", value=value)')
    selected = _publish(tmp_path, manager, step_source=LATER_FAIL_STEP, sub_source=later_sub, rules=rules)
    assert manager.set_default(base).ok
    choices = iter([selected, None])
    service = ApplicationService(tmp_path, manifest_manager=manager, recovery_choice=lambda *_: next(choices))

    state = _finish(service, service.start("tasks.run", {"value": 3}))

    assert state["result"]["failure_code"] == "execution_anomaly"
    assert state["working_manifest_id"] == selected
    assert [event["manifest_id"] for event in state["trace"] if event["event"] == "working_manifest_selected"] == [selected]
    assert [event["event"] for event in state["trace"]].count("step_interrupted") == 2


@pytest.mark.parametrize(
    "replacement_source",
    [
        NEW_STEP.replace("*, value: int", "*, value: int, extra: int"),
        NEW_STEP.replace("-> str:", "-> int:").replace('return f"step-new:{value}"', "return value"),
        NEW_STEP + "\ndef condition(ctx, *, value: int) -> bool:\n    return False\n",
    ],
)
def test_incompatible_replacement_is_rejected_before_selection(
    tmp_path: Path, replacement_source: str,
) -> None:
    manager = ManifestManager(tmp_path)
    rules = {"blocking": _rule('raise RuntimeError("needs repair")')}
    base = _publish(tmp_path, manager, step_source=STEP.replace("{nonce}", tmp_path.name), rules=rules)
    incompatible = _publish(tmp_path, manager, step_source=replacement_source, rules=rules)
    assert manager.set_default(base).ok
    choices = iter([incompatible, None])
    service = ApplicationService(tmp_path, manifest_manager=manager, recovery_choice=lambda *_: next(choices))

    state = _finish(service, service.start("tasks.run", {"value": 6}))

    assert state["result"]["failure_code"] == "execution_anomaly"
    assert state["working_manifest_id"] == base
    assert state["attempted_manifest_ids"] == [base]
    assert any(event["event"] == "manifest_selection_rejected" and event["manifest_id"] == incompatible for event in state["trace"])


def test_repeated_interruption_and_step_external_interruption_terminate(tmp_path: Path) -> None:
    manager = ManifestManager(tmp_path)
    repeated = _publish(tmp_path, manager, step_source=FAIL_STEP)
    assert manager.set_default(repeated).ok
    service = ApplicationService(tmp_path, manifest_manager=manager)

    repeated_state = _finish(service, service.start("tasks.run", {"value": 2}))
    assert repeated_state["result"]["failure_code"] == "execution_anomaly"
    repeated_events = [event["event"] for event in repeated_state["trace"]]
    assert sum(event["event"] == "component_failed" and event["logical_name"] == "steps.break" for event in repeated_state["trace"]) == 2
    assert repeated_events.count("step_reinvocation_failed") == 1

    external_task = TASK.replace(
        '    first = ctx.call("steps.break", value=value)',
        '    raise ExecutionInterruption("outside Step")',
    ).replace("from lalc import task_workflow", "from lalc import ExecutionInterruption, task_workflow")
    external = _publish(tmp_path, manager, step_source=NEW_STEP, task_source=external_task)
    external_state = _finish(service, service.start("tasks.run", {"value": 2}, manifest_id=external))
    assert external_state["result"]["failure_code"] == "execution_anomaly"
    external_events = [event["event"] for event in external_state["trace"]]
    assert "step_reinvocation_started" not in external_events
    assert external_events.count("safe_task_termination") == 1


def test_unsatisfied_step_condition_never_enters_step_body(tmp_path: Path) -> None:
    source = '''"""Step whose current state is not enterable."""
from lalc import step

@step
def execute(ctx, *, value: int) -> str:
    return "must-not-run"

def condition(ctx, *, value: int) -> bool:
    return False
'''
    manager = ManifestManager(tmp_path)
    manifest_id = _publish(tmp_path, manager, step_source=source)
    assert manager.set_default(manifest_id).ok
    service = ApplicationService(tmp_path, manifest_manager=manager)

    state = _finish(service, service.start("tasks.run", {"value": 1}))

    assert state["result"]["failure_code"] == "execution_anomaly"
    assert not any(event["event"] == "component_started" and event["logical_name"] == "steps.break" for event in state["trace"])
    assert [event["return_value"] for event in state["trace"] if event["event"] == "condition_evaluated"] == [False, False]


def test_invalid_complete_manifest_cannot_replace_working_manifest(tmp_path: Path) -> None:
    manager = ManifestManager(tmp_path)
    rules = {"blocking": _rule('raise RuntimeError("needs repair")')}
    base = _publish(tmp_path, manager, step_source=STEP.replace("{nonce}", tmp_path.name), rules=rules)
    invalid = _publish(tmp_path, manager, step_source=NEW_STEP, rules=rules)
    path = manager.manifests_dir / f"{invalid}.json"
    document = json.loads(path.read_text())
    document["components"]["steps.break"]["component_id"] = "sha256:" + "0" * 64
    path.write_text(json.dumps(document))
    assert manager.set_default(base).ok
    choices = iter([invalid, None])
    service = ApplicationService(tmp_path, manifest_manager=manager, recovery_choice=lambda *_: next(choices))

    state = _finish(service, service.start("tasks.run", {"value": 9}))

    assert state["result"]["failure_code"] == "execution_anomaly"
    assert state["working_manifest_id"] == base
    assert state["attempted_manifest_ids"] == [base]
    assert any(event["event"] == "manifest_selection_rejected" and event["manifest_id"] == invalid for event in state["trace"])


def test_working_manifest_write_failure_prevents_replacement_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = ManifestManager(tmp_path)
    rules = {"blocking": _rule('raise RuntimeError("needs repair")')}
    base = _publish(tmp_path, manager, step_source=STEP.replace("{nonce}", tmp_path.name), rules=rules)
    replacement = _publish(tmp_path, manager, step_source=NEW_STEP, rules=rules)
    replacement_step_id = manager.load(replacement).loaded.components["steps.break"].component_id
    assert manager.set_default(base).ok
    original_write = application_module.atomic_write_json

    def fail_replacement(path: Path, value: dict[str, Any]) -> None:
        if path.parent.name == "runs" and path.exists():
            raise OSError("disk unavailable")
        original_write(path, value)

    monkeypatch.setattr(application_module, "atomic_write_json", fail_replacement)
    service = ApplicationService(tmp_path, manifest_manager=manager, recovery_choice=lambda *_: replacement)

    state = _finish(service, service.start("tasks.run", {"value": 8}))

    assert state["result"]["failure_code"] == "working_manifest_write_failed"
    assert state["working_manifest_id"] == base
    assert json.loads((tmp_path / "runs" / "1.json").read_text())["working_manifest_id"] == base
    assert not any(event["event"] == "component_started" and event["component_id"] == replacement_step_id for event in state["trace"])
