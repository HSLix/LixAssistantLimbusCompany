"""覆盖 Developer 发布、不可变试运行、启动拒绝、取消清理和日志证据；不调用模型。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_developer_policy.py
"""

import json
import threading

import pytest

from lalc.application import StartError
from lalc.runtime import UserInterruption
from test_agent_repair import host_for


def test_publish_trial_uses_saved_version_and_retained_logs(tmp_path, monkeypatch):
    host, original = host_for(tmp_path)
    monkeypatch.setattr(host.service, "_start_session", lambda: None)
    tools = host.conversation.tools
    source = host.candidate / "steps.total.py"
    with host.service.activity("Agent"):
        saved = tools.publish()["details"]["manifest_id"]
        source.write_text(source.read_text().replace(" if value > 0", ""))
        first = tools.trial_run(saved, logical_name="steps.total", inputs={"values": [1, -2]})["details"]
        assert first["result"]["output"] == 1
        updated = tools.publish()["details"]["manifest_id"]
        second = tools.trial_run(updated, logical_name="steps.total", inputs={"values": [1, -2]})["details"]
        assert second["result"]["output"] == -1
        assert second["run_id"] != first["run_id"]
        assert tools.list_runs(limit=1)["details"] == {"run_ids": [second["run_id"]], "next_offset": 1}
        page = tools.read_run_log(first["run_id"], limit=1)["details"]
        assert page["events"][0]["event"] == "run_started" and page["next_sequence"] == 2
        with pytest.raises(StartError):
            host.service.start("steps.total", {"values": []})
    assert host.manager.default_manifest_id() == original.manifest_id


def test_rejected_start_has_no_run_and_failure_keeps_trace(tmp_path, monkeypatch):
    host, saved = host_for(tmp_path)
    monkeypatch.setattr(host.service, "_start_session", lambda: None)
    tools = host.conversation.tools
    with host.service.activity("Agent"):
        result = tools.trial_run(saved.manifest_id, logical_name="missing", inputs={})["details"]
        assert result["status"] == "rejected" and result["run_id"] is None
        assert host.service.state["run_id"] is None
        assert "再次调用" in result["feedback"]
        (host.candidate / "plan.json").write_text("broken")
        result = tools.trial_run(saved.manifest_id, plan_path="plan.json")["details"]
        assert result["run_id"] and result["result"]["status"] == "interrupted"
        assert tools.read_run_log(result["run_id"])["details"]["events"]
        with pytest.raises(ValueError):
            tools.trial_run(saved.manifest_id, plan_path="../outside.json")


@pytest.mark.parametrize("role", ["task_workflow", "sub_workflow", "step", "plan"])
def test_all_trial_entry_types_use_explicit_saved_manifest(tmp_path, monkeypatch, role):
    host, _ = host_for(tmp_path)
    monkeypatch.setattr(host.service, "_start_session", lambda: None)
    component_role = "task_workflow" if role == "plan" else role
    name = "entry.compute"
    tools = host.conversation.tools
    source = f'''"""仅用于验证入口类型的计算组件。"""
from lalc import {component_role}
@{component_role}
def execute(ctx, *, n: int) -> int:
    """返回显式输入。"""
    return n
'''
    tools.add_component("entry.py", name, source)
    with host.service.activity("Agent"):
        identity = tools.publish()["details"]["manifest_id"]
        if role == "plan":
            (host.candidate / "plan.json").write_text(json.dumps({"items": [{"task": name, "inputs": {"n": 2}}]}))
            result = tools.trial_run(identity, plan_path="plan.json")["details"]
            assert result["result"]["status"] == "completed"
            assert result["result"]["items"][0]["result"] == "success"
        else:
            result = tools.trial_run(identity, logical_name=name, inputs={"n": 2})["details"]
            assert result["result"]["output"] == 2
        assert result["manifest_id"] == identity and result["run_id"]


@pytest.mark.parametrize("cancel_round", [False, True])
def test_stop_and_round_cancel_wait_for_trial_completion(tmp_path, monkeypatch, cancel_round):
    host, saved = host_for(tmp_path)
    entered = threading.Event()
    cleaned = threading.Event()
    tools = host.conversation.tools
    def run(_manifest, _name, _component, _inputs, gate):
        gate.pause()
        entered.set()
        try:
            gate.checkpoint()
        except UserInterruption:
            return {"status": "failure", "failure_code": "user_cancelled"}
        finally:
            cleaned.set()
    monkeypatch.setattr(host.service, "_run", run)
    def stop():
        assert entered.wait(5)
        if cancel_round:
            tools.cancelled.set()
        else:
            host.service.stop()
    worker = threading.Thread(target=stop)
    worker.start()
    with host.service.activity("Agent"):
        if cancel_round:
            with pytest.raises(RuntimeError, match="cancelled"):
                tools.trial_run(saved.manifest_id, logical_name="steps.total", inputs={"values": []})
        else:
            result = tools.trial_run(saved.manifest_id, logical_name="steps.total", inputs={"values": []})
            assert "用户主动停止" in result["details"]["feedback"]
            assert not tools.cancelled.is_set()
        assert host.service.state["phase"] == "finished" and cleaned.is_set()
    worker.join(5)


def test_log_evidence_is_bound_to_run_and_missing_is_explicit(tmp_path):
    from PIL import Image
    host, _ = host_for(tmp_path)
    tools = host.conversation.tools
    root = host.service.data_root
    trace = root / "traces" / "1.jsonl"
    trace.parent.mkdir(exist_ok=True)
    trace.write_text(json.dumps({"sequence": 1, "evidence_id": "1/2"}) + "\n")
    image = root / "evidence" / "1" / "2.png"
    image.parent.mkdir(parents=True)
    Image.new("RGB", (4, 4)).save(image)
    result = tools.read_run_log(1, evidence_id="1/2")
    assert result["content"][-1]["type"] == "image"
    for evidence in ("2/2", "1/../2", "1/3"):
        with pytest.raises(ValueError):
            tools.read_run_log(1, evidence_id=evidence)
    with pytest.raises(ValueError, match="不可用"):
        tools.read_run_log(2)
    with pytest.raises(ValueError):
        tools.read_run_log(True)


def test_trial_log_failure_does_not_leave_game_running(tmp_path, monkeypatch):
    host, saved = host_for(tmp_path)
    tools = host.conversation.tools
    def run(_manifest, _name, _component, _inputs, gate):
        gate.pause()
        try:
            gate.checkpoint()
        except UserInterruption:
            return {"status": "failure", "failure_code": "user_cancelled"}
    def fail(_event):
        raise OSError("interaction log unavailable")
    monkeypatch.setattr(host.service, "_run", run)
    monkeypatch.setattr(tools.log, "record", fail)
    with host.service.activity("Agent"):
        with pytest.raises(OSError, match="interaction log"):
            tools.trial_run(saved.manifest_id, logical_name="steps.total", inputs={"values": []})
        assert host.service.state["phase"] == "finished"
