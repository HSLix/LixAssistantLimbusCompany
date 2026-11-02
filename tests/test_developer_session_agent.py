"""经真实 pi 与本机 HTTP 替身验证 Session 续聊、人工反馈、图片、中断与 CLI 发布试运行。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --run-agent-tests -q tests/test_developer_session_agent.py
默认跳过；不调用真实模型，不替代 Windows 或真实游戏验收。
"""

import asyncio
import base64
import copy
import json

import pytest

import lalc.__main__ as cli
from lalc.agent_log import read_json, read_events
from lalc.developer_session import DeveloperSession
from test_agent_repair_agent import conversation, script, tool, answer
from test_agent_repair_agent import test_developer_publish_trial_and_logs_continue_same_round as check_publish_trial
from test_image_attachments import make_images
from agent_test_server import agent_server
from test_developer_gui import gui

pytestmark = pytest.mark.agent


@pytest.mark.parametrize('mode', ['Construct', 'Repair'])
def test_page_tool_declarations_same_round_and_restored_drafts(conversation, mode):
    """页面工具仅 Construct 声明；源码保存和预览结果经真实 pi 回到同轮。"""
    from lalc.agent_policy import PAGE_TOOLS
    from lalc.page_drafts import PageDrafts
    from test_page_drafts import SOURCE
    original, options, state = conversation
    session = DeveloperSession.create(original.host.service, original.host.manager.default_manifest_id(), mode=mode, entry='gui')
    chat = session.conversation()
    seen = []
    def preview(request):
        seen.append(request)
        request.finish({'status': 'not_installed', 'sha256': request.snapshot['sha256']})
    if mode == 'Construct':
        script(state, [tool('page_create', {'filename': 'sample.py', 'source': SOURCE}),
                       tool('page_list', {'scope': 'drafts'}),
                       tool('page_read', {'scope': 'settings'}),
                       tool('page_update', {'filename': 'sample.py', 'source': SOURCE.replace('"Sample"', '"Updated"')}),
                       tool('page_preview', {'filename': 'sample.py', 'summary': '保留字段和 ID，未改变 Plan 参数。'}),
                       answer('review closed')])
    else:
        script(state, [tool('page_list', {}), answer('not permitted')])
    result = asyncio.run(chat.run('review page', options, on_page_preview=preview))
    assert result['status'] == 'completed', result
    declared = {item['function']['name'] for item in state['calls'][-1]['tools']}
    assert (set(PAGE_TOOLS) <= declared) if mode == 'Construct' else not (set(PAGE_TOOLS) & declared)
    assert chat.tools.on_page_preview is None
    if mode == 'Construct':
        assert len(seen) == 1 and seen[0].done.is_set()
        assert not seen[0].finish({'status': 'installed'})
        assert any(message.get('role') == 'tool' and 'not_installed' in str(message) for message in state['calls'][-1]['messages'])
        restored = DeveloperSession(chat.host.service, session.identity, entry='gui').conversation()
        assert PageDrafts(restored.session).snapshot('sample.py')['source'] == SOURCE.replace('"Sample"', '"Updated"').encode()
        assert [message for message in restored.history if message.get('toolName') == 'page_preview'][-1]['details']['status'] == 'not_installed'
        assert not (chat.host.service.data_root / 'pages').exists()
    else:
        assert not seen and not (session.path / 'page-drafts').exists()


@pytest.mark.parametrize('invalid_first', [False, True])
def test_actual_gui_page_install_returns_to_agent(conversation, gui, invalid_first):
    """真实 GUI → pi → 双页审查 → 人工点击安装 → 同轮继续，不自动重载。"""
    from PySide6.QtCore import QTimer
    from lalc.agent_settings import save_settings
    from test_page_drafts import SOURCE
    from test_developer_gui import wait_jobs
    _, options, state = conversation
    app, window = gui
    save_settings(window.service.data_root, {'base_url': options.base_url, 'model': options.model, 'max_requests': 20})
    session = DeveloperSession.create(window.service, None, mode='Construct', entry='gui')
    session.conversation()
    window.repair_page.activate_session(session)
    initial = SOURCE.replace('PAGE_ID = "sample.page"', '') if invalid_first else SOURCE
    steps = [tool('page_create', {'filename': 'sample.py', 'source': initial}),
             tool('page_preview', {'filename': 'sample.py', 'summary': '新增页面；不改现有字段。'})]
    if invalid_first:
        steps.extend([tool('page_update', {'filename': 'sample.py', 'source': SOURCE}),
                      tool('page_preview', {'filename': 'sample.py', 'summary': '已补齐 PAGE_ID，字段不变。'})])
    script(state, [*steps, answer('installed; reload manually')])
    seen = []
    timer = QTimer()
    def install():
        dialog = getattr(window.repair_page, 'page_preview_dialog', None)
        if dialog is not None and dialog.isVisible() and dialog.install_button.isEnabled():
            seen.append(dialog.request)
            dialog.install_button.click()
            timer.stop()
    timer.timeout.connect(install)
    timer.start(10)
    try:
        window.repair_page.message.setPlainText('创建并审查页面')
        window.repair_page.send()
        wait_jobs(app, window)
    finally:
        timer.stop()
        window.cancel_operation()
        wait_jobs(app, window)
    assert len(seen) == 1 and seen[0].result['status'] == 'installed'
    assert (window.service.data_root / 'pages/sample.py').read_text() == SOURCE
    assert read_json(session.path / 'log/result.json')['status'] == 'completed'
    assert any(message.get('role') == 'tool' and 'reload_required' in str(message) for message in state['calls'][-1]['messages'])
    assert app.activeModalWidget() is None and window.service.state['activity'] is None
    results = [item for item in session.host.conversation.history if item.get('toolName') == 'page_preview']
    if invalid_first:
        assert len(results) == 2
        assert results[0]['isError'] and results[0]['details']['status'] == 'preview_failed'
        assert 'PAGE_ID' in results[0]['details']['error']
        assert any(message.get('role') == 'tool' and 'preview_failed' in str(message) for message in state['calls'][2]['messages'])
    assert results[-1]['details']['status'] == 'installed'


@pytest.mark.parametrize('mode,continuation', [('Construct', 'memory'), ('Construct', 'gui'),
                                             ('Repair', 'memory'), ('Repair', 'gui'), ('Repair', 'cli')])
@pytest.mark.parametrize('corrections', [1, 2])
def test_tools_restored_after_final_correction(conversation, mode, continuation, corrections):
    """格式纠正禁用工具不污染下轮或恢复入口；旧日志与实际工具结果保留。"""
    original, options, state = conversation
    session = DeveloperSession.create(original.host.service, original.host.manager.default_manifest_id(),
                                      mode=mode, entry='gui')
    chat = session.conversation()
    seen = []

    def feedback(request):
        seen.append(request)
        request.finish('confirmed', '已检查')

    script(state, [tool('request_feedback', {'message': '第一次反馈'}),
                   *[({'role': 'assistant', 'content': 'invalid'}, 'stop')] * corrections,
                   answer('corrected')])
    result = asyncio.run(chat.run('先请求反馈再回答', options, on_feedback=feedback))
    assert result['status'] == 'completed', result
    assert len(seen) == 1
    assert all(not body.get('tools') for body in state['calls'][-corrections:])
    events = list(read_events(chat.log.root / 'events.jsonl'))
    assert any(row['event']['type'] == 'message_end' and row['event']['message'].get('toolsRemoved')
               for row in events)
    retained = {path: path.read_bytes() for path in (chat.log.root / 'round-1').rglob('*') if path.is_file()}
    if continuation != 'memory':
        chat = DeveloperSession(original.host.service, session.identity, entry=continuation).conversation()
    assert any(message.get('role') == 'system' and message.get('toolsRemoved') for message in chat.history)
    returned = [message for message in chat.history if message.get('toolName') == 'request_feedback']
    assert returned[-1]['details'] == {'status': 'confirmed', 'text': '已检查'}
    expected = set(chat.allowed)
    next_tool = 'action_contracts' if continuation == 'cli' else 'request_feedback'
    steps = iter([tool(next_tool, {} if continuation == 'cli' else {'message': '第二次反馈'}), answer('continued')])

    def respond(body):
        assert {item['function']['name'] for item in body.get('tools', [])} == expected
        guidance = body['messages'][0]['content'].split('# Tool Guidance\n', 1)[1]
        assert {line[2:].split(':', 1)[0] for line in guidance.splitlines() if line.startswith('- ')} == expected
        assert any(message.get('role') == 'tool' and '已检查' in str(message) for message in body['messages'])
        return next(steps)

    state['respond'] = respond
    result = asyncio.run(chat.run('继续调用工具', options, on_feedback=feedback))
    assert result['status'] == 'completed' and result['requests'] == 2, result
    assert len(seen) == (1 if continuation == 'cli' else 2)
    assert ('request_feedback' in expected) == (continuation != 'cli')
    assert all(path.read_bytes() == content for path, content in retained.items())


@pytest.mark.parametrize('mode', ['Construct', 'Repair'])
@pytest.mark.parametrize('status,text', [('confirmed', ''), ('confirmed', '操作完成'), ('skipped', '')])
def test_feedback_returns_in_same_round_and_survives_cli_resume(conversation, mode, status, text):
    """人工反馈经真实 pi 回到同轮上下文；续聊不重放、不向 CLI 授权。"""
    original, options, state = conversation
    session = DeveloperSession.create(original.host.service, original.host.manager.default_manifest_id(), mode=mode, entry='gui')
    chat = session.conversation()
    seen = []
    def feedback(request):
        seen.append(request)
        request.finish(status, text)
    script(state, [tool('request_feedback', {'message': '请检查当前界面'}), answer('received')])
    result = asyncio.run(chat.run('interact', options, on_feedback=feedback))
    assert result['status'] == 'completed', result
    assert len(seen) == 1 and result['requests'] == 2
    returned = [item for item in chat.history if item.get('toolName') == 'request_feedback']
    assert returned[-1]['details'] == {'status': status, 'text': text}
    assert any(message.get('role') == 'tool' and status in str(message) for message in state['calls'][-1]['messages'])
    before = len(seen)
    if mode == 'Repair':
        restored = DeveloperSession(original.host.service, session.identity, entry='cli').conversation()
        script(state, [tool('request_feedback', {'message': 'forbidden'}), answer('denied')])
        result = asyncio.run(restored.run('CLI continuation', options, on_feedback=feedback))
        assert result['status'] == 'completed', result
        assert len(seen) == before
        assert 'request_feedback' not in {item['function']['name'] for item in state['calls'][-1]['tools']}
        assert [item for item in restored.history if item.get('toolName') == 'request_feedback'][-1]['isError']
    else:
        restored = DeveloperSession(original.host.service, session.identity, entry='gui').conversation()
        assert [item for item in restored.history if item.get('toolName') == 'request_feedback'][-1]['details'] == returned[-1]['details']


@pytest.mark.parametrize('cancel', [False, True])
def test_feedback_batch_waits_before_trial_and_cancel_reaps(conversation, monkeypatch, cancel):
    """同响应内人工等待先于后续工具；取消清理 pi 后不能再执行试运行。"""
    original, options, state = conversation
    session = DeveloperSession.create(original.host.service, original.host.manager.default_manifest_id(), entry='gui')
    chat = session.conversation()
    batch = []
    for index, (name, arguments) in enumerate([('request_feedback', {'message': 'wait'}),
                                              ('trial_run', {'manifest_id': 'saved'})]):
        call = tool(name, arguments)[0]['tool_calls'][0]
        call['index'] = index
        batch.append(call)
    script(state, [({'role': 'assistant', 'tool_calls': batch}, 'tool_calls'), answer()])
    requests, trials = [], []
    def trial(**arguments):
        trials.append(arguments)
        assert requests[0].done.is_set()
        return chat.tools.text({'status': 'completed'})
    monkeypatch.setattr(chat.tools, 'trial_run', trial)
    async def run():
        task = asyncio.create_task(chat.run('batch interaction', options, on_feedback=requests.append))
        try:
            async with asyncio.timeout(15):
                while not requests:
                    await asyncio.sleep(.01)
            await asyncio.sleep(.1)
            assert not trials and not task.done()
            assert chat.host.service.state['activity'] == 'Agent'
            from lalc.application import StartError
            with pytest.raises(StartError, match='当前活动'):
                chat.host.capture()
            if cancel:
                task.cancel()
            else:
                requests[0].finish('confirmed', '')
            return await task
        finally:
            if not task.done():
                task.cancel()
                await task
    result = asyncio.run(run())
    assert result['status'] == ('cancelled' if cancel else 'completed'), result
    assert bool(trials) is not cancel
    assert requests[0].done.is_set() and not requests[0].finish('confirmed', 'late')
    assert chat.tools.on_feedback is None and chat.host.service.state['activity'] is None
    restored = session.conversation()
    results = [item for item in restored.history if item.get('toolName') == 'request_feedback']
    assert results and (results[-1]['isError'] if cancel else results[-1]['details']['status'] == 'confirmed')


def test_actual_gui_feedback_signal_and_empty_confirmation(conversation, gui):
    """真实 GUI 发送链路经 pi 请求反馈，点击空确认后完成同轮。"""
    from PySide6.QtCore import QTimer
    from lalc.agent_settings import save_settings
    from test_developer_gui import wait_jobs
    _, options, state = conversation
    app, window = gui
    save_settings(window.service.data_root, {'base_url': options.base_url, 'model': options.model, 'max_requests': 20})
    script(state, [tool('request_feedback', {'message': '请操作后确认'}), answer('feedback received')])
    seen = []
    timer = QTimer()
    def confirm():
        dialog = getattr(window.repair_page, 'feedback_dialog', None)
        if dialog is not None and dialog.isVisible():
            seen.append(dialog.request)
            dialog.confirm.click()
            timer.stop()
    timer.timeout.connect(confirm)
    timer.start(10)
    try:
        window.repair_page.message.setPlainText('request human feedback')
        window.repair_page.send()
        wait_jobs(app, window)
    finally:
        timer.stop()
    assert len(seen) == 1 and seen[0].result == {'status': 'confirmed', 'text': ''}
    chat = window.repair_page.host.conversation
    assert read_json(chat.log.root / 'result.json')['status'] == 'completed'
    assert 'feedback received' in window.repair_page.chat.toPlainText()


@pytest.mark.parametrize('mode,entry,build', [('Construct', 'gui', '26156805'), ('Repair', 'gui', None), ('Repair', 'cli', '26156805')])
def test_version_history_tools_text_images_and_persistent_context(conversation, monkeypatch, mode, entry, build):
    """三个工具经真实 pi 与替代服务往返；轮次标版本、图片按需取，入口权限一致。"""
    from lalc import agent_history
    from lalc.agent_repair import RepairLog
    chat, options, state = conversation
    root = chat.host.service.data_root
    value = {'game_version': '1.118.0', 'steam_build_id': build,
             'observed_at': '2026-11-01T06:53:31Z', 'errors': []}
    monkeypatch.setattr(agent_history, 'observe_game_version', lambda _: value)
    previous = RepairLog(root)
    previous.group = 1
    agent_history.record_observation(previous, root, 'cli:Repair', 'Historical repair')
    # 传输真实可解码的小 PNG，避免测试依赖服务端容忍无效图片。
    from PIL import Image
    import io
    stream = io.BytesIO()
    Image.new('RGB', (2, 2), 'red').save(stream, format='PNG')
    image = stream.getvalue()
    previous.record({'type': 'historical_answer', 'text': 'Historical version evidence',
                     'image': {'type': 'image', 'mimeType': 'image/png', 'data': base64.b64encode(image).decode()}})
    page, _ = agent_history.AgentHistory(root).read(previous.identity)
    image_id = page['events'][-1]['images'][0]
    source = chat.host.manager.default_manifest_id()
    session = DeveloperSession.create(chat.host.service, source, mode=mode, entry=entry)
    current = session.conversation()
    script(state, [tool('list_game_versions', {}),
                   tool('search_agent_sessions', {'version_group': {'game_version': '1.118.0', 'steam_build_id': build}}),
                   tool('read_agent_session', {'session_id': previous.identity, 'version_group': {'game_version': '1.118.0', 'steam_build_id': build}}),
                   tool('read_agent_session', {'session_id': previous.identity, 'image_id': image_id}), answer('history checked')])
    result = asyncio.run(current.run('Use versioned historical evidence', options))
    assert result['status'] == 'completed', result
    declared = {item['function']['name'] for item in state['calls'][-1]['tools']}
    assert {'list_game_versions', 'search_agent_sessions', 'read_agent_session'} <= declared
    assert 'Historical version evidence' in json.dumps(state['calls'][-1])
    results = [message for message in current.history if message.get('role') == 'toolResult']
    assert len(results) == 4 and not any(message.get('isError') for message in results)
    assert not any(part.get('type') == 'image' for part in results[2]['content'])
    assert any(part.get('type') == 'image' and base64.b64decode(part['data']) == image for part in results[3]['content'])
    saved = read_json(current.log.root / 'round-1/input.json')
    assert saved['game_version_observation'] == value
    restored = DeveloperSession(chat.host.service, session.identity, entry=entry).conversation()
    assert restored.history == current.history


@pytest.mark.parametrize('mode', ['Construct', 'Repair'])
def test_gui_knowledge_tools_images_and_cli_permissions(conversation, tmp_path, monkeypatch, mode):
    """知识库经实际 pi 注册、宿主返回及历史恢复；GUI 权限不流入 CLI。"""
    from PIL import Image
    from lalc.agent_policy import KNOWLEDGE_TOOLS
    chat, options, state = conversation
    source = chat.host.manager.default_manifest_id()
    session = DeveloperSession.create(chat.host.service, source, mode=mode, entry='gui')
    gui_chat = session.conversation()
    root = chat.host.service.data_root / 'knowledge'
    root.mkdir()
    (root / 'guide.md').write_text('Knowledge evidence needle\n')
    Image.new('RGB', (3, 2), 'red').save(root / 'reference.jpg')
    before = {p: p.read_bytes() for p in session.host.candidate.rglob('*') if p.is_file()}
    script(state, [tool('knowledge_list', {}), tool('knowledge_read', {'path': 'guide.md'}),
                   tool('knowledge_search', {'query': 'needle'}),
                   tool('knowledge_read', {'path': 'reference.jpg'}), answer('knowledge read')])
    result = asyncio.run(gui_chat.run('read external references', options))
    assert result['status'] == 'completed', result
    declared = {item['function']['name'] for item in state['calls'][-1]['tools']}
    assert set(KNOWLEDGE_TOOLS) <= declared
    payload = json.dumps(state['calls'][-1])
    assert 'Knowledge evidence needle' in payload and 'image/jpeg' in payload
    assert all(path.read_bytes() == value for path, value in before.items())
    assert any(path.suffix == '.jpeg' and path.read_bytes() == (root / 'reference.jpg').read_bytes()
               for path in gui_chat.log.path.iterdir())
    restored = DeveloperSession(chat.host.service, session.identity, entry='gui').conversation()
    script(state, [answer('restored reference evidence')])
    assert asyncio.run(restored.run('continue', options))['status'] == 'completed'
    assert 'Knowledge evidence needle' in json.dumps(state['calls'][-1])
    if mode == 'Repair':
        cli_chat = DeveloperSession(chat.host.service, session.identity, entry='cli').conversation()
        monkeypatch.setattr(cli_chat.tools, 'knowledge_read', lambda **kwargs: pytest.fail('CLI 禁止读取资料'))
        script(state, [tool('knowledge_read', {'path': 'guide.md'}), answer('CLI has no knowledge access')])
        assert asyncio.run(cli_chat.run('continue in CLI', options))['status'] == 'completed'
        assert not set(KNOWLEDGE_TOOLS) & {item['function']['name'] for item in state['calls'][-1]['tools']}
        assert any(message.get('role') == 'toolResult' and message.get('isError') for message in cli_chat.history)


def persistent(conversation):
    chat, options, state = conversation
    source = json.loads(chat.host.metadata.read_text())["manifest_id"]
    session = DeveloperSession.create(chat.host.service, source)
    return session, session.conversation(), options, state


def test_restart_retains_original_images_tools_and_rounds(conversation, tmp_path):
    session, chat, options, state = persistent(conversation)
    paths = make_images(tmp_path)
    script(state, [tool("read", {"path": "steps.total.py"}), answer("remember this answer")])
    result = asyncio.run(chat.run("remember these images", options, images=paths, key="session-private-key"))
    assert result["status"] == "completed", result
    original_history = chat.history
    original_files = {path: path.read_bytes() for path in chat.log.root.glob("tool-*")}
    restored = DeveloperSession(session.host.service, session.identity).conversation()
    assert restored.history == original_history
    state["respond"] = lambda body: answer("resumed")
    result = asyncio.run(restored.run("continue after restart", options, key="session-private-key"))
    assert result["status"] == "completed" and result["round"] == 2, result
    payload = state["calls"][-1]
    assert "remember this answer" in json.dumps(payload)
    urls = [part["image_url"]["url"] for item in payload["messages"] if isinstance(item.get("content"), list)
            for part in item["content"] if part["type"] == "image_url"]
    assert [base64.b64decode(url.split(",", 1)[1]) for url in urls] == [path.read_bytes() for path in paths]
    assert all(path.read_bytes() == value for path, value in original_files.items())
    assert all(b"session-private-key" not in path.read_bytes() for path in session.path.rglob("*") if path.is_file())


def test_interrupted_calls_continue_with_known_and_unknown_results_without_replay(conversation):
    session, chat, options, state = persistent(conversation)
    script(state, [tool("read", {"path": "steps.total.py"}), answer("first round")])
    assert asyncio.run(chat.run("read once", options))["status"] == "completed"
    assistant = copy.deepcopy(next(item for item in chat.history if item["role"] == "assistant"
                                   and any(part["type"] == "toolCall" for part in item["content"])))
    assistant["content"] = [
        {"type": "toolCall", "id": "pending-publish", "name": "publish", "arguments": {}},
        {"type": "toolCall", "id": "pending-read", "name": "read", "arguments": {"path": "steps.total.py"}}]
    chat.log.group = 2
    (chat.log.root / "round-2").mkdir()
    chat.append_user({"role": "user", "content": [{"type": "text", "text": "interrupted round"}], "timestamp": 1})
    chat.log.record({"type": "message_end", "message": assistant})
    published = chat.tools.publish()
    chat.log.record({"type": "repair_tool", "toolCallId": "pending-publish", "result": published})
    manifests = chat.host.manager.list_manifests()
    calls = len(state["calls"])
    restored = session.conversation()
    assert len(state["calls"]) == calls
    assert read_json(restored.log.root / "round-2/result.json")["status"] == "interrupted"
    state["respond"] = lambda body: answer("checked retained evidence")
    result = asyncio.run(restored.run("continue carefully", options))
    assert result["status"] == "completed" and result["round"] == 3, result
    payload = state["calls"][-1]
    tool_results = {item["tool_call_id"]: item for item in payload["messages"] if item["role"] == "tool"}
    assert "结果未知" in tool_results["pending-read"]["content"]
    assert "pending-publish" in tool_results
    assert chat.host.manager.list_manifests() == manifests
    assert not any(row["event"].get("type") == "repair_tool" for row in read_events(restored.log.root / "events.jsonl")
                   if row["round"] == 3)


def test_session_keeps_publish_and_explicit_saved_trial(conversation, monkeypatch):
    _, chat, options, state = persistent(conversation)
    check_publish_trial((chat, options, state), monkeypatch)


def test_cli_creates_and_resumes_without_manual_candidate(conversation, monkeypatch, capsys, tmp_path):
    session, _, options, state = persistent(conversation)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "default_data_root", lambda: session.host.service.data_root)
    source = json.loads((session.path / "session.json").read_text())["source_manifest_id"]
    common = ["--base-url", options.base_url, "--model", options.model, "--max-requests", "5"]
    state["respond"] = lambda body: answer("CLI first answer")
    assert cli.main(["repair", "--from", source, "--problem", "CLI first message", *common]) == 0
    lines = capsys.readouterr().out.splitlines()
    identity = json.loads(lines[0])["session_id"]
    assert json.loads(lines[-1])["session_id"] == identity
    state["respond"] = lambda body: answer("CLI resumed")
    assert cli.main(["repair", "--session", identity, "--problem", "CLI next message", *common]) == 0
    result = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert result["round"] == 2
    assert "CLI first message" in json.dumps(state["calls"][-1])
    assert not (tmp_path / "candidate").exists()


@pytest.mark.parametrize('mode', ['Repair', 'Construct'])
def test_gui_references_are_shared_readonly_tools_and_survive_cli_resume(conversation, tmp_path, mode):
    chat, options, state = conversation
    source = chat.host.manager.default_manifest_id()
    session = DeveloperSession.create(chat.host.service, source, mode=mode, entry='gui')
    gui_chat = session.conversation()
    second = DeveloperSession.create(chat.host.service, None, mode='Construct', entry='gui')
    second.conversation()
    other_id = second.host.publish()
    before = {path: path.read_bytes() for path in session.host.candidate.rglob('*') if path.is_file()}
    script(state, [tool('list_manifests', {'limit': 1}),
                   tool('read_manifest', {'manifest_id': other_id, 'limit': 1}),
                   tool('read_manifest_source', {'manifest_id': source, 'section': 'components',
                                                 'logical_name': 'steps.total', 'limit': 2}),
                   answer('references inspected')])
    images = make_images(tmp_path)[:1]
    result = asyncio.run(gui_chat.run('compare these versions', options, images=images,
                                     manifest_references=[source, other_id]))
    assert result['status'] == 'completed', result
    assert all(path.read_bytes() == content for path, content in before.items())
    assert gui_chat.host.manager.default_manifest_id() == source
    payload = state['calls'][-1]
    assert source in json.dumps(payload) and other_id in json.dumps(payload)
    assert {'list_manifests', 'read_manifest', 'read_manifest_source'} <= {
        item['function']['name'] for item in payload['tools']}
    if mode == 'Construct':
        with pytest.raises(ValueError, match='CLI'):
            DeveloperSession(chat.host.service, session.identity).conversation()
        restored = DeveloperSession(chat.host.service, session.identity, entry='gui').conversation()
    else:
        restored = DeveloperSession(chat.host.service, session.identity).conversation()
    state['respond'] = lambda body: answer('continued')
    result = asyncio.run(restored.run('continue with retained references', options))
    assert result['status'] == 'completed', result
    assert source in json.dumps(state['calls'][-1]) and other_id in json.dumps(state['calls'][-1])
    assert 'references inspected' in json.dumps(state['calls'][-1])


def test_blank_construct_adds_task_publishes_and_trials_plan(conversation, monkeypatch):
    chat, options, state = conversation
    session = DeveloperSession.create(chat.host.service, None, mode='Construct', entry='gui')
    chat = session.conversation()
    monkeypatch.setattr(chat.host.service, '_start_session', lambda: None)
    source = ('"""构建验收 Task；返回固定业务结果。"""\n'
              'from lalc import RunContext, task_workflow\n\n'
              '@task_workflow\n'
              'def execute(ctx: RunContext) -> dict[str, int]:\n'
              '    return {"value": 7}\n')
    count = 0
    def respond(body):
        nonlocal count
        count += 1
        if count == 1:
            return tool('add_component', {'filename': 'task.py', 'logical_name': 'tasks.built', 'source': source})
        if count == 2:
            return tool('edit', {'path': 'plan.py', 'oldText': '    return None',
                                 'newText': '    ctx.call("tasks.built")\n    return None'})
        if count == 3:
            return tool('validate', {})
        if count == 4:
            return tool('publish', {})
        if count == 5:
            identity = chat.host.manager.list_manifests()[0]['manifest_id']
            return tool('trial_run', {'manifest_id': identity})
        return answer('built and tried')
    state['respond'] = respond
    result = asyncio.run(chat.run('construct a new task and trial the published plan', options))
    assert result['status'] == 'completed', result
    run = chat.host.service.state['result']
    assert run['status'] == 'completed' and run['all_tasks_succeeded']
    assert len(run['items']) == 1 and run['items'][0]['output'] == {'value': 7}


def test_mode_white_list_hides_and_rejects_disallowed_native_tools(conversation, monkeypatch):
    from lalc.agent_policy import MODE_TOOLS
    chat, options, state = conversation
    source = chat.host.manager.default_manifest_id()
    monkeypatch.setitem(MODE_TOOLS, 'Construct', frozenset({'read_manifest'}))
    session = DeveloperSession.create(chat.host.service, source, mode='Construct', entry='gui')
    chat = session.conversation()
    before = (chat.host.candidate / 'steps.total.py').read_bytes()
    script(state, [tool('edit', {'path': 'steps.total.py', 'oldText': 'if value > 0', 'newText': 'if value >= 0'}),
                   answer('denied')])
    result = asyncio.run(chat.run('do not allow native edit through a restricted mode', options))
    assert result['status'] == 'completed', result
    assert [item['function']['name'] for item in state['calls'][-1]['tools']] == ['read_manifest']
    guidance = state['calls'][-1]['messages'][0]['content'].split('# Tool Guidance\n', 1)[1]
    assert [line[2:].split(':', 1)[0] for line in guidance.splitlines() if line.startswith('- ')] == ['read_manifest']
    assert (chat.host.candidate / 'steps.total.py').read_bytes() == before
    assert any(row['event'].get('type') == 'tool_execution_end' and row['event'].get('isError')
               for row in read_events(chat.log.root / 'events.jsonl'))


def test_gui_send_uses_actual_pi_events_and_cli_can_continue(conversation, gui):
    from lalc.agent_settings import save_settings
    from test_developer_gui import wait_jobs
    _, options, state = conversation
    app, window = gui
    save_settings(window.service.data_root, {'base_url': options.base_url, 'model': options.model, 'max_requests': 20})
    page = window.repair_page
    source = window.host.manager.default_manifest_id()
    page.new()
    page.mode.setCurrentItem('Repair')
    page.baseline.setCurrentIndex(page.baseline.findData(source))
    page.manifest_references = [source]
    page.message.setPlainText('actual GUI message')
    state['respond'] = lambda body: answer('actual GUI reply')
    page.send()
    wait_jobs(app, window)
    assert page.session is not None
    text = page.chat.toPlainText()
    assert text.count('actual GUI message') == 1 and text.count('actual GUI reply') == 1
    restored = DeveloperSession(window.service, page.session.identity).conversation()
    result = asyncio.run(restored.run('CLI continuation', options))
    assert result['status'] == 'completed', result
    assert 'actual GUI message' in json.dumps(state['calls'][-1])
    assert source in json.dumps(state['calls'][-1])
