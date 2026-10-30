"""覆盖双 ZIP 内容、归档边界及成品草稿路径；不构建 Windows 或调用 pi。

项目根目录运行：QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_windows_packaging.py
"""

import importlib.util
import json
from pathlib import Path
import sys
import zipfile

import pytest

from lalc import application
import lalc.__main__ as cli


spec = importlib.util.spec_from_file_location("windows_build", Path(__file__).parents[1] / "scripts/build_windows.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


@pytest.fixture
def archive(tmp_path, monkeypatch):
    path = tmp_path / "pi.zip"
    with zipfile.ZipFile(path, "w") as bundle:
        bundle.writestr("pi.exe", b"test-only-binary")
        bundle.writestr("package.json", json.dumps({"version": "1.4.0"}))
        bundle.writestr("native/win32/prebuilds/win32-x64/helper.dll", b"test-runtime")
    monkeypatch.setattr(build, "PI_SHA256", build.digest(path))
    return path


def test_two_archives_share_application_and_keep_complete_pi_runtime(tmp_path, archive):
    app = tmp_path / "application"
    for name in ("LALC.exe", "LALC-console.exe", "_internal/lalc/pi_probe.ts",
                 "_internal/lalc/translations/lalc_zh_CN.qm", "_internal/PySide6/translations/qtbase_zh_CN.qm"):
        target = app / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(name.encode())
    (tmp_path / "user-settings.json").write_text('"private"', encoding="utf-8")
    outputs = build.assemble(app, archive, tmp_path / "dist", {"version": "0.1.0"})
    with zipfile.ZipFile(outputs[0]) as plain, zipfile.ZipFile(outputs[1]) as bundled:
        core = {name: plain.read(name) for name in plain.namelist()}
        assert core == {name: bundled.read(name) for name in bundled.namelist() if not name.startswith("LALC/pi/")}
        assert bundled.read("LALC/pi/native/win32/prebuilds/win32-x64/helper.dll") == b"test-runtime"
        assert b"MIT License" in bundled.read("LALC/pi/LICENSE.txt")
        assert not any("user-settings" in name or "candidate" in name for name in bundled.namelist())
        assert b'"%~dp0LALC.exe" --developer' in core["LALC/Developer.cmd"]
    sums = (tmp_path / "dist/SHA256SUMS").read_text(encoding="utf-8")
    assert all(build.digest(path) in sums for path in outputs)


def test_tampered_pi_and_missing_frozen_resource_are_rejected(tmp_path, archive):
    with pytest.raises(ValueError, match="Missing packaged"):
        build.assemble(tmp_path, archive, tmp_path / "dist", {"version": "0.1.0"})
    archive.write_bytes(archive.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="摘要"):
        build.check_pi(archive)


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/escape", "dir\\escape"])
def test_pi_archive_paths_are_checked_before_extraction(tmp_path, monkeypatch, name):
    path = tmp_path / "bad.zip"
    with zipfile.ZipFile(path, "w") as bundle:
        bundle.writestr(name, b"bad")
    monkeypatch.setattr(build, "PI_SHA256", build.digest(path))
    with pytest.raises(ValueError, match="Unsafe"):
        build.check_pi(path)


@pytest.mark.parametrize("frozen", [False, True])
def test_default_candidate_and_cli_lock_follow_same_path(tmp_path, monkeypatch, frozen):
    runtime, first, second = tmp_path / "data", tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    monkeypatch.setattr(sys, "frozen", frozen, raising=False)
    monkeypatch.setattr(cli, "default_data_root", lambda: runtime)
    locks = []
    class Lock:
        def __init__(self, name):
            locks.append(name)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
    monkeypatch.setattr("lalc.process_lock.ProcessLock", Lock)
    for cwd in (first, second):
        monkeypatch.chdir(cwd)
        expected = (runtime if frozen else cwd) / "candidate"
        assert application.default_candidate_root(runtime) == expected
        if not expected.exists():
            assert cli.main(["init"]) == 0
        assert (expected / "manifest.json").exists()
        cli.main(["validate"])
        assert locks[-1] == "candidate:" + str(expected.resolve())


@pytest.mark.parametrize("message,status,outcomes", [
    ("Hello", "completed", ["success", "success", "success"]),
    ("task-fail", "completed", ["success", "failure", "success"]),
    ("plan-fail", "interrupted", ["success"]),
])
def test_acceptance_sample_uses_real_plan_boundaries(tmp_path, monkeypatch, message, status, outcomes):
    from lalc.actions import application_actions
    from lalc.manifest import ManifestManager
    def wait(ctx, *, seconds: float) -> None:
        assert seconds == 5.0
    monkeypatch.setattr("lalc.actions.wait", wait)
    manager = ManifestManager(tmp_path, actions=application_actions())
    published = manager.publish(Path(__file__).parents[1] / "example/acceptance/manifest.json")
    assert published.ok, published.errors
    service = application.ApplicationService(tmp_path, manifest_manager=manager)
    service.start_plan(manifest_id=published.loaded.manifest_id, task_repetitions={"exp": 3},
                       settings={"exp": {"message": message}})
    result = service.wait_for(lambda state: state["phase"] == "finished")["result"]
    service.shutdown()
    assert result["status"] == status, result
    assert [item["status"] for item in result["items"]] == outcomes
