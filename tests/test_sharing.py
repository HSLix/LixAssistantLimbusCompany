"""覆盖四类对象 ZIP 往返、路径／哈希边界、冲突、非执行导入及部分完成。

项目根目录运行：.venv/bin/python -m pytest -q tests/test_sharing.py
"""

import base64
from io import BytesIO
import json
from pathlib import Path
import stat
import uuid
import zipfile

import pytest
from PIL import Image

from lalc.agent_repair import RepairLog
from lalc.manifest import EMPTY_PLAN, ManifestManager
from lalc.knowledge import KnowledgeLibrary
from lalc.sharing import (SharingPackage, _index, asset_files, build_export, catalog, digest,
    import_selected, inspect_objects, json_bytes, replace_asset, save_package)


def png(color):
    output = BytesIO()
    Image.new("RGB", (4, 3), color).save(output, format="PNG")
    return output.getvalue()


def put_asset(root, name, content):
    folder = root / "assets" / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{digest(content)}.png").write_bytes(content)
    (folder / "asset-tag.json").write_text(json.dumps({digest(content): ["tag"]}))


@pytest.fixture
def source(tmp_path, monkeypatch):
    root = tmp_path / "source"
    manager = ManifestManager(root)
    manager.manifests_dir.mkdir(parents=True)
    manager.components_dir.mkdir()
    identity = str(uuid.uuid4())
    plan = EMPTY_PLAN.encode()
    (manager.components_dir / f"{digest(plan)}.py").write_bytes(plan)
    manifest = {"schema_version": 2, "manifest_id": identity,
                "components": {"plans.default": {"component_id": "sha256:" + digest(plan)}}, "recovery_rules": {}}
    (manager.manifests_dir / f"{identity}.json").write_text(json.dumps(manifest))
    put_asset(root, "ui", png("red"))
    put_asset(root, "ui/child", png("blue"))
    page = root / "pages/sample"
    (page / "assets").mkdir(parents=True)
    marker = tmp_path / "must-not-execute"
    (page / "page.py").write_text(f'PAGE_ID = "sharing.sample"\nPAGE_NAME = "Sample"\nfrom pathlib import Path\nPath({str(marker)!r}).touch()\n')
    (page / "assets/banner.png").write_bytes(png("green"))
    session = root / "developer-sessions" / str(uuid.uuid4())
    (session / "candidate").mkdir(parents=True)
    (session / "candidate/plan.py").write_bytes(plan)
    (session / ".candidate-baseline.json").write_text(json.dumps({"manifest_id": identity, "files": {"plan.py": base64.b64encode(plan).decode()}}))
    (session / "page-drafts").mkdir()
    (session / "page-drafts/draft.py").write_text("# export-time draft")
    log = RepairLog(root, path=session / "log")
    log.record({"type": "message_end", "message": {"role": "user", "content": [{"type": "text", "text": "hello history"}]}})
    log.record({"type": "trial_started", "run_id": 1})
    (root / "traces").mkdir()
    (root / "traces/1.jsonl").write_text(json.dumps({"sequence": 1, "evidence_id": "1/2"}) + "\n")
    (root / "evidence/1").mkdir(parents=True)
    (root / "evidence/1/2.png").write_bytes(png("white"))
    (root / "user-settings.json").write_text('{"private":"must not export"}')
    def forbidden(*args, **kwargs):
        pytest.fail("分享不得执行 Workflow")
    monkeypatch.setattr(ManifestManager, "_load", forbidden)
    return manager, marker


@pytest.mark.parametrize('category', ['developer-operations', 'agent-interactions'])
def test_operation_logs_remain_discoverable_and_exportable(source, category):
    manager, _ = source
    log = RepairLog(manager.data_root, category=category)
    log.record({'type': 'candidate_initialized'})
    identity = log.path.relative_to(manager.data_root).as_posix()
    assert identity in catalog(manager)['history']
    objects = build_export(manager, {'history': [identity]})
    assert len(objects) == 1 and objects[0]['id'] == identity
    assert 'log/events.jsonl' in objects[0]['files']


def test_four_type_roundtrip_without_execution_or_session_restore(source, tmp_path):
    manager, marker = source
    selected = catalog(manager)
    objects = build_export(manager, selected)
    assert not any("user-settings.json" in obj["files"] for obj in objects)
    workflow, = [obj for obj in objects if obj["kind"] == "workflow"]
    assert all(not name.startswith("assets/") for name in workflow["files"])
    history, = [obj for obj in objects if obj["kind"] == "history"]
    assert "baseline/plan.py" in history["files"]
    assert "runs/1/evidence/2.png" in history["files"]
    target = ManifestManager(tmp_path / "target")
    archive = tmp_path / "share.zip"
    save_package(objects, archive)
    package = SharingPackage(archive)
    try:
        checks = inspect_objects(target, package)
        assert all(not check["errors"] for check in checks.values()), checks
        outcome = import_selected(target, package, checks, set(checks), asset_actions={}, reviewed={}, allow_unreviewed=True)
        assert outcome["failed"] is None, outcome
        assert len(outcome["completed"]) == 5
        assert not marker.exists() and not (target.manifests_dir / "default.json").exists()
        assert (target.data_root / "pages/sample/assets/banner.png").exists()
        assert not (target.data_root / "developer-sessions").exists()
        imported, = (target.data_root / "knowledge/imported-agent-history").iterdir()
        assert (imported / "baseline/plan.py").read_text() == EMPTY_PLAN
        knowledge = KnowledgeLibrary(target.data_root, lambda: None)
        chunks = list((imported / "readable").glob("*.txt"))
        assert any("hello history" in chunk.read_text() for chunk in chunks)
        for chunk in chunks:
            metadata, image = knowledge.read(chunk.relative_to(target.data_root / "knowledge").as_posix())
            assert metadata["text"] and image is None
    finally:
        package.close()


def test_uuid_collision_gets_new_identity_without_default_changes(source, tmp_path):
    manager, _ = source
    identity = catalog(manager)["workflow"][0]
    archive = tmp_path / "share.zip"
    save_package(build_export(manager, {"workflow": [identity]}), archive)
    old = (manager.manifests_dir / f"{identity}.json").read_bytes()
    (manager.manifests_dir / "default.json").write_text(json.dumps({"manifest_id": identity}))
    package = SharingPackage(archive)
    try:
        checks = inspect_objects(manager, package)
        assert checks[0]["uuid_conflict"] and checks[0]["manifest_id"] != identity
        result = import_selected(manager, package, checks, {0}, asset_actions={}, reviewed={})
        assert result["failed"] is None
        assert (manager.manifests_dir / f"{identity}.json").read_bytes() == old
        assert manager.default_manifest_id() == identity
    finally:
        package.close()


def test_parent_asset_replacement_preserves_unselected_child_and_rolls_back(source, tmp_path, monkeypatch):
    manager, _ = source
    original = asset_files(manager.data_root, "ui")
    child = asset_files(manager.data_root, "ui/child")
    replacement = {f"{digest(png('yellow'))}.png": png("yellow"), "asset-tag.json": b"{}"}
    from lalc.sharing import files_version
    rename = Path.rename
    def fail(path, target):
        if path.parent.name == "new":
            raise OSError("commit failed")
        return rename(path, target)
    with monkeypatch.context() as patch:
        patch.setattr(Path, "rename", fail)
        with pytest.raises(OSError, match="commit failed"):
            replace_asset(manager.data_root, "ui", replacement, files_version(original))
    assert asset_files(manager.data_root, "ui") == original
    replace_asset(manager.data_root, "ui", replacement, files_version(original))
    assert asset_files(manager.data_root, "ui") == replacement
    assert asset_files(manager.data_root, "ui/child") == child


def test_import_stops_after_first_failure_and_keeps_completed(source, tmp_path, monkeypatch):
    manager, _ = source
    archive = tmp_path / "share.zip"
    save_package(build_export(manager, catalog(manager)), archive)
    target = ManifestManager(tmp_path / "target")
    package = SharingPackage(archive)
    try:
        checks = inspect_objects(target, package)
        monkeypatch.setattr("lalc.sharing.replace_asset", lambda *args: (_ for _ in ()).throw(OSError("disk full")))
        result = import_selected(target, package, checks, set(checks), asset_actions={}, reviewed={}, allow_unreviewed=True)
        assert len(result["completed"]) == 1
        assert result["failed"]["kind"] == "assets" and len(result["unprocessed"]) == 3
        assert (target.manifests_dir / f"{package.objects[0]['id']}.json").exists()
        assert not (target.data_root / "pages").exists()
    finally:
        package.close()


@pytest.mark.parametrize("bad", ["../escape", "/absolute", "C:/escape", "objects/0/CON.txt", "objects/0/a."])
def test_unsafe_zip_members_are_rejected(tmp_path, bad):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        stream.writestr(bad, b"bad")
    with pytest.raises(ValueError):
        SharingPackage(archive)


@pytest.mark.parametrize("attack", ["hash", "extra", "symlink", "case", "duplicate", "version", "size"])
def test_archive_index_and_members_must_agree(tmp_path, attack):
    files = {"page.py": b'PAGE_ID="test"\nPAGE_NAME="Test"'}
    index = _index([{"kind": "pages", "id": "sample.py", "files": files}])
    if attack == "hash":
        index["objects"][0]["files"]["page.py"]["sha256"] = "0" * 64
    if attack == "version":
        index["version"] = True
    if attack == "size":
        index["objects"][0]["files"]["page.py"]["size"] = 1
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        stream.writestr("sharing.json", json_bytes(index))
        name = "objects/0/page.py"
        if attack == "symlink":
            info = zipfile.ZipInfo(name)
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            stream.writestr(info, files["page.py"])
        else:
            stream.writestr(name, files["page.py"])
        if attack in {"extra", "case", "duplicate"}:
            with pytest.warns(UserWarning) if attack == "duplicate" else __import__('contextlib').nullcontext():
                stream.writestr(name if attack == "duplicate" else "Objects/0/a" if attack == "case" else "unlisted", b"extra")
    with pytest.raises(ValueError):
        SharingPackage(archive)


def test_unreviewed_requires_confirmation_and_known_id_conflicts_block(source, tmp_path):
    manager, marker = source
    archive = tmp_path / "pages.zip"
    save_package(build_export(manager, {"pages": ["sample.py"]}), archive)
    target = ManifestManager(tmp_path / "target")
    package = SharingPackage(archive)
    try:
        checks = inspect_objects(target, package)
        outcome = import_selected(target, package, checks, {0}, asset_actions={}, reviewed={})
        assert outcome["failed"] and not marker.exists()
        other = target.data_root / "pages/other"
        other.mkdir(parents=True)
        (other / "page.py").write_text('PAGE_ID="sharing.sample"\nPAGE_NAME="Other"')
        with pytest.raises(ValueError, match="PAGE_ID"):
            import_selected(target, package, checks, {0}, asset_actions={}, reviewed={}, allow_unreviewed=True)
        assert not (target.data_root / "pages/sample").exists()
    finally:
        package.close()


def test_staging_survives_zip_removal_and_detects_staging_changes(source, tmp_path, monkeypatch):
    manager, _ = source
    objects = build_export(manager, {"pages": ["sample.py"]})
    archive = tmp_path / "share.zip"
    save_package(objects, archive)
    package = SharingPackage(archive)
    try:
        archive.unlink()
        package.verify()
        member = package.objects[0]["root"] / "page.py"
        member.write_bytes(b"changed")
        with pytest.raises(ValueError, match="暂存包内容已变化"):
            package.verify()
    finally:
        package.close()


def test_history_reference_cannot_read_outside_its_log(tmp_path):
    files = {"log/log-format.json": b'{"format":"lalc-agent-log","version":1}',
             "log/events.jsonl": (json.dumps({"$lalc_log": {"path": "../private.json", "sha256": "0" * 64, "kind": "json"}}) + "\n").encode(),
             "candidate/private.json": b'"private"'}
    path = tmp_path / "history.zip"
    save_package([{"kind": "history", "id": "external", "files": files}], path)
    package = SharingPackage(path)
    try:
        checks = inspect_objects(ManifestManager(tmp_path / "target"), package)
        assert "相对路径" in checks[0]["errors"][0]
        assert not (tmp_path / "target").exists()
    finally:
        package.close()


def test_large_history_images_keep_original_and_offer_readable_preview(source, tmp_path):
    import random
    manager, _ = source
    identity = catalog(manager)["history"][0]
    image = Image.frombytes("RGB", (1024, 1024), random.Random(0).randbytes(1024 * 1024 * 3))
    stream = BytesIO()
    image.save(stream, format="PNG")
    original = stream.getvalue()
    assert len(original) > 2 * 1024 * 1024
    log = RepairLog(manager.data_root, path=manager.data_root / identity / "log")
    log.record({"type": "message_end", "message": {"role": "user", "content": [
        {"type": "image", "mimeType": "image/png", "data": base64.b64encode(original).decode()}]}})
    path = tmp_path / "large-history.zip"
    save_package(build_export(manager, {"history": [identity]}), path)
    package = SharingPackage(path)
    target = ManifestManager(tmp_path / "target")
    try:
        checks = inspect_objects(target, package)
        assert not checks[0]["errors"], checks
        outcome = import_selected(target, package, checks, {0}, asset_actions={}, reviewed={})
        assert outcome["failed"] is None, outcome
        folder = Path(outcome["completed"][0]["path"])
        assert any(path.read_bytes() == original for path in (folder / "log/objects").glob("*.bin"))
        preview, = (folder / "readable/images").glob("*.jpg")
        metadata, picture = KnowledgeLibrary(target.data_root, lambda: None).read(preview.relative_to(target.data_root / "knowledge").as_posix())
        assert metadata["mime_type"] == "image/jpeg" and picture
    finally:
        package.close()


def test_target_asset_changes_require_recheck_even_when_skip_was_chosen(source, tmp_path):
    manager, _ = source
    path = tmp_path / "asset.zip"
    save_package(build_export(manager, {"assets": ["ui"]}), path)
    package = SharingPackage(path)
    try:
        checks = inspect_objects(manager, package)
        put_asset(manager.data_root, "ui", png("pink"))
        before = asset_files(manager.data_root, "ui")
        result = import_selected(manager, package, checks, {0}, asset_actions={0: "skip"}, reviewed={})
        assert result["failed"] and asset_files(manager.data_root, "ui") == before
    finally:
        package.close()


def test_hidden_resource_files_are_preserved_without_privacy_filtering(source, tmp_path):
    manager, _ = source
    folder = manager.data_root / "pages/sample/.images"
    folder.mkdir()
    (folder / "banner.png").write_bytes(png("green"))
    objects = build_export(manager, {"pages": ["sample.py"]})
    assert objects[0]["files"][".images/banner.png"] == png("green")
    path = tmp_path / "hidden.zip"
    save_package(objects, path)
    package = SharingPackage(path)
    try:
        target = ManifestManager(tmp_path / "target")
        checks = inspect_objects(target, package)
        result = import_selected(target, package, checks, {0}, asset_actions={}, reviewed={}, allow_unreviewed=True)
        assert result["failed"] is None
        assert (target.data_root / "pages/sample/.images/banner.png").read_bytes() == png("green")
    finally:
        package.close()


@pytest.mark.parametrize("name", [".GiT", ".gıt"])
def test_windows_case_alias_cannot_smuggle_git_configuration(tmp_path, name):
    files = {"page.py": b'PAGE_ID="sample"\nPAGE_NAME="Sample"', f"assets/{name}/config": b"[core]"}
    metadata = {"format": "lalc-sharing", "version": 1, "objects": [{"kind": "pages", "id": "sample.py",
                "files": {name: {"size": len(content), "sha256": digest(content)} for name, content in files.items()}}]}
    path = tmp_path / "git.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("sharing.json", json_bytes(metadata))
        for name, content in files.items():
            archive.writestr("objects/0/" + name, content)
    with pytest.raises(ValueError, match="索引"):
        SharingPackage(path)


def test_history_keeps_invalid_candidate_and_raw_snapshots(source, tmp_path):
    manager, _ = source
    session, = (manager.data_root / "developer-sessions").iterdir()
    for relative in ("candidate/manifest.json", "log/baseline/manifest.json", "log/round-1/original/manifest.json", "log/tool-1-page-package/resources/data.json"):
        path = session / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"{broken candidate")
    (session / "page-drafts/binary.txt").write_bytes(b"\xff\xfe")
    objects = build_export(manager, {"history": catalog(manager)["history"]})
    archive = tmp_path / "history.zip"
    save_package(objects, archive)
    package = SharingPackage(archive)
    try:
        target = ManifestManager(tmp_path / "target")
        checks = inspect_objects(target, package)
        assert not any(check["errors"] for check in checks.values()), checks
        outcome = import_selected(target, package, checks, set(checks), asset_actions={}, reviewed={})
        assert outcome["failed"] is None, outcome
        imported, = (target.data_root / "knowledge/imported-agent-history").iterdir()
        assert (imported / "candidate/manifest.json").read_bytes() == b"{broken candidate"
        assert (imported / "page-drafts/binary.txt").read_bytes() == b"\xff\xfe"
        assert any("{broken candidate" in path.read_text() for path in (imported / "readable").glob("*.txt"))
    finally:
        package.close()


def test_history_repeated_reference_expansion_is_bounded(tmp_path, monkeypatch):
    from lalc.agent_log import LogStore, MARKER
    from lalc.sharing import validate_history
    root = tmp_path / "history"
    log = root / "log"
    log.mkdir(parents=True)
    store = LogStore(log)
    leaf = store._put(b"x" * 64, "txt")
    repeated = store._put(json_bytes([leaf] * 10), "json")
    (log / "events.jsonl").write_text(json.dumps(repeated) + "\n")
    monkeypatch.setattr("lalc.sharing.available_memory", lambda: len(json_bytes([leaf] * 10)) + 100)
    with pytest.raises(ValueError, match="展开超过大小限制"):
        validate_history(root)


def test_history_repeated_images_are_verified_once(tmp_path, monkeypatch):
    import lalc.sharing as sharing
    from lalc.agent_log import LogStore, MARKER
    root = tmp_path / "history"
    log = root / "log"
    log.mkdir(parents=True)
    image = png("green")
    stored = LogStore(log)._put(image, "bin")[MARKER]
    reference = {MARKER: {**stored, "base64": True}}
    (log / "events.jsonl").write_text(json.dumps([reference] * 5) + "\n")
    calls = []
    original = sharing.FileContent.from_path
    def counted(path):
        if path.suffix == ".bin":
            calls.append(path)
        return original(path)
    monkeypatch.setattr(sharing.FileContent, "from_path", counted)
    sharing.validate_history(root)
    assert len(calls) == 1
