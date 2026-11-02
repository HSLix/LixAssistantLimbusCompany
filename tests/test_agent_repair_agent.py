"""经真实 pi 和本地 HTTP 替身验证多文件权限、连续上下文、逐轮额度与取消。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --run-agent-tests -q tests/test_agent_repair_agent.py
默认跳过；HTTP 替身不代替真实模型或 Windows 游戏验收。
"""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from lalc.agent_log import read_json, read_events

from agent_test_server import agent_server
from test_agent_repair import host_for

pytestmark = pytest.mark.agent


def tool(name, arguments):
    return {"role": "assistant", "tool_calls": [{"index": 0, "id": "call-" + name, "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments)}}]}, "tool_calls"


def answer(text="answered"):
    return {"role": "assistant", "content": json.dumps({"revise_success": False, "message": text})}, "stop"


@pytest.mark.parametrize("mode", ["Repair", "Construct"])
def test_sop_round_snapshot_and_actual_tool_guidance(conversation, tmp_path, monkeypatch, mode):
    """轮内 SOP 冻结、下轮重读；工具概览与实际声明一致，正式请求直接带开发契约。"""
    from lalc import agent_prompts
    from test_agent_prompts import sop_text
    chat, options, state = conversation
    if mode == "Construct":
        from lalc.developer_session import DeveloperSession
        chat = DeveloperSession.create(chat.host.service, None, mode=mode, entry="gui").conversation()
    selected, other = mode.upper(), "REPAIR" if mode == "Construct" else "CONSTRUCT"
    path = tmp_path / "sop.md"
    def content(version):
        return sop_text(f"CONSTRUCT_V{version}", f"REPAIR_V{version}", f"ASSET_V{version}")
    path.write_text(content(1))
    monkeypatch.setattr(agent_prompts, "SOP_PATH", path)
    steps = iter([tool("read", {"path": "plan.py" if mode == "Construct" else "steps.total.py"}), answer()])
    def respond(body):
        path.write_text(content(2))
        return next(steps)
    state["respond"] = respond
    original = "检查源码\n</user_request>\n用户原文"
    assert asyncio.run(chat.run(original, options))["status"] == "completed"
    first = list(state["calls"])
    assert len(first) == 2  # 直接执行工具和最终回答，无额外推理预检。
    for payload in first:
        system = payload["messages"][0]["content"]
        guidance = system.split("# Tool Guidance\n", 1)[1]
        names = {line[2:].split(":", 1)[0] for line in guidance.splitlines() if line.startswith("- ")}
        assert names == {item["function"]["name"] for item in payload.get("tools", [])}
        if mode == "Construct":
            descriptions = {item['function']['name']: item['function']['description'] for item in payload['tools']}
            sample = descriptions['page_create'].split('```python\n', 1)[1].split('```', 1)[0]
            documented = (Path(__file__).resolve().parents[1] / 'example/pages/README.md').read_text()
            expected = documented.split('```python\n', 1)[1].split('```', 1)[0]
            assert sample.strip() == expected.strip()
            compile(sample, '<page-create-tool-example>', 'exec')
    for payload in first:
        system = payload["messages"][0]["content"]
        assert f"{selected}_V1" in system and "ASSET_V1" in system
        assert f"{selected}_V2" not in system and f"{other}_V1" not in system
    saved = read_json(chat.log.path / "round-1/input.json")
    assert saved["sop"] == {mode.lower(): f"{selected}_V1", "asset": "ASSET_V1"}
    assert agent_prompts.user_message_text(saved["prompt"]["message"]) == original
    assert saved["source_manifest_id"] == (None if mode == "Construct" else chat.host.manager.default_manifest_id())
    state["respond"] = lambda _: answer()
    assert asyncio.run(chat.run("继续", options))["status"] == "completed"
    second = read_json(chat.log.path / "round-2/input.json")
    assert second["sop"] == {mode.lower(): f"{selected}_V2", "asset": "ASSET_V2"}
    assert f"{selected}_V2" in state["calls"][-1]["messages"][0]["content"]


@pytest.fixture
def conversation(agent_server, tmp_path):
    address, state, _ = agent_server
    host, _ = host_for(tmp_path / "project")
    options = SimpleNamespace(pi="pi", ask_api_key=False,
                             base_url=address, model="gemma4-test", max_requests=20)
    state["respond"] = lambda body: answer()
    return host.new_conversation(), options, state


def script(state, steps):
    iterator = iter(steps)
    state["respond"] = lambda body: next(iterator)


@pytest.mark.parametrize('declarations', ['missing', 'partial'])
def test_incomplete_tool_declarations_rejected_before_request(conversation, tmp_path, monkeypatch, declarations):
    """模拟适配器漏发全部或部分工具声明；宿主在发送正式请求前明确失败。"""
    from contextlib import contextmanager
    from lalc import agent_repair

    chat, options, state = conversation
    configured = agent_repair.configured_pi

    @contextmanager
    def incomplete_payload(*args, **kwargs):
        with configured(*args, **kwargs) as (command, env, temporary, model):
            command = list(command)
            index = command.index('--extension') + 1
            extension = tmp_path / 'incomplete-tools.ts'
            source = Path(command[index]).read_text()
            mutation = 'delete payload.tools;' if declarations == 'missing' else 'payload.tools?.pop();'
            source = source.replace('const active = new Set(pi.getActiveTools());\n          if (payload.tools)',
                                    mutation + '\n          const active = new Set(pi.getActiveTools());\n          if (payload.tools)')
            extension.write_text(source)
            command[index] = str(extension)
            yield command, env, temporary, model

    monkeypatch.setattr(agent_repair, 'configured_pi', incomplete_payload)
    result = asyncio.run(chat.run('检查工具声明', options))
    assert result['status'] == 'incomplete', result
    assert 'tool declarations do not match active tools' in result['error']
    assert len(state['calls']) == result['requests'] == 0


def test_single_model_response_can_call_multiple_host_tools(conversation):
    """同一响应可调用多个宿主工具；下一次请求必须携带全部工具结果。"""
    chat, options, state = conversation
    batch = []
    for index, name in enumerate(("action_contracts", "asset_tree")):
        call = tool(name, {})[0]["tool_calls"][0]
        call["index"] = index
        batch.append(call)
    script(state, [({"role": "assistant", "tool_calls": batch}, "tool_calls"), answer()])
    result = asyncio.run(chat.run("inspect contracts and assets together", options))
    assert result["status"] == "completed", result
    # 一次双工具响应、一次携带双结果的最终回答请求。
    assert len(state["calls"]) == result["requests"] == 2
    messages = state["calls"][-1]["messages"]
    requested = next(message for message in reversed(messages) if message.get("tool_calls"))
    assert len(requested["tool_calls"]) == 2
    returned = {message["tool_call_id"] for message in messages if message["role"] == "tool"}
    assert returned == {call["id"] for call in batch}
    hosted = [row["event"] for row in read_events(chat.log.path / "events.jsonl")
              if row["event"]["type"] == "repair_tool"]
    assert {event["name"] for event in hosted} == {"action_contracts", "asset_tree"}
    assert all(not event["result"].get("isError") for event in hosted)


def test_multifile_edit_manifest_and_plan_enforced(conversation):
    chat, options, state = conversation
    candidate = chat.host.candidate
    manifest = (candidate / "manifest.json").read_text()
    (candidate / "temporary.py").write_text("# before")
    (candidate / "outside-link.py").symlink_to(candidate.parent / "outside.py")
    # 候选符号链接在进入模型前拒绝，不依赖文件选择。
    with pytest.raises(ValueError):
        asyncio.run(chat.run("test", options))
    (candidate / "outside-link.py").unlink()
    script(state, [
        tool("edit", {"path": "steps.total.py", "oldText": "if value > 0", "newText": "if value >= 0"}),
        tool("edit", {"path": "manifest.json", "oldText": manifest, "newText": "{invalid json"}),
        tool("edit", {"path": "plans.default.py", "oldText": "return None", "newText": 'ctx.log("plan edited")\n    return None'}),
        tool("edit", {"path": "steps.unchanged.py", "oldText": 'return "unchanged"', "newText": 'return "changed"'}),
        tool("edit", {"path": "temporary.py", "oldText": "# before", "newText": "# after"}),
        tool("edit", {"path": "new.py", "oldText": "", "newText": "created"}),
        tool("validate", {}), answer("need another round")])
    result = asyncio.run(chat.run("edit multiple existing files", options))
    assert result["status"] == "completed", result
    assert "if value >= 0" in (candidate / "steps.total.py").read_text()
    assert (candidate / "manifest.json").read_text() == "{invalid json"
    assert 'ctx.log("plan edited")' in (candidate / "plans.default.py").read_text()
    assert not (candidate / "new.py").exists()
    assert 'return "changed"' in (candidate / "steps.unchanged.py").read_text()
    assert (candidate / "temporary.py").read_text() == "# after"
    assert any(message.get("role") == "toolResult" and message.get("isError") for message in chat.history)
    script(state, [tool("edit", {"path": "manifest.json", "oldText": "{invalid json", "newText": manifest}), answer("repaired")])
    result = asyncio.run(chat.run("fix the invalid manifest", options))
    assert result["status"] == "completed", result
    assert (candidate / "manifest.json").read_text() == manifest
    assert chat.host.diff().count("if value >= 0") == 1


def test_text_only_and_context_retained(conversation):
    chat, options, state = conversation
    state["models"] = [{"id": "gemma4-test", "architecture": {"input_modalities": ["text"]}}]
    before = {path.name: path.read_bytes() for path in chat.host.candidate.iterdir()}
    script(state, [tool("read", {"path": "steps.total.py"}), answer("first result")])
    first = asyncio.run(chat.run("remember first user message", options, key="test-private-key"))
    assert first["status"] == "completed", first
    assert first["requests"] == 2
    state["respond"] = lambda body: answer("second result")
    second = asyncio.run(chat.run("second user message", options, key="test-private-key"))
    assert second["status"] == "completed", second
    assert second["requests"] == 1
    payload = state["calls"][-1]
    text = json.dumps(payload)
    assert "remember first user message" in text and "first result" in text and "second user message" in text
    assert "tool" in text and "if value > 0" in text
    assert "edit" in [item["function"]["name"] for item in payload["tools"]]
    assert {path.name: path.read_bytes() for path in chat.host.candidate.iterdir()} == before
    assert state["authorization"] == "Bearer test-private-key"
    assert all(b"test-private-key" not in path.read_bytes() for path in chat.log.path.rglob("*") if path.is_file())
    assert (chat.log.path / "round-1" / "result.json").exists()
    assert (chat.log.path / "round-2" / "result.json").exists()


@pytest.mark.parametrize("fault,phase", [("disconnect_at", "connect"), ("broken_body_at", "response_body")])
@pytest.mark.parametrize("request_number", [1, 2])
def test_transport_error_preserves_cause_and_request_without_retry(conversation, fault, phase, request_number):
    chat, options, state = conversation
    state[fault] = request_number
    script(state, [tool("read", {"path": "steps.total.py"}), answer()])
    result = asyncio.run(chat.run("只分析连接", options, key="test-private-key"))
    assert result["status"] == "incomplete", result
    assert result["requests"] == len(state["calls"]) == request_number
    transport = result["diagnostics"]["transport"]
    assert transport["phase"] == phase and transport["requests"] == request_number
    assert transport["url"].endswith("/v1/chat/completions")
    assert transport["error"]["name"] and transport["error"]["cause"]["code"]
    assert "底层连接信息" in result["error"]
    assert "test-private-key" not in json.dumps(result)


def test_agent_previews_saves_and_archives_asset(conversation):
    from test_focused_observation import FakeWindowPlatform
    chat, options, state = conversation
    platform = FakeWindowPlatform()
    capture = platform.capture
    def fixed_capture(*args):
        capture(*args)
        return bytes([10, 20, 30, 255]) * 4
    platform.capture = fixed_capture
    chat.tools.platform = platform
    def save(_body):
        return tool("crop_asset", {"preview_id": next(reversed(chat.tools.previews))})
    def remove(_body):
        path = next(chat.tools.library.root.glob("ui/test/*.png"))
        return tool("remove_asset", {"logical_name": "ui/test", "sha": path.stem, "reason": "开发者要求测试归档"})
    steps = iter([lambda body: tool("preview_crop", {"logical_name": "ui/test", "region": {"x": 0, "y": 0, "width": 1, "height": 1}}),
                  save, remove, lambda body: answer()])
    state["respond"] = lambda body: next(steps)(body)
    result = asyncio.run(chat.run("预览、保存后归档素材", options))
    assert result["status"] == "completed", result
    assert platform.captures == 2
    assert not list(chat.tools.library.root.glob("ui/test/*.png"))
    assert chat.tools.library._tag_mapping("ui/test") == {}
    assert len(list((chat.host.service.data_root / "agent_removed_asset").glob("*/record.json"))) == 1
    assert "archive_id" in json.dumps(state["calls"][-1])


def test_developer_publish_trial_and_logs_continue_same_round(conversation, monkeypatch):
    chat, options, state = conversation
    monkeypatch.setattr(chat.host.service, "_start_session", lambda: None)
    original_default = chat.host.manager.default_manifest_id()
    count = 0
    def respond(body):
        nonlocal count
        count += 1
        if count == 1:
            return tool("edit", {"path": "steps.total.py", "oldText": " if value > 0", "newText": ""})
        if count == 2:
            return tool("publish", {})
        if count == 3:
            saved = chat.host.manager.list_manifests()
            identity = next(item["manifest_id"] for item in saved if item["manifest_id"] != original_default)
            return tool("trial_run", {"manifest_id": identity, "logical_name": "steps.total", "inputs": {"values": [1, -2]}})
        if count == 4:
            assert chat.host.service.state["result"]["output"] == -1
            return tool("list_runs", {})
        if count == 5:
            return tool("read_run_log", {"run_id": chat.host.service.state["run_id"], "limit": 2})
        assert "run_started" in json.dumps(body)
        assert "run_id" in json.dumps(body)
        return answer("developed and tested")
    state["respond"] = respond
    result = asyncio.run(chat.run("develop and trial", options))
    assert result["status"] == "completed", result
    assert result["round"] == 1 and result["requests"] == 6
    assert chat.host.manager.default_manifest_id() == original_default
    assert {"publish", "trial_run", "list_runs", "read_run_log"} <= {
        item["function"]["name"] for item in state["calls"][-1]["tools"]}


@pytest.mark.parametrize("cancel_round", [False, True])
def test_trial_stop_or_round_cancel_waits_for_cleanup(conversation, monkeypatch, cancel_round):
    import threading
    from lalc.runtime import UserInterruption
    chat, options, state = conversation
    entered, cleaned = threading.Event(), threading.Event()
    identity = chat.host.manager.default_manifest_id()
    def run(_manifest, _name, _component, _inputs, gate):
        gate.pause()
        entered.set()
        try:
            gate.checkpoint()
        except UserInterruption:
            return {"status": "failure", "failure_code": "user_cancelled"}
        finally:
            cleaned.set()
    monkeypatch.setattr(chat.host.service, "_run", run)
    script(state, [tool("trial_run", {"manifest_id": identity, "logical_name": "steps.total", "inputs": {"values": []}}), answer("stopped")])
    async def interact():
        task = asyncio.create_task(chat.run("trial", options))
        try:
            assert await asyncio.to_thread(entered.wait, 15)
            if cancel_round:
                task.cancel()
            else:
                chat.host.service.stop()
            return await asyncio.wait_for(task, 10)
        finally:
            chat.host.service.stop()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    result = asyncio.run(interact())
    assert result["status"] == ("cancelled" if cancel_round else "completed"), result
    assert cleaned.is_set() and chat.host.service.state["phase"] == "finished"
    assert chat.host.service.state["activity"] is None
    if not cancel_round:
        assert "用户主动停止" in json.dumps(state["calls"][-1], ensure_ascii=False)


def test_request_limit_ends_round_and_next_round_resets(conversation):
    chat, options, state = conversation
    options.max_requests = 2
    state["respond"] = lambda body: tool("read", {"path": "steps.total.py"})
    limited = asyncio.run(chat.run("inspect repeatedly", options))
    assert limited["reason"] == "request_limit", limited
    assert limited["requests"] == len(state["calls"]) == 2
    state["respond"] = lambda body: answer("continue")
    continued = asyncio.run(chat.run("now answer", options))
    assert continued["status"] == "completed", continued
    assert continued["requests"] == 1


def test_cancel_reaps_process_and_keeps_candidate_and_log(conversation):
    chat, options, state = conversation
    state["block"] = True
    original = (chat.host.candidate / "steps.total.py").read_bytes()
    async def cancel():
        task = asyncio.create_task(chat.run("cancel me", options))
        try:
            async with asyncio.timeout(15):
                while not state["started"].is_set():
                    if task.done():
                        pytest.fail(f"Repair ended before the model request: {task.result()}")
                    await asyncio.sleep(.01)
            task.cancel()
            return await task
        finally:
            state["release"].set()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    result = asyncio.run(cancel())
    assert result["status"] == "cancelled", result
    assert chat.host.service.state["activity"] is None
    assert (chat.host.candidate / "steps.total.py").read_bytes() == original
    assert (chat.log.path / "round-1" / "result.json").exists()


def live_conversation(tmp_path):
    """只在显式提供连接时调用真实模型，全部草稿和产物使用测试目录。"""
    import os
    endpoint, model = os.environ.get("LALC_REPAIR_TEST_BASE_URL"), os.environ.get("LALC_REPAIR_TEST_MODEL")
    if not endpoint or not model:
        pytest.skip("Set LALC_REPAIR_TEST_BASE_URL and LALC_REPAIR_TEST_MODEL for real-model acceptance")
    host, _ = host_for(tmp_path)
    options = SimpleNamespace(pi="pi", ask_api_key=False, base_url=endpoint, model=model, max_requests=20)
    return host.conversation, options


def test_real_model_repairs_fixed_pure_case(tmp_path):
    import runpy
    chat, options = live_conversation(tmp_path)
    before = {p: p.read_bytes() for p in chat.host.service.data_root.rglob("*") if p.is_file()}
    image = Path(__file__).resolve().parents[1] / "test_pi_img.png"
    result = asyncio.run(chat.run("修复 steps.total.py：输入 values 的所有数值都应计入总和，包含负数；请实际 read、edit、validate。",
                                 options, images=[image]))
    print(f"Real model repair evidence: {chat.log.path}")
    assert result["status"] == "completed", result
    assert chat.host.validate()["ok"]
    execute = runpy.run_path(str(chat.host.candidate / "steps.total.py"))["execute"]
    for values in ([], [-3, 2], [1, 4], [-5, -8]):
        assert execute(None, values=values) == sum(values)
    assert all(p.read_bytes() == content for p, content in before.items())


def test_real_model_inspects_assets_and_actions(tmp_path):
    chat, options = live_conversation(tmp_path)
    result = asyncio.run(chat.run("只分析。实际调用 asset_tree 和 action_contracts，简短报告结果，不修改候选。", options))
    print(f"Real model inspection evidence: {chat.log.path}")
    assert result["status"] == "completed", result
    events = [row["event"] for row in read_events(chat.log.path / "events.jsonl")]
    assert {"asset_tree", "action_contracts"} <= {e.get("name") for e in events if e.get("type") == "repair_tool" and not e["result"].get("isError")}


def test_windows_saved_dpapi_secret_authenticates_real_model(tmp_path):
    import os
    import sys
    import shutil
    from lalc.application import default_data_root
    from lalc.agent_settings import save_settings, secret_path
    from lalc.pi_probe import _models
    if sys.platform != "win32":
        pytest.skip("Requires real Windows DPAPI")
    name = os.environ.get("LALC_REPAIR_TEST_SECRET_NAME")
    if not name:
        pytest.skip("Set LALC_REPAIR_TEST_SECRET_NAME")
    chat, options = live_conversation(tmp_path)
    with pytest.raises(ValueError, match="authentication failed"):
        _models(options.base_url.rstrip("/"), "lalc-no-key")
    target = secret_path(chat.host.service.data_root, name)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(secret_path(default_data_root(), name), target)
    save_settings(chat.host.service.data_root, {"secret_name": name})
    result = asyncio.run(chat.run("请确认收到此消息，结束本轮。", options))
    print(f"Windows authenticated model evidence: {chat.log.path}")
    assert result["status"] == "completed", result


def test_windows_real_model_captures_and_reuses_crop(tmp_path):
    import os
    import sys
    if sys.platform != "win32":
        pytest.skip("Requires real Windows game window")
    region = os.environ.get("LALC_REPAIR_TEST_REGION")
    if not region:
        pytest.skip("Set LALC_REPAIR_TEST_REGION to a stable client pixel rectangle")
    chat, options = live_conversation(tmp_path)
    # 绕过测试套件的公共平台替身，验收必须使用真实 Win32 服务。
    from lalc.focused import WindowsWindowPlatform
    chat.tools.platform = WindowsWindowPlatform(checkpoint=chat.tools.checkpoint)
    message = ("不改候选。调用 game_screenshot，然后分别 preview_crop 并用返回的 preview_id 调用 crop_asset 保存两次，logical_name=acceptance/live，region="
               + region + "。第一次预览 tags=[\"keep\"]，第二次预览 tags=[\"replace\"]，报告工具结果后结束本轮。")
    result = asyncio.run(chat.run(message, options))
    print(f"Windows live screenshot/crop evidence: {chat.log.path}")
    assert result["status"] == "completed", result
    events = [row["event"] for row in read_events(chat.log.path / "events.jsonl")]
    crops = [e["result"]["details"] for e in events if e.get("type") == "repair_tool" and e.get("name") == "crop_asset" and not e["result"].get("isError")]
    assert len(crops) >= 2
    assert not crops[0]["existed"] and crops[1]["existed"]
    assert crops[0]["sha256"] == crops[1]["sha256"] and crops[1]["tags"] == ["keep"]


def test_unloaded_model_reaches_inference_without_management_load_request(conversation):
    chat, options, state = conversation
    state["models"] = [{"id": "gemma4-test", "status": {"value": "unloaded"}}]
    result = asyncio.run(chat.run("只分析，不修改。", options))
    assert result["status"] == "completed", result
    assert len(state["calls"]) == result["requests"] == 1
    assert state["get_paths"] == ["/v1/models"]
    assert all(path == "/v1/chat/completions" for path in state["post_paths"])


@pytest.mark.parametrize("invalid", ['您好！\n```json\n{"revise_success":false,"message":"说明"}\n```',
                                    'not json', '{"revise_success":"false","message":"说明"}'])
def test_invalid_final_gets_error_feedback_then_strict_json_without_tools(conversation, invalid):
    chat, options, state = conversation
    calls = []
    def respond(body):
        calls.append(body)
        if len(calls) == 1:
            return {"role": "assistant", "content": invalid}, "stop"
        assert not body.get("tools")
        assert "只纠正最终 JSON" in json.dumps(body["messages"], ensure_ascii=False)
        assert "外层不加代码围栏" in json.dumps(body["messages"], ensure_ascii=False)
        assert "当前没有启用工具。" in body["messages"][0]["content"]
        return answer("已联通，仅分析。")
    state["respond"] = respond
    before = {p.name: p.read_bytes() for p in chat.host.candidate.iterdir()}
    result = asyncio.run(chat.run("测试联通", options))
    assert result["status"] == "completed", result
    assert result["answer"] == {"revise_success": False, "message": "已联通，仅分析。"}
    assert len(state["calls"]) == result["requests"] == 2
    for index, payload in enumerate(state["calls"], 1):
        system = "\n".join(message["content"] for message in payload["messages"] if message["role"] == "system")
        assert "本轮模型请求第" not in system and "<cwd>" not in system
        assert "对象外不加解释或代码围栏" in system
        assert "内部可用 Markdown" in system
        assert f"本轮模型请求第 {index}/20 次" in json.dumps(payload["messages"][-1], ensure_ascii=False)
    assert all(not ({"max_tokens", "max_completion_tokens", "max_output_tokens"} & body.keys())
               for body in state["calls"])
    assert any(part.get("text") == invalid for message in chat.history for part in message.get("content", []))
    assert {p.name: p.read_bytes() for p in chat.host.candidate.iterdir()} == before
    events = [row["event"] for row in read_events(chat.log.path / "events.jsonl")]
    retry = next(e for e in events if e.get("type") == "final_answer_retry")
    assert retry["diagnostics"]["raw_text"] == invalid
    assert retry["diagnostics"]["stage"] == "final_answer"


@pytest.mark.parametrize("limit", [2, 3])
def test_invalid_final_retries_never_exceed_round_budget(conversation, limit):
    chat, options, state = conversation
    options.max_requests = limit
    state["respond"] = lambda body: ({"role": "assistant", "content": "invalid"}, "stop")
    result = asyncio.run(chat.run("测试", options))
    assert result["reason"] == "request_limit" and result["status"] == "incomplete"
    assert result["diagnostics"]["raw_text"] == "invalid" and result["diagnostics"]["budget_exhausted"]
    assert len(state["calls"]) == result["requests"] == limit


def test_output_truncation_records_reason_and_does_not_format_retry(conversation):
    chat, options, state = conversation
    state["respond"] = lambda body: ({"role": "assistant", "reasoning_content": "unfinished reasoning"}, "length")
    result = asyncio.run(chat.run("测试截断", options))
    assert result["reason"] == "output_limit", result
    assert len(state["calls"]) == result["requests"] == 1
    details = result["diagnostics"]
    assert details["stop_reason"] == "length" and details["text_chars"] == 0
    assert details["thinking_chars"] == len("unfinished reasoning")
    assert details["stage"] == "provider_request"
    events = [row["event"] for row in read_events(chat.log.path / "events.jsonl")]
    assert not any(event.get("type") == "final_answer_retry" for event in events)


@pytest.mark.parametrize("failure", ["unauthorized", "provider_error", "invalid_final"])
def test_setup_and_final_failures_preserve_candidate_and_do_not_auto_continue(conversation, failure):
    chat, options, state = conversation
    before = {p.name: p.read_bytes() for p in chat.host.candidate.iterdir()}
    if failure == "unauthorized":
        state["get_status"] = 401
    elif failure == "provider_error":
        state["status"] = 503
    else:
        options.max_requests = 2
        state["respond"] = lambda body: ({"role": "assistant", "content": "invalid final"}, "stop")
    result = asyncio.run(chat.run("message retained despite failure", options, key="test-only-key"))
    assert result["status"] == "incomplete", result
    if failure == "invalid_final":
        assert result["diagnostics"]["stage"] == "final_answer"
        assert result["diagnostics"]["raw_text"] == "invalid final"
        assert result["diagnostics"]["parse_offset"] == 0
    assert len(state["calls"]) == {"unauthorized": 0, "provider_error": 1, "invalid_final": 2}[failure]
    assert {p.name: p.read_bytes() for p in chat.host.candidate.iterdir()} == before
    assert "message retained despite failure" in json.dumps(chat.history)
    assert chat.host.service.state["activity"] is None
    assert all(b"test-only-key" not in p.read_bytes() for p in chat.log.path.rglob("*") if p.is_file())


def test_live_asset_tool_images_retained_across_rounds_without_overwrite(conversation):
    from test_focused_observation import FakeWindowPlatform
    chat, options, state = conversation
    platform = FakeWindowPlatform()
    platform.capture = lambda hwnd, width, height: bytes([10, 20, 30, 255]) * width * height
    chat.tools.platform = platform
    region = {"x": 0, "y": 0, "width": 1, "height": 1}
    crop = {"logical_name": "ui/new", "region": region, "tags": ["keep"]}
    def save_preview(_body):
        return tool("crop_asset", {"preview_id": next(reversed(chat.tools.previews))})
    steps = iter([lambda body: tool("game_screenshot", {}), lambda body: tool("preview_crop", crop), save_preview, lambda body: answer()])
    state["respond"] = lambda body: next(steps)(body)
    first = asyncio.run(chat.run("inspect and crop", options))
    assert first["status"] == "completed", first
    for index, body in enumerate(state["calls"], 1):
        assert read_json(chat.log.path / f"round-1/request-{index}.json") == chat.log.clean(body)
    first_requests = len(state["calls"])
    retained = {p: p.read_bytes() for p in chat.log.path.glob("tool-*") if p.is_file()}
    steps = iter([lambda body: tool("preview_crop", {**crop, "tags": ["replace"]}), save_preview, lambda body: answer()])
    state["respond"] = lambda body: next(steps)(body)
    second = asyncio.run(chat.run("reuse the same crop", options))
    assert second["status"] == "completed", second
    for index, body in enumerate(state["calls"][first_requests:], 1):
        assert read_json(chat.log.path / f"round-2/request-{index}.json") == chat.log.clean(body)
    assert all(p.read_bytes() == value for p, value in retained.items())
    assert "data:image/png;base64," in json.dumps(state["calls"][-1])
    mapping = json.loads((chat.host.service.data_root / "assets/ui/new/asset-tag.json").read_text())
    assert list(mapping.values()) == [["keep"]]


def test_each_request_sees_current_budget_and_next_message_resets(conversation):
    chat, options, state = conversation
    options.max_requests = 3
    script(state, [tool("read", {"path": "steps.total.py"}), answer("done")])
    events = []
    result = asyncio.run(chat.run("inspect then answer", options, on_event=events.append))
    assert result["status"] == "completed" and result["requests"] == 2
    first_calls = list(state["calls"])
    for index, payload in enumerate(first_calls, 1):
        system = "\n".join(message["content"] for message in payload["messages"] if message["role"] == "system")
        latest = json.dumps(payload["messages"][-1], ensure_ascii=False)
        assert payload["messages"][-1]["role"] == "user"
        assert f"当前对话第 1 轮；本轮模型请求第 {index}/3 次" in latest
        assert f"还可请求 {3 - index} 次" in latest
        assert "当前对话第" not in system
        assert "<cwd>" not in system and "lalc-pi-" not in system
        assert "达到上限后必须停止" in system
    assert first_calls[1]["messages"][:len(first_calls[0]["messages"])] == first_calls[0]["messages"]
    assert first_calls[0]["messages"][0] == first_calls[1]["messages"][0]
    requests = [event["event"] for event in events if event["event"]["type"] == "lalc_request"]
    assert [(value["requests"], value["request_limit"]) for value in requests] == [(1, 3), (2, 3)]
    options.max_requests = 2
    state["respond"] = lambda _: answer("next")
    result = asyncio.run(chat.run("next message", options))
    assert result["status"] == "completed" and result["requests"] == 1
    for index, payload in enumerate(state["calls"][2:], 1):
        system = "\n".join(message["content"] for message in payload["messages"] if message["role"] == "system")
        assert f"当前对话第 2 轮；本轮模型请求第 {index}/2 次" in json.dumps(payload["messages"][-1], ensure_ascii=False)
        assert "当前对话第" not in system
    assert state["calls"][-1]["messages"][:len(first_calls[-1]["messages"])] == first_calls[-1]["messages"]
    budgets = [message for message in chat.history if "LALC_REQUEST_BUDGET" in json.dumps(message)]
    assert len(budgets) == 3  # 所有正式请求的通知均进入修复历史。
    assert read_json(chat.log.path / "context.json") == chat.history


def test_add_both_source_kinds_then_edit_new_files_in_same_round(conversation):
    from test_add_source import COMPONENT, RULE
    chat, options, state = conversation
    script(state, [
        tool("add_component", {"filename": "new/step.py", "logical_name": "steps.new", "source": COMPONENT}),
        tool("add_recovery_rule", {"filename": "new/rule.py", "logical_name": "rules.new", "source": RULE}),
        tool("edit", {"path": "new/step.py", "oldText": 'return "new"', "newText": 'return "edited"'}),
        tool("edit", {"path": "new/rule.py", "oldText": "return False", "newText": "return True"}),
        tool("validate", {}), answer("created and edited")])
    result = asyncio.run(chat.run("add both kinds", options))
    assert result["status"] == "completed", result
    assert 'return "edited"' in (chat.host.candidate / "new/step.py").read_text()
    assert "return True" in (chat.host.candidate / "new/rule.py").read_text()
    assert chat.host.validate()["ok"]
    assert (chat.log.path / "round-1/final/new/step.py").exists()
    assert "new/step.py" in (chat.log.path / "round-1/cumulative.diff").read_text()
    assert any(message.get("toolName") == "add_component" for message in chat.history)


def test_multiple_image_formats_are_forwarded_without_conversion_and_retained(conversation, tmp_path):
    from test_image_attachments import make_images
    import base64
    chat, options, state = conversation
    paths = make_images(tmp_path)
    expected = ["image/png", "image/jpeg", "image/webp", "image/gif", "image/bmp", "image/tiff", "image/avif"]
    result = asyncio.run(chat.run("inspect all images", options, images=paths))
    assert result["status"] == "completed", result
    assert result["requests"] == 1
    for payload in state["calls"]:
        urls = [part["image_url"]["url"] for message in payload["messages"] if isinstance(message.get("content"), list)
                for part in message["content"] if part["type"] == "image_url"]
        assert len(urls) == len(paths)
        for url, mime, path in zip(urls, expected, paths):
            prefix, data = url.split(",", 1)
            assert prefix == f"data:{mime};base64"
            assert base64.b64decode(data) == path.read_bytes()
    files = read_json(chat.log.path / "round-1/input.json")["attachments"]
    assert len(files) == len(paths)
    originals = {path: path.read_bytes() for path in (chat.log.path / "round-1").glob("input-*.*")}
    result = asyncio.run(chat.run("remember images from previous message", options))
    assert result["status"] == "completed", result
    urls = [part["image_url"]["url"] for message in state["calls"][-1]["messages"] if isinstance(message.get("content"), list)
            for part in message["content"] if part["type"] == "image_url"]
    assert len(urls) == len(paths)
    assert all(path.read_bytes() == value for path, value in originals.items())


def test_image_batch_service_rejection_keeps_details_and_no_automatic_retry(conversation, tmp_path):
    from test_image_attachments import make_images
    chat, options, state = conversation
    paths = make_images(tmp_path, ("PNG", "JPEG"))
    state["status"], state["error_message"] = 413, "too many image bytes"
    result = asyncio.run(chat.run("send images", options, images=paths))
    assert result["status"] == "incomplete" and result["requests"] == 1
    assert "too many image bytes" in result["error"]
    assert len(state["calls"]) == 1
    assert len(read_json(chat.log.path / "round-1/input.json")["attachments"]) == 2


def test_images_stay_original_during_format_correction(conversation, tmp_path):
    from test_image_attachments import make_images
    import base64
    chat, options, state = conversation
    paths = make_images(tmp_path, ("JPEG", "BMP"))
    script(state, [({"role": "assistant", "content": "not json"}, "stop"), answer()])
    result = asyncio.run(chat.run("inspect then answer as JSON", options, images=paths))
    assert result["status"] == "completed" and result["requests"] == 2, result
    for payload in state["calls"]:
        urls = [part["image_url"]["url"] for message in payload["messages"] if isinstance(message.get("content"), list)
                for part in message["content"] if part["type"] == "image_url"]
        assert len(urls) == 2
        assert [base64.b64decode(url.split(",", 1)[1]) for url in urls] == [path.read_bytes() for path in paths]


def test_cancel_waits_for_new_source_rollback_before_final_snapshot(conversation, monkeypatch):
    import threading
    from lalc.developer import candidate_files
    from test_add_source import COMPONENT
    chat, options, state = conversation
    before = candidate_files(chat.host.candidate)
    original = chat.host.add_source
    entered = threading.Event()
    def slow_add(section, filename, logical_name, source, checkpoint):
        def pause_after_write():
            if (chat.host.candidate / filename).exists():
                entered.set()
                if not chat.tools.cancelled.wait(10):
                    raise TimeoutError("test cancellation did not arrive")
            checkpoint()
        return original(section, filename, logical_name, source, pause_after_write)
    monkeypatch.setattr(chat.host, "add_source", slow_add)
    state["respond"] = lambda _: tool("add_component", {"filename": "new/cancel.py", "logical_name": "steps.new", "source": COMPONENT})
    async def exercise():
        task = asyncio.create_task(chat.run("cancel new source transaction", options))
        try:
            async with asyncio.timeout(15):
                while not entered.is_set():
                    if task.done():
                        pytest.fail(str(task.result()))
                    await asyncio.sleep(.01)
            task.cancel()
            return await task
        finally:
            chat.tools.cancelled.set()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    result = asyncio.run(exercise())
    assert result["status"] == "cancelled", result
    assert candidate_files(chat.host.candidate) == before
    assert not (chat.host.candidate / "new").exists()
    assert not (chat.log.path / "round-1/final/new/cancel.py").exists()


def test_host_and_pi_events_share_call_ids_without_removing_raw_logs(conversation):
    chat, options, state = conversation
    calls = []
    for name, arguments, identity in [
        ("action_contracts", {}, "contract-first"),
        ("action_contracts", {}, "contract-second"),
        ("read", {"path": "steps.total.py"}, "read-source"),
        ("edit", {"path": "steps.total.py", "oldText": "if value > 0", "newText": "if value >= 0"}, "edit-source"),
        ("validate", {}, "validate-draft"),
    ]:
        response = tool(name, arguments)
        response[0]["tool_calls"][0]["id"] = identity
        calls.append(response)
    script(state, [*calls, answer()])
    result = asyncio.run(chat.run("inspect contracts twice, read, edit and validate", options))
    assert result["status"] == "completed", result
    events = [row["event"] for row in read_events(chat.log.path / "events.jsonl")]
    hosted = [event for event in events if event["type"] == "repair_tool"]
    assert len(hosted) == 2
    assert len({event["toolCallId"] for event in hosted}) == 2
    completed = {event["toolCallId"]: event for event in events if event["type"] == "tool_execution_end"}
    for event in hosted:
        assert completed[event["toolCallId"]]["toolName"] == "action_contracts"
        assert completed[event["toolCallId"]]["result"] == event["result"]
    validation = next(event for event in events if event["type"] == "validation")
    assert completed[validation["toolCallId"]]["toolName"] == "validate"
    assert {"read", "edit"} <= {event["toolName"] for event in completed.values()}


@pytest.mark.parametrize('thinking,effort', [(True, 'high'), (True, 'low'), (True, 'max'), (False, 'high')])
def test_deepseek_thinking_survives_tools_and_next_round(conversation, tmp_path, thinking, effort):
    from test_image_attachments import make_images

    chat, options, state = conversation
    options.provider, options.model = 'deepseek', 'deepseek-flash'
    options.thinking, options.reasoning_effort = thinking, effort
    state['models'] = [{'id': 'deepseek-flash'}]
    first, finish_reason = tool('read', {'path': 'steps.total.py'})
    first['reasoning_content'] = 'Inspect source before answering.'
    second, stop = answer('first deepseek result')
    second['reasoning_content'] = 'Source inspection completed.'
    third, third_reason = tool('action_contracts', {})
    third['reasoning_content'] = 'Check available actions too.'
    script(state, [(first, finish_reason), (third, third_reason), (second, stop)])
    result = asyncio.run(chat.run('inspect with deepseek', options, key='deepseek-test-key',
                                 images=make_images(tmp_path, ('PNG',))))
    assert result['status'] == 'completed', result
    assert result['requests'] == 3
    state['respond'] = lambda body: answer('second deepseek result')
    result = asyncio.run(chat.run('continue deepseek discussion', options, key='deepseek-test-key'))
    assert result['status'] == 'completed', result
    payload = state['calls'][-1]
    assistant = [m for m in payload['messages'] if m['role'] == 'assistant']
    assert [m['reasoning_content'] for m in assistant] == [
        'Inspect source before answering.', 'Check available actions too.', 'Source inspection completed.']
    # 连续工具调用及新一轮均完整保留先前实际请求的消息前缀。
    for previous, current in ((0, 1), (1, 2), (2, 3)):
        before = state['calls'][previous]['messages']
        assert state['calls'][current]['messages'][:len(before)] == before
    for payload in state['calls']:
        assert payload['model'] == 'deepseek-flash'
        assert payload['thinking'] == {'type': 'enabled' if thinking else 'disabled'}
        if thinking:
            assert payload['reasoning_effort'] == effort
        else:
            assert 'reasoning_effort' not in payload
        assert all(m['role'] != 'developer' for m in payload['messages'])
    assert state['authorization'] == 'Bearer deepseek-test-key'
    assert all(b'deepseek-test-key' not in path.read_bytes()
               for path in chat.log.path.rglob('*') if path.is_file())


def test_python_plan_edit_publish_and_saved_trial_ignore_unpublished_changes(conversation, monkeypatch):
    """真实 pi 工具协议编辑 Plan；未发布后续修改不能进入试运行。"""
    chat, options, state = conversation
    monkeypatch.setattr(chat.host.service, "_start_session", lambda: None)
    original = chat.host.manager.default_manifest_id()
    step = 0
    def respond(body):
        nonlocal step
        step += 1
        if step == 1:
            return tool("edit", {"path": "plans.default.py", "oldText": "-> None:\n    return None",
                                 "newText": '-> Any:\n    return {"value": 7}'})
        if step == 2:
            return tool("publish", {})
        if step == 3:
            return tool("edit", {"path": "plans.default.py", "oldText": '{"value": 7}',
                                 "newText": '{"value": 9}'})
        if step == 4:
            saved = next(m["manifest_id"] for m in chat.host.manager.list_manifests() if m["manifest_id"] != original)
            return tool("trial_run", {"manifest_id": saved})
        if step == 5:
            result = chat.host.service.state["result"]
            assert result["status"] == "completed" and result["output"] == {"value": 7}
            return tool("read_run_log", {"run_id": chat.host.service.state["run_id"], "limit": 2})
        return answer("Plan published and tested")
    state["respond"] = respond
    result = asyncio.run(chat.run("edit, publish and trial Python Plan", options))
    assert result["status"] == "completed", result
    assert chat.host.manager.default_manifest_id() == original
    assert '{"value": 9}' in (chat.host.candidate / "plans.default.py").read_text()


def test_round_freezes_shared_config_and_auth_until_next_message(conversation):
    """轮次中清除/替换凭据和额度不改变当前工具循环，下一轮读取新设置。"""
    from lalc.agent_settings import save_settings
    chat, original, state = conversation
    root, keys = chat.host.service.data_root, chat.host.secrets
    save_settings(root, {"base_url": original.base_url, "model": original.model, "max_requests": 6},
                  secret="example-round-A", temporary_keys=keys)
    seen = []
    def respond(body):
        seen.append(state["authorization"])
        if len(seen) == 1:
            save_settings(root, {}, clear=True, temporary_keys=keys)
            save_settings(root, {"max_requests": 7}, secret="example-round-B", temporary_keys=keys)
            return tool("read", {"path": "steps.total.py"})
        return answer("finished")
    state["respond"] = respond
    args = SimpleNamespace(pi="pi", ask_api_key=False)
    first = asyncio.run(chat.run("inspect source", args))
    assert first["status"] == "completed", first
    assert seen == ["Bearer example-round-A", "Bearer example-round-A"]
    second = asyncio.run(chat.run("continue", args))
    assert second["status"] == "completed", second
    assert seen[-1] == "Bearer example-round-B"
    assert read_json(chat.log.path / "round-1/input.json")["settings"]["max_requests"] == 6
    assert read_json(chat.log.path / "round-2/input.json")["settings"]["max_requests"] == 7
    for path in chat.log.path.rglob("*"):
        if path.is_file():
            assert b"example-round-A" not in path.read_bytes()
            assert b"example-round-B" not in path.read_bytes()


def test_two_invalid_final_answers_retry_automatically_and_preserve_business_reply(conversation):
    chat, options, state = conversation
    invalid = '```json\n{"revise_success":false,"message":"I can inspect the Candidate."}\n```'
    steps = iter([({'role': 'assistant', 'content': invalid}, 'stop'),
                  ({'role': 'assistant', 'content': 'not JSON'}, 'stop'),
                  answer('I can inspect the Candidate.')])
    payloads = []
    def respond(body):
        payloads.append(body)
        if len(payloads) > 1:
            assert not body.get('tools')
            assert '保留上次回复中真正回答开发者问题的内容' in json.dumps(body, ensure_ascii=False)
            assert '不要要求用户重发问题' in json.dumps(body, ensure_ascii=False)
        return next(steps)
    state['respond'] = respond
    before = {path: path.read_bytes() for path in chat.host.candidate.rglob('*') if path.is_file()}
    result = asyncio.run(chat.run('Tell me what you can see', options))
    assert result['status'] == 'completed' and result['requests'] == 3, result
    assert result['answer']['message'] == 'I can inspect the Candidate.'
    assert all(path.read_bytes() == value for path, value in before.items())
    events = list(read_events(chat.log.root / 'events.jsonl'))
    assert len([row for row in events if row['event']['type'] == 'final_answer_retry']) == 2


def test_live_raw_output_is_forwarded_without_preflight_or_history_storage(conversation):
    """真实 pi 的 thinking / 工具参数 / 文字在 message_end 前通知，日志只留完整消息。"""
    chat, options, state = conversation
    options.provider = 'deepseek'
    options.model = 'deepseek-flash'
    state['models'] = [{'id': 'deepseek-flash'}]
    script(state, [tool('read', {'path': 'steps.total.py'}),
                   ({'role': 'assistant', 'reasoning_content': 'Inspect raw-stream-secret',
                     'content': json.dumps({'revise_success': False, 'message': 'finished'})}, 'stop')])
    events = []
    result = asyncio.run(chat.run('inspect source', options, key='raw-stream-secret', on_event=events.append))
    assert result['status'] == 'completed' and result['requests'] == 2, result
    assert len(state['calls']) == 2
    live = [row['event'] for row in events if row['event']['type'] == 'raw_output']
    assert live
    parts = [part for event in live for part in event['content']]
    assert any(part.get('name') == 'read' for part in parts)
    assert any('steps.total.py' in json.dumps(part) for part in parts)
    assert any(part.get('thinking') == 'Inspect [REDACTED]' for part in parts)
    assert any('finished' in part.get('text', '') for part in parts)
    first_stream = next(i for i, row in enumerate(events) if row['event']['type'] == 'raw_output')
    first_end = next(i for i, row in enumerate(events) if row['event']['type'] == 'message_end'
                     and row['event'].get('message', {}).get('role') == 'assistant')
    assert first_stream < first_end
    assert 'raw-stream-secret' not in json.dumps(events)
    saved = list(read_events(chat.log.root / 'events.jsonl'))
    assert not any(row['event']['type'] in {'raw_output', 'message_update', 'model_check_started'} for row in saved)
    assert not (chat.log.root / 'round-1/events.jsonl').exists()
    assert (chat.log.root / 'round-1/request-1.json').exists()
