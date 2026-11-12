"""覆盖单日志 ZIP 快照、隔离导入、安全检查及左侧记录分批加载。

从项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_run_log_sharing.py
"""

import json
import os
import stat
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from lalc.file_content import file_operation
from lalc.run_log_sharing import export_log, import_log, list_logs
from lalc.run_logs import read_page, snapshot
from test_run_logs import write_logs, log_page


def package(root, destination):
    path, _ = write_logs(root, 2)
    image = root / 'evidence/1/1.png'
    image.parent.mkdir(parents=True)
    Image.new('RGB', (20, 10)).save(image)
    with path.open('a') as stream:
        stream.write(json.dumps(dict(event='component_log', level='info', message='image',
                                    evidence_id='1/1', recorded_at='2026-11-06T12:00:02Z')) + '\n')
    boundary = snapshot(root, 1)
    with path.open('a') as stream:
        stream.write('{"message":"partial')
    export_log(root, 1, destination, boundary)
    return path


def test_roundtrip_snapshot_images_and_same_number(tmp_path):
    root = tmp_path / 'source'
    root.mkdir()
    archive = tmp_path / 'log.zip'
    package(root, archive)
    if os.name != 'nt':
        assert stat.S_IMODE(archive.stat().st_mode) == stat.S_IMODE((root / 'traces/1.jsonl').stat().st_mode)
    target = tmp_path / 'target'
    target.mkdir()
    write_logs(target, 1)
    first, second = import_log(target, archive), import_log(target, archive)
    assert first != second
    entries = list_logs(target)
    assert len(entries) == 3
    assert sum(entry['imported'] for entry in entries) == 2
    assert all(entry['run_id'] == 1 for entry in entries)
    assert not (target / 'run-sequence.json').exists()
    entry = next(entry for entry in entries if entry['key'] == first)
    rows = read_page(entry['root'], 1, snapshot(entry['root'], 1))['rows']
    assert len(rows) == 3
    assert rows[0]['image'].is_file()
    assert entry['started_at'] == '2026-11-06T12:00:00Z'
    export_log(entry['root'], 1, tmp_path / 'again.zip')
    assert len(list(zipfile.ZipFile(tmp_path / 'again.zip').namelist())) == 3


@pytest.mark.parametrize('problem', ['path', 'hash', 'duplicate', 'size', 'extra', 'format'])
def test_bad_archive_never_commits(tmp_path, problem):
    root = tmp_path / 'source'
    root.mkdir()
    original = tmp_path / 'original.zip'
    package(root, original)
    with zipfile.ZipFile(original) as archive:
        contents = {name: archive.read(name) for name in archive.namelist()}
    metadata = json.loads(contents['run.json'])
    if problem == 'path':
        metadata['files']['../escape'] = metadata['files'].pop('traces/1.jsonl')
        contents['../escape'] = contents.pop('traces/1.jsonl')
    elif problem == 'hash':
        metadata['files']['traces/1.jsonl']['sha256'] = '0' * 64
    elif problem == 'size':
        metadata['files']['traces/1.jsonl']['size'] += 1
    elif problem == 'extra':
        contents['extra'] = b'bad'
    elif problem == 'format':
        metadata['format'] = 'other'
    contents['run.json'] = json.dumps(metadata).encode()
    bad = tmp_path / 'bad.zip'
    with zipfile.ZipFile(bad, 'w') as archive:
        for name, content in contents.items():
            archive.writestr(name, content)
        if problem == 'duplicate':
            with pytest.warns(UserWarning):
                archive.writestr('run.json', contents['run.json'])
    target = tmp_path / 'target'
    with pytest.raises(ValueError):
        import_log(target, bad)
    assert not list((target / 'imported-run-logs').glob('*'))
    assert not (tmp_path / 'escape').exists()


def test_cancelled_import_and_export_clean_up(tmp_path):
    root = tmp_path / 'source'
    root.mkdir()
    archive = tmp_path / 'log.zip'
    package(root, archive)
    for operation in (lambda: import_log(tmp_path / 'target', archive),
                      lambda: export_log(root, 1, tmp_path / 'cancelled.zip')):
        with file_operation(lambda: True):
            with pytest.raises(InterruptedError):
                operation()
    assert not list((tmp_path / 'target/imported-run-logs').glob('*'))
    assert not (tmp_path / 'cancelled.zip').exists()


def test_gui_local_and_imported_same_number_are_separate(log_page, tmp_path):
    from PySide6.QtCore import Qt
    app, page, path, until = log_page
    archive = tmp_path / 'log.zip'
    export_log(tmp_path, 1, archive)
    key = import_log(tmp_path, archive)
    page.refresh_runs()
    until(lambda: page.runs.count() == 2)
    imported = next(page.runs.item(i) for i in range(2)
                    if page.runs.item(i).data(Qt.ItemDataRole.UserRole) == key)
    page.select_run(imported)
    until(lambda: not page.loading and bool(page.model.rows))
    assert page.read_root == tmp_path / 'imported-run-logs' / key
    assert page.run_id == 1
    assert 'Imported' in page.run_title.text()
    assert 'Log No.1' in imported.text()
    page.source_filter.setCurrentItem('local')
    page.select_source('local')
    until(lambda: page.runs.count() == 1 and page.selected_key == 1)
    assert page.read_root == tmp_path


def test_gui_export_then_import_without_review(log_page, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    import lalc.sharing_gui as sharing_gui
    app, page, path, until = log_page
    destination = tmp_path / 'saved.zip'
    order = []
    def task(parent, operation):
        order.append('progress')
        return operation()
    def save(*args):
        assert order == ['progress']
        order.append('save-dialog')
        return str(destination), 'ZIP'
    monkeypatch.setattr(sharing_gui, 'sharing_task', task)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', save)
    page.export_zip()
    assert destination.is_file()
    assert order == ['progress', 'save-dialog', 'progress']
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(destination), 'ZIP'))
    confirmations = []
    monkeypatch.setattr(QMessageBox, 'information', lambda *args: confirmations.append(args))
    page.import_zip()
    until(lambda: page.runs.count() == 2)
    assert len(confirmations) == 1
    assert len(list_logs(tmp_path)) == 2


def test_gui_run_list_loads_ten_at_a_time_and_resets_source(log_page, tmp_path):
    from PySide6.QtCore import Qt
    app, page, path, until = log_page
    archive = tmp_path / 'log.zip'
    # 导入副本早于后续 Run，避免同一时间的 UUID 排序影响批次数量断言。
    path.write_text(path.read_text().replace('2026-11-06T', '2026-11-01T'))
    export_log(tmp_path, 1, archive)
    imported = import_log(tmp_path, archive)
    for identity in range(2, 26):
        (path.parent / f'{identity}.jsonl').write_text(json.dumps(dict(
            event='component_log', level='info', message=str(identity),
            recorded_at=f'2026-11-{identity:02}T12:00:00Z')) + '\n')
    page.refresh_runs()
    until(lambda: page.runs.count() == 10 and page.selected_key == 25 and not page.loading)
    keys = lambda: [page.runs.item(i).data(Qt.ItemDataRole.UserRole) for i in range(page.runs.count())]
    assert keys() == list(range(25, 15, -1))
    assert len(page.entries) == 10
    rows = page.model.rows
    bar = page.runs.verticalScrollBar()
    app.processEvents()
    previous_bottom = bar.maximum()
    bar.setValue(previous_bottom)
    until(lambda: page.runs.count() == 20)
    app.processEvents()
    assert bar.value() == previous_bottom
    assert keys() == list(range(25, 5, -1))
    assert page.selected_key == 25 and page.model.rows is rows
    app.processEvents()
    bar.setValue(bar.maximum())
    until(lambda: page.runs.count() == 26)
    assert len(set(keys())) == 26 and imported in keys()
    page.append_runs()
    assert page.runs.count() == 26
    page.select_run(page.runs.item(19))
    until(lambda: not page.loading)
    page.refresh_runs()
    until(lambda: page.runs.count() == 10 and page.selected_key == 25 and not page.loading)
    page.select_source('imported')
    until(lambda: page.runs.count() == 1 and page.selected_key == imported and not page.loading)
    page.select_source('local')
    until(lambda: page.runs.count() == 10 and page.selected_key == 25 and not page.loading)
    page.select_source('imported')
    page.select_source('local')
    until(lambda: not page.tasks)
    assert keys() == list(range(25, 15, -1))


def test_gui_run_list_without_scrollbar_accepts_wheel_and_keyboard(log_page, tmp_path):
    from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
    from PySide6.QtGui import QKeyEvent, QWheelEvent
    app, page, path, until = log_page
    for identity in range(2, 26):
        (path.parent / f'{identity}.jsonl').write_bytes(path.read_bytes())
    page.resize(1100, 2600)
    page.refresh_runs()
    until(lambda: page.runs.count() == 10 and not page.tasks)
    assert page.runs.verticalScrollBar().maximum() == 0
    wheel = QWheelEvent(QPointF(20, 20), QPointF(20, 20), QPoint(), QPoint(0, -120),
                        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                        Qt.ScrollPhase.NoScrollPhase, False)
    app.sendEvent(page.runs.viewport(), wheel)
    assert page.runs.count() == 20
    app.processEvents()
    assert page.runs.verticalScrollBar().maximum() == 0
    page.runs.setCurrentRow(19)
    app.sendEvent(page.runs, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier))
    assert page.runs.count() == 25
