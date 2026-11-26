"""分享对象的快照、受控 ZIP、静态审查及逐对象导入；不执行包内代码。"""

import ast
from contextlib import contextmanager
from datetime import datetime, timezone
from io import BytesIO
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import stat
import uuid
import zipfile

from .work_files import work_root, WorkDirectory, create_work_directory, work_file
from .file_content import (FileContent, content_hash, content_bytes, copy_content, write_content,
    content_stream, require_memory, require_disk, available_memory, open_image, image_preview, ResourceUnknown, checkpoint, file_transfers, transfer_file)
from .agent_log import FORMAT, LogStore
from .assets import AssetLibrary, asset_name
from .page_packages import (PageSnapshot, _relative, install_page_package, page_entries, page_entry,
                            page_filename, real_directory, snapshot_page)
from .user_pages import UserSettings
from .runtime import _strict_json
from .process_lock import ProcessLock
from .workflow_sharing import _prepare, import_workflow, inspect_workflow_import

KINDS = ("workflow", "assets", "pages", "history", "skills", "page_settings")
MIRROR_SETTINGS_ID = "mirror.settings"
MIRROR_DEFAULT_FIELDS = {"shop_gifts", "theme_packs"}
PAGE_DEFAULTS_FILE = "defaults.json"
GROUPED_SETTINGS_FILE = "grouped-settings.json"
OTHER_SETTINGS_GROUP = "__other__"


def digest(content):
    return content_hash(content)


def _git_metadata(parts):
    """Windows 大写折叠也需检查，不能让点号目录通过 Unicode 大小写别名带入 Git 配置。"""
    return any(part.casefold() == ".git" or part.upper() == ".GIT" for part in parts)


def strict_json(content):
    """拒绝重复 JSON 键及非有限数值，避免检查和使用阶段解释不一致。"""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"重复 JSON 键：{key}")
            result[key] = value
        return result
    def constant(value):
        raise ValueError(f"JSON 数值无效：{value}")
    content = content_bytes(content)
    require_memory(len(content) * 8)
    return json.loads(content, object_pairs_hook=pairs, parse_constant=constant)


def json_lines(path):
    """逐行解析，不因整段日志很大而全量加载；单行解析按当前内存检查。"""
    pending = bytearray()
    with path.open("rb") as stream:
        while chunk := stream.read(65536):
            checkpoint()
            pending.extend(chunk)
            require_memory(len(pending) * 12)
            while (end := pending.find(b"\n")) >= 0:
                line = bytes(pending[:end])
                del pending[:end + 1]
                if line.strip():
                    yield strict_json(line)
        if pending.strip():
            yield strict_json(pending)


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")


def files_version(files):
    return digest(json_bytes({name: digest(content) for name, content in sorted(files.items())}))


def read_file(path):
    real_directory(path.parent)
    return content_bytes(FileContent.from_path(path))


def tree_files(root):
    """只复制明确对象树的普通文件，不跟随链接，不包含临时／Python 缓存。"""
    root = real_directory(root)
    files = {}
    for path in root.rglob("*"):
        checkpoint()
        if path.is_symlink() or path.is_junction():
            raise ValueError("对象过大或包含链接。")
        relative = path.relative_to(root)
        if _git_metadata(relative.parts):
            raise ValueError("分享对象不能包含 Git 仓库元数据。")
        if (any(part == "__pycache__" or part.startswith((".pending-", ".page-install-", ".sharing-")) for part in relative.parts)
                or path.name == ".DS_Store" or path.suffix == ".pyc"):
            continue
        if path.is_dir():
            continue
        name = relative.as_posix()
        _relative(name)
        files[name] = FileContent.from_path(path)
    return files


def image_size(content):
    """检查图片真实格式，不解码全尺寸像素或使用固定像素门槛。"""
    with open_image(content) as image:
        image.verify()
        return image.format


def validate_assets(files):
    if "asset-tag.json" not in files:
        raise ValueError("Asset 缺少标签文件。")
    for name, content in files.items():
        if name == "asset-tag.json":
            continue
        if not re.fullmatch(r"[0-9a-f]{64}\.png", name) or digest(content) != name[:-4]:
            raise ValueError("Asset 图片文件名／内容哈希无效。")
        if image_size(content) != "PNG":
            raise ValueError("Asset 图片必须是 PNG。")
    tags = strict_json(files["asset-tag.json"])
    if type(tags) is not dict or any(not re.fullmatch(r"[0-9a-f]{64}", key) for key in tags):
        raise ValueError("Asset 标签格式无效。")
    for value in tags.values():
        AssetLibrary.tags(value)


def asset_files(data_root, name):
    """只读取本逻辑名的直接图片／标签，其他子逻辑名不在本组内。"""
    _relative(name)
    folder = real_directory(real_directory(data_root / "assets") / asset_name(name))
    if not folder.exists():
        return None
    files: dict[str, bytes | FileContent] = {path.name: FileContent.from_path(path) for path in sorted(folder.glob("*.png"))}
    tags = folder / "asset-tag.json"
    files["asset-tag.json"] = FileContent.from_path(tags) if tags.exists() or tags.is_symlink() else b"{}"
    return files


def page_declarations(package, *, settings=False):
    """仅提取可证明的字面量声明；动态属性留为未验证，不为检查导入模块。"""
    source = content_bytes(package.files["page.py"])
    require_memory(len(source) * 12)
    tree = ast.parse(source)
    values = {}
    names = ("PAGE_ID", "PAGE_NAME", "TASKS")
    if settings:
        names += ("PAGE_NAMES", "PAGE_SETTINGS_GROUPS")
    for name in names:
        nodes = []
        for node in tree.body:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and any(isinstance(target, ast.Name) and target.id == name for target in targets):
                nodes.append(node.value)
        if not nodes:
            continue
        try:
            value = ast.literal_eval(nodes[0])
        except (ValueError, TypeError):
            continue
        if len(nodes) != 1 or name in {"PAGE_ID", "PAGE_NAME"} and (type(value) is not str or not value.strip()):
            raise ValueError(f"页面声明无效：{name}")
        if name == "TASKS":
            from .user_pages import validate_tasks
            value = validate_tasks(value)
        elif name == "PAGE_SETTINGS_GROUPS":
            validate_settings_groups(value, allow_other=False)
        values[name] = value
    if values.get("PAGE_ID") in {"dashboard", "general-settings"}:
        raise ValueError("页面使用了宿主保留 ID。")
    return values


def installed_page(root, filename):
    page_filename(filename)
    directory = real_directory(root / "pages")
    legacy, package = directory / filename, real_directory(directory / Path(filename).stem)
    if legacy.is_symlink() or legacy.exists() and not legacy.is_file():
        raise ValueError("旧页面必须是普通文件。")
    if legacy.exists() and package.exists():
        raise ValueError("旧页面与目录同时占用目标。")
    return legacy if legacy.exists() else package


def skill_files(root, identity):
    """按顶层目录标识完整 Skill；拒绝链接并保留所有普通附属文件。"""
    if len(_relative(identity)) != 1:
        raise ValueError("Skill 名称必须是单层目录名。")
    target = real_directory(real_directory(root / "skills") / identity)
    if not target.exists():
        return None
    from .agent_skills import skill_files as enumerate_files
    diagnostics = []
    files = {path.as_posix(): content for path, content in enumerate_files(target, diagnostics).items()}
    if diagnostics:
        raise ValueError("Skill 包含链接或特殊文件。")
    validate_skill(files)
    return files


def validate_skill(files):
    """分享只检查结构，不执行 Skill 内容或附属脚本。"""
    if "SKILL.md" not in files:
        raise ValueError("Skill 缺少 SKILL.md。")


def replace_skill(root, identity, files, expected):
    """同盘准备后整目录替换，恢复失败时保留唯一旧副本。"""
    base = real_directory(root / "skills")
    base.mkdir(parents=True, exist_ok=True)
    target = base / identity
    work = Path(create_work_directory(dir=base, prefix=".sharing-skill-"))
    staged, backup = work / "new", work / "old"
    staged.mkdir()
    preserve = False
    try:
        for name, content in files.items():
            path = staged / name
            path.parent.mkdir(parents=True, exist_ok=True)
            write_content(path, content, name=name)
        current = skill_files(root, identity)
        if (files_version(current) if current is not None else None) != expected:
            raise ValueError("本地 Skill 已变化，请重新检查。")
        if current is not None:
            target.rename(backup)
        try:
            staged.rename(target)
        except BaseException:
            if backup.exists():
                try:
                    backup.rename(target)
                except BaseException as error:
                    preserve = True
                    raise OSError(f"Skill 恢复失败，旧副本保留于 {backup}") from error
            raise
    finally:
        if not preserve:
            shutil.rmtree(work)


def validate_settings_groups(groups, *, allow_other):
    """校验分组名称、字段归属和以条目为单位的合并路径。"""
    if type(groups) is not dict or not groups:
        raise ValueError("页面配置分组必须为非空对象。")
    fields = set()
    for key, group in groups.items():
        if (type(key) is not str or not key.strip() or (key == OTHER_SETTINGS_GROUP and not allow_other)
                or type(group) is not dict or set(group) != {"names", "fields"}):
            raise ValueError("页面配置分组声明无效。")
        names, rules = group["names"], group["fields"]
        if (type(names) is not dict or set(names) != {"zh_CN", "en_US"}
                or any(type(name) is not str or not name.strip() for name in names.values())
                or type(rules) is not dict or not rules or fields.intersection(rules)
                or any(type(field) is not str for field in rules)):
            raise ValueError("页面配置分组名称无效或字段重复。")
        for path in rules.values():
            if path is not None and (type(path) is not list or len(path) > 8
                                     or any(type(part) is not str for part in path)):
                raise ValueError("页面配置分组的条目合并路径无效。")
        fields.update(rules)
    return fields


def saved_settings_groups(manager, identities):
    """读取安装页的字面量声明，展示已保存字段。"""
    if not identities:
        return {}
    saved = UserSettings(manager.data_root).value["pages"]
    directory = real_directory(manager.data_root / "pages")
    result, seen = {}, set()
    for entry in page_entries(directory):
        try:
            declarations = page_declarations(PageSnapshot({"page.py": FileContent.from_path(page_entry(entry))}), settings=True)
        except (OSError, SyntaxError, ValueError):
            continue
        identity = declarations.get("PAGE_ID")
        if identity not in identities:
            continue
        if identity in seen:
            result.pop(identity, None)
            continue
        seen.add(identity)
        groups = declarations.get("PAGE_SETTINGS_GROUPS")
        if not groups or not (values := saved[identity]):
            continue
        active = {}
        for key, group in groups.items():
            if rules := {field: path for field, path in group["fields"].items() if field in values}:
                active[key] = {**group, "fields": rules}
        other = values.keys() - {field for group in active.values() for field in group["fields"]}
        if other:
            active[OTHER_SETTINGS_GROUP] = {"names": {"zh_CN": "其他配置", "en_US": "Other settings"},
                                            "fields": dict.fromkeys(sorted(other))}
        declared_names = declarations.get("PAGE_NAMES")
        names = {language: (declared_names or {}).get(language)
                 if type(declared_names) is dict else None for language in ("zh_CN", "en_US")}
        for language, name in names.items():
            if type(name) is not str or not name.strip():
                names[language] = declarations.get("PAGE_NAME", identity)
        result[identity] = {"groups": active, "settings": values, "names": names}
    return result


def page_settings_groups(identity, files):
    """读取新版局部配置并校验每个值只属于一个组。"""
    if type(identity) is not str or not identity.strip() or set(files) != {GROUPED_SETTINGS_FILE}:
        raise ValueError("局部页面配置的对象无效。")
    doc = strict_json(files[GROUPED_SETTINGS_FILE])
    if type(doc) is not dict or set(doc) != {"groups", "settings", "names"}:
        raise ValueError("局部页面配置结构无效。")
    if (type(doc["names"]) is not dict or set(doc["names"]) != {"zh_CN", "en_US"}
            or any(type(name) is not str or not name.strip() for name in doc["names"].values())):
        raise ValueError("局部页面配置的页面名称无效。")
    fields = validate_settings_groups(doc["groups"], allow_other=True)
    if type(doc["settings"]) is not dict or doc["settings"].keys() != fields:
        raise ValueError("局部页面配置与分组的字段不一致。")
    for group in doc["groups"].values():
        for field, path in group["fields"].items():
            if path is None:
                continue
            value = doc["settings"][field]
            for part in path:
                if type(value) is not dict:
                    break
                value = value.get(part, {})
            if type(value) is not dict:
                raise ValueError(f"页面配置字段 {field} 的合并位置必须是对象。")
    return _strict_json(doc)


def settings_group_change(group, incoming, current):
    """按声明计算局部更新及覆盖，名单等值整体替换，目录按条目替换。"""
    def merge(value, old, path):
        if path is None or type(old) is not dict:
            return value, settings_version(value) != settings_version(old)
        if not path:
            return {**old, **value}, any(key in old and json_bytes(old[key]) != json_bytes(new)
                                         for key, new in value.items())
        key, *remaining = path
        if key not in value:
            return merge(value, old, [])
        child, conflict = merge(value[key], old.get(key), remaining)
        conflict = key in old and conflict or any(
            name in old and json_bytes(old[name]) != json_bytes(new) for name, new in value.items() if name != key)
        return {**old, **value, key: child}, conflict

    update, overwrites = {}, False
    for field, path in group["fields"].items():
        value, conflict = merge(incoming[field], current.get(field), path)
        update[field] = value
        overwrites |= field in current and conflict
    return update, overwrites


def page_settings_config(identity, files, *, current=None):
    """验证整页配置或镜牢默认配置；后者只合并自身包含的字段。"""
    if type(identity) is not str or not identity.strip():
        raise ValueError("页面配置 PAGE_ID 必须为非空字符串。")
    if set(files) not in ({"settings.json"}, {PAGE_DEFAULTS_FILE}):
        raise ValueError("页面配置只允许一份 settings.json 或 defaults.json。")
    name, content = next(iter(files.items()))
    config = strict_json(content)
    if type(config) is not dict:
        raise ValueError("页面配置必须是 JSON 对象。")
    if name == PAGE_DEFAULTS_FILE:
        if (identity != MIRROR_SETTINGS_ID or not config or not config.keys() <= MIRROR_DEFAULT_FIELDS
                or any(type(value) is not dict for value in config.values())):
            raise ValueError("默认页面配置只允许镜牢的饰品与主题包配置。")
        config = {**(current or {}), **config}
    return _strict_json(config)


def settings_version(config):
    """区分缺失和空对象，并保留 JSON 布尔与数值的差异。"""
    return digest(json_bytes(config)) if config is not None else None


def catalog(manager, *, include_private=True):
    """枚举可显式选择的对象；不加载页面、Workflow 或可恢复 Session。"""
    root = manager.data_root
    assets = real_directory(root / "assets")
    names = set()
    if assets.exists():
        for path in assets.rglob("*"):
            if path.is_symlink() or path.is_junction():
                raise ValueError("Asset Library 包含链接。")
            if path.is_file() and (path.suffix == ".png" or path.name == "asset-tag.json"):
                names.add(path.parent.relative_to(assets).as_posix())
    pages = real_directory(root / "pages")
    handles = [path.name if path.parent == pages else path.parent.name + ".py" for path in page_entries(pages)]
    result = {"workflow": [item["manifest_id"] for item in manager.list_manifests()],
              "assets": sorted(names), "pages": sorted(handles),
              "skills": sorted(path.name for path in real_directory(root / "skills").iterdir()
                               if (path / "SKILL.md").exists()) if (root / "skills").exists() else []}
    if not include_private:
        return result
    histories = []
    for pattern in ("developer-sessions/*/log/events.jsonl", "developer-operations/*/*/events.jsonl",
                    "agent-interactions/*/*/events.jsonl"):
        paths = root.glob(pattern)
        if pattern.startswith("developer-sessions/"):
            paths = sorted(paths, key=lambda path: path.parent.parent.lstat().st_mtime, reverse=True)
        else:
            paths = sorted(paths)
        for path in paths:
            real_directory(path.parent)
            histories.append(path.parent.parent.relative_to(root).as_posix() if path.parent.name == "log"
                             else path.parent.relative_to(root).as_posix())
    return {**result, "history": histories, "page_settings": sorted(UserSettings(root).value["pages"])}


@contextmanager
def sharing_activity(service):
    """共享 GUI／CLI 活动边界；文件检查及提交期间禁止启动运行或 Agent。"""
    with service.activity("Sharing"), ProcessLock("game"):
        yield


def history_files(root, identity):
    _relative(identity)
    parts = identity.split("/")
    if not ((len(parts) == 2 and parts[0] == "developer-sessions") or
            (len(parts) == 3 and parts[0] in {"developer-operations", "agent-interactions"})):
        raise ValueError("对话不在支持的本地来源中。")
    folder = real_directory(root / identity)
    if parts[0] == "developer-sessions":
        with ProcessLock("candidate:" + str((folder / "candidate").resolve())):
            files = {"log/" + name: content for name, content in tree_files(folder / "log").items()}
            files.update({"candidate/" + name: content for name, content in tree_files(folder / "candidate").items()})
            baseline = strict_json(read_file(folder / ".candidate-baseline.json"))
            import base64
            for name, value in baseline["files"].items():
                _relative(name)
                files["baseline/" + name] = base64.b64decode(value, validate=True)
            files["baseline-origin.json"] = json_bytes({"manifest_id": baseline["manifest_id"]})
            if (folder / "page-drafts").exists():
                files.update({"page-drafts/" + name: content for name, content in tree_files(folder / "page-drafts").items()})
    else:
        files = {"log/" + name: content for name, content in tree_files(folder).items()}
    log = folder / "log" if parts[0] == "developer-sessions" else folder
    store, run_ids, missing = LogStore(log), set(), []
    for value in json_lines(log / "events.jsonl"):
        record = store.unpack(value, image_handler=lambda reference: {"image_file": reference["path"]}, max_bytes=(available_memory() or 0) // 16)
        if not isinstance(record, dict) or not isinstance(record.get("event"), dict):
            raise ValueError("对话事件格式无效。")
        event = record["event"]
        assert isinstance(event, dict)
        arguments = event.get("arguments", {})
        run_id = event.get("run_id") if event.get("type") == "trial_started" else arguments.get("run_id") if event.get("type") == "repair_tool" and event.get("name") in {"read_run_log", "search_run_logs"} and isinstance(arguments, dict) else None
        if type(run_id) is int and run_id > 0:
            run_ids.add(run_id)
        if event.get("type") == "repair_tool" and event.get("name") == "search_run_logs":
            for match in event.get("result", {}).get("details", {}).get("matches", []):
                identity = match.get("run_id")
                if type(identity) is int and identity > 0:
                    run_ids.add(identity)
    def evidence_ids(value):
        if isinstance(value, dict):
            if isinstance(value.get("evidence_id"), str):
                yield value["evidence_id"]
            for item in value.values():
                yield from evidence_ids(item)
        elif isinstance(value, list):
            for item in value:
                yield from evidence_ids(item)
    for run_id in sorted(run_ids):
        trace = root / "traces" / f"{run_id}.jsonl"
        if not trace.exists():
            missing.append(f"traces/{run_id}.jsonl")
            continue
        files[f"runs/{run_id}/trace.jsonl"] = FileContent.from_path(trace)
        state = root / "runs" / f"{run_id}.json"
        if state.exists():
            files[f"runs/{run_id}/state.json"] = FileContent.from_path(state)
        referenced = set()
        for record in json_lines(trace):
            referenced.update(evidence_ids(record))
        for identity in referenced:
            if not re.fullmatch(fr"{run_id}/[0-9]+", identity):
                continue
            from .run_logs import image_path
            source = image_path(root, run_id, {"evidence_id": identity})
            if source is not None and source.is_file():
                files[f"runs/{run_id}/evidence/{source.name}"] = FileContent.from_path(source)
            else:
                missing.append("evidence/" + identity)
    if missing:
        files["missing-evidence.json"] = json_bytes({"missing": sorted(missing)})
    validate_history(folder, log_root=log)
    return files


def build_export(manager, selection, *, builtin_skills=False, settings_groups=None):
    """冻结明确选择及必要文件；Workflow 不分析或附带 Assets，不做隐私扫描。"""
    objects = []
    for kind in KINDS:
        for identity in selection.get(kind, []):
            if kind == "workflow":
                prepared, _ = _prepare(manager, manager.data_root, identity)
                files = {f"manifests/{identity}.json": json_bytes(prepared.manifest)}
                files.update({f"components/{source.component_id[7:]}.py": source.content for source in prepared.sources.values()})
            elif kind == "assets":
                files = asset_files(manager.data_root, identity)
                if files is None:
                    raise ValueError(f"Asset 不存在：{identity}")
                validate_assets(files)
            elif kind == "skills":
                files = skill_files(manager.data_root, identity)
                if files is None and builtin_skills:
                    from .agent_skills import DEFAULT_SKILLS
                    files = skill_files(DEFAULT_SKILLS.parent, identity)
                if files is None:
                    raise ValueError(f"Skill 不存在：{identity}")
            elif kind == "page_settings":
                config = UserSettings(manager.data_root).value["pages"][identity]
                if settings_groups and identity in settings_groups:
                    names, groups = settings_groups[identity]["names"], settings_groups[identity]["groups"]
                    subset = {field: config[field] for group in groups.values() for field in group["fields"]}
                    doc = {"names": names, "groups": groups, "settings": subset}
                    files = {GROUPED_SETTINGS_FILE: json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8")}
                    page_settings_groups(identity, files)
                else:
                    files = {"settings.json": json_bytes(config)}
                    page_settings_config(identity, files)
            elif kind == "pages":
                path = installed_page(manager.data_root, identity)
                files = {"page.py": FileContent.from_path(path)} if path.is_file() else tree_files(path)
                page_declarations(PageSnapshot(files))
            else:
                files = history_files(manager.data_root, identity)
                files["snapshot-info.json"] = json_bytes({"captured_at": datetime.now(timezone.utc).isoformat(),
                    "source": identity, "note": "Candidate and page drafts are export-time snapshots, not per-round snapshots."})
            objects.append({"kind": kind, "id": identity, "files": files})
    _index(objects)
    require_disk([(work_root(), sum(len(content) for obj in objects for content in obj["files"].values()))])
    owner = WorkDirectory(prefix="lalc-export-")
    root = Path(owner.name).resolve()
    with file_transfers("Preparing export files", sum(len(obj["files"]) for obj in objects)):
        for number, obj in enumerate(objects):
            fixed = {}
            for name, content in obj["files"].items():
                checkpoint()
                target = root / str(number) / name
                target.parent.mkdir(parents=True, exist_ok=True)
                write_content(target, content, name=f"{obj['kind']}/{obj['id']}/{name}")
                fixed[name] = FileContent(target, len(content), digest(content), owner)
            obj["files"] = fixed
    return objects


def _index(objects):
    if not objects:
        raise ValueError("请选择分享对象。")
    entries, identities = [], set()
    for obj in objects:
        if obj["kind"] not in KINDS or (obj["kind"], obj["id"]) in identities:
            raise ValueError("对象类别无效或重复。")
        if obj["kind"] != "page_settings":
            _relative(obj["id"])
        identities.add((obj["kind"], obj["id"]))
        # 复用整包路径／Windows 别名检查，不把这一临时入口写入实际包。
        paths = {**obj["files"], "page.py": obj["files"].get("page.py", b"")}
        PageSnapshot(paths)
        files = {}
        for name, content in obj["files"].items():
            checkpoint()
            if _git_metadata(_relative(name)):
                raise ValueError("分享包不能包含 Git 元数据。")
            files[name] = {"size": len(content), "sha256": digest(content)}
        entries.append({"kind": obj["kind"], "id": obj["id"], "files": files})
    return {"format": "lalc-sharing", "version": 1, "objects": entries}


def save_package(objects, destination):
    """完整待提交 ZIP 写完才替换用户目标；失败保留此前文件。"""
    index = json_bytes(_index(objects))
    destination = Path(destination)
    real_directory(destination.parent)
    require_disk([(destination.parent, len(index) + sum(len(content) + 1024 for obj in objects for content in obj["files"].values()))])
    if destination.is_symlink():
        raise ValueError("保存目标不能是链接。")
    with file_transfers("Writing ZIP", sum(len(obj["files"]) for obj in objects)) as progress:
        temporary = None
        try:
            with work_file(dir=destination.parent, prefix=".sharing-", delete=False) as stream:
                temporary = Path(stream.name)
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("sharing.json", index)
                for number, obj in enumerate(objects):
                    for name, content in sorted(obj["files"].items()):
                        with archive.open(f"objects/{number}/{name}", "w", force_zip64=True) as stream:
                            copy_content(content, stream, name=f"{obj['kind']}/{obj['id']}/{name}")
                        progress.complete()
            progress.update(phase="Finishing…")
            temporary.replace(destination)
            progress.update(finished=True)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def staging_root():
    root = work_root() / "sharing"
    real_directory(root).mkdir(exist_ok=True)
    return root


def cleanup_staging():
    """只删除宿主管理且活动锁已释放的旧暂存，不跟随链接、不碰正式对象。"""
    for folder in staging_root().iterdir():
        if folder.is_symlink() or not folder.is_dir():
            continue
        try:
            identity = str(uuid.UUID(folder.name))
            with ProcessLock("sharing-stage:" + identity):
                shutil.rmtree(real_directory(folder))
        except (OSError, ValueError):
            continue


class SharingPackage:
    """索引及空间预检后流式校验到受控暂存；后续不再依赖原 ZIP。"""

    def __init__(self, path, data_root=None, *, allow_unknown_space=False):
        self.path = Path(path)
        self.objects = []
        self.identity = str(uuid.uuid4())
        self.stage_lock = ProcessLock("sharing-stage:" + self.identity)
        self.root = staging_root() / self.identity
        self.closed = False
        self.stage_lock.acquire()
        try:
            self.root.mkdir()
            if self.path.is_symlink() or not self.path.is_file():
                raise ValueError("ZIP 必须是普通文件。")
            # zipfile 在内存中建立中央目录；先按其实际字节数检查解析所需内存。
            with self.path.open("rb") as stream:
                ending = getattr(zipfile, "_EndRecData")(stream)
                if ending is None:
                    raise ValueError("ZIP 索引无效。")
                require_memory(ending[getattr(zipfile, "_ECD_SIZE")] * 12)
            with zipfile.ZipFile(self.path) as archive:
                members = archive.infolist()
                names, aliases, total = set(), {}, 0
                for info in members:
                    checkpoint(0, 0, info.filename)
                    _relative(info.filename)
                    if info.filename in names or info.flag_bits & 1 or info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                        raise ValueError("ZIP 成员重复、加密或压缩格式不受支持。")
                    mode = stat.S_IFMT(info.external_attr >> 16)
                    if mode not in {0, stat.S_IFREG} or info.is_dir():
                        raise ValueError("ZIP 含链接／特殊文件／目录成员。")
                    for index in range(1, len(info.filename.split("/")) + 1):
                        prefix = "/".join(info.filename.split("/")[:index])
                        if aliases.setdefault(prefix.casefold(), prefix) != prefix:
                            raise ValueError("ZIP 路径存在大小写别名。")
                    names.add(info.filename)
                    total += info.file_size
                if "sharing.json" not in names:
                    raise ValueError("ZIP 索引无效。")
                require_memory(archive.getinfo("sharing.json").file_size * 12)
                metadata = strict_json(archive.read("sharing.json"))
                if (type(metadata) is not dict or set(metadata) != {"format", "version", "objects"}
                        or metadata["format"] != "lalc-sharing" or type(metadata["version"]) is not int or metadata["version"] != 1
                        or type(metadata["objects"]) is not list or not metadata["objects"]):
                    raise ValueError("不支持的分享包格式。")
                expected, ids = {"sharing.json"}, set()
                for number, obj in enumerate(metadata["objects"]):
                    if (type(obj) is not dict or set(obj) != {"kind", "id", "files"}
                            or obj["kind"] not in KINDS or type(obj["id"]) is not str
                            or type(obj["files"]) is not dict or not obj["files"]):
                        raise ValueError("包对象结构无效。")
                    if (obj["kind"], obj["id"]) in ids:
                        raise ValueError("包对象身份重复。")
                    if obj["kind"] != "page_settings":
                        _relative(obj["id"])
                    ids.add((obj["kind"], obj["id"]))
                    PageSnapshot({**{name: b"" for name in obj["files"]}, "page.py": b""})
                    for name, record in obj["files"].items():
                        if _git_metadata(_relative(name)) or type(record) is not dict or set(record) != {"size", "sha256"}:
                            raise ValueError("包文件索引无效。")
                        member = f"objects/{number}/{name}"
                        expected.add(member)
                        if (member not in names or type(record["size"]) is not int or record["size"] < 0
                                or record["size"] != archive.getinfo(member).file_size
                                or not isinstance(record["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", record["sha256"])):
                            raise ValueError("文件缺失或大小／哈希声明无效。")
                    self.objects.append({**obj, "root": self.root / str(number), "number": number})
                if expected != names:
                    raise ValueError("ZIP 含未登记文件。")
                # 替换采用同盘 rename 备份旧对象；预算包含完整的新对象副本及目录开销。
                required = total + sum(len(info.filename.encode()) + 4096 for info in members)
                requirements = [(self.root, required)]
                if data_root is not None:
                    requirements.append((Path(data_root), required))
                require_disk(requirements, allow_unknown=allow_unknown_space)
                with file_transfers("Extracting files", sum(len(obj["files"]) for obj in self.objects)) as progress:
                    done = 0
                    for obj in self.objects:
                        progress.prefix = f"{obj['kind']}/{obj['id']}/"
                        for name, record in obj["files"].items():
                            transfer_file(0, record["size"], name)
                            checkpoint(done, total, name)
                            target = obj["root"] / name
                            target.parent.mkdir(parents=True, exist_ok=True)
                            hashed, size = hashlib.sha256(), 0
                            with archive.open(f"objects/{obj['number']}/{name}") as source, target.open("xb") as destination:
                                while chunk := source.read(1024 * 1024):
                                    checkpoint(done, total, name)
                                    size += len(chunk)
                                    if size > record["size"]:
                                        raise ValueError("解压数据超过声明大小。")
                                    hashed.update(chunk)
                                    destination.write(chunk)
                                    done += len(chunk)
                                    transfer_file(size, record["size"], name)
                            if size != record["size"] or hashed.hexdigest() != record["sha256"]:
                                raise ValueError("包文件内容哈希不符。")
                            transfer_file(size, record["size"], name, finished=True)
                            progress.complete()
                    checkpoint(total, total, "")
                progress.update(finished=True)
        except BaseException:
            self.close()
            raise

    def verify(self):
        for obj in self.objects:
            for name, record in obj["files"].items():
                checkpoint()
                content = FileContent.from_path(obj["root"] / name)
                if len(content) != record["size"] or digest(content) != record["sha256"]:
                    raise ValueError("暂存包内容已变化，请重新打开。")

    def files(self, obj):
        return {name: FileContent(obj["root"] / name, record["size"], record["sha256"]) for name, record in obj["files"].items()}

    def close(self):
        if not self.closed:
            self.closed = True
            try:
                if self.root.exists():
                    shutil.rmtree(real_directory(self.root))
            finally:
                self.stage_lock.release()


def inspect_objects(manager, package):
    """分类收集语义错误和目标冲突；某类有错不执行，也不妨碍取消选择该类。"""
    package.verify()
    results = {}
    for obj in package.objects:
        checkpoint()
        result = {"errors": [], "before": None}
        try:
            kind, identity = obj["kind"], obj["id"]
            files = package.files(obj)
            if kind == "workflow":
                require_memory(sum(record["size"] for record in obj["files"].values()) * 16)
                result.update(inspect_workflow_import(manager, obj["root"], identity))
                prepared, _ = _prepare(manager, obj["root"], identity)
                expected = {f"manifests/{identity}.json", *(f"components/{source.component_id[7:]}.py" for source in prepared.sources.values())}
                if set(files) != expected:
                    raise ValueError("Workflow 含非登记内容。")
            elif kind in {"assets", "skills"}:
                if kind == "assets":
                    asset_name(identity)
                    validate_assets(files)
                else:
                    if len(_relative(identity)) != 1:
                        raise ValueError("Skill 名称必须是单层目录名。")
                    validate_skill(files)
                old = (asset_files if kind == "assets" else skill_files)(manager.data_root, identity)
                result.update(before=files_version(old) if old is not None else None,
                              same=old == files, conflict=old is not None and old != files,
                              changed_files=file_changes(old or {}, files))
            elif kind == "page_settings":
                old = UserSettings(manager.data_root).value["pages"].get(identity)
                before = settings_version(old)
                if GROUPED_SETTINGS_FILE in files:
                    doc = page_settings_groups(identity, files)
                    groups = {}
                    for key, group in doc["groups"].items():
                        update, conflict = settings_group_change(group, doc["settings"], old or {})
                        local = {field: old[field] for field in update if old is not None and field in old}
                        groups[key] = {"names": group["names"], "fields": group["fields"], "current": local, "config": update,
                                       "conflict": conflict, "same": settings_version(local) == settings_version(update)}
                    result.update(groups=groups, names=doc["names"], before=before)
                else:
                    config = page_settings_config(identity, files, current=old)
                    after = settings_version(config)
                    result.update(config=config, current=old, before=before,
                                  same=before == after, conflict=old is not None and before != after)
            elif kind == "pages":
                page_filename(identity)
                snapshot = PageSnapshot(files)
                result.update(declarations=page_declarations(snapshot), package=snapshot)
                target = installed_page(manager.data_root, identity)
                old = snapshot_page(target, freeze=False) if target.exists() else None
                result.update(target=target, before=old.sha256 if old else None,
                              same=old is not None and old.sha256 == snapshot.sha256,
                              changed_files=file_changes(old.files if old else {}, files))
            else:
                _relative(identity)
                if any(not (name.startswith(("log/", "candidate/", "baseline/", "page-drafts/", "runs/")) or name in {"baseline-origin.json", "missing-evidence.json", "snapshot-info.json"}) for name in files):
                    raise ValueError("历史包含未登记类型的资料。")
                if strict_json(files.get("log/log-format.json", b"null")) != FORMAT or "log/events.jsonl" not in files:
                    raise ValueError("不支持的对话日志格式。")
                result["content_hash"] = files_version(files)
                # 先验证所有引用，不把只存在于本机的路径当作附件读取授权。
                validate_history(obj["root"])
        except InterruptedError:
            raise
        except Exception as error:
            result["errors"].append(str(error))
        results[obj["number"]] = result
    return results


def file_changes(old, new):
    """依内容比较文件，保留新增、修改和移除的类别。"""
    return {name: "added" if name not in old else "removed" if name not in new else "modified"
            for name in sorted(old.keys() | new.keys())
            if name not in old or name not in new or content_hash(old[name]) != content_hash(new[name])}


def validate_history(root, *, output=None, log_root=None):
    """展开对话内受控引用并生成可读分块；原始日志完整保留且不能恢复执行。"""
    log = log_root if log_root is not None else root / "log"
    store = LogStore(log)
    count = 0
    images = {}
    def image_reference(reference):
        key = (reference["path"], reference["sha256"])
        if key in images:
            return images[key]
        path = store._path(reference["path"])
        content = FileContent.from_path(path)
        if digest(content) != reference["sha256"]:
            raise ValueError("对话图片引用哈希不符。")
        result = {"image_file": "log/" + reference["path"], "sha256": reference["sha256"]}
        if output is not None and len(content) > 2 * 1024 * 1024:
            previews = output / "images"
            previews.mkdir(exist_ok=True)
            target = previews / (reference["sha256"] + ".jpg")
            if not target.exists():
                try:
                    target.write_bytes(image_preview(content))
                except InterruptedError:
                    raise
                except (OSError, ValueError):
                    images[key] = result
                    return result
            result["scaled_preview"] = "readable/images/" + target.name
        images[key] = result
        return result
    paths = [path for path in sorted(root.rglob("*")) if path.suffix in {".json", ".jsonl", ".py", ".txt", ".md"}
             and "objects" not in path.relative_to(root).parts and "readable" not in path.relative_to(root).parts]
    for path in paths:
        checkpoint()
        in_log = path.is_relative_to(log)
        parts = path.relative_to(log).parts if in_log else ()
        raw_snapshot = any(part in {"baseline", "original", "final"} or part.endswith("-page-package") for part in parts[:-1])
        protocol = in_log and not raw_snapshot and path.suffix in {".json", ".jsonl"}
        if protocol:
            values = json_lines(path) if path.suffix == ".jsonl" else [strict_json(FileContent.from_path(path))]
        elif output is None:
            continue
        else:
            def raw_chunks():
                with path.open("r", encoding="utf-8", errors="replace") as stream:
                    while text := stream.read(200000):
                        checkpoint()
                        yield text
            values = raw_chunks()
        for value in values:
            checkpoint()
            expanded = store.unpack(value, image_handler=image_reference, max_bytes=(available_memory() or 0) // 16) if protocol else value
            text = expanded if isinstance(expanded, str) else json.dumps(expanded, ensure_ascii=False, indent=2)
            if output is not None:
                for offset in range(0, len(text), 200000):
                    checkpoint()
                    block = f"Source: {path.relative_to(root).as_posix()}\n\n" + text[offset:offset + 200000]
                    require_disk([(output, len(block.encode("utf-8")))])
                    count += 1
                    (output / f"{count:06d}.txt").write_text(block, encoding="utf-8")
    return count


def replace_asset(root, identity, files, expected):
    """事务化替换直属图片／标签，保留所有其他子逻辑名目录。"""
    current = asset_files(root, identity)
    if (files_version(current) if current is not None else None) != expected:
        raise ValueError("本地 Asset 已变化，请重新检查。")
    require_disk([(root, sum(len(content) for content in files.values()))])
    base = real_directory(root / "assets")
    base.mkdir(parents=True, exist_ok=True)
    target = real_directory(base / identity)
    target.mkdir(parents=True, exist_ok=True)
    work = Path(create_work_directory(dir=base, prefix=".sharing-asset-"))
    backup, staged = work / "old", work / "new"
    backup.mkdir()
    staged.mkdir()
    written, moved, success = [], [], False
    try:
        for name, content in files.items():
            write_content(staged / name, content, name=name)
        originals = list(target.glob("*.png")) + ([target / "asset-tag.json"] if (target / "asset-tag.json").exists() else [])
        for path in originals:
            path.rename(backup / path.name)
            moved.append(path.name)
        for name in files:
            (staged / name).rename(target / name)
            written.append(name)
        success = True
    except BaseException:
        try:
            for name in written:
                (target / name).unlink()
            for name in moved:
                (backup / name).rename(target / name)
        except OSError as error:
            raise OSError(f"Asset 恢复失败，原文件保留在 {backup}") from error
        raise
    finally:
        if success or not any(backup.iterdir()):
            try:
                shutil.rmtree(work)
            except OSError:
                logging.getLogger(__name__).warning("Asset 工作目录未清理：%s", work, exc_info=True)
        if current is None and not success and target.exists() and not any(target.iterdir()):
            target.rmdir()


def import_history(root, obj, content_hash):
    parent = real_directory(real_directory(root / "knowledge") / "imported-agent-history")
    parent.mkdir(parents=True, exist_ok=True)
    target = real_directory(parent / content_hash)
    if target.exists():
        for name, record in obj["files"].items():
            if digest(FileContent.from_path(target / name)) != record["sha256"]:
                raise ValueError("同名历史资料已被修改，不能覆盖。")
        return target
    with WorkDirectory(dir=parent, prefix=".sharing-history-") as temporary:
        folder = Path(temporary) / "history"
        folder.mkdir()
        for name in obj["files"]:
            path = folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            write_content(path, FileContent.from_path(obj["root"] / name), name=name)
        readable = folder / "readable"
        if readable.exists():
            raise ValueError("历史来源占用了宿主可读索引目录。")
        readable.mkdir()
        count = validate_history(folder, output=readable)
        (folder / "README.md").write_text(f"# Imported Agent history\n\nUntrusted read-only reference. No Session restore or tool replay.\nSource: {obj['id']}\n\nFull original files are retained. Read readable/000001.txt through {count:06d}.txt in order. Image references are relative to this folder. Candidate and baseline files are export-time/reference snapshots.\n", encoding="utf-8")
        folder.rename(target)
    return target


def page_selection_errors(manager, package, checks, selected, reviewed):
    """静态比较本地及选中页面的可知身份，不为未 Review 页面执行源码。"""
    local = []
    for entry in page_entries(manager.data_root / "pages"):
        try:
            declarations = page_declarations(PageSnapshot({"page.py": read_file(entry)}))
        except (OSError, ValueError, SyntaxError):
            declarations = {}
        local.append((entry, declarations))
    errors, chosen = {}, []
    for obj in package.objects:
        number = obj["number"]
        if number not in selected or obj["kind"] != "pages" or checks[number]["errors"]:
            continue
        check = checks[number]
        declarations = dict(check["declarations"])
        approval = reviewed.get(number)
        if approval and approval["sha256"] == check["package"].sha256 and approval["before"] == check["before"]:
            declarations.update(PAGE_ID=approval["page_id"], TASKS=approval["tasks"])
        target = check["target"] if check["target"].is_file() else check["target"] / "page.py"
        for other, values in [*local, *chosen]:
            if other == target:
                continue
            if declarations.get("PAGE_ID") is not None and declarations.get("PAGE_ID") == values.get("PAGE_ID"):
                errors.setdefault(number, []).append(f"PAGE_ID 冲突：{other}")
            if {task["id"] for task in declarations.get("TASKS", [])} & {task["id"] for task in values.get("TASKS", [])}:
                errors.setdefault(number, []).append(f"TASKS 冲突：{other}")
        chosen.append((target, declarations))
    return errors


def import_selected(manager, package, checks, selected, *, asset_actions, reviewed, allow_unreviewed=False,
                    settings_groups=None, confirm_settings_overwrites=False):
    """调用方确认后逐对象提交，失败停止；已成功对象保留并明确列未处理项。"""
    package.verify()
    require_disk([(manager.data_root, sum(record["size"] + 4096 for obj in package.objects if obj["number"] in selected for record in obj["files"].values()))])
    result = {"completed": [], "failed": None, "unprocessed": []}
    objects = [obj for obj in package.objects if obj["number"] in selected]
    page_errors = page_selection_errors(manager, package, checks, selected, reviewed)
    if page_errors:
        raise ValueError("; ".join(message for messages in page_errors.values() for message in messages))
    with file_transfers("Installing files", sum(len(obj["files"]) for obj in objects)) as progress:
        for index, obj in enumerate(objects):
            number, kind, identity = obj["number"], obj["kind"], obj["id"]
            progress.prefix = f"{kind}/{identity}/"
            progress.update(phase="Installing files", name=progress.prefix, done=0, size=0, file_finished=False)
            check = checks[number]
            try:
                if check["errors"]:
                    raise ValueError("; ".join(check["errors"]))
                if kind == "workflow":
                    outcome = import_workflow(manager, obj["root"], identity, manifest_id=check["manifest_id"], manifest_sha256=check["manifest_sha256"])
                elif kind in {"assets", "skills"}:
                    current = (asset_files if kind == "assets" else skill_files)(manager.data_root, identity)
                    if (files_version(current) if current is not None else None) != check["before"]:
                        raise ValueError("本地 Asset 已变化，请重新检查。")
                    if check["same"] or check["conflict"] and asset_actions.get(number) == "skip":
                        for name, record in obj["files"].items():
                            transfer_file(record["size"], record["size"], name, finished=True)
                        outcome = {"status": "skipped"}
                    else:
                        if check["conflict"] and asset_actions.get(number) != "replace":
                            raise ValueError("Asset 冲突尚未选择替换或跳过。")
                        (replace_asset if kind == "assets" else replace_skill)(manager.data_root, identity, package.files(obj), check["before"])
                        outcome = {"status": "imported"}
                elif kind == "page_settings":
                    store = UserSettings(manager.data_root)
                    current = store.value["pages"].get(identity)
                    if settings_version(current) != check["before"]:
                        raise ValueError("本地页面配置已变化，请重新检查。")
                    files = package.files(obj)
                    if GROUPED_SETTINGS_FILE in files:
                        doc = page_settings_groups(identity, files)
                        chosen = (settings_groups or {}).get(number, set())
                        if not chosen or not chosen <= doc["groups"].keys():
                            raise ValueError("请选择有效的页面配置分组。")
                        config = dict(current or {})
                        for key in sorted(chosen):
                            update, conflict = settings_group_change(doc["groups"][key], doc["settings"], current or {})
                            if conflict and not confirm_settings_overwrites:
                                raise ValueError("页面配置分组覆盖尚未确认。")
                            config.update(update)
                    else:
                        config = page_settings_config(identity, files, current=current)
                    if settings_version(current) == settings_version(config) or check.get("conflict") and asset_actions.get(number) == "skip":
                        outcome = {"status": "skipped"}
                    else:
                        if check.get("conflict") and asset_actions.get(number) != "replace":
                            raise ValueError("页面配置冲突尚未选择替换或跳过。")
                        store.save("pages", identity, config)
                        outcome = {"status": "imported", "reload_required": True}
                    name, record = next(iter(obj["files"].items()))
                    transfer_file(record["size"], record["size"], name, finished=True)
                elif kind == "pages":
                    if number not in reviewed and not allow_unreviewed:
                        raise ValueError("页面尚未核验，也未明确确认跳过核验并安装。")
                    target = installed_page(manager.data_root, identity)
                    before = snapshot_page(target, freeze=False).sha256 if target.exists() else None
                    if before != check["before"]:
                        raise ValueError("本地页面已变化，请重新检查。")
                    install_page_package(manager.data_root / "pages", Path(identity).stem, check["package"],
                                         replace=before is not None, legacy_filename=identity if target.is_file() else None)
                    outcome = {"status": "installed", "reviewed": number in reviewed, "reload_required": True}
                else:
                    outcome = {"path": str(import_history(manager.data_root, obj, check["content_hash"]))}
                progress.complete(len(obj["files"]), skipped=outcome.get("status") == "skipped")
                result["completed"].append({"kind": kind, "id": identity, **outcome})
            except Exception as error:
                result["failed"] = {"kind": kind, "id": identity, "error": str(error)}
                result["unprocessed"] = [{"kind": item["kind"], "id": item["id"]} for item in objects[index + 1:]]
                break
        if result["failed"] is None:
            progress.update(finished=True)
    return result
