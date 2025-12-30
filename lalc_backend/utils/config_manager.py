import json
import os
from typing import Dict, Any
from utils.logger import init_logger


logger = init_logger()


class ConfigManager:
    """
    配置管理器，用于管理exp、thread、mirror三类配置以及其他零散的共享变量
    """

    def __init__(self, config_dir: str = "config"):
        """
        初始化配置管理器
        :param config_dir: 配置文件目录路径
        """
        self.config_dir = config_dir
        # logger.debug(f"ConfigManager 配置文件到 {config_dir}")
        self.exp_cfg_file = os.path.join(config_dir, "exp_cfg.json")
        self.thread_cfg_file = os.path.join(config_dir, "thread_cfg.json")
        self.mirror_cfg_file = os.path.join(config_dir, "mirror_cfg.json")
        self.other_task_cfg_file = os.path.join(config_dir, "other_task_cfg.json")
        self.theme_pack_cfg_file = os.path.join(config_dir, "theme_pack_cfg.json")
        
        # 初始化配置数据结构
        self.exp_cfg = {}
        self.thread_cfg = {}
        self.mirror_cfg = {}
        self.other_task_cfg = {}
        self.theme_pack_cfg = {}

    def load_configs(self):
        """
        从配置文件加载所有配置
        """
        self.exp_cfg = self._load_config_file(self.exp_cfg_file)
        self.thread_cfg = self._load_config_file(self.thread_cfg_file)
        self.mirror_cfg = self._load_config_file(self.mirror_cfg_file)
        self.other_task_cfg = self._load_config_file(self.other_task_cfg_file)
        self.theme_pack_cfg = self._load_config_file(self.theme_pack_cfg_file)

    def save_configs(self):
        """
        将配置保存到对应的配置文件
        """
        self._save_config_file(self.exp_cfg_file, self.exp_cfg)
        self._save_config_file(self.thread_cfg_file, self.thread_cfg)
        self._save_config_file(self.mirror_cfg_file, self.mirror_cfg)
        self._save_config_file(self.other_task_cfg_file, self.other_task_cfg)
        self._save_config_file(self.theme_pack_cfg_file, self.theme_pack_cfg)

    def _load_config_file(self, file_path: str) -> Dict[str, Any]:
        """
        从指定文件加载配置
        :param file_path: 配置文件路径
        :return: 配置字典
        """
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.log(f"警告: 配置文件 {file_path} 格式错误，使用空配置", level="ERROR")
                return {}
        else:
            # 文件不存在，创建空文件
            logger.log(f"警告: 配置文件 {file_path} 不存在，使用空配置", level="WARNING")
            self._save_config_file(file_path, {})
            return {}

    def _save_config_file(self, file_path: str, config_data: Dict[str, Any]):
        """
        将配置保存到指定文件
        :param file_path: 配置文件路径
        :param config_data: 配置数据
        """
        # 确保目录存在
        os.makedirs(os.path.dirname(file_path) if os.path.dirname(file_path) else '.', exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)

    def get_exp_config(self) -> Dict[str, Any]:
        """
        获取经验副本配置
        :return: 经验副本配置字典
        """
        return self.exp_cfg.copy()

    def get_thread_config(self) -> Dict[str, Any]:
        """
        获取thread副本配置
        :return: thread副本配置字典
        """
        return self.thread_cfg.copy()

    def get_mirror_config(self) -> Dict[str, Any]:
        """
        获取镜像迷宫配置
        :return: 镜像迷宫配置字典
        """
        return self.mirror_cfg.copy()

    def get_other_task_config(self) -> Dict[str, Any]:
        """
        获取其他零散配置
        :return: 其他零散配置字典
        """
        return self.other_task_cfg.copy()

    def get_theme_pack_config(self) -> Dict[str, Any]:
        """
        获取主题包配置
        :return: 主题包配置字典
        """
        return self.theme_pack_cfg.copy()

    def update_exp_config(self, config: Dict[str, Any]):
        """
        更新经验副本配置
        :param config: 新的经验副本配置
        """
        self.exp_cfg.update(config)

    def update_thread_config(self, config: Dict[str, Any]):
        """
        更新thread副本配置
        :param config: 新的thread副本配置
        """
        self.thread_cfg.update(config)

    def update_mirror_config(self, config: Dict[str, Any]):
        """
        更新镜像迷宫配置
        :param config: 新的镜像迷宫配置
        """
        self.mirror_cfg.update(config)

    def update_other_task_config(self, config: Dict[str, Any]):
        """
        更新其他任务零散配置
        :param config: 新的零散配置
        """
        self.other_task_cfg.update(config)

    def update_theme_pack_config(self, config: Dict[str, Any]):
        """
        更新主题包配置
        :param config: 新的主题包配置
        """
        self.theme_pack_cfg.update(config)

    def initialize_theme_pack_config(self):
        """
        初始化主题包配置：
        1. 首先读取已有的配置
        2. 遍历 img/theme_packs 文件夹下的图片
        3. 以图片名为 key，值为一个字典，包含权重值 weight，默认为 10
        """
        # 先加载已有的配置
        self.theme_pack_cfg = self._load_config_file(self.theme_pack_cfg_file)
        
        # 遍历 img/theme_packs 文件夹
        theme_packs_dir = "img/theme_packs"
        if os.path.exists(theme_packs_dir):
            for filename in os.listdir(theme_packs_dir):
                # 检查是否为 PNG 文件
                if filename.endswith(".png"):
                    # 获取文件名（不含扩展名）作为 key
                    name = os.path.splitext(filename)[0]
                    
                    # 如果该主题包尚未在配置中，则添加默认配置
                    if name not in self.theme_pack_cfg:
                        self.theme_pack_cfg[name] = {
                            "weight": 10
                        }

        # 保存更新后的配置
        self._save_config_file(self.theme_pack_cfg_file, self.theme_pack_cfg)


    def get_config_structure(self) -> Dict[str, Dict[str, Any]]:
        """
        获取完整的配置结构，便于在TaskExecution中使用
        :return: 包含所有配置的字典
        """
        return {
            "exp_cfg": self.get_exp_config(),
            "thread_cfg": self.get_thread_config(),
            "mirror_cfg": self.get_mirror_config(),
            "other_task_cfg": self.get_other_task_config(),
            "theme_pack_cfg": self.get_theme_pack_config()
        }

    def get_other_param(self, key: str, default=None):
        """
        获取其他配置中的特定参数
        :param key: 参数键名
        :param default: 默认值
        :return: 参数值
        """
        return self.other_task_cfg.get(key, default)

    def set_other_param(self, key: str, value):
        """
        设置其他配置中的特定参数
        :param key: 参数键名
        :param value: 参数值
        """
        self.other_task_cfg[key] = value


# 全局配置管理器实例引用
_config_manager_instance = None


def init_config_manager(config_dir: str = "config"):
    """
    初始化并返回配置管理器单例实例
    :param config_dir: 配置文件目录路径
    :return: ConfigManager实例
    """
    global _config_manager_instance
    if _config_manager_instance is None:
        _config_manager_instance = ConfigManager(config_dir)
    return _config_manager_instance


def initialize_configs():
    """
    初始化配置管理器并加载所有配置
    """
    global _config_manager_instance
    if _config_manager_instance is None:
        _config_manager_instance = ConfigManager()
    _config_manager_instance.load_configs()
    _config_manager_instance.initialize_theme_pack_config()
    return _config_manager_instance


if __name__ == "__main__":
    # 测试配置管理器
    cm = initialize_configs()
    
    # 示例：更新配置
    cm.update_exp_config({
        "check_node_name":"exp_check",
        "luxcavation_mode": "skip_battle",
        "exp_stage": "08",
        "check_node_target_count": 0,
        "team_indexes": [6],
        "team_orders": [["Yi Sang", "Faust", "Don Quixote", "Ryoshu", "Meursault", "Hong Lu", "Heathcliff", "Ishmael", "Rodion", "Sinclair", "Outis", "Gregor"]]
    })
    
    cm.update_thread_config({
        "check_node_name":"thread_check",
        "luxcavation_mode": "skip_battle",
        "thread_stage": "50",
        "check_node_target_count": 0,
        "team_indexes": [3],
        "team_orders": [["Yi Sang", "Faust", "Gregor", "Don Quixote", "Ishmael", "Rodion", "Ryoshu", "Meursault", "Hong Lu", "Heathcliff", "Sinclair", "Outis"]]
    })
    
    cm.update_mirror_config({
        "check_node_name":"mirror_check",
        "check_node_target_count": 99,
        "team_indexes": [1],
        "mirror_shop_heal":[False],
        "team_orders": [["Don Quixote", "Yi Sang", "Ishmael", "Rodion", "Gregor", "Heathcliff", "Hong Lu", "Ryoshu", "Faust", "Meursault", "Sinclair", "Outis"]],
        "mirror_team_styles": ["Bleed"],
        "mirror_team_initial_ego_orders": [[2, 1, 3]],
        "mirror_team_ego_gift_styles": [["Bleed", "Poise"]],
        "mirror_team_ego_allow_list": [["Lithograph", "Phlebotomy Pack", "Golden Urn"]],
        "mirror_team_ego_block_list": [["Oracle"]],
        "mirror_team_stars": [["0", "3", "6", "7"]],
        "mirror_replace_skill": [{'Don Quixote': [1, 2, 3], 'Yi Sang': [1, 2, 3], 'Ishmael': [1, 2, 3], 'Rodion': [1, 2, 3], 'Gregor': [3, 2, 1], 'Hong Lu': [1, 2, 3], "Heathcliff":[3, 1, 2]}],
        "mirror_stop_purchase_gift_money":600,
    })
    
    # 示例：更新零散配置
    cm.update_other_task_config({
        "lunary_purchase_target": 2,
        "test_mode":True, 
    })
    
    # 保存配置
    cm.save_configs()
    print("配置已保存")