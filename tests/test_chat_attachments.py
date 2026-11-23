"""覆盖附件托盘的折叠、滚动、预览、删除、即时提交与安全历史恢复。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_chat_attachments.py
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from lalc.agent_log import LogStore
from lalc.chat_attachments import AttachmentTray, ImagePreview, draft_attachments, history_attachments, thumbnail
from lalc.repair_chat import RepairChat
from test_developer_gui import gui, wait_jobs


def make_image(path):
    image = QImage(800, 400, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.darkCyan)
    assert image.save(str(path))
    return path


def test_many_attachments_are_bounded_and_scrollable_at_narrow_width(gui, tmp_path):
    app, _ = gui
    path = make_image(tmp_path / 'screenshot.png')
    tray = AttachmentTray(removable=True)
    tray.resize(750, 72)
    tray.set_items(draft_attachments([path] * 100, []))
    tray.show()
    app.processEvents()
    assert len(tray.cards) == 3 and tray.more.isVisible()
    assert tray.height() == 72
    tray.more.click()
    app.processEvents()
    assert tray.expanded and tray.height() <= 188
    assert len(tray.cards) <= tray.columns * 3
    assert tray.scroll.verticalScrollBar().maximum() > 0
    tray.scroll.verticalScrollBar().setValue(tray.scroll.verticalScrollBar().maximum())
    assert 99 in tray.cards and 0 not in tray.cards
    tray.resize(220, tray.height())
    app.processEvents()
    assert tray.columns == 1 and tray.height() <= 188
    tray.toggle.click()
    app.processEvents()
    assert not tray.expanded and tray.more.isVisible() and not tray.cards
    tray.more.click()
    app.processEvents()
    assert tray.cards
    tray.close()
    tray.deleteLater()


def test_remove_selected_attachment_preserves_files_full_ids_and_busy_boundary(gui, tmp_path, monkeypatch):
    _, window = gui
    page = window.repair_page
    first = make_image(tmp_path / 'one.png')
    second = make_image(tmp_path / 'two.png')
    identities = ['12345678-0000-4000-8000-000000000001', '12345678-0000-4000-8000-000000000002']
    images = draft_attachments([first, second], [])
    page.images, page.manifest_references = list(images), list(identities)
    page.update_attachment_notice()
    monkeypatch.setattr(page, 'is_busy', lambda: False)
    page.remove_attachment(1)
    assert page.images == images[:1] and second.exists()
    page.remove_attachment(1)
    assert page.manifest_references == [identities[1]]
    monkeypatch.setattr(page, 'is_busy', lambda: True)
    page.remove_attachment(0)
    assert page.images == images[:1] and first.exists()


def test_history_metadata_does_not_expand_prompt_and_rejects_unsafe_images(gui, tmp_path):
    root = tmp_path / 'log'
    root.mkdir()
    folder = root / 'round-1'
    folder.mkdir()
    image = make_image(folder / 'input-1.png')
    outside = make_image(tmp_path / 'outside.png')
    (folder / 'linked.png').symlink_to(outside)
    store = LogStore(root)
    store.initialize()
    identity = 'ea3c6c01-0000-4000-8000-000000000001'
    store.write_json(folder / 'input.json', {
        'attachments': [{'filename': name, 'original_name': '截图.png'} for name in
                        ['input-1.png', 'missing.png', '../outside.png', 'linked.png']],
        'manifest_references': [identity],
        'prompt': {'$lalc_log': {'path': 'missing-object.json', 'kind': 'json', 'sha256': '0' * 64}},
    })
    items = history_attachments(root, 1)
    assert len(items) == 5 and items[-1]['name'] == identity
    assert not thumbnail(items[0]).isNull()
    assert all(thumbnail(item).isNull() for item in items[1:4])
    image.unlink()
    image.symlink_to(outside)
    assert thumbnail(items[0]).isNull()
    assert history_attachments(root, 2) == []


def test_preview_retains_original_dimensions_and_handles_missing_images(gui, tmp_path):
    _, window = gui
    path = make_image(tmp_path / 'original.png')
    item = draft_attachments([path], [])[0]
    dialog = ImagePreview(item, window)
    assert dialog.original.size().width() == 800
    assert dialog.original.size().height() == 400
    dialog.resize(400, 300)
    dialog.fit_image()
    assert dialog.image.pixmap().width() <= 376
    dialog.close()
    path.unlink()
    missing = ImagePreview(item, window)
    assert missing.original.isNull() and missing.image.text()
    missing.close()


def test_chat_attachment_position_expansion_and_refresh_preserve_reading(gui, tmp_path):
    app, _ = gui
    path = make_image(tmp_path / 'shot.png')
    chat = RepairChat()
    chat.resize(800, 600)
    chat.show()
    chat.add_message('你', 'message body', 1, attachments=draft_attachments([path] * 18, []))
    app.processEvents()
    tray = next(iter(chat.attachment_trays.values()))
    text = chat.document().find('message body')
    assert tray.y() >= 0
    assert tray.geometry().bottom() < chat.cursorRect(text).top()
    assert not tray.removable
    tray.more.click()
    app.processEvents()
    assert tray.expanded
    tray.scroll.verticalScrollBar().setValue(80)
    offset = tray.scroll.verticalScrollBar().value()
    chat.set_activity('Thinking', 1)
    app.processEvents()
    assert next(iter(chat.attachment_trays.values())) is tray
    assert tray.expanded and tray.scroll.verticalScrollBar().value() == offset
    chat.add_message('Agent', 'long reply\n' * 100, 1)
    app.processEvents()
    bar = chat.verticalScrollBar()
    bar.setValue(30)
    assert tray.y() == chat.cursorRect(next(iter_cursor(chat))).y()
    chat.resize(420, 600)
    app.processEvents()
    assert tray.width() <= chat.viewport().width()
    chat.clear()
    assert not chat.attachment_trays
    chat.close()
    chat.deleteLater()


def iter_cursor(chat):
    from PySide6.QtGui import QTextCursor
    for position in chat.attachment_positions.values():
        cursor = QTextCursor(chat.document())
        cursor.setPosition(position)
        yield cursor


def test_submit_snapshot_and_restored_attachments_survive_source_removal(gui, tmp_path, monkeypatch):
    from datetime import datetime
    from lalc.agent_repair import RepairConversation, image_attachments
    app, window = gui
    page = window.repair_page
    path = make_image(tmp_path / 'original.png')
    identity = window.host.manager.default_manifest_id()
    observed = []
    live_times = []
    original_add = page.chat.add_message
    def add(role, text, number=0, **kwargs):
        if role == '你':
            observed.append(kwargs.get('attachments', []))
        return original_add(role, text, number, **kwargs)
    monkeypatch.setattr(page.chat, 'add_message', add)
    window.operation_event.connect(lambda row: live_times.append(row['time'])
                                   if row['event']['type'] == 'round_opened' else None)
    async def run(self, message, *args, images=(), manifest_references=(), **kwargs):
        self.log.group += 1
        self.log.on_event = kwargs['on_event']
        self.log.record({'type': 'round_opened'})
        folder = self.log.path / f'round-{self.log.group}'
        folder.mkdir(exist_ok=True)
        _, records = image_attachments(images, folder)
        self.append_user({'role': 'user', 'content': [{'type': 'text', 'text': message}]})
        self.log.save_json(f'round-{self.log.group}/input.json', {
            'attachments': records, 'manifest_references': list(manifest_references)})
        return {'reason': 'answered', 'requests': 0, 'answer': {'message': 'ready'}}
    monkeypatch.setattr(RepairConversation, 'run', run)
    page.images, page.manifest_references = draft_attachments([path], []), [identity]
    page.update_attachment_notice()
    page.message.setPlainText('use these attachments')
    page.send()
    wait_jobs(app, window)
    assert observed[0][0]['path'] == path
    assert page.chat.round_times[1] == datetime.fromisoformat(live_times[0])
    assert page.images == [] and page.manifest_references == []
    path.unlink()
    page.reload_history()
    entries = [item for item in page.chat.entries if item['role'] == '你']
    assert entries[-1]['attachments'][1]['name'] == identity
    assert not thumbnail(entries[-1]['attachments'][0]).isNull()
    tray = page.chat.attachment_trays[id(entries[-1])]
    tray.toggle_expanded()
    page.answered({'reason': 'answered', 'requests': 0, 'answer': {'message': 'ready'}})
    assert next(iter(page.chat.attachment_trays.values())).expanded
    session_id = page.session.identity
    page.new()
    item = next(page.history.item(i) for i in range(page.history.count())
                if page.history.item(i).data(Qt.ItemDataRole.UserRole) == session_id)
    page.open_session(item)
    wait_jobs(app, window)
    entry = next(entry for entry in page.chat.entries if entry['role'] == '你')
    restored = entry['attachments']
    assert restored[1]['name'] == identity and not thumbnail(restored[0]).isNull()
    assert page.chat.round_times[1] == datetime.fromisoformat(live_times[0])
    page.chat.message_actions[id(entry)].edit.click()
    assert page.message.toPlainText() == 'use these attachments'
    assert page.message.textCursor().atEnd()
    assert page.images == restored[:1] and page.images[0] is not restored[0]
    assert page.manifest_references == [identity]
    page.message.insertPlainText(' again')
    page.send()
    wait_jobs(app, window)
    assert page.chat.entries[0]['round'] == 2
    page.load_older_history()
    wait_jobs(app, window)
    messages = [entry['text'] for entry in page.chat.entries if entry['role'] == '你']
    assert messages == ['use these attachments', 'use these attachments again']
    assert page.chat.round_times[1] == datetime.fromisoformat(live_times[0])


def test_edit_confirmation_protects_draft_and_revalidates_reused_image(gui, tmp_path, monkeypatch):
    import pytest
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QMessageBox

    app, window = gui
    page = window.repair_page
    root = tmp_path / 'log'
    root.mkdir()
    folder = root / 'round-1'
    folder.mkdir()
    image = make_image(folder / 'input-1.png')
    store = LogStore(root)
    store.initialize()
    store.write_json(folder / 'input.json', {'attachments': [{'filename': image.name}]})
    page.chat.add_message('你', 'History', 1, attachments=history_attachments(root, 1))
    edit = next(iter(page.chat.message_actions.values())).edit
    page.message.setPlainText('Unsaved draft')
    QTimer.singleShot(0, lambda: app.activeModalWidget().button(QMessageBox.StandardButton.Cancel).click())
    edit.click()
    assert page.message.toPlainText() == 'Unsaved draft' and not page.images
    def replace_draft():
        dialog = app.activeModalWidget()
        next(button for button in dialog.buttons()
             if dialog.buttonRole(button) == QMessageBox.ButtonRole.AcceptRole).click()

    QTimer.singleShot(0, replace_draft)
    edit.click()
    assert page.message.toPlainText() == 'History' and len(page.images) == 1

    image.unlink()
    image.symlink_to(make_image(tmp_path / 'outside.png'))
    monkeypatch.setattr(window, '_interact', lambda operation: operation())
    with pytest.raises(ValueError, match=r'input-1\.png'):
        page.send()
    assert page.message.toPlainText() == 'History' and len(page.images) == 1
    assert not window.jobs


def test_keyboard_removal_and_attachment_card_labels(gui, tmp_path):
    from lalc.i18n import tr
    app, _ = gui
    tray = AttachmentTray(removable=True)
    tray.resize(400, 72)
    identity = 'ea3c6c01-0000-4000-8000-000000000001'
    tray.set_items(draft_attachments([tmp_path / 'missing.png'], [identity]))
    tray.show()
    app.processEvents()
    removed = []
    tray.removed.connect(removed.append)
    image, manifest = tray.cards[0], tray.cards[1]
    assert tr('Image unavailable') in image.caption.text()
    assert manifest.caption.text() == tr('Manifest') + '\nea3c6c01'
    assert manifest.button.toolTip() == identity
    manifest.button.setFocus()
    app.processEvents()
    assert not manifest.remove.isHidden()
    manifest.remove.click()
    assert removed == [1]
    assert '#fafafa' in manifest.button.styleSheet()
    tray.close()
    tray.deleteLater()
