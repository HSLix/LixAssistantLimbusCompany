"""覆盖单日志 ZIP 快照、隔离导入、恶意路径及取消清理。

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
