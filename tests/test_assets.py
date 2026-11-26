"""覆盖模板检测、按路径组匹配、使用索引、现场和暂存裁剪及同 Run 可见性。

在项目根目录运行：
UV_CACHE_DIR=.generated/uv-cache uv run --frozen --extra automation pytest -q tests/test_assets.py
"""

from __future__ import annotations

import json
import shutil
from collections import Counter
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
        self.size = (12, 8)

    def find_windows(self):
        return [7]

    def cursor_position(self, hwnd):
        return {"x": -1, "y": -1, "inside": False}

    def create_input_backend(self):
        from test_input_control import FakeInput
        return FakeInput()

    def open_game_process(self, pid):
        from test_input_control import FakeProcess
        return FakeProcess(pid)

    def focus(self, hwnd, *, checkpoint=None, max_attempts=10, on_first_attempt=None, fallback=None):
        if checkpoint is not None:
            checkpoint()

    def window_info(self, hwnd):
        return {"hwnd": 7, "process_id": 1, "width": self.size[0], "height": self.size[1],
                "valid": True, "visible": True, "minimized": False,
                "foreground": self.foreground, "title": "LimbusCompany"}

    def capture(self, hwnd, width, height):
        self.captures += 1
        frame = np.zeros((height, width, 3), dtype=self.image.dtype)
        image_height, image_width = self.image.shape[:2]
        frame[:image_height, :image_width] = self.image
        return pixels(frame)

    def resize_client(self, hwnd, width, height):
        self.size = (width, height)



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


def test_group_in_regions_matches_independent_searches_on_one_frame(tmp_path, monkeypatch):
    from lalc.image_annotations import action_annotations
    from lalc.run_logs import log_text
    from runtime_support import add_plan

    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "step.py").write_text('''"""对照各窗口的正式 Action 返回值。"""
from lalc import step

@step
def execute(ctx) -> str:
    ctx.action("observe.capture_screen")
    right = {"x": 7, "y": 4, "width": 5, "height": 4}
    partial = {"x": 3, "y": 1, "width": 3, "height": 2}
    left = {"x": 1, "y": 0, "width": 4, "height": 4}
    overlap = {"x": 2, "y": 1, "width": 4, "height": 4}
    regions = [right, partial, left, overlap]
    group = "items"
    for nms in [True, False]:
        options = {"group": group, "threshold": 0.999, "nms": nms}
        expected = [ctx.action("observe.match_asset_group", region=region, **options) for region in regions]
        actual = ctx.action("observe.match_asset_group_in_regions", regions=regions, **options)
        assert actual == expected
        count = 1 if nms else 2
        assert [len(hits) for hits in actual] == [1, 0, count, count]
        assert actual[2] == actual[3]
        assert actual[0][0]["centerxy"] == (9, 6)
    assert ctx.action("observe.match_asset_group_in_regions", group="missing", regions=regions) == [[], [], [], []]
    assert ctx.action("observe.match_asset_group_in_regions", group=group, regions=[]) == []
    return "ok"
''', encoding="utf-8")
    manifest = candidate / "manifest.json"
    manifest.write_text(json.dumps({"schema_version": 2, "components": {
        "steps.find": {"source_path": "step.py"}}, "recovery_rules": {}}), encoding="utf-8")
    add_plan(manifest)
    manager = ManifestManager(tmp_path)
    published = manager.publish(manifest)
    assert published.ok, published.errors

    second = np.flip(template(), axis=0).copy()
    entries = [entry(tmp_path, "items/one"), entry(tmp_path, "items/duplicate"),
               entry(tmp_path, "items/other/two", second)]
    reads = Counter()
    read = AssetLibrary.read

    def counted_read(library, asset):
        reads[asset["path"]] += 1
        return read(library, asset)

    monkeypatch.setattr(AssetLibrary, "read", counted_read)
    window = Window()
    window.image[5:7, 8:10] = second
    service = ApplicationService(tmp_path, manifest_manager=manager, window_platform=window)
    state = finish(service, service.start("steps.find", {}, manifest_id=published.loaded.manifest_id))
    assert state["result"]["status"] == "success", state["result"]
    assert window.captures == 1
    assert reads == {asset["path"]: 10 for asset in entries}

    calls = [record for record in state["trace"] if record["event"] == "trusted_action_returned"
             and record.get("logical_name") == "observe.match_asset_group_in_regions"]
    assert [len(record["return_value"]) for record in calls] == [4, 4, 4, 0]
    assert calls[0]["debug_image"]["evidence_id"].endswith("/1")
    assert [(box["number"], box["x"]) for box in action_annotations(calls[0])] == [(1, 8), (2, 2), (3, 2)]
    assert f'#3: score={calls[0]["return_value"][3][0]["score"]}' in log_text(calls[0])
    matches = [record for record in state["trace"] if record["event"] == "asset_matched" and "search_regions" in record]
    assert matches[0]["search_regions"] == calls[0]["inputs"]["regions"]
    assert len(matches[0]["templates"]) == 3
    index = json.loads((tmp_path / "asset-usage.json").read_text(encoding="utf-8"))
    assert index["items/other/two"]["search_regions"] == matches[0]["search_regions"]
    assert index["items/other/two"]["detections"][0]["logical_name"] == "items/other/two"


def test_group_in_regions_rejects_invalid_window_before_reading_assets(tmp_path):
    asset = entry(tmp_path, "items/test")
    library = AssetLibrary(tmp_path)
    library.path(asset["path"]).write_bytes(b"invalid template")
    window = {"x": 0, "y": 0, "width": 4, "height": 4}
    options = dict(run_id=1, observation=1, emit=lambda *_: None, _group=True)
    with pytest.raises(ValueError, match="inside the client area"):
        library.match("items", pixels(screenshot()), (12, 8), _regions=[window, {**window, "width": 20}], **options)
    with pytest.raises(ValueError, match="Asset hash mismatch"):
        library.match("items", pixels(screenshot()), (12, 8), _regions=[window, window], **options)


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
    from runtime_support import add_plan
    add_plan(candidate / "manifest.json")
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
    from runtime_support import add_plan
    add_plan(candidate / "manifest.json")
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
    from runtime_support import add_plan
    add_plan(candidate / "manifest.json")
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


def test_group_matching_uses_path_segments_and_global_nms(tmp_path):
    library = AssetLibrary(tmp_path)
    entry(tmp_path, "gifts/bleed")
    entry(tmp_path, "gifts/bleed/nested/gift")
    entry(tmp_path, "gifts/bleeding/gift")
    events = []
    found = library.match("gifts/bleed", pixels(screenshot()), (12, 8), run_id=3,
                          observation=7, emit=lambda _, event: events.append(event),
                          threshold=.999, _group=True)
    assert [hit["logical_name"] for hit in found] == ["gifts/bleed"] * 2
    assert [item["path"].rsplit("/", 1)[0] for item in events[0]["templates"]] == [
        "gifts/bleed", "gifts/bleed/nested/gift",
    ]


def test_formal_staged_crops_survive_frame_refresh_and_are_immediately_matchable(tmp_path):
    from runtime_support import add_plan

    first = template()
    second = np.flip(first, axis=0).copy()
    image = screenshot()
    image[5:7, 8:10] = second

    class ChangingWindow(Window):
        def capture(self, hwnd, width, height):
            self.image = np.zeros_like(image) if self.captures == 1 else image
            return super().capture(hwnd, width, height)

    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "step.py").write_text(
        '''"""校验暂存裁剪受正式动作保护，并保留点击前画面。"""
from lalc import step

@step
def execute(ctx) -> str:
    ctx.action("observe.capture_screen", save=False)
    assert ctx.action("observe.match_asset_group", group="gifts") == []
    left = {"x": 2, "y": 1, "width": 2, "height": 2}
    right = {"x": 8, "y": 5, "width": 2, "height": 2}
    one = ctx.action("observe.stage_asset_crop", region=left)
    two = ctx.action("observe.stage_asset_crop", region=right)
    unused = ctx.action("observe.stage_asset_crop", region=right)
    ctx.action("observe.discard_asset_crop", crop_id=unused)
    ctx.action("observe.stage_asset_crop", region=right)
    ctx.action("observe.capture_screen", save=False)
    ctx.action("observe.save_asset_crop", crop_id=two, asset="gifts/burn/second")
    ctx.action("observe.save_asset_crop", crop_id=one, asset="gifts/bleed/first", tags=["en"])
    ctx.action("observe.capture_screen", save=False)
    hits = ctx.action("observe.match_asset_group", group="gifts", threshold=.999)
    return ",".join(hit["logical_name"] for hit in hits)
''', encoding="utf-8",
    )
    manifest = candidate / "manifest.json"
    manifest.write_text(json.dumps({"schema_version": 2, "components": {
        "steps.find": {"source_path": "step.py"}}, "recovery_rules": {}}), encoding="utf-8")
    add_plan(manifest)
    manager = ManifestManager(tmp_path)
    published = manager.publish(manifest)
    assert published.ok, published.errors
    window = ChangingWindow()
    service = ApplicationService(tmp_path, manifest_manager=manager, window_platform=window)
    state = finish(service, service.start("steps.find", {}, manifest_id=published.loaded.manifest_id))
    assert state["result"]["status"] == "success", state["result"]
    assert state["result"]["output"] == "gifts/bleed/first,gifts/burn/second"
    assert window.captures == 3
    assert not (tmp_path / "evidence").exists()
    assert not service._staged_crops
    captured = [record for record in state["trace"] if record["event"] == "asset_created"]
    assert len(captured) == 2
    assert captured[0]["observation"] == captured[1]["observation"]
    for record, expected in zip(captured, (second, first), strict=True):
        assert np.array_equal(decode_image((tmp_path / "assets" / record["path"]).read_bytes()), expected)
    index = json.loads((tmp_path / "asset-usage.json").read_text(encoding="utf-8"))
    assert set(index) == {"gifts/bleed/first", "gifts/burn/second"}
    assert all(row["observation"] > captured[0]["observation"] for row in index.values())
