"""可信外置业务页发现、稳定 ID 配置保存及 Dashboard 调度输入。"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
import importlib.util
import json
import sys
from pathlib import Path
import uuid
from typing import Any

from .runtime import _strict_json, atomic_write_json


class UserSettings:
    """页面与次数跨 Manifest 共用；每次保存先落盘，再更新内存。"""

    def __init__(self, data_root: Path):
        self.path = data_root / "user-settings.json"
        self.value = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {"pages": {}, "tasks": {}}
        if (type(self.value) is not dict or set(self.value) != {"pages", "tasks"} or
                type(self.value["pages"]) is not dict or type(self.value["tasks"]) is not dict):
            raise ValueError("用户页面设置格式错误，原文件保留。")
        for page_id, config in self.value["pages"].items():
            if not isinstance(page_id, str) or type(config) is not dict:
                raise ValueError("页面配置必须是 JSON 对象。")
        for task_id, task in self.value["tasks"].items():
            if (not isinstance(task_id, str) or type(task) is not dict or set(task) != {"enabled", "count"} or
                    type(task["enabled"]) is not bool or type(task["count"]) is not int or task["count"] < 1):
                raise ValueError("任务次数设置无效，原文件保留。")
        _strict_json(self.value)

    def save(self, section: str, identity: str, value: dict):
        prepared = deepcopy(self.value)
        prepared[section][identity] = _strict_json(value)
        atomic_write_json(self.path, prepared)
        self.value = prepared

    def save_task(self, task_id: str, enabled: bool, count: int):
        if type(enabled) is not bool or type(count) is not int or count < 1:
            raise ValueError("循环次数必须为正整数。")
        self.save("tasks", task_id, {"enabled": enabled, "count": count})


class PageContext:
    """供可信页面读取/保存自身配置；业务校验仍由页面负责。"""

    def __init__(self, store: UserSettings, page_id: str):
        self.store, self.page_id = store, page_id

    def load(self, defaults: dict | None = None) -> dict:
        return deepcopy(self.store.value["pages"].get(self.page_id, defaults or {}))

    def save(self, config: dict):
        if type(config) is not dict:
            raise ValueError("页面必须提交 JSON 对象。")
        self.store.save("pages", self.page_id, config)


@dataclass
class BusinessPage:
    """已成功创建且无注册歧义的外置页。"""

    page_id: str
    name: str
    task_id: str | None
    widget: Any
    context: PageContext


def discover_pages(directory: Path, store: UserSettings) -> tuple[list[BusinessPage], list[str]]:
    """普通导入/创建异常只隔离单页，所有冲突注册均不进入可执行列表。"""
    modules, errors, pages = [], [], []
    if not directory.exists():
        return pages, errors
    for path in sorted(directory.glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location("lalc_page_" + uuid.uuid4().hex, path)
            assert spec is not None
            module = importlib.util.module_from_spec(spec)
            sys.modules[module.__name__] = module
            # 直接编译当前字节，避免同秒改页后旧 pyc 被误复用。
            exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
            page_id, name, task_id = module.PAGE_ID, module.PAGE_NAME, getattr(module, "TASK_ID", None)
            if (type(page_id) is not str or not page_id.strip() or page_id in {"dashboard", "general-settings"} or
                    type(name) is not str or not name.strip() or
                    task_id is not None and (type(task_id) is not str or not task_id.strip()) or
                    not callable(module.create_page)):
                raise ValueError("无效页面声明或保留页面 ID。")
            modules.append((path, module, page_id, name, task_id))
        except Exception as error:
            errors.append(f"{path.name}：{type(error).__name__}: {error}")
    ids = Counter(item[2] for item in modules)
    tasks = Counter(item[4] for item in modules if item[4] is not None)
    for path, module, page_id, name, task_id in modules:
        try:
            if ids[page_id] > 1 or task_id is not None and tasks[task_id] > 1:
                raise ValueError(f"页面或任务 ID 冲突：{page_id} / {task_id}")
            from PySide6.QtWidgets import QWidget
            context = PageContext(store, page_id)
            widget = module.create_page(context)
            if not isinstance(widget, QWidget) or not callable(getattr(widget, "submit", None)):
                raise ValueError("create_page 必须返回提供 submit() -> dict 的 QWidget。")
            pages.append(BusinessPage(page_id, name, task_id, widget, context))
        except Exception as error:
            errors.append(f"{path.name}：{type(error).__name__}: {error}")
    return pages, errors


def task_inputs(pages: list[BusinessPage], supported: tuple[str, ...], store: UserSettings):
    """双向匹配；仅匹配且启用的项获得非零次数，告警不删除保存值。"""
    registered = {page.task_id for page in pages if page.task_id is not None}
    allowed = set(supported)
    warnings = []
    if not allowed:
        warnings.append("当前 Plan 未声明支持任何循环任务。")
    warnings.extend(f"页面任务不受当前 Plan 支持：{identity}" for identity in sorted(registered - allowed))
    warnings.extend(f"Plan 任务缺少可用设置页：{identity}" for identity in sorted(allowed - registered))
    repetitions = {}
    for identity in registered | allowed:
        saved = store.value["tasks"].get(identity, {"enabled": False, "count": 1})
        repetitions[identity] = saved["count"] if identity in registered & allowed and saved["enabled"] else 0
    return repetitions, deepcopy(store.value["pages"]), warnings
