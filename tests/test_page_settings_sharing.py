"""覆盖页面配置分享的独立选择、严格校验、冲突与旧界面保护。

项目根目录运行：QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_page_settings_sharing.py
"""

from contextlib import closing

import pytest

from lalc.manifest import ManifestManager
from lalc.sharing import (SharingPackage, build_export, catalog, import_selected,
                          inspect_objects, json_bytes, save_package)
from lalc.sharing_gui import ExportDialog, ImportDialog
from lalc.user_pages import UserSettings
from test_sharing_gui import window
from test_user_pages import app, owner


def package_at(tmp_path, config, identity="sample.page"):
    path = tmp_path / "settings.zip"
    save_package([{"kind": "page_settings", "id": identity,
                   "files": {"settings.json": json_bytes(config)}}], path)
    return SharingPackage(path)


def commit(manager, package, checks=None, action=None):
    return import_selected(manager, package, checks or inspect_objects(manager, package), {0},
                           asset_actions={0: action} if action else {}, reviewed={})


def test_export_only_saved_page_values_and_preserve_arbitrary_page_id(tmp_path):
    manager = ManifestManager(tmp_path / "source")
    store = UserSettings(manager.data_root)
    identity = "非路径:队伍/配置?"
    store.save("pages", identity, {"team": [1, 2]})
    store.save("pages", "unselected", {"secret": "excluded"})
    store.save_task("task", True, 9)
    assert catalog(manager)["page_settings"] == sorted([identity, "unselected"])
    archive = tmp_path / "export.zip"
    save_package(build_export(manager, {"page_settings": [identity]}), archive)
    with closing(SharingPackage(archive)) as package:
        assert [(obj["kind"], obj["id"]) for obj in package.objects] == [("page_settings", identity)]
        assert set(package.files(package.objects[0])) == {"settings.json"}
        target = ManifestManager(tmp_path / "target")
        assert commit(target, package)["failed"] is None
        assert UserSettings(target.data_root).value == {"pages": {identity: {"team": [1, 2]}}, "tasks": {}}


def test_conflict_requires_action_preserves_unselected_and_tasks(tmp_path):
    target = ManifestManager(tmp_path / "target")
    store = UserSettings(target.data_root)
    store.save("pages", "sample.page", {"old": 1, "removed": True})
    store.save("pages", "other", {"keep": True})
    store.save_task("task", True, 7)
    with closing(package_at(tmp_path, {"new": 2})) as package:
        checks = inspect_objects(target, package)
        assert checks[0]["conflict"] and checks[0]["current"]["old"] == 1
        assert commit(target, package, checks)["failed"]
        assert commit(target, package, checks, "skip")["completed"][0]["status"] == "skipped"
        assert commit(target, package, checks, "replace")["failed"] is None
        expected = {"pages": {"sample.page": {"new": 2}, "other": {"keep": True}},
                    "tasks": {"task": {"enabled": True, "count": 7}}}
        assert UserSettings(target.data_root).value == expected
        # 旧实例保存任务也不能将已导入页面回滚。
        store.save_task("task", False, 3)
        assert UserSettings(target.data_root).value["pages"] == expected["pages"]
        assert commit(target, package)["completed"][0]["status"] == "skipped"


def test_changed_target_rejected_and_json_types_distinguished(tmp_path):
    target = ManifestManager(tmp_path / "target")
    store = UserSettings(target.data_root)
    store.save("pages", "sample.page", {"value": True})
    with closing(package_at(tmp_path, {"value": 1})) as package:
        checks = inspect_objects(target, package)
        assert checks[0]["conflict"] and not checks[0]["same"]
        store.save("pages", "sample.page", {"value": 2})
        assert commit(target, package, checks, "replace")["failed"]
        assert UserSettings(target.data_root).value["pages"]["sample.page"] == {"value": 2}


@pytest.mark.parametrize("files", [
    {"settings.json": b"[]"},
    {"settings.json": b'{"x":1,"x":2}'},
    {"settings.json": b'{"x":NaN}'},
    {"settings.json": b'{"x":1e999}'},
    {"settings.json": b"{}", "extra.json": b"{}"},
])
def test_invalid_configuration_is_rejected_without_writes(tmp_path, files):
    archive = tmp_path / "invalid.zip"
    save_package([{"kind": "page_settings", "id": "sample.page", "files": files}], archive)
    target = ManifestManager(tmp_path / "target")
    with closing(SharingPackage(archive)) as package:
        assert inspect_objects(target, package)[0]["errors"]
        assert commit(target, package)["failed"]
        assert not (target.data_root / "user-settings.json").exists()


def test_gui_defaults_conflict_details_recheck_and_commit(window, tmp_path, monkeypatch):
    store = UserSettings(window.service.data_root)
    store.save("pages", "sample.page", {"local": 1})
    export = ExportDialog(window)
    try:
        assert export.selectors["page_settings"].count() == 1
        assert export.selection()["page_settings"] == []
    finally:
        export.close()
    with closing(package_at(tmp_path, {"imported": 2})) as package:
        dialog = ImportDialog(window, package)
        changed = []
        window.imported_page_settings = lambda ids: changed.append(ids)
        monkeypatch.setattr("lalc.sharing_gui.QMessageBox.information", lambda *args: None)
        try:
            assert not dialog.selected
            assert dialog.page_settings.item(0).checkState().value == 0
            assert '"local": 1' in dialog.settings_details.toPlainText()
            assert '"imported": 2' in dialog.settings_details.toPlainText()
            dialog.trust.setChecked(True)
            dialog.set_kind_selected("page_settings", True)
            assert not dialog.commit.isEnabled()
            dialog.settings_action("replace")
            assert dialog.commit.isEnabled()
            store.save("pages", "sample.page", {"changed": True})
            dialog.recheck()
            assert not dialog.commit.isEnabled() and not dialog.asset_actions
            dialog.settings_action("replace")
            dialog.submit()
            assert dialog.result_data["failed"] is None
            assert changed == [{"sample.page"}]
            assert UserSettings(window.service.data_root).value["pages"]["sample.page"] == {"imported": 2}
        finally:
            dialog.close()


def test_imported_page_is_frozen_until_reload_and_other_pages_still_save(owner, monkeypatch):
    user = owner.user
    page = user.business_pages[0]
    store = UserSettings(user.service.data_root)
    store.save("pages", page.page_id, {"imported": 42})
    user.imported_page_settings({page.page_id})
    assert page.context.requires_reload and not page.widget.isEnabled()
    assert not user.start_button.isEnabled()
    user.render_state(user.service.status)
    assert not page.widget.isEnabled()
    with pytest.raises(ValueError, match="重载"):
        page.context.save({"old": True})
    with pytest.raises(ValueError, match="Reload"):
        user.start_plan()
    monkeypatch.setattr(page.widget, "submit", lambda: pytest.fail("不得提交旧页"))
    user.submit_pages()
    assert UserSettings(user.service.data_root).value["pages"][page.page_id] == {"imported": 42}
    # 重开窗口共享原页面实例，待重载保护不能只保存在旧窗口上。
    user.close()
    reopened = owner.open_window()
    assert any(p.context.requires_reload for p in reopened.business_pages)
    assert not reopened.start_button.isEnabled()
    owner.request_reload()
    assert owner.reloading
    assert UserSettings(user.service.data_root).value["pages"][page.page_id] == {"imported": 42}


def test_write_failure_keeps_original_configuration(tmp_path, monkeypatch):
    target = ManifestManager(tmp_path / "target")
    store = UserSettings(target.data_root)
    store.save("pages", "sample.page", {"original": True})
    before = store.path.read_bytes()
    with closing(package_at(tmp_path, {"replacement": True})) as package:
        def fail(*args):
            raise OSError("write failed")
        monkeypatch.setattr("lalc.user_pages.atomic_write_json", fail)
        result = commit(target, package, action="replace")
        assert result["failed"] and store.path.read_bytes() == before
