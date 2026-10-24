"""覆盖显式 Candidate、多文件授权、固定基线和修复回答；不启动 Agent。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_agent_repair.py
"""

import json
from pathlib import Path
import shutil

import pytest

from lalc.agent_repair import final_answer
from lalc.manifest import ManifestManager
from lalc.application import ApplicationService
from lalc.developer import DeveloperHost, candidate_files, editable_files

FIXTURE = Path(__file__).parent / "fixtures" / "component-repair"


def baseline(tmp_path):
    """从仓库中的不变缺陷种子发布到测试自有数据目录。"""
    manager = ManifestManager(tmp_path / "data")
    seed = tmp_path / "seed"
    shutil.copytree(FIXTURE, seed)
    saved = manager.publish(seed / "manifest.json")
    assert saved.ok, saved.errors
    assert manager.set_default(saved.loaded.manifest_id).ok
    return manager, saved.loaded


def host_for(tmp_path):
    manager, loaded = baseline(tmp_path)
    host = DeveloperHost(ApplicationService(manager.data_root, manifest_manager=manager), tmp_path / "candidate")
    host.initialize(loaded.manifest_id)
    return host, loaded


def test_existing_files_editable_despite_validation_failure_and_missing_reference(tmp_path):
    host, _ = host_for(tmp_path)
    (host.candidate / "manifest.json").write_text("broken json")
    (host.candidate / "plan.json").write_text("{}")
    (host.candidate / "temporary.py").write_text("# 临时测试文件")
    expected = tuple(name for name in candidate_files(host.candidate) if name != "plan.json")
    assert editable_files(host.candidate) == expected
    assert not host.validate()["ok"]
    assert editable_files(host.candidate) == expected
    (host.candidate / "linked.py").symlink_to(tmp_path / "outside.py")
    with pytest.raises(ValueError):
        editable_files(host.candidate)


@pytest.mark.parametrize("valid", [True, False])
def test_manual_validation_immediately_persists_in_current_conversation(tmp_path, valid):
    host, _ = host_for(tmp_path)
    if not valid:
        (host.candidate / "manifest.json").write_text("broken json")
    for chat in (host.conversation, host.new_conversation()):
        host.conversation = chat
        result = host.validate()
        assert result["ok"] is valid
        assert json.loads((chat.log.path / "context.json").read_text()) == chat.history
        assert json.dumps(result, ensure_ascii=False) in chat.history[-1]["content"][0]["text"]
        event = json.loads((chat.log.path / "events.jsonl").read_text().splitlines()[-1])["event"]
        assert event == {"type": "validation", "source": "manual", **result}


def test_explicit_rebuild_preserves_draft_until_success_and_resets_conversation(tmp_path, monkeypatch):
    host, loaded = host_for(tmp_path)
    draft = host.candidate / "steps.total.py"
    draft.write_text("unpublished")
    conversation = host.new_conversation()
    metadata = host.metadata.read_bytes()
    with pytest.raises(ValueError):
        host.initialize(loaded.manifest_id)
    assert draft.read_text() == "unpublished"
    with pytest.raises(ValueError):
        host.initialize("missing", replace=True)
    assert draft.read_text() == "unpublished"
    assert host.conversation is conversation
    assert host.metadata.read_bytes() == metadata
    host.initialize(loaded.manifest_id, replace=True)
    assert draft.read_bytes() == (FIXTURE / "steps.total.py").read_bytes()
    assert host.conversation is not conversation
    assert conversation.log.path.exists()


def test_metadata_failure_restores_previous_candidate(tmp_path, monkeypatch):
    host, loaded = host_for(tmp_path)
    draft = host.candidate / "steps.total.py"
    draft.write_text("must survive")
    metadata = host.metadata.read_bytes()
    def fail(*_):
        raise OSError("disk unavailable")
    monkeypatch.setattr("lalc.developer.atomic_write_json", fail)
    with pytest.raises(OSError):
        host.initialize(loaded.manifest_id, replace=True)
    assert draft.read_text() == "must survive"
    assert host.metadata.read_bytes() == metadata


def test_cumulative_diff_and_new_conversation_keep_baseline(tmp_path):
    host, loaded = host_for(tmp_path)
    assert host.diff() == ""
    source = host.candidate / "steps.total.py"
    source.write_text(source.read_text().replace("if value > 0", "if value >= 0"))
    first = host.new_conversation()
    first.add_validation({"ok": False, "errors": [{"code": "test"}]})
    diff = host.diff()
    second = host.new_conversation()
    assert second.history == [] and first.history
    assert host.diff() == diff and "if value >= 0" in diff
    host.select_runner(None)
    assert host.diff() == diff
    assert host.manager.default_manifest_id() == loaded.manifest_id


@pytest.mark.parametrize("value", ['plain text', '{"revise_success": "true", "message": "x"}',
                                   '{"message":"x"}', '[]', '{"revise_success":1,"message":"x"}',
                                   '{"revise_success":false,"message":""}'])
def test_invalid_final_is_not_guessed(value):
    with pytest.raises(ValueError):
        final_answer({"content": [{"type": "text", "text": value}]})


def test_final_boolean_is_model_report():
    for success in (True, False):
        answer = {"revise_success": success, "message": "说明"}
        assert final_answer({"content": [{"type": "text", "text": json.dumps(answer)}]}) == answer


@pytest.mark.parametrize("language", ["json", "", "JSON"])
def test_final_rejects_fenced_json_even_when_object_is_valid(language):
    answer = {"revise_success": False, "message": "本轮仅分析。"}
    text = "您好，已联通。\n\n```" + language + "\n" + json.dumps(answer) + "\n```\n说明结束。"
    with pytest.raises(ValueError):
        final_answer({"content": [{"type": "thinking", "thinking": "not parsed"},
                                  {"type": "text", "text": text}]})


@pytest.mark.parametrize("text", ["", "plain text", '```json\n{"revise_success": false,}\n```',
                                 '```json\n{}\n```\n```json\n{}\n```'])
def test_final_parse_errors_include_actual_text_and_position(text):
    from lalc.agent_diagnostics import AgentDiagnosticError, error_details, details_text
    with pytest.raises(AgentDiagnosticError) as caught:
        final_answer({"content": [{"type": "text", "text": text}]})
    details = error_details(caught.value, "agent")
    assert details["stage"] == "final_answer" and details["raw_text"] == text
    assert details["parse_line"] >= 1 and details["parse_column"] >= 1
    assert "JSONDecodeError" in details["traceback"]
    assert text in details_text(details)


def test_final_schema_error_retains_parsed_value():
    from lalc.agent_diagnostics import AgentDiagnosticError
    with pytest.raises(AgentDiagnosticError) as caught:
        final_answer({"content": [{"type": "text", "text": '{"revise_success":"false","message":"x"}'}]})
    assert caught.value.evidence["parsed_value"]["revise_success"] == "false"
    assert caught.value.stage == "final_answer"


def test_output_length_is_not_request_budget_or_generic_provider_error():
    from lalc.agent_repair import model_error
    from lalc.agent_diagnostics import error_details
    message = {"stopReason": "length", "usage": {"input": 1724, "output": 4096},
               "content": [{"type": "thinking", "thinking": "unfinished"}]}
    details = error_details(model_error(message, "provider_request", 2, 20), "agent")
    assert details["failure_code"] == "output_limit"
    assert details["stop_reason"] == "length" and details["usage"]["output"] == 4096
    assert details["requests_used"] == 2 and details["request_limit"] == 20
    assert details["text_chars"] == 0 and details["thinking_chars"] == len("unfinished")
    assert "4096" in details["message"] and "不是本轮请求次数超限" in details["message"]


def test_unknown_provider_stop_keeps_stop_reason_instead_of_empty_message():
    from lalc.agent_repair import model_error
    error = model_error({"stopReason": "error"}, "provider_request", 2, 20)
    assert "stopReason=error" in str(error) and error.evidence["failure_code"] == "provider_error"


@pytest.mark.parametrize("stage", ["就绪事件 lalc_ready", "配置响应 set_auto_retry"])
def test_rpc_wait_timeout_identifies_stage_and_preserves_cause(stage):
    import asyncio
    from lalc.pi_probe import rpc_event
    original = TimeoutError()
    async def event():
        raise original
    with pytest.raises(TimeoutError, match=stage) as caught:
        asyncio.run(rpc_event(event, stage))
    assert caught.value.__cause__ is original
    assert "30 秒" in str(caught.value) and "stderr" in str(caught.value)
