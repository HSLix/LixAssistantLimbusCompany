"""覆盖调试匹配只读边界、资源增量检查、独立截图与 GUI 输入失效。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_template_match_lab.py
"""

import json
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import Qt

from lalc.assets import AssetLibrary
from lalc.application import StartError
from test_agent_repair import host_for
from test_assets import entry, pixels, screenshot, template
from test_developer_gui import gui, wait_jobs


def test_group_and_single_match_use_formal_rules_without_writes(tmp_path):
    host, _ = host_for(tmp_path)
    library = host.service.asset_library
    a = entry(host.service.data_root, 'ui/start')
    b = entry(host.service.data_root, 'ui/start', np.full((2, 2, 3), 200, dtype=np.uint8))
    library.path('ui/start/asset-tag.json').write_text(json.dumps({a['sha256']: ['en'], b['sha256']: ['other']}))
    snapshot = pixels(screenshot()), (12, 8), 4
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    group = host.match_template_preview(snapshot, 'ui/start', threshold=.999, priority_tags=['en'])
    single = host.match_template_preview(snapshot, 'ui/start', a['sha256'], threshold=.999)
    assert [(m['x'], m['y'], m['sha256']) for m in group] == [(2, 1, a['sha256']), (8, 5, a['sha256'])]
    assert [(m['x'], m['y']) for m in single] == [(2, 1), (8, 5)]
    assert single[0]['centerxy'] == (3, 2)
    fallback = host.match_template_preview(snapshot, 'ui/start', threshold=.999, priority_tags=['missing'])
    assert fallback == group
    assert host.match_template_preview(snapshot, 'ui/start', threshold=.999, priority_tags=['other']) == group
    region = {'x': 7, 'y': 4, 'width': 5, 'height': 4}
    assert len(host.match_template_preview(snapshot, 'ui/start', region=region, threshold=.999)) == 1
    assert host.match_template_preview(snapshot, 'ui/start', b['sha256'], threshold=.999) == []
    after = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    assert before == after
    # 正式入口的默认索引写入行为保持。
    library.match('ui/start', *snapshot[:2], run_id=1, observation=4, emit=lambda *_: None, threshold=.999)
    assert (host.service.data_root / 'asset-usage.json').exists()


def test_preview_validation_activity_and_hash_failure(tmp_path):
    host, _ = host_for(tmp_path)
    a = entry(host.service.data_root, 'ui/start')
    snapshot = pixels(screenshot()), (12, 8), 1
    with host.service.activity('Agent'):
        with pytest.raises(StartError):
            host.match_template_preview(snapshot, 'ui/start')
    for name, digest in [('../outside', a['sha256']), ('ui/start', '../outside')]:
        with pytest.raises(ValueError):
            host.template_preview(name, digest)
    host.service.asset_library.path(a['path']).write_bytes(b'changed')
    with pytest.raises(ValueError, match='hash mismatch'):
        host.match_template_preview(snapshot, 'ui/start', a['sha256'])
    assert host.service.state['activity'] is None


@pytest.mark.parametrize('single', [False, True])
def test_match_preview_passes_nms_options(tmp_path, single):
    host, _ = host_for(tmp_path)
    image = np.full((2, 3, 3), 150, dtype=np.uint8)
    a = entry(host.service.data_root, 'ui/flat', image[:, :2])
    snapshot = pixels(image), (3, 2), 1
    digest = a['sha256'] if single else None
    assert len(host.match_template_preview(snapshot, 'ui/flat', digest, nms_iou_threshold=.3)) == 1
    assert len(host.match_template_preview(snapshot, 'ui/flat', digest, nms=False)) == 2


def test_catalog_checks_metadata_without_reading_contents(tmp_path, monkeypatch):
    host, _ = host_for(tmp_path)
    assert host.template_catalog() == ((), [])
    a = entry(host.service.data_root, 'ui/start')
    monkeypatch.setattr(Path, 'read_bytes', lambda *_: pytest.fail('metadata scan must not read image bytes'))
    first = host.template_catalog()
    assert first[1] == [a['path']] and host.template_catalog() == first
    tags = host.service.asset_library.path('ui/start/asset-tag.json')
    tags.write_text('{}')
    second = host.template_catalog()
    assert second[0] != first[0]
    tags.write_text('{ }')
    assert host.template_catalog()[0] != second[0]
    host.service.asset_library.path(a['path']).unlink()
    assert host.template_catalog()[1] == []


def test_catalog_rejects_symlinks(tmp_path):
    host, _ = host_for(tmp_path)
    root = host.service.asset_library.root
    root.mkdir()
    (root / 'outside').symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match='符号链接'):
        host.template_catalog()


def test_gui_tree_unchanged_and_changed_on_reentry(gui, monkeypatch):
    app, window = gui
    page = window.template_match_page
    a = entry(window.service.data_root, 'ui/start')
    reads = []
    original = AssetLibrary.read
    def read(self, selected):
        reads.append(selected)
        return original(self, selected)
    monkeypatch.setattr(AssetLibrary, 'read', read)
    window.show()
    window.switchTo(page)
    app.processEvents()
    wait_jobs(app, window)
    assert not reads
    ui = page.tree.topLevelItem(0)
    group = ui.child(0)
    leaf = group.child(0)
    page.tree.setCurrentItem(leaf)
    wait_jobs(app, window)
    assert len(reads) == 1 and not page.preview.pixmap().isNull()
    ui.setExpanded(False)
    window.switchTo(window.capture_page)
    window.switchTo(page)
    app.processEvents()
    wait_jobs(app, window)
    assert page.tree.currentItem() is leaf and not ui.isExpanded() and len(reads) == 1
    tags = window.service.asset_library.path('ui/start/asset-tag.json')
    tags.write_text(json.dumps({a['sha256']: ['en']}))
    window.switchTo(window.capture_page)
    window.switchTo(page)
    app.processEvents()
    wait_jobs(app, window)
    assert page.tree.currentItem().data(0, Qt.ItemDataRole.UserRole) == ('ui/start', a['sha256'])
    assert not page.tree.topLevelItem(0).isExpanded() and len(reads) == 2
    window.service.asset_library.path(a['path']).unlink()
    page.refresh_pending = True
    page.refresh_assets()
    wait_jobs(app, window)
    assert page.selected_template() is None and page.preview.pixmap().isNull()


def test_gui_frozen_capture_parameters_results_and_failure(gui, monkeypatch):
    from lalc.gui import ErrorDialog
    app, window = gui
    page = window.template_match_page
    a = entry(window.service.data_root, 'ui/start')
    page.update_catalog(window.host.template_catalog())
    page.tree.setCurrentItem(page.tree.topLevelItem(0).child(0))
    assert page.tags.isEnabled()
    captures = []
    snapshot = pixels(screenshot()), (12, 8), 5
    def capture(self, *, update_preview):
        assert update_preview is False
        captures.append(True)
        return snapshot
    monkeypatch.setattr(type(window.host), 'capture', capture)
    original = window.host.preview = (bytes(16), (2, 2), 99)
    page.capture()
    wait_jobs(app, window)
    assert page.snapshot is snapshot and window.host.preview is original
    page.threshold.setValue(.999)
    page.run_button.click()
    assert not page.run_button.isEnabled() and not page.tree.isEnabled()
    wait_jobs(app, window)
    assert len(page.view.items) == 2 and a['path'] in page.results.toPlainText()
    page.view.region = {'x': 7, 'y': 4, 'width': 5, 'height': 4}
    page.view.selected.emit(page.view.region)
    assert not page.view.items and not page.results.toPlainText()
    page.run_button.click()
    wait_jobs(app, window)
    assert len(page.view.items) == 1 and page.view.items[0]['box']['x'] == 8
    page.full_button.click()
    assert page.view.region is None and not page.view.items
    page.run_button.click()
    wait_jobs(app, window)
    page.nms.setChecked(False)
    assert not page.iou.isEnabled() and not page.view.items
    assert len(captures) == 1
    assert not (window.service.data_root / 'asset-usage.json').exists()
    page.tree.setCurrentItem(page.tree.topLevelItem(0).child(0).child(0))
    wait_jobs(app, window)
    assert not page.tags.isEnabled()
    page.run_button.click()
    wait_jobs(app, window)
    assert len(page.view.items) == 2
    page.threshold.setValue(.998)
    assert not page.view.items and not page.results.toPlainText()
    errors = []
    monkeypatch.setattr(ErrorDialog, 'open', lambda dialog: errors.append(dialog.details.toPlainText()))
    window.service.asset_library.path(a['path']).write_bytes(b'broken')
    page.run_button.click()
    wait_jobs(app, window)
    assert errors and 'hash mismatch' in errors[-1]
    assert not page.view.items and not page.results.toPlainText() and page.run_button.isEnabled()
