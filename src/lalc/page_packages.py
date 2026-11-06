"""页面源码与资源的固定整包快照、受控路径及失败安全替换。"""

from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import json
import logging
from pathlib import Path
import shutil
import tempfile
from types import MappingProxyType
from typing import Mapping

from .file_content import FileContent, content_hash, write_content, require_disk, require_memory, checkpoint


def page_filename(filename):
    """仅允许 Windows 也可用的顶层页面文件名；保留旧工具契约。"""
    if (not isinstance(filename, str) or not filename or len(filename) > 128
            or filename.startswith(("_", ".")) or not filename.endswith(".py")
            or any(ord(char) < 32 or char in '/\\<>:"|?*' for char in filename)
            or not filename[:-3].strip(" .")
            or filename.split(".", 1)[0].rstrip(" ").upper() in {"CON", "PRN", "AUX", "NUL",
                *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}):
        raise ValueError("页面文件名必须是顶层普通 .py 文件名，不能使用保留名称。")
    return filename


def real_directory(path):
    """拒绝访问链上的符号链接、Windows junction 及非目录目标。"""
    path = Path(path).absolute()
    if (any(part.is_symlink() or part.is_junction() for part in (path, *path.parents))
            or path.exists() and not path.is_dir()):
        raise ValueError("页面目录必须是真实目录，不能包含符号链接。")
    return path


def _relative(name):
    """校验页内相对路径，拒绝 Windows 别名、保留名和路径穿越。"""
    if not isinstance(name, str) or not name or len(name.encode("utf-8")) > 1024:
        raise ValueError("页面资源路径无效。")
    parts = name.split("/")
    if len(parts) > 32:
        raise ValueError("页面资源路径层级过多。")
    for part in parts:
        if (not part or len(part.encode("utf-8")) > 255 or part in {".", ".."} or part != part.rstrip(" .")
                or any(ord(char) < 32 or char in '\\<>:"|?*' for char in part)
                or part.split(".", 1)[0].rstrip(" ").upper() in {"CON", "PRN", "AUX", "NUL",
                    *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}):
            raise ValueError("页面资源路径无效。")
    return parts


def resource_path(root, relative):
    """定位页面包内已有普通文件，不跟随资源链接或目录链接。"""
    path = real_directory(root).joinpath(*_relative(relative))
    real_directory(path.parent)
    if path.is_symlink() or not path.is_file():
        raise ValueError("页面资源必须是包内普通文件。")
    return path


def page_entry(path):
    """统一定位旧单文件或新目录中的固定 page.py 入口。"""
    path = Path(path)
    if path.is_dir():
        return resource_path(path, "page.py")
    page_filename(path.name)
    return resource_path(path.parent, path.name)


def page_entries(directory):
    """列举正式页入口，不递归发现资源目录里的 Python 文件。"""
    directory = real_directory(directory)
    if not directory.exists():
        return []
    entries = []
    for item in sorted(directory.iterdir()):
        if item.name.startswith(("_", ".")):
            continue
        if item.suffix == ".py" and not item.is_dir():
            entries.append(item)
        elif item.is_dir() and ((item / "page.py").exists() or (item / "page.py").is_symlink()):
            entries.append(item / "page.py")
    return entries


@dataclass(frozen=True)
class PageSnapshot:
    """不可变源码／资源字节；路径与文件内容共同决定整个页面版本。"""

    files: Mapping[str, bytes | FileContent]
    sha256: str = field(init=False)

    def __post_init__(self):
        require_memory(sum(len(name.encode("utf-8")) + 1024 for name in self.files))
        files = dict(self.files)
        aliases = {}
        for name, content in files.items():
            checkpoint()
            parts = _relative(name)
            if not isinstance(content, (bytes, FileContent)):
                raise ValueError("页面快照内容必须是字节。")
            for index in range(1, len(parts) + 1):
                prefix = "/".join(parts[:index])
                previous = aliases.setdefault(prefix.casefold(), prefix)
                if previous != prefix or index < len(parts) and prefix in files:
                    raise ValueError("页面文件路径存在大小写或文件／目录冲突。")
        if "page.py" not in files:
            raise ValueError("页面包缺少 page.py。")
        version = [(name, content_hash(content)) for name, content in sorted(files.items())]
        object.__setattr__(self, "files", MappingProxyType(files))
        object.__setattr__(self, "sha256", hashlib.sha256(json.dumps(version).encode()).hexdigest())


def snapshot_page(path, *, freeze=True):
    """只读固定页面全部文件；旧单文件包装为 page.py，不执行源码。"""
    path = Path(path)
    entry = page_entry(path)
    if not path.is_dir():
        files = {"page.py": FileContent.from_path(entry)}
        return _freeze_snapshot(files) if freeze else PageSnapshot(files)
    files = {}
    for item in path.rglob("*"):
        if item.is_symlink() or item.is_junction():
            raise ValueError("页面包不允许链接。")
        if item.is_dir():
            continue
        relative = item.relative_to(path).as_posix()
        files[relative] = FileContent.from_path(resource_path(path, relative))
    return _freeze_snapshot(files) if freeze else PageSnapshot(files)


def _freeze_snapshot(files):
    """磁盘副本由资源引用持有，维持原有固定快照语义。"""
    require_disk([(Path(tempfile.gettempdir()), sum(len(content) for content in files.values()))])
    owner = tempfile.TemporaryDirectory(prefix="lalc-page-snapshot-")
    root = Path(owner.name).resolve()
    fixed = {}
    for name, content in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        write_content(target, content)
        fixed[name] = FileContent(target, len(content), content_hash(content), owner)
    return PageSnapshot(fixed)


def _write_snapshot(snapshot, directory):
    directory.mkdir()
    for name, content in snapshot.files.items():
        path = directory.joinpath(*_relative(name))
        path.parent.mkdir(parents=True, exist_ok=True)
        write_content(path, content)


@contextmanager
def materialized_page(snapshot):
    """临时提供固定整包入口，供预览在整个窗口生命周期内使用。"""
    with tempfile.TemporaryDirectory(prefix="lalc-page-preview-") as temporary:
        package = Path(temporary).resolve() / "package"
        _write_snapshot(snapshot, package)
        yield package / "page.py"


def install_page_package(directory, name, snapshot, *, replace=False, legacy_filename=None):
    """调用方批准并持有互斥后整包安装；普通失败恢复旧页，不执行源码。"""
    if len(_relative(name)) != 1 or name.startswith(("_", ".")):
        raise ValueError("页面包名称必须是顶层普通目录名。")
    directory = real_directory(directory)
    target = real_directory(directory / name)
    legacy = None
    if legacy_filename is not None:
        page_filename(legacy_filename)
        if legacy_filename != f"{name}.py":
            raise ValueError("旧页面与新页面包目标不一致。")
        legacy = directory / legacy_filename
        if legacy.is_symlink() or legacy.exists() and not legacy.is_file():
            raise ValueError("旧页面必须是普通文件。")
    if target.exists() and legacy is not None and legacy.exists():
        raise ValueError("旧文件与新页面目录同时存在，请先处理冲突。")
    old = target if target.exists() else legacy if legacy is not None and legacy.exists() else None
    if old is not None and not replace:
        raise FileExistsError("页面已存在，不能覆盖。")
    require_disk([(directory, sum(len(content) for content in snapshot.files.values()))])
    directory.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(dir=directory, prefix=".page-install-"))
    staged, backup = work / "new", work / "previous"
    installed = False
    try:
        _write_snapshot(snapshot, staged)
        if old is not None:
            old.rename(backup)
        try:
            if target.exists() or target.is_symlink():
                raise FileExistsError("页面目标已被占用。")
            staged.rename(target)
            installed = True
        except BaseException:
            if old is not None:
                try:
                    if old.exists() or old.is_symlink():
                        raise FileExistsError("旧页面恢复目标已被占用。")
                    backup.rename(old)
                except OSError as error:
                    raise OSError(f"旧页面恢复失败，原内容保留在 {backup}") from error
            raise
    finally:
        # 恢复失败时不能让临时目录清理删掉唯一的旧版本。
        if installed or not backup.exists():
            try:
                shutil.rmtree(work)
            except OSError:
                logging.getLogger(__name__).warning("页面临时目录未清理：%s", work, exc_info=True)
    return target
