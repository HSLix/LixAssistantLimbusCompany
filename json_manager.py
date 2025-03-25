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

class ThemePackManager(JSONManager):
    JSON_FILE = "theme_pack.json"

    def __init__(self):
        self.weight_dict = {}
        self._generate_weight_dict()

    def _generate_weight_dict(self):
        for theme, data in self._config.items():
            if theme and 'keyword' in data and 'weight' in data:
                weight = data['weight']
                keyword = data['keyword']
                if weight not in self.weight_dict:
                    self.weight_dict[weight] = []
                self.weight_dict[weight].append(keyword)

    def get_keywords_by_weight(self, weight):
        return self.weight_dict.get(weight, [])

# 初始化单例实例
config_manager = ConfigManager()
team_manager = TeamManager()
theme_pack_manager = ThemePackManager()
