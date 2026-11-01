"""覆盖生成过程的折叠、消息保留、历史恢复与脱敏通知，不启动 Agent。

项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_raw_output.py
"""

from types import SimpleNamespace

from PySide6.QtCore import QUrl

import pytest

from lalc.agent_repair import RepairLog
from test_developer_gui import gui


def raw(page, content):
    if not page.host.conversation.log.group:
        page.host.conversation.log.group = 1
    page.show_event({'round': page.host.conversation.log.group, 'event': {'type': 'raw_output', 'content': content}})


def test_raw_output_collapsed_streams_and_preserves_choice(gui):
    _, window = gui
    page = window.repair_page
    page._round_running = True
    raw(page, [{'type': 'text', 'text': '<b>literal</b>'}])
    assert page.chat.activity()['pending'] and not page.chat.activity()['expanded']
    assert '<b>literal</b>' not in page.chat.toPlainText()
    page.chat.open_link(QUrl(f'raw:{page.chat.activity_round}'))
    assert '<b>literal</b>' in page.chat.toPlainText()
    raw(page, [{'type': 'thinking', 'thinking': 'checking'},
               {'type': 'toolCall', 'name': 'read', 'partialArgs': '{"path": "st', 'arguments': {}}])
    page.flush_raw_output()
    assert page.chat.activity()['expanded']
    assert 'checking' in page.chat.toPlainText() and '{"path": "st' in page.chat.toPlainText()
    page.chat.open_link(QUrl(f'raw:{page.chat.activity_round}'))
    raw(page, [{'type': 'text', 'text': 'next chunk'}])
    assert not page.chat.activity()['expanded'] and 'next chunk' not in page.chat.toPlainText()
    assert not page.chat.entries
    page.show_event({'round': 1, 'event': {'type': 'message_end', 'message': {'role': 'assistant'}}})
    assert not page.chat.activity()['pending'] and not page.raw_pending
    assert not page.raw_timer.isActive()
    raw(page, [{'type': 'text', 'text': 'new message'}])
    assert page.chat.activity()['pending'] and not page.chat.activity()['expanded']


@pytest.mark.parametrize('kind', ['repair_error', 'round_finished', 'round_interrupted',
                                  'final_answer_retry', 'agent_settled', 'tool_execution_start'])
def test_terminal_event_clears_pending_render(gui, kind):
    _, window = gui
    page = window.repair_page
    page._round_running = True
    raw(page, [{'type': 'text', 'text': 'partial'}])
    page.chat.open_link(QUrl(f'raw:{page.chat.activity_round}'))
    raw(page, [{'type': 'text', 'text': 'pending'}])
    assert page.raw_timer.isActive()
    value = {'type': kind, 'message': 'failed', 'requests_remaining': 2,
             'toolCallId': 'read-1', 'toolName': 'read'}
    page.show_event({'round': 1, 'event': value})
    assert not page.chat.activity()['pending'] and not page.raw_timer.isActive()
    assert not page.raw_pending and not page.chat.activity()['pending']


@pytest.mark.parametrize('boundary', ['replay', 'cancel', 'closing', 'idle'])
def test_stale_stream_does_not_open(gui, boundary):
    _, window = gui
    page = window.repair_page
    page._round_running = boundary != 'idle'
    page._replaying = boundary == 'replay'
    window.closing = boundary == 'closing'
    if boundary == 'cancel':
        window.jobs.append(SimpleNamespace(cancel_requested=True))
    try:
        raw(page, [{'type': 'text', 'text': 'stale'}])
        assert not page.chat.activity()['pending'] and not page.raw_pending
    finally:
        page._replaying = False
        window.closing = False
        window.jobs.clear()


def test_idle_cleanup_and_history_do_not_restore_unfinished_stream(gui):
    _, window = gui
    page = window.repair_page
    page._round_running = True
    raw(page, [{'type': 'text', 'text': 'partial'}])
    page.render(False)
    assert not page.chat.activity()['pending'] and not page.raw_pending
    page.reload_history()
    assert not page.chat.activity()['pending']


def test_stream_redacts_accumulated_snapshot_without_persistence(tmp_path):
    events = []
    log = RepairLog(tmp_path, key='test-secret', on_event=events.append)
    log.group = 2
    for event in [
        {'type': 'text_delta', 'contentIndex': 0, 'delta': 'test-'},
        {'type': 'text_delta', 'contentIndex': 0, 'delta': 'secret'},
        {'type': 'toolcall_start', 'contentIndex': 1, 'toolName': 'read'},
        {'type': 'toolcall_delta', 'contentIndex': 1, 'delta': '{"path": "st'},
    ]:
        log.stream({'type': 'message_update', 'assistantMessageEvent': event})
    assert events[-1] == {'round': 2, 'event': {'type': 'raw_output', 'content': [
        {'type': 'text', 'text': '[REDACTED]'},
        {'type': 'toolCall', 'name': 'read', 'partialArgs': '{"path": "st'}]}}
    assert not (log.path / 'events.jsonl').exists()
    log.record({'type': 'message_end', 'message': {'role': 'assistant'}})
    log.stream({'assistantMessageEvent': {'type': 'text_delta', 'contentIndex': 0, 'delta': 'next'}})
    assert events[-1]['event']['content'] == [{'type': 'text', 'text': 'next'}]


def test_status_and_raw_are_inline_before_agent_content(gui):
    """顶部状态跟随所属回复，原始输出展开不跑到聊天页底部。"""
    _, window = gui
    page = window.repair_page
    page.host.conversation.log.group = 2
    page.chat.add_message('你', 'previous question', 1)
    page.chat.add_message('Agent', 'previous answer', 1)
    page.chat.add_message('你', 'current question', 2)
    page.chat.upsert_tool(2, 'read', 'read', 'tool_execution_start', {})
    page.chat.add_message('Agent', 'current answer', 2)
    page.set_status('Reading source', 'status details')
    page._round_running = True
    raw(page, [{'type': 'text', 'text': '<literal raw>'}])
    assert page.status.isHidden()
    text = page.chat.toPlainText()
    assert text.index('current question') < text.index('Reading source') < text.index('Tool:') < text.index('current answer')
    assert '<literal raw>' not in text
    page.chat.open_link(QUrl(f'raw:{page.chat.activity_round}'))
    text = page.chat.toPlainText()
    assert text.index('Reading source') < text.index('<literal raw>') < text.index('Tool:')
    page.clear_raw_output()
    assert 'Reading source' in page.chat.toPlainText() and '<literal raw>' not in page.chat.toPlainText()
    page.set_status('Round complete')
    assert 'Round complete' in page.chat.toPlainText() and 'Reading source' not in page.chat.toPlainText()


def test_completed_generation_survives_answer_followup_and_history(gui):
    """最终回答后每轮独立保留生成过程，重开仅从完整消息恢复并默认收起。"""
    _, window = gui
    page = window.repair_page
    log = page.host.conversation.log
    log.group = 1
    (log.root / 'round-1').mkdir()
    log.record({'type': 'session_message', 'message': {'role': 'user', 'content': [
        {'type': 'text', 'text': 'first question'}]}})
    page.chat.add_message('你', 'first question', 1)
    page._round_running = True
    page.set_status('responding')
    raw(page, [{'type': 'thinking', 'thinking': 'earlier reasoning'}])
    page.chat.open_link(QUrl('raw:1'))
    messages = [
        {'role': 'assistant', 'content': [{'type': 'thinking', 'thinking': 'earlier reasoning'},
            {'type': 'toolCall', 'id': 'read-1', 'name': 'read', 'arguments': {'path': 'step.py'}}]},
        {'role': 'assistant', 'content': [{'type': 'thinking', 'thinking': 'final reasoning'},
            {'type': 'text', 'text': '{"revise_success":false,"message":"final business answer"}'}]},
    ]
    for message in messages:
        value = {'type': 'message_end', 'message': message}
        log.record(value)
        page.show_event({'round': 1, 'event': value})
    result = {'status': 'completed', 'reason': 'answered', 'round': 1, 'requests': 2,
              'answer': {'revise_success': False, 'message': 'final business answer'}}
    log.save_json('round-1/result.json', result)
    log.record({'type': 'round_finished', **result})
    page.answered(result)
    activity = page.chat.activity(1)
    assert activity['expanded'] and len(activity['messages']) == 2 and not activity['pending']
    text = page.chat.toPlainText()
    assert text.index('earlier reasoning') < text.index('final reasoning') < text.rindex('final business answer')
    assert 'step.py' in text

    log.group = 2
    page.chat.add_message('你', 'next question', 2)
    page.set_status('next response')
    raw(page, [{'type': 'text', 'text': 'second partial'}])
    assert len(page.chat.activity(1)['messages']) == 2
    assert not page.chat.activity(2)['expanded']
    page.chat.open_link(QUrl('raw:1'))
    assert not page.chat.activity(1)['expanded'] and not page.chat.activity(2)['expanded']
    assert 'earlier reasoning' not in page.chat.toPlainText()
    page.clear_raw_output()
    page.reload_history()
    assert len(page.chat.activity(1)['messages']) == 2 and not page.chat.activity(1)['expanded']
    assert 'earlier reasoning' not in page.chat.toPlainText()
    page.chat.open_link(QUrl('raw:1'))
    assert 'earlier reasoning' in page.chat.toPlainText() and 'final reasoning' in page.chat.toPlainText()


def test_partial_cleanup_preserves_completed_messages(gui):
    _, window = gui
    page = window.repair_page
    page.host.conversation.log.group = 1
    page.chat.remember_message(1, [{'type': 'text', 'text': 'completed earlier output'}])
    page.chat.open_link(QUrl('raw:1'))
    page._round_running = True
    raw(page, [{'type': 'text', 'text': 'cancelled partial'}])
    page.clear_raw_output()
    assert page.chat.activity(1)['expanded']
    assert page.chat.activity(1)['messages'] == ['completed earlier output']
    assert 'completed earlier output' in page.chat.toPlainText()
    assert 'cancelled partial' not in page.chat.toPlainText()
