"""覆盖人工反馈的权限、空确认、跳过、取消、迟到答复与非模态 GUI。

项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_human_feedback.py
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading
import time

import pytest

from lalc.agent_log import read_json
from lalc.agent_policy import allowed_tools
from lalc.agent_repair import RepairLog
from lalc.human_feedback import FeedbackRequest
from lalc.repair_tools import RepairTools
from test_developer_gui import gui, wait_jobs


def test_feedback_permissions_validation_and_redaction(tmp_path):
    log = RepairLog(tmp_path, 'known-secret')
    for mode in ('Construct', 'Repair'):
        assert 'request_feedback' in allowed_tools(mode, 'gui')
    assert 'request_feedback' not in allowed_tools('Repair', 'cli')
    tools = RepairTools(tmp_path, log)
    tools.on_feedback = lambda request: pytest.fail('CLI 不得进入反馈界面')
    assert read_json(tools.call('request_feedback', {'message': 'hello'}))['isError']
    tools.allowed = allowed_tools('Repair', 'gui')
    for message in ('', ' ', None, 1):
        assert read_json(tools.call('request_feedback', {'message': message}))['isError']
    tools.on_feedback = None
    assert read_json(tools.call('request_feedback', {'message': 'hello'}))['isError']
    tools.on_feedback = lambda request: request.finish('confirmed', 'known-secret')
    result = read_json(tools.call('request_feedback', {'message': 'known-secret'}))
    assert result['details']['status'] == 'confirmed'
    assert 'known-secret' not in str(result)
    assert 'known-secret' not in (log.path / 'events.jsonl').read_text()


def test_cancel_wakes_tool_and_invalidates_late_response(tmp_path):
    tools = RepairTools(tmp_path, RepairLog(tmp_path), allowed=allowed_tools('Repair', 'gui'))
    ready = threading.Event()
    requests = []
    def show(request):
        requests.append(request)
        ready.set()
    tools.on_feedback = show
    with ThreadPoolExecutor() as pool:
        pending = pool.submit(tools.call, 'request_feedback', {'message': 'wait'})
        try:
            assert ready.wait(2)
            assert not pending.done()
        finally:
            tools.cancelled.set()
        assert read_json(pending.result(timeout=2))['isError']
    assert requests[0].done.is_set()
    assert not requests[0].finish('confirmed', 'late')
    current = FeedbackRequest('next', ('session', 2, 1))
    assert current.finish('confirmed', '')
    assert not current.finish('skipped')
    assert current.result == {'status': 'confirmed', 'text': ''}


def test_interrupted_feedback_is_unknown_without_replaying(gui):
    from test_developer_session import interrupted
    from lalc.developer_session import DeveloperSession
    _, window = gui
    session = window.repair_page.session
    chat = session.host.conversation
    interrupted(chat, ('request_feedback',))
    restored = DeveloperSession(window.service, session.identity, entry='gui').conversation()
    result = next(item for item in restored.history if item.get('toolName') == 'request_feedback')
    assert result['isError'] and result['details']['outcome'] == 'unknown'
    assert read_json(chat.log.root / 'round-1/result.json')['status'] == 'interrupted'
    assert not hasattr(window.repair_page, 'feedback_dialog')


def start_wait(gui):
    app, window = gui
    chat = window.repair_page.host.conversation
    request = FeedbackRequest('请切到准备界面 <b>原文显示</b>', (chat.log.identity, chat.log.group, 1))
    async def operation():
        with window.service.activity('Agent'):
            window.feedback_requested.emit(request)
            try:
                while not request.done.is_set():
                    await asyncio.sleep(.01)
                return request.result
            finally:
                request.close()
    window.launch(operation)
    until = time.monotonic() + 3
    while not hasattr(window.repair_page, 'feedback_dialog') and time.monotonic() < until:
        app.processEvents()
        time.sleep(.005)
    assert hasattr(window.repair_page, 'feedback_dialog')
    return request, window.repair_page.feedback_dialog


@pytest.mark.parametrize('action,text,status', [('confirm', '', 'confirmed'), ('confirm', 'done', 'confirmed'),
                                              ('skip', 'ignored', 'skipped'), ('close', '', 'skipped'),
                                              ('escape', '', 'skipped')])
def test_nonmodal_feedback_controls(gui, action, text, status):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QPlainTextEdit
    app, window = gui
    request, dialog = start_wait(gui)
    assert dialog.windowModality() == Qt.WindowModality.NonModal
    assert not dialog.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert app.activeModalWidget() is None
    assert request.message in [field.toPlainText() for field in dialog.findChildren(QPlainTextEdit)]
    assert not window.repair_page.new_button.isEnabled()
    assert not window.capture_page.capture_button.isEnabled()
    dialog.reply.setPlainText(text)
    if action == 'escape':
        QTest.keyClick(dialog, Qt.Key.Key_Escape)
    elif action == 'close':
        dialog.close()
    else:
        getattr(dialog, action).click()
    wait_jobs(app, window)
    assert request.result == {'status': status, 'text': text if status == 'confirmed' else ''}
    assert window.service.state['activity'] is None


@pytest.mark.parametrize('cancel_from', ['dialog', 'main', 'exit'])
def test_feedback_cancel_and_main_exit(gui, monkeypatch, cancel_from):
    from PySide6.QtWidgets import QMessageBox
    app, window = gui
    request, dialog = start_wait(gui)
    if cancel_from == 'exit':
        monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.No)
        assert not window.close()
        assert not request.done.is_set() and dialog.isVisible()
        monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Yes)
        assert not window.close()
    elif cancel_from == 'main':
        window.cancel_operation()
    else:
        dialog.cancel.click()
    wait_jobs(app, window)
    assert request.done.is_set() and request.result is None
    assert not request.finish('confirmed', 'late')
    window.repair_page.show_feedback(request)
    assert not request.finish('skipped')


def test_queued_old_session_request_cannot_replace_current_wait(gui):
    app, window = gui
    request, dialog = start_wait(gui)
    try:
        stale = FeedbackRequest('old session', ('another-session', request.identity[1], 1))
        window.repair_page.show_feedback(stale)
        assert stale.done.is_set() and stale.result is None
        assert window.repair_page.feedback_dialog is dialog
        assert not request.done.is_set()
    finally:
        window.cancel_operation()
        queued = FeedbackRequest('queued during cancellation', request.identity)
        window.repair_page.show_feedback(queued)
        assert queued.done.is_set() and queued.result is None
        assert window.repair_page.feedback_dialog is dialog
        wait_jobs(app, window)


def test_late_cancel_from_completed_dialog_does_not_cancel_next_work(gui, monkeypatch):
    from lalc.developer_gui import FeedbackDialog
    _, window = gui
    request = FeedbackRequest('old request', ('old', 1, 1))
    dialog = FeedbackDialog(request, window)
    request.finish('confirmed', '')
    monkeypatch.setattr(window, 'cancel_operation', lambda: pytest.fail('旧窗口不得取消后续工作'))
    dialog.cancel_round()
    assert request.result == {'status': 'confirmed', 'text': ''}
