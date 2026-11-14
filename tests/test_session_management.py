"""覆盖会话标题固定、重命名、删除回滚、悬停菜单及忙碌边界，不启动 Agent。

项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_session_management.py
"""

import json
from pathlib import Path

import pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialogButtonBox, QMessageBox

from lalc.agent_history import AgentHistory
from lalc.developer_session import DeveloperSession
from lalc.i18n import tr
from test_developer_gui import gui, wait_jobs
from test_developer_session import session


def index_session(session):
    history = AgentHistory(session.host.service.data_root)
    record = dict(version=1, session_id=session.identity, round=1, source='gui:Repair', title='original',
                  observation=dict(game_version='1.118.0', steam_build_id='123', observed_at='2026-11-11T00:00:00Z'))
    directory = session.path / 'log/version-observations'
    directory.mkdir()
    (directory / '1.json').write_text(json.dumps(record), encoding="utf-8")
    history.add(record, directory.parent)
    return history


def test_rename_is_persistent_atomic_and_preserves_identity_and_order(session, monkeypatch):
    metadata = session.path / 'session.json'
    before = json.loads(metadata.read_text(encoding="utf-8"))
    stamp = session.path.stat().st_mtime_ns
    assert session.rename('  我的会话  ') == '我的会话'
    renamed = session.check()
    assert renamed.pop('title') == '我的会话' and renamed == before
    assert session.path.stat().st_mtime_ns == stamp
    original = metadata.read_bytes()
    for title in ('', '  ', 'a\nb', 'a\rb', None):
        with pytest.raises(ValueError):
            session.rename(title)
    def fail(*args):
        raise OSError('disk full')
    monkeypatch.setattr('lalc.developer_session.atomic_write_json', fail)
    with pytest.raises(OSError):
        session.rename('changed')
    assert metadata.read_bytes() == original


def test_delete_removes_private_data_and_index_but_keeps_published_and_other_sessions(session):
    service = session.host.service
    other = DeveloperSession.create(service, session.check()['source_manifest_id'])
    history = index_session(session)
    index_session(other)
    draft = session.path / 'page-drafts/example'
    draft.mkdir(parents=True)
    (draft / 'page.py').write_text('private draft', encoding="utf-8")
    manifest = service.manifest_manager.default_manifest_id()
    shared = service.data_root / 'assets/shared.txt'
    installed = service.data_root / 'pages/installed.py'
    for path in (shared, installed):
        path.parent.mkdir(exist_ok=True)
        path.write_text('retained', encoding="utf-8")
    assert session.delete() is None
    assert not session.path.exists() and other.path.exists()
    assert [row['session_id'] for row in history.search()['sessions']] == [other.identity]
    assert history.rebuild()['observations'] == 1
    assert service.manifest_manager.default_manifest_id() == manifest
    assert any(item['manifest_id'] == manifest for item in service.manifest_manager.list_manifests())
    assert shared.read_text(encoding="utf-8") == installed.read_text(encoding="utf-8") == 'retained'
    assert not list(session.path.parent.glob('.delete-*'))


def test_management_rejects_session_symlink_without_touching_target(session):
    alias = session.path.parent / 'original'
    session.path.rename(alias)
    session.path.symlink_to(alias, target_is_directory=True)
    with pytest.raises(ValueError):
        session.rename('unsafe')
    with pytest.raises(ValueError):
        session.delete()
    assert (alias / 'session.json').is_file()


def test_delete_index_commit_failure_restores_directory_and_index(session, monkeypatch):
    from contextlib import contextmanager
    history = index_session(session)
    original = AgentHistory.connection
    @contextmanager
    def fail_commit(self, **kwargs):
        with original(self, **kwargs) as connection:
            yield connection
            raise OSError('commit failed')
    monkeypatch.setattr(AgentHistory, 'connection', fail_commit)
    with pytest.raises(OSError, match='commit failed'):
        session.delete()
    monkeypatch.setattr(AgentHistory, 'connection', original)
    assert session.check()
    assert history.search()['sessions'][0]['session_id'] == session.identity
    assert not list(session.path.parent.glob('.delete-*'))


def test_delete_failed_restore_preserves_only_copy(session, monkeypatch):
    from contextlib import contextmanager
    index_session(session)
    original_connection, original_replace = AgentHistory.connection, Path.replace
    @contextmanager
    def fail_commit(self, **kwargs):
        with original_connection(self, **kwargs) as connection:
            yield connection
            raise OSError('commit failed')
    def replace(path, target):
        if path.name == 'session':
            raise OSError('restore failed')
        return original_replace(path, target)
    monkeypatch.setattr(AgentHistory, 'connection', fail_commit)
    monkeypatch.setattr(Path, 'replace', replace)
    with pytest.raises(OSError, match='retained data:'):
        session.delete()
    assert not session.path.exists()
    retained = list(session.path.parent.glob('.delete-*/session/session.json'))
    assert len(retained) == 1 and json.loads(retained[0].read_text(encoding="utf-8"))['session_id'] == session.identity


def test_delete_cleanup_failure_returns_retained_location(session, monkeypatch):
    history = index_session(session)
    def fail(*args):
        raise OSError('file in use')
    monkeypatch.setattr('lalc.developer_session.shutil.rmtree', fail)
    remaining = session.delete()
    assert remaining.is_dir() and (remaining / 'session/session.json').is_file()
    assert not session.path.exists() and not history.search()['sessions']


@pytest.mark.parametrize('operation', ['rename', 'delete'])
def test_management_rejects_busy_or_locked_session(session, operation):
    call = (lambda: session.rename('new name')) if operation == 'rename' else session.delete
    with session.host.service.activity('Capture'):
        with pytest.raises(Exception, match='当前活动尚未结束'):
            call()
    with session.host.candidate_lock():
        with pytest.raises(OSError):
            call()
    assert session.check()


def test_live_title_is_fixed_across_rounds_and_manual_title_survives_reopen(gui, monkeypatch):
    import io

    # 模拟中文 Windows 默认编码，避免 UTF-8 开发机掩盖遗漏的文件编码。
    monkeypatch.setattr(io, 'text_encoding', lambda encoding, stacklevel=2: encoding or 'gbk')
    app, window = gui
    page = window.repair_page
    current = page.session
    page.show_event({'event': dict(type='workbench_session', session=current, message='First request.', round=1)})
    page.show_event({'event': dict(type='workbench_session', session=current, message='Different request.', round=2)})
    assert page.identity.text() == 'First request.'
    assert page.session_uuid.text() == tr('Chat ID: {0}').format(current.identity)
    assert not page.session_uuid.isHidden()
    assert page.session_uuid.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse
    current.rename('人工名称' * 20)
    page.update_source_label()
    assert current.check()['source_manifest_id'] in page.source_label.text()
    page.titles.clear()
    page.refresh_sessions()
    assert page.identity.text().endswith('…')
    assert '人工名称' * 20 in page.identity.toolTip()
    page.show_event({'event': dict(type='workbench_session', session=current, message='Third request.', round=3)})
    assert '人工名称' in page.identity.text()
    page.new()
    assert page.session_uuid.isHidden() and not page.session_uuid.text()
    page.open_session(page.history.item(0))
    wait_jobs(app, window)
    assert '人工名称' * 20 in page.identity.toolTip()
    assert page.session_uuid.text() == tr('Chat ID: {0}').format(current.identity)
    assert not page.session_uuid.isHidden()


def test_rename_dialog_cancel_empty_save_and_busy_gate(gui):
    from lalc.developer_gui import QLineEdit
    app, window = gui
    page = window.repair_page
    identity = page.session.identity
    page.session.rename('before')
    page.rename_session(identity)
    dialog = page.rename_dialog
    editor = dialog.findChild(QLineEdit)
    buttons = dialog.findChild(QDialogButtonBox)
    assert editor.text() == 'before'
    editor.setText('   ')
    assert not buttons.button(QDialogButtonBox.StandardButton.Save).isEnabled()
    buttons.button(QDialogButtonBox.StandardButton.Cancel).click()
    assert page.session.check()['title'] == 'before'
    page.rename_session(identity)
    dialog = page.rename_dialog
    editor = dialog.findChild(QLineEdit)
    buttons = dialog.findChild(QDialogButtonBox)
    editor.setText('  after  ')
    with window.service.activity('Capture'):
        page.render(True)
        assert not buttons.button(QDialogButtonBox.StandardButton.Save).isEnabled()
        assert not page.history.menu_button.isEnabled()
    page.render(False)
    buttons.button(QDialogButtonBox.StandardButton.Save).click()
    wait_jobs(app, window)
    assert page.rename_dialog is None and page.session.check()['title'] == 'after'
    assert page.identity.text() == 'after'


def test_hover_and_keyboard_menu_and_busy_action_guards(gui, monkeypatch):
    from lalc.developer_gui import RoundMenu
    app, window = gui
    page = window.repair_page
    window.show()
    window.switchTo(page)
    app.processEvents()
    point = page.history.visualItemRect(page.history.item(0)).center()
    QTest.mouseMove(page.history.viewport(), point)
    app.processEvents()
    assert page.history.menu_button.isVisible()
    menus = []
    def menu_exec(menu, position):
        menus.append([action.text() for action in menu.actions()])
    monkeypatch.setattr(RoundMenu, 'exec', menu_exec)
    QTest.mouseClick(page.history.menu_button, Qt.MouseButton.LeftButton)
    assert menus == [[tr('Rename'), tr('Delete')]]
    page.history.setCurrentRow(0)
    app.sendEvent(page.history, QContextMenuEvent(QContextMenuEvent.Reason.Keyboard, QPoint(), QPoint()))
    assert len(menus) == 2
    with window.service.activity('Capture'):
        page.render(True)
        page.open_session_menu(page.session.identity, QPoint())
        page.rename_session(page.session.identity)
        page.delete_session(page.session.identity)
        assert len(menus) == 2 and page.rename_dialog is None
    page.render(False)


def test_delete_confirm_cancel_other_and_current(gui, monkeypatch):
    app, window = gui
    page = window.repair_page
    current = page.session
    other = DeveloperSession.create(window.service, current.check()['source_manifest_id'], entry='gui')
    calls = []
    def cancel(*args):
        calls.append(args)
        return QMessageBox.StandardButton.Cancel
    monkeypatch.setattr(QMessageBox, 'warning', cancel)
    page.delete_session(current.identity)
    assert current.path.exists() and not window.jobs
    assert calls[0][2] == tr('Delete this Session and its conversation, attachments and unpublished drafts? This cannot be undone.')
    assert calls[0][-1] == QMessageBox.StandardButton.Cancel
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: QMessageBox.StandardButton.Yes)
    page.delete_session(other.identity)
    wait_jobs(app, window)
    assert page.session is current and not other.path.exists()
    page.delete_session(current.identity)
    wait_jobs(app, window)
    assert page.session is None and not current.path.exists()
    assert page.history.count() == 0 and page.identity.text() == tr('New Chat')
    assert not page.chat.entries


def test_real_menu_remains_visible_and_actions_follow_busy_state(gui):
    app, window = gui
    page = window.repair_page
    window.show()
    page.open_session_menu(page.session.identity, QPoint(100, 100))
    app.processEvents()
    menu = page.session_menu
    assert menu.isVisible()
    with window.service.activity('Capture'):
        page.render(True)
        assert all(not action.isEnabled() for action in menu.actions())
    page.render(False)
    assert all(action.isEnabled() for action in menu.actions())
    menu.actions()[0].trigger()
    assert page.rename_dialog is not None and page.rename_dialog.isVisible()
    page.rename_dialog.reject()
    menu.close()


@pytest.mark.parametrize('language', ['zh_CN', 'en_US'])
def test_management_dialog_language(gui, monkeypatch, language):
    from lalc.i18n import current_language, install_translations
    app, window = gui
    previous = current_language()
    page = window.repair_page
    try:
        install_translations(app, language)
        page.rename_session(page.session.identity)
        dialog = page.rename_dialog
        assert dialog.windowTitle() == ('重命名会话' if language == 'zh_CN' else 'Rename Session')
        buttons = dialog.findChild(QDialogButtonBox)
        assert ('保存' if language == 'zh_CN' else 'Save') in buttons.button(QDialogButtonBox.StandardButton.Save).text()
        assert ('取消' if language == 'zh_CN' else 'Cancel') in buttons.button(QDialogButtonBox.StandardButton.Cancel).text()
        dialog.reject()
        prompts = []
        def warning(*args):
            prompts.append(args[2])
            return QMessageBox.StandardButton.Cancel
        monkeypatch.setattr(QMessageBox, 'warning', warning)
        page.delete_session(page.session.identity)
        assert ('删除后不可恢复' if language == 'zh_CN' else 'cannot be undone') in prompts[0]
    finally:
        install_translations(app, previous)
