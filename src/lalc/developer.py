"""开发工具共享宿主：草稿、固定基线、活动互斥与人工截图保存。"""

from __future__ import annotations

import ast
import base64
import difflib
import json
from pathlib import Path
import shutil
import tempfile
from contextlib import contextmanager

from .process_lock import ProcessLock

from .focused import FocusedAutomationSession, WindowError
from .runtime import atomic_write_json, staging_directory


def candidate_files(candidate: Path) -> dict[str, bytes]:
    """只读取真实候选目录内的已有普通文件，拒绝符号链接。"""
    if candidate.is_symlink() or not candidate.is_dir():
        raise ValueError("请先明确初始化 Candidate。")
    result = {}
    for path in sorted(candidate.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Candidate 不允许符号链接：{path.name}")
        if path.is_file():
            result[path.relative_to(candidate).as_posix()] = path.read_bytes()
    return result


def editable_files(candidate: Path) -> tuple[str, ...]:
    """冻结本轮全部已有文件；不按校验或 Manifest 引用过滤，已有 Python Plan 可编辑。"""
    return tuple(candidate_files(candidate))


def file_diff(original: dict[str, bytes], current: dict[str, bytes]) -> str:
    """比较真实文件，含增删与无法解码的文件，不猜测模型的修改声明。"""
    parts = []
    for name in sorted(original.keys() | current.keys()):
        before, after = original.get(name), current.get(name)
        if before == after:
            continue
        try:
            parts.extend(difflib.unified_diff(
                (before or b"").decode("utf-8").splitlines(keepends=True),
                (after or b"").decode("utf-8").splitlines(keepends=True),
                fromfile=f"base/{name}" if before is not None else "/dev/null",
                tofile=f"candidate/{name}" if after is not None else "/dev/null"))
        except UnicodeError:
            parts.append(f"Binary file changed: {name}\n")
        if before is None and after == b"" or after is None and before == b"":
            parts.append(f"{'Added' if before is None else 'Deleted'} empty file: {name}\n")
    return "".join(parts)


class DeveloperHost:
    """GUI/CLI 共用服务；宿主元数据不进入正式 Manifest 或候选授权集合。"""

    def __init__(self, service, candidate: Path):
        self.service = service
        self.manager = service.manifest_manager
        self.candidate = Path(candidate).absolute()
        self.metadata = self.candidate.parent / f".{self.candidate.name}-baseline.json"
        self.conversation = None
        self.preview = None
        self.monitored_window = None
        self.secrets = {}

    def candidate_lock(self):
        """同一草稿的跨进程锁；不受运行数据目录影响。"""
        return ProcessLock("candidate:" + str(self.candidate.resolve()))

    @contextmanager
    def candidate_activity(self, name):
        """同时检查本服务活动与其他进程对同一草稿的占用。"""
        with self.service.activity(name), self.candidate_lock():
            yield

    @property
    def secret(self):
        """当前已保存平台的临时凭据，不跨平台复用。"""
        from .agent_settings import load_settings
        return self.secrets.get(load_settings(self.service.data_root)["provider"])

    @secret.setter
    def secret(self, value):
        from .agent_settings import load_settings
        provider = load_settings(self.service.data_root)["provider"]
        if value is None:
            self.secrets.pop(provider, None)
        else:
            self.secrets[provider] = value

    def initialize(self, manifest_id: str | None, *, replace: bool = False) -> None:
        """先完整物化；替换或元数据保存失败时恢复原 Candidate 和基线。"""
        with self.candidate_activity("Candidate 初始化"):
            if self.candidate.is_symlink() or (self.candidate.exists() and not self.candidate.is_dir()):
                raise ValueError("Candidate must be a real directory")
            if self.candidate.exists() and any(self.candidate.iterdir()) and not replace:
                raise ValueError("替换非空 Candidate 需要明确确认；使用 lalc init --replace，或先执行 lalc clear。")
            self.candidate.parent.mkdir(parents=True, exist_ok=True)
            with staging_directory(self.candidate.parent, prefix=".lalc-candidate-") as directory:
                prepared, backup = Path(directory) / "prepared", Path(directory) / "previous"
                errors = self.manager.initialize_candidate(prepared, manifest_id=manifest_id)
                if errors:
                    raise ValueError(json.dumps([error.as_dict() for error in errors], ensure_ascii=False))
                source = manifest_id if manifest_id is not None else self.manager.default_manifest_id()
                metadata = {"manifest_id": source, "files": {
                    name: base64.b64encode(value).decode() for name, value in candidate_files(prepared).items()}}
                from .agent_repair import RepairConversation
                conversation = RepairConversation(self)
                existed = self.candidate.exists()
                if existed:
                    self.candidate.replace(backup)
                try:
                    prepared.replace(self.candidate)
                    atomic_write_json(self.metadata, metadata)
                except BaseException:
                    if self.candidate.exists():
                        shutil.rmtree(self.candidate)
                    if existed:
                        backup.replace(self.candidate)
                    raise
            self.conversation = conversation

    def add_source(self, section, filename, logical_name, source, checkpoint):
        """专用新增：先检查源码，再提交文件与登记；提交前失败回退，不导入候选。"""
        files = candidate_files(self.candidate)
        path = Path(filename)
        if (not isinstance(filename, str) or not filename or "\\" in filename or ":" in filename
                or path.is_absolute() or path.as_posix() != filename or ".." in path.parts
                or "plan.json" in path.parts or path.suffix != ".py" or filename in files):
            raise ValueError("新增文件必须是未占用的 Candidate 内相对 .py 路径。")
        if section not in {"components", "recovery_rules"}:
            raise ValueError("未知 Manifest 分区。")
        if not isinstance(logical_name, str) or not self.manager._valid_logical_name(logical_name):
            raise ValueError("逻辑名必须由点分隔的 Python 标识符组成。")
        manifest_path = self.candidate / "manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        if (not isinstance(manifest, dict) or manifest.get("schema_version") != 2
                or any(not isinstance(manifest.get(key), dict) for key in ("components", "recovery_rules"))):
            raise ValueError("Candidate Manifest 必须包含 components 和 recovery_rules 对象。")
        if any(logical_name in manifest[key] for key in ("components", "recovery_rules")):
            raise ValueError("逻辑名已存在，不能覆盖。")
        if not isinstance(source, str) or not source.strip():
            raise ValueError("必须提供完整 Python 源码。")
        tree = ast.parse(source, filename=filename)
        errors = []
        if section == "components":
            role = self.manager._validate_component_source(tree, logical_name, errors)
            if role == "automation_plan":
                raise ValueError("Plan 由初始化提供；Agent 只能编辑已有 Plan，不能新增 Plan。")
        else:
            self.manager._validate_recovery_source(tree, logical_name, errors)
        self.manager._validate_source_structure(tree, [(section, logical_name)], errors)
        if errors:
            raise ValueError(json.dumps([error.as_dict() for error in errors], ensure_ascii=False))
        target = self.candidate / path
        if not target.resolve().is_relative_to(self.candidate.resolve()):
            raise ValueError("新增文件不能越出 Candidate。")
        manifest[section][logical_name] = {"source_path": filename}
        directories = []
        parent = target.parent
        while not parent.exists():
            directories.append(parent)
            parent = parent.parent
        created = False
        # Manifest 临时文件放在 Candidate 外，失败不会污染快照；replace 是提交点。
        with tempfile.TemporaryDirectory(dir=self.candidate.parent, prefix=".lalc-add-") as directory:
            prepared = Path(directory) / "manifest.json"
            prepared.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            try:
                checkpoint()
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("x", encoding="utf-8", newline="") as stream:
                    created = True
                    stream.write(source)
                checkpoint()
                prepared.replace(manifest_path)
            except BaseException:
                if created:
                    target.unlink()
                for folder in directories:
                    if folder.exists():
                        folder.rmdir()
                raise
        return {"filename": filename, "logical_name": logical_name, "section": section}

    def baseline(self) -> dict[str, bytes]:
        metadata = json.loads(self.metadata.read_text(encoding="utf-8"))
        return {name: base64.b64decode(content) for name, content in metadata["files"].items()}

    def diff(self) -> str:
        with self.candidate_activity("Candidate Diff"):
            return file_diff(self.baseline(), candidate_files(self.candidate))

    def validate(self) -> dict:
        with self.candidate_activity("Candidate 校验"):
            if getattr(self, "session", None) and self.conversation:
                self.session.restore(self.conversation)
            errors = self.manager.validate(self.candidate / "manifest.json")
            result = {"ok": not errors, "errors": [error.as_dict() for error in errors]}
            if self.conversation:
                self.conversation.add_validation(result)
            return result

    def publish(self) -> str:
        with self.candidate_activity("Candidate 发布"):
            if getattr(self, "session", None) and self.conversation:
                self.session.restore(self.conversation)
            result = self.manager.publish(self.candidate / "manifest.json")
            if not result.ok:
                raise ValueError(json.dumps([error.as_dict() for error in result.errors], ensure_ascii=False))
            if getattr(self, "session", None) and self.conversation:
                self.conversation.log.record({"type": "manual_publish", "manifest_id": result.loaded.manifest_id})
                self.conversation.append_user({"role": "user", "content": [{"type": "text", "text":
                    "开发者已 Publish 完整草稿，Manifest ID：" + result.loaded.manifest_id + "；Default 未改变。"}], "timestamp": 0})
                self.conversation.log.save_json("context.json", self.conversation.history)
            return result.loaded.manifest_id

    def new_conversation(self):
        with self.candidate_activity("新对话"):
            from .agent_repair import RepairConversation
            candidate_files(self.candidate)
            if not self.metadata.exists():
                raise ValueError("请先明确初始化 Candidate，保存固定基线。")
            self.conversation = RepairConversation(self)
            return self.conversation

    def capture(self, *, update_preview=True):
        """固定原始截图；默认更新素材预览，OCR 可独立取图，不写 Asset。"""
        with self.service.activity("Capture 截图"):
            session = FocusedAutomationSession(self.service._window_platform(), lambda *_: None)
            session.capture()
            snapshot = (session.image, session.size, session.observation)
            if update_preview:
                self.preview = snapshot
            return snapshot

    def recognize_preview(self, snapshot, region=None):
        """只识别已固定的截图；不连接窗口，不替换 Capture 预览。"""
        from .ocr import ocr_service
        from .recognition import client_image
        with self.service.activity("OCR"):
            pixels, size, _ = snapshot
            return ocr_service.recognize(client_image(pixels, size), region=region, checkpoint=lambda: None)

    def match_crop_preview(self, snapshot, region):
        """以固定截图裁剪模板并同图匹配；不截图、不写入素材库。"""
        from .recognition import client_image, decode_image, detect_template
        with self.service.activity("Capture"):
            pixels, size, _ = snapshot
            content, _ = self.service.asset_library.crop_content(pixels, size, region)
            matches = detect_template(client_image(pixels, size), decode_image(content), threshold=0.8)
            return content, matches

    def template_catalog(self):
        """只扫描目录和文件状态，不读图片；不跟随素材库内的符号链接。"""
        import os
        root = self.service.asset_library.root
        if root.is_symlink():
            raise ValueError("Asset Library 不允许符号链接。")
        signature, images = [], []
        def failed(error):
            raise error
        if not root.exists():
            return (), []
        for directory, folders, files in os.walk(root, followlinks=False, onerror=failed):
            folder_names, file_names = set(folders), set(files)
            for name in ["", *sorted(folders), *sorted(files)]:
                path = Path(directory) / name
                if name and path.suffix != ".png" and name != "asset-tag.json" and name not in folder_names:
                    continue
                if path.is_symlink():
                    raise ValueError(f"Asset Library 不允许符号链接：{path.name}")
                stat = path.stat()
                relative = path.relative_to(root).as_posix()
                signature.append((relative, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino))
                if name in file_names and path.suffix == ".png":
                    images.append(relative)
        return tuple(sorted(signature)), sorted(images)

    def template_preview(self, name, digest):
        """按需验哈希读取单图，不能借模板选择访问库外路径。"""
        from .assets import asset_name
        return self.service.asset_library.read({"path": f"{asset_name(name)}/{digest}.png", "sha256": digest})

    def match_template_preview(self, snapshot, name, digest=None, *, priority_tags=None,
                               region=None, threshold=0.9, nms=True, nms_iou_threshold=0.5):
        """只在固定截图上运行正式算法；不连接窗口，不写使用索引或 Trace。"""
        from .recognition import client_image, decode_image, detect_template
        from .assets import asset_name
        asset_name(name)
        with self.service.activity("Template Match"):
            pixels, size, observation = snapshot
            options = dict(region=region, threshold=threshold, nms=nms, nms_iou_threshold=nms_iou_threshold)
            if digest is None:
                return self.service.asset_library.match(name, pixels, size, run_id=None,
                    observation=observation, emit=lambda *_: None, priority_tags=priority_tags,
                    record_usage=False, **options)
            content = self.template_preview(name, digest)
            matches = detect_template(client_image(pixels, size), decode_image(content), **options)
            return [{**match, "path": f"{name}/{digest}.png", "sha256": digest,
                     "centerxy": (match["x"] + match["width"] // 2,
                                  match["y"] + match["height"] // 2)} for match in matches]

    def resize_window(self, width=1280, height=720):
        """人工尺寸调整与 Run/Agent 互斥；不重截或替换已固定的预览。"""
        with self.service.activity("Capture 调整窗口尺寸"):
            platform = self.service._window_platform()
            windows = platform.find_windows()
            if len(windows) != 1:
                raise WindowError(f"Expected one Limbus Company window, found {len(windows)}.")
            return platform.resize_client(windows[0], width, height)

    def save_crop(self, name, region, tags, *, preview=None):
        with self.service.activity("Capture 保存"):
            snapshot = self.preview if preview is None else preview
            if snapshot is None:
                raise ValueError("请先截图。")
            pixels, size, observation = snapshot
            return self.service.asset_library.save_crop(name, pixels, size, region, run_id=None,
                                                        observation=observation, tags=tags)

    def refresh_coordinates(self):
        self.monitored_window = None
        platform = self.service._window_platform()
        matches = platform.find_windows()
        if len(matches) != 1:
            raise WindowError(f"Expected one Limbus Company window, found {len(matches)}.")
        info = platform.window_info(matches[0])
        self.monitored_window = (matches[0], info["process_id"])
        return self.coordinates()

    def coordinates(self):
        """被动观察不调用 focus；窗口失效后必须显式刷新。"""
        if self.monitored_window is None:
            raise WindowError("请手动刷新窗口。")
        try:
            platform = self.service._window_platform()
            hwnd, process_id = self.monitored_window
            if platform.find_windows() != [hwnd]:
                raise WindowError("窗口无法唯一定位，请手动刷新。")
            info = platform.window_info(hwnd)
            if (not info["valid"] or not info["visible"] or info["minimized"]
                    or info["width"] <= 0 or info["height"] <= 0 or info["process_id"] != process_id):
                raise WindowError("窗口已失效，请手动刷新。")
            return platform.cursor_position(hwnd)
        except Exception:
            self.monitored_window = None
            raise
