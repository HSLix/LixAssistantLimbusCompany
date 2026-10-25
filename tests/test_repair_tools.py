"""覆盖修复工具的只读权限、多图原子返回、现场聚焦及裁剪的旧标签保护。

在项目根目录运行：
UV_CACHE_DIR=.generated/uv-cache uv run --frozen --extra automation pytest -q tests/test_repair_tools.py
"""

import base64
import json
from pathlib import Path

import pytest

from lalc.actions import application_actions
from lalc.agent_repair import RepairLog
from lalc.repair_tools import RepairTools
from test_assets import entry
from test_focused_observation import FakeWindowPlatform


def invoke(tools, name, **arguments):
    return json.loads(Path(tools.call(name, arguments)).read_text())


def crop(tools, **arguments):
    preview = invoke(tools, "preview_crop", **arguments)
    if preview.get("isError"):
        return preview
    return invoke(tools, "crop_asset", preview_id=preview["details"]["preview_id"])


def snapshot(root):
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}


@pytest.fixture
def tools(tmp_path):
    return RepairTools(tmp_path / "data", RepairLog(tmp_path / "data", "test-secret"),
                       platform=FakeWindowPlatform())


def test_readonly_tree_directory_images_and_actual_action_contracts(tools):
    first = entry(tools.library.data_root, "ui/claim")
    second = entry(tools.library.data_root, "other/button")
    tags = tools.library.path("ui/claim/asset-tag.json")
    tags.write_text(json.dumps({first["sha256"]: ["zh", "event", "zh"]}))
    before = snapshot(tools.library.root)
    assert "  claim/" in invoke(tools, "asset_tree")["details"]["tree"]
    directory = invoke(tools, "asset_directory", logical_name="ui/claim")["details"]
    assert directory["files"] == sorted([first["sha256"] + ".png", "asset-tag.json"])
    assert directory["tag_content"] == tags.read_text() and not directory["tags_missing"]
    missing = invoke(tools, "asset_directory", logical_name="other/button")["details"]
    assert missing["tags_missing"] and missing["tag_content"] is None
    images = [{"logical_name": name, "sha256": item["sha256"]}
              for name, item in [("ui/claim", first), ("other/button", second)]]
    result = invoke(tools, "asset_images", images=images)
    assert [part["type"] for part in result["content"]] == ["text", "image", "text", "image"]
    for index, item in enumerate([first, second]):
        assert base64.b64decode(result["content"][index * 2 + 1]["data"]) == tools.library.read(item)
        assert result["details"]["images"][index]["sha256"] == item["sha256"]
    actions = invoke(tools, "action_contracts")["details"]["actions"]
    assert [item["logical_name"] for item in actions] == list(application_actions())
    assert all("ctx" in item["signature"] and "->" in item["signature"] and item["docstring"] for item in actions)
    assert "def click" not in json.dumps(actions)
    assert snapshot(tools.library.root) == before


@pytest.mark.parametrize("problem", ["missing", "prefix", "hash", "decode", "escape", "link"])
def test_image_batch_failure_returns_no_images_and_writes_no_asset(tools, tmp_path, problem):
    first = entry(tools.library.data_root, "ui/claim")
    bad = {"logical_name": "ui/claim", "sha256": first["sha256"]}
    if problem == "missing":
        bad["sha256"] = "0" * 64
    elif problem == "prefix":
        bad["sha256"] = first["sha256"][:8]
    elif problem == "hash":
        bad["logical_name"] = "bad/hash"
        path = tools.library.path(f"bad/hash/{first['sha256']}.png")
        path.parent.mkdir(parents=True)
        path.write_bytes(b"bad content")
    elif problem == "decode":
        from lalc.runtime import sha256_bytes
        bad["sha256"] = sha256_bytes(b"not an image")
        tools.library.path(f"ui/claim/{bad['sha256']}.png").write_bytes(b"not an image")
    elif problem == "escape":
        bad["logical_name"] = "../outside"
    else:
        outside = tmp_path / "outside"
        outside.mkdir()
        (tools.library.root / "link").symlink_to(outside, target_is_directory=True)
        bad["logical_name"] = "link"
    before = snapshot(tools.library.root)
    result = invoke(tools, "asset_images", images=[{"logical_name": "ui/claim", "sha256": first["sha256"]}, bad])
    assert result["isError"] and [part["type"] for part in result["content"]] == ["text"]
    assert bad["logical_name"] in result["details"]["error"] and bad["sha256"] in result["details"]["error"]
    assert not list(tools.log.path.glob("*-image-*.png"))
    assert snapshot(tools.library.root) == before


def test_every_capture_refocuses_and_crop_preserves_old_tags_and_source(tools):
    first = invoke(tools, "game_screenshot")
    assert first["details"]["width"] == first["details"]["height"] == 2
    tools.platform.foreground = False
    tools.platform.minimized = True
    # 固定真实像素，单独核对重复裁剪；截图次数依然真实递增。
    capture = tools.platform.capture
    def fixed_capture(*args):
        capture(*args)
        return bytes([10, 20, 30, 255]) * 4
    tools.platform.capture = fixed_capture
    args = {"logical_name": "ui/new", "region": {"x": 0, "y": 0, "width": 1, "height": 1}}
    added = crop(tools, **args, tags=["keep", "keep"])["details"]
    before = snapshot(tools.library.root)
    reused = crop(tools, **args, tags=["replace"])["details"]
    assert not added["existed"] and reused["existed"]
    assert reused["tags"] == ["keep", "keep"] and reused["sha256"] == added["sha256"]
    assert snapshot(tools.library.root) == before
    assert tools.platform.focus_calls == tools.platform.captures == 3
    source = json.loads((tools.library.data_root / "asset-provenance" / f"{reused['provenance_id']}.json").read_text())
    assert Path(source["source_screenshot"]).is_file()
    assert source["interaction_id"] == tools.log.path.name
    other = crop(tools, logical_name="ui/new", region={"x": 0, "y": 0, "width": 2, "height": 1})["details"]
    tags = json.loads(tools.library.path("ui/new/asset-tag.json").read_text())
    assert tags == {added["sha256"]: ["keep", "keep"], other["sha256"]: []}
    assert invoke(tools, "asset_images", images=[{"logical_name": "ui/new", "sha256": other["sha256"]}])["details"]["images"]


def test_reusing_image_without_tag_file_does_not_create_metadata(tools):
    crop(tools, logical_name="ui/new", region={"x": 0, "y": 0, "width": 1, "height": 1})
    tags = tools.library.path("ui/new/asset-tag.json")
    tags.unlink()
    tools.platform.captures = 0
    result = crop(tools, logical_name="ui/new", region={"x": 0, "y": 0, "width": 1, "height": 1}, tags=["ignored"])
    assert result["details"]["existed"] and result["details"]["tags"] == []
    assert not tags.exists()


def test_crop_preserves_tag_entry_even_if_its_image_is_missing(tools):
    args = {"logical_name": "ui/new", "region": {"x": 0, "y": 0, "width": 1, "height": 1}}
    first = crop(tools, **args, tags=["keep"])["details"]
    Path(first["image_path"]).unlink()
    tools.platform.captures = 0
    second = crop(tools, **args, tags=["replace"])["details"]
    assert not second["existed"] and second["tags"] == ["keep"]


def test_failed_capture_never_returns_previous_image_and_can_be_retried(tools):
    invoke(tools, "game_screenshot")
    tools.platform.blur_during_capture = True
    failed = invoke(tools, "game_screenshot")
    assert failed["isError"] and all(part["type"] != "image" for part in failed["content"])
    tools.platform.blur_during_capture = False
    assert not invoke(tools, "game_screenshot").get("isError")
    assert tools.platform.focus_calls == 3


@pytest.mark.parametrize("windows", [[], [42, 43]])
def test_live_tools_reject_nonunique_window_without_capturing(tools, windows):
    tools.platform.windows = windows
    assert invoke(tools, "game_screenshot")["isError"]
    assert tools.platform.captures == tools.platform.focus_calls == 0


def test_crop_rejects_invalid_region_and_cancel_retains_new_asset(tools):
    bad = crop(tools, logical_name="ui/new", region={"x": 0, "y": 0, "width": 3, "height": 1})
    assert bad["isError"] and not tools.library.root.exists()
    crop(tools, logical_name="ui/new", region={"x": 0, "y": 0, "width": 1, "height": 1})
    before = snapshot(tools.library.root)
    tools.cancelled.set()
    with pytest.raises(RuntimeError, match="cancelled"):
        invoke(tools, "game_screenshot")
    assert snapshot(tools.library.root) == before
