"""文件快照的流式读写与实时资源预检；处理块大小不作为文件准入上限。"""

from contextlib import contextmanager
from dataclasses import dataclass, replace
from io import BytesIO
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time

CHUNK = 1024 * 1024
_operation = threading.local()


@contextmanager
def file_operation(cancelled=lambda: False, progress=lambda *args: None, *, allow_unknown_space=False,
                   details=lambda value: None):
    previous = getattr(_operation, 'callbacks', None)
    _operation.callbacks = (cancelled, progress, allow_unknown_space, details)
    try:
        yield
    finally:
        _operation.callbacks = previous


def checkpoint(done=0, total=0, name=''):
    callbacks = getattr(_operation, 'callbacks', None)
    if callbacks:
        if callbacks[0]():
            raise InterruptedError('操作已取消。')
        callbacks[1](done, total, name)


@dataclass(frozen=True)
class TransferProgress:
    """整体计数按文件提交，当前文件按字节更新；快照可安全送往 GUI。"""

    phase: str
    total: int
    completed: int = 0
    name: str = ''
    done: int = 0
    size: int = 0
    file_finished: bool = False
    finished: bool = False


class FileTransfers:
    """为一次文件任务集中计数，不在底层复制结束时提前宣告对象提交。"""

    def __init__(self, phase, total):
        self.value = TransferProgress(phase, total)
        self.prefix = ''
        self.update()

    def update(self, **changes):
        self.value = replace(self.value, **changes)
        callbacks = getattr(_operation, 'callbacks', None)
        if callbacks:
            callbacks[3](self.value)

    def complete(self, count=1, *, skipped=False):
        self.update(completed=self.value.completed + count,
                    phase='Skipped' if skipped else self.value.phase)


@contextmanager
def file_transfers(phase, total):
    """限定进度作用域；嵌套或失败后恢复调用方状态，不改变事务边界。"""
    previous = getattr(_operation, 'transfers', None)
    progress = FileTransfers(phase, total)
    _operation.transfers = progress
    try:
        yield progress
    finally:
        _operation.transfers = previous


def transfer_file(done, size, name, *, finished=False):
    """只更新当前文件；取消仍由原检查点处理，提交后的通知不可触发取消。"""
    progress = getattr(_operation, 'transfers', None)
    if progress is not None:
        progress.update(name=progress.prefix + name, done=done, size=size, file_finished=finished)


class ResourceUnknown(OSError):
    """系统无法报告容量；调用界面须明确确认后才能跳过对应预检。"""


_memory_sample = (0.0, None)
_memory_lock = threading.Lock()


def available_memory():
    """短时共享系统采样，避免逐文件启动 vm_stat；容量检查不承诺资源预留。"""
    global _memory_sample
    with _memory_lock:
        now = time.monotonic()
        if now - _memory_sample[0] >= .2:
            _memory_sample = (now, _read_available_memory())
        return _memory_sample[1]


def _read_available_memory():
    """读取当前可用物理内存；失败不把未知视为无限容量。"""
    try:
        if os.name == 'nt':
            import ctypes
            class Memory(ctypes.Structure):
                _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong),
                            *[(name, ctypes.c_ulonglong) for name in ('total', 'available', 'page_total', 'page_available', 'virtual_total', 'virtual_available', 'extended')]]
            status = Memory()
            status.length = ctypes.sizeof(status)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return None
            return status.available
        if sys.platform == 'darwin':
            value = subprocess.check_output(['vm_stat'], text=True, timeout=5)
            page = int(re.findall(r'page size of (\d+)', value)[0])
            return sum(int(re.findall(rf'{name}:\s+(\d+)', value)[0]) for name in ('Pages free', 'Pages inactive', 'Pages speculative')) * page
        return os.sysconf('SC_AVPHYS_PAGES') * os.sysconf('SC_PAGE_SIZE')
    except (OSError, ValueError, TypeError, KeyError, IndexError, subprocess.SubprocessError):
        return None


def require_memory(size):
    available = available_memory()
    if available is None:
        raise ResourceUnknown('无法获取当前可用内存。')
    if size > available:
        raise OSError(f'当前可用内存不足：预计需要 {size} bytes，可用 {available} bytes。')


def existing_parent(path):
    path = Path(path)
    while not path.exists():
        path = path.parent
    return path


def require_disk(requirements, *, allow_unknown=False):
    """按实际文件系统汇总需求，同盘暂存和正式副本不能分别误判容量。"""
    callbacks = getattr(_operation, "callbacks", None)
    allow_unknown = allow_unknown or bool(callbacks and callbacks[2])
    volumes = {}
    for path, size in requirements:
        parent = existing_parent(path)
        volume = parent.stat().st_dev
        previous = volumes.get(volume, (parent, 0))
        volumes[volume] = (parent, previous[1] + size)
    for parent, size in volumes.values():
        try:
            available = shutil.disk_usage(parent).free
        except OSError as error:
            if allow_unknown:
                continue
            raise ResourceUnknown(f'无法获取磁盘剩余空间：{parent}') from error
        if size > available:
            raise OSError(f'磁盘空间不足：{parent}，预计需要 {size} bytes，可用 {available} bytes。')


@dataclass(frozen=True, eq=False)
class FileContent:
    """受控文件的路径、大小和哈希；复制／读取时重新验证，资源不常驻内存。"""

    path: Path
    size: int
    sha256: str
    owner: object = None

    @classmethod
    def from_path(cls, path, *, owner=None):
        path = Path(path)
        if path.is_symlink() or not path.is_file():
            raise ValueError('资源必须是普通文件。')
        hashed = hashlib.sha256()
        with path.open('rb') as stream:
            while chunk := stream.read(CHUNK):
                checkpoint()
                hashed.update(chunk)
        fingerprint = hashed.hexdigest()
        return cls(path, path.stat().st_size, fingerprint, owner)

    def __len__(self):
        return self.size

    def __eq__(self, other):
        if isinstance(other, (bytes, FileContent)):
            return self.size == len(other) and self.sha256 == content_hash(other)
        return NotImplemented

    def decode(self, encoding='utf-8', errors='strict'):
        return content_bytes(self).decode(encoding, errors)


def content_hash(content):
    return content.sha256 if isinstance(content, FileContent) else hashlib.sha256(content).hexdigest()


@contextmanager
def content_stream(content):
    if isinstance(content, FileContent):
        with content.path.open('rb') as stream:
            yield stream
    else:
        with BytesIO(content) as stream:
            yield stream


def copy_content(content, destination, *, name=None):
    """流式写入并核验固定版本；目标由调用方的事务管理。"""
    fingerprint, size = hashlib.sha256(), 0
    name = name or (content.path.name if isinstance(content, FileContent) else '')
    transfer_file(0, len(content), name)
    with content_stream(content) as source:
        while chunk := source.read(CHUNK):
            checkpoint()
            size += len(chunk)
            if size > len(content):
                raise ValueError('文件内容已变化。')
            fingerprint.update(chunk)
            destination.write(chunk)
            transfer_file(size, len(content), name)
    if size != len(content) or fingerprint.hexdigest() != content_hash(content):
        raise ValueError('文件内容已变化。')
    transfer_file(size, len(content), name, finished=True)


def write_content(path, content, *, name=None):
    with Path(path).open('wb') as stream:
        copy_content(content, stream, name=name or Path(path).name)


def content_bytes(content):
    if not isinstance(content, FileContent):
        return content
    require_memory(len(content) * 4)
    output = BytesIO()
    copy_content(content, output)
    return output.getvalue()


_image_lock = threading.RLock()


@contextmanager
def open_image(content, *, decoding=False):
    """仅本次受控图片读取取消 Pillow 固定像素门槛，解码前按像素估算内存。"""
    from PIL import Image
    with _image_lock, content_stream(content) as stream:
        previous = Image.MAX_IMAGE_PIXELS
        try:
            Image.MAX_IMAGE_PIXELS = None
            with Image.open(stream) as image:
                if decoding:
                    require_memory(image.width * image.height * 12)
                yield image
        finally:
            Image.MAX_IMAGE_PIXELS = previous


def image_preview(content, size=(1280, 1280)):
    """按需生成传输／显示用 JPEG，原始资源不改写；资源不足只影响预览。"""
    with open_image(content) as image:
        image.draft('RGB', size)
        require_memory(image.width * image.height * 12)
        checkpoint()
        image.thumbnail(size)
        output = BytesIO()
        image.convert('RGB').save(output, format='JPEG', quality=85)
        return output.getvalue()
