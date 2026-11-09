"""覆盖直接导出、四 Tab 红点、Asset 冲突、可选页面 Review 和统一提交。

项目根目录运行：QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_sharing_gui.py
"""

from types import SimpleNamespace
import os
import stat

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QMessageBox

from lalc.application import ApplicationService
from lalc.i18n import install_translations
from lalc.manifest import ManifestManager
from lalc.sharing import SharingPackage, build_export, catalog, save_package, sharing_activity
from lalc.sharing_gui import ExportDialog, ImportDialog, tree_items
from test_page_drafts import SOURCE
from test_sharing import source, put_asset, png
from test_user_pages import app


@pytest.fixture
def window(tmp_path, app):
    install_translations(app, "en_US")
    widget = QWidget()
    widget.service = ApplicationService(tmp_path / "target")
    widget.host = SimpleNamespace(manager=widget.service.manifest_manager)
    widget.jobs, widget.closing = [], False
    widget.clean_details = lambda text: text
    yield widget
    widget.service.shutdown()
    widget.close()
    app.processEvents()


def make_package(source, tmp_path, *, pages_only=False, valid_page=False):
    manager, _ = source
    objects = build_export(manager, {"pages": ["sample.py"]} if pages_only else catalog(manager))
    if valid_page:
        next(obj for obj in objects if obj["kind"] == "pages")["files"]["page.py"] = SOURCE.encode()
    path = tmp_path / "shared.zip"
    save_package(objects, path)
    return SharingPackage(path)


def visit_all(dialog):
    for kind in ("workflow", "assets", "pages", "history"):
        dialog.tabs.setCurrentItem(kind)
    dialog.trust.setChecked(True)


def test_export_defaults_and_direct_save(window, source, tmp_path, monkeypatch):
    window.host.manager = source[0]
    dialog = ExportDialog(window)
    try:
        selected = dialog.selection()
        assert set(selected["assets"]) == {"ui", "ui/child"}
        assert not selected["history"] and not selected["pages"]
        assert not hasattr(dialog, "review")
        path = tmp_path / "export.zip"
        monkeypatch.setattr("lalc.sharing_gui.QFileDialog.getSaveFileName", lambda *args: (str(path), "ZIP"))
        dialog.advance()
        if os.name != 'nt':
            sibling = tmp_path / "ordinary-file"
            sibling.write_bytes(b"ordinary")
            assert stat.S_IMODE(path.stat().st_mode) == stat.S_IMODE(sibling.stat().st_mode)
        package = SharingPackage(path)
        try:
            assert len(package.objects) == 2
        finally:
            package.close()
    finally:
        dialog.close()



def test_export_cancel_does_not_prepare_snapshot(window, source, monkeypatch):
    window.host.manager = source[0]
    dialog = ExportDialog(window)
    monkeypatch.setattr("lalc.sharing_gui.QFileDialog.getSaveFileName", lambda *args: ("", ""))
    def unexpected(*args):
        pytest.fail("取消保存不应准备快照")
    monkeypatch.setattr("lalc.sharing_gui.build_export", unexpected)
    dialog.advance()
    assert dialog.result() == 0
    dialog.close()

def test_tabs_view_state_asset_conflicts_and_recheck_are_independent(window, source, tmp_path):
    put_asset(window.service.data_root, "ui", png("yellow"))
    package = make_package(source, tmp_path)
    dialog = ImportDialog(window, package)
    try:
        assert dialog.viewed == {"workflow"}
        assert not dialog.tabs.items["workflow"].text().endswith("🔴")
        assert dialog.tabs.items["history"].text().endswith("🔴")
        dialog.trust.setChecked(True)
        assert not dialog.commit.isEnabled()
        visit_all(dialog)
        assert not dialog.commit.isEnabled()
        dialog.set_kind_selected("assets", False)
        assert dialog.commit.isEnabled()
        dialog.set_kind_selected("assets", True)
        assert not dialog.commit.isEnabled()
        dialog.asset_action("skip")
        assert dialog.commit.isEnabled()
        assert not dialog.reviewed
        leaf = next(item for item in tree_items(dialog.assets) if item.data(0, 256) == "ui")
        dialog.assets.setCurrentItem(leaf)
        assert not dialog.asset_more.isChecked()
        assert "changed files" in dialog.asset_summary.text()
        viewed = set(dialog.viewed)
        dialog.recheck()
        assert dialog.viewed == viewed and dialog.asset_actions
        put_asset(window.service.data_root, "ui", png("purple"))
        dialog.recheck()
        assert not dialog.asset_actions and not dialog.commit.isEnabled()
    finally:
        dialog.close()
        package.close()


def test_unreviewed_confirmation_cancel_then_explicit_install(window, source, tmp_path, monkeypatch):
    package = make_package(source, tmp_path, pages_only=True)
    dialog = ImportDialog(window, package)
    prompts = []
    try:
        dialog.trust.setChecked(True)
        assert dialog.commit.isEnabled() and not dialog.reviewed
        def decline(parent, title, message, *args):
            prompts.append(message)
            return QMessageBox.StandardButton.No
        monkeypatch.setattr(QMessageBox, "question", decline)
        dialog.submit()
        assert "sample.py" in prompts[0]
        assert not (window.service.data_root / "pages").exists()
        monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
        monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
        dialog.submit()
        assert dialog.result_data["failed"] is None
        assert (window.service.data_root / "pages/sample/page.py").exists()
        assert not source[1].exists()
    finally:
        dialog.close()
        package.close()


def test_review_approval_does_not_install_until_import_selected(window, source, tmp_path, monkeypatch, app):
    package = make_package(source, tmp_path, pages_only=True, valid_page=True)
    dialog = ImportDialog(window, package)
    try:
        def approve(preview):
            preview.show()
            app.processEvents()
            preview.install_button.click()
            app.processEvents()
            return 0
        monkeypatch.setattr("lalc.page_preview.PagePreviewDialog.exec", approve)
        monkeypatch.setattr("lalc.developer_session.DeveloperSession.__init__", lambda *args, **kwargs: pytest.fail("Sharing 不应创建 Session"))
        dialog.open_page_review()
        assert dialog.reviewed and not (window.service.data_root / "pages").exists()
        dialog.trust.setChecked(True)
        monkeypatch.setattr(QMessageBox, "question", lambda *args: pytest.fail("已 Review 页面不应提示未 Review"))
        monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
        dialog.submit()
        assert dialog.result_data["failed"] is None
        assert (window.service.data_root / "pages/sample/page.py").read_text() == SOURCE
    finally:
        dialog.close()
        package.close()


def test_sharing_activity_blocks_runs_and_competing_activities(window):
    with sharing_activity(window.service):
        assert window.service.state["activity"] == "Sharing"
        with pytest.raises(Exception, match="活动"):
            with window.service.activity("Agent"):
                pytest.fail("不应取得第二个活动")
    assert window.service.state["activity"] is None


def test_failed_review_blocks_submit_and_is_not_treated_as_unreviewed(window, source, tmp_path, app):
    package = make_package(source, tmp_path, pages_only=True)
    dialog = ImportDialog(window, package)
    try:
        dialog.trust.setChecked(True)
        assert dialog.commit.isEnabled()
        dialog.open_page_review()
        app.processEvents()
        assert dialog.review_failed and not dialog.reviewed
        assert not dialog.commit.isEnabled()
        assert not (window.service.data_root / "pages").exists()
        dialog.recheck()
        assert not dialog.commit.isEnabled()
    finally:
        dialog.close()
        package.close()


def test_uuid_conflict_popup_names_original_and_confirmed_new_uuid(window, source, tmp_path, monkeypatch):
    manager, _ = source
    identity = catalog(manager)["workflow"][0]
    path = tmp_path / "workflow.zip"
    save_package(build_export(manager, {"workflow": [identity]}), path)
    package = SharingPackage(path)
    window.host.manager = manager
    dialog = ImportDialog(window, package)
    prompts = []
    try:
        new_id = dialog.checks[0]["manifest_id"]
        dialog.trust.setChecked(True)
        def decline(parent, title, text, *args):
            prompts.append(text)
            return QMessageBox.StandardButton.No
        monkeypatch.setattr(QMessageBox, "question", decline)
        dialog.submit()
        assert identity in prompts[0] and new_id in prompts[0]
        assert not (manager.manifests_dir / f"{new_id}.json").exists()
        monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
        monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
        dialog.submit()
        assert dialog.result_data["completed"][0]["manifest_id"] == new_id
        assert (manager.manifests_dir / f"{identity}.json").exists()
    finally:
        dialog.close()
        package.close()


def test_progress_worker_keeps_gui_responsive_across_repeated_hidden_parent_tasks(window, app):
    import time
    from PySide6.QtCore import QTimer
    from lalc.sharing_gui import sharing_task
    from lalc.file_content import checkpoint
    events = []
    timer = QTimer()
    timer.timeout.connect(lambda: events.append(True))
    timer.start(2)
    previous = app.quitOnLastWindowClosed()
    app.setQuitOnLastWindowClosed(True)
    try:
        for expected in range(3):
            def work():
                until = time.monotonic() + .03
                while time.monotonic() < until:
                    checkpoint()
                    time.sleep(.001)
                return expected
            assert sharing_task(window, work) == expected
        assert events and app.quitOnLastWindowClosed()
    finally:
        timer.stop()
        app.setQuitOnLastWindowClosed(previous)


def test_progress_cancel_waits_for_worker_checkpoint(window, app):
    import time
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from lalc.sharing_gui import sharing_task
    from lalc.file_content import checkpoint
    stopped = []
    def work():
        try:
            until = time.monotonic() + 2
            while time.monotonic() < until:
                checkpoint()
                time.sleep(.001)
        finally:
            stopped.append(True)
    QTimer.singleShot(10, lambda: QApplication.activeModalWidget().reject())
    with pytest.raises(InterruptedError):
        sharing_task(window, work)
    assert stopped


def test_unknown_disk_space_requires_explicit_continuation(window, monkeypatch):
    from lalc.file_content import require_disk
    from lalc.sharing_gui import sharing_task
    def unavailable(path):
        raise OSError("unknown disk")
    monkeypatch.setattr("lalc.file_content.shutil.disk_usage", unavailable)
    asked = []
    monkeypatch.setattr(QMessageBox, "question", lambda *args: asked.append(args[2]) or QMessageBox.StandardButton.Yes)
    assert sharing_task(window, lambda: require_disk([(window.service.data_root, 1)])) is None
    assert asked and window.allow_unknown_space


def test_skill_import_defaults_and_asset_tree_depth(window, source, tmp_path):
    from lalc.sharing_gui import asset_tree
    manager, _ = source
    folder = manager.data_root / 'skills/custom'
    folder.mkdir(parents=True)
    (folder / 'SKILL.md').write_text('guidance')
    path = tmp_path / 'skill.zip'
    save_package(build_export(manager, {'skills': ['custom']}), path)
    package = SharingPackage(path)
    dialog = ImportDialog(window, package)
    try:
        assert not dialog.selected
        dialog.trust.setChecked(True)
        dialog.set_kind_selected('skills', True)
        assert dialog.commit.isEnabled()
        assert dialog.skills.item(0).checkState().value == 2
    finally:
        dialog.close()
        package.close()
    tree = asset_tree(['ui', 'ui/child', 'ui/child/deep'])
    try:
        items = list(tree_items(tree))
        assert [item.text(0) for item in items] == ['ui', 'child', 'deep']
        assert items[0].isExpanded() and not items[1].isExpanded()
        items[0].setCheckState(0, Qt.CheckState.Unchecked)
        assert all(item.checkState(0).value == 0 for item in items)
    finally:
        tree.close()
