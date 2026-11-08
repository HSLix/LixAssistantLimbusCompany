"""可信外置业务页发现、稳定 ID 配置保存及 Dashboard 调度输入。"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
import importlib.util
import json
import logging
import sys
from pathlib import Path
import uuid
from typing import Any

from .runtime import _strict_json, atomic_write_json
from .page_packages import page_entries, page_entry, resource_path


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


class PageAvailability:
    """独立保存本机停用名单，页面更新及业务配置保存不改变启停状态。"""

    def __init__(self, data_root):
        self.path = Path(data_root) / "page-availability.json"
        if self.path.is_symlink():
            raise ValueError("页面状态不能通过符号链接读取。")
        self.disabled = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else []
        if type(self.disabled) is not list or any(type(name) is not str for name in self.disabled):
            raise ValueError("页面启停状态无效，原文件保留。")

    def enabled(self, filename):
        return filename not in self.disabled

    def set_enabled(self, filename, enabled):
        if type(enabled) is not bool:
            raise ValueError("enabled 必须为布尔值。")
        latest = PageAvailability(self.path.parent)
        disabled = set(latest.disabled)
        if enabled:
            disabled.discard(filename)
        else:
            disabled.add(filename)
        atomic_write_json(self.path, sorted(disabled))
        self.disabled = sorted(disabled)


def validate_tasks(tasks):
    """校验单页任务声明；ID 全局唯一性由注册检查负责。"""
    if type(tasks) is not list:
        raise ValueError("TASKS 必须为列表。")
    ids = set()
    for task in tasks:
        if (type(task) is not dict or not {"id", "name", "show_task_count"} <= task.keys()
                or task.keys() - {"id", "name", "show_task_count", "names"}
                or any(type(task[key]) is not str or not task[key].strip() for key in ("id", "name"))
                or type(task["show_task_count"]) is not bool):
            raise ValueError("TASKS 项必须声明 id、name 和布尔 show_task_count。")
        names = task.get("names", {})
        if (type(names) is not dict or any(key not in {"zh_CN", "en_US"} or
                type(value) is not str or not value.strip() for key, value in names.items())):
            raise ValueError("TASKS names 必须为中英文非空名称映射。")
        if task["id"] in ids:
            raise ValueError("TASKS 任务 ID 重复。")
        ids.add(task["id"])
    return deepcopy(tasks)


class PageContext:
    """供可信页面读取/保存自身配置；业务校验仍由页面负责。"""

    def __init__(self, store: UserSettings, page_id: str, package_root: Path | None = None):
        self.store, self.page_id, self.package_root = store, page_id, package_root
        from .i18n import current_language
        self.language = current_language()

    def translate(self, chinese: str, english: str) -> str:
        """页面自带两语文案；语言固定为本次应用启动时的选择。"""
        return chinese if self.language == "zh_CN" else english

    def load(self, defaults: dict | None = None) -> dict:
        return deepcopy(self.store.value["pages"].get(self.page_id, defaults or {}))

    def save(self, config: dict):
        if type(config) is not dict:
            raise ValueError("页面必须提交 JSON 对象。")
        self.store.save("pages", self.page_id, config)

    def resource_path(self, relative: str) -> Path:
        """定位当前页面目录内资源；旧配置仍由 load/save 独立管理。"""
        if self.package_root is None:
            raise ValueError("当前页面没有资源目录。")
        return resource_path(self.package_root, relative)


@dataclass
class BusinessPage:
    """已成功创建且无注册歧义的外置页。"""

    page_id: str
    name: str
    tasks: list[dict]
    widget: Any
    context: PageContext
    icon: Any = None


def load_page_module(path: Path, source: bytes):
    """加载指定字节并检查声明；每次独立模块身份，不使用 pyc。"""
    spec = importlib.util.spec_from_file_location("lalc_page_" + uuid.uuid4().hex, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module.__name__] = module
    # 直接编译当前字节，避免同秒改页后旧 pyc 被误复用。
    exec(compile(source, str(path), "exec"), module.__dict__)
    if hasattr(module, "TASK_ID") or hasattr(module, "SHOW_TASK_COUNT"):
        raise ValueError("旧 TASK_ID / SHOW_TASK_COUNT 已移除，请使用 TASKS。")
    page_id, name = module.PAGE_ID, module.PAGE_NAME
    tasks = validate_tasks(getattr(module, "TASKS", []))
    if (type(page_id) is not str or not page_id.strip() or page_id in {"dashboard", "general-settings"} or
            type(name) is not str or not name.strip() or
            not callable(module.create_page)):
        raise ValueError("无效页面声明或保留页面 ID。")
    return module, page_id, name, tasks


def create_business_page(path, module, page_id, name, tasks, store):
    """按共享契约创建页面；检查 submit 存在但不主动调用。"""
    from PySide6.QtWidgets import QWidget
    from qfluentwidgets import FluentIcon
    context = PageContext(store, page_id, Path(path).parent)
    names = getattr(module, "PAGE_NAMES", {})
    if (type(names) is not dict or any(key not in {"zh_CN", "en_US"} or
            type(value) is not str or not value.strip() for key, value in names.items())):
        raise ValueError("PAGE_NAMES must map zh_CN/en_US to non-empty display names.")
    name = names.get(context.language, name)
    widget = module.create_page(context)
    if not isinstance(widget, QWidget) or not callable(getattr(widget, "submit", None)):
        raise ValueError("create_page 必须返回提供 submit() -> dict 的 QWidget。")
    icon = getattr(module, "PAGE_ICON", None)
    if icon is not None and not isinstance(icon, FluentIcon):
        logging.getLogger(__name__).warning("%s（%s）：PAGE_ICON 无效，使用默认导航图标。", path.name, page_id)
        icon = None
    return BusinessPage(page_id, name, tasks, widget, context, icon or FluentIcon.APPLICATION)


def discover_pages(directory: Path, store: UserSettings) -> tuple[list[BusinessPage], list[str]]:
    """普通导入/创建异常只隔离单页，所有冲突注册均不进入可执行列表。"""
    directory = Path(directory).absolute()
    modules, errors, pages = [], [], []
    availability = PageAvailability(directory.parent)
    if not directory.exists():
        return pages, errors
    try:
        entries = page_entries(directory)
    except (OSError, ValueError) as error:
        return [], [f"{directory}：{type(error).__name__}: {error}"]
    for path in entries:
        try:
            path = page_entry(path)
            module, page_id, name, page_tasks = load_page_module(path, path.read_bytes())
            modules.append((path, module, page_id, name, page_tasks))
        except Exception as error:
            errors.append(f"{path.relative_to(directory)}：{type(error).__name__}: {error}")
    ids = Counter(item[2] for item in modules)
    tasks = Counter(task["id"] for item in modules for task in item[4])
    for path, module, page_id, name, page_tasks in modules:
        try:
            if ids[page_id] > 1 or any(tasks[task["id"]] > 1 for task in page_tasks):
                raise ValueError(f"页面或任务 ID 冲突：{page_id} / {page_tasks}")
            filename = path.name if path.parent == directory else path.parent.name + ".py"
            if availability.enabled(filename):
                pages.append(create_business_page(path, module, page_id, name, page_tasks, store))
        except Exception as error:
            errors.append(f"{path.relative_to(directory)}：{type(error).__name__}: {error}")
    return pages, errors


def check_page_registration(directory, target, page_id, page_tasks):
    """运行式预览专用注册检查；普通包检查不能调用会加载模块的此函数。"""
    for path in page_entries(directory):
        if path == target:
            continue
        checked = page_entry(path)
        try:
            _, other_id, _, other_tasks = load_page_module(checked, checked.read_bytes())
        except Exception:
            continue
        if page_id == other_id or {task["id"] for task in page_tasks} & {task["id"] for task in other_tasks}:
            raise ValueError(f"页面或任务 ID 冲突：{path} / {page_id} / {page_tasks}")


def task_inputs(pages: list[BusinessPage], supported: tuple[str, ...], store: UserSettings):
    """双向匹配；仅匹配且启用的项获得非零次数，告警不删除保存值。"""
    registered = {task["id"] for page in pages for task in page.tasks}
    single_run = {task["id"] for page in pages for task in page.tasks if not task["show_task_count"]}
    allowed = set(supported)
    warnings = []
    if not allowed:
        warnings.append("当前 Plan 未声明支持任何循环任务。")
    warnings.extend(f"页面任务不受当前 Plan 支持：{identity}" for identity in sorted(registered - allowed))
    warnings.extend(f"Plan 任务缺少可用设置页：{identity}" for identity in sorted(allowed - registered))
    repetitions = {}
    for identity in registered | allowed:
        saved = store.value["tasks"].get(identity, {"enabled": False, "count": 1})
        count = 1 if identity in single_run else saved["count"]
        repetitions[identity] = count if identity in registered & allowed and saved["enabled"] else 0
    return repetitions, deepcopy(store.value["pages"]), warnings
