# coding: utf-8
import json
from pathlib import Path
from globals import CONFIG_DIR

class JSONManager:
    _instance = None
    JSON_FILE = None  # 子类必须重写此变量

    def __new__(cls):
        if cls._instance is None:
            if not cls.JSON_FILE:
                raise ValueError("子类必须设置JSON_FILE类变量")
            cls._instance = super().__new__(cls)
            cls._instance._config_path = Path(CONFIG_DIR, cls.JSON_FILE)
            cls._instance._config = cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        if self._config_path.exists():
            with open(self._config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def get_config(self, task_type):
        return self._config.get(task_type, {})

    def save_config(self, task_type, params):
        self._config = self._load_config()
        self._config[task_type] = params
        with open(self._config_path, 'w', encoding='utf-8') as f:
            json.dump(self._config, f, indent=4)

class ConfigManager(JSONManager):
    JSON_FILE = "lalc_config.json"

class TeamManager(JSONManager):
    JSON_FILE = "teams.json"  # 假设队伍数据存储在teams.json

# 初始化单例实例
config_manager = ConfigManager()
team_manager = TeamManager()