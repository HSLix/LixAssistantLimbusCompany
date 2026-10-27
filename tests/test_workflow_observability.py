"""覆盖中心元组、互斥点击参数及正式 Run/Plan 的语义日志和已有截图证据。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_workflow_observability.py
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from lalc.actions import click
from lalc.application import ApplicationService
from lalc.assets import AssetLibrary
from lalc.manifest import ManifestManager
from lalc.runtime import InputValidationError, _bind_and_normalize
from test_assets import Window, entry, finish, matching


@pytest.mark.parametrize('arguments', [{'x': 4, 'y': 3}, {'centerxy': (4, 3)}])
def test_click_coordinates_share_checked_input_path(arguments):
    calls = []
    click(SimpleNamespace(control_input=lambda name, **values: calls.append((name, values))),
          **_bind_and_normalize(click, arguments))
    assert calls == [('click', {'x': 4, 'y': 3})]


@pytest.mark.parametrize('arguments', [
    {}, {'x': 1}, {'y': 1}, {'x': 1, 'y': 2, 'centerxy': (3, 4)},
    {'centerxy': (1,)}, {'centerxy': (1, 2, 3)}, {'centerxy': [1, 2]},
    {'centerxy': (True, 2)}, {'centerxy': (1.5, 2)},
])
def test_invalid_click_never_reaches_input(arguments):
    ctx = SimpleNamespace(control_input=lambda *_args, **_values: pytest.fail('invalid input injected'))
    with pytest.raises((ValueError, InputValidationError)):
        click(ctx, **_bind_and_normalize(click, arguments))


def test_matching_returns_integer_center_tuples(tmp_path):
    entry(tmp_path, 'ui/claim')
    found, _ = matching(AssetLibrary(tmp_path))
    assert found and all(type(d['centerxy']) is tuple for d in found)
    assert all(d['centerxy'] == (d['x'] + d['width'] // 2, d['y'] + d['height'] // 2) for d in found)
    local, _ = matching(AssetLibrary(tmp_path), region={'x': 7, 'y': 4, 'width': 5, 'height': 4})
    assert local[0]['centerxy'] == found[1]['centerxy']


def make_service(tmp_path, source):
    candidate = tmp_path / 'candidate'
    candidate.mkdir()
    (candidate / 'step.py').write_text('"""测试语义日志。"""\nfrom lalc import step, RunContext\n'
        '@step\ndef execute(ctx: RunContext) -> None:\n' + source)
    (candidate / 'task.py').write_text('"""测试日志所属任务。"""\nfrom lalc import task_workflow, RunContext\n'
        '@task_workflow\ndef execute(ctx: RunContext) -> None:\n'
        '    ctx.log("开始选择 Drive")\n    ctx.call("steps.drive")\n')
    manifest = {'schema_version': 2, 'components': {
        'steps.drive': {'source_path': 'step.py'}, 'tasks.drive': {'source_path': 'task.py'}},
        'recovery_rules': {}}
    (candidate / 'manifest.json').write_text(json.dumps(manifest))
    from runtime_support import add_plan
    add_plan(candidate / 'manifest.json', '    ctx.call("tasks.drive")\n')
    manager = ManifestManager(tmp_path)
    published = manager.publish(candidate / 'manifest.json')
    assert published.ok, published.errors
    window = Window()
    return ApplicationService(tmp_path, manifest_manager=manager, window_platform=window), window, published.loaded.manifest_id


@pytest.mark.parametrize('plan', [False, True])
def test_logs_attach_same_screenshot_and_keep_call_identity(tmp_path, plan):
    service, window, manifest = make_service(tmp_path,
        '    ctx.action("observe.capture_screen")\n'
        '    ctx.log("已选中 Drive", screenshot=True)\n'
        '    ctx.log("无需点击", screenshot=True)\n')
    if plan:
        run = service.start_plan(manifest_id=manifest)
    else:
        run = service.start('tasks.drive', {}, manifest_id=manifest)
    state = finish(service, run)
    assert state['result']['status'] == ('completed' if plan else 'success')
    assert window.captures == 1
    logs = [event for event in state['trace'] if event['event'] == 'component_log']
    assert [event['message'] for event in logs] == ['开始选择 Drive', '已选中 Drive', '无需点击']
    assert 'evidence_path' not in logs[0]
    assert logs[1]['call_id'] == logs[2]['call_id'] != logs[0]['call_id']
    assert logs[1]['logical_name'] == 'steps.drive' and logs[0]['logical_name'] == 'tasks.drive'
    assert logs[1]['observation'] == 1 and logs[1]['evidence_path'] == logs[2]['evidence_path']
    assert Path(logs[1]['evidence_path']).is_file()
    from lalc.recognition import decode_image
    assert (decode_image(Path(logs[1]['evidence_path']).read_bytes()) == window.image).all()
    assert len(list((tmp_path / 'evidence' / str(run)).glob('*.png'))) == 1
    persisted = [json.loads(line) for line in (tmp_path / 'traces' / f'{run}.jsonl').read_text().splitlines()]
    assert [event for event in persisted if event['event'] == 'component_log'] == logs


def test_log_with_missing_screenshot_fails_without_capture(tmp_path):
    service, window, manifest = make_service(tmp_path, '    ctx.log("缺少图片", screenshot=True)\n')
    state = finish(service, service.start('steps.drive', {}, manifest_id=manifest))
    assert state['result']['status'] == 'failure'
    assert window.captures == 0
    assert 'No current screenshot' in state['result']['failure_message']
    assert not [event for event in state['trace'] if event['event'] == 'component_log']


def test_formal_match_center_passes_through_action_validation_as_tuple(tmp_path):
    service, window, manifest = make_service(tmp_path,
        '    ctx.action("observe.capture_screen")\n'
        '    matches = ctx.action("observe.match_asset", asset="ui/claim", threshold=0.999)\n'
        '    center = matches[0]["centerxy"]\n'
        '    if type(center) is not tuple:\n'
        '        raise ValueError("centerxy must remain a tuple")\n'
        '    ctx.action("control.click", centerxy=center)\n')
    entry(tmp_path, 'ui/claim')
    state = finish(service, service.start('steps.drive', {}, manifest_id=manifest))
    assert state['result']['status'] == 'success', state['result']
    matched = next(e for e in state['trace'] if e['event'] == 'asset_matched')
    assert type(matched['detections'][0]['centerxy']) is list
    clicked = next(e for e in state['trace'] if e['event'] == 'trusted_action_started' and e['logical_name'] == 'control.click')
    assert clicked['inputs']['centerxy'] == list(matched['detections'][0]['centerxy'])
