"""用真实 pi 和本机 HTTP 替身覆盖持久压缩、目标、图片窗口和失败边界。

项目根目录运行：QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --run-agent-tests -q tests/test_context_compaction_agent.py
默认跳过，不调用真实模型或游戏。
"""

import asyncio
import json

import pytest

from lalc.agent_log import read_events
from lalc.agent_settings import save_options
from lalc.developer_session import DeveloperSession
from agent_test_server import agent_server
from test_agent_repair_agent import conversation, answer, tool
from test_image_attachments import make_images

pytestmark = pytest.mark.agent


def records(chat):
    return [row['event'] for row in read_events(chat.log.root / 'events.jsonl')]


@pytest.mark.parametrize('mode', ['ratio', 'fixed'])
def test_compaction_is_persisted_and_counted_separately(conversation, mode):
    original, options, state = conversation
    chat = DeveloperSession.create(original.host.service, original.host.manager.default_manifest_id(), entry='cli').conversation()
    save_options(chat.host.service.data_root, context_compaction_mode=mode)
    def respond(body):
        return answer('done') if body.get('tools') else ({'role': 'assistant', 'content': '已整理旧资料；继续当前任务。'}, 'stop')
    state['respond'] = respond
    result = asyncio.run(chat.run('请整理资料：' + 'historical material ' * 20000, options))
    assert result['status'] == 'completed', result
    assert result['requests'] == 1 and result['compaction_requests'] > 0
    events = records(chat)
    completed = [e for e in events if e['type'] == 'lalc_compaction' and e['phase'] == 'completed']
    assert completed and completed[-1]['after'] < 50000
    assert completed[-1]['target'] == (int(completed[-1]['before'] * .3) if mode == 'ratio' else 20000)
    path = chat.session.path / 'pi/session.jsonl'
    assert any(json.loads(line)['type'] == 'compaction' for line in path.read_text().splitlines())
    chat.host.service.pi_process.close()
    restored = DeveloperSession(chat.host.service, chat.session.identity, entry='cli').conversation()
    result = asyncio.run(restored.run('继续下一步', options))
    assert result['status'] == 'completed', result
    assert 'historical material ' * 100 not in json.dumps(state['calls'][-1])
    assert '已整理旧资料' in json.dumps(state['calls'][-1], ensure_ascii=False)


def test_tool_loop_can_compact_without_losing_tool_pair(conversation):
    chat, options, state = conversation
    count = 0
    def respond(body):
        nonlocal count
        if not body.get('tools'):
            return {'role': 'assistant', 'content': '已读取工作流源码。'}, 'stop'
        count += 1
        if count == 1:
            return tool('asset_tree', {})
        return answer()
    state['respond'] = respond
    # 单条工具结果可越过压缩线，必须在下一请求前处理。
    chat.tools.asset_tree = lambda **_: chat.tools.text({'large': 'tool-result ' * 30000})
    result = asyncio.run(chat.run('读取并总结', options))
    assert result['status'] == 'completed', result
    assert any(e['type'] == 'lalc_compaction' and e['phase'] == 'completed' for e in records(chat))
    for body in state['calls']:
        calls = set()
        for message in body['messages']:
            calls.update(call['id'] for call in message.get('tool_calls', []))
            if message['role'] == 'tool':
                assert message['tool_call_id'] in calls


def test_old_images_are_not_sent_and_can_be_read_by_id(conversation, tmp_path):
    original, options, state = conversation
    chat = DeveloperSession.create(original.host.service, original.host.manager.default_manifest_id(), entry='cli').conversation()
    paths = make_images(tmp_path, ('PNG', 'JPEG'))
    result = asyncio.run(chat.run('看这些图片', options, images=paths))
    assert result['status'] == 'completed', result
    session_id = chat.session.identity
    result = asyncio.run(chat.run('只看文字', options))
    assert result['status'] == 'completed', result
    body = json.dumps(state['calls'][-1])
    assert 'data:image/' not in body and 'image_id=' in body
    from lalc.agent_history import AgentHistory
    page, _ = AgentHistory(chat.host.service.data_root).read(session_id, round_numbers=[1])
    image_id = next(event['images'][0] for event in page['events'] if event['images'])
    count = 0
    def respond(body):
        nonlocal count
        count += 1
        return tool('read_agent_session', {'session_id': session_id, 'image_id': image_id}) if count == 1 else answer()
    state['respond'] = respond
    result = asyncio.run(chat.run('回看旧图', options))
    assert result['status'] == 'completed', result
    assert 'data:image/' in json.dumps(state['calls'][-1])


def test_image_window_keeps_latest_blocks(conversation, tmp_path):
    chat, options, state = conversation
    save_options(chat.host.service.data_root, context_image_limit=1)
    result = asyncio.run(chat.run('看最新一张', options, images=make_images(tmp_path, ('PNG', 'JPEG'))))
    assert result['status'] == 'completed', result
    assert json.dumps(state['calls'][-1]).count('data:image/') == 1


@pytest.mark.parametrize("failure", ["length", "empty", "http"])
def test_summary_failure_does_not_commit_compaction(conversation, failure):
    chat, options, state = conversation
    state['respond'] = lambda body: ({'role': 'assistant', 'content': '' if failure == 'empty' else 'partial'},
                                      'length' if failure == 'length' else 'stop')
    if failure == 'http':
        state['status'] = 503
    result = asyncio.run(chat.run('资料：' + 'historical material ' * 20000, options))
    assert result['status'] == 'incomplete'
    assert result['requests'] == 0
    path = chat.log.root / 'pi/session.jsonl'
    assert not path.exists() or not any(json.loads(line)['type'] == 'compaction' for line in path.read_text().splitlines())


def test_legacy_messages_migrate_once_without_old_image_upload(conversation, tmp_path):
    import base64
    original, options, state = conversation
    session = DeveloperSession.create(original.host.service, original.host.manager.default_manifest_id(), entry='cli')
    chat = session.conversation()
    path = make_images(tmp_path, ('PNG',))[0]
    chat.append_user({'role': 'user', 'content': [{'type': 'text', 'text': 'legacy request'},
        {'type': 'image', 'mimeType': 'image/png', 'data': base64.b64encode(path.read_bytes()).decode()}], 'timestamp': 1})
    assert not (session.path / 'pi/session.jsonl').exists()
    for request in ('first continuation', 'second continuation'):
        result = asyncio.run(chat.run(request, options))
        assert result['status'] == 'completed', result
        body = json.dumps(state['calls'][-1])
        assert body.count('legacy request') == 1 and 'image_id=' in body
        assert 'data:image/' not in body
    assert (session.path / 'pi/initialized').is_file()


def test_deepseek_uses_400k_instead_of_local_50k(conversation):
    chat, options, state = conversation
    options.provider, options.model = 'deepseek', 'deepseek-flash'
    state['models'] = [{'id': 'deepseek-flash'}]
    result = asyncio.run(chat.run('history ' * 30000, options))
    assert result['status'] == 'completed', result
    assert result['compaction_requests'] == 0
    gauges = [e for e in records(chat) if e['type'] == 'lalc_context_usage']
    assert gauges and all(e['limit'] == 400000 for e in gauges)
    assert any(e['tokens'] > 50000 for e in gauges)


def test_cancelled_initial_compaction_can_resume_without_replaying(conversation):
    chat, options, state = conversation
    state['block'] = True
    async def cancel():
        task = asyncio.create_task(chat.run('history ' * 30000, options))
        assert await asyncio.to_thread(state['started'].wait, 5)
        task.cancel()
        return await task
    result = asyncio.run(cancel())
    assert result['status'] == 'cancelled'
    state['block'] = False
    state['release'].set()
    state['respond'] = lambda body: answer() if body.get('tools') else ({'role': 'assistant', 'content': '已总结旧资料。'}, 'stop')
    result = asyncio.run(chat.run('continue after cancellation', options))
    assert result['status'] == 'completed', result
    assert result['requests'] == 1


def test_known_connection_key_is_redacted_before_pi_persistence(conversation):
    chat, options, state = conversation
    key = 'lalc-test-private-key'
    path = chat.host.candidate / 'steps.total.py'
    path.write_text(path.read_text() + '\n# ' + key)
    from test_agent_repair_agent import script
    script(state, [tool('read', {'path': 'steps.total.py'}), answer()])
    result = asyncio.run(chat.run('inspect ' + key, options, key=key))
    assert result['status'] == 'completed', result
    assert key not in json.dumps(state['calls'])
    assert '[REDACTED]' in json.dumps(state['calls'])
    for path in (chat.log.root / 'pi').rglob('*'):
        if path.is_file():
            assert key.encode() not in path.read_bytes()
