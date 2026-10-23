"""覆盖 schema 2、Manifest 与素材解耦，以及应用动作和会话边界。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen UV_CACHE_DIR=.generated/uv-cache uv run --frozen --all-extras pytest -q tests/test_manifest_transition.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import lalc.__main__ as cli
from lalc.actions import application_actions
from lalc.application import ApplicationService
from lalc.manifest import ManifestManager


def draft(root: Path, manager: ManifestManager) -> Path:
    folder = root / "candidate"
    assert not manager.initialize_candidate(folder)
    return folder


def test_manifest_lifecycle_is_independent_of_assets(tmp_path):
    manager = ManifestManager(tmp_path / "data")
    candidate = tmp_path / "candidate"
    assert not manager.initialize_candidate(candidate)
    assert {p.name for p in candidate.iterdir()} == {"manifest.json"}
    # 素材损坏不再阻止 Component 发布；使用时才报告其原始错误。
    (manager.data_root / "assets").mkdir(parents=True)
    (manager.data_root / "assets" / "broken.png").write_bytes(b"broken")
    assert not manager.validate(candidate / "manifest.json")
    result = manager.publish(candidate / "manifest.json")
    assert result.ok and not hasattr(result.loaded, "assets")
    assert manager.set_default(result.loaded.manifest_id).ok
    assert manager.load(result.loaded.manifest_id).ok
    assert not (manager.data_root / "asset-libraries").exists()
    other = tmp_path / "other"
    assert not manager.initialize_candidate(other)
    assert {p.name for p in other.iterdir()} == {"manifest.json"}


@pytest.mark.parametrize("version,extra", [(1, {}), (2, {"assets": {}}), (2, {"trusted_actions": {}})])
def test_legacy_format_is_rejected_without_writes(tmp_path, version, extra):
    manager = ManifestManager(tmp_path / "data")
    candidate = draft(tmp_path, manager)
    (candidate / "manifest.json").write_text(json.dumps({
        "schema_version": version, "components": {}, "recovery_rules": {}, **extra,
    }), encoding="utf-8")
    errors = manager.validate(candidate / "manifest.json")
    assert {error.code for error in errors} & {"schema_version_unsupported", "field_unknown"}
    assert not manager.publish(candidate / "manifest.json").ok
    assert not manager.manifests_dir.exists()
    assert not (manager.data_root / "asset-libraries").exists()


def test_production_action_registration_is_shared_and_not_manifest_owned(tmp_path):
    actions = application_actions()
    manager = ManifestManager(tmp_path, actions=actions)
    assert set(actions) == {"observe.capture_screen", "observe.match_asset", "observe.crop_asset",
                            "control.click", "control.key_press", "control.drag", "control.wait"}
    actions.clear()
    assert manager.actions["control.wait"].classification == "control"
    with pytest.raises(TypeError):
        manager.actions["new"] = manager.actions["control.wait"]


def test_run_and_plan_connect_and_monitor_before_calculation_only_components(tmp_path):
    from test_input_control import FakeWindow
    manager = ManifestManager(tmp_path / "data")
    candidate = draft(tmp_path, manager)
    (candidate / "task.py").write_text('''"""只计算的任务仍在完整窗口会话中执行。"""
from lalc import task_workflow
@task_workflow
def execute(ctx) -> int:
    return 7
''', encoding="utf-8")
    (candidate / "manifest.json").write_text(json.dumps({"schema_version": 2,
        "components": {"tasks.compute": {"source_path": "task.py"}}, "recovery_rules": {}}), encoding="utf-8")
    saved = manager.publish(candidate / "manifest.json").loaded
    window = FakeWindow()
    startups = []
    original_backend = window.create_input_backend
    def backend():
        assert window.foreground and window.focus_calls == 1
        startups.append(True)
        return original_backend()
    window.create_input_backend = backend
    service = ApplicationService(manager.data_root, manifest_manager=manager, window_platform=window)
    run_id = service.start("tasks.compute", {}, manifest_id=saved.manifest_id)
    done = service.wait_for(lambda s: s["run_id"] == run_id and s["phase"] == "finished")
    assert done["result"]["output"] == 7
    assert startups == [True] and window.backend.closed
    events = [e["event"] for e in done["trace"]]
    assert events.index("target_window_connected") < events.index("component_started")
    assert window.captures == 0  # 启动会话不代替 Component 决定何时截图。
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"items": [{"task": "tasks.compute", "inputs": {}}] * 2}), encoding="utf-8")
    plan_window = FakeWindow()
    plan_service = ApplicationService(manager.data_root, manifest_manager=manager, window_platform=plan_window)
    plan_run = plan_service.start_plan(plan, manifest_id=saved.manifest_id)
    done = plan_service.wait_for(lambda s: s["run_id"] == plan_run and s["phase"] == "finished")
    assert done["result"]["status"] == "completed"
    assert plan_window.focus_calls == 1 and plan_window.backend.closed
    assert len(done["result"]["items"]) == 2


def test_unavailable_window_fails_run_before_component_entry(tmp_path):
    from test_focused_observation import FakeWindowPlatform
    from test_manifest import _write_candidate
    manager = ManifestManager(tmp_path / "data")
    saved = manager.publish(_write_candidate(tmp_path / "candidate")).loaded
    service = ApplicationService(manager.data_root, manifest_manager=manager,
                                 window_platform=FakeWindowPlatform(windows=[]))
    run_id = service.start("steps.finish", {}, manifest_id=saved.manifest_id)
    done = service.wait_for(lambda s: s["run_id"] == run_id and s["phase"] == "finished")
    assert done["result"]["status"] == "failure"
    assert "Expected one Limbus Company window" in done["result"]["traceback"]
    assert not any(e["event"] == "component_started" for e in done["trace"])


def test_old_saved_manifest_is_rejected_without_rewriting_it(tmp_path):
    manager = ManifestManager(tmp_path / "data")
    candidate = draft(tmp_path, manager)
    saved = manager.publish(candidate / "manifest.json").loaded
    path = manager.manifests_dir / f"{saved.manifest_id}.json"
    legacy = {**saved.manifest, "schema_version": 1, "assets": {}, "trusted_actions": {}}
    path.write_text(json.dumps(legacy), encoding="utf-8")
    before = path.read_bytes()
    result = manager.load(saved.manifest_id)
    assert not result.ok
    assert {e.code for e in result.errors} >= {"schema_version_unsupported", "field_unknown"}
    assert path.read_bytes() == before
    assert not manager.list_manifests()
