"""覆盖历史状态恢复、瞬时提示隔离及实时取消收尾；不启动模型或 Agent 工具循环。

项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_workbench_status.py
"""

import asyncio
import threading

import pytest
from PySide6.QtCore import Qt

from lalc.agent_log import read_json
from lalc.gui import MainWindow
from lalc.i18n import tr
from test_developer_gui import gui, wait_jobs


@pytest.mark.parametrize('reopen', [False, True])
@pytest.mark.parametrize('result,expected', [
    ({'status': 'completed', 'reason': 'answered'}, 'Round complete'),
    ({'status': 'cancelled', 'reason': 'user_cancelled'}, 'Round cancelled'),
    ({'status': 'incomplete', 'reason': 'request_limit'}, 'Round incomplete'),
    ({'status': 'incomplete', 'reason': 'error', 'error': 'provider failed'}, 'Error: '),
    (None, 'Interrupted; results may be unknown. No operations replayed.'),
])
def test_open_history_restores_latest_round_status(gui, monkeypatch, reopen, result, expected):
    """切换和重建 GUI 均取最新轮结果，不采用旧事件尾部或全局 result.json。"""
    app, original = gui
    session = original.repair_page.session
    log = session.host.conversation.log
    for number in (1, 2):
        log.group = number
        (log.root / f'round-{number}').mkdir()
        log.record({'type': 'lalc_request', 'requests': number + 5, 'request_limit': 20})
    old = {'status': 'cancelled', 'reason': 'user_cancelled', 'requests': 1}
    log.save_json('round-1/result.json', old)
    log.save_json('result.json', old)
    if result is not None:
        log.save_json('round-2/result.json', {**result, 'requests': 7})
    log.group = 1
    log.record({'type': 'round_finished', **old})

    def forbidden(*args, **kwargs):
        pytest.fail('打开历史不得请求模型、执行工具或弹出历史错误')

    monkeypatch.setattr('lalc.agent_repair.configured_pi', forbidden)
    monkeypatch.setattr('lalc.repair_tools.RepairTools.call', forbidden)
    monkeypatch.setattr('lalc.gui.ErrorDialog.open', forbidden)
    window = original
    if reopen:
        original.close()
        window = MainWindow(original.service)
    try:
        page = window.repair_page
        page.status.setText('old progress')
        page.refresh_sessions()
        item = next(page.history.item(i) for i in range(page.history.count())
                    if page.history.item(i).data(Qt.ItemDataRole.UserRole) == session.identity)
        page.open_session(item)
        wait_jobs(app, window)
        summary = tr(expected) + ('provider failed' if result and result.get('error') else '')
        assert page.status.text() == summary
        assert page.status.toolTip() == tr('{0}; actual requests: {1}').format(summary, 7)
        assert not window.jobs and window.service.state['activity'] is None and not page._round_running
        assert read_json(log.root / 'round-2/result.json')['status'] == (result['status'] if result else 'interrupted')
        page.message.setPlainText('continue')
        assert page.send_button.isEnabled()
    finally:
        if reopen:
            window.close()
            app.processEvents()


@pytest.mark.parametrize('event', [
    {'type': 'lalc_request', 'requests': 2},
    {'type': 'final_answer_retry', 'requests_remaining': 2},
    {'type': 'tool_execution_start', 'toolCallId': 'call', 'toolName': 'read'},
    {'type': 'repair_tool', 'toolCallId': 'call', 'name': 'read',
     'result': {'isError': True, 'details': {'message': 'read failed'}}},
])
@pytest.mark.parametrize('replaying', [False, True])
def test_history_events_preserve_status_but_live_events_update(gui, event, replaying):
    _, window = gui
    page = window.repair_page
    page.status.setText('current status')
    page.status.setToolTip('current details')
    page._replaying = replaying
    try:
        page.show_event({'round': 1, 'event': event})
    finally:
        page._replaying = False
    if replaying:
        assert page.status.text() == 'current status' and page.status.toolTip() == 'current details'
    else:
        assert page.status.text() != 'current status'
    if event['type'] in {'tool_execution_start', 'repair_tool'}:
        assert len(page.chat.tools) == 1
    if event['type'] == 'repair_tool':
        assert page.diagnostics.errors.count() == 1
    if event['type'] == 'final_answer_retry':
        assert page.chat.entries[-1]['format_retry'] == 1


@pytest.mark.parametrize('action', ['reload', 'new', 'switch'])
def test_empty_history_clears_previous_status_and_tooltip(gui, action):
    _, window = gui
    page = window.repair_page
    page.status.setText('old status')
    page.status.setToolTip('old details')
    if action == 'switch':
        from lalc.developer_session import DeveloperSession
        session = DeveloperSession.create(window.service, None, mode='Construct', entry='gui')
        session.conversation()
        page.activate_session(session)
    elif action == 'new':
        page.new()
    else:
        page.reload_history()
    assert not page.status.text() and not page.status.toolTip()


def test_history_refresh_and_late_event_preserve_exit_notice(gui):
    _, window = gui
    page = window.repair_page
    window.closing = True
    try:
        page.status.setText('stopping')
        page.status.setToolTip('cleanup pending')
        page.reload_history()
        page.show_event({'round': 1, 'event': {'type': 'lalc_request', 'requests': 2}})
        assert page.status.text() == 'stopping' and page.status.toolTip() == 'cleanup pending'
    finally:
        window.closing = False


def test_history_refresh_keeps_active_wait_and_cancellation_until_cleanup(gui):
    app, window = gui
    page = window.repair_page
    entered, cleaned = threading.Event(), threading.Event()

    async def operation():
        with window.service.activity('Agent'):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                await asyncio.sleep(.05)
                cleaned.set()

    page._round_running = True
    window.launch(operation)
    try:
        assert entered.wait(1)
        page.status.setText(tr('Waiting for feedback'))
        page.status.setToolTip('waiting')
        page.reload_history()
        assert page.status.text() == tr('Waiting for feedback') and page.status.toolTip() == 'waiting'
        assert window.jobs and window.service.state['activity'] == 'Agent'
        assert not page.history.isEnabled() and not page.new_button.isEnabled()
        window.cancel_operation()
        assert page.status.text() == tr('Cancelling…')
        page.show_event({'round': 1, 'event': {'type': 'lalc_request', 'requests': 2}})
        assert page.status.text() == tr('Cancelling…')
        assert page.status.toolTip() == tr('Cancelling…')
    finally:
        if any(not job.cancel_requested for job in window.jobs):
            window.cancel_operation()
        wait_jobs(app, window)
    assert cleaned.is_set() and window.service.state['activity'] is None
    assert page.status.text() == tr('Round cancelled')
