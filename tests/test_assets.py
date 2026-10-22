"""覆盖模板检测、Asset 文件约束、语言选择、使用索引、现场裁剪及恢复切换。

在项目根目录运行：
UV_CACHE_DIR=.generated/uv-cache uv run --frozen --extra automation pytest -q tests/test_assets.py
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import cv2
import numpy as np
import pytest

from lalc.application import ApplicationService
from lalc.assets import AssetLibrary
from lalc.manifest import ManifestManager
from lalc.recognition import decode_image, detect_template
from lalc.runtime import sha256_bytes


def template() -> np.ndarray:
    return np.array([[[20, 60, 230], [200, 40, 90]],
                     [[75, 220, 20], [190, 95, 160]]], dtype=np.uint8)


def screenshot() -> np.ndarray:
    image = np.zeros((8, 12, 3), dtype=np.uint8)
    image[1:3, 2:4] = template()
    image[5:7, 8:10] = template()
    return image


def pixels(image: np.ndarray) -> bytes:
    return cv2.cvtColor(image, cv2.COLOR_BGR2BGRA).tobytes()


def entry(root: Path, name: str, image: np.ndarray | None = None) -> dict[str, str]:
    path = root / "assets" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, data = cv2.imencode(".png", template() if image is None else image)
    assert ok
    path.write_bytes(data.tobytes())
    return {"path": name, "sha256": sha256_bytes(data.tobytes())}


def test_local_detection_and_empty_results() -> None:
    found = detect_template(screenshot(), template(), threshold=0.999)
    assert [(d["x"], d["y"]) for d in found] == [(2, 1), (8, 5)]
    local = detect_template(screenshot(), template(), threshold=0.999,
                            region={"x": 7, "y": 4, "width": 5, "height": 4})
    assert [(d["x"], d["y"]) for d in local] == [(8, 5)]
    assert detect_template(np.zeros((4, 4, 3), dtype=np.uint8), template()) == []
    assert detect_template(screenshot(), np.ones((20, 20, 3), dtype=np.uint8)) == []


def test_nms_stable_order_and_strict_iou() -> None:
    image = np.full((2, 3, 3), 150, dtype=np.uint8)
    templ = image[:, :2]
    options = {"threshold": 0.99, "nms_iou_threshold": 0.3}
    assert [d["x"] for d in detect_template(image, templ, nms=False, **options)] == [0, 1]
    assert [d["x"] for d in detect_template(image, templ, **options)] == [0]
    assert len(detect_template(image, templ, nms_iou_threshold=1 / 3)) == 2
    black = np.zeros((2, 2, 3), dtype=np.uint8)
    assert len(detect_template(black, black, threshold=1)) == 1


@pytest.mark.parametrize("options", [
    {"threshold": float("nan")}, {"threshold": 1.1}, {"nms_iou_threshold": -1},
    {"nms": 1}, {"region": {"x": -1, "y": 0, "width": 2, "height": 2}},
    {"region": {"x": 0, "y": 0, "width": 20, "height": 2}},
])
def test_invalid_detection_inputs_are_errors(options) -> None:
    with pytest.raises(ValueError):
        detect_template(screenshot(), template(), **options)


def test_language_selection_index_and_no_automatic_mapping(tmp_path: Path) -> None:
    library = AssetLibrary(tmp_path)
    first = entry(tmp_path, "a.png")
    second = entry(tmp_path, "b.png")
    bad = entry(tmp_path, "bad.png", np.full((2, 2, 3), 255, dtype=np.uint8))
    mapping = {"ui/claim": {"zh": second, "en": first}}
    original = json.loads(json.dumps(mapping))
    events = []
    options = {"run_id": 3, "observation": 7, "emit": lambda event, fields: events.append((event, fields)),
               "threshold": 0.999}
    found = library.match(mapping, "ui/claim", "ja", pixels(screenshot()), (12, 8), **options)
    assert len(found) == 2
    assert all(d["source_language"] == "en" for d in found)
    assert found[0]["normalized_region"]["x"] == 2 / 12
    assert mapping == original
    assert not (tmp_path / "evidence").exists()
    stored = next(iter(json.loads((tmp_path / "asset-usage.json").read_text(encoding="utf-8")).values()))
    assert stored["detections"] == found
    assert stored["observation"] == 7 and stored["trace_path"] == "traces/3.jsonl"
    before = (tmp_path / "asset-usage.json").read_bytes()
    mapping["ui/claim"]["ja"] = bad
    assert library.match(mapping, "ui/claim", "ja", pixels(screenshot()), (12, 8), **options) == []
    assert (tmp_path / "asset-usage.json").read_bytes() == before
    assert events[-1][1]["detections"] == []


def test_hash_decode_and_path_errors_remain_errors(tmp_path: Path) -> None:
    library = AssetLibrary(tmp_path)
    saved = entry(tmp_path, "a.png")
    (tmp_path / "assets" / "a.png").write_bytes(b"broken")
    with pytest.raises(ValueError, match="hash mismatch"):
        library.validate({"ui/claim": {"en": saved}})
    saved["sha256"] = sha256_bytes(b"broken")
    with pytest.raises(ValueError, match="decoded"):
        library.validate({"ui/claim": {"en": saved}})
    for path in ("../outside.png", "/outside.png", "C:/outside.png", "..\\outside.png"):
        with pytest.raises(ValueError):
            library.path(path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "assets" / "link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="escapes"):
        library.path("link/image.png")


class Window:
    """固定客户区图像，可在下一次截图时替换内容。"""

    def __init__(self) -> None:
        self.image = screenshot()
        self.captures = 0
        self.foreground = True

    def find_windows(self):
        return [7]

    def create_input_backend(self):
        from test_input_control import FakeInput
        return FakeInput()

    def focus(self, hwnd):
        pass

    def window_info(self, hwnd):
        return {"hwnd": 7, "process_id": 1, "width": 12, "height": 8,
                "valid": True, "visible": True, "minimized": False,
                "foreground": self.foreground, "title": "LimbusCompany"}

    def capture(self, hwnd, width, height):
        self.captures += 1
        return pixels(self.image)


ACTION = '''"""语义匹配和现场裁剪观察动作。"""
import json

def execute(ctx, *, crop: bool = False) -> str:
    if crop:
        return json.dumps(ctx.crop_asset("ui/claim", region={"x": 2, "y": 1, "width": 2, "height": 2}))
    return json.dumps(ctx.match_asset("ui/claim", threshold=0.999))
'''
STEP = '''"""在同一截图内识别多个按钮。"""
from lalc import step

@step
def execute(ctx) -> str:
    ctx.action("observe.capture")
    return ctx.action("observe.match")
'''


def publish(folder: Path, manager: ManifestManager, mapping: dict, source: str = STEP) -> str:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "step.py").write_text(source, encoding="utf-8")
    capture = '''"""刷新内存截图。"""
def execute(ctx) -> int:
    return ctx.capture_screen()["observation"]
'''
    candidate = {"schema_version": 2, "components": {"steps.find": {"source_path": "step.py"}},
                 "recovery_rules": {}}
    from runtime_support import register_sources
    register_sources(manager, {"observe.match": (ACTION, "observe"), "observe.capture": (capture, "observe")})
    (folder / "assets.json").write_text(json.dumps(mapping), encoding="utf-8")
    path = folder / "manifest.json"
    path.write_text(json.dumps(candidate), encoding="utf-8")
    result = manager.publish(path)
    assert result.ok, result.errors
    return result.loaded.manifest_id


def finish(service: ApplicationService, run_id: int) -> dict:
    return service.wait_for(lambda s: s["run_id"] == run_id and s["phase"] == "finished")


def test_formal_run_trace_index_and_original_errors(tmp_path: Path) -> None:
    manager = ManifestManager(tmp_path)
    saved = entry(tmp_path, "a.png")
    manifest = publish(tmp_path / "draft", manager, {"ui/claim": {"zh": saved}})
    service = ApplicationService(tmp_path, manifest_manager=manager, window_platform=Window(), game_language="ja")
    state = finish(service, service.start("steps.find", {}, manifest_id=manifest))
    assert state["result"]["status"] == "success"
    assert len(json.loads(state["result"]["output"])) == 2
    match = next(e for e in state["trace"] if e["event"] == "asset_matched")
    assert match["source_language"] == "zh" and match["running_language"] == "ja"
    assert not (tmp_path / "evidence").exists()
    assert manager.load(manifest).loaded.assets == {"ui/claim": {"zh": saved}}
    # 在成功加载之后破坏文件，必须由运行时报告原始错误而非空匹配。
    window = Window()
    original_capture = window.capture
    def damage(*args):
        (tmp_path / "assets" / "a.png").write_bytes(b"corrupted")
        return original_capture(*args)
    window.capture = damage
    service.window_platform = window
    failed = finish(service, service.start("steps.find", {}, manifest_id=manifest))
    assert failed["result"]["status"] == "failure"
    assert "Asset hash mismatch" in failed["result"]["traceback"]
    assert "assets.py" in failed["result"]["traceback"]


def test_crop_refreshes_and_retains_existing_files(tmp_path: Path) -> None:
    manager = ManifestManager(tmp_path)
    source = STEP.replace('return ctx.action("observe.match")', 'return ctx.action("observe.match", crop=True)')
    manifest = publish(tmp_path / "draft", manager, {}, source)
    original_manifest = (tmp_path / "manifests" / f"{manifest}.json").read_bytes()
    window = Window()
    original_capture = window.capture
    def changing(*args):
        if window.captures:
            window.image[1:3, 2:4] = 177
        return original_capture(*args)
    window.capture = changing
    service = ApplicationService(tmp_path, manifest_manager=manager, window_platform=window)
    state = finish(service, service.start("steps.find", {}, manifest_id=manifest))
    crop = json.loads(state["result"]["output"])
    assert window.captures == 2 and crop["observation"] == 2
    assert np.all(decode_image(Path(crop["image_path"]).read_bytes()) == 177)
    assert crop["sha256"] == sha256_bytes(Path(crop["image_path"]).read_bytes())
    assert (tmp_path / "asset-provenance" / f"{crop['provenance_id']}.json").exists()
    assert not (tmp_path / "evidence").exists()
    assert (tmp_path / "manifests" / f"{manifest}.json").read_bytes() == original_manifest
    before = Path(crop["image_path"]).read_bytes()
    finish(service, service.start("steps.find", {}, manifest_id=manifest))
    assert Path(crop["image_path"]).read_bytes() == before


def test_candidate_condition_uses_new_asset_mapping(tmp_path: Path) -> None:
    manager = ManifestManager(tmp_path)
    old = entry(tmp_path, "old.png", np.full((2, 2, 3), 255, dtype=np.uint8))
    new = entry(tmp_path, "new.png")
    base_source = STEP.replace('return ctx.action("observe.match")', 'raise ValueError("needs new template")')
    base = publish(tmp_path / "base", manager, {"ui/claim": {"en": old}}, base_source)
    replacement_source = STEP + '''
def condition(ctx) -> bool:
    return ctx.action("observe.match") != "[]"
'''
    replacement = publish(tmp_path / "replacement", manager, {"ui/claim": {"en": new}}, replacement_source)
    before = (tmp_path / "manifests" / f"{base}.json").read_bytes()
    choices = iter([replacement, None])
    service = ApplicationService(tmp_path, manifest_manager=manager, window_platform=Window(),
                                 recovery_choice=lambda *_: next(choices))
    state = finish(service, service.start("steps.find", {}, manifest_id=base))
    assert state["result"]["status"] == "success"
    assert state["working_manifest_id"] == replacement
    assert state["attempted_manifest_ids"] == [base, replacement]
    assert (tmp_path / "manifests" / f"{base}.json").read_bytes() == before
    assert (tmp_path / "assets" / "old.png").exists()
    assert all(e["path"] == "new.png" for e in state["trace"] if e["event"] == "asset_matched")


def test_step_failure_keeps_successful_match_index(tmp_path: Path) -> None:
    manager = ManifestManager(tmp_path)
    mapping = {"ui/claim": {"en": entry(tmp_path, "a.png")}}
    source = STEP.replace('return ctx.action("observe.match")',
                          'ctx.action("observe.match")\n    raise ValueError("later business failure")')
    manifest = publish(tmp_path / "draft", manager, mapping, source)
    service = ApplicationService(tmp_path, manifest_manager=manager, window_platform=Window())
    state = finish(service, service.start("steps.find", {}, manifest_id=manifest))
    assert state["result"]["status"] == "failure"
    stored = next(iter(json.loads((tmp_path / "asset-usage.json").read_text(encoding="utf-8")).values()))
    assert len(stored["detections"]) == 2


def test_crop_hash_prefix_collision_does_not_overwrite(tmp_path: Path) -> None:
    library = AssetLibrary(tmp_path)
    image = screenshot()
    content = cv2.imencode(".png", image[1:3, 2:4])[1].tobytes()
    digest = sha256_bytes(content)
    collision = tmp_path / "assets" / f"ui/claim-en-{digest[:12]}.png"
    collision.parent.mkdir(parents=True)
    collision.write_bytes(b"existing file")
    result = library.save_crop("ui/claim", "en", pixels(image), (12, 8),
                               {"x": 2, "y": 1, "width": 2, "height": 2}, run_id=1, observation=1)
    assert result["path"].endswith(f"-{digest}.png")
    assert collision.read_bytes() == b"existing file"
    assert Path(result["image_path"]).read_bytes() == content


def test_assets_incomplete_or_corrupt_manifest_never_publishes(tmp_path: Path) -> None:
    manager = ManifestManager(tmp_path)
    saved = entry(tmp_path, "a.png")
    manifest = publish(tmp_path / "draft", manager, {"ui/claim": {"en": saved}})
    assert manager.set_default(manifest).ok
    path = tmp_path / "draft" / "manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    library = path.parent / "assets.json"
    mapping = json.loads(library.read_text(encoding="utf-8"))
    mapping["ui/claim"]["en"]["sha256"] = "0" * 64
    library.write_text(json.dumps(mapping), encoding="utf-8")
    path.write_text(json.dumps(data), encoding="utf-8")
    result = manager.publish(path)
    assert not result.ok
    error = next(e for e in result.errors if e.code == "asset_invalid")
    assert "hash mismatch" in error.as_dict()["traceback"]
    assert manager.default_manifest_id() == manifest
    assert len(manager.list_manifests()) == 1


def test_candidate_condition_rejection_keeps_base(tmp_path: Path) -> None:
    manager = ManifestManager(tmp_path)
    old = entry(tmp_path, "old.png")
    new = entry(tmp_path, "new.png", np.full((2, 2, 3), 255, dtype=np.uint8))
    source = STEP.replace('return ctx.action("observe.match")', 'raise ValueError("needs repair")')
    base = publish(tmp_path / "base", manager, {"ui/claim": {"en": old}}, source)
    candidate = publish(tmp_path / "candidate", manager, {"ui/claim": {"en": new}},
                        STEP + '\ndef condition(ctx) -> bool:\n    return ctx.action("observe.match") != "[]"\n')
    choices = iter([candidate, None])
    service = ApplicationService(tmp_path, manifest_manager=manager, window_platform=Window(),
                                 recovery_choice=lambda *_: next(choices))
    state = finish(service, service.start("steps.find", {}, manifest_id=base))
    assert state["working_manifest_id"] == base
    assert state["attempted_manifest_ids"] == [base]


def test_asset_fixture_publishes_and_runs_with_typed_results(tmp_path: Path) -> None:
    fixture = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "asset-recognition"
    manager = ManifestManager(tmp_path)
    result = manager.publish(fixture / "manifest.json")
    assert result.ok, result.errors
    manifest = result.loaded.manifest_id
    service = ApplicationService(tmp_path, manifest_manager=manager, window_platform=Window(), game_language="zh")
    state = finish(service, service.start("steps.crop", {
        "asset": "ui/claim", "region": {"x": 2, "y": 1, "width": 2, "height": 2},
    }, manifest_id=manifest))
    assert state["result"]["status"] == "success"
    crop = state["result"]["output"]
    assert crop["source_language"] == "zh" and crop["observation"] == 1
    # 新建候选引用裁剪文件，通过正式加载、Plan 入口检测，不改原 Manifest。
    draft = tmp_path / "new"
    shutil.copytree(fixture, draft)
    data = json.loads((draft / "manifest.json").read_text(encoding="utf-8"))
    (draft / "assets.json").write_text(json.dumps({"ui/claim": {"zh": {key: crop[key] for key in ("path", "sha256")}}}), encoding="utf-8")
    data["components"]["tasks.detect"] = {"source_path": "task.py"}
    (draft / "task.py").write_text('''"""识别任务。"""
from lalc import task_workflow
@task_workflow
def execute(ctx) -> int:
    return len(ctx.call("steps.detect", asset="ui/claim", threshold=0.999))
''', encoding="utf-8")
    (draft / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
    published = manager.publish(draft / "manifest.json")
    assert published.ok, published.errors
    plan = draft / "plan.json"
    plan.write_text(json.dumps({"items": [{"task": "tasks.detect", "inputs": {}}]}), encoding="utf-8")
    state = finish(service, service.start_plan(plan, manifest_id=published.loaded.manifest_id))
    assert state["result"]["status"] == "completed"
    task = next(e for e in state["trace"] if e["event"] == "component_returned" and e["logical_name"] == "tasks.detect")
    assert task["return_value"] == 2
    assert manager.load(manifest).loaded.assets == {}


def test_matching_cannot_bypass_trusted_action_gate(tmp_path: Path) -> None:
    manager = ManifestManager(tmp_path)
    source = STEP.replace('return ctx.action("observe.match")', 'return str(ctx.match_asset("ui/claim"))')
    manifest = publish(tmp_path / "draft", manager, {"ui/claim": {"en": entry(tmp_path, "a.png")}}, source)
    service = ApplicationService(tmp_path, manifest_manager=manager, window_platform=Window())
    state = finish(service, service.start("steps.find", {}, manifest_id=manifest))
    assert state["result"]["status"] == "failure"
    assert "requires an observe Trusted Action" in state["result"]["traceback"]


def test_cli_carries_running_language_to_crop(tmp_path: Path, monkeypatch, capsys) -> None:
    import lalc.__main__ as cli

    manager = ManifestManager(tmp_path)
    fixture = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "asset-recognition"
    published = manager.publish(fixture / "manifest.json")
    assert published.ok
    monkeypatch.setattr(cli, "default_data_root", lambda: tmp_path)
    monkeypatch.setattr(cli, "ApplicationService", lambda root, **kwargs: ApplicationService(
        root, window_platform=Window(), **kwargs,
    ))
    inputs = json.dumps({"asset": "ui/claim", "region": {"x": 2, "y": 1, "width": 2, "height": 2}})
    assert cli.main(["run", "steps.crop", "--manifest", published.loaded.manifest_id,
                     "--language", "ja", "--inputs", inputs]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["output"]["source_language"] == "ja"
