"""覆盖模板检测、文件约束、优先标签分组、使用索引、现场裁剪及同 Run 可见性。

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
    ok, data = cv2.imencode(".png", template() if image is None else image)
    assert ok
    digest = sha256_bytes(data.tobytes())
    path = root / "assets" / name / f"{digest}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.tobytes())
    return {"path": f"{name}/{digest}.png", "sha256": digest}


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



def matching(library, *, image=None, **options):
    events = []
    found = library.match("ui/claim", pixels(screenshot() if image is None else image), (12, 8),
                          run_id=3, observation=7, emit=lambda event, fields: events.append((event, fields)),
                          threshold=0.999, **options)
    return found, events


def test_tags_are_optional_and_all_templates_are_candidates(tmp_path):
    library = AssetLibrary(tmp_path)
    saved = entry(tmp_path, "ui/claim")
    found, events = matching(library)
    assert [(d["x"], d["y"], d["tags"]) for d in found] == [(2, 1, []), (8, 5, [])]
    assert events[-1][1]["templates"][0]["sha256"] == saved["sha256"]
    tags_path = tmp_path / "assets/ui/claim/asset-tag.json"
    tags_path.write_text("{}", encoding="utf-8")
    assert matching(library)[0] == found
    index = json.loads((tmp_path / "asset-usage.json").read_text(encoding="utf-8"))
    assert index["ui/claim"]["detections"] == json.loads(json.dumps(found))


def test_priority_group_short_circuits_remaining_image_reads(tmp_path):
    library = AssetLibrary(tmp_path)
    first = entry(tmp_path, "ui/claim")
    # 不同尺寸模板也有命中，优先组应返回两者而非只选最高分模板。
    second = entry(tmp_path, "ui/claim", screenshot()[0:4, 1:5])
    third = entry(tmp_path, "ui/claim", np.full((2, 2, 3), 255, dtype=np.uint8))
    tags = {first["sha256"]: ["zh"], second["sha256"]: ["event"], third["sha256"]: []}
    (tmp_path / "assets/ui/claim/asset-tag.json").write_text(json.dumps(tags), encoding="utf-8")
    (tmp_path / "assets" / third["path"]).write_bytes(b"remaining must not be read")
    found, events = matching(library, priority_tags=["zh", "event"], nms=False)
    assert {d["sha256"] for d in found} == {first["sha256"], second["sha256"]}
    assert events[-1][1]["matched_batch"] == "preferred"
    assert len(events[-1][1]["templates"]) == 2
    assert [d["score"] for d in found] == sorted((d["score"] for d in found), reverse=True)


def test_priority_failure_falls_back_to_untagged_templates(tmp_path):
    library = AssetLibrary(tmp_path)
    bad = entry(tmp_path, "ui/claim", np.full((2, 2, 3), 255, dtype=np.uint8))
    good = entry(tmp_path, "ui/claim")
    (tmp_path / "assets/ui/claim/asset-tag.json").write_text(json.dumps({bad["sha256"]: ["zh"]}), encoding="utf-8")
    found, events = matching(library, priority_tags=["zh"])
    assert {d["sha256"] for d in found} == {good["sha256"]}
    assert events[-1][1]["matched_batch"] == "remaining"
    assert len(events[-1][1]["templates"]) == 2
    assert matching(library, priority_tags=None)[0] == matching(library, priority_tags=[])[0]
    before = (tmp_path / "asset-usage.json").read_bytes()
    assert matching(library, image=np.zeros((8, 12, 3), dtype=np.uint8))[0] == []
    assert (tmp_path / "asset-usage.json").read_bytes() == before


def test_cross_template_nms_uses_actual_sizes_and_stable_order(tmp_path):
    library = AssetLibrary(tmp_path)
    entry(tmp_path, "ui/claim")
    entry(tmp_path, "ui/claim", screenshot()[0:4, 1:5])
    unfiltered, _ = matching(library, nms=False)
    filtered, _ = matching(library, nms_iou_threshold=0.1)
    assert len(unfiltered) > len(filtered)
    assert filtered == matching(library, nms_iou_threshold=0.1)[0]
    assert {d["sha256"] for d in unfiltered} != set()


def test_hash_decode_and_path_errors_remain_errors(tmp_path):
    library = AssetLibrary(tmp_path)
    saved = entry(tmp_path, "ui/claim")
    path = tmp_path / "assets" / saved["path"]
    path.write_bytes(b"broken")
    with pytest.raises(ValueError, match="hash mismatch"):
        matching(library)
    path.unlink()
    digest = sha256_bytes(b"broken")
    (path.parent / f"{digest}.png").write_bytes(b"broken")
    with pytest.raises(ValueError, match="decoded"):
        matching(library)
    for path in ("../outside.png", "/outside.png", "C:/outside.png", "..\\outside.png"):
        with pytest.raises(ValueError):
            library.path(path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "assets/link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="escapes"):
        library.path("link/image.png")


@pytest.mark.parametrize("bad_tags", [None, "zh", [1], [""]])
def test_malformed_tag_metadata_is_not_a_missing_tag(tmp_path, bad_tags):
    library = AssetLibrary(tmp_path)
    saved = entry(tmp_path, "ui/claim")
    (tmp_path / "assets/ui/claim/asset-tag.json").write_text(json.dumps({saved["sha256"]: bad_tags}), encoding="utf-8")
    with pytest.raises(ValueError):
        matching(library)


def test_missing_logical_name_is_distinct_from_empty_directory(tmp_path):
    library = AssetLibrary(tmp_path)
    with pytest.raises(FileNotFoundError):
        matching(library)
    (tmp_path / "assets/ui/claim").mkdir(parents=True)
    assert matching(library)[0] == []


def test_full_hash_path_never_overwrites_different_bytes(tmp_path):
    library = AssetLibrary(tmp_path)
    content, _ = library.crop_content(pixels(screenshot()), (12, 8), {"x": 2, "y": 1, "width": 2, "height": 2})
    path = library.path(f"ui/claim/{sha256_bytes(content)}.png")
    path.parent.mkdir(parents=True)
    path.write_bytes(b"old content")
    with pytest.raises(FileExistsError):
        library.save_crop("ui/claim", pixels(screenshot()), (12, 8),
                          {"x": 2, "y": 1, "width": 2, "height": 2}, run_id=1, observation=1)
    assert path.read_bytes() == b"old content"


def finish(service, run_id):
    return service.wait_for(lambda state: state["run_id"] == run_id and state["phase"] == "finished")


def test_same_run_sees_new_crops_tags_and_preserves_manifest(tmp_path):
    """同一正式 Step 内裁剪后立即匹配，再追加标签；无需 publish 或切换 Manifest。"""
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "step.py").write_text('''"""新素材的立即可见性与标签更新。"""
from lalc import step

@step
def execute(ctx) -> str:
    ctx.action("observe.crop_asset", asset="ui/claim", region={"x":2,"y":1,"width":2,"height":2})
    ctx.action("observe.capture_screen", save=True)
    first = ctx.action("observe.match_asset", asset="ui/claim", threshold=0.999)
    ctx.action("observe.crop_asset", asset="ui/claim", region={"x":2,"y":1,"width":2,"height":2}, tags=["event"])
    second = ctx.action("observe.match_asset", asset="ui/claim", priority_tags=["event"], threshold=0.999)
    return str([first[0]["tags"], second[0]["tags"]])
''', encoding="utf-8")
    (candidate / "manifest.json").write_text(json.dumps({"schema_version":2,"components":{"steps.find":{"source_path":"step.py"}},"recovery_rules":{}}), encoding="utf-8")
    manager = ManifestManager(tmp_path)
    published = manager.publish(candidate / "manifest.json")
    assert published.ok, published.errors
    manifest = published.loaded.manifest_id
    before = (tmp_path / "manifests" / f"{manifest}.json").read_bytes()
    service = ApplicationService(tmp_path, manifest_manager=manager, window_platform=Window())
    state = finish(service, service.start("steps.find", {}, manifest_id=manifest))
    assert state["result"]["output"] == "[[], ['event']]"
    assert state["working_manifest_id"] == manifest
    assert state["attempted_manifest_ids"] == [manifest]
    assert len(manager.list_manifests()) == 1
    assert (tmp_path / "manifests" / f"{manifest}.json").read_bytes() == before
    matches = [e for e in state["trace"] if e["event"] == "asset_matched"]
    assert len(matches) == 2 and matches[1]["priority_tags"] == ["event"]
    saved = [e for e in state["trace"] if e["event"] == "screenshot_saved"]
    assert saved and Path(saved[0]["path"]).is_file()
    assert all(e["detections"][0]["observation"] == e["observation"] for e in matches)


def test_formal_error_keeps_original_stack_and_trusted_action_boundary(tmp_path):
    fixture = Path(__file__).resolve().parent / "fixtures/asset-recognition"
    manager = ManifestManager(tmp_path)
    published = manager.publish(fixture / "manifest.json")
    assert published.ok
    saved = entry(tmp_path, "ui/claim")
    (tmp_path / "assets" / saved["path"]).write_bytes(b"changed")
    state = finish(service := ApplicationService(tmp_path, manifest_manager=manager, window_platform=Window()),
                   service.start("steps.detect", {"asset":"ui/claim"}, manifest_id=published.loaded.manifest_id))
    assert state["result"]["status"] == "failure"
    assert "Asset hash mismatch" in state["result"]["traceback"]
    assert "assets.py" in state["result"]["traceback"]


def test_each_match_freezes_tags_but_next_call_observes_updates(tmp_path, monkeypatch):
    import lalc.recognition as recognition
    library = AssetLibrary(tmp_path)
    first = entry(tmp_path, "ui/claim")
    second = entry(tmp_path, "ui/claim", screenshot()[0:4, 1:5])
    path = library.path("ui/claim/asset-tag.json")
    detect = recognition.detect_template
    def change_tags(*args, **kwargs):
        path.write_text(json.dumps({first["sha256"]:["new"],second["sha256"]:["new"]}), encoding="utf-8")
        return detect(*args, **kwargs)
    monkeypatch.setattr(recognition, "detect_template", change_tags)
    found, _ = matching(library, nms=False)
    assert all(d["tags"] == [] for d in found)
    assert all(d["tags"] == ["new"] for d in matching(library, nms=False)[0])


def test_usage_index_survives_later_step_failure(tmp_path):
    fixture = Path(__file__).resolve().parent / "fixtures/asset-recognition"
    candidate = tmp_path / "candidate"
    shutil.copytree(fixture, candidate)
    path = candidate / "steps.detect.py"
    path.write_text(path.read_text(encoding="utf-8").replace('return ctx.action("observe.match_asset"', 'result = ctx.action("observe.match_asset"') + '\n    raise ValueError("business check failed")\n', encoding="utf-8")
    manager = ManifestManager(tmp_path)
    published = manager.publish(candidate / "manifest.json")
    assert published.ok, published.errors
    entry(tmp_path, "ui/claim")
    service = ApplicationService(tmp_path, manifest_manager=manager, window_platform=Window())
    state = finish(service, service.start("steps.detect", {"asset":"ui/claim"}, manifest_id=published.loaded.manifest_id))
    assert state["result"]["status"] == "failure"
    stored = json.loads((tmp_path / "asset-usage.json").read_text(encoding="utf-8"))["ui/claim"]
    assert len(stored["detections"]) == 2


@pytest.mark.parametrize("operation", ["match", "crop"])
def test_components_cannot_bypass_asset_trusted_action_gate(tmp_path, operation):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    call = 'str(ctx.match_asset("ui/claim"))' if operation == "match" else 'str(ctx.crop_asset("ui/claim", region={"x":2,"y":1,"width":2,"height":2}))'
    (candidate / "step.py").write_text('"""验证素材调用权限。"""\nfrom lalc import step\n@step\ndef execute(ctx) -> str:\n    return '+call+'\n', encoding="utf-8")
    (candidate / "manifest.json").write_text(json.dumps({"schema_version":2,"components":{"steps.find":{"source_path":"step.py"}},"recovery_rules":{}}), encoding="utf-8")
    manager = ManifestManager(tmp_path)
    published = manager.publish(candidate / "manifest.json")
    assert published.ok, published.errors
    service = ApplicationService(tmp_path, manifest_manager=manager, window_platform=Window())
    state = finish(service, service.start("steps.find", {}, manifest_id=published.loaded.manifest_id))
    assert state["result"]["status"] == "failure"
    assert "requires an observe Trusted Action" in state["result"]["traceback"]


def test_crop_is_fresh_and_keeps_original_pixels_and_provenance(tmp_path):
    fixture = Path(__file__).resolve().parent / "fixtures/asset-recognition"
    manager = ManifestManager(tmp_path)
    published = manager.publish(fixture / "manifest.json")
    assert published.ok
    window = Window()
    service = ApplicationService(tmp_path, manifest_manager=manager, window_platform=window)
    inputs = {"asset":"ui/claim","region":{"x":2,"y":1,"width":2,"height":2}}
    first = finish(service, service.start("steps.crop", inputs, manifest_id=published.loaded.manifest_id))["result"]["output"]
    original = Path(first["image_path"]).read_bytes()
    window.image[1:3,2:4] = 177
    second = finish(service, service.start("steps.crop", inputs, manifest_id=published.loaded.manifest_id))["result"]["output"]
    assert first["sha256"] != second["sha256"] and window.captures == 2
    assert np.all(decode_image(Path(second["image_path"]).read_bytes()) == 177)
    assert Path(first["image_path"]).read_bytes() == original
    for crop in (first, second):
        record = json.loads((tmp_path / "asset-provenance" / f"{crop['provenance_id']}.json").read_text(encoding="utf-8"))
        assert record["sha256"] == crop["sha256"] and record["region"] == inputs["region"]
