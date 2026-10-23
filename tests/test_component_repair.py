"""覆盖显式 Candidate、多文件授权、固定基线和修复回答；不启动 Agent。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_component_repair.py
"""

import json
from pathlib import Path
import shutil

import pytest

from lalc.component_repair import final_answer
from lalc.manifest import ManifestManager
from lalc.application import ApplicationService
from lalc.developer import DeveloperHost, candidate_files, selected_files

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


def test_draft_selection_and_validation_failure_are_independent(tmp_path):
    host, _ = host_for(tmp_path)
    (host.candidate / "manifest.json").write_text("broken json")
    (host.candidate / "plan.json").write_text("{}")
    assert selected_files(host.candidate, ["manifest.json", "steps.total.py"]) == ("manifest.json", "steps.total.py")
    assert selected_files(host.candidate, []) == ()
    assert not host.validate()["ok"]
    assert selected_files(host.candidate, ["manifest.json"]) == ("manifest.json",)
    with pytest.raises(ValueError):
        selected_files(host.candidate, ["plan.json"])
    with pytest.raises(ValueError):
        selected_files(host.candidate, ["../candidate/steps.total.py"])
    (host.candidate / "linked.py").symlink_to(tmp_path / "outside.py")
    with pytest.raises(ValueError):
        candidate_files(host.candidate)


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
