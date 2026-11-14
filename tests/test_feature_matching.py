"""覆盖 SIFT 多实例、原图坐标、参数校验、只读后台与识别页状态。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_feature_matching.py
"""

import cv2
import numpy as np
import pytest

from lalc.feature_matching import detect_features, prepare_image
from test_agent_repair import host_for
from test_assets import entry, pixels
from test_developer_gui import gui, wait_jobs


def scene():
    """两处完全相同的纹理可暴露模板向截图配对导致的重复目标丢失。"""
    rng = np.random.default_rng(42)
    template = cv2.GaussianBlur(rng.integers(0, 256, (70, 80, 3), dtype=np.uint8), (3, 3), 0)
    image = np.full((230, 360, 3), 40, np.uint8)
    image[20:90, 25:105] = template
    image[130:200, 240:320] = template
    return image, template


@pytest.mark.parametrize('scale', [1, 3, 5])
def test_repeated_targets_and_original_coordinates_without_mutation(scale):
    image, template = scene()
    before = image.copy(), template.copy()
    results = detect_features(image, template, scale=scale)
    assert len(results) == 2
    assert [m['score'] for m in results] == sorted([m['score'] for m in results], reverse=True)
    for result, center in zip(sorted(results, key=lambda m: m['x']), [(65, 55), (280, 165)]):
        assert np.linalg.norm(np.array(result['centerxy']) - center) < 3
        assert result['score'] >= 6 and .5 <= result['inlier_ratio'] <= 1
        assert result['inlier_ratio'] == result['inliers'] / result['good_matches']
    assert np.array_equal(image, before[0]) and np.array_equal(template, before[1])
    assert detect_features(image, template, scale=scale) == results


def test_roi_scaling_and_no_features_or_unrelated_image():
    image, template = scene()
    roi = dict(x=210, y=110, width=130, height=110)
    result = detect_features(image, template, region=roi)
    assert len(result) == 1 and np.linalg.norm(np.array(result[0]['centerxy']) - (280, 165)) < 3
    assert detect_features(image, np.zeros_like(template)) == []
    assert detect_features(np.zeros_like(image), template) == []
    unrelated = np.random.default_rng(93).integers(0, 256, image.shape, dtype=np.uint8)
    assert detect_features(unrelated, template) == []
    assert detect_features(image, template, min_inliers=10000) == []


def test_geometric_transform():
    _, template = scene()
    matrix = np.float32([[1.1, .12, 90], [.05, 1.05, 60], [.0003, .0002, 1]])
    image = cv2.warpPerspective(template, matrix, (300, 220), borderValue=(40, 40, 40))
    result = detect_features(image, template)
    assert len(result) == 1
    assert 85 <= result[0]['x'] <= 95 and 55 <= result[0]['y'] <= 65
    assert result[0]['width'] > 80 and result[0]['height'] > 60


def test_multiple_scales_in_dense_background():
    """密集背景中的两个缩放实例应分别计分，不把对方配对计入分母。"""
    _, template = scene()
    image = np.random.default_rng(102).integers(0, 256, (330, 530, 3), dtype=np.uint8)
    image[20:90, 30:110] = template
    enlarged = cv2.resize(template, None, fx=1.3, fy=1.3)
    h, w = enlarged.shape[:2]
    image[170:170 + h, 340:340 + w] = enlarged
    results = sorted(detect_features(image, template), key=lambda m: m['x'])
    assert len(results) == 2
    for result, center in zip(results, [(70, 55), (392, 215)]):
        assert np.linalg.norm(np.array(result['centerxy']) - center) < 3
        assert result['inlier_ratio'] > .9


@pytest.mark.parametrize('options', [dict(scale=True), dict(scale=6), dict(nfeatures=-1),
    dict(n_octave_layers=0), dict(min_inliers=3), dict(pair_ratio=1), dict(pair_ratio=float('nan')),
    dict(min_inlier_ratio=0), dict(sigma=0), dict(ransac_threshold=float('inf')), dict(clahe=1),
    dict(region=dict(x=-1, y=0, width=5, height=5))])
def test_invalid_parameters(options):
    image, template = scene()
    with pytest.raises(ValueError):
        detect_features(image, template, **options)


@pytest.mark.parametrize('grayscale,clahe', [(True, True), (True, False), (False, True), (False, False)])
def test_preprocessing_is_repeatable_and_does_not_modify_input(grayscale, clahe):
    _, template = scene()
    before = template.copy()
    first = prepare_image(template, grayscale=grayscale, clahe=clahe)
    assert first.shape == (210, 240) and first.dtype == np.uint8
    assert np.array_equal(first, prepare_image(template, grayscale=grayscale, clahe=clahe))
    assert np.array_equal(template, before) and not np.shares_memory(first, template)


def test_host_all_templates_sorting_nms_readonly_and_validation(tmp_path):
    from lalc.application import StartError
    host, _ = host_for(tmp_path)
    image, template = scene()
    a = entry(host.service.data_root, 'ui/symbol', template)
    b = entry(host.service.data_root, 'ui/symbol', cv2.convertScaleAbs(template, alpha=.95))
    snapshot = pixels(image), (360, 230), 1
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    all_results = host.match_feature_preview(snapshot, 'ui/symbol', nms=False)
    assert len(all_results) == 4 and {m['sha256'] for m in all_results} == {a['sha256'], b['sha256']}
    assert [m['score'] for m in all_results] == sorted([m['score'] for m in all_results], reverse=True)
    assert len(host.match_feature_preview(snapshot, 'ui/symbol')) == 2
    assert len(host.match_feature_preview(snapshot, 'ui/symbol', a['sha256'])) == 2
    assert before == {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    with host.service.activity('Run'):
        with pytest.raises(StartError):
            host.match_feature_preview(snapshot, 'ui/symbol')
    for name, digest in [('../outside', a['sha256']), ('ui/symbol', '../outside')]:
        with pytest.raises(ValueError):
            host.match_feature_preview(snapshot, name, digest)
    host.service.asset_library.path(a['path']).write_bytes(b'broken')
    with pytest.raises(ValueError, match='hash mismatch'):
        host.match_feature_preview(snapshot, 'ui/symbol', a['sha256'])


def test_gui_feature_state_parameters_capture_and_errors(gui, monkeypatch):
    from copy import deepcopy
    from lalc.gui import ErrorDialog
    app, window = gui
    page = window.recognition_page
    image, template = scene()
    a = entry(window.service.data_root, 'ui/symbol', template)
    page.update_catalog(window.host.template_catalog())
    page.tree.setCurrentItem(page.tree.topLevelItem(0).child(0))
    snapshot = pixels(image), (360, 230), 4
    monkeypatch.setattr(type(window.host), 'capture', lambda *_, **__: snapshot)
    calls = []
    original = type(window.host).match_feature_preview
    def run(self, frame, *args, **options):
        assert frame is snapshot
        calls.append(options)
        return original(self, frame, *args, **options)
    monkeypatch.setattr(type(window.host), 'match_feature_preview', run)
    page.capture()
    wait_jobs(app, window)
    page.methods.setCurrentItem('feature')
    wait_jobs(app, window)
    assert not calls and not page.view.items
    assert page.feature_controls['scale'].value() == 3
    page.full_button.click()
    assert not page.methods.isEnabled()
    assert all(not control.isEnabled() for control in page.feature_controls.values())
    wait_jobs(app, window)
    assert len(page.view.items) == 2 and a['path'] in page.results.toPlainText()
    assert calls[-1]['min_inliers'] == 6 and calls[-1]['min_inlier_ratio'] == .5
    roi = dict(x=210, y=110, width=130, height=110)
    page.view.region = roi
    page.view.selected.emit(roi)
    wait_jobs(app, window)
    assert len(page.view.items) == 1 and calls[-1]['region'] == roi
    text = page.results.toPlainText()
    image_key = page.view.image.cacheKey()
    page.methods.setCurrentItem('template')
    wait_jobs(app, window)
    page.threshold.setValue(.95)
    page.methods.setCurrentItem('ocr')
    page.methods.setCurrentItem('feature')
    wait_jobs(app, window)
    assert page.view.region == roi and page.results.toPlainText() == text
    assert page.view.image.cacheKey() == image_key and len(calls) == 2
    page.feature_controls['min_inliers'].setValue(7)
    assert not page.view.items and not page.results.toPlainText() and len(calls) == 2
    page.run_button.click()
    wait_jobs(app, window)
    assert len(page.view.items) == 1 and calls[-1]['min_inliers'] == 7
    page.feature_controls['nms'].setChecked(False)
    assert not page.feature_controls['nms_iou_threshold'].isEnabled()
    page.run_button.click()
    wait_jobs(app, window)
    before = deepcopy(page.states)
    errors = []
    monkeypatch.setattr(ErrorDialog, 'open', lambda dialog: errors.append(dialog.details.toPlainText()))
    def fail(*_, **__):
        raise RuntimeError('capture failed')
    monkeypatch.setattr(type(window.host), 'capture', fail)
    page.capture()
    wait_jobs(app, window)
    assert errors and page.states == before and page.snapshot is snapshot
    window.service.asset_library.path(a['path']).write_bytes(b'broken')
    page.run_button.click()
    wait_jobs(app, window)
    assert 'hash mismatch' in errors[-1] and not page.view.items and page.view.region == roi
    monkeypatch.setattr(type(window.host), 'capture', lambda *_, **__: snapshot)
    page.capture()
    wait_jobs(app, window)
    assert all(state == dict(region=None, items=[], text='') for state in page.states.values())
    assert page.feature_controls['min_inliers'].value() == 7


def test_asset_change_invalidates_both_matching_modes_only(gui):
    app, window = gui
    page = window.recognition_page
    _, template = scene()
    a = entry(window.service.data_root, 'ui/symbol', template)
    page.update_catalog(window.host.template_catalog())
    for method in ('template', 'feature', 'ocr'):
        page.states[method]['text'] = method
    page.methods.setCurrentItem('ocr')
    window.service.asset_library.path(a['path']).unlink()
    page.update_catalog(window.host.template_catalog())
    assert page.states['template']['text'] == page.states['feature']['text'] == ''
    assert page.results.toPlainText() == 'ocr'
