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
    state['usage'] = {'prompt_tokens': 11, 'completion_tokens': 3, 'total_tokens': 14}
    result = asyncio.run(chat.run('请整理资料：' + 'historical material ' * 20000, options))
    assert result['status'] == 'completed', result
    assert result['requests'] == 1 and result['compaction_requests'] > 0
    assert result['requests_with_token_usage'] == result['requests'] + result['compaction_requests']
    assert result['reported_tokens'] == result['requests_with_token_usage'] * 14
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
    assert result['requests_with_token_usage'] == 1 and result['reported_tokens'] == 14
    assert 'historical material ' * 100 not in json.dumps(state['calls'][-1])
    assert '已整理旧资料' in json.dumps(state['calls'][-1], ensure_ascii=False)


@pytest.mark.parametrize('with_image', [False, True])
def test_tool_loop_can_compact_without_losing_tool_pair(conversation, tmp_path, with_image):
    import base64
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
    payload = chat.tools.text({'large': '工具正文标记' + '材料' * 30000})
    if with_image:
        path = make_images(tmp_path, ('PNG',))[0]
        payload['content'].append({'type': 'image', 'mimeType': 'image/png', 'data': base64.b64encode(path.read_bytes()).decode()})
    chat.tools.asset_tree = lambda **_: payload
    result = asyncio.run(chat.run('读取并总结', options))
    assert result['status'] == 'completed', result
    events = records(chat)
    compaction = next(e for e in events if e['type'] == 'lalc_compaction' and e['phase'] == 'completed')
    assert compaction['before'] < 120000
    summaries = [body for body in state['calls'] if not body.get('tools')]
    assert sum(json.dumps(body, ensure_ascii=False).count('工具正文标记') for body in summaries) == 1
    raw = next(e['result'] for e in events if e['type'] == 'repair_tool' and e['name'] == 'asset_tree')
    assert raw['details'] == payload['details']
    assert any(e['type'] == 'extension_ui_request' and e.get('title', '').startswith('lalc.image_ids:')
               for e in records(chat)) == with_image
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


@pytest.mark.parametrize('source', ['host', 'native'])
def test_tool_images_sync_ids_in_memory_and_survive_restart(conversation, tmp_path, source):
    """宿主与原生图片均先同步编号；窗口淘汰、进程复用和重启保持可回读。"""
    import base64
    import hashlib
    import shutil
    from lalc.agent_history import AgentHistory
    from test_agent_repair_agent import script

    original, options, state = conversation
    session = DeveloperSession.create(original.host.service, original.host.manager.default_manifest_id(), entry='cli')
    chat = session.conversation()
    save_options(chat.host.service.data_root, context_image_limit=1)
    paths = make_images(tmp_path, ('PNG', 'JPEG'))
    if source == 'native':
        names = ['probe.png', 'probe.jpg']
        for path, name in zip(paths, names):
            shutil.copyfile(path, chat.host.candidate / name)
        script(state, [*(tool('read', {'path': name}) for name in names), answer()])
    else:
        images = [{'type': 'image', 'mimeType': mime, 'data': base64.b64encode(path.read_bytes()).decode()}
                  for path, mime in zip(paths, ('image/png', 'image/jpeg'))]
        chat.tools.asset_tree = lambda **_: {'content': images}
        script(state, [tool('asset_tree', {}), answer()])

    result = asyncio.run(chat.run('读取图片', options))
    assert result['status'] == 'completed', result
    assert json.dumps(state['calls'][-1]).count('data:image/') == 1
    events = records(chat)
    queries = [event for event in events if event['type'] == 'extension_ui_request'
               and event.get('title', '').startswith('lalc.image_ids:')]
    assert queries
    history = AgentHistory(chat.host.service.data_root)
    for path in paths:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        _, content = history.read(session.identity, image_id=chat.log.image_ids[digest])
        assert content == path.read_bytes()
    first_pid = next(event['pid'] for event in events if event['type'] == 'pi_process')
    assert not list(chat.host.service.data_root.rglob('image-index.json'))

    for restart in (False, True):
        if restart:
            chat.host.service.pi_process.close()
        chat = DeveloperSession(chat.host.service, session.identity, entry='cli').conversation()
        state['respond'] = lambda body: answer()
        result = asyncio.run(chat.run('继续文字对话', options))
        assert result['status'] == 'completed', result
        assert 'data:image/' not in json.dumps(state['calls'][-1])
        assert 'image_id=' in json.dumps(state['calls'][-1])
        latest = records(chat)
        process = [event for event in latest if event['type'] == 'pi_process'][-1]
        if not restart:
            assert process['reused'] and process['pid'] == first_pid
        assert not any(event['type'] == 'extension_ui_request' and event.get('title', '').startswith('lalc.image_ids:')
                       for event in latest[len(events):])
        events = latest


@pytest.mark.parametrize('failure', ['missing', 'invalid'])
def test_invalid_image_sync_does_not_commit_context_edits(conversation, tmp_path, monkeypatch, failure):
    """同步失败直接报告本地上下文错误，不提交不可回读的引用或重复请求模型。"""
    import base64
    from test_agent_repair_agent import script
    chat, options, state = conversation
    save_options(chat.host.service.data_root, context_image_limit=1)
    images = [{'type': 'image', 'mimeType': mime, 'data': base64.b64encode(path.read_bytes()).decode()}
              for path, mime in zip(make_images(tmp_path, ('PNG', 'JPEG')), ('image/png', 'image/jpeg'))]
    chat.tools.asset_tree = lambda **_: {'content': images}
    monkeypatch.setattr(chat.log, 'image_references', lambda hashes: {} if failure == 'missing' else {h: 'bad-id' for h in hashes})
    script(state, [tool('asset_tree', {}), answer()])
    result = asyncio.run(chat.run('读取图片', options))
    assert result['status'] == 'incomplete', result
    assert '图片编号同步响应不完整' in result['error']
    assert len(state['calls']) == 1
    entries = [json.loads(line) for line in (chat.log.root / 'pi/session.jsonl').read_text().splitlines()]
    assert not any(entry['type'] == 'context_edit' for entry in entries)


def test_cancel_image_sync_can_resume_without_replaying_tool(conversation, tmp_path):
    """编号同步期间取消会丢弃进程，续聊从日志恢复图片编号且不重放工具。"""
    import base64
    from test_agent_repair_agent import script
    chat, options, state = conversation
    path = make_images(tmp_path, ('PNG',))[0]
    image = {'type': 'image', 'mimeType': 'image/png', 'data': base64.b64encode(path.read_bytes()).decode()}
    chat.tools.asset_tree = lambda **_: {'content': [image]}
    script(state, [tool('asset_tree', {}), answer()])
    reached = False

    async def cancel():
        def on_event(row):
            nonlocal reached
            event = row['event']
            if event['type'] == 'extension_ui_request' and event.get('title', '').startswith('lalc.image_ids:'):
                reached = True
                task.cancel()
        task = asyncio.create_task(chat.run('读取图片', options, on_event=on_event))
        return await task

    result = asyncio.run(cancel())
    assert reached and result['status'] == 'cancelled', result
    assert chat.host.service.pi_process.process is None
    state['respond'] = lambda body: answer()
    result = asyncio.run(chat.run('继续，不要重放工具', options))
    assert result['status'] == 'completed', result
    assert len([e for e in records(chat) if e['type'] == 'repair_tool' and e['name'] == 'asset_tree']) == 1
    assert 'image_id=' in json.dumps(state['calls'][-1])


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
    if failure == 'length':
        assert result['reason'] == 'output_limit'
        assert result['diagnostics']['stage'] == 'compaction'
        events = records(chat)
        response = next(e['response'] for e in events if e['type'] == 'lalc_compaction' and e['phase'] == 'failed')
        assert response['stopReason'] == 'length'
        assert response['content'][0]['text'] == 'partial'
        assert any(e['type'] == 'lalc_compaction_usage' and e['stop_reason'] == 'length' for e in events)


def test_repeated_system_states_do_not_fill_context(conversation):
    original, options, state = conversation
    chat = DeveloperSession.create(original.host.service, original.host.manager.default_manifest_id(), entry='cli').conversation()
    for _ in range(6):
        result = asyncio.run(chat.run('继续检查，不修改文件', options))
        assert result['status'] == 'completed', result
        assert result['compaction_requests'] == 0
    gauges = [e['tokens'] for e in records(chat) if e['type'] == 'lalc_context_usage' and 'product_limit' in e]
    assert gauges[-1] - gauges[0] < 3000
    assert len(state['calls']) == 6


def test_insufficient_summary_space_stops_without_model_call(conversation):
    chat, options, state = conversation
    save_options(chat.host.service.data_root, context_summary_min_tokens=2147483647)
    result = asyncio.run(chat.run('需要保留的历史 ' * 20000, options))
    assert result['status'] == 'incomplete' and '剩余摘要空间不足' in result['error']
    assert result['compaction_requests'] == result['requests'] == len(state['calls']) == 0
    events = records(chat)
    assert any(e['type'] == 'session_message' for e in events)
    assert not any(e['type'] == 'lalc_compaction' and e['phase'] == 'completed' for e in events)
    path = chat.log.root / 'pi/session.jsonl'
    assert not path.exists() or not any(json.loads(line)['type'] == 'compaction' for line in path.read_text().splitlines())


@pytest.mark.parametrize('provider,field,limit', [('deepseek', 'context_deepseek_limit', 100000),
                                              ('llama.cpp', 'context_llama_limit', 40000)])
def test_saved_threshold_applies_to_preparation_and_payload(conversation, provider, field, limit):
    chat, options, state = conversation
    options.provider = provider
    if provider == 'deepseek':
        options.model = 'deepseek-flash'
        state['models'] = [{'id': 'deepseek-flash'}]
    save_options(chat.host.service.data_root, **{field: limit})
    result = asyncio.run(chat.run('只检查，不修改', options))
    assert result['status'] == 'completed', result
    gauges = [e for e in records(chat) if e['type'] == 'lalc_context_usage']
    assert any('product_limit' in e for e in gauges) and any('bytes' in e for e in gauges)
    assert all(e['limit'] == limit for e in gauges)
    start = len(records(chat))
    save_options(chat.host.service.data_root, **{field: 120000 if provider == 'deepseek' else 100000})
    result = asyncio.run(chat.run('继续检查新的触发值', options))
    assert result['status'] == 'completed', result
    gauges = [e for e in records(chat)[start:] if e['type'] == 'lalc_context_usage']
    assert gauges and all(e['limit'] == (120000 if provider == 'deepseek' else 65536 - 8192) for e in gauges)


def test_tool_loop_summary_failure_keeps_evidence_and_does_not_replay(conversation):
    chat, options, state = conversation
    chat.tools.asset_tree = lambda **_: chat.tools.text({'large': 'tool-result ' * 30000})
    state['respond'] = lambda body: tool('asset_tree', {}) if body.get('tools') else (
        {'role': 'assistant', 'content': '尚未完成的摘要'}, 'length')
    result = asyncio.run(chat.run('读取素材，不修改', options))
    assert result['reason'] == 'output_limit' and result['requests'] == 1
    assert result['diagnostics']['stage'] == 'compaction'
    assert not any(e['type'] == 'lalc_compaction' and e['phase'] == 'completed' for e in records(chat))
    state['respond'] = lambda body: answer() if body.get('tools') else (
        {'role': 'assistant', 'content': '之前已读取素材清单，无需重复读取。'}, 'stop')
    result = asyncio.run(chat.run('继续，不要重复工具操作', options))
    assert result['status'] == 'completed', result
    executed = [e for e in records(chat) if e['type'] == 'tool_execution_end' and e.get('toolName') == 'asset_tree']
    assert len(executed) == 1


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
