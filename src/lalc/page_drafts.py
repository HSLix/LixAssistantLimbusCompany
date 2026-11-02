"""Session 单文件页面草稿；专用文件边界和人工预览版本安装。"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile

from .runtime import _strict_json
from .user_pages import UserSettings, load_page_module


def page_filename(filename):
    """仅允许 Windows 也可用的顶层页面文件名。"""
    if (not isinstance(filename, str) or not filename or len(filename) > 128
            or filename.startswith(("_", ".")) or not filename.endswith(".py")
            or any(ord(char) < 32 or char in '/\\<>:"|?*' for char in filename)
            or not filename[:-3].strip(" .")
            or filename.split(".", 1)[0].rstrip(" ").upper() in {"CON", "PRN", "AUX", "NUL",
                *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}):
        raise ValueError("页面文件名必须是顶层普通 .py 文件名，不能使用保留名称。")
    return filename


def real_directory(path):
    """拒绝整个访问链上的符号链接，不通过 resolve 静默追踪。"""
    if any(part.is_symlink() for part in (path, *path.parents)) or path.exists() and not path.is_dir():
        raise ValueError("页面目录必须是真实目录，不能包含符号链接。")
    return path


def write_source(path, source, *, exclusive=False):
    """同目录临时文件提交；写入或替换失败保留旧源码。"""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".page-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(source)
        if exclusive:
            os.link(temporary, path)
        else:
            temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class MemorySettings:
    """预览专用配置；两侧各自复制，不持有正式文件写入路径。"""

    def __init__(self, value):
        self.value = deepcopy(value)

    def save(self, section, identity, value):
        self.value[section][identity] = deepcopy(_strict_json(value))


class PageDrafts:
    """仅访问当前 Construct Session 草稿及共享正式页；调用方持有 Session 锁。"""

    def __init__(self, session):
        session.check()
        if session.entry != "gui" or session.mode != "Construct":
            raise ValueError("页面工具仅允许 GUI Construct Session。")
        self.session = session
        self.root = real_directory(session.path / "page-drafts")
        self.installed = real_directory(session.host.service.data_root / "pages")

    def path(self, filename, scope="drafts"):
        page_filename(filename)
        directory = self.root if scope == "drafts" else self.installed if scope == "installed" else None
        if directory is None:
            raise ValueError("页面范围必须为 installed 或 drafts。")
        real_directory(directory)
        target = directory / filename
        if target.is_symlink() or target.exists() and not target.is_file():
            raise ValueError("页面必须是普通文件，不能是符号链接。")
        return target

    def metadata(self, filename):
        path = self.path(filename).with_suffix(".json")
        if path.is_symlink():
            raise ValueError("草稿元数据不能是符号链接。")
        value = json.loads(path.read_bytes())
        if (type(value) is not dict or set(value) != {"filename", "replace"}
                or value["filename"] != filename or type(value["replace"]) is not bool):
            raise ValueError("草稿目标元数据无效。")
        return value

    def list(self, scope="installed", offset=0, limit=50):
        if scope not in {"installed", "drafts"} or type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("无效页面范围或分页参数。")
        directory = real_directory(self.installed if scope == "installed" else self.root)
        names = sorted(path.name for path in directory.glob("*.py") if not path.name.startswith("_"))
        items = []
        for name in names[offset:offset + limit]:
            source = self.path(name, scope).read_bytes()
            items.append({"filename": name, "sha256": hashlib.sha256(source).hexdigest()})
        return {"scope": scope, "items": items, "next_offset": offset + limit if offset + limit < len(names) else None}

    def read(self, scope="installed", filename="", offset=0, limit=16000):
        """源码和正式配置只读分页，不为读取而导入页面。"""
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 16000:
            raise ValueError("无效读取分页参数。")
        if scope == "settings":
            if (self.session.host.service.data_root / "user-settings.json").is_symlink():
                raise ValueError("正式配置不能通过符号链接读取。")
            source = json.dumps(UserSettings(self.session.host.service.data_root).value, ensure_ascii=False, indent=2)
        else:
            source = self.path(filename, scope).read_bytes().decode("utf-8")
        result = {"scope": scope, "filename": filename, "source": source[offset:offset + limit],
                  "sha256": hashlib.sha256(source.encode()).hexdigest(),
                  "next_offset": offset + limit if offset + limit < len(source) else None}
        if scope == "drafts":
            result["target"] = self.metadata(filename)
        return result

    def create(self, filename, source=None, copy_from=None):
        """空白完整源码或复制正式页；新建不覆盖已有草稿或正式页。"""
        target = self.path(filename)
        if target.exists() or target.with_suffix(".json").exists() or target.with_suffix(".json").is_symlink():
            raise ValueError("草稿已存在，请使用 page_update。")
        if copy_from is not None:
            if source is not None or filename != copy_from:
                raise ValueError("复制正式页须沿用原文件名，且不能同时提供 source。")
            content = self.path(copy_from, "installed").read_bytes()
        else:
            if self.path(filename, "installed").exists():
                raise ValueError("正式文件已存在；请用 copy_from 创建替换草稿。")
            content = self.source_bytes(source)
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            write_source(target.with_suffix(".json"), json.dumps({"filename": filename, "replace": copy_from is not None}).encode(), exclusive=True)
            write_source(target, content, exclusive=True)
        except BaseException:
            target.with_suffix(".json").unlink(missing_ok=True)
            raise
        return self.read("drafts", filename)

    @staticmethod
    def source_bytes(source):
        """只检查完整源码语法，不执行或判断业务兼容。"""
        if not isinstance(source, str) or not source.strip():
            raise ValueError("必须提供完整 Python 页面源码。")
        compile(source, "<page-draft>", "exec")
        return source.encode("utf-8")

    def update(self, filename, source):
        self.metadata(filename)
        target = self.path(filename)
        if not target.is_file():
            raise ValueError("草稿不存在。")
        write_source(target, self.source_bytes(source))
        return self.read("drafts", filename)

    def snapshot(self, filename):
        """固定拟安装字节与目标身份；后续草稿修改不进入已有批准。"""
        target = self.metadata(filename)
        source = self.path(filename).read_bytes()
        return {**target, "source": source, "sha256": hashlib.sha256(source).hexdigest()}

    def check_registration(self, snapshot, page_id, task_id):
        """按当前正式注册检查必要冲突，不检查旧文件版本或自动合并。"""
        target = self.path(snapshot["filename"], "installed")
        if target.exists() and not snapshot["replace"]:
            raise ValueError("新增目标已存在，不能覆盖；请复制当前正式页重新审查。")
        for path in sorted(self.installed.glob("*.py")):
            if path == target or path.name.startswith("_"):
                continue
            checked = self.path(path.name, "installed")
            try:
                _, other_id, _, other_task = load_page_module(checked, checked.read_bytes())
            except Exception:
                # 与正式发现一致：加载失败的模块没有有效注册。
                continue
            if page_id == other_id or task_id is not None and task_id == other_task:
                raise ValueError(f"页面或任务 ID 冲突：{path.name} / {page_id} / {task_id}")

    def install(self, snapshot, page_id, task_id):
        """只由人工审查窗口调用；提交固定版本，不导入试填配置。"""
        self.check_registration(snapshot, page_id, task_id)
        self.installed.mkdir(parents=True, exist_ok=True)
        target = self.path(snapshot["filename"], "installed")
        write_source(target, snapshot["source"], exclusive=not snapshot["replace"])
        return {"status": "installed", "filename": snapshot["filename"], "sha256": snapshot["sha256"],
                "page_id": page_id, "task_id": task_id, "reload_required": True}
