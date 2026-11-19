"""按页面 ID 读写独立的 JSON 资源。"""

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .page_packages import _relative, real_directory
from .runtime import _strict_json
from .work_files import work_file


class PageJsonResources:
    """正式页面和运行共享磁盘资源；页面包预览可使用独立内存副本。"""

    def __init__(self, root: Path | None = None):
        self.root = root
        self._preview: dict[tuple[str, str], dict[str, Any]] = {}

    def _path(self, page_id: str, name: str) -> Path | None:
        if not isinstance(page_id, str) or not page_id.strip():
            raise ValueError("页面 ID 必须为非空字符串。")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,127}", name):
            raise ValueError("页面资源名必须使用小写字母、数字、点、下划线或连字符。")
        filename = _relative(f"{name}.json")[0]
        if self.root is None:
            return None
        # 保留已有 PAGE_ID 的精确身份，避免 Windows 路径别名和分隔符。
        directory = real_directory(self.root / hashlib.sha256(page_id.encode("utf-8")).hexdigest())
        path = directory / filename
        if path.is_symlink() or path.exists() and not path.is_file():
            raise ValueError("页面 JSON 资源必须是普通文件。")
        return path

    def read_json(self, page_id: str, name: str) -> dict[str, Any] | None:
        """读取最新 JSON 对象；缺失返回 None，损坏的文件保留并报错。"""
        path = self._path(page_id, name)
        if path is None:
            return _strict_json(self._preview.get((page_id, name)))
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        if type(value) is not dict:
            raise ValueError("页面资源必须是 JSON 对象。")
        return _strict_json(value)

    def write_json(self, page_id: str, name: str, value: dict[str, Any]) -> None:
        """整份替换一个 JSON 对象，提交失败时保留旧文件。"""
        path = self._path(page_id, name)
        if type(value) is not dict:
            raise ValueError("页面资源必须是 JSON 对象。")
        value = _strict_json(value)
        if path is None:
            self._preview[page_id, name] = value
            return
        content = json.dumps(value, ensure_ascii=True, allow_nan=False, indent=2).encode("utf-8")
        path.parent.mkdir(parents=True, exist_ok=True)
        pending = None
        try:
            with work_file(dir=path.parent, delete=False) as stream:
                pending = Path(stream.name)
                stream.write(content)
            pending.replace(path)
        finally:
            if pending is not None:
                pending.unlink(missing_ok=True)
