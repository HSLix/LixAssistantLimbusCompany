"""Workflow 分享底层：只检查和保存数据，不加载 Python 或修改 Default。"""

import json
import os
import re
from pathlib import Path
import uuid

from .work_files import work_file
from .file_content import require_memory
from .manifest import ManifestManager
from .runtime import sha256_bytes


def _directory(path):
    """拒绝目录访问链上的链接及非目录目标，包括 Windows junction。"""
    path = Path(path).absolute()
    if (any(item.is_symlink() or item.is_junction() for item in (path, *path.parents))
            or path.exists() and not path.is_dir()):
        raise ValueError("分享目录必须是真实目录，不能包含链接。")
    return path


def _prepare(manager, source_root, manifest_id):
    """读取受控暂存目录并复用 Manifest 静态检查，不调用 load/validate。"""
    errors = []
    manager._check_manifest_id(manifest_id, errors)
    if errors:
        raise ValueError(errors[0].code)
    root = _directory(source_root)
    source = ManifestManager(root, actions=manager.actions)
    _directory(source.manifests_dir)
    _directory(source.components_dir)
    path = source.manifests_dir / f"{manifest_id}.json"
    if path.is_symlink() or not path.is_file():
        raise ValueError("Manifest 必须是普通文件。")
    for component in source.components_dir.glob("*.py"):
        if component.is_symlink() or not component.is_file():
            raise ValueError("Component 必须是普通文件。")
    require_memory(path.stat().st_size * 16)
    declared, _ = source._read_json(path)
    required = path.stat().st_size
    if isinstance(declared, dict):
        for section in ("components", "recovery_rules"):
            entries = declared.get(section, {})
            if isinstance(entries, dict):
                for entry in entries.values():
                    identity = entry.get("component_id") if isinstance(entry, dict) else None
                    if isinstance(identity, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", identity):
                        component = source.components_dir / (identity[7:] + ".py")
                        if component.is_file():
                            required += component.stat().st_size
    require_memory(required * 16)
    prepared = source._prepare(path, saved=True)
    if prepared.errors:
        raise ValueError("; ".join(f"{error.code}: {error.message}" for error in prepared.errors))
    if not isinstance(prepared.manifest, dict):
        raise ValueError("Manifest 必须是对象。")
    if prepared.manifest["manifest_id"] != manifest_id:
        raise ValueError("Manifest UUID 与文件名不一致。")
    fingerprint = sha256_bytes(json.dumps(prepared.manifest, sort_keys=True).encode("utf-8"))
    return prepared, fingerprint


def _occupied(manager, manifest_id):
    """缺失文件但仍被 Default 指针引用的 UUID 也保留，避免导入使其自动激活。"""
    target = manager.manifests_dir / f"{manifest_id}.json"
    default = manager.manifests_dir / "default.json"
    if default.is_symlink():
        raise ValueError("Default 指针不能是链接。")
    saved, _ = manager._read_json(default) if default.exists() else (None, [])
    return target.exists() or target.is_symlink() or isinstance(saved, dict) and saved.get("manifest_id") == manifest_id


def inspect_workflow_import(manager, source_root, manifest_id):
    """检查暂存 Workflow，返回供人工确认的 UUID 和规范化内容指纹，不写本地。"""
    prepared, fingerprint = _prepare(manager, source_root, manifest_id)
    _directory(manager.data_root)
    directory = _directory(manager.manifests_dir)
    occupied = _occupied(manager, manifest_id)
    return {"source_manifest_id": manifest_id,
            "manifest_id": str(uuid.uuid4()) if occupied else manifest_id,
            "uuid_conflict": occupied, "manifest_sha256": fingerprint,
            "component_count": len(prepared.sources)}


def import_workflow(manager, source_root, source_manifest_id, *, manifest_id, manifest_sha256):
    """提交已确认的固定 UUID；重新静态检查，排他创建，失败不覆盖原版本。"""
    errors = []
    manager._check_manifest_id(manifest_id, errors)
    if errors:
        raise ValueError(errors[0].code)
    prepared, fingerprint = _prepare(manager, source_root, source_manifest_id)
    if fingerprint != manifest_sha256:
        raise ValueError("Manifest 内容已变化，请重新检查并确认。")
    _directory(manager.data_root)
    for directory in (manager.manifests_dir, manager.components_dir):
        _directory(directory).mkdir(parents=True, exist_ok=True)
    target = manager.manifests_dir / f"{manifest_id}.json"
    if _occupied(manager, manifest_id):
        raise FileExistsError("Manifest UUID 已被占用，请重新检查。")
    for source in prepared.sources.values():
        component = manager.components_dir / f"{source.component_id.removeprefix('sha256:')}.py"
        if component.is_symlink() or component.exists() and not component.is_file():
            raise ValueError("本地 Component 必须是普通文件。")
        manager._store_component(source)
    assert isinstance(prepared.manifest, dict)
    manifest = {**prepared.manifest, "manifest_id": manifest_id}
    temporary = None
    try:
        with work_file(dir=manager.manifests_dir, prefix=".import-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        # 排他创建也保护检查之后发生的占用；失败保留已存储的共享哈希源码。
        os.link(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {"source_manifest_id": source_manifest_id, "manifest_id": manifest_id}
