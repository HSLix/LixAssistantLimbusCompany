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
    content_stream, require_memory, require_disk, available_memory, open_image, image_preview, ResourceUnknown, checkpoint)
from .agent_log import FORMAT, LogStore
from .assets import AssetLibrary, asset_name
from .page_packages import (PageSnapshot, _relative, install_page_package, page_entries,
                            page_filename, real_directory, snapshot_page)
from .process_lock import ProcessLock
from .workflow_sharing import _prepare, import_workflow, inspect_workflow_import

KINDS = ("workflow", "assets", "pages", "history", "skills")


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


def page_declarations(package):
    """仅提取可证明的字面量声明；动态属性留为未验证，不为检查导入模块。"""
    source = content_bytes(package.files["page.py"])
    require_memory(len(source) * 12)
    tree = ast.parse(source)
    values = {}
    for name in ("PAGE_ID", "PAGE_NAME", "TASKS"):
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
        if len(nodes) != 1 or name != "TASKS" and (type(value) is not str or not value.strip()):
            raise ValueError(f"页面声明无效：{name}")
        if name == "TASKS":
            from .user_pages import validate_tasks
            value = validate_tasks(value)
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
            write_content(path, content)
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


def catalog(manager):
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
    return {"workflow": [item["manifest_id"] for item in manager.list_manifests()],
            "assets": sorted(names), "pages": sorted(handles), "history": histories,
            "skills": sorted(path.name for path in real_directory(root / "skills").iterdir()
                             if (path / "SKILL.md").exists()) if (root / "skills").exists() else []}


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
        run_id = event.get("run_id") if event.get("type") == "trial_started" else arguments.get("run_id") if event.get("type") == "repair_tool" and event.get("name") == "read_run_log" and isinstance(arguments, dict) else None
        if type(run_id) is int and run_id > 0:
            run_ids.add(run_id)
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
            source = root / "evidence" / (identity + ".png")
            if source.exists():
                files[f"runs/{run_id}/evidence/{identity.split('/')[1]}.png"] = FileContent.from_path(source)
            else:
                missing.append("evidence/" + identity + ".png")
    if missing:
        files["missing-evidence.json"] = json_bytes({"missing": sorted(missing)})
    validate_history(folder, log_root=log)
    return files


def build_export(manager, selection):
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
                if files is None:
                    raise ValueError(f"Skill 不存在：{identity}")
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
    for number, obj in enumerate(objects):
        fixed = {}
        for name, content in obj["files"].items():
            checkpoint()
            target = root / str(number) / name
            target.parent.mkdir(parents=True, exist_ok=True)
            write_content(target, content)
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
    temporary = None
    try:
        with work_file(dir=destination.parent, prefix=".sharing-", delete=False) as stream:
            temporary = Path(stream.name)
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("sharing.json", index)
            for number, obj in enumerate(objects):
                for name, content in sorted(obj["files"].items()):
                    with archive.open(f"objects/{number}/{name}", "w", force_zip64=True) as stream:
                        copy_content(content, stream)
        temporary.replace(destination)
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
                done = 0
                for obj in self.objects:
                    for name, record in obj["files"].items():
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
                        if size != record["size"] or hashed.hexdigest() != record["sha256"]:
                            raise ValueError("包文件内容哈希不符。")
                checkpoint(total, total, "")
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
                              changed_files=[name for name in sorted(set(old or {}) | set(files)) if (old or {}).get(name) != files.get(name)])
            elif kind == "pages":
                page_filename(identity)
                snapshot = PageSnapshot(files)
                result.update(declarations=page_declarations(snapshot), package=snapshot)
                target = installed_page(manager.data_root, identity)
                result.update(target=target, before=snapshot_page(target, freeze=False).sha256 if target.exists() else None)
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
            write_content(staged / name, content)
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
            write_content(path, FileContent.from_path(obj["root"] / name))
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


def import_selected(manager, package, checks, selected, *, asset_actions, reviewed, allow_unreviewed=False):
    """调用方确认后逐对象提交，失败停止；已成功对象保留并明确列未处理项。"""
    package.verify()
    require_disk([(manager.data_root, sum(record["size"] + 4096 for obj in package.objects if obj["number"] in selected for record in obj["files"].values()))])
    result = {"completed": [], "failed": None, "unprocessed": []}
    objects = [obj for obj in package.objects if obj["number"] in selected]
    page_errors = page_selection_errors(manager, package, checks, selected, reviewed)
    if page_errors:
        raise ValueError("; ".join(message for messages in page_errors.values() for message in messages))
    for index, obj in enumerate(objects):
        number, kind, identity = obj["number"], obj["kind"], obj["id"]
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
                    outcome = {"status": "skipped"}
                else:
                    if check["conflict"] and asset_actions.get(number) != "replace":
                        raise ValueError("Asset 冲突尚未选择替换或跳过。")
                    (replace_asset if kind == "assets" else replace_skill)(manager.data_root, identity, package.files(obj), check["before"])
                    outcome = {"status": "imported"}
            elif kind == "pages":
                if number not in reviewed and not allow_unreviewed:
                    raise ValueError("页面尚未 Review，也未明确确认跳过 Review 安装。")
                target = installed_page(manager.data_root, identity)
                before = snapshot_page(target, freeze=False).sha256 if target.exists() else None
                if before != check["before"]:
                    raise ValueError("本地页面已变化，请重新检查。")
                install_page_package(manager.data_root / "pages", Path(identity).stem, check["package"],
                                     replace=before is not None, legacy_filename=identity if target.is_file() else None)
                outcome = {"status": "installed", "reviewed": number in reviewed, "reload_required": True}
            else:
                outcome = {"path": str(import_history(manager.data_root, obj, check["content_hash"]))}
            result["completed"].append({"kind": kind, "id": identity, **outcome})
        except Exception as error:
            result["failed"] = {"kind": kind, "id": identity, "error": str(error)}
            result["unprocessed"] = [{"kind": item["kind"], "id": item["id"]} for item in objects[index + 1:]]
            break
    return result
