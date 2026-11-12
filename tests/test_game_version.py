"""覆盖 Steam 多库发现、缓存失效、独立 ID 失败及受限 Unity 布局，不调用模型。

项目根目录运行：QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_game_version.py
"""

import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from lalc import game_version as versions


def steam_install(root, library=None, build="26156805"):
    root.mkdir(parents=True, exist_ok=True)
    (root / "steam.exe").touch()
    (root / "steamapps").mkdir(exist_ok=True)
    library = library or root
    game = library / "steamapps/common/Limbus Company"
    game.mkdir(parents=True, exist_ok=True)
    escaped = str(library).replace("\\", "\\\\")
    (root / "steamapps/libraryfolders.vdf").write_text('"libraryfolders" {"0" {"path" "' + escaped + '"}}', encoding="utf-8")
    manifest = library / "steamapps/appmanifest_1973530.acf"
    manifest.write_text('"AppState" {"appid" "1973530" "installdir" "Limbus Company" "buildid" "' + build + '"}', encoding="utf-8")
    return game, manifest


def windows(monkeypatch, roots):
    monkeypatch.setattr(versions.sys, "platform", "win32")
    monkeypatch.setattr(versions, "discover_steam_roots", lambda: roots)


def test_vdf_nested_comments_escapes_and_rejects_truncation():
    value = versions.parse_vdf('// header\n"libraryfolders" { "0" { "path" "D:\\\\Steam" } }')
    assert value["libraryfolders"]["0"]["path"] == r"D:\Steam"
    for invalid in ('"a" {', '"a" "b" garbage', '"a" "b" "A" "c"', '}'):
        with pytest.raises(ValueError):
            versions.parse_vdf(invalid)


def test_multilibrary_and_partial_failure_still_cache_client(tmp_path, monkeypatch):
    root = tmp_path / "Steam"
    game, manifest = steam_install(root, tmp_path / "Library")
    windows(monkeypatch, [root, root])
    monkeypatch.setattr(versions, "read_game_version", lambda _: (_ for _ in ()).throw(ImportError("UnityPy missing")))
    observation = versions.observe_game_version(tmp_path / "data")
    assert observation["steam_build_id"] == "26156805" and observation["game_version"] is None
    assert observation["errors"][0]["field"] == "game_version"
    assert versions.load_steam_root(tmp_path / "data") == str(root.resolve())
    assert versions.installation(root)[1:] == (game.resolve(), manifest)
    with pytest.raises(ValueError, match="steam.exe"):
        versions.installation(tmp_path / "Library")


@pytest.mark.parametrize("build", ["invalid", "0", "9" * 5000])
def test_build_failure_does_not_discard_game_version(tmp_path, monkeypatch, build):
    root = tmp_path / "Steam"
    steam_install(root, build=build)
    windows(monkeypatch, [root])
    monkeypatch.setattr(versions, "read_game_version", lambda _: "1.118.0")
    observation = versions.observe_game_version(tmp_path / "data")
    assert observation["game_version"] == "1.118.0" and observation["steam_build_id"] is None
    assert observation["errors"][0]["field"] == "steam_build_id"


def test_cached_client_preferred_and_invalid_cache_rediscovered(tmp_path, monkeypatch):
    first, second = tmp_path / "Steam1", tmp_path / "Steam2"
    steam_install(first)
    steam_install(second, build="42")
    data = tmp_path / "data"
    data.mkdir()
    (data / versions.SETTINGS).write_text(json.dumps({"steam_root": str(first)}), encoding="utf-8")
    windows(monkeypatch, [first, second])
    monkeypatch.setattr(versions, "read_game_version", lambda _: "1.118.0")
    assert versions.observe_game_version(data)["steam_build_id"] == "26156805"
    (first / "steam.exe").unlink()
    assert versions.observe_game_version(data)["steam_build_id"] == "42"
    assert versions.load_steam_root(data) == str(second)


def test_ambiguity_and_nonwindows_are_unknown_without_writing_cache(tmp_path, monkeypatch):
    first, second = tmp_path / "Steam1", tmp_path / "Steam2"
    steam_install(first)
    steam_install(second)
    windows(monkeypatch, [first, second])
    observation = versions.observe_game_version(tmp_path / "data")
    assert observation["game_version"] is observation["steam_build_id"] is None
    assert "ambiguous" in observation["errors"][0]["message"]
    assert not (tmp_path / "data" / versions.SETTINGS).exists()
    monkeypatch.setattr(versions.sys, "platform", "darwin")
    monkeypatch.setattr(versions, "discover_steam_roots", lambda: pytest.fail("Unexpected disk discovery"))
    assert versions.observe_game_version(tmp_path)["errors"][0]["field"] == "installation"


def test_bad_manual_setting_preserves_previous_and_manifest_escape_rejected(tmp_path, monkeypatch):
    root = tmp_path / "Steam"
    _, manifest = steam_install(root)
    monkeypatch.setattr(versions, "read_game_version", lambda _: "1.118.0")
    data = tmp_path / "data"
    versions.save_steam_root(data, root)
    previous = (data / versions.SETTINGS).read_bytes()
    with pytest.raises((OSError, ValueError)):
        versions.save_steam_root(data, tmp_path / "missing")
    assert (data / versions.SETTINGS).read_bytes() == previous
    manifest.write_text('"AppState" {"appid" "1973530" "installdir" "..\\\\outside"}', encoding="utf-8")
    with pytest.raises(ValueError, match="directory"):
        versions.installation(root)


@pytest.mark.parametrize("unread,engine,layout,accepted", [(0, "future", "other", True),
    (4, "6000.3.12f1", "known", True), (4, "6000.3.13f1", "known", False),
    (4, "6000.3.12f1", "other", False), (8, "6000.3.12f1", "known", False)])
def test_unity_compatibility_exception_is_bound_to_validated_layout(monkeypatch, unread, engine, layout, accepted):
    helper = SimpleNamespace(read_typetree_boost="original")
    obj = SimpleNamespace(type=SimpleNamespace(name="PlayerSettings"), byte_start=100, byte_size=968,
                          reader=SimpleNamespace(Position=1068 - unread),
                          assets_file=SimpleNamespace(unity_version=engine, header=SimpleNamespace(version=22)),
                          dump_typetree_structure=lambda: layout,
                          read_typetree=lambda **_: {"companyName": "ProjectMoon", "productName": "LimbusCompany", "bundleVersion": "1.118.0"})
    monkeypatch.setitem(sys.modules, "UnityPy", SimpleNamespace(__version__="1.25.4", load=lambda _: SimpleNamespace(objects=[obj])))
    monkeypatch.setitem(sys.modules, "UnityPy.helpers", SimpleNamespace(TypeTreeHelper=helper))
    monkeypatch.setattr(versions, "_KNOWN_LAYOUT", hashlib.sha256(b"known").hexdigest())
    if accepted:
        assert versions.read_game_version(Path("test")) == "1.118.0"
    else:
        with pytest.raises(ValueError, match="layout"):
            versions.read_game_version(Path("test"))
    assert helper.read_typetree_boost == "original"
