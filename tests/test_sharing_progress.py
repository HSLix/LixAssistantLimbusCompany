"""覆盖分享整体文件计数、单文件进度、提交失败和双进度窗口。

项目根目录运行：QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_sharing_progress.py
"""

from io import BytesIO
from pathlib import Path
from threading import Event

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QProgressBar, QLabel
from qfluentwidgets import BodyLabel

from lalc.file_content import copy_content, file_operation, file_transfers, checkpoint
from lalc.manifest import ManifestManager
from lalc.sharing import SharingPackage, build_export, catalog, import_selected, inspect_objects, save_package
from lalc.sharing_gui import sharing_task
from test_sharing import source
from test_sharing_gui import window
from test_user_pages import app


def payload():
    return [{"kind": "pages", "id": "sample.py", "files": {
        "page.py": b'PAGE_ID="sample"\nPAGE_NAME="Sample"',
        "empty.txt": b"", "large.bin": b"x" * (3 * 1024 * 1024)}}]


def test_zip_overall_files_and_current_file_bytes(tmp_path):
    path = tmp_path / "share.zip"
    events, committed = [], []
    def record(value):
        events.append(value)
        if value.finished:
            committed.append(path.is_file())
    with file_operation(details=record):
        save_package(payload(), path)
    assert committed == [True]
    assert events[-1].total == events[-1].completed == 3
    assert [event.completed for event in events] == sorted(event.completed for event in events)
    large = [event for event in events if event.name.endswith("large.bin")]
    assert any(0 < event.done < event.size for event in large)
    assert any(event.file_finished and event.done == event.size for event in large)
    assert any(event.name.endswith("empty.txt") and event.file_finished for event in events)
    extracted = []
    with file_operation(details=extracted.append):
        package = SharingPackage(path)
    try:
        assert extracted[-1].finished
        assert extracted[-1].total == extracted[-1].completed == 3
        assert any(event.name.endswith("large.bin") and 0 < event.done < event.size for event in extracted)
    finally:
        package.close()


@pytest.mark.parametrize("failure", ["write", "commit", "cancel"])
def test_export_failure_does_not_report_completion_or_replace_old_zip(tmp_path, monkeypatch, failure):
    path = tmp_path / "share.zip"
    path.write_bytes(b"old ZIP")
    events = []
    if failure == "write":
        def broken(*args, **kwargs):
            raise OSError("write failed")
        monkeypatch.setattr("lalc.sharing.copy_content", broken)
    elif failure == "commit":
        def broken(*args, **kwargs):
            raise OSError("commit failed")
        monkeypatch.setattr(Path, "replace", broken)
    with file_operation(lambda: failure == "cancel", details=events.append):
        with pytest.raises((OSError, InterruptedError)):
            save_package(payload(), path)
    assert path.read_bytes() == b"old ZIP"
    assert not any(event.finished for event in events)
    assert not list(tmp_path.glob(".sharing-*"))


def test_install_all_kinds_counts_only_successful_objects(source, tmp_path):
    manager, _ = source
    skill = manager.data_root / "skills/example"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_bytes(b"guidance")
    path = tmp_path / "share.zip"
    save_package(build_export(manager, catalog(manager)), path)
    target = ManifestManager(tmp_path / "target")
    package = SharingPackage(path)
    try:
        checks = inspect_objects(target, package)
        events = []
        with file_operation(details=events.append):
            result = import_selected(target, package, checks, set(checks), asset_actions={},
                                     reviewed={}, allow_unreviewed=True)
        assert result["failed"] is None
        assert events[-1].finished
        assert events[-1].completed == events[-1].total == sum(len(obj["files"]) for obj in package.objects)
        assert [event.completed for event in events] == sorted(event.completed for event in events)
        for kind in ("workflow", "assets", "pages", "history", "skills"):
            assert any(event.name.startswith(kind + "/") and event.file_finished for event in events), kind
        # 相同对象重入时，跳过仍推进整体计数。
        checks = inspect_objects(target, package)
        selected = {obj["number"] for obj in package.objects if obj["kind"] in {"assets", "skills"}}
        events.clear()
        with file_operation(details=events.append):
            result = import_selected(target, package, checks, selected, asset_actions={}, reviewed={})
        assert result["failed"] is None
        assert all(item["status"] == "skipped" for item in result["completed"])
        assert events[-1].completed == events[-1].total and events[-1].finished
        assert any(event.phase == "Skipped" and event.file_finished for event in events)
    finally:
        package.close()


def test_install_failure_does_not_count_staged_files(tmp_path, monkeypatch):
    path = tmp_path / "share.zip"
    save_package(payload(), path)
    target = ManifestManager(tmp_path / "target")
    package = SharingPackage(path)
    try:
        checks = inspect_objects(target, package)
        from lalc.page_packages import _write_snapshot
        def fail_after_copy(snapshot, directory):
            _write_snapshot(snapshot, directory)
            raise OSError("installation failed")
        monkeypatch.setattr("lalc.page_packages._write_snapshot", fail_after_copy)
        events = []
        with file_operation(details=events.append):
            result = import_selected(target, package, checks, {0}, asset_actions={}, reviewed={}, allow_unreviewed=True)
        assert result["failed"]
        assert any(event.file_finished for event in events)
        assert all(event.completed == 0 and not event.finished for event in events)
        assert not (target.data_root / "pages/sample").exists()
    finally:
        package.close()


@pytest.mark.parametrize("title", ["Export sharing package", "Import sharing package"])
def test_two_progress_bars_keep_filename_across_empty_checkpoints(window, app, title):
    release, ready = Event(), Event()
    observed = []
    def work():
        with file_transfers("Writing ZIP", 4) as progress:
            copy_content(b"data", BytesIO(), name="assets/ui/start.png")
            progress.complete()
            checkpoint()
            ready.set()
            if not release.wait(3):
                raise TimeoutError("GUI did not inspect progress")
            progress.update(completed=4, finished=True)
    def inspect():
        if not ready.is_set():
            return
        dialog = QApplication.activeModalWidget()
        if dialog is None or dialog.findChild(QProgressBar, "overallProgress").value() != 25:
            return
        observed.append((dialog.windowTitle(), dialog.findChild(QProgressBar, "currentFileProgress").value(),
                         dialog.findChild(BodyLabel, "currentFilename").text(),
                         dialog.findChild(BodyLabel, "fileCount").text()))
        release.set()
    timer = QTimer()
    timer.timeout.connect(inspect)
    timer.start(2)
    try:
        sharing_task(window, work, title=title)
    finally:
        release.set()
        timer.stop()
    assert observed
    assert observed[0] == (title, 100, "assets/ui/start.png", "Processed 1 / 4 files")


def test_detailed_progress_cancel_keeps_cancelling_text_until_cleanup(window, app):
    ready, resume, late, finish, cleaned = (Event() for _ in range(5))
    observed = []
    def work():
        try:
            with file_transfers("Writing ZIP", 2) as progress:
                ready.set()
                if not resume.wait(3):
                    raise TimeoutError("cancel was not requested")
                progress.update(phase="Finishing…", name="late.png")
                late.set()
                if not finish.wait(3):
                    raise TimeoutError("GUI did not inspect cancellation")
                checkpoint()
        finally:
            cleaned.set()
    def inspect():
        dialog = QApplication.activeModalWidget()
        if dialog is None:
            return
        if ready.is_set() and not resume.is_set():
            dialog.reject()
            resume.set()
        elif late.is_set():
            observed.append(dialog.findChild(QLabel, "transferPhase").text())
            finish.set()
    timer = QTimer()
    timer.timeout.connect(inspect)
    timer.start(2)
    try:
        with pytest.raises(InterruptedError):
            sharing_task(window, work)
    finally:
        resume.set()
        finish.set()
        timer.stop()
    assert cleaned.is_set() and observed
    assert all(text == "Cancelling…" for text in observed)
