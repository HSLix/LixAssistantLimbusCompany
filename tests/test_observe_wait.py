"""覆盖 observe.wait 的调用阶段、输入隔离、时长与旧名称拒绝。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_observe_wait.py
"""

import json
from types import SimpleNamespace

import pytest

from lalc.application import ApplicationService
from lalc.control import InputSession
from lalc.manifest import ManifestManager
from lalc.runtime import ExecutionFailure, RunGate, WorkflowExecutor
from runtime_support import add_plan
from test_input_control import FakeWindow, finished, paused


def wait_candidate(tmp_path):
    """建立经过真实校验的三层调用及 condition/detect/recover 等待样例。"""
    candidate = tmp_path / 'candidate'
    candidate.mkdir()
    sources = {
        'task': '''from lalc import task_workflow
@task_workflow
def execute(ctx, *, fail: bool = False) -> None:
    ctx.action("observe.wait", seconds=0)
    ctx.call("sub.flow", fail=fail)
''',
        'sub': '''from lalc import sub_workflow
@sub_workflow
def execute(ctx, *, fail: bool = False) -> None:
    ctx.action("observe.wait", seconds=0)
    ctx.call("steps.wait", fail=fail)
''',
        'step': '''from lalc import step
@step
def execute(ctx, *, fail: bool = False) -> None:
    ctx.action("observe.wait", seconds=0)
    if fail:
        raise ValueError("exercise recovery")
def condition(ctx, *, fail: bool = False) -> bool:
    ctx.action("observe.wait", seconds=0)
    return True
''',
        'rule': '''def detect(ctx) -> bool:
    ctx.action("observe.wait", seconds=0)
    return True
def recover(ctx) -> None:
    ctx.action("observe.wait", seconds=0)
''',
    }
    for name, body in sources.items():
        (candidate / f'{name}.py').write_text('"""等待权限测试。"""\n' + body, encoding="utf-8")
    path = candidate / 'manifest.json'
    path.write_text(json.dumps({'schema_version': 2, 'components': {
        'tasks.wait': {'source_path': 'task.py'}, 'sub.flow': {'source_path': 'sub.py'},
        'steps.wait': {'source_path': 'step.py'}},
        'recovery_rules': {'rules.wait': {'source_path': 'rule.py'}}}), encoding="utf-8")
    add_plan(path)
    return path


@pytest.mark.parametrize('fail', [False, True])
def test_wait_executes_in_all_observe_phases_without_injecting_input(tmp_path, fail):
    path = wait_candidate(tmp_path)
    manager = ManifestManager(tmp_path / 'data')
    published = manager.publish(path)
    assert published.ok, published.errors
    window = FakeWindow()
    service = ApplicationService(manager.data_root, manifest_manager=manager, window_platform=window)
    service.start('tasks.wait', {'fail': fail}, manifest_id=published.loaded.manifest_id)
    state = finished(service)
    assert state['result']['status'] == ('failure' if fail else 'success')
    events = state['trace']
    waits = [e for e in events if e['event'] == 'trusted_action_started']
    assert waits and all(e['logical_name'] == 'observe.wait' and e['classification'] == 'observe' for e in waits)
    parents = {}
    phases = set()
    for event in events:
        if event['event'] in {'component_started', 'condition_started', 'recovery_rule_started'}:
            parents[event['call_id']] = (event['role'], event['phase'])
        elif event['event'] == 'trusted_action_started':
            phases.add(parents[event['parent_call_id']])
    assert phases == ({('task_workflow', 'execute'), ('sub_workflow', 'execute'),
                       ('step', 'condition'), ('step', 'execute')}
                      | ({('recovery_rule', 'detect'), ('recovery_rule', 'recover')} if fail else set()))
    assert window.backend.events == []


def test_old_wait_name_is_rejected_without_rewriting_source(tmp_path):
    path = wait_candidate(tmp_path)
    source = path.parent / 'task.py'
    source.write_text(source.read_text(encoding="utf-8").replace('observe.wait', 'control.wait'), encoding="utf-8")
    before = source.read_bytes()
    result = ManifestManager(tmp_path / 'data').publish(path)
    assert not result.ok
    assert any('control.wait' in error.message for error in result.errors)
    assert source.read_bytes() == before


@pytest.mark.parametrize('classification', [None, 'observe', 'control'])
@pytest.mark.parametrize('operation', ['wait', 'click', 'key_press', 'drag', 'restart_game'])
def test_observe_backend_allows_only_wait(classification, operation):
    calls = []
    executor = WorkflowExecutor(SimpleNamespace(manifest_id='test'), RunGate(), lambda *_: None,
                                control_input=lambda *args: calls.append(args))
    executor._active_action = classification
    if classification == 'control' or (classification == 'observe' and operation == 'wait'):
        executor.control_input(operation, {})
        assert calls == [(operation, {})]
    else:
        with pytest.raises(ExecutionFailure):
            executor.control_input(operation, {})
        assert calls == []


@pytest.mark.parametrize('seconds', [-1, 60.1, float('nan'), float('inf'), True, '1'])
def test_invalid_wait_duration_is_rejected_before_waiting(monkeypatch, seconds):
    session = InputSession.__new__(InputSession)
    session.check = lambda: None
    session.backend = type('Backend', (), {'any_pressed': lambda self: False})()
    monkeypatch.setattr(session, '_wait', lambda *_: pytest.fail('invalid duration reached wait'))
    with pytest.raises(ValueError, match='between 0 and 60'):
        session.execute('wait', {'seconds': seconds})


@pytest.mark.parametrize('cancel', [False, True])
def test_workflow_wait_takeover_preserves_stack_and_can_cancel(tmp_path, monkeypatch, cancel):
    path = wait_candidate(tmp_path)
    task = path.parent / 'task.py'
    task.write_text(task.read_text(encoding="utf-8").replace(
        '    ctx.action("observe.wait", seconds=0)',
        '    ctx.call("steps.wait")\n    ctx.action("observe.wait", seconds=0.03)'), encoding="utf-8")
    manager = ManifestManager(tmp_path / 'data')
    published = manager.publish(path)
    assert published.ok, published.errors
    window = FakeWindow()
    service = ApplicationService(manager.data_root, manifest_manager=manager, window_platform=window)
    durations = []
    original_wait = InputSession._wait

    def wait(session, duration, update=None):
        if duration == 0.03:
            durations.append(duration)
            if len(durations) == 1:
                window.backend.monitor.record("键盘", False)
        original_wait(session, duration, update)

    monkeypatch.setattr(InputSession, '_wait', wait)
    monkeypatch.setattr(InputSession, 'QUIET_SECONDS', 0.001)
    service.start('tasks.wait', {}, manifest_id=published.loaded.manifest_id)
    state = paused(service)
    assert state['pause_info']['restart_step'] is False
    if cancel:
        service.stop()
    else:
        service.resume()
    state = finished(service)
    assert state['result']['status'] == ('failure' if cancel else 'success')
    if cancel:
        assert state['result']['failure_code'] == 'user_cancelled'
    assert durations == ([0.03] if cancel else [0.03, 0.03])
    starts = [e for e in state['trace'] if e['event'] == 'component_started']
    assert sum(e['role'] == 'task_workflow' for e in starts) == 1
    assert sum(e['role'] == 'step' for e in starts) == (1 if cancel else 2)
    assert window.backend.events == []
