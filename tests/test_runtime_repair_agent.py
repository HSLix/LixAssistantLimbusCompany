"""真实 pi 与本机模型替身验证 Runtime 工具交接及父 Run 续接。

从项目根目录运行：.venv/bin/python -m pytest --run-agent-tests tests/test_runtime_repair_agent.py -q
默认跳过；本机 HTTP 替身不代表真实模型、Windows 或游戏验收。
"""

import json

import pytest

from agent_test_server import agent_server
from test_agent_repair_agent import tool, answer
from test_recovery import _publish, NEW_STEP
from lalc.application import ApplicationService
from lalc.manifest import ManifestManager
from lalc.agent_settings import save_settings, save_selection
from lalc.agent_log import read_events

pytestmark = pytest.mark.agent


def test_real_pi_recheck_ends_round_without_another_request_and_resumes_parent(tmp_path, agent_server):
    address, server, _ = agent_server
    manager = ManifestManager(tmp_path)
    broken = NEW_STEP.replace('return f"step-new:{value}"', 'raise ExecutionFailure("runtime broken")').replace(
        "from lalc import step", "from lalc import step, ExecutionFailure")
    base = _publish(tmp_path, manager, step_source=broken)
    manager.set_default(base)
    save_settings(tmp_path, {"provider": "llama.cpp", "base_url": address, "model": "gemma4-test", "max_requests": 5})
    save_selection(tmp_path, "user", "llama.cpp", enabled=True)

    def respond(body):
        number = len(server["calls"])
        if number == 1:
            return tool("read_run_state", {})
        if number == 2:
            return tool("edit", {"path": "steps.break.py", 'oldText': 'raise ExecutionFailure("runtime broken")',
                                 'newText': 'return f"step-new:{value}"'})
        if number == 3:
            return tool("publish", {"summary": "修复运行时失败，保留调用约定"})
        if number == 4:
            return tool("recheck", {"manifest_id": manager.list_manifests()[0]["manifest_id"]})
        return answer("unexpected extra request")

    server["respond"] = respond
    service = ApplicationService(tmp_path, manifest_manager=manager)
    try:
        service.start("tasks.run", {"value": 5}, manifest_id=base)
        state = service.wait_for(lambda value: value["phase"] == "finished")
        assert state["result"]["status"] == "success", state["result"].get("traceback", state["result"])
        assert state["result"]["output"] == ["task-old", "step-new:5", "sub-old"]
        assert len(server["calls"]) == 4
        chat = service._runtime_chat
        assert chat is not None
        rows = list(read_events(chat.log.root / "events.jsonl"))
        assert any(row["event"].get("status") == "recheck" for row in rows)
        assert manager.load(state["working_manifest_id"]).loaded.manifest["AdditionalMessage"] == "修复运行时失败，保留调用约定"
        assert manager.default_manifest_id() == state["working_manifest_id"]
        tools = {item["function"]["name"] for item in server["calls"][0]["tools"]}
        assert {"read_run_state", "recheck"} <= tools
        assert not {"trial_run", "remove_asset", "knowledge_git", "request_feedback"} & tools
    finally:
        service.shutdown()


def test_stop_during_runtime_agent_finishes_run_and_releases_activity(tmp_path, agent_server):
    address, server, _ = agent_server
    manager = ManifestManager(tmp_path)
    broken = NEW_STEP.replace('return f"step-new:{value}"', 'raise ExecutionFailure("broken")').replace(
        "from lalc import step", "from lalc import step, ExecutionFailure")
    base = _publish(tmp_path, manager, step_source=broken)
    manager.set_default(base)
    save_settings(tmp_path, {"provider": "llama.cpp", "base_url": address, "model": "gemma4-test", "max_requests": 5})
    save_selection(tmp_path, "user", "llama.cpp", enabled=True)
    server["block"] = True
    service = ApplicationService(tmp_path, manifest_manager=manager)
    try:
        service.start("tasks.run", {"value": 5}, manifest_id=base)
        assert server["started"].wait(15)
        service.stop()
        state = service.wait_for(lambda value: value["phase"] == "finished")
        assert state["result"]["failure_code"] == "user_cancelled", state["result"]
        assert state["activity"] is None and service._gate is None
        assert service._runtime_chat.tools.run_state is None
        assert manager.default_manifest_id() == base and state["default_update"] is None
        assert (service._runtime_chat.log.path / "round-1" / "result.json").exists()
    finally:
        server["release"].set()
        service.shutdown()
