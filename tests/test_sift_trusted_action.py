"""覆盖正式 SIFT 动作的接线、当前帧、来源／NMS、日志与权限及失败边界。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_sift_trusted_action.py
"""

import json

import cv2
import pytest

from lalc.application import ApplicationService
from lalc.manifest import ManifestManager
from runtime_support import add_plan
from test_assets import Window, entry, finish
from test_feature_matching import scene


@pytest.mark.parametrize('mode', ['normal', 'all', 'roi', 'direct', 'no_capture', 'invalid', 'corrupt', 'no_matches'])
def test_formal_sift_action(tmp_path, mode):
    """使用真实 OpenCV 和窗口替身，检验正式动作完整调用链。"""
    class SceneWindow(Window):
        def window_info(self, hwnd):
            return {**super().window_info(hwnd), 'width': 360, 'height': 230}

    window = SceneWindow()
    window.image, template = scene()
    first = entry(tmp_path, 'ui/symbol', template)
    entry(tmp_path, 'ui/symbol', cv2.convertScaleAbs(template, alpha=.95))
    if mode == 'no_matches':
        window.image.fill(0)
    if mode == 'corrupt':
        (tmp_path / 'assets' / first['path']).write_bytes(b'broken')
    candidate = tmp_path / 'candidate'
    candidate.mkdir()
    capture = '' if mode == 'no_capture' else '    ctx.action("observe.capture_screen")\n'
    call = 'ctx.match_feature("ui/symbol")' if mode == 'direct' else 'ctx.action("observe.match_feature", asset="ui/symbol"'
    if mode != 'direct':
        call += {
            'all': ', nms=False',
            'invalid': ', min_inlier_ratio=0',
            'roi': ', region={"x":210,"y":110,"width":130,"height":110}',
        }.get(mode, '') + ')'
    (candidate / 'step.py').write_text(
        '"""正式 SIFT 观察。"""\nfrom lalc import step\n@step\ndef execute(ctx) -> str:\n'
        + capture + f'    return str(len({call}))\n', encoding='utf-8')
    path = candidate / 'manifest.json'
    path.write_text(json.dumps({'schema_version': 2, 'components': {
        'steps.find': {'source_path': 'step.py'}}, 'recovery_rules': {}}), encoding='utf-8')
    add_plan(path)
    manager = ManifestManager(tmp_path)
    published = manager.publish(path)
    assert published.ok, published.errors
    service = ApplicationService(tmp_path, manifest_manager=manager, window_platform=window)
    state = finish(service, service.start('steps.find', {}, manifest_id=published.loaded.manifest_id))
    if mode in {'direct', 'no_capture', 'invalid', 'corrupt'}:
        assert state['result']['status'] == 'failure'
        expected = {'direct': 'requires an observe Trusted Action', 'no_capture': 'No current screenshot',
                    'invalid': 'min_inlier_ratio', 'corrupt': 'hash mismatch'}[mode]
        assert expected in state['result']['traceback']
        assert not (tmp_path / 'asset-usage.json').exists()
        return
    assert state['result']['output'] == {'normal': '2', 'all': '4', 'roi': '1', 'no_matches': '0'}[mode]
    assert window.captures == 1
    event = next(e for e in state['trace'] if e['event'] == 'asset_matched')
    assert event['method'] == 'sift' and len(event['templates']) == 2
    assert event['nms_iou_threshold'] == .4 and event['feature_options']['min_inlier_ratio'] == .4
    assert len(event['detections']) == int(state['result']['output'])
    if mode == 'no_matches':
        assert not (tmp_path / 'asset-usage.json').exists()
        return
    result = event['detections'][0]
    assert result['score'] == result['inliers'] and result['inlier_ratio'] >= .4
    assert result['logical_name'] == 'ui/symbol' and result['tags'] == []
    assert result['observation'] == event['observation']
    assert set(result['normalized_region']) == {'x', 'y', 'width', 'height'}
    stored = json.loads((tmp_path / 'asset-usage.json').read_text(encoding='utf-8'))['ui/symbol']
    assert stored['detections'] == json.loads(json.dumps(event['detections']))
    actions = [e for e in state['trace'] if e.get('logical_name') == 'observe.match_feature'
               and e['event'] == 'trusted_action_returned']
    assert len(actions) == 1 and actions[0]['return_value']
    assert 'debug_image' not in actions[0]
    from lalc.image_annotations import action_annotations
    from lalc.run_logs import log_text
    assert len(action_annotations(actions[0])) == len(event['detections'])
    assert '#1: score=' in log_text(actions[0])
    assert not any(e['event'] == 'screenshot_saved' for e in state['trace'])
