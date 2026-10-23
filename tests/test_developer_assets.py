"""覆盖独立素材裁剪、离线标签合并、来源与哈希验证，不依赖 Candidate。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_developer_assets.py
"""

import json
from pathlib import Path

import pytest

import lalc.__main__ as cli
from lalc.application import ApplicationService
from lalc.assets import AssetLibrary
from test_assets import pixels, screenshot, Window


def prepare(root):
    library = AssetLibrary(root / "data")
    crop = library.save_crop("ui/claim", pixels(screenshot()), (12, 8),
                             {"x":2,"y":1,"width":2,"height":2}, run_id=7, observation=1)
    return library, crop


def snapshot(root):
    return {str(p.relative_to(root)):p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_cli_tags_merge_offline_without_candidate_or_publish(tmp_path, monkeypatch, capsys):
    library, crop = prepare(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "default_data_root", lambda: library.data_root)
    monkeypatch.setattr("lalc.application.WindowsWindowPlatform", lambda **_: pytest.fail("must stay offline"))
    cli.configure_logging(library.data_root)
    before = snapshot(tmp_path)
    command = ["add-asset", "ui/claim", "--image", crop["image_path"]]
    assert cli.main([*command, "--tags", "zh", "event", "zh"]) == 0
    assert json.loads(capsys.readouterr().out)["tags"] == ["zh", "event"]
    after = snapshot(tmp_path)
    assert {p for p in after if after[p] != before.get(p)} == {"data/assets/ui/claim/asset-tag.json"}
    assert cli.main([*command, "--tags", "event", "dark"]) == 0
    assert json.loads(capsys.readouterr().out)["tags"] == ["zh", "event", "dark"]
    before = snapshot(tmp_path)
    assert cli.main(command) == 0
    assert json.loads(capsys.readouterr().out)["unchanged"]
    assert snapshot(tmp_path) == before
    assert not (tmp_path / "candidate").exists()
    assert not (library.data_root / "manifests").exists()


def test_missing_tag_record_is_created_as_empty_list(tmp_path):
    library, crop = prepare(tmp_path)
    tag_file = library.path("ui/claim/asset-tag.json")
    tag_file.unlink()
    added = library.add_tags("ui/claim", Path(crop["image_path"]))
    assert added["tags"] == []
    assert json.loads(tag_file.read_text(encoding="utf-8")) == {crop["sha256"]:[]}


def test_existing_duplicate_tags_are_deduplicated_on_configuration(tmp_path):
    library, crop = prepare(tmp_path)
    path = library.path("ui/claim/asset-tag.json")
    path.write_text(json.dumps({crop["sha256"]:["zh", "zh", "event"]}), encoding="utf-8")
    result = library.add_tags("ui/claim", Path(crop["image_path"]), ["event", "dark"])
    assert result["tags"] == ["zh", "event", "dark"]
    assert json.loads(path.read_text(encoding="utf-8"))[crop["sha256"]] == result["tags"]


@pytest.mark.parametrize("problem", ["external", "no_source", "hash", "name"])
def test_invalid_crop_reference_writes_nothing(tmp_path, problem):
    library, crop = prepare(tmp_path)
    image = Path(crop["image_path"])
    name = "ui/claim"
    if problem == "external":
        other = tmp_path / "external.png"
        other.write_bytes(image.read_bytes())
        image = other
    elif problem == "no_source":
        (library.data_root / "asset-provenance" / f"{crop['provenance_id']}.json").unlink()
    elif problem == "hash":
        image.write_bytes(b"changed")
    elif problem == "name":
        name = "ui/other"
    before = snapshot(tmp_path)
    with pytest.raises(ValueError):
        library.add_tags(name, image, ["event"])
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("tags", ["zh", [1], [""]])
def test_invalid_tags_do_not_write(tmp_path, tags):
    library, crop = prepare(tmp_path)
    before = snapshot(tmp_path)
    with pytest.raises(ValueError):
        library.add_tags("ui/claim", Path(crop["image_path"]), tags)
    assert snapshot(tmp_path) == before


def test_developer_crop_reuses_image_and_keeps_provenance(tmp_path):
    service = ApplicationService(tmp_path, window_platform=Window())
    first = service.crop_developer_asset("ui/claim", {"x":2,"y":1,"width":2,"height":2}, ["zh"])
    second = service.crop_developer_asset("ui/claim", {"x":2,"y":1,"width":2,"height":2}, ["dark"])
    assert first["path"] == second["path"] == f"ui/claim/{first['sha256']}.png"
    assert second["tags"] == ["zh", "dark"]
    assert len(list(service.asset_library.path("ui/claim").glob("*.png"))) == 1
    assert len(list((tmp_path / "asset-provenance").glob("*.json"))) == 2
    assert not (tmp_path / "candidate").exists()


def test_cli_crop_tags_do_not_require_candidate(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "default_data_root", lambda: tmp_path / "data")
    monkeypatch.setattr("lalc.application.WindowsWindowPlatform", lambda **_: Window())
    assert cli.main(["crop-asset", "ui/claim", "--region", '{"x":2,"y":1,"width":2,"height":2}', "--tags", "zh", "dark"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["tags"] == ["zh", "dark"]
    assert Path(result["image_path"]).name == f"{result['sha256']}.png"
    assert not (tmp_path / "candidate").exists()


def test_cli_missing_crop_source_is_an_ordinary_error(tmp_path, monkeypatch, capsys):
    library, crop = prepare(tmp_path)
    (library.data_root / "asset-provenance" / f"{crop['provenance_id']}.json").unlink()
    monkeypatch.setattr(cli, "default_data_root", lambda: library.data_root)
    assert cli.main(["add-asset", "ui/claim", "--image", crop["image_path"]]) == 1
    error = capsys.readouterr().err
    assert "No crop provenance matches" in error and "Traceback" in error
    assert cli.FATAL_MESSAGE not in error
