"""覆盖发版记录、双渠道版本查询、校验和更新交接准备。

项目根目录运行：uv run --frozen pytest -q tests/test_framework_update.py
"""

import hashlib
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
from urllib.error import HTTPError
import zipfile

import pytest

from lalc import framework_update as update


def test_packaged_beta_has_a_display_version_but_no_stable_update_version(tmp_path, monkeypatch):
    monkeypatch.setattr(update.sys, "frozen", True, raising=False)
    monkeypatch.setattr(update.sys, "executable", str(tmp_path / "LALC.exe"))
    (tmp_path / "build-info.json").write_text('{"version": "6.0.0-beta.12"}', encoding="utf-8")
    installed = update.installed_build()
    assert installed["version"] == "6.0.0-beta.12"
    assert update.version_number(installed["version"]) is None


def test_old_release_is_an_announcement_but_not_a_package(monkeypatch):
    monkeypatch.setattr(update, "_json", lambda _: {"tag_name": "v5.0.0", "body": "legacy news"})
    assert update.check_releases("with-agent", {}) == update.ReleaseStatus("legacy news", None, None,
                                                                          github_version=(5, 0, 0), resources_checked=True)


def test_bad_download_metadata_does_not_hide_release_body(monkeypatch):
    monkeypatch.setattr(update, "_json", lambda _: {"tag_name": "v6.0.1", "body": "## Latest GitHub notes", "assets": [
        None, {"name": "LALC-6.0.1-windows-x64-with-agent.zip", "digest": 8}]})
    assert update.check_releases("with-agent", {}) == update.ReleaseStatus("## Latest GitHub notes", None, None,
                                                                          github_version=(6, 0, 1), resources_checked=True)


def test_resource_appended_to_current_release_is_independent_of_framework(monkeypatch):
    def asset(name, date, **fields):
        return {"name": name, "digest": "sha256:" + "3" * 64, "state": "uploaded",
                "size": 42, "created_at": date, **fields}

    date = "2026-11-23T14:30:00Z"
    name = "lalc-sharing-20261122-143000-000.zip"
    release = {"tag_name": "v6.0.0", "assets": [
        asset(name, date),
        asset("default-resources.zip", "2026-11-22T14:30:00Z"),
        asset("irrelevant.zip", "2026-11-24T14:30:00Z"),
        asset("LALC-6.0.0-windows-x64-with-agent.zip", "2026-11-22T14:30:00Z"),
    ]}
    monkeypatch.setattr(update, "_json", lambda _: release)
    status = update.check_releases("with-agent", {})
    assert status.github.version == (6, 0, 0)
    assert status.resource == update.ResourceRelease(name, f"{update.REPOSITORY_URL}/releases/download/v6.0.0/{name}",
                                                    "3" * 64, 42, datetime.fromisoformat(date))
    release["prerelease"] = True
    status = update.check_releases("with-agent", {})
    assert status.github is None and status.resource is None


def test_resource_download_verifies_size_and_digest(tmp_path, monkeypatch):
    class Response(io.BytesIO):
        def geturl(self):
            return "https://example.test/package"

    payload = b"resource archive"
    monkeypatch.setattr(update, "urlopen", lambda *args, **kwargs: Response(payload))
    resource = update.ResourceRelease("default-resources.zip", "https://example.test/package",
                                      hashlib.sha256(payload).hexdigest(), len(payload), datetime.now(timezone.utc))
    update.download_resource(resource, tmp_path / resource.name)
    assert (tmp_path / resource.name).read_bytes() == payload
    bad = update.ResourceRelease(resource.name, resource.url, "0" * 64, resource.size, resource.uploaded)
    with pytest.raises(ValueError, match="checksum"):
        update.download_resource(bad, tmp_path / "invalid.zip")


def test_versioned_resource_uses_export_time_even_when_upload_order_differs(monkeypatch):
    name = "default-resources-20261125T103045Z.zip"
    assets = [
        (name, "2026-11-25T11:00:00Z"),
        ("default-resources-20261125T103044Z.zip", "2026-11-26T00:00:00Z"),
        ("default-resources-20261131T103046Z.zip", "2026-11-27T00:00:00Z"),
        ("default-resources.zip", "2026-11-28T00:00:00Z"),
    ]
    monkeypatch.setattr(update, "_json", lambda _: {"tag_name": "v6.0.0", "assets": [
        {"name": name, "created_at": date, "state": "uploaded", "size": 42, "digest": "sha256:" + "3" * 64}
        for name, date in assets
    ]})
    resource = update.check_releases("with-agent", {}).resource
    assert resource.name == name
    assert resource.exported == datetime(2026, 11, 25, 10, 30, 45, tzinfo=timezone.utc)


def test_api_rate_limit_reads_only_latest_release_body(monkeypatch, caplog):
    expected = '<h2>Release changes</h2>\n<div><p>Nested notes</p></div>\n<p>More changes</p>'

    class ReleasePage(io.BytesIO):
        def geturl(self):
            return f"{update.REPOSITORY_URL}/releases/tag/v5.0.0"

    def open_release(request, *, timeout):
        if request.full_url.startswith("https://api.github.com/"):
            raise HTTPError(request.full_url, 403, "rate limit exceeded", None, None)
        assert request.full_url == update.LATEST_RELEASE_URL
        return ReleasePage(f'<div>GitHub navigation</div>\n<div data-test-selector="body-content">\n{expected}\n</div><div>Assets</div>'.encode())

    monkeypatch.setattr(update, "urlopen", open_release)
    assert update.check_releases("with-agent", {}) == update.ReleaseStatus(expected, None, None, announcement_html=True,
                                                                          github_version=(5, 0, 0))
    assert "HTTP 403" in caplog.text


def test_release_channels_are_independent_and_use_exact_package(monkeypatch):
    def api(url):
        if "mirrorchyan" in url:
            assert "cdk=" not in url
            return {"code": 0, "data": {"version_name": "v6.0.1"}}
        return {"tag_name": "v6.0.2", "body": "news", "assets": [
            {"name": "lalc.zip", "digest": "sha256:" + "1" * 64},
            {"name": "LALC-6.0.2-windows-x64-without-agent.zip", "digest": "sha256:" + "2" * 64},
        ]}

    monkeypatch.setattr(update, "_json", api)
    mirror = {"rid": "new-rid"}
    result = update.check_releases("without-agent", mirror)
    assert result.announcement == "news" and result.mirror == (6, 0, 1)
    assert result.github.sha256 == "2" * 64 and result.github.version == (6, 0, 2)
    assert update.check_releases("with-agent", mirror).github is None


@pytest.mark.parametrize("name", ["LALC/../outside", "LALC/AUX.txt", "LALC/test:stream", "LALC/dir\\file", "other/file"])
def test_reject_update_archive_paths(name, tmp_path):
    archive = tmp_path / "bad.zip"
    extract_to = tmp_path / "extracted"
    extract_to.mkdir()
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("LALC/valid.txt", "valid")
        member = zipfile.ZipInfo("placeholder")
        member.filename = name
        bundle.writestr(member, "bad")
    with pytest.raises(ValueError, match="Unsafe update archive"):
        update._extract(archive, extract_to)
    assert not list(extract_to.iterdir())


def test_bad_mirror_package_falls_back_to_verified_github(tmp_path, monkeypatch):
    published = io.BytesIO()
    with zipfile.ZipFile(published, "w") as archive:
        for name in (*update.REQUIRED_FILES, "agent/codesearch.exe"):
            archive.writestr(f"LALC/{name}", json.dumps({"version": "6.0.1"}) if name == "build-info.json" else b"fixture")
    payload = published.getvalue()
    executable = tmp_path / "LALC.exe"
    (tmp_path / "install-update.ps1").write_text("trusted installed script", encoding="utf-8")
    monkeypatch.setattr(update.sys, "executable", str(executable))
    monkeypatch.setattr(update, "_read_cdk", lambda _: "fake-secret")
    mirror_url = "https://mirror.example/package"
    monkeypatch.setattr(update, "_mirror", lambda *args: {
        "version_name": "v6.0.1", "url": mirror_url, "update_type": "full", "sha256": "0" * 64})
    attempts = []

    class Response(io.BytesIO):
        def geturl(self):
            return attempts[-1]

    def download(request, **kwargs):
        attempts.append(request.full_url)
        return Response(payload)

    monkeypatch.setattr(update, "urlopen", download)
    version = (6, 0, 1)
    github = update.Package(version, "https://github.example/package", hashlib.sha256(payload).hexdigest())
    status = update.ReleaseStatus("news", github, version)
    root = tmp_path / "data"
    workspace = update.prepare_update(root, status, version, "with-agent", {"rid": "LALC6"})
    assert attempts == [mirror_url, github.url]
    assert (workspace / "LALC/LALC.exe").is_file()
    assert (workspace / "install-update.ps1").read_text() == "trusted installed script"
    assert list((root / "work").iterdir()) == [workspace]
    attempts.clear()
    assert update.prepare_update(root, status, version, "with-agent", {"rid": "LALC6"}, lambda: bool(attempts)) is None
    assert attempts == [mirror_url] and list((root / "work").iterdir()) == [workspace]


def test_release_notes_count_direct_commits_and_coauthors(tmp_path):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(tmp_path), *args], encoding="utf-8").strip()

    git("init", "-q")
    git("config", "user.name", "First Author")
    git("config", "user.email", "first@example.com")
    git("commit", "--allow-empty", "-qm", "previous release")
    git("tag", "v6.0.0")
    git("commit", "--allow-empty", "-qm", "direct fix", "-m", "Co-authored-by: Second Author <second@example.com>")
    script = Path(__file__).parents[1] / "scripts/release_notes.py"
    notes = subprocess.check_output([sys.executable, str(script), "v6.0.0", "HEAD"], cwd=tmp_path, encoding="utf-8")
    links, changelog = notes.split("\n\n## 更新记录\n", 1)
    assert ["mirrorchyan.com", "github.com", "pan.quark.cn", "discord.gg"] == [
        next(domain for domain in ("mirrorchyan.com", "github.com", "pan.quark.cn", "discord.gg") if domain in line)
        for line in links.splitlines()]
    assert "First Author (1)" in changelog and "Second Author (1)" in changelog
    assert changelog.count("direct fix") == 2 and "previous release" not in changelog


@pytest.mark.skipif(sys.platform != "win32", reason="Windows directory and process behavior")
@pytest.mark.parametrize("legacy, ready", [(True, True), (False, False)])
def test_windows_installer_in_place_and_rollback(legacy, ready, tmp_path):
    import ctypes

    if not ctypes.windll.shell32.IsUserAnAdmin():
        pytest.skip("Installer test needs an elevated Windows test runner")
    powershell = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass"]
    target = tmp_path / "old installation"
    payload = tmp_path / "staged package"
    target.mkdir()
    payload.mkdir()
    old_exe = target / ("LixAssistantLimbusCompany.exe" if legacy else "LALC.exe")
    old_exe.write_bytes(b"previous program")
    if not legacy:
        (target / "build-info.json").write_text("{}")
    exe = payload / "LALC.exe"
    for name in ("LALC-console.exe", "install-update.ps1"):
        (payload / name).touch()
    (payload / "build-info.json").write_text(json.dumps({"version": "6.0.1"}), encoding="utf-8")
    (payload / "_internal").mkdir()
    if ready:
        helper = r'''
$code = @'
using System;
using System.Threading;
public class Program {
    public static int Main(string[] args) {
        foreach (var arg in args) {
            if (arg.StartsWith("--update-ready=")) {
                using (var ready = EventWaitHandle.OpenExisting(@"Local\LALC-update-" + arg.Substring(15))) {
                    ready.Set();
                    return 0;
                }
            }
        }
        return 1;
    }
}
'@
Add-Type -TypeDefinition $code -OutputAssembly $env:LALC_TEST_UPDATE_EXE -OutputType ConsoleApplication
'''
        compiler = tmp_path / "compile.ps1"
        compiler.write_text(helper, encoding="utf-8")
        subprocess.run([*powershell, "-File", str(compiler)], check=True,
                       env={**os.environ, "LALC_TEST_UPDATE_EXE": str(exe)}, timeout=30)
        assert exe.is_file()
    else:
        exe.write_bytes(b"invalid executable")
    script = Path(__file__).parents[1] / "packaging/install-update.ps1"
    result = subprocess.run([*powershell, "-File", str(script), "-Source", str(payload), "-Target", str(target),
                             *(["-Legacy"] if legacy else [])], cwd=tmp_path, stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=65)
    assert result.returncode == (0 if ready else 1), (result.stdout, result.stderr)
    backups = list(tmp_path.glob(target.name + ".backup-*"))
    if ready:
        assert (target / "LALC.exe").read_bytes() == exe.read_bytes()
        assert old_exe.read_bytes() == exe.read_bytes()
        assert len(backups) == 1 and (backups[0] / old_exe.name).read_bytes() == b"previous program"
    else:
        assert old_exe.read_bytes() == b"previous program" and not backups
