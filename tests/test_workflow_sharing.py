"""覆盖 Workflow 非执行式导入、UUID 重分配、内容变化及失败不覆盖。

在项目根目录运行：.venv/bin/python -m pytest -q tests/test_workflow_sharing.py
"""

import json
import os
from pathlib import Path
import uuid

import pytest

from lalc.manifest import EMPTY_PLAN, ManifestManager
from lalc.runtime import sha256_bytes
from lalc.workflow_sharing import import_workflow, inspect_workflow_import


@pytest.fixture
def workflow(tmp_path, monkeypatch):
    root = tmp_path / "incoming"
    (root / "manifests").mkdir(parents=True)
    (root / "components").mkdir()
    digest = sha256_bytes(EMPTY_PLAN.encode())
    component = root / "components" / f"{digest}.py"
    component.write_text(EMPTY_PLAN, encoding="utf-8")
    identity = str(uuid.uuid4())
    manifest = {"schema_version": 2, "manifest_id": identity,
                "components": {"plans.default": {"component_id": f"sha256:{digest}"}},
                "recovery_rules": {}}
    (root / "manifests" / f"{identity}.json").write_text(json.dumps(manifest), encoding="utf-8")
    manager = ManifestManager(tmp_path / "local")
    def forbidden(*args, **kwargs):
        pytest.fail("导入不得加载 Python 源码")
    monkeypatch.setattr(ManifestManager, "_load", forbidden)
    monkeypatch.setattr(ManifestManager, "_load_module", forbidden)
    return manager, root, identity, component


def commit(manager, root, proposal):
    return import_workflow(manager, root, proposal["source_manifest_id"],
                           manifest_id=proposal["manifest_id"], manifest_sha256=proposal["manifest_sha256"])


def test_inspect_has_no_writes_and_import_does_not_execute(workflow):
    manager, root, identity, component = workflow
    proposal = inspect_workflow_import(manager, root, identity)
    assert not manager.data_root.exists()
    assert proposal["manifest_id"] == identity and not proposal["uuid_conflict"]
    assert commit(manager, root, proposal)["manifest_id"] == identity
    assert (manager.components_dir / component.name).read_bytes() == component.read_bytes()
    assert not (manager.manifests_dir / "default.json").exists()
    assert manager.default is None


def test_collision_allocates_new_uuid_and_preserves_default_and_components(workflow):
    manager, root, identity, component = workflow
    commit(manager, root, inspect_workflow_import(manager, root, identity))
    original = (manager.manifests_dir / f"{identity}.json").read_bytes()
    default = manager.manifests_dir / "default.json"
    default.write_text(json.dumps({"manifest_id": identity}), encoding="utf-8")
    stored = manager.components_dir / component.name
    modified = stored.stat().st_mtime_ns
    proposal = inspect_workflow_import(manager, root, identity)
    assert proposal["uuid_conflict"] and proposal["manifest_id"] != identity
    assert len(list(manager.manifests_dir.glob("*.json"))) == 2
    commit(manager, root, proposal)
    imported = json.loads((manager.manifests_dir / f"{proposal['manifest_id']}.json").read_bytes())
    assert imported["manifest_id"] == proposal["manifest_id"]
    assert (manager.manifests_dir / f"{identity}.json").read_bytes() == original
    assert manager.default_manifest_id() == identity
    assert stored.stat().st_mtime_ns == modified


@pytest.mark.parametrize("kind", ["corrupt", "symlink"])
def test_local_component_conflict_never_overwrites_old_data(workflow, tmp_path, kind):
    manager, root, identity, component = workflow
    proposal = inspect_workflow_import(manager, root, identity)
    manager.components_dir.mkdir(parents=True)
    stored = manager.components_dir / component.name
    if kind == "symlink":
        outside = tmp_path / "private.py"
        outside.write_bytes(component.read_bytes())
        stored.symlink_to(outside)
    else:
        stored.write_bytes(b"keep corrupt local file for investigation")
    original = stored.read_bytes()
    with pytest.raises(ValueError):
        commit(manager, root, proposal)
    assert stored.read_bytes() == original
    assert not (manager.manifests_dir / f"{identity}.json").exists()


def test_occupied_confirmed_uuid_is_never_replaced(workflow, monkeypatch):
    manager, root, identity, _ = workflow
    proposal = inspect_workflow_import(manager, root, identity)
    original_link = os.link
    def raced_link(source, target):
        Path(target).write_bytes(b"occupied after inspection")
        return original_link(source, target)
    monkeypatch.setattr("lalc.workflow_sharing.os.link", raced_link)
    # 先存入同哈希 Component，避免故障注入影响 Component 自身的排他写入。
    manager.components_dir.mkdir(parents=True)
    for component in (root / "components").glob("*.py"):
        (manager.components_dir / component.name).write_bytes(component.read_bytes())
    with pytest.raises(FileExistsError):
        commit(manager, root, proposal)
    assert (manager.manifests_dir / f"{identity}.json").read_bytes() == b"occupied after inspection"
    assert not list(manager.manifests_dir.glob(".import-*"))


def test_changed_manifest_requires_new_confirmation(workflow):
    manager, root, identity, _ = workflow
    proposal = inspect_workflow_import(manager, root, identity)
    path = root / "manifests" / f"{identity}.json"
    manifest = json.loads(path.read_bytes())
    manifest["components"]["plans.other"] = manifest["components"].pop("plans.default")
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="内容已变化"):
        commit(manager, root, proposal)
    assert not manager.data_root.exists()


def test_dangling_default_uuid_is_reserved_to_prevent_implicit_activation(workflow):
    manager, root, identity, _ = workflow
    manager.manifests_dir.mkdir(parents=True)
    default = manager.manifests_dir / "default.json"
    default.write_text(json.dumps({"manifest_id": identity}), encoding="utf-8")
    original = default.read_bytes()
    proposal = inspect_workflow_import(manager, root, identity)
    assert proposal["uuid_conflict"] and proposal["manifest_id"] != identity
    commit(manager, root, proposal)
    assert default.read_bytes() == original
    assert not (manager.manifests_dir / f"{identity}.json").exists()
    assert manager.default_manifest_id() is None


def test_hash_corruption_and_links_are_rejected(workflow, tmp_path):
    manager, root, identity, component = workflow
    original = component.read_bytes()
    component.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="component_id_mismatch"):
        inspect_workflow_import(manager, root, identity)
    outside = tmp_path / "outside.py"
    outside.write_bytes(original)
    component.unlink()
    component.symlink_to(outside)
    with pytest.raises(ValueError, match="普通文件"):
        inspect_workflow_import(manager, root, identity)
    assert not manager.data_root.exists()
