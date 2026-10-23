"""覆盖 schema 2、独立库发布、开发者裁剪确认和应用统一动作边界。

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
from test_assets import Window, entry, screenshot


REGION = {"x": 2, "y": 1, "width": 2, "height": 2}


def draft(root: Path, manager: ManifestManager) -> Path:
    folder = root / "candidate"
    assert not manager.initialize_candidate(folder)
    return folder


def mapping(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_asset_only_publish_creates_independent_complete_libraries(tmp_path):
    manager = ManifestManager(tmp_path / "data")
    candidate = draft(tmp_path, manager)
    shared = entry(manager.data_root, "shared.png")
    (candidate / "asset-library.json").write_text(json.dumps({"ui/claim": {"en": shared}}), encoding="utf-8")
    first = manager.publish(candidate / "manifest.json")
    assert first.ok
    first_id = first.loaded.manifest_id
    assert manager.set_default(first_id).ok
    second_candidate = tmp_path / "second"
    assert not manager.initialize_candidate(second_candidate)
    assert mapping(second_candidate / "asset-library.json") == first.loaded.assets
    second = manager.publish(second_candidate / "manifest.json")
    assert second.ok and second.loaded.manifest_id != first_id
    assert second.loaded.assets == first.loaded.assets
    assert len(list((manager.data_root / "assets").glob("*.png"))) == 1
    assert not manager.validate(second_candidate / "manifest.json")
    assert set(mapping(second_candidate / "manifest.json")) == {"schema_version", "components", "recovery_rules"}
    # 仅修改草稿库再发布，不修改任何已保存库或 Component 映射。
    (second_candidate / "asset-library.json").write_text("{}", encoding="utf-8")
    third = manager.publish(second_candidate / "manifest.json")
    assert third.ok and third.loaded.assets == {}
    assert manager.load(first_id).loaded.assets == first.loaded.assets
    assert manager.load(second.loaded.manifest_id).loaded.assets == first.loaded.assets
    assert manager.default_manifest_id() == first_id
    assert third.loaded.manifest["components"] == first.loaded.manifest["components"]
    assert set(mapping(manager.manifests_dir / f"{first_id}.json")) == {
        "schema_version", "manifest_id", "components", "recovery_rules"}


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
    assert not manager.asset_libraries_dir.exists()


def test_missing_library_does_not_fall_back_to_another_manifest(tmp_path):
    manager = ManifestManager(tmp_path / "data")
    candidate = draft(tmp_path, manager)
    a = manager.publish(candidate / "manifest.json").loaded
    b = manager.publish(candidate / "manifest.json").loaded
    (manager.asset_libraries_dir / f"{a.manifest_id}.json").unlink()
    rejected = manager.load(a.manifest_id)
    assert not rejected.ok
    assert manager.load(b.manifest_id).ok


@pytest.mark.parametrize("answer", ["n", "", "eof", "cancel"])
def test_cli_duplicate_refusal_changes_no_files(tmp_path, monkeypatch, capsys, answer):
    import lalc.application as application
    manager = ManifestManager(tmp_path / "data")
    candidate = draft(tmp_path, manager)
    old = entry(manager.data_root, "old.png")
    (candidate / "asset-library.json").write_text(json.dumps({"ui/claim": {"en": old}}), encoding="utf-8")
    window = Window()
    window.image = screenshot().copy()
    window.image[1:3, 2:4] = 255
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "default_data_root", lambda: manager.data_root)
    monkeypatch.setattr(application, "WindowsWindowPlatform", lambda **_: window)
    def respond(prompt):
        assert "already has an image" in prompt
        if answer == "eof":
            raise EOFError
        if answer == "cancel":
            raise KeyboardInterrupt
        return answer
    monkeypatch.setattr("builtins.input", respond)
    cli.configure_logging(manager.data_root)
    before = {p: p.read_bytes() for base in (candidate, manager.data_root) for p in base.rglob("*") if p.is_file()}
    assert cli.main(["crop-asset", "ui/claim", "--region", json.dumps(REGION)]) == 1
    assert window.captures == 1
    after = {p: p.read_bytes() for base in (candidate, manager.data_root) for p in base.rglob("*") if p.is_file()}
    assert after == before
    assert "cancelled" in capsys.readouterr().err


def test_candidate_crop_replacement_language_and_identical_reuse(tmp_path):
    manager = ManifestManager(tmp_path / "data")
    candidate = draft(tmp_path, manager)
    window = Window()
    service = ApplicationService(manager.data_root, manifest_manager=manager, window_platform=window)
    first = service.crop_candidate_asset(candidate, "ui/claim", REGION, lambda _: pytest.fail("new pair"))
    assert first["path"].endswith(f"-{first['sha256']}.png")
    old_bytes = Path(first["image_path"]).read_bytes()
    saved = manager.publish(candidate / "manifest.json").loaded
    saved_bytes = (manager.asset_libraries_dir / f"{saved.manifest_id}.json").read_bytes()
    same = service.crop_candidate_asset(candidate, "ui/claim", REGION, lambda _: pytest.fail("identical content"))
    assert same["unchanged"] and same["path"] == first["path"]
    assert len(list((manager.data_root / "asset-provenance").glob("*.json"))) == 1
    window.image = screenshot().copy()
    window.image[1:3, 2:4] = 255
    prompts = []
    replacement = service.crop_candidate_asset(candidate, "ui/claim", REGION, lambda prompt: prompts.append(prompt) or True)
    assert len(prompts) == 1 and replacement["path"] != first["path"]
    assert Path(first["image_path"]).read_bytes() == old_bytes
    assert (manager.asset_libraries_dir / f"{saved.manifest_id}.json").read_bytes() == saved_bytes
    assert manager.load(saved.manifest_id).loaded.assets["ui/claim"]["en"]["path"] == first["path"]
    service.game_language = "zh"
    other = service.crop_candidate_asset(candidate, "ui/claim", REGION, lambda _: pytest.fail("another language"))
    assert other["source_language"] == "zh"
    assert set(mapping(candidate / "asset-library.json")["ui/claim"]) == {"en", "zh"}
    assert window.captures == 4


def test_production_action_registration_is_shared_and_not_manifest_owned(tmp_path):
    actions = application_actions()
    manager = ManifestManager(tmp_path, actions=actions)
    assert set(actions) == {"observe.capture_screen", "observe.match_asset", "observe.crop_asset",
                            "control.click", "control.key_press", "control.drag", "control.wait"}
    actions.clear()
    assert manager.actions["control.wait"].classification == "control"
    with pytest.raises(TypeError):
        manager.actions["new"] = manager.actions["control.wait"]


def test_published_library_is_loaded_as_an_independent_memory_mapping(tmp_path):
    manager = ManifestManager(tmp_path / "data")
    candidate = draft(tmp_path, manager)
    saved = entry(manager.data_root, "a.png")
    (candidate / "asset-library.json").write_text(json.dumps({"ui/claim": {"en": saved}}), encoding="utf-8")
    published = manager.publish(candidate / "manifest.json").loaded
    loaded = manager.load(published.manifest_id).loaded
    loaded.assets["ui/claim"]["en"]["path"] = "memory-only.png"
    assert manager.load(published.manifest_id).loaded.assets["ui/claim"]["en"] == saved
    assert published.assets["ui/claim"]["en"] == saved


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


def test_full_hash_path_with_different_bytes_is_never_overwritten(tmp_path):
    from lalc.assets import AssetLibrary
    from test_assets import pixels
    library = AssetLibrary(tmp_path)
    image = screenshot()
    first = library.save_crop("ui/claim", "en", pixels(image), (12, 8), REGION, run_id=None, observation=1)
    path = Path(first["image_path"])
    path.write_bytes(b"unexpected existing content")
    with pytest.raises(FileExistsError):
        library.save_crop("ui/claim", "en", pixels(image), (12, 8), REGION, run_id=None, observation=2)
    assert path.read_bytes() == b"unexpected existing content"


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
