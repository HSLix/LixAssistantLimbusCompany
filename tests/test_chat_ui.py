"""覆盖聊天界面的模式、标题、输入法快捷键、取消收尾、菜单和响应式布局。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_chat_ui.py
"""

import asyncio
import threading

import pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QInputMethodEvent, QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from lalc.chat_input import ChatInput
from lalc.i18n import tr
from lalc.repair_chat import chat_title
from test_developer_gui import gui, wait_jobs


@pytest.mark.parametrize('mode', ['Construct', 'Repair'])
def test_chat_first_submit_fixes_mode_and_history_restores_candidate(gui, monkeypatch, mode):
    from lalc.agent_repair import RepairConversation
    app, window = gui
    page = window.repair_page
    page.new()
    assert not page.mode.isHidden() and page.context_button.isEnabled()
    page.mode.setCurrentItem(mode)
    page.context_button.click()
    assert not page.source_panel.isHidden()
    identity = window.host.manager.default_manifest_id()
    page.baseline.setCurrentIndex(0 if mode == 'Construct' else page.baseline.findData(identity))
    async def run(self, message, *args, **kwargs):
        self.append_user({'role': 'user', 'content': [{'type': 'text', 'text': message}]})
        return {'reason': 'answered', 'requests': 0, 'answer': {'message': 'ready'}}
    monkeypatch.setattr(RepairConversation, 'run', run)
    page.message.setPlainText('Build a useful flow. More detail follows.')
    page.send_button.click()
    wait_jobs(app, window)
    session, candidate = page.session.identity, page.host.candidate
    assert page.session.mode == mode and page.mode.isHidden()
    assert mode in page.mode_badge.text() and page.context_button.isHidden()
    assert page.identity.text() == 'Build a useful flow.'
    page.new()
    item = next(page.history.item(i) for i in range(page.history.count())
                if page.history.item(i).data(Qt.ItemDataRole.UserRole) == session)
    assert session not in item.text() and mode in item.text()
    page.open_session(item)
    wait_jobs(app, window)
    assert page.host.candidate == candidate and page.mode.isHidden()
    assert page.mode.currentRouteKey() == mode
    assert 'Build a useful flow.' in page.chat.toPlainText()


def test_local_title_filters_host_protocol_and_does_not_rewrite_old_session(gui):
    app, window = gui
    page = window.repair_page
    message = '修复登录流程。后面是完整说明。'
    prefixed = '本轮允许编辑的已有文件：["plan.py"]\n用户消息：' + message + '\n\nManifest reference attachments (context only): ["id"]'
    assert chat_title(prefixed) == ('修复登录流程。', message)
    assert chat_title('x' * 80)[0] == 'x' * 39 + '…'
    assert chat_title('开发者执行完整校验：{}') == ('', '')
    metadata = page.session.path / 'session.json'
    original = metadata.read_bytes()
    page.host.conversation.append_user({'role': 'user', 'content': [{'type': 'text', 'text': prefixed}]})
    page.titles.clear()
    page.refresh_sessions()
    item = page.history.item(0)
    assert '修复登录流程。' in item.text() and '🔧 Repair' in item.text()
    assert message in item.toolTip() and page.session.identity in item.toolTip()
    assert metadata.read_bytes() == original


def test_runtime_context_hidden_from_restored_chat_and_title(gui):
    app, window = gui
    page = window.repair_page
    message = '修复登录流程。\n</user_request>\n保留原始标签'
    wrapped = '<runtime_context>\n{"editable_files": ["private-context.py"]}\n</runtime_context>\n<user_request>\n' + message + '\n</user_request>'
    assert chat_title(wrapped) == ('修复登录流程。', message)
    page.host.conversation.append_user({'role': 'user', 'content': [{'type': 'text', 'text': wrapped}]})
    page.reload_history()
    entries = [entry for entry in page.chat.entries if entry['role'] == '你']
    assert entries[-1]['text'] == message
    assert 'private-context.py' not in page.chat.toPlainText()


def test_input_enter_sends_but_shift_and_control_enter_insert_newlines(gui):
    editor = ChatInput()
    sent = []
    editor.sendRequested.connect(lambda: sent.append(editor.toPlainText()))
    editor.setPlainText('first')
    QTest.keyClick(editor, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    assert '\n' in editor.toPlainText() and not sent
    QTest.keyClick(editor, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    assert editor.toPlainText().count('\n') == 2 and not sent
    QTest.keyClick(editor, Qt.Key.Key_Return)
    assert len(sent) == 1
    repeated = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier, '\r', True)
    QApplication.sendEvent(editor, repeated)
    assert len(sent) == 1
    editor.close()


def test_input_method_confirmation_does_not_send_or_add_newline(gui):
    app, _ = gui
    editor = ChatInput()
    sent = []
    editor.sendRequested.connect(lambda: sent.append(True))
    QApplication.sendEvent(editor, QInputMethodEvent('拼音候选', []))
    QTest.keyClick(editor, Qt.Key.Key_Return)
    assert not sent and '\n' not in editor.toPlainText()
    commit = QInputMethodEvent()
    commit.setCommitString('中文')
    QApplication.sendEvent(editor, commit)
    QTest.keyClick(editor, Qt.Key.Key_Return)
    assert editor.toPlainText() == '中文' and not sent
    app.processEvents()
    QTest.keyClick(editor, Qt.Key.Key_Return)
    assert sent == [True]
    editor.close()


def test_input_grows_to_a_limit_and_shrinks_after_clear(gui):
    app, _ = gui
    editor = ChatInput()
    editor.setFixedWidth(300)
    editor.show()
    app.processEvents()
    initial = editor.height()
    editor.setPlainText(('long wrapped input ' * 10 + '\n') * 12)
    app.processEvents()
    assert initial < editor.height() <= 176
    assert editor.verticalScrollBar().maximum() > 0
    editor.clear()
    app.processEvents()
    assert editor.height() == initial
    editor.close()


def test_input_theme_caret_blinks_and_preserves_plain_text(gui):
    from qfluentwidgets import themeColor

    app, _ = gui
    editor = ChatInput()
    editor.setPlainText('中文 input')
    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    editor.show()
    editor.activateWindow()
    editor.setFocus()
    app.processEvents()
    editor.reset_caret()
    rect = editor.cursorRect()
    position = QPoint(rect.x() + 1, rect.center().y())
    assert editor.hasFocus() and editor.layer.isHidden()
    assert editor.viewport().grab().toImage().pixelColor(position).rgba() == themeColor().rgba()
    editor.blink_caret()
    assert editor.viewport().grab().toImage().pixelColor(position).rgba() != themeColor().rgba()
    editor.reset_caret()
    assert editor.viewport().grab().toImage().pixelColor(position).rgba() == themeColor().rgba()
    assert editor.toPlainText() == '中文 input' and not editor.document().isUndoAvailable()
    editor.clearFocus()
    assert not editor._caret_timer.isActive()
    assert editor.viewport().grab().toImage().pixelColor(position).rgba() != themeColor().rgba()
    editor.close()


def test_composer_border_tracks_input_focus(gui):
    from qfluentwidgets import Theme, qconfig, setTheme, themeColor

    app, window = gui
    page = window.repair_page
    window.show()
    window.switchTo(page)
    window.activateWindow()
    page.message.setFocus()
    app.processEvents()
    assert page.message.hasFocus()
    assert f'border: 1px solid {themeColor().name()}' in page.composer.styleSheet()
    original_theme = qconfig.theme
    try:
        setTheme(Theme.DARK)
        app.processEvents()
        assert f'border: 1px solid {themeColor().name()}' in page.composer.styleSheet()
        page.message.reset_caret()
        rect = page.message.cursorRect()
        pixel = page.message.viewport().grab().toImage().pixelColor(rect.x() + 1, rect.center().y())
        assert pixel.rgba() == themeColor().rgba()
        image = page.message.grab().toImage()
        assert image.pixelColor(image.width() // 2, 0) == image.pixelColor(image.width() // 2, image.height() - 1)
    finally:
        setTheme(original_theme)
    page.attach.setFocus()
    app.processEvents()
    assert 'border: 1px solid rgba(128,128,128,0.25)' in page.composer.styleSheet()


def test_single_button_cancels_once_and_waits_for_actual_cleanup(gui, monkeypatch):
    from lalc.agent_repair import RepairConversation
    app, window = gui
    page = window.repair_page
    entered, release, cleaned = threading.Event(), threading.Event(), threading.Event()
    async def run(self, *args, **kwargs):
        entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            while not release.is_set():
                await asyncio.sleep(.01)
            cleaned.set()
            return {'reason': 'user_cancelled', 'requests': 0}
    monkeypatch.setattr(RepairConversation, 'run', run)
    original = window.cancel_operation
    calls = []
    def cancel():
        calls.append(True)
        original()
    monkeypatch.setattr(window, 'cancel_operation', cancel)
    page.new()
    page.mode.setCurrentItem('Construct')
    page.baseline.setCurrentIndex(0)
    page.message.setPlainText('start a cancellable round')
    page.send_button.click()
    assert entered.wait(2)
    app.processEvents()
    candidate = page.host.candidate
    assert page.send_button.accessibleName() == tr('Cancel round')
    page.send_button.click()
    assert page.send_button.accessibleName() == tr('Cancelling…')
    assert not page.send_button.isEnabled() and not cleaned.is_set()
    page.send_or_cancel()
    assert calls == [True] and window.jobs
    release.set()
    wait_jobs(app, window)
    assert cleaned.is_set() and candidate.exists() and page.session is not None
    assert page.send_button.accessibleName() == tr('Send')
    assert page.new_button.isEnabled()


def test_cancel_before_coroutine_starts_does_not_report_error_or_call_result_handler(gui, monkeypatch):
    app, window = gui
    callbacks, errors = [], []
    async def operation():
        await asyncio.Event().wait()
    monkeypatch.setattr(window, '_interact', lambda action: errors.append(action))
    window.launch(operation, callbacks.append)
    window.cancel_operation()
    wait_jobs(app, window)
    assert not callbacks and not errors


def test_more_menu_retains_actions_diagnostics_and_busy_gates(gui, monkeypatch):
    from PySide6.QtGui import QDesktopServices
    app, window = gui
    page = window.repair_page
    opened = []
    assert page.logs_action.text() == tr('Open Agent log directory')
    assert page.app_logs_action.text() == tr('Open LALC log directory')
    monkeypatch.setattr(QDesktopServices, 'openUrl', lambda url: opened.append(url.toLocalFile()) or True)
    page.workspace_action.trigger()
    page.pages_action.trigger()
    page.logs_action.trigger()
    assert str(page.host.candidate) in opened
    assert str(window.service.data_root / 'pages') in opened
    assert str(page.host.conversation.log.path) in opened
    assert page.publish_action.isEnabled() and not page.copy_action.isEnabled()
    monkeypatch.setattr(page.more_menu, 'exec', lambda *args: None)
    page.open_more_menu()
    assert not page.error_action.isEnabled() and not page.error_actions
    selected = []
    monkeypatch.setattr(page.diagnostics, 'show_error', lambda: selected.append(page.diagnostics.errors.currentData()['message']))
    page.diagnostics.add_error({'message': 'first error'})
    page.diagnostics.add_error({'message': 'second error'})
    page.open_more_menu()
    assert len(page.error_actions) == 2
    page.error_actions[0].trigger()
    assert selected == ['first error'] and page.copy_action.isEnabled()
    calls = []
    monkeypatch.setattr(page.host, 'validate', lambda: calls.append('validate') or {'ok': True, 'errors': []})
    page.validate_action.trigger()
    wait_jobs(app, window)
    assert calls == ['validate']
    default = window.host.manager.default_manifest_id()
    page.publish_action.trigger()
    wait_jobs(app, window)
    assert window.host.manager.default_manifest_id() == default
    page.diff_action.trigger()
    wait_jobs(app, window)
    assert page.diff_dialog.isVisible()
    page.diff_dialog.close()
    with window.service.activity('Capture'):
        page.render(True)
        assert not page.publish_action.isEnabled() and not page.validate_action.isEnabled()
        assert page.more_button.isEnabled()
    page.render(False)
    page.new()
    assert not page.publish_action.isEnabled() and not page.workspace_action.isEnabled()


def test_collapsed_history_and_narrow_window_keep_composer_visible(gui):
    app, window = gui
    page = window.repair_page
    window.switchTo(page)
    window.resize(1250, 850)
    window.show()
    app.processEvents()
    assert page.sidebar.isVisible()
    before = page.chat.width()
    page.history_button.click()
    app.processEvents()
    assert page.sidebar.isHidden() and page.chat.width() > before
    bottom = page.composer.mapTo(page, page.composer.rect().bottomLeft()).y()
    for index in range(30):
        page.chat.add_message('Agent', f'message {index}\n' + 'content ' * 20, 1)
    app.processEvents()
    assert page.chat.verticalScrollBar().maximum() > 0
    assert page.composer.mapTo(page, page.composer.rect().bottomLeft()).y() == bottom
    window.resize(740, 600)
    app.processEvents()
    assert page.sidebar.isHidden()
    rect = page.send_button.rect()
    assert page.composer.rect().contains(page.send_button.mapTo(page.composer, rect.topLeft()))
    assert page.composer.rect().contains(page.send_button.mapTo(page.composer, rect.bottomRight()))
    assert not hasattr(window, 'status')


def test_settings_background_inherits_capture_background(gui):
    app, window = gui
    window.show()
    window.switchTo(window.capture_page)
    app.processEvents()
    def background(page):
        point = page.mapTo(window, QPoint(2, 2))
        pixmap = window.grab()
        ratio = pixmap.devicePixelRatio()
        return pixmap.toImage().pixelColor(round(point.x() * ratio), round(point.y() * ratio))
    capture = background(window.capture_page)
    window.switchTo(window.settings_view)
    app.processEvents()
    settings = background(window.settings_view)
    assert settings == capture
    assert not window.settings_page.autoFillBackground()
    assert not window.settings_view.viewport().autoFillBackground()


def test_format_retry_history_is_one_system_notice_without_internal_user_prompts(gui):
    from lalc.agent_repair import FORMAT_RETRY_PREFIX
    from lalc.agent_log import read_events
    app, window = gui
    page = window.repair_page
    chat = page.host.conversation
    chat.log.group = 1
    chat.append_user({'role': 'user', 'content': [{'type': 'text', 'text': 'Tell me what you can see'}]})
    details = {'message': 'invalid JSON', 'stage': 'final_answer', 'round': 1, 'raw_text': '```json\n{}\n```'}
    for attempt in range(2):
        chat.log.record({'type': 'repair_error', **details})
        chat.log.record({'type': 'final_answer_retry', 'diagnostics': details, 'requests_remaining': 18 - attempt})
        chat.append_user({'role': 'user', 'content': [{'type': 'text', 'text': FORMAT_RETRY_PREFIX + 'internal correction'}]})
    chat.log.record({'type': 'message_end', 'message': {'role': 'assistant', 'content': [
        {'type': 'text', 'text': '{"revise_success": false, "message": "I can read the Candidate."}'}]}})
    # 这是一个完成的真实轮次布局，恢复不应补造中断。
    (chat.log.root / 'round-1').mkdir()
    chat.log.save_json('round-1/result.json', {'status': 'completed'})
    page.reload_history()
    assert len([entry for entry in page.chat.entries if entry['role'] == '你']) == 1
    notices = [entry for entry in page.chat.entries if 'format_retry' in entry]
    assert len(notices) == 1 and notices[0]['format_retry'] == 2
    assert FORMAT_RETRY_PREFIX not in page.chat.toPlainText()
    assert page.diagnostics.errors.count() == 2
    assert 'I can read the Candidate.' in page.chat.toPlainText()
    events = list(read_events(chat.log.root / 'events.jsonl'))
    assert len([row for row in events if row['event']['type'] == 'final_answer_retry']) == 2
    assert sum(part.get('text', '').startswith(FORMAT_RETRY_PREFIX)
               for message in chat.history for part in message.get('content', [])) == 2


def test_live_retry_and_budget_failure_keep_one_diagnostic_per_failed_response(gui, monkeypatch):
    app, window = gui
    page = window.repair_page
    details = {'message': 'invalid JSON', 'stage': 'final_answer', 'round': 1, 'raw_text': 'not JSON'}
    for _ in range(2):
        page.show_event({'round': 1, 'event': {'type': 'repair_error', **details}})
        page.show_event({'round': 1, 'event': {'type': 'final_answer_retry', 'diagnostics': details, 'requests_remaining': 2}})
    assert page.diagnostics.errors.count() == 2
    assert len(page.chat.entries) == 1 and page.chat.entries[0]['format_retry'] == 2
    # 回合结果补充预算耗尽信息，不应把同一失败再显示成一个新错误。
    monkeypatch.setattr(page, 'reload_history', lambda: None)
    monkeypatch.setattr(page.diagnostics, 'show_error', lambda: None)
    page.answered({'reason': 'request_limit', 'requests': 20, 'diagnostics': {**details, 'budget_exhausted': True}})
    assert page.diagnostics.errors.count() == 2
    assert page.diagnostics.errors.itemData(1)['budget_exhausted']


def test_history_loads_latest_round_then_prepends_on_scroll_without_replay(gui, monkeypatch):
    app, window = gui
    page = window.repair_page
    log = page.host.conversation.log
    for number in range(1, 5):
        log.group = number
        (log.root / f'round-{number}').mkdir()
        log.record({'type': 'session_message', 'message': {'role': 'user', 'content': [
            {'type': 'text', 'text': f'question {number}\n' * 30}]}})
        for index in range(20):
            log.record({'type': 'tool_execution_start', 'toolCallId': f'call-{index}', 'toolName': 'read'})
            log.record({'type': 'tool_execution_end', 'toolCallId': f'call-{index}',
                        'toolName': 'read', 'result': {}})
        log.record({'type': 'message_end', 'message': {'role': 'assistant', 'content': [
            {'type': 'text', 'text': '{"revise_success":false,"message":"answer %s"}' % number}]}})
        log.save_json(f'round-{number}/result.json', {'status': 'completed', 'reason': 'answered'})
    window.show()
    window.switchTo(page)
    app.processEvents()
    renders = []
    original = page.chat.setHtml
    monkeypatch.setattr(page.chat, 'setHtml', lambda html: (renders.append(html), original(html))[-1])
    monkeypatch.setattr(page.session, 'restore', lambda *_: pytest.fail('视图不得重新恢复完整模型历史'))
    page.reload_history()
    assert {entry['round'] for entry in page.chat.entries} == {4}
    assert len(renders) <= 2
    assert page.history_rounds == [1, 2, 3]
    status = page.status.text(), page.status.toolTip()
    while page.history_rounds:
        previous = min(entry['round'] for entry in page.chat.entries)
        bar = page.chat.verticalScrollBar()
        assert bar.value() > 0
        bar.setValue(0)
        cursor = page.chat.cursorForPosition(QPoint(0, 0))
        old_block = cursor.block().text()
        wait_jobs(app, window)
        assert min(entry['round'] for entry in page.chat.entries) == previous - 1
        assert bar.value() > 0
        assert page.chat.cursorForPosition(QPoint(0, 0)).block().text() == old_block
        assert (page.status.text(), page.status.toolTip()) == status
    numbers = [entry['round'] for entry in page.chat.entries]
    assert numbers == sorted(numbers)
    assert len(page.chat.tools) == 80
    assert all(entry['status'] == '成功' for entry in page.chat.tools.values())
    assert all(len(activity['messages']) == 1 for number, activity in page.chat.activities.items() if number)
    assert page.chat.activity_round == 4
    page.new()
    assert not page.history_rounds and page.history_reader is None


def test_short_history_can_load_older_round_with_wheel(gui):
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QWheelEvent
    app, window = gui
    page = window.repair_page
    log = page.host.conversation.log
    for number in (1, 2):
        log.group = number
        log.record({'type': 'session_message', 'message': {'role': 'user', 'content': [
            {'type': 'text', 'text': f'question {number}'}]}})
    page.reload_history()
    assert page.chat.verticalScrollBar().value() == 0
    wheel = QWheelEvent(QPointF(10, 10), QPointF(10, 10), QPoint(), QPoint(0, 120),
                        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                        Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(page.chat.viewport(), wheel)
    wait_jobs(app, window)
    assert [entry['round'] for entry in page.chat.entries] == [1, 2]
    assert not page.history_rounds


def test_open_history_prepares_only_latest_round_in_background(gui, monkeypatch):
    from lalc.agent_log import RoundEventReader
    from lalc.developer_session import DeveloperSession
    app, window = gui
    page = window.repair_page
    log = page.host.conversation.log
    for number in (1, 2):
        log.group = number
        (log.root / f'round-{number}').mkdir()
        log.record({'type': 'session_message', 'message': {'role': 'user', 'content': [
            {'type': 'text', 'text': f'question {number}'}]}})
        log.save_json(f'round-{number}/result.json', {'status': 'completed', 'reason': 'answered'})
    main_thread = threading.get_ident()
    reads, restores = [], []
    original_read, original_restore = RoundEventReader.read, DeveloperSession.restore
    def read(self, number):
        reads.append((number, threading.get_ident()))
        return original_read(self, number)
    def restore(self, chat, *, load_history=True):
        restores.append(load_history)
        return original_restore(self, chat, load_history=load_history)
    monkeypatch.setattr(RoundEventReader, 'read', read)
    monkeypatch.setattr(DeveloperSession, 'restore', restore)
    identity = page.session.identity
    page.new()
    item = next(page.history.item(i) for i in range(page.history.count())
                if page.history.item(i).data(Qt.ItemDataRole.UserRole) == identity)
    page.open_session(item)
    wait_jobs(app, window)
    assert restores == [False]
    assert len(reads) == 1 and reads[0][0] == 2 and reads[0][1] != main_thread
    assert {entry['round'] for entry in page.chat.entries} == {2}
