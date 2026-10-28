"""覆盖 P0 启动门槛、无效文本保存、密钥弹窗及错误详情折叠。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_user_gui_p0.py
"""

import pytest
from PySide6.QtWidgets import QDialog, QDialogButtonBox

from lalc.agent_settings import load_settings, save_settings, save_selection, settings_document
from lalc.gui import ErrorDialog
from test_user_pages import app, owner


def test_invalid_other_provider_does_not_block_selection_or_reading(tmp_path):
    save_settings(tmp_path, {"model": "local"})
    save_settings(tmp_path, {"provider": "deepseek", "base_url": "invalid"})
    save_selection(tmp_path, "user", "llama.cpp", enabled=False)
    assert not settings_document(tmp_path)["user_enabled"]
    assert load_settings(tmp_path, side="user")["model"] == "local"
    assert load_settings(tmp_path, for_use=False)["base_url"] == "invalid"
    with pytest.raises(ValueError):
        load_settings(tmp_path)


@pytest.mark.parametrize("provider,address,model,key,enabled,ready", [
    ("llama.cpp", "invalid", None, False, False, True),
    ("llama.cpp", "invalid", "local", False, True, False),
    ("llama.cpp", "http://localhost:12138/v1", None, False, True, False),
    ("llama.cpp", "http://localhost:12138/v1", "local", False, True, True),
    ("deepseek", "https://api.deepseek.com", "deepseek-flash", False, True, False),
    ("deepseek", "https://api.deepseek.com", "deepseek-flash", True, True, True),
])
def test_agent_readiness_matches_start_entry(owner, monkeypatch, provider, address, model, key, enabled, ready):
    root, user = owner.service.data_root, owner.user
    save_settings(root, {"provider": provider, "base_url": address, "model": model}, side="user")
    save_selection(root, "user", provider, enabled=enabled)
    if key:
        owner.host.secrets[provider] = "test-key"
    owner.refresh_agent()
    calls = []
    monkeypatch.setattr(user.service, "start_plan", lambda **kwargs: calls.append(kwargs))
    assert user.start_button.isEnabled() == ready
    assert user.start_hint.isHidden() == ready
    assert user.settings_page.isHidden() != enabled
    if ready:
        user.start_plan()
        assert len(calls) == 1
    else:
        assert "待配置" in user.agent_status.text()
        with pytest.raises(ValueError, match="补全 Agent 配置"):
            user.start_plan()
        assert not calls


def test_disabled_agent_does_not_submit_hidden_form(owner, monkeypatch):
    def unexpected():
        pytest.fail("关闭 Agent 后不提交隐藏表单")
    with monkeypatch.context() as patch:
        patch.setattr(owner.user.settings_page, "submit", unexpected)
        patch.setattr(owner.service, "start_plan", lambda **_: None)
        owner.user.start_plan()


def test_user_groups_navigation_and_developer_lock(owner, app):
    user, page = owner.user, owner.user.settings_page
    assert not hasattr(page, "diagnostics") and page.key is None
    assert page.isHidden()
    user.user_enabled.setChecked(True)
    assert not page.isHidden() and page.advanced.isHidden()
    page.advanced_button.click()
    assert not page.advanced.isHidden()
    user.agent_status.click()
    app.processEvents()
    assert user.pages.currentWidget() is user.general_settings
    assert not user.update_button.isEnabled()
    developer = owner.open_window(True)
    assert not user.agent_controls.isEnabled()
    assert user.edit_owner_notice.text() == "请在 Developer GUI 中修改"
    assert hasattr(developer.settings_page, "diagnostics")
    assert developer.close()
    assert user.agent_controls.isEnabled()


def key_dialog(page):
    page.key_button.click()
    dialog = next(dialog for dialog in page.findChildren(QDialog) if dialog.windowTitle() == "设置 API KEY")
    return dialog, dialog.findChild(QDialogButtonBox)


def test_api_key_dialog_cancel_save_and_clear(owner, app, monkeypatch):
    import lalc.agent_settings as settings
    monkeypatch.setattr(settings.sys, "platform", "darwin")
    page = owner.user.settings_page
    owner.user.user_enabled.setChecked(True)
    dialog, buttons = key_dialog(page)
    assert not buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    page.key.setText("cancel-key")
    buttons.rejected.emit()
    app.processEvents()
    assert page.key is None and not owner.host.secrets
    dialog, buttons = key_dialog(page)
    assert page.key.text() == ""
    page.key.setText("saved-key")
    buttons.accepted.emit()
    app.processEvents()
    assert page.key is None
    assert owner.host.secrets["llama.cpp"] == "saved-key"
    assert "saved-key" not in (owner.service.data_root / "agent-settings.json").read_text()
    page.clear_button.click()
    assert not owner.host.secrets


def test_api_key_save_failure_preserves_dialog_and_redacts_error(owner, app, monkeypatch):
    import lalc.agent_settings as settings
    owner.user.user_enabled.setChecked(True)
    page = owner.user.settings_page
    dialog, buttons = key_dialog(page)
    page.key.setText("pending-key")
    def fail(*_):
        raise OSError("cannot save pending-key")
    monkeypatch.setattr(settings, "atomic_write_json", fail)
    buttons.accepted.emit()
    app.processEvents()
    assert dialog.isVisible() and page.key.text() == "pending-key"
    error = owner.user.findChildren(ErrorDialog)[-1]
    assert "pending-key" not in error.details.toPlainText()
    assert error.details.isHidden()
    error.close()
    dialog.reject()


def test_error_details_expand_and_copy_full_text(app):
    dialog = ErrorDialog("操作失败", "Traceback\nfull details")
    dialog.show()
    assert dialog.details.isHidden()
    dialog.details_button.click()
    assert not dialog.details.isHidden()
    from qfluentwidgets import PushButton
    next(button for button in dialog.findChildren(PushButton) if "复制错误信息" in button.text()).click()
    assert app.clipboard().text() == "操作失败\n\nTraceback\nfull details"
    dialog.details_button.click()
    assert dialog.details.isHidden()
    dialog.close()


def test_pending_key_requires_explicit_confirmation_before_handoff_or_reload(owner, app):
    owner.user.user_enabled.setChecked(True)
    page = owner.user.settings_page
    dialog, _ = key_dialog(page)
    page.key.setText("unconfirmed-key")
    with pytest.raises(ValueError, match="确认或取消"):
        owner.open_window(True)
    assert owner.developer is None and owner.user.agent_controls.isEnabled()
    with pytest.raises(ValueError, match="确认或取消"):
        owner.request_reload()
    assert not owner.reloading and not owner.host.secrets
    dialog.reject()
    app.processEvents()


def test_empty_tasks_and_manifest_failure_dialog(owner, monkeypatch):
    from types import SimpleNamespace
    from qfluentwidgets import BodyLabel
    user, manager = owner.user, owner.host.manager
    monkeypatch.setattr(manager, "default_manifest_id", lambda: None)
    user.refresh_tasks()
    assert any(label.text() == "请先选择 Manifest。" for label in user.task_list.findChildren(BodyLabel))
    monkeypatch.setattr(manager, "default_manifest_id", lambda: "bad-manifest")
    monkeypatch.setattr(manager, "load", lambda _: SimpleNamespace(ok=False, errors=[SimpleNamespace(message="invalid source")]))
    errors = []
    monkeypatch.setattr(ErrorDialog, "open", lambda dialog: errors.append(dialog.details.toPlainText()))
    user.refresh_tasks()
    user.refresh_tasks()
    assert errors == ["invalid source"]
    assert not user.task_rows


def test_task_list_uses_remaining_height_and_no_matching_tasks_message(owner, app):
    from qfluentwidgets import BodyLabel
    user = owner.user
    before = user.task_scroll.height()
    user.resize(user.width(), user.height() + 160)
    app.processEvents()
    assert user.task_scroll.height() > before
    user.business_pages = []
    user.refresh_tasks()
    assert any(label.text() == "当前 Manifest 与已加载的配置页没有匹配任务。"
               for label in user.task_list.findChildren(BodyLabel))


def test_user_check_errors_use_dialog_without_diagnostics_and_do_not_validate_new_input(owner, monkeypatch):
    user, page = owner.user, owner.user.settings_page
    user.user_enabled.setChecked(True)
    result = {"ok": False, "message": "连接失败", "error": {"message": "连接失败", "traceback": "original error"}}
    dialogs = []
    monkeypatch.setattr(ErrorDialog, "open", lambda dialog: dialogs.append(dialog))
    def launch(_operation, done):
        page.url.setText("changed-after-check")
        done(result)
    monkeypatch.setattr(user, "launch", launch)
    page.check(False)
    assert len(dialogs) == 1 and dialogs[0].details.isHidden()
    assert "original error" in dialogs[0].details.toPlainText()
    assert "设置已变更" in page.check_status.text()
    assert not hasattr(page, "diagnostics")


def test_undeclared_tasks_and_no_manifest_show_neutral_empty_state(owner, monkeypatch):
    from types import SimpleNamespace
    from qfluentwidgets import IconWidget
    from lalc.user_pages import task_inputs
    user, manager = owner.user, owner.host.manager
    monkeypatch.setattr(manager, "load", lambda _: SimpleNamespace(ok=True, loaded=SimpleNamespace(
        components={"plan": SimpleNamespace(role="automation_plan", supported_task_ids=())})))
    user.refresh_tasks()
    assert not user.task_rows
    assert user.task_warning.isHidden() and user.warning_button.isHidden()
    assert user.task_list.findChildren(IconWidget)
    assert task_inputs(user.business_pages, (), user.page_store)[2]
    monkeypatch.setattr(manager, "default_manifest_id", lambda: None)
    user.refresh_tasks()
    assert user.task_warning.isHidden() and user.warning_button.isHidden()


def test_task_mismatch_shows_reason_and_resolved_history_is_neutral(owner, monkeypatch):
    from types import SimpleNamespace
    user, manager = owner.user, owner.host.manager
    supported = ["missing.task"]
    monkeypatch.setattr(manager, "load", lambda _: SimpleNamespace(ok=True, loaded=SimpleNamespace(
        components={"plan": SimpleNamespace(role="automation_plan", supported_task_ids=tuple(supported))})))
    before = user.page_store.value.copy()
    user.refresh_tasks()
    assert not user.task_warning.isHidden()
    assert "missing.task" in user.task_warning.text()
    assert "sample.loop" in user.task_warning.text()
    assert user.warning_button.iconSize().width() == 16
    assert user.warning_button.width() == 28
    assert user.warning_button.toolTip() == user.task_warning.text()
    assert user.page_store.value == before
    supported[:] = ["sample.loop"]
    user.refresh_tasks()
    assert user.task_warning.isHidden()
    assert not user.warning_button.isHidden()
    assert "当前无配置异常" in user.warning_button.toolTip()
    assert any("missing.task" in entry for entry in user.warning_history)
