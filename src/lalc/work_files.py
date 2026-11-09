"""普通工作目录和待提交文件；继承父目录权限并按拥有者生命周期清理。"""

from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import uuid
import weakref


def work_root():
    """默认工作区随应用数据保存，不使用系统临时目录。"""
    from .application import default_data_root

    root = default_data_root() / "work"
    root.mkdir(parents=True, exist_ok=True)
    return root


def create_work_directory(*, dir=None, prefix="work-"):
    """创建唯一普通目录；调用方负责清理或提交，不能复用既有路径。"""
    path = Path(dir) if dir is not None else work_root()
    path = path / f"{prefix}{uuid.uuid4()}"
    path.mkdir()
    return str(path)


def _remove_directory(path):
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        pass


class WorkDirectory:
    """拥有一个普通工作目录，支持作用域退出或最后一个快照引用释放时清理。"""

    def __init__(self, *, dir=None, prefix="work-"):
        self.name = create_work_directory(dir=dir, prefix=prefix)
        self._finalizer = weakref.finalize(self, _remove_directory, self.name)

    def cleanup(self):
        self._finalizer()

    def __enter__(self):
        return self.name

    def __exit__(self, *args):
        self.cleanup()


def create_work_file(*, dir=None, prefix="pending-", suffix=""):
    """排他创建普通文件，返回描述符及路径；调用方负责关闭和清理。"""
    parent = Path(dir) if dir is not None else work_root()
    path = parent / f"{prefix}{uuid.uuid4()}{suffix}"
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o666)
    return descriptor, str(path)


@contextmanager
def work_file(*, dir=None, prefix="pending-", suffix="", delete=True):
    """提供可读写的普通文件；未交给提交方的文件在退出时删除。"""
    parent = Path(dir) if dir is not None else work_root()
    path = parent / f"{prefix}{uuid.uuid4()}{suffix}"
    stream = path.open("x+b")
    try:
        with stream:
            yield stream
    finally:
        if delete:
            path.unlink(missing_ok=True)
