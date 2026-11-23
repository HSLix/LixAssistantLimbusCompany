"""打包已发布默认资源，并在空白用户目录中显式安装。"""

import json
from pathlib import Path
import sys

from .agent_skills import DEFAULT_SKILL_NAMES
from .manifest import ManifestManager
from .process_lock import ProcessLock
from .runtime import atomic_write_json
from .sharing import (MIRROR_DEFAULT_FIELDS, MIRROR_SETTINGS_ID, PAGE_DEFAULTS_FILE, SharingPackage,
                      build_export, catalog, import_selected, inspect_objects, json_bytes,
                      page_settings_config, save_package)
from .user_pages import UserSettings

DEFAULT_RESOURCE_NAME = "default-resources.zip"
RESOURCE_KINDS = {"workflow", "assets", "pages", "skills"}


def viewed_resource_packages(root):
    """读取本机已打开导入预览的官方包摘要。"""
    try:
        value = json.loads((root / "viewed-resource-packages.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def record_viewed_resource(root, resource):
    """同一份内容即使重新上传，也只提示一次。由分享活动互斥保护。"""
    viewed = viewed_resource_packages(root)
    if resource.sha256 not in viewed:
        viewed[resource.sha256] = resource.uploaded.isoformat()
        atomic_write_json(root / "viewed-resource-packages.json", viewed)


def bundled_default_resources():
    """资源包与 Windows 程序并列交付。"""
    return Path(sys.executable).parent / DEFAULT_RESOURCE_NAME if getattr(sys, "frozen", False) else None


def export_default_resources(source, destination):
    """导出正式资源及已保存的镜牢饰品与主题包默认配置。"""
    manager = ManifestManager(source)
    with ProcessLock("game"):
        available = catalog(manager, include_private=False)
        selection = {"workflow": available["workflow"][:1], "assets": available["assets"], "pages": available["pages"],
                     "skills": sorted(set(DEFAULT_SKILL_NAMES) | set(available["skills"]))}
        if missing := [kind for kind, entries in selection.items() if not entries]:
            raise ValueError(f"默认资源目录缺少可导出的内容：{', '.join(missing)}")
        objects = build_export(manager, selection, builtin_skills=True)
        mirror = UserSettings(manager.data_root).value["pages"].get(MIRROR_SETTINGS_ID, {})
        defaults = {key: value for key, value in mirror.items() if key in MIRROR_DEFAULT_FIELDS}
        if defaults:
            files = {PAGE_DEFAULTS_FILE: json_bytes(defaults)}
            page_settings_config(MIRROR_SETTINGS_ID, files)
            objects.append({"kind": "page_settings", "id": MIRROR_SETTINGS_ID, "files": files})
            selection["page_settings"] = [MIRROR_SETTINGS_ID]
        save_package(objects, destination)
    return {kind: len(entries) for kind, entries in selection.items()}


def check_default_package(package):
    """接受旧默认包及可选的镜牢饰品与主题包默认配置。"""
    kinds = [obj["kind"] for obj in package.objects]
    if set(kinds) - {"page_settings"} != RESOURCE_KINDS or kinds.count("workflow") != 1:
        raise ValueError("默认资源包需要一个 Workflow、Assets、页面及 Skills。")
    for obj in package.objects:
        if obj["kind"] == "page_settings":
            files = package.files(obj)
            if set(files) != {PAGE_DEFAULTS_FILE}:
                raise ValueError("默认资源包只允许镜牢的饰品与主题包配置。")
            page_settings_config(obj["id"], files)


def is_empty_for_default_resources(root):
    """程序初始化产生的日志或空目录不妨碍首次安装。"""
    if any(UserSettings(root).value.values()):
        return False
    for name in ("manifests", "components", "assets", "pages", "skills", "page-resources"):
        directory = root / name
        if directory.is_symlink() or directory.is_junction() or directory.is_file():
            return False
        if any(path.name != ".DS_Store" and (not path.is_dir() or path.is_symlink() or path.is_junction())
               for path in directory.rglob("*")):
            return False
    return True


def import_default_resources(manager, path):
    """用户确认后复用分享导入；局部已有资源时提示用普通导入。"""
    if not is_empty_for_default_resources(manager.data_root):
        raise ValueError("已有用户资源，请使用常规分享包导入。")
    package = SharingPackage(path, manager.data_root)
    try:
        check_default_package(package)
        checks = inspect_objects(manager, package)
        errors = [message for check in checks.values() for message in check["errors"]]
        if errors:
            raise ValueError("\n".join(errors))
        if not is_empty_for_default_resources(manager.data_root):
            raise ValueError("导入期间出现了用户资源，请使用常规分享包导入。")
        result = import_selected(manager, package, checks, set(checks), asset_actions={}, reviewed={}, allow_unreviewed=True)
        if failed := result["failed"]:
            raise ValueError(f"已导入 {len(result['completed'])} 项，{failed['id']} 导入失败：{failed['error']}")
        return result
    finally:
        package.close()
