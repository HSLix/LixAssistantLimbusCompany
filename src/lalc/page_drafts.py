"""Session 整包页面草稿；兼容旧单文件并保留专用人工安装边界。"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile

from .runtime import _strict_json
from .user_pages import UserSettings, check_page_registration
from .page_packages import (PageSnapshot, _relative, install_page_package, page_entries, page_entry,
                            page_filename, real_directory, snapshot_page)

from .file_content import FileContent, content_bytes, content_hash, require_memory


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

    def package_path(self, filename, scope="drafts"):
        """逻辑文件名保持兼容，实际定位旧文件或同 stem 的页面目录。"""
        page_filename(filename)
        directory = self.root if scope == "drafts" else self.installed if scope == "installed" else None
        if directory is None:
            raise ValueError("页面范围必须为 installed 或 drafts。")
        real_directory(directory)
        legacy = directory / filename
        package = directory / Path(filename).stem
        real_directory(package)
        if legacy.is_symlink() or legacy.exists() and not legacy.is_file():
            raise ValueError("页面必须是普通文件，不能是符号链接。")
        if legacy.exists() and package.exists():
            raise ValueError("同名旧页面与页面目录同时存在，请先处理冲突。")
        return legacy if legacy.exists() else package

    def path(self, filename, scope="drafts"):
        """定位源码入口；新页面入口始终为页内 page.py。"""
        package = self.package_path(filename, scope)
        if package.exists():
            return page_entry(package)
        return package / "page.py"

    def metadata_path(self, filename):
        page_filename(filename)
        real_directory(self.root)
        path = self.root / Path(filename).with_suffix(".json").name
        if path.is_symlink():
            raise ValueError("草稿元数据不能是符号链接。")
        return path

    def metadata(self, filename):
        path = self.metadata_path(filename)
        value = json.loads(path.read_bytes())
        if (type(value) is not dict or set(value) != {"filename", "replace"}
                or value["filename"] != filename or type(value["replace"]) is not bool):
            raise ValueError("草稿目标元数据无效。")
        return value

    def list(self, scope="installed", offset=0, limit=50, filename=None):
        if scope not in {"installed", "drafts"} or type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("无效页面范围或分页参数。")
        directory = real_directory(self.installed if scope == "installed" else self.root)
        if filename is not None:
            package = snapshot_page(self.package_path(filename, scope), freeze=False)
            files = sorted(package.files.items())
            items = [{"path": path, "size": len(content), "sha256": content_hash(content)}
                     for path, content in files[offset:offset + limit]]
            return {"scope": scope, "filename": filename, "items": items,
                    "package_sha256": package.sha256,
                    "next_offset": offset + limit if offset + limit < len(files) else None}
        names = sorted(path.name if path.parent == directory else path.parent.name + ".py"
                       for path in page_entries(directory))
        items = []
        for name in names[offset:offset + limit]:
            package = snapshot_page(self.package_path(name, scope), freeze=False)
            items.append({"filename": name, "sha256": package.sha256, "file_count": len(package.files)})
        return {"scope": scope, "items": items, "next_offset": offset + limit if offset + limit < len(names) else None}

    def read(self, scope="installed", filename="", offset=0, limit=16000, path="page.py"):
        """源码和正式配置只读分页，不为读取而导入页面。"""
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 16000:
            raise ValueError("无效读取分页参数。")
        result = {}
        source = ""
        if scope == "settings":
            if (self.session.host.service.data_root / "user-settings.json").is_symlink():
                raise ValueError("正式配置不能通过符号链接读取。")
            source = json.dumps(UserSettings(self.session.host.service.data_root).value, ensure_ascii=False, indent=2)
        else:
            target = self.file_content(scope, filename, path)
            with target.path.open("r", encoding="utf-8", newline="") as stream:
                remaining = offset
                while remaining:
                    chunk = stream.read(min(remaining, 65536))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                page = stream.read(limit + 1)
            result = {"scope": scope, "filename": filename, "source": page[:limit], "path": path,
                      "sha256": target.sha256, "next_offset": offset + limit if len(page) > limit else None}
        if scope == "settings":
            result = {"scope": scope, "filename": filename, "source": source[offset:offset + limit], "path": path,
                      "sha256": hashlib.sha256(source.encode()).hexdigest(),
                      "next_offset": offset + limit if offset + limit < len(source) else None}
        if scope == "drafts":
            result["target"] = self.metadata(filename)
        return result

    def file_content(self, scope, filename, path="page.py"):
        """有界读取页内文件，不执行源码；不把旧单文件的邻居当作资源。"""
        _relative(path)
        package = self.package_path(filename, scope)
        from .page_packages import resource_path
        if package.is_file():
            if path != "page.py":
                raise ValueError("旧单文件页面没有登记资源。")
            target = package
        else:
            target = resource_path(package, path)
        return FileContent.from_path(target)

    def file_bytes(self, scope, filename, path="page.py"):
        """仅显式请求完整内容时读取；大文本工具入口改用分页。"""
        return content_bytes(self.file_content(scope, filename, path))

    def create(self, filename, source=None, copy_from=None):
        """空白完整源码或复制正式页；新建不覆盖已有草稿或正式页。"""
        target = self.package_path(filename)
        metadata = self.metadata_path(filename)
        if target.exists() or metadata.exists():
            raise ValueError("草稿已存在，请使用 page_update。")
        if copy_from is not None:
            if source is not None or filename != copy_from:
                raise ValueError("复制正式页须沿用原文件名，且不能同时提供 source。")
            package = snapshot_page(self.package_path(copy_from, "installed"), freeze=False)
        else:
            if self.package_path(filename, "installed").exists():
                raise ValueError("正式文件已存在；请用 copy_from 创建替换草稿。")
            package = PageSnapshot({"page.py": self.source_bytes(source)})
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            write_source(metadata, json.dumps({"filename": filename, "replace": copy_from is not None}).encode(), exclusive=True)
            install_page_package(self.root, Path(filename).stem, package)
        except BaseException:
            metadata.unlink(missing_ok=True)
            raise
        return self.read("drafts", filename)

    @staticmethod
    def source_bytes(source):
        """只检查完整源码语法，不执行或判断业务兼容。"""
        if not isinstance(source, str) or not source.strip():
            raise ValueError("必须提供完整 Python 页面源码。")
        require_memory(len(source) * 48)
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
        package = snapshot_page(self.package_path(filename))
        return {**target, "source": content_bytes(package.files["page.py"]), "sha256": package.sha256,
                "package": package}

    def write_resource(self, filename, path, content=None, *, remove=False):
        """只修改当前草稿资源；源码用 page_update，正式页与配置不可写。"""
        _relative(path)
        if Path(path).suffix.lower() in {".py", ".pyc", ".pyo"}:
            raise ValueError("Python 源码只能通过 page_update 修改。")
        if type(remove) is not bool or remove and content is not None:
            raise ValueError("移除资源不能同时提供内容。")
        if not remove and not isinstance(content, (bytes, FileContent)):
            raise ValueError("页面资源必须是字节或受控文件内容。")
        self.metadata(filename)
        current = self.package_path(filename)
        files = dict(snapshot_page(current, freeze=False).files)
        if remove:
            if path not in files:
                raise ValueError("草稿资源不存在。")
            del files[path]
        else:
            assert isinstance(content, (bytes, FileContent))
            files[path] = content
        package = PageSnapshot(files)
        install_page_package(self.root, Path(filename).stem, package, replace=True,
                             legacy_filename=filename if current.is_file() else None)
        return {"filename": filename, "path": path, "removed": remove, "package_sha256": package.sha256}

    def check_registration(self, snapshot, page_id, task_id):
        """按当前正式注册检查必要冲突，不检查旧文件版本或自动合并。"""
        package = self.package_path(snapshot["filename"], "installed")
        if package.exists() and not snapshot["replace"]:
            raise ValueError("新增目标已存在，不能覆盖；请复制当前正式页重新审查。")
        check_page_registration(self.installed, package if package.is_file() else package / "page.py", page_id, task_id)

    def install(self, snapshot, page_id, task_id):
        """只由人工审查窗口调用；提交固定版本，不导入试填配置。"""
        self.check_registration(snapshot, page_id, task_id)
        filename = snapshot["filename"]
        current = self.package_path(filename, "installed")
        package = snapshot["package"]
        if package.sha256 != snapshot["sha256"] or package.files["page.py"] != snapshot["source"]:
            raise ValueError("页面快照与批准版本不一致。")
        install_page_package(self.installed, Path(filename).stem, package, replace=snapshot["replace"],
                             legacy_filename=filename if current.is_file() else None)
        return {"status": "installed", "filename": snapshot["filename"], "sha256": snapshot["sha256"],
                "page_id": page_id, "task_id": task_id, "reload_required": True}
