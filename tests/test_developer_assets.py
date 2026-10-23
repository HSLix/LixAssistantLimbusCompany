"""覆盖已有裁剪的离线登记、重名确认、来源校验和 Candidate 库文件名。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_developer_assets.py
"""

import json
from pathlib import Path

import pytest

import lalc.__main__ as cli
from lalc.application import ApplicationService
from lalc.assets import AssetLibrary
from lalc.manifest import ManifestManager
from test_assets import pixels, screenshot


def prepare(root: Path):
    """创建真实裁剪与空工作台，登记阶段不再接触窗口。"""
    manager = ManifestManager(root / "data")
    candidate = root / "candidate"
    assert not manager.initialize_candidate(candidate)
    crop = AssetLibrary(manager.data_root).save_crop(
        "ui/claim", "zh", pixels(screenshot()), (12, 8),
        {"x": 2, "y": 1, "width": 2, "height": 2}, run_id=7, observation=1,
    )
    service = ApplicationService(manager.data_root, manifest_manager=manager, game_language="zh")
    return manager, candidate, crop, service


def snapshot(root: Path):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_cli_registers_existing_crop_offline_then_publishes(tmp_path, monkeypatch, capsys):
    manager, candidate, crop, _ = prepare(tmp_path)
    first = manager.publish(candidate / "manifest.json").loaded
    assert manager.set_default(first.manifest_id).ok
    old_library = (manager.asset_libraries_dir / f"{first.manifest_id}.json").read_bytes()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "default_data_root", lambda: manager.data_root)
    monkeypatch.setattr("lalc.application.WindowsWindowPlatform", lambda **_: pytest.fail("must stay offline"))
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("new entry needs no confirmation"))
    cli.configure_logging(manager.data_root)
    before = snapshot(tmp_path)
    command = ["add-asset", "ui/claim", "--language", "zh", "--image", crop["image_path"]]
    assert cli.main(command) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["sha256"] == crop["sha256"]
    after = snapshot(tmp_path)
    assert {p for p in after if after[p] != before.get(p)} == {"candidate/asset-library.json"}
    assert cli.main(command) == 0
    assert json.loads(capsys.readouterr().out)["unchanged"]
    assert snapshot(tmp_path) == after
    second = manager.publish(candidate / "manifest.json").loaded
    assert second.manifest_id != first.manifest_id
    assert second.assets["ui/claim"]["zh"]["sha256"] == crop["sha256"]
    assert (manager.asset_libraries_dir / f"{first.manifest_id}.json").read_bytes() == old_library
    assert manager.load(first.manifest_id).loaded.assets == {}
    assert manager.default_manifest_id() == first.manifest_id


@pytest.mark.parametrize("answer", ["n", "", "eof", "cancel", "y"])
def test_cli_crop_registration_replacement_is_explicit(tmp_path, monkeypatch, capsys, answer):
    manager, candidate, crop, service = prepare(tmp_path)
    assert service.add_candidate_asset(candidate, "ui/claim", Path(crop["image_path"]), lambda _: True)
    image = screenshot()
    image[1:3, 2:4] = 255
    replacement = service.asset_library.save_crop(
        "ui/claim", "zh", pixels(image), (12, 8),
        {"x": 2, "y": 1, "width": 2, "height": 2}, run_id=7, observation=2,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "default_data_root", lambda: manager.data_root)
    def respond(prompt):
        assert "Replace Candidate mapping?" in prompt
        if answer == "eof":
            raise EOFError
        if answer == "cancel":
            raise KeyboardInterrupt
        return answer
    monkeypatch.setattr("builtins.input", respond)
    cli.configure_logging(manager.data_root)
    before = snapshot(tmp_path)
    assert cli.main(["add-asset", "ui/claim", "--language", "zh", "--image", replacement["image_path"]]) == (0 if answer == "y" else 1)
    capsys.readouterr()
    after = snapshot(tmp_path)
    if answer != "y":
        assert after == before
    else:
        assert {p for p in after if after[p] != before.get(p)} == {"candidate/asset-library.json"}
        assert json.loads((candidate / "asset-library.json").read_text(encoding="utf-8"))["ui/claim"]["zh"]["sha256"] == replacement["sha256"]


@pytest.mark.parametrize("problem", ["external", "no_source", "hash", "name", "language", "decode"])
def test_registration_rejects_non_crop_or_changed_content_without_writes(tmp_path, problem):
    manager, candidate, crop, service = prepare(tmp_path)
    image = Path(crop["image_path"])
    name = "ui/claim"
    if problem == "external":
        other = tmp_path / "external.png"
        other.write_bytes(image.read_bytes())
        image = other
    elif problem == "no_source":
        (manager.data_root / "asset-provenance" / f"{crop['provenance_id']}.json").unlink()
    elif problem == "hash":
        image.write_bytes(b"changed")
    elif problem == "name":
        name = "ui/other"
    elif problem == "language":
        service.game_language = "en"
    elif problem == "decode":
        from lalc.runtime import sha256_bytes
        image.write_bytes(b"not a PNG")
        source = manager.data_root / "asset-provenance" / f"{crop['provenance_id']}.json"
        record = json.loads(source.read_text(encoding="utf-8"))
        record["sha256"] = sha256_bytes(image.read_bytes())
        source.write_text(json.dumps(record), encoding="utf-8")
    before = snapshot(tmp_path)
    with pytest.raises(ValueError):
        service.add_candidate_asset(candidate, name, image, lambda _: pytest.fail("invalid input must not prompt"))
    assert snapshot(tmp_path) == before


def test_new_library_name_is_required_without_legacy_fallback(tmp_path):
    manager, candidate, _, _ = prepare(tmp_path)
    (candidate / "asset-library.json").rename(candidate / "assets.json")
    before = snapshot(tmp_path)
    assert manager.validate(candidate / "manifest.json")
    assert not manager.publish(candidate / "manifest.json").ok
    assert snapshot(tmp_path) == before


def test_registration_keeps_same_name_in_other_language(tmp_path):
    _, candidate, first, service = prepare(tmp_path)
    assert service.add_candidate_asset(candidate, "ui/claim", Path(first["image_path"]), lambda _: True)
    other = service.asset_library.save_crop(
        "ui/claim", "en", pixels(screenshot()), (12, 8),
        {"x": 2, "y": 1, "width": 2, "height": 2}, run_id=7, observation=2,
    )
    service.game_language = "en"
    assert service.add_candidate_asset(candidate, "ui/claim", Path(other["image_path"]), lambda _: pytest.fail("different language"))
    mapping = json.loads((candidate / "asset-library.json").read_text(encoding="utf-8"))
    assert mapping["ui/claim"]["zh"]["sha256"] == first["sha256"]
    assert mapping["ui/claim"]["en"]["path"] == other["path"]


def test_cli_missing_crop_source_is_an_ordinary_error(tmp_path, monkeypatch, capsys):
    manager, _, crop, _ = prepare(tmp_path)
    (manager.data_root / "asset-provenance" / f"{crop['provenance_id']}.json").unlink()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "default_data_root", lambda: manager.data_root)
    assert cli.main(["add-asset", "ui/claim", "--language", "zh", "--image", crop["image_path"]]) == 1
    error = capsys.readouterr().err
    assert "No crop provenance matches" in error
    assert "Traceback" in error
    assert cli.FATAL_MESSAGE not in error
