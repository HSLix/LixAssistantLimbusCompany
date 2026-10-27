"""覆盖 Python Plan 身份、输入快照、结果隔离、环境中断及旧数据拒绝。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_python_plan.py
"""

import json
from pathlib import Path

import pytest

from lalc.application import ApplicationService, StartError
from lalc.manifest import ManifestManager
from test_plan import _publish, _finished
from runtime_support import add_plan


def test_empty_initial_plan_publishes_and_runs(tmp_path):
    manager = ManifestManager(tmp_path / 'data')
    candidate = tmp_path / 'candidate'
    assert not manager.initialize_candidate(candidate)
    assert (candidate / 'plan.py').exists()
    saved = manager.publish(candidate / 'manifest.json')
    assert saved.ok, saved.errors
    assert manager.default_manifest_id() is None
    service = ApplicationService(manager.data_root, manifest_manager=manager)
    result = _finished(service, service.start_plan(manifest_id=saved.loaded.manifest_id))['result']
    assert result['status'] == 'completed' and result['all_tasks_succeeded']
    assert result['items'] == [] and result['output'] is None


@pytest.mark.parametrize('count', [0, 2])
def test_exactly_one_plan_required_without_rewriting_candidate(tmp_path, count):
    manager = _publish(tmp_path)
    path = tmp_path / 'candidate-0/manifest.json'
    data = json.loads(path.read_text())
    if count == 0:
        del data['components']['plans.default']
    else:
        data['components']['plans.other'] = data['components']['plans.default']
    path.write_text(json.dumps(data))
    before = path.read_bytes()
    result = manager.publish(path)
    assert not result.ok and 'unique_plan_required' in {e.code for e in result.errors}
    assert path.read_bytes() == before
    assert len(manager.list_manifests()) == 1


def test_legacy_saved_manifest_and_arbitrary_path_are_rejected_without_run(tmp_path):
    manager = _publish(tmp_path)
    path = manager.manifests_dir / f'{manager.default.manifest_id}.json'
    data = json.loads(path.read_text())
    del data['components']['plans.default']
    path.write_text(json.dumps(data))
    before = path.read_bytes()
    service = ApplicationService(tmp_path, manifest_manager=manager)
    with pytest.raises(StartError, match='incompatible'):
        service.start_plan()
    with pytest.raises(TypeError):
        service.start_plan(tmp_path / 'plan.py')
    assert service.state['run_id'] is None
    assert path.read_bytes() == before
    assert not (tmp_path / 'traces').exists()


@pytest.mark.parametrize('body', [
    '    ctx.call("steps.double", value=1)\n',
    '    ctx.call("plans.default", task_repetitions={}, settings={})\n',
    '    ctx.action("control.wait", seconds=0)\n',
    '    ctx.action("observe.capture_screen")\n',
    '    name = "tasks.double"\n    ctx.call(name, value=1)\n',
])
def test_plan_cannot_bypass_task_or_literal_call_boundary(tmp_path, body):
    manager = _publish(tmp_path)
    path = tmp_path / 'candidate-0/manifest.json'
    add_plan(path, body)
    assert not manager.publish(path).ok


def test_plan_input_snapshot_and_business_output_do_not_replace_statistics(tmp_path):
    manager = _publish(tmp_path, plan_body='    settings["page"]["items"].append("local")\n    ctx.call("tasks.double", value=1)\n    return {"items": [], "status": "fake", "configuration": settings}\n')
    path = tmp_path / 'candidate-0/plan.py'
    path.write_text(path.read_text().replace('-> None:', '-> Any:'))
    saved = manager.publish(path.parent / 'manifest.json')
    assert saved.ok, saved.errors
    service = ApplicationService(tmp_path, manifest_manager=manager)
    settings = {'page': {'items': [1, True, None, {'nested': 1.5}]}}
    result = _finished(service, service.start_plan(manifest_id=saved.loaded.manifest_id, settings=settings))['result']
    assert settings['page']['items'] == [1, True, None, {'nested': 1.5}]
    assert result['status'] == 'completed' and len(result['items']) == 1
    assert result['output']['status'] == 'fake' and result['output']['items'] == []
    assert result['output']['configuration']['page']['items'][-1] == 'local'


@pytest.mark.parametrize('inputs', [
    {'task_repetitions': {'task': True}}, {'task_repetitions': {'task': -1}},
    {'settings': {'page': {'value': float('nan')}}},
    {'settings': {'page': {'value': (1, 2)}}}, {'settings': {'page': {1: 'bad key'}}},
])
def test_invalid_plan_inputs_do_not_allocate_run(tmp_path, inputs):
    manager = _publish(tmp_path)
    service = ApplicationService(tmp_path, manifest_manager=manager)
    with pytest.raises(StartError) as raised:
        service.start_plan(**inputs)
    assert raised.value.code == 'inputs_invalid'
    assert service.state['run_id'] is None


def test_repetitions_continue_after_task_failures(tmp_path):
    manager = _publish(tmp_path, plan_body='    for _ in range(task_repetitions["sample"]):\n        ctx.call("tasks.double", value=-1)\n')
    service = ApplicationService(tmp_path, manifest_manager=manager)
    result = _finished(service, service.start_plan(task_repetitions={'sample': 3}))['result']
    assert result['status'] == 'completed' and not result['all_tasks_succeeded']
    assert len(result['items']) == 3
    assert all(i['failure_code'] == 'execution_failed' for i in result['items'])


def test_plan_error_keeps_previous_task_output_and_ledger(tmp_path):
    manager = _publish(tmp_path, plan_body='    ctx.call("tasks.double", value=1)\n    raise ValueError("plan failed")\n    ctx.call("tasks.double", value=2)\n')
    service = ApplicationService(tmp_path, manifest_manager=manager)
    result = _finished(service, service.start_plan())['result']
    assert result['status'] == 'interrupted' and result['reason'] == 'execution_failed'
    assert len(result['items']) == 1 and result['items'][0]['output'] == 2
    assert 'plan failed' in result['traceback'] and 'output' not in result
    assert sum(r['workflow_kind'] == 'task' for r in service.ledger_records()) == 1


def test_environment_failure_ends_plan_without_task_recovery(tmp_path, monkeypatch):
    from lalc.focused import WindowError
    manager = _publish(tmp_path)
    def execute(ctx, *, value: int) -> int:
        raise WindowError('game environment unavailable')
    execute.__lalc_role__ = 'step'
    monkeypatch.setattr(manager.default.components['steps.double'].module, 'execute', execute)
    service = ApplicationService(tmp_path, manifest_manager=manager)
    state = _finished(service, service.start_plan())
    assert state['result']['status'] == 'interrupted'
    assert state['result']['reason'] == 'environment_unavailable'
    assert len(state['result']['items']) == 1
    assert not any(e['event'] == 'safe_task_termination' for e in state['trace'])


def test_published_plan_hash_is_checked_before_start(tmp_path):
    manager = _publish(tmp_path)
    component = manager.default.components['plans.default']
    source = manager.components_dir / (component.component_id.removeprefix('sha256:') + '.py')
    source.write_text(source.read_text() + '\n# tampered\n')
    service = ApplicationService(tmp_path, manifest_manager=manager)
    with pytest.raises(StartError):
        service.start_plan()
    assert service.state['run_id'] is None


def test_agent_cannot_create_an_additional_plan(tmp_path):
    from test_agent_repair import host_for
    from lalc.manifest import EMPTY_PLAN
    host, _ = host_for(tmp_path)
    before = (host.candidate / "manifest.json").read_bytes()
    with pytest.raises(ValueError, match="只能编辑已有 Plan"):
        host.conversation.tools.add_component("another.py", "plans.another", EMPTY_PLAN)
    assert not (host.candidate / "another.py").exists()
    assert (host.candidate / "manifest.json").read_bytes() == before


def test_later_task_missing_from_working_manifest_is_recorded_as_task_failure(tmp_path):
    from test_plan import STEP
    broken = STEP.replace('if calls == 1:', 'if True:')
    manager = _publish(tmp_path, step_source=broken)
    first = manager.default.manifest_id
    replacement = STEP.replace('if calls == 1:', 'if False:')
    _publish(tmp_path, manager, step_source=replacement)
    candidate = tmp_path / 'candidate-1/manifest.json'
    add_plan(candidate)
    data = json.loads(candidate.read_text())
    del data['components']['tasks.double']
    candidate.write_text(json.dumps(data))
    saved = manager.publish(candidate)
    assert saved.ok, saved.errors
    choices = iter([saved.loaded.manifest_id])
    service = ApplicationService(tmp_path, manifest_manager=manager,
                                 recovery_choice=lambda *_: next(choices, None))
    result = _finished(service, service.start_plan(manifest_id=first))['result']
    assert result['status'] == 'completed'
    assert [i['result'] for i in result['items']] == ['success', 'failure']
    assert result['items'][1]['failure_code'] == 'working_manifest_incompatible'
    tasks = [r for r in service.ledger_records() if r['workflow_kind'] == 'task']
    assert len(tasks) == 2 and tasks[1]['component_id'] is None
    assert None not in service.workflow_health()


def test_cancellation_before_task_entry_creates_no_task_result(tmp_path, monkeypatch):
    from lalc.runtime import WorkflowExecutor
    manager = _publish(tmp_path)
    invoke = WorkflowExecutor._invoke_component
    def cancel_before_entry(self, name, component, arguments, **kwargs):
        if component.role == "task_workflow":
            self.gate.stop()
        return invoke(self, name, component, arguments, **kwargs)
    monkeypatch.setattr(WorkflowExecutor, "_invoke_component", cancel_before_entry)
    service = ApplicationService(tmp_path, manifest_manager=manager)
    result = _finished(service, service.start_plan())["result"]
    assert result["reason"] == "user_cancelled" and result["items"] == []
    assert service.ledger_records() == []


@pytest.mark.parametrize("key", ["manifest_id", "_developer_trial"])
def test_cli_plan_inputs_cannot_override_start_request(tmp_path, monkeypatch, capsys, key):
    import lalc.__main__ as cli
    _publish(tmp_path)
    monkeypatch.setattr(cli, "default_data_root", lambda: tmp_path)
    assert cli.main(["run-plan", "--inputs", json.dumps({key: True})]) == 1
    assert "only task_repetitions and settings" in capsys.readouterr().err
    assert not (tmp_path / "run-sequence.json").exists()
