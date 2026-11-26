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
        source.write_text(source.read_text(encoding="utf-8").replace(" if value > 0", ""), encoding="utf-8")
        with monkeypatch.context() as patch:
            patch.setattr(type(host.service), "state", property(lambda _: pytest.fail("Trial copied full Trace")))
            first = tools.trial_run(saved, logical_name="steps.total", inputs={"values": [1, -2]})["details"]
        assert first["result"]["output"] == 1
        assert first["log"]["last_sequence"] == len(host.service.state["trace"])
        updated = tools.publish()["details"]["manifest_id"]
        second = tools.trial_run(updated, logical_name="steps.total", inputs={"values": [1, -2]})["details"]
        assert second["result"]["output"] == -1
        assert second["run_id"] != first["run_id"]
        listing = tools.list_runs(limit=1)["details"]
        assert listing['run_ids'] == [second['run_id']] and listing['next_offset'] == 1
        assert listing['runs'][0]['source'] == 'agent_trial'
        assert listing['runs'][0]['logical_name'] == 'steps.total'
        page = tools.read_run_log(first["run_id"], limit=1)["details"]
        assert page["events"][0]["event"] == "run_started" and page["next_sequence"] == 2
        assert page["events"][0]["trial_session_id"] == tools.log.identity
        with pytest.raises(StartError):
            host.service.start("steps.total", {"values": []})
    assert host.manager.default_manifest_id() == original.manifest_id


def test_run_visibility_filters_before_paging_and_blocks_direct_reads(tmp_path):
    """会话可见集合同时约束试运行、父 Run、搜索与各类证据读取。"""
    from lalc.agent_settings import save_options
    from lalc.developer_session import DeveloperSession

    host, saved = host_for(tmp_path)
    session = DeveloperSession.create(host.service, saved.manifest_id, entry="runtime", parent_run_id=2)
    other = DeveloperSession.create(host.service, saved.manifest_id, entry="gui")
    traces = host.service.data_root / "traces"
    traces.mkdir()
    for run_id in range(1, 8):
        record = {"event": "run_started", "run_id": run_id, "sequence": 1, "developer_trial": run_id in {4, 5, 6, 7}}
        if run_id in {5, 7}:
            record["trial_session_id"] = other.identity
        if run_id == 4:
            record["trial_session_id"] = session.identity
        (traces / f"{run_id}.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")
    session.conversation().log.record({"type": "trial_started", "run_id": 6})
    all_ids = list(range(7, 0, -1))
    assert session.host.conversation.tools.list_runs()["details"]["run_ids"] == all_ids
    assert other.conversation().tools.list_runs()["details"]["run_ids"] == all_ids
    assert DeveloperSession(host.service, session.identity).conversation().tools.list_runs()["details"]["run_ids"] == [6, 4, 2]

    save_options(host.service.data_root, other_run_logs_enabled=False)
    for entry in ("runtime", "gui", "cli"):
        tools = DeveloperSession(host.service, session.identity, entry=entry).conversation().tools
        first = tools.list_runs(limit=2)["details"]
        assert first["run_ids"] == [6, 4] and first["next_offset"] == 2
        assert tools.list_runs(offset=2)["details"]["run_ids"] == [2]
        page = tools.search_run_logs("run_started", run_id=6)["details"]
        assert [item["run_id"] for item in page["matches"]] == [6]
        assert page["next"] is None
        assert tools.read_run_log(2)["details"]["events"][0]["run_id"] == 2
        for arguments in ({}, {"evidence_id": "7/1"}, {"render_sequence": 1}):
            with pytest.raises(ValueError, match="没有访问权限"):
                tools.read_run_log(7, **arguments)
        with pytest.raises(ValueError, match="没有访问权限"):
            tools.search_run_logs("run_started", run_id=7)
    assert other.conversation().tools.list_runs()["details"]["run_ids"] == [7, 5]


def test_legacy_runtime_parent_uses_host_trace(tmp_path):
    """旧 Runtime Session 通过宿主介入事件恢复父 Run 归属。"""
    from lalc.agent_settings import save_options
    from lalc.developer_session import DeveloperSession

    host, saved = host_for(tmp_path)
    session = DeveloperSession.create(host.service, saved.manifest_id, entry="runtime")
    session.conversation().log.record({"type": "game_version_observed", "source": "runtime:Repair"})
    traces = host.service.data_root / "traces"
    traces.mkdir()
    for run_id in (1, 2):
        records = [{"event": "run_started", "run_id": run_id, "sequence": 1, "developer_trial": False}]
        if run_id == 1:
            records.append({"event": "agent_invoked", "session_id": session.identity, "sequence": 2})
        (traces / f"{run_id}.jsonl").write_text("".join(json.dumps(row) + "\n" for row in records), encoding="utf-8")
    save_options(host.service.data_root, other_run_logs_enabled=False)
    tools = DeveloperSession(host.service, session.identity, entry="gui").conversation().tools
    assert tools.list_runs()["details"]["run_ids"] == [1]


def test_rejected_start_has_no_run_and_failure_keeps_trace(tmp_path, monkeypatch):
    host, saved = host_for(tmp_path)
    monkeypatch.setattr(host.service, "_start_session", lambda: None)
    tools = host.conversation.tools
    with host.service.activity("Agent"):
        result = tools.trial_run(saved.manifest_id, logical_name="missing", inputs={})["details"]
        assert result["status"] == "rejected" and result["run_id"] is None
        assert host.service.state["run_id"] is None
        assert "再次调用" in result["feedback"]
        (host.candidate / "plans.default.py").write_text("broken", encoding="utf-8")
        result = tools.trial_run(saved.manifest_id)["details"]
        assert result["result"]["status"] == "completed"
        assert tools.read_run_log(result["run_id"])["details"]["events"]
        with pytest.raises(TypeError):
            tools.trial_run(saved.manifest_id, plan_path="../outside.py")



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
    if role == "plan":
        source = host.candidate / "plans.default.py"
        source.write_text(source.read_text(encoding="utf-8").replace("    return None", '    ctx.call("entry.compute", n=2)'), encoding="utf-8")
    with host.service.activity("Agent"):
        identity = tools.publish()["details"]["manifest_id"]
        if role == "plan":
            result = tools.trial_run(identity)["details"]
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
    def run(_manifest, _name, _component, _inputs, gate, _run_state, _options):
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
    trace.write_text(json.dumps({"sequence": 1, "event": "run_started", "run_id": 1,
                                "developer_trial": True, "trial_session_id": tools.log.identity,
                                "evidence_id": "1/2"}) + "\n", encoding="utf-8")
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
    def run(_manifest, _name, _component, _inputs, gate, _run_state, _options):
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


def test_validate_and_publish_replaces_old_agent_tools(tmp_path):
    """所有 Agent 入口合并校验与发布，失败不保存版本，成功返回可用 ID。"""
    from lalc.agent_policy import allowed_tools
    from lalc.agent_log import read_json

    for mode, entry in [("Construct", "gui"), ("Repair", "gui"), ("Repair", "cli"), ("Repair", "runtime")]:
        names = allowed_tools(mode, entry)
        assert "validate_and_publish" in names
        assert not {"validate", "publish"} & set(names)
    host, original = host_for(tmp_path)
    tools = host.conversation.tools
    before = host.manager.list_manifests()
    for name in ("validate", "publish"):
        assert read_json(tools.call(name, {}))["isError"]
    source = host.candidate / "steps.total.py"
    valid = source.read_text(encoding="utf-8")
    source.write_text("def broken(:", encoding="utf-8")
    failed = read_json(tools.call("validate_and_publish", {}))
    assert failed["isError"] and failed["details"]["errors"]
    assert host.manager.list_manifests() == before
    source.write_text(valid, encoding="utf-8")
    published = read_json(tools.call("validate_and_publish", {}))
    assert published["details"]["ok"]
    identity = published["details"]["manifest_id"]
    assert identity != original.manifest_id
    assert identity in {item["manifest_id"] for item in host.manager.list_manifests()}
    assert host.manager.default_manifest_id() == original.manifest_id


@pytest.mark.parametrize("mode,summary", [("Construct", "本次改动"), ("Repair", "None")])
def test_gui_agent_publish_requires_and_replaces_summary(tmp_path, mode, summary):
    """GUI Agent 发布漏填说明时拒绝，成功后只保存本次说明。"""
    from lalc.agent_log import read_json
    from lalc.developer_session import DeveloperSession

    host, original = host_for(tmp_path)
    chat = DeveloperSession.create(host.service, original.manifest_id, mode=mode, entry="gui").conversation()
    path = chat.host.candidate / "manifest.json"
    candidate = json.loads(path.read_text(encoding="utf-8"))
    candidate["AdditionalMessage"] = "旧版本说明"
    path.write_text(json.dumps(candidate, ensure_ascii=False), encoding="utf-8")
    before = host.manager.list_manifests()
    for arguments in ({}, {"summary": "   "}):
        failed = read_json(chat.tools.call("validate_and_publish", arguments))
        assert failed["isError"] and "summary" in failed["details"]["message"]
    assert host.manager.list_manifests() == before
    assert json.loads(path.read_text(encoding="utf-8")) == candidate

    published = read_json(chat.tools.call("validate_and_publish", {"summary": f" {summary} "}))
    assert published["details"]["ok"]
    identity = published["details"]["manifest_id"]
    assert host.manager.load(identity).loaded.manifest["AdditionalMessage"] == summary
    assert json.loads(path.read_text(encoding="utf-8"))["AdditionalMessage"] == summary
