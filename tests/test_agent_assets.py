"""覆盖裁剪预览关联、辅助图隔离和移除归档的图片/标签一致性，不调用模型。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_agent_assets.py
"""

import base64
import json
from pathlib import Path

import numpy as np
import pytest

from lalc.recognition import client_image, decode_image
from lalc.runtime import sha256_bytes
from test_repair_tools import tools, invoke, snapshot


def preview(tools):
    return invoke(tools, "preview_crop", logical_name="ui/claim",
                  region={"x": 0, "y": 0, "width": 1, "height": 1}, tags=["en", "en"])


def test_preview_does_not_add_asset_and_save_uses_identical_pixels(tools):
    first = preview(tools)
    assert not tools.library.root.exists()
    assert first["details"]["matches"] and first["details"]["match_count"]
    assert len([part for part in first["content"] if part["type"] == "image"]) == 2
    crop_image = base64.b64decode(first["content"][-1]["data"])
    count = tools.platform.captures
    tools.platform.capture = lambda *args: pytest.fail("Saving preview must not capture again")
    saved = invoke(tools, "crop_asset", preview_id=first["details"]["preview_id"])["details"]
    assert tools.library.read({"path": saved["path"], "sha256": saved["sha256"]}) == crop_image
    assert saved["tags"] == ["en", "en"] and tools.platform.captures == count
    assert saved["source_screenshot"] == first["details"]["source_screenshot"]
    assert invoke(tools, "crop_asset", preview_id="unknown")["isError"]
    assert invoke(tools, "crop_asset", logical_name="ui/claim", region={})["isError"]


def test_grid_uses_40px_coordinates_and_never_modifies_original(tools):
    tools.platform.width, tools.platform.height = 100, 90
    pixels = bytes([10, 20, 30, 255]) * 100 * 90
    tools.platform.capture = lambda *args: pixels
    result = invoke(tools, "game_screenshot")
    images = [decode_image(base64.b64decode(part["data"])) for part in result["content"] if part["type"] == "image"]
    assert np.array_equal(images[0], client_image(pixels, (100, 90)))
    assert not np.array_equal(images[0], images[1])
    assert tuple(images[1][50, 40]) == (0, 255, 255)
    assert tuple(images[1][40, 50]) == (0, 255, 255)
    assert tuple(images[1][50, 50]) == (10, 20, 30)
    assert result["details"]["grid"]["spacing"] == 40


def test_remove_archives_raw_image_tags_and_fresh_screenshot_preserving_other_name(tools):
    saved = invoke(tools, "crop_asset", preview_id=preview(tools)["details"]["preview_id"])["details"]
    raw_asset = tools.library.read({"path": saved["path"], "sha256": saved["sha256"]})
    other = tools.library.path(f"other/name/{saved['sha256']}.png")
    other.parent.mkdir(parents=True)
    other.write_bytes(raw_asset)
    tools.library._set_tags("other/name", saved["sha256"], ["other"])
    tools.platform.capture = lambda *args: bytes([31, 41, 59, 255]) * 4
    removed = invoke(tools, "remove_asset", logical_name="ui/claim", sha=saved["sha256"], reason="误裁")["details"]
    archive = Path(removed["archive_path"])
    assert archive.parent.name == "agent_removed_asset"
    assert (archive / "asset.png").read_bytes() == raw_asset
    assert removed["tags"] == ["en", "en"] and removed["reason"] == "误裁"
    assert sha256_bytes((archive / "asset.png").read_bytes()) == saved["sha256"]
    assert np.array_equal(decode_image((archive / "screenshot.png").read_bytes()), np.full((2, 2, 3), [31, 41, 59], dtype=np.uint8))
    assert not tools.library.path(saved["path"]).exists()
    assert tools.library._tag_mapping("ui/claim") == {}
    assert other.read_bytes() == raw_asset and tools.library._tag_mapping("other/name") == {saved["sha256"]: ["other"]}
    assert json.loads((archive / "record.json").read_text())["state"] == "completed"
    assert tools.library.match("ui/claim", bytes([0, 0, 0, 255]) * 4, (2, 2), run_id=1, observation=1, emit=lambda *args: None) == []


@pytest.mark.parametrize("fault", ["capture", "archive_image", "prepare", "tags", "unlink", "complete", "cancel"])
def test_remove_failures_preserve_active_image_and_tags(tools, monkeypatch, fault):
    import lalc.assets as assets
    saved = invoke(tools, "crop_asset", preview_id=preview(tools)["details"]["preview_id"])["details"]
    before = snapshot(tools.library.root)
    original_write = assets.atomic_write_json
    original_open = Path.open
    original_unlink = Path.unlink
    def fail_write(path, value):
        if ((fault == "prepare" and path.name == "record.json" and value["state"] == "prepared")
                or (fault == "complete" and path.name == "record.json" and value["state"] == "completed")
                or (fault == "tags" and path.name == "asset-tag.json" and value == {})):
            raise OSError("injected failure")
        result = original_write(path, value)
        if fault == "cancel" and path.name == "record.json" and value["state"] == "prepared":
            tools.cancelled.set()
        return result
    def fail_open(path, *args, **kwargs):
        if fault == "archive_image" and path.name == "asset.png":
            raise OSError("archive unavailable")
        return original_open(path, *args, **kwargs)
    def fail_unlink(path, *args, **kwargs):
        if fault == "unlink" and path == tools.library.path(saved["path"]):
            raise OSError("active image locked")
        return original_unlink(path, *args, **kwargs)
    monkeypatch.setattr(assets, "atomic_write_json", fail_write)
    monkeypatch.setattr(Path, "open", fail_open)
    monkeypatch.setattr(Path, "unlink", fail_unlink)
    if fault == "capture":
        tools.platform.windows = []
    result = invoke(tools, "remove_asset", logical_name="ui/claim", sha=saved["sha256"], reason="测试失败")
    assert result["isError"]
    assert snapshot(tools.library.root) == before


def test_repeated_archive_ids_are_unique_and_invalid_hash_cannot_remove(tools):
    identity = preview(tools)["details"]["preview_id"]
    saved = invoke(tools, "crop_asset", preview_id=identity)["details"]
    image = tools.library.path(saved["path"])
    original = image.read_bytes()
    image.write_bytes(original + b"corrupted")
    count = tools.platform.captures
    failed = invoke(tools, "remove_asset", logical_name="ui/claim", sha=saved["sha256"], reason="错误图片")
    assert failed["isError"] and image.exists() and tools.platform.captures == count
    image.write_bytes(original)
    archives = []
    for _ in range(2):
        invoke(tools, "crop_asset", preview_id=identity)
        archives.append(invoke(tools, "remove_asset", logical_name="ui/claim", sha=saved["sha256"], reason="重复移除")["details"])
    assert archives[0]["archive_id"] != archives[1]["archive_id"]
    assert all(Path(item["archive_path"]).is_dir() for item in archives)


def test_remove_rejects_internal_symlink_to_other_logical_name(tools):
    saved = invoke(tools, "crop_asset", preview_id=preview(tools)["details"]["preview_id"])["details"]
    alias = tools.library.root / "alias"
    alias.symlink_to(tools.library.path("ui/claim"), target_is_directory=True)
    before = snapshot(tools.library.root)
    result = invoke(tools, "remove_asset", logical_name="alias", sha=saved["sha256"], reason="越名移除")
    assert result["isError"] and snapshot(tools.library.root) == before
