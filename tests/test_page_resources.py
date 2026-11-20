"""覆盖页面 JSON 共享、安全写入、素材目录候选读取和改名。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_page_resources.py
"""

import json
from hashlib import sha256
from pathlib import Path

import pytest

from lalc.application import ApplicationService
from lalc.page_drafts import MemorySettings
from lalc.process_lock import ProcessLock
from lalc.user_pages import PageContext, UserSettings
from runtime_support import add_plan


def test_plan_trial_and_page_share_rotation(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    path = candidate / "manifest.json"
    path.write_text(json.dumps({"schema_version": 2, "components": {}, "recovery_rules": {}}))
    add_plan(path, """    rotation = ctx.action("page_resource.read_json", page_id="mirror.settings", name="rotation")
    teams = [2, 5, 8]
    team = rotation["next_team"] if rotation else teams[0]
    next_team = teams[(teams.index(team) + 1) % len(teams)]
    ctx.action("page_resource.write_json", page_id="mirror.settings", name="rotation",
               value={"next_team": next_team, "previous": {"team": team, "settled": True}})
""")
    service = ApplicationService(tmp_path)
    published = service.manifest_manager.publish(path)
    assert published.ok, published.errors
    identity = published.loaded.manifest_id
    store = UserSettings(tmp_path)
    page = PageContext(store, "mirror.settings")
    page.save({"mirror_teams": [2, 5, 8]})

    def run(*, trial=False):
        run_id = service.start_plan(manifest_id=identity, _developer_trial=trial)
        state = service.wait_for(lambda state: state["run_id"] == run_id and state["phase"] == "finished")
        assert state["result"]["status"] == "completed", state["result"]
        return [event["return_value"] for event in state["trace"]
                if event["event"] == "trusted_action_returned"
                and event["logical_name"] == "page_resource.read_json"]

    assert run() == [None]
    assert page.read_resource_json("rotation")["next_team"] == 5
    with service.activity("Agent"):
        assert run(trial=True) == [{"next_team": 5, "previous": {"team": 2, "settled": True}}]
    assert page.read_resource_json("rotation")["next_team"] == 8
    page.save({"mirror_teams": [2, 5, 8]})
    assert run()[0]["next_team"] == 8
    assert page.load() == {"mirror_teams": [2, 5, 8]}
    assert page.read_resource_json("rotation")["next_team"] == 2

    preview = PageContext(MemorySettings(store.value), page.page_id)
    assert preview.read_resource_json("rotation") is None
    preview.write_resource_json("rotation", {"next_team": 40})
    assert page.read_resource_json("rotation")["next_team"] == 2


def test_failed_page_resource_write_keeps_previous_json(tmp_path, monkeypatch):
    page = PageContext(UserSettings(tmp_path), "mirror.settings")
    page.write_resource_json("rotation", {"next_team": 5})
    with pytest.raises(ValueError):
        page.write_resource_json("../rotation", {})
    with pytest.raises(ValueError):
        page.write_resource_json("rotation", {"next_team": float("nan")})

    def fail_replace(self, target):
        raise OSError("replace failed")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError, match="replace failed"):
        page.write_resource_json("rotation", {"next_team": 8})
    assert page.read_resource_json("rotation") == {"next_team": 5}
    assert len(list((tmp_path / "page-resources").rglob("*.*"))) == 1


def test_page_asset_rename_commit_and_rollback(tmp_path, monkeypatch):
    page = PageContext(UserSettings(tmp_path), "mirror.settings")
    old = "mirror/gift/burn/ashes_s_to_ashes"
    new = "mirror/gift/burn/ashes_to_ashes"
    image = b"saved template"
    digest = sha256(image).hexdigest()
    source = tmp_path / "assets" / old
    source.mkdir(parents=True)
    (source / f"{digest}.png").write_bytes(image)
    (source / "asset-tag.json").write_text(json.dumps({digest: ["en"]}))
    previous = {"id": {"logical_name": old, "sha256": digest}}
    updated = {"id": {"logical_name": new, "sha256": digest}}
    page.write_resource_json("catalog", previous)
    assert page.read_asset_image(old, digest) == image

    preview = PageContext(MemorySettings(page.store.value), page.page_id)
    assert preview.read_asset_image(old, digest) is None
    preview.commit_resource_json("catalog", None, updated, asset_rename=(old, new))
    assert source.is_dir() and page.read_resource_json("catalog") == previous
    with pytest.raises(ValueError, match="刷新"):
        page.commit_resource_json("catalog", None, updated, asset_rename=(old, new))
    with ProcessLock("game"), pytest.raises(OSError):
        page.commit_resource_json("catalog", previous, updated, asset_rename=(old, new))
    assert source.is_dir()

    target = tmp_path / "assets" / new
    target.mkdir()
    with pytest.raises(FileExistsError):
        page.commit_resource_json("catalog", previous, updated, asset_rename=(old, new))
    target.rmdir()

    def fail_replace(self, target):
        raise OSError("replace failed")

    with monkeypatch.context() as patch:
        patch.setattr(Path, "replace", fail_replace)
        with pytest.raises(OSError, match="replace failed"):
            page.commit_resource_json("catalog", previous, updated, asset_rename=(old, new))
    assert page.read_resource_json("catalog") == previous
    assert page.read_asset_image(old, digest) == image
    assert not target.exists()

    page.commit_resource_json("catalog", previous, updated, asset_rename=(old, new))
    assert page.read_resource_json("catalog") == updated
    assert page.read_asset_image(old, digest) is None
    assert page.read_asset_image(new, digest) == image
    assert json.loads((target / "asset-tag.json").read_bytes()) == {digest: ["en"]}


def test_page_lists_only_direct_hash_named_asset_images(tmp_path):
    page = PageContext(UserSettings(tmp_path), "mirror.settings")
    name = "mirror/gift/burn/ashes_to_ashes"
    directory = tmp_path / "assets" / name
    assert page.list_asset_images(name) == []
    nested = directory / "other"
    nested.mkdir(parents=True)
    first, second, child = (value * 64 for value in "abc")
    (directory / f"{second}.png").write_bytes(b"second")
    (directory / f"{first}.png").write_bytes(b"first")
    (nested / f"{child}.png").write_bytes(b"child")
    (directory / "notes.png").write_bytes(b"not a candidate")
    (directory / f"{'d' * 64}.png").symlink_to(nested / f"{child}.png")
    assert page.list_asset_images(name) == [first, second]
    (directory.parent / "alias").symlink_to(directory, target_is_directory=True)
    assert page.list_asset_image_groups("mirror/gift") == {
        name: [first, second],
        f"{name}/other": [child],
    }
    assert page.list_asset_image_groups("mirror/missing") == {}
    with pytest.raises(ValueError, match="aliases"):
        page.list_asset_images("mirror/gift/burn/alias")
    with pytest.raises(ValueError, match="aliases"):
        page.list_asset_image_groups("mirror/gift/burn/alias")
    with pytest.raises(ValueError, match="semantic names"):
        page.list_asset_images("../outside")
    preview = PageContext(MemorySettings(page.store.value), page.page_id)
    assert preview.list_asset_images(name) == []
    assert preview.list_asset_image_groups("mirror/gift") == {}
