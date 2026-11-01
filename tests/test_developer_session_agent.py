"""经真实 pi 与本机 HTTP 替身验证 Session 续聊、图片、中断与 CLI 发布试运行。

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
from test_pi_probe import probe
from test_developer_gui import gui

pytestmark = pytest.mark.agent


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
