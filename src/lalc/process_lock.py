"""同一系统用户的跨进程排他；进程退出时由操作系统释放。"""

from __future__ import annotations

import getpass
import hashlib
import os
import tempfile
from pathlib import Path


class ProcessLock:
    """持有文件锁直至显式释放；锁文件保留以避免删除重建竞争。"""

    def __init__(self, name: str):
        identity = hashlib.sha256(f"{Path.home()}:{getpass.getuser()}:{name}".encode()).hexdigest()
        self.path = Path(tempfile.gettempdir()) / f"lalc-{identity}.lock"
        self.file = None

    def acquire(self) -> None:
        """非阻塞取得排他权；竞争和系统错误交给调用方报告。"""
        if self.file is not None:
            raise RuntimeError("Lock already held")
        handle = open(self.path, "a+b")
        try:
            if os.name == "nt":
                import msvcrt
                handle.seek(0, 2)
                if handle.tell() == 0:
                    handle.write(b"\0")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            handle.close()
            raise
        self.file = handle

    def release(self) -> None:
        """解锁并关闭句柄，不删除共享锁文件。"""
        if self.file is None:
            return
        handle, self.file = self.file, None
        try:
            if os.name == "nt":
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *_):
        self.release()
