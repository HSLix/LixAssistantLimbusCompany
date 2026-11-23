"""覆盖远程控制、持久工作台、异步去重、审批取消及真实 HTTP 协议，不启动 pi 或模型。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_remote_mcp.py
"""

import json
from pathlib import Path
import threading
import time
import uuid

import pytest

from lalc.application import StartError
from lalc.runtime import UserInterruption
from lalc.remote_mcp import MCP_TOOLS, RemoteWorkbench
from test_agent_repair import host_for


@pytest.fixture
def remote(tmp_path, monkeypatch):
    host, saved = host_for(tmp_path)
    monkeypatch.setattr(host.service, "_start_session", lambda: None)
    value = host.service.remote_mcp
    value.initialize(saved.manifest_id)
    value.reset_token()
    value.enabled = True
    value.allow()
    yield value
    value.close()


def acquired(remote):
    return remote.acquire()["control_token"]


def wait_operation(remote, identity):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        with remote.service._condition:
            if remote.active is None:
                return remote.operation(identity)
        time.sleep(.01)
    pytest.fail("Remote operation did not settle")


def perform(remote, token, name, arguments):
    identity = str(uuid.uuid4())
    remote.invoke(name, arguments, token, identity)
    return wait_operation(remote, identity)


def test_control_is_independent_persistent_and_private(remote):
    first = remote.acquire("Chat A")
    assert first["previous_used_at"] is None
    assert "control_token" not in json.dumps(remote.snapshot())
    with pytest.raises(ValueError, match="正忙"):
        remote.acquire("Chat B")
    with pytest.raises(ValueError, match="凭据"):
        remote.release("someone else")
    with pytest.raises(StartError):
        with remote.service.activity("Agent"):
            pass
    with pytest.raises(StartError):
        remote.service.start_plan()
    remote.release(first["control_token"])
    second = remote.acquire()
    assert second["previous_used_at"] == first["workspace"]["last_used_at"]
    remote.release(second["control_token"])
    restarted = RemoteWorkbench(remote.service)
    assert not restarted.enabled and not restarted.authorized and restarted.owner is None
    assert restarted.check()["last_used_at"] == second["workspace"]["last_used_at"]


def test_remote_construct_tools_include_remote_page_read_and_update(remote):
    from lalc.agent_policy import allowed_tools
    gui_tools = set(allowed_tools("Construct", "gui"))
    remote_tools = set(MCP_TOOLS)
    assert remote_tools - gui_tools == {"page_read", "page_update"}
    assert gui_tools <= remote_tools
    token = acquired(remote)
    with pytest.raises(ValueError):
        remote.invoke("recheck", {}, token)
    assert remote.invoke("list_skills", {}, token)["details"]["skills"]


@pytest.mark.parametrize("name", ["list_manifests", "read_manifest", "add_component"])
def test_tool_results_expand_log_references_before_mcp_transport(remote, monkeypatch, name):
    """长文本、图片及字面标记经真实工具日志存储后仍完整返回，覆盖立即与异步路径。"""
    import base64
    from lalc.agent_log import read_json
    from lalc.repair_tools import RepairTools

    payload = {"source": "中文源码\n" * 400, "$lalc_log": {"user": "literal"}}
    expected = RepairTools.text(payload)
    expected["content"].append({"type": "image", "mimeType": "image/png",
                                "data": base64.b64encode(bytes(range(256)) * 8).decode()})
    monkeypatch.setattr(RepairTools, name, lambda self, **kwargs: expected)
    token = acquired(remote)
    if name == "add_component":
        op = perform(remote, token, name, {})
        assert op["status"] == "finished"
        result = remote.query(token, operation_id=op["operation_id"])["result"]
    else:
        result = remote.invoke(name, {}, token)
    assert result == expected
    # 磁盘仍保留去重引用；仅对外输出展开，审计事件也能按原契约还原。
    paths = list(remote.root.rglob("tool-*.json"))
    assert len(paths) == 1
    assert isinstance(json.loads(paths[0].read_text())["content"][0]["text"], dict)
    assert read_json(paths[0]) == expected


def test_token_hash_only_and_reset_revokes(remote):
    token = remote.reset_token()
    assert remote.authenticate(token)
    assert token not in remote.config_path.read_text()
    remote.allow()
    control = acquired(remote)
    replacement = remote.reset_token()
    assert not remote.authenticate(token) and remote.authenticate(replacement)
    with pytest.raises(ValueError):
        remote.query(control)
    assert not remote.owner and not remote.authorized
    assert token not in (remote.root / "events.jsonl").read_text()


def test_latest_is_not_default_and_reset_protects_candidate(remote):
    old = remote.check()["source_manifest_id"]
    latest = remote.host.manager.publish(remote.host.candidate / "manifest.json").loaded.manifest_id
    assert remote.host.manager.default_manifest_id() == old
    with pytest.raises(ValueError):
        remote.initialize()
    remote.initialize(replace=True)
    assert remote.check()["source_manifest_id"] == latest
    from lalc.page_drafts import PageDrafts
    drafts = PageDrafts(remote)
    from test_page_drafts import SOURCE
    drafts.create("sample.py", SOURCE)
    remote.initialize(old, replace=True)
    assert drafts.read("drafts", "sample.py")["source"] == SOURCE


def test_read_edit_boundaries_and_atomic_error(remote, tmp_path):
    token = acquired(remote)
    path = remote.host.candidate / "steps.total.py"
    original = path.read_text()
    assert remote.invoke("read", {"path": "steps.total.py", "offset": 3, "limit": 5}, token)["details"]["next_offset"] == 8
    for name in ("../outside", str(path), "C:\\outside", "missing.py"):
        with pytest.raises(ValueError):
            remote.invoke("read", {"path": name}, token)
    bad = perform(remote, token, "edit", {"path": "steps.total.py", "old_text": "not present", "new_text": "x"})
    assert bad["status"] == "failed" and path.read_text() == original
    good = perform(remote, token, "edit", {"path": "steps.total.py", "old_text": "def execute", "new_text": "def execute"})
    assert good["status"] == "finished"
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")
    (remote.host.candidate / "link.txt").symlink_to(outside)
    with pytest.raises(ValueError):
        remote.invoke("read", {"path": "link.txt"}, token)


def test_publish_and_trial_are_deduplicated_and_queryable(remote):
    token = acquired(remote)
    identity = str(uuid.uuid4())
    args = {}
    remote.invoke("validate_and_publish", args, token, identity)
    published = wait_operation(remote, identity)
    manifest_id = published["result"]["details"]["manifest_id"]
    assert remote.invoke("validate_and_publish", args, token, identity)["details"]["result"]["details"]["manifest_id"] == manifest_id
    with pytest.raises(ValueError, match="不同"):
        remote.invoke("validate_and_publish", {"summary": "changed"}, token, identity)
    trial_id = str(uuid.uuid4())
    arguments = {"manifest_id": manifest_id, "logical_name": "steps.total", "inputs": {"values": [1, -2]}}
    remote.invoke("trial_run", arguments, token, trial_id)
    trial = wait_operation(remote, trial_id)
    run_id = trial["result"]["details"]["run_id"]
    remote.service.wait_for(lambda state: state["phase"] == "finished")
    remote.invoke("trial_run", arguments, token, trial_id)
    assert remote.service.status["run_id"] == run_id
    assert remote.query(token, run_id=run_id)["result"]["output"] == 1
    assert not remote.service._runtime_allowed
    assert remote.service.state["trace"][0]["remote_operation_id"] == trial_id


def test_running_pause_debug_stop_and_revoke_cleanup(remote, monkeypatch):
    token = acquired(remote)
    entered, cleaned = threading.Event(), threading.Event()
    def run(_manifest, _name, _component, _inputs, gate, _state, _options):
        try:
            for number in range(8):
                remote.service._emit("component_log", {"level": "debug", "message": str(number)})
            remote.service.pause()
            entered.set()
            gate.checkpoint()
        except UserInterruption:
            return {"status": "failure", "failure_code": "user_cancelled"}
        finally:
            cleaned.set()
        return {"status": "success"}
    monkeypatch.setattr(remote.service, "_run", run)
    trial = perform(remote, token, "trial_run", {"manifest_id": remote.check()["source_manifest_id"],
                                                "logical_name": "steps.total", "inputs": {"values": []}})
    assert entered.wait(3)
    run_id = trial["result"]["details"]["run_id"]
    state = remote.query(token, run_id=run_id)
    assert state["status"] == "已暂停" and [r["message"] for r in state["logs"]] == ["3", "4", "5", "6", "7"]
    with pytest.raises(ValueError):
        remote.release(token)
    with pytest.raises(ValueError):
        remote.invoke("game_screenshot", {}, token, str(uuid.uuid4()))
    assert remote.invoke("read", {"path": "manifest.json"}, token)
    remote.revoke()
    remote.service.wait_for(lambda state: state["phase"] == "finished")
    assert cleaned.is_set() and not remote.owner and remote.game_lock is None
    with pytest.raises(ValueError):
        remote.query(token)


def test_waiting_local_approval_is_async_and_revocable(remote):
    token = acquired(remote)
    requests = []
    remote.on_feedback = requests.append
    identity = str(uuid.uuid4())
    remote.invoke("request_feedback", {"message": "Please confirm"}, token, identity)
    deadline = time.monotonic() + 3
    while not requests and time.monotonic() < deadline:
        time.sleep(.01)
    assert requests and remote.query(token, operation_id=identity)["status"] == "waiting_local"
    remote.revoke()
    value = wait_operation(remote, identity)
    assert value["status"] == "finished" and value["result"]["isError"]
    assert not requests[0].finish("confirmed", "late")
    assert not remote.owner


def test_restart_recovers_publish_evidence_without_replay(remote):
    token = acquired(remote)
    op = perform(remote, token, "validate_and_publish", {})
    op["status"] = "running"
    op.pop("result")
    remote._save_operation(op)
    remote.release(token)
    restored = RemoteWorkbench(remote.service)
    result = restored.operation(op["operation_id"])
    assert result["status"] == "finished" and result["result"]["details"]["manifest_id"] == op["manifest_id"]


def test_local_offline_matching_allowed_but_writes_blocked(remote):
    token = acquired(remote)
    with remote.service.activity("Template Match"):
        pass
    with remote.service.activity("Capture 保存"):
        pass
    for name in ("Sharing", "Candidate 发布", "Capture 调整窗口尺寸"):
        with pytest.raises(StartError):
            with remote.service.activity(name):
                pass
    remote.release(token)


def test_streamable_http_authentication_discovery_and_tool_call(remote):
    pytest.importorskip("mcp")
    from starlette.testclient import TestClient
    from lalc.mcp_server import make_app
    token = remote.reset_token()
    remote.config["url"] = "https://windows.example.ts.net:8443/mcp"
    with TestClient(make_app(remote), base_url="http://127.0.0.1:8765") as client:
        headers = {"Accept": "application/json, text/event-stream", "Authorization": "Bearer " + token}
        initialize = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}}
        assert client.post("/mcp", json=initialize).status_code == 401
        assert client.post("/mcp", json=initialize, headers={**headers, "Origin": "https://evil.example"}).status_code == 403
        assert client.post("/mcp", json=initialize, headers=headers).status_code == 200
        assert client.post("/mcp", json=initialize, headers={**headers, "Host": "windows.example.ts.net:8443",
            "Origin": "https://windows.example.ts.net:8443"}).status_code == 200
        listing = client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, headers=headers)
        tools = {tool["name"]: tool for tool in listing.json()["result"]["tools"]}
        assert set(MCP_TOOLS) <= tools.keys() and "recheck" not in tools and "pause" not in tools
        assert tools["read_run_log"]["inputSchema"]["properties"]["render_sequence"]["type"] == ["integer", "null"]
        search = tools["search_manifest_source"]
        assert search["annotations"]["readOnlyHint"]
        assert set(search["inputSchema"]["required"]) == {"control_token", "manifest_id", "query"}
        assert "operation_id" not in search["inputSchema"]["properties"]
        assert "next_offset" in search["description"]
        call = client.post("/mcp", json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
            "name": "mcp_status", "arguments": {}}}, headers=headers)
        assert call.status_code == 200 and not call.json()["result"]["isError"]
        remote.allow()
        control_token = acquired(remote)
        call = client.post("/mcp", json={"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {
            "name": "search_manifest_source", "arguments": {
                "control_token": control_token, "manifest_id": remote.check()["source_manifest_id"],
                "query": "IF VALUE > 0",
            }}}, headers=headers)
        assert call.status_code == 200
        result = call.json()["result"]
        assert not result["isError"]
        hits = result["structuredContent"]
        assert hits["total"] == 1 and hits["items"][0]["logical_name"] == "steps.total"


def test_real_http_server_development_loop_and_shutdown(remote):
    pytest.importorskip("mcp")
    import socket
    from urllib.request import Request, build_opener, ProxyHandler
    local_http = build_opener(ProxyHandler({}))
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    remote.enabled = False
    remote.configure(port, "")
    bearer = remote.reset_token()
    remote.open()
    remote.allow()
    sequence = 0
    def rpc(method, params=None):
        nonlocal sequence
        sequence += 1
        body = {"jsonrpc": "2.0", "id": sequence, "method": method}
        if params is not None:
            body["params"] = params
        request = Request(f"http://127.0.0.1:{port}/mcp", json.dumps(body).encode(), headers={
            "Authorization": "Bearer " + bearer, "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"})
        with local_http.open(request, timeout=8) as response:
            return json.load(response)["result"]
    def call(name, arguments):
        value = rpc("tools/call", {"name": name, "arguments": arguments})
        assert not value.get("isError"), value
        return value["structuredContent"]
    def complete(identity, token):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            value = call("mcp_query", {"control_token": token, "operation_id": identity})
            if value["status"] not in {"running", "waiting_local"}:
                assert value["status"] == "finished", value
                return value["result"]["details"]
            time.sleep(.01)
        pytest.fail("HTTP operation did not finish")
    rpc("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                       "clientInfo": {"name": "local-protocol-test", "version": "1"}})
    assert rpc("tools/list")["tools"]
    control = call("mcp_acquire", {})["control_token"]
    listing = call("list_manifests", {"control_token": control})
    assert listing["total"] >= 1 and isinstance(listing["items"], list)
    manifest = call("read_manifest", {"control_token": control,
                                      "manifest_id": remote.check()["source_manifest_id"]})
    assert manifest["manifest_id"] == remote.check()["source_manifest_id"]
    assert any(item["logical_name"] == "steps.total" for item in manifest["items"])
    source = call("read", {"control_token": control, "path": "steps.total.py"})
    assert "if value > 0" in source["text"]
    for name, args in (("edit", {"path": "steps.total.py", "old_text": " if value > 0", "new_text": ""}),
                       ("validate_and_publish", {})):
        identity = str(uuid.uuid4())
        call(name, {"control_token": control, "operation_id": identity, **args})
        result = complete(identity, control)
    identity = str(uuid.uuid4())
    call("trial_run", {"control_token": control, "operation_id": identity, "manifest_id": result["manifest_id"],
                       "logical_name": "steps.total", "inputs": {"values": [1, -2]}})
    run_id = complete(identity, control)["run_id"]
    remote.service.wait_for(lambda state: state["phase"] == "finished")
    assert call("mcp_query", {"control_token": control, "run_id": run_id})["result"]["output"] == -1
    call("mcp_release", {"control_token": control})
    remote.close()
    assert not remote.enabled and remote._server_thread is None


def test_revoke_or_stop_before_trial_start_never_creates_a_run(remote, monkeypatch):
    token = acquired(remote)
    entered, proceed = threading.Event(), threading.Event()
    original = remote._execute
    def delayed(name, arguments, tools, op):
        entered.set()
        assert proceed.wait(3)
        return original(name, arguments, tools, op)
    monkeypatch.setattr(remote, "_execute", delayed)
    identity = str(uuid.uuid4())
    remote.invoke("trial_run", {"manifest_id": remote.check()["source_manifest_id"]}, token, identity)
    assert entered.wait(3)
    remote.revoke()
    proceed.set()
    op = wait_operation(remote, identity)
    assert op["status"] == "failed" and remote.service.status["run_id"] is None
    assert remote.owner is None


def test_existing_privacy_switches_are_enforced_at_acquisition(remote, monkeypatch):
    from lalc import agent_settings
    original = agent_settings.settings_document
    monkeypatch.setattr(agent_settings, "settings_document", lambda root: {
        **original(root), "history_enabled": False, "knowledge_enabled": False, "manifest_reference_enabled": False})
    token = acquired(remote)
    for name in ("list_game_versions", "knowledge_list", "list_manifests", "search_manifest_source"):
        with pytest.raises(ValueError, match="关闭"):
            remote.invoke(name, {}, token)
    assert remote.invoke("read", {"path": "manifest.json"}, token)


def test_audit_and_unknown_operation_survive_restart_without_replay(remote):
    token = acquired(remote)
    remote.release(token)
    identity = str(uuid.uuid4())
    remote._save_operation({"operation_id": identity, "name": "edit", "request": {}, "status": "running"})
    restored = RemoteWorkbench(remote.service)
    assert restored.operation(identity)["status"] == "unknown"
    assert any(row["event"] == "released" for row in restored.snapshot()["recent"])
