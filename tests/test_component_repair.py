"""覆盖修复前置检查、候选替换、最终 JSON 和独立日志，不启动 Agent。

在项目根目录运行：
UV_CACHE_DIR=.generated/uv-cache uv run --frozen pytest -q tests/test_component_repair.py
"""

import json
from pathlib import Path
import shutil

import pytest

import lalc.__main__ as cli
import lalc.component_repair as repair
from lalc.component_repair import RepairLog, final_answer, prepare_candidate, repair_baseline
from lalc.manifest import ManifestManager


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


@pytest.mark.parametrize("problem", ["missing_default", "broken_default", "missing_target", "recovery_rule"])
def test_preflight_preserves_existing_draft(tmp_path, problem):
    manager, loaded = baseline(tmp_path)
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    draft = candidate / "unpublished.py"
    draft.write_bytes(b"must survive")
    default = manager.manifests_dir / "default.json"
    if problem == "missing_default":
        default.unlink()
    elif problem == "broken_default":
        default.write_text('{"manifest_id":"missing"}')
    elif problem == "recovery_rule":
        # 目标即使存在于 Recovery Rules 中也不属于可修复 Component。
        loaded.recovery_rules["rules.only"] = loaded.components["steps.total"]
        manager.load_default = lambda: type("Result", (), {"ok": True, "loaded": loaded})()
    with pytest.raises(ValueError):
        repair_baseline(manager, candidate, "rules.only" if problem == "recovery_rule" else "missing.target")
    assert draft.read_bytes() == b"must survive"


def test_materialization_uses_pinned_default_and_logs_survive_next_rebuild(tmp_path):
    manager, loaded = baseline(tmp_path)
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "old.py").write_text("unpublished")
    retained = {p: p.read_bytes() for p in manager.data_root.rglob("*") if p.is_file()}
    selected = repair_baseline(manager, candidate, "steps.total")
    manifest_id, source, original = prepare_candidate(manager, candidate, "steps.total", selected)
    assert manifest_id == loaded.manifest_id
    assert not (candidate / "old.py").exists()
    assert source.read_bytes() == (FIXTURE / "steps.total.py").read_bytes()
    assert set(p.name for p in candidate.iterdir()) == {"manifest.json", "steps.total.py", "steps.unchanged.py"}
    log = RepairLog(manager.data_root, "test-secret")
    log.record({"message": "test-secret", "nested": [{"key": "test-secret"}]})
    log.snapshot("final", source, original)
    prepare_candidate(manager, candidate, "steps.total", selected)
    assert (log.path / "final.py").read_bytes() == original
    assert "test-secret" not in (log.path / "events.jsonl").read_text()
    assert all(path.read_bytes() == content for path, content in retained.items())


def test_materialization_failure_keeps_draft(tmp_path):
    manager, _ = baseline(tmp_path)
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    draft = candidate / "old.py"
    draft.write_text("unpublished")
    selected = repair_baseline(manager, candidate, "steps.total")
    for path in manager.components_dir.iterdir():
        path.unlink()
    with pytest.raises(ValueError):
        prepare_candidate(manager, candidate, "steps.total", selected)
    assert draft.read_text() == "unpublished"


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


@pytest.mark.parametrize("missing_default", [True, False])
def test_cli_rejects_invalid_start_before_model_setup(tmp_path, monkeypatch, capsys, missing_default):
    manager, _ = baseline(tmp_path)
    if missing_default:
        (manager.manifests_dir / "default.json").unlink()
    project = tmp_path / "project"
    candidate = project / "candidate"
    candidate.mkdir(parents=True)
    draft = candidate / "old.py"
    draft.write_bytes(b"unpublished draft")
    monkeypatch.chdir(project)
    monkeypatch.setattr(cli, "default_data_root", lambda: manager.data_root)
    monkeypatch.setattr(repair, "configured_pi", lambda *args: pytest.fail("Invalid start reached model setup"))
    assert cli.main(["repair", "missing.target", "--problem", "repair", "--image", "missing.png"]) == 1
    assert draft.read_bytes() == b"unpublished draft"
    assert not (candidate / "manifest.json").exists()
    assert "missing.png" not in capsys.readouterr().out
