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

from test_pi_probe import probe
from test_agent_repair import host_for

pytestmark = pytest.mark.agent


def tool(name, arguments):
    return {"role": "assistant", "tool_calls": [{"index": 0, "id": "call-" + name, "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments)}}]}, "tool_calls"


def answer(text="answered"):
    return {"role": "assistant", "content": json.dumps({"revise_success": False, "message": text})}, "stop"


@pytest.fixture
def conversation(probe, tmp_path):
    command, state, _ = probe
    host, _ = host_for(tmp_path / "project")
    options = SimpleNamespace(pi="pi", ask_api_key=False,
                             base_url=command[command.index("--base-url") + 1], model="gemma4-test", max_requests=20)
    state["repair_check"] = True
    state["respond"] = lambda body: answer()
    return host.new_conversation(), options, state


def script(state, steps):
    iterator = iter(steps)
    state["respond"] = lambda body: next(iterator)


def test_multifile_edit_manifest_and_plan_enforced(conversation):
    chat, options, state = conversation
    candidate = chat.host.candidate
    manifest = (candidate / "manifest.json").read_text()
    (candidate / "plan.json").write_text("{}")
    (candidate / "temporary.py").write_text("# before")
    (candidate / "outside-link.py").symlink_to(candidate.parent / "outside.py")
    # 候选符号链接在进入模型前拒绝，不依赖文件选择。
    with pytest.raises(ValueError):
        asyncio.run(chat.run("test", options))
    (candidate / "outside-link.py").unlink()
    script(state, [
        tool("edit", {"path": "steps.total.py", "oldText": "if value > 0", "newText": "if value >= 0"}),
        tool("edit", {"path": "manifest.json", "oldText": manifest, "newText": "{invalid json"}),
        tool("edit", {"path": "plan.json", "oldText": "{}", "newText": "hacked"}),
        tool("edit", {"path": "steps.unchanged.py", "oldText": 'return "unchanged"', "newText": 'return "changed"'}),
        tool("edit", {"path": "temporary.py", "oldText": "# before", "newText": "# after"}),
        tool("edit", {"path": "new.py", "oldText": "", "newText": "created"}),
        tool("validate", {}), answer("need another round")])
    result = asyncio.run(chat.run("edit multiple existing files", options))
    assert result["status"] == "completed", result
    assert "if value >= 0" in (candidate / "steps.total.py").read_text()
    assert (candidate / "manifest.json").read_text() == "{invalid json"
    assert (candidate / "plan.json").read_text() == "{}"
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
    assert first["requests"] == 3
    state["respond"] = lambda body: answer("second result")
    second = asyncio.run(chat.run("second user message", options, key="test-private-key"))
    assert second["status"] == "completed", second
    assert second["requests"] == 2
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
    assert continued["requests"] == 2


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
    image = (Path(__file__).resolve().parents[1] / "test_pi_img.png").read_bytes()
    result = asyncio.run(chat.run("修复 steps.total.py：输入 values 的所有数值都应计入总和，包含负数；请实际 read、edit、validate。",
                                 options, image=image))
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
    events = [json.loads(line)["event"] for line in (chat.log.path / "events.jsonl").read_text().splitlines()]
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
    message = ("不改候选。调用 game_screenshot，然后连续调用两次 crop_asset，logical_name=acceptance/live，region="
               + region + "。第一次 tags=[\"keep\"]，第二次 tags=[\"replace\"]，报告工具结果后结束本轮。")
    result = asyncio.run(chat.run(message, options))
    print(f"Windows live screenshot/crop evidence: {chat.log.path}")
    assert result["status"] == "completed", result
    events = [json.loads(line)["event"] for line in (chat.log.path / "events.jsonl").read_text().splitlines()]
    crops = [e["result"]["details"] for e in events if e.get("type") == "repair_tool" and e.get("name") == "crop_asset" and not e["result"].get("isError")]
    assert len(crops) >= 2
    assert not crops[0]["existed"] and crops[1]["existed"]
    assert crops[0]["sha256"] == crops[1]["sha256"] and crops[1]["tags"] == ["keep"]


def test_unloaded_model_reaches_inference_without_management_load_request(conversation):
    chat, options, state = conversation
    state["models"] = [{"id": "gemma4-test", "status": {"value": "unloaded"}}]
    result = asyncio.run(chat.run("只分析，不修改。", options))
    assert result["status"] == "completed", result
    assert len(state["calls"]) == result["requests"] == 2
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
        assert "严格 JSON 校验" in json.dumps(body["messages"], ensure_ascii=False)
        return answer("已联通，仅分析。")
    state["respond"] = respond
    before = {p.name: p.read_bytes() for p in chat.host.candidate.iterdir()}
    result = asyncio.run(chat.run("测试联通", options))
    assert result["status"] == "completed", result
    assert result["answer"] == {"revise_success": False, "message": "已联通，仅分析。"}
    assert len(state["calls"]) == result["requests"] == 3
    for index, payload in enumerate(state["calls"], 1):
        system = "\n".join(message["content"] for message in payload["messages"] if message["role"] == "system")
        assert f"本轮模型请求第 {index}/20 次" in system
    assert all(not ({"max_tokens", "max_completion_tokens", "max_output_tokens"} & body.keys())
               for body in state["calls"])
    assert any(part.get("text") == invalid for message in chat.history for part in message.get("content", []))
    assert {p.name: p.read_bytes() for p in chat.host.candidate.iterdir()} == before
    events = [json.loads(line)["event"] for line in (chat.log.path / "events.jsonl").read_text().splitlines()]
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


@pytest.mark.parametrize("preflight", [False, True])
def test_output_truncation_records_reason_and_does_not_format_retry(conversation, preflight):
    chat, options, state = conversation
    if preflight:
        state["repair_check"] = False
    state["respond"] = lambda body: ({"role": "assistant", "reasoning_content": "unfinished reasoning"}, "length")
    result = asyncio.run(chat.run("测试截断", options))
    assert result["reason"] == "output_limit", result
    assert len(state["calls"]) == result["requests"] == (1 if preflight else 2)
    details = result["diagnostics"]
    assert details["stop_reason"] == "length" and details["text_chars"] == 0
    assert details["thinking_chars"] == len("unfinished reasoning")
    assert details["stage"] == ("model_preflight" if preflight else "provider_request")
    events = [json.loads(line)["event"] for line in (chat.log.path / "events.jsonl").read_text().splitlines()]
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
    script(state, [tool("game_screenshot", {}), tool("crop_asset", crop), answer()])
    first = asyncio.run(chat.run("inspect and crop", options))
    assert first["status"] == "completed", first
    retained = {p: p.read_bytes() for p in chat.log.path.glob("tool-*") if p.is_file()}
    script(state, [tool("crop_asset", {**crop, "tags": ["replace"]}), answer()])
    second = asyncio.run(chat.run("reuse the same crop", options))
    assert second["status"] == "completed", second
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
    assert result["status"] == "completed" and result["requests"] == 3
    first_calls = list(state["calls"])
    for index, payload in enumerate(first_calls, 1):
        system = "\n".join(message["content"] for message in payload["messages"] if message["role"] == "system")
        assert f"当前对话第 1 轮；本轮模型请求第 {index}/3 次" in system
        assert f"还可请求 {3 - index} 次" in system
        assert system.count("当前对话第") == 1
        assert "达到上限后必须停止" in system
    requests = [event["event"] for event in events if event["event"]["type"] == "lalc_request"]
    assert [(value["requests"], value["request_limit"]) for value in requests] == [(1, 3), (2, 3), (3, 3)]
    options.max_requests = 2
    state["respond"] = lambda _: answer("next")
    result = asyncio.run(chat.run("next message", options))
    assert result["status"] == "completed" and result["requests"] == 2
    for index, payload in enumerate(state["calls"][3:], 1):
        system = "\n".join(message["content"] for message in payload["messages"] if message["role"] == "system")
        assert f"当前对话第 2 轮；本轮模型请求第 {index}/2 次" in system
        assert "当前对话第 1 轮" not in system
    assert "当前对话第" not in json.dumps(chat.history, ensure_ascii=False)
