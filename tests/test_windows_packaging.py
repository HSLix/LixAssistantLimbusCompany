"""覆盖同源双包、旧版迁移包、归档边界及成品草稿路径。

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
from lalc.resource_version import read_resource_version, resource_asset_name
from scripts import prepare_default_resource, publish_default_resources
from test_sharing import source


spec = importlib.util.spec_from_file_location("windows_build", Path(__file__).parents[1] / "scripts/build_windows.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


@pytest.fixture
def prepared_resources(tmp_path, monkeypatch, source):
    packaging = tmp_path / "packaging"
    packaging.mkdir()
    monkeypatch.setattr(prepare_default_resource, "ROOT", tmp_path)
    monkeypatch.setattr(prepare_default_resource, "default_data_root", lambda: source[0].data_root)
    prepare_default_resource.main()
    resource = packaging / "default-resources.zip"
    return resource, read_resource_version(resource)


@pytest.fixture
def archive(tmp_path, monkeypatch):
    path = tmp_path / "pi.zip"
    with zipfile.ZipFile(path, "w") as bundle:
        bundle.writestr("pi.exe", b"test-only-binary")
        bundle.writestr("package.json", json.dumps({"version": build.PI_VERSION}))
        bundle.writestr("native/win32/prebuilds/win32-x64/helper.dll", b"test-runtime")
    monkeypatch.setattr(build, "PI_SHA256", build.digest(path))
    return path


@pytest.fixture(autouse=True)
def agent_resources(tmp_path, monkeypatch):
    path = tmp_path / "codesearch.zip"
    with zipfile.ZipFile(path, "w") as bundle:
        bundle.writestr("codesearch.exe", b"test-codesearch")
    monkeypatch.setattr(build, "CODESEARCH_ARCHIVE", path)
    monkeypatch.setattr(build, "CODESEARCH_SHA256", build.digest(path))
    models = tmp_path / "models"
    snapshot = models / build.MODEL_REPO / "snapshots" / build.MODEL_REVISION
    hashes = {}
    for name in build.MODEL_FILES:
        file = snapshot / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(name.encode())
        hashes[name] = build.digest(file)
    monkeypatch.setattr(build, "MODEL_ROOT", models)
    monkeypatch.setattr(build, "MODEL_FILES", hashes)


def test_two_archives_share_application_and_keep_complete_pi_runtime(tmp_path, archive, monkeypatch, prepared_resources):
    app = tmp_path / "application"
    for name in ("LALC.exe", "LALC-console.exe", "_internal/lalc/MagicAndWonder.ico", "_internal/lalc/mirror_chyan.png", "_internal/lalc/pi_probe.ts", "_internal/lalc/pi_context.ts", *[f"_internal/lalc/skills/{name}/SKILL.md" for name in build.DEFAULT_SKILL_NAMES],
                 "_internal/lalc/translations/lalc_zh_CN.qm", "_internal/PySide6/translations/qtbase_zh_CN.qm",
                 "_internal/rapidocr/config.yaml", "_internal/rapidocr/default_models.yaml",
                 "_internal/UnityPy/resources/lzma.tpk",
                 *["_internal/rapidocr/models/" + name for name in build.MODEL_HASHES]):
        target = app / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(name.encode())
    monkeypatch.setattr(build, "MODEL_HASHES", {name: build.digest(app / "_internal/rapidocr/models" / name)
                                              for name in build.MODEL_HASHES})
    (tmp_path / "user-settings.json").write_text('"private"', encoding="utf-8")
    resource, version = prepared_resources
    attachment_name = resource_asset_name(version)
    outputs = build.assemble(app, archive, tmp_path / "dist", {"version": "0.1.0"},
                             default_resources=resource, resource_version=version)
    with zipfile.ZipFile(outputs[0]) as plain, zipfile.ZipFile(outputs[1]) as bundled:
        core = {name: plain.read(name) for name in plain.namelist()}
        assert core == {name: bundled.read(name) for name in bundled.namelist() if not name.startswith(("LALC/pi/", "LALC/agent/"))}
        assert bundled.read("LALC/pi/native/win32/prebuilds/win32-x64/helper.dll") == b"test-runtime"
        assert b"MIT License" in bundled.read("LALC/pi/LICENSE.txt")
        assert bundled.read("LALC/agent/codesearch.exe") == b"test-codesearch"
        assert any(name.endswith("onnx/model_quantized.onnx") for name in bundled.namelist())
        assert "LALC/agent/agent-resources-NOTICE.txt" in bundled.namelist()
        assert outputs[0].name.endswith("without-agent.zip") and outputs[1].name.endswith("with-agent.zip")
        assert not any("user-settings" in name or "candidate" in name for name in bundled.namelist())
        assert b'"%~dp0LALC.exe" --developer' in core["LALC/Developer.cmd"]
        assert json.loads(core["LALC/build-info.json"])["default_resources_sha256"] == build.hashlib.sha256(
            core["LALC/default-resources.zip"]).hexdigest()
        assert json.loads(core["LALC/build-info.json"])["default_resources_version"] == version
        assert outputs[3].name == attachment_name
        assert outputs[3].read_bytes() == core["LALC/default-resources.zip"]
        with zipfile.ZipFile(outputs[2]) as legacy:
            assert outputs[2].name == "lalc.zip"
            assert b"-Legacy" in legacy.read("lalc/update_to.bat")
            assert "LALC/update_to.bat" not in bundled.namelist()
            assert {name.removeprefix("lalc/"): legacy.read(name) for name in legacy.namelist() if name != "lalc/update_to.bat"} == {
                name.removeprefix("LALC/"): bundled.read(name) for name in bundled.namelist()}
    sums = (tmp_path / "dist/SHA256SUMS").read_text(encoding="utf-8")
    assert all(build.digest(path) in sums for path in outputs)
    beta = build.assemble(app, archive, tmp_path / "beta", {"version": "0.1.0"},
                          default_resources=resource, beta_number=12, resource_version=version)
    assert [path.name for path in beta] == [
        "LALC-0.1.0-windows-x64-without-agent.zip",
        "LALC-0.1.0-windows-x64-with-agent.zip",
        attachment_name,
    ]
    assert beta[2].read_bytes() == resource.read_bytes()
    for path in beta[:2]:
        with zipfile.ZipFile(path) as package:
            assert json.loads(package.read("LALC/build-info.json"))["version"] == "0.1.0-beta.12"
            assert package.read("LALC/default-resources.zip") == outputs[3].read_bytes()
    assert (tmp_path / "beta/SHA256SUMS").read_text(encoding="utf-8").splitlines() == [
        f"{build.digest(path)}  {path.name}" for path in beta
    ]
    before = {path: build.digest(path) for path in outputs}
    (app / "_internal/lalc/skills/workflow-development/SKILL.md").unlink()
    with pytest.raises(ValueError, match="SKILL.md"):
        build.assemble(app, archive, tmp_path / "dist", {"version": "0.1.0"})
    assert {path: build.digest(path) for path in outputs} == before


def test_export_metadata_rejects_missing_and_mismatched_zip(tmp_path):
    resource = tmp_path / "default-resources.zip"
    resource.write_bytes(b"new resource package")
    with pytest.raises(ValueError, match="缺少"):
        read_resource_version(resource)
    resource.with_suffix(".txt").write_text("20261125T103045Z\n" + "0" * 64 + "\n", encoding="ascii")
    with pytest.raises(ValueError, match="SHA-256"):
        read_resource_version(resource)


def test_resource_target_resolves_github_latest_stable(monkeypatch):
    repo = "HSLix/LixAssistantLimbusCompany"

    def api(args, *, text):
        assert args == ["gh", "api", f"repos/{repo}/releases/latest"]
        return '{"tag_name":"v6.1.0"}'

    monkeypatch.setattr(publish_default_resources.subprocess, "check_output", api)
    assert publish_default_resources.resolve_release_tag(repo, "", "最新正式版") == "v6.1.0"


def test_resource_target_resolves_newest_published_beta_across_pages(monkeypatch):
    repo = "HSLix/LixAssistantLimbusCompany"

    def release(tag, day, *, draft=False, prerelease=True):
        return {"tag_name": tag, "published_at": f"2026-11-{day:02}T00:00:00Z",
                "draft": draft, "prerelease": prerelease, "id": day}

    pages = [[release("v6.0.0-beta.8", 25, draft=True), release("v6.0.0", 24, prerelease=False),
              release("v6.0.0-rc.1", 23), release("v6.0.0-beta.6", 21)],
             [release("v6.0.0-beta.5", 22), release("v6.0.0-beta.4", 20)]]

    def api(args, *, text):
        assert args == ["gh", "api", "--paginate", "--slurp", f"repos/{repo}/releases"]
        return json.dumps(pages)

    monkeypatch.setattr(publish_default_resources.subprocess, "check_output", api)
    assert publish_default_resources.resolve_release_tag(repo, "", "最新 Beta") == "v6.0.0-beta.5"
    pages.clear()
    with pytest.raises(ValueError, match="找不到已发布"):
        publish_default_resources.resolve_release_tag(repo, "", "最新 Beta")


@pytest.mark.parametrize(("selection", "tag", "message"), [
    ("指定 Release", "", "必须填写目标标签"),
    ("最新正式版", "v6.0.0", "请留空目标标签"),
    ("最新 Beta", "v6.0.0-beta.5", "请留空目标标签"),
])
def test_resource_target_rejects_missing_or_conflicting_input(selection, tag, message):
    with pytest.raises(ValueError, match=message):
        publish_default_resources.resolve_release_tag("HSLix/LixAssistantLimbusCompany", tag, selection)


@pytest.mark.parametrize("existing", ["absent", "matching", "conflict"])
def test_append_resource_keeps_existing_assets(monkeypatch, prepared_resources, existing):
    source, version = prepared_resources
    asset_name = resource_asset_name(version)
    digest = build.digest(source) if existing == "matching" else "0" * 64
    assets = [] if existing == "absent" else [{"name": asset_name, "digest": "sha256:" + digest, "state": "uploaded"}]
    repo, tag = "HSLix/LixAssistantLimbusCompany", "v6.0.0-beta.5"
    uploads = []

    def release(args, *, text):
        assert args == ["gh", "api", f"repos/{repo}/releases/tags/{tag}"]
        return json.dumps({"draft": False, "assets": assets})

    def upload(args, *, check):
        assert args[:4] == ["gh", "release", "upload", tag]
        assert args[5:] == ["--repo", repo]
        asset = Path(args[4])
        assert asset.name == asset_name and asset.read_bytes() == source.read_bytes()
        assert check
        uploads.append(asset.name)

    monkeypatch.setattr(publish_default_resources, "ROOT", source.parents[1])
    monkeypatch.setattr(publish_default_resources.subprocess, "check_output", release)
    monkeypatch.setattr(publish_default_resources.subprocess, "run", upload)
    if existing == "conflict":
        with pytest.raises(ValueError, match="同名附件"):
            publish_default_resources.publish(repo, tag)
    else:
        publish_default_resources.publish(repo, tag)
    assert uploads == ([asset_name] if existing == "absent" else [])


def test_tampered_ocr_model_prevents_replacing_archives(tmp_path, archive, monkeypatch):
    app = tmp_path / "application"
    resources = ["LALC.exe", "LALC-console.exe", "_internal/lalc/MagicAndWonder.ico", "_internal/lalc/mirror_chyan.png",
                 "_internal/lalc/pi_probe.ts", "_internal/lalc/pi_context.ts", *[f"_internal/lalc/skills/{name}/SKILL.md" for name in build.DEFAULT_SKILL_NAMES],
                 "_internal/lalc/translations/lalc_zh_CN.qm", "_internal/PySide6/translations/qtbase_zh_CN.qm",
                 "_internal/rapidocr/config.yaml", "_internal/rapidocr/default_models.yaml",
                 "_internal/UnityPy/resources/lzma.tpk"]
    for name in resources:
        path = app / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"test")
    model = app / "_internal/rapidocr/models/det.onnx"
    model.parent.mkdir(parents=True)
    model.write_bytes(b"original")
    monkeypatch.setattr(build, "MODEL_HASHES", {"det.onnx": build.digest(model)})
    model.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="OCR model hash"):
        build.assemble(app, archive, tmp_path / "dist", {"version": "0.1.0"})
    assert not (tmp_path / "dist").exists()


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
        member = zipfile.ZipInfo("placeholder")
        member.filename = name
        bundle.writestr(member, b"bad")
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


def test_codesearch_and_model_tampering_are_rejected(agent_resources, tmp_path):
    build.check_codesearch(build.CODESEARCH_ARCHIVE, build.MODEL_ROOT)
    snapshot = build.MODEL_ROOT / build.MODEL_REPO / 'snapshots' / build.MODEL_REVISION
    target = snapshot / next(iter(build.MODEL_FILES))
    target.write_bytes(b'tampered')
    with pytest.raises(ValueError, match='MiniLM model hash'):
        build.check_codesearch(build.CODESEARCH_ARCHIVE, build.MODEL_ROOT)
    build.CODESEARCH_ARCHIVE.write_bytes(b'tampered archive')
    with pytest.raises(ValueError, match='codesearch ZIP'):
        build.check_codesearch(build.CODESEARCH_ARCHIVE, build.MODEL_ROOT)
