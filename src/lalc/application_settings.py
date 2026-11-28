"""保存本机主题和自动恢复设置，供界面与无界面运行共用。"""

import json
from pathlib import Path

from .runtime import atomic_write_json


APPEARANCES = ("system", "light", "dark")
DEFAULT_APPEARANCE = "system"
DEFAULT_IDLE_SECONDS = 10
MIN_IDLE_SECONDS = 1
MAX_IDLE_SECONDS = 120


def _validate(settings):
    if (type(settings) is not dict or settings.keys() - {"appearance", "input_idle_seconds"}
            or settings.get("appearance", DEFAULT_APPEARANCE) not in APPEARANCES):
        raise ValueError("Invalid application settings.")
    seconds = settings.get("input_idle_seconds", DEFAULT_IDLE_SECONDS)
    if type(seconds) is not int or not MIN_IDLE_SECONDS <= seconds <= MAX_IDLE_SECONDS:
        raise ValueError("Input idle time must be between 1 and 120 seconds.")


def load_application_settings(data_root: Path) -> dict:
    """读取并校验已保存的选择，缺失字段由各自调用方使用默认值。"""
    try:
        settings = json.loads((data_root / "application-settings.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        settings = {}
    _validate(settings)
    return settings


def save_application_setting(data_root: Path, key: str, value) -> None:
    """合并改单项并原子提交，失败时保留之前的选择。"""
    settings = load_application_settings(data_root) | {key: value}
    _validate(settings)
    atomic_write_json(data_root / "application-settings.json", settings)
