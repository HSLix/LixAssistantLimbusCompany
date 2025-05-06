# coding: utf-8
import json
from time import sleep
from typing import Union, List, Dict
from random import uniform
from copy import deepcopy
from os.path import join

from executor.eye import get_eye
from globals import sinner_place, sinner_name, CONFIG_DIR
from .game_window import activateWindow
from .custom_action_dict import CustomActionDict
from .mouse_keyboard import get_mouse_keyboard
from .logger import lalc_logger
from json_manager import theme_pack_manager

    


def initJsonTask(json_path: str = join(CONFIG_DIR, "task.json")):
    """
    从JSON文件加载任务配置到全局字典
    
    参数：
    json_path -- 任务配置文件的路径 (默认: "task.json")
    
    异常：
    FileNotFoundError -- 当配置文件不存在时抛出
    JSONDecodeError -- 当JSON格式错误时抛出
    """
  
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"任务配置文件 {json_path} 不存在")
    except json.JSONDecodeError:
        raise ValueError("JSON文件格式错误")


    task_dict: Dict[str, Task] = dict()
    for task_name, task_config in raw_data.items():
        # 处理 next 字段的两种形式：字符串或列表
        if 'next' in task_config:
            next_tasks = task_config['next']
            if isinstance(next_tasks, str):
                task_config['next'] = [next_tasks]
        else:
            task_config['next'] = []

        if 'interrupt' in task_config:
            interrupt_tasks = task_config['interrupt']
            if isinstance(interrupt_tasks, str):
                task_config['interrupt'] = [interrupt_tasks]
        else:
            task_config['interrupt'] = []

        # 创建任务实例并存入字典
        task_dict[task_name] = Task(
            name=task_name,
            **task_config
        )

    return task_dict







def generate_random_num(min_val, max_val):
    """
    此函数用于生成一个随机数
    列表中的每个元素都是介于 min_val 和 max_val 之间的随机数。

    :param min_val: 随机数的最小值
    :param max_val: 随机数的最大值
    :return: 包含两个随机数的列表
    """
    return int(uniform(min_val, max_val))




class Task:
    """
    重构后的任务类，支持通过装饰器实现流程控制
    """
    def __init__(self, name: str, **kwargs):
        # 基础属性
        self.name = name
        self.enabled: bool = kwargs.get('enabled', True)

        # 初始化自定义行动字典
        self.custom_action_dict = initCustomAction()

        # 初始化日志等级
        self.log_level = kwargs.get("log_level", "DEBUG")

        # 识别配置
        self.recognition: str = kwargs.get('recognition', 'DirectHit')
        
        # 动作配置
        self.action: str = kwargs.get('action', 'DoNothing')
        self.action_rest: float = kwargs.get('action_rest', 0.1)
        self.action_count: int = kwargs.get('action_count', 1)
        
        # 流程控制
        self.next: List[str] = self._normalize_list(kwargs.get('next', []))
        self.interrupt: List[str] = self._normalize_list(kwargs.get('interrupt', []))
        self.on_error: List[str] = self._normalize_list(kwargs.get('on_error', []))
        
        # 时间控制
        self.pre_delay: float = kwargs.get('pre_delay', 0.1)
        self.post_delay: float = kwargs.get('post_delay', 0.1)
        self.pre_wait_freezes: int = kwargs.get('pre_wait_freezes', 0)
        self.post_wait_freezes: int = kwargs.get('post_wait_freezes', 0)
        #   任务执行所需要的图像获取与识别
        self.eye = get_eye()
        # 初始化识别算法参数
        self._init_recognize_params(kwargs)

        # 初始化识别函数
        self.recognition_function = self._init_recognize_function()

        # 初始化动作参数
        self._init_action_params(kwargs)
        
        # 初始化动作函数
        self.action_function = self._init_action_function()

        # 任务执行动作的鼠标/键盘
        self.mk = get_mouse_keyboard()

        

        

    def _init_recognize_params(self, config: dict):
        """初始化识别算法相关参数"""
        # 模板匹配参数
        if self.recognition == "TemplateMatch":
            self.recognize_area: List[int] = config.get('recognize_area', [0, 0, 0, 0])  
            self.template: str = config.get('template', '')
            self.threshold: Union[float, List[float]] = config.get('threshold', 0.7)
        # 颜色匹配
        elif self.recognition == "ColorMatch":
            self.recognize_area: List[int] = config.get('recognize_area', [0, 0, 0, 0])  
            self.color_point: List[int] = config.get('color_point')
            self.lower : int = config.get("lower", 0)
            self.upper : int = config.get("upper", 255)



    def _init_action_params(self, config: dict):
        """初始化动作相关参数"""
        # 点击参数
        if self.action == "Click":
            self.target: Union[bool, List[int]] = config.get('target', True)
            self.target_offset: List[int] = config.get('target_offset', [0, 0])

        # 滑动参数
        elif self.action == "Swipe":
            self.begin: Union[bool, List[int]] = config.get('begin', True)
            self.begin_offset: List[int] = config.get('begin_offset', [0, 0])
            self.end: Union[bool, List[int]] = config.get('end', True)
            self.end_offset: List[int] = config.get('end_offset', [0, 0])
            self.duration: float = config.get('duration', 0.2)
        
        # 多目标点击
        # elif self.action == "MultiClick":
        #     self.target_offset: List[int] = config.get('target_offset', [0, 0])

        # 按键参数
        elif self.action == "Key":
            keys = config.get('key', [])
            self.key: List[str] = [keys] if isinstance(keys, str) else keys

        # 自定义参数
        elif self.action == "Custom":
            self.custom_name = config.get("custom_name", None)
            if (self.custom_name == "None"):
                print("Unknown Custom")
                raise ValueError("Unknown Custom")
        
        # 系列任务终止的检查点
        elif self.action == "Checkpoint":
            self.target_task_count_name = config.get("target_task_count_name","")
            self.current_task_name = config.get("current_task_name","")
            self.next_task_name = config.get("next_task_name","")

    def click_action(self):
        click_list = None
        if (type(self.target) == list):
            click_center = deepcopy(self.target)
        else:
            click_center = deepcopy(self.recognize_center)

        click_center[0] += self.target_offset[0] + generate_random_num(-7, 7)
        click_center[1] += self.target_offset[1] + generate_random_num(-7, 7)
        self.mk.moveClick(click_center, click_count=self.action_count, rest_time=self.action_rest)
        self.mk.mouseBackHome()



    def swipe_action(self):
        if (type(self.begin) == bool):
            start = deepcopy(self.recognize_center)
        else:
            start = self.begin
        if (type(self.end) == bool):
            end = deepcopy(self.recognize_center)
        else:
            end = self.end

        # start += self.begin_offset + generate_random_list(-7, -7)
        # end += self.end_offset + generate_random_list(-7, -7)
        start[0] += self.begin_offset[0] + generate_random_num(-7,7)
        start[1] += self.begin_offset[1] + generate_random_num(-7,7)
        end[0] += self.end_offset[0] + generate_random_num(-7,7)
        end[1] += self.end_offset[1] + generate_random_num(-7,7)

        self.mk.dragMouse([start[0], start[1], end[0], end[1]], self.duration)
        self.mk.mouseBackHome()


    def key_action(self):
        for single_key in self.key:
            self.mk.pressKey(single_key, press_count=self.action_count, rest_time=self.action_rest)


    def end_action(self, **kwargs):
        executed = kwargs.get("executed_time")
        target_task_count_dict = kwargs.get("target_task_count", {})
        target_count = target_task_count_dict.get(self.target_task_count_name, 0)

        if executed >= target_count:
            kwargs.get("target_task_count", {})["Pass"] = 1
            self.next[0] = self.next_task_name
        else:
            self.next[0] = self.current_task_name


    def _init_action_function(self):
        """根据动作类型初始化执行函数"""
        if self.action == "Click":
            return self.click_action
        elif self.action == "Swipe":
            return self.swipe_action
        elif self.action == "Key":
            return self.key_action
        elif self.action == "Custom":
            if self.custom_action_dict.get(self.custom_name) is None:
                raise ValueError(f"正在尝试从自定义活动调用不存在的自定义活动[{self.custom_name}]")
            return custom_action_dict[self.custom_name]
        elif self.action == "Checkpoint":
            return self.end_action
        else:
            return None
        
    
    def _init_recognize_function(self):
        """根据识别类型初始化识别函数"""
        if self.recognition == "TemplateMatch":
            return self.eye.templateMatch
        elif self.recognition == "ColorMatch":
            return self.eye.rgbDetection
        else:
            return lambda:(None, None)



    @staticmethod
    def _normalize_list(value: Union[str, List]) -> List:
        """统一处理字符串和列表类型的字段"""
        if isinstance(value, str):
            return [value]
        return value.copy() if value else []
    

    # 执行检测逻辑
    def execute_recognize(self):
        """执行检测，把检测结果保存自身"""
        # print(f"eye编号：{id(self.eye)}")
        if (self.recognition == "DirectHit"):
            lalc_logger.log_task(
                    "INFO",
                    self.name,
                    f"DirectHit Not Recognize"
                    )
            return
        lalc_logger.log_task(
                    "INFO",
                    self.name,
                    f"Execute Recognize:[{self.recognition}]"
                    )
        if self.recognition == "TemplateMatch":
            self.recognize_center, self.recognize_score = self.recognition_function(self.template, threshold=self.threshold, recognize_area=self.recognize_area)
            lalc_logger.log_task(
                    "DEBUG",
                    self.name,
                    f"[{self.recognition}] FINISH, recognize_center:[{self.recognize_center}]; recognize_score:[{self.recognize_score}]"
                    )
            if(self.recognize_center == None):
                return
            print(f"[{self.name}] 识别中心点坐标：[{self.recognize_center}];识别分数：[{self.recognize_score}]")
        elif self.recognition == "ColorMatch":
            self.recognize_score = self.recognition_function(coordinate=self.color_point, recognize_area=self.recognize_area)
            lalc_logger.log_task(
                    "DEBUG",
                    self.name,
                    f"[{self.recognition}] FINISH, recognize_score:[{self.recognize_score}]; lower:[{self.lower}]; upper:[{self.upper}]"
                    )
            if self.recognize_score < self.lower or self.recognize_score > self.upper:
                self.recognize_score = -1
                return
        else:
            raise ValueError("Unexpected recognition: {0}".format(self.recognition))
        

    def update_screenshot(self):
        self.eye.captureScreenShot()

    # 执行任务逻辑 
    def execute_task(self, **kwargs):
        """执行任务"""
        
        self.eye.waitFreeze(self.pre_wait_freezes)
        sleep(self.pre_delay)
        self.mk.updateMouseBasepoint()
        lalc_logger.log_task(
            "INFO",
            self.name,
            f"Action: {self.action}"
            )
        print(f"[{self.name}] 执行动作: {self.action}")
        if (self.action != "DoNothing"):
            activateWindow()
            if (self.action=="Custom" or self.action=="Checkpoint"):
                self.action_function(**kwargs)
            else:
                self.action_function()

        self.eye.waitFreeze(self.post_wait_freezes)
        sleep(self.post_delay)



custom_action_dict = None
def initCustomAction():
    global custom_action_dict

    if (not (custom_action_dict is None)):
        return custom_action_dict
    
    custom_action_dict = CustomActionDict()

    mk = get_mouse_keyboard()
    eye = get_eye()

    @custom_action_dict.register
    def click_all_pass_mission_coin(**kwarg):
        click_list = eye.templateMultiMatch("pass_mission_coin.png")
        for click_center in click_list:
            mk.moveClick([click_center[0], click_center[1]])
            sleep(0.6)

    @custom_action_dict.register
    def test_task_executed_time(**kwargs):
        t = kwargs.get("executed_time")
        print(get_team_by_index(t))

    

    @custom_action_dict.register
    def choose_team(**kwargs):
        team_index = get_team_by_index(kwargs.get("executed_time"))
        mk.moveClick([150, 630])
        mk.scroll([0,1], 30, 0.01)
        sleep(0.5)
        if (team_index > 4):
            scroll_count = team_index // 4 * 7
            mk.scroll([0, -1], scroll_count=scroll_count, rest_time=0.02)
        while(team_index > 4):
            team_index -= 4
        if (team_index == 1):
            mk.moveClick([150, 555])
        elif (team_index == 2):
            mk.moveClick([150, 600])
        elif (team_index == 3):
            mk.moveClick([150, 650])
        elif (team_index == 4):
            mk.moveClick([150, 700])
        else:
            raise ValueError("Over Index in choose_team")
        sleep(0.2)

        mk.pressKey("enter")

        mk.mouseBackHome()

    @custom_action_dict.register
    def choose_star_buff(**kwargs):
        mk.moveClick([1040, 400])
        mk.moveClick([810, 665])
        mk.moveClick([585, 665])
        mk.moveClick([1280, 400])
        mk.moveClick([350, 400])
        # 下面是结算
        mk.moveClick([1440, 900], rest_time=2)
        mk.moveClick([945, 720])
        mk.mouseBackHome()

    
    @custom_action_dict.register
    def choose_start_ego_gift(**kwargs):
        team_index = get_team_by_index(kwargs.get("executed_time"))
        team_style = get_style_by_team(team_index)


        if (team_style == "Burn"):
            mk.moveClick([260, 360])
        elif (team_style == "Bleed"):
            mk.moveClick([450, 360])
        elif (team_style == "Tremor"):
            mk.moveClick([650, 360])
        elif (team_style == "Rupture"):
            mk.moveClick([830, 360])
        elif (team_style == "Sinking"):
            mk.moveClick([260, 630])
        elif (team_style == "Poise"):
            mk.moveClick([450, 630])
        elif (team_style == "Charge"):
            mk.moveClick([650, 630])
        else:
            raise ValueError("Over Team Style in choose_start_ego_gift")
        
        mk.moveClick([1045, 380], rest_time=0.5)
        mk.moveClick([1045, 510], rest_time=0.5)
        mk.moveClick([1045, 650], rest_time=0.5)
        mk.pressKey("enter", press_count=2, rest_time=1)


        
    def get_style_by_team(team_number: int, json_path: str = "team.json") -> str:
        """
        根据队伍编号返回对应队伍的 style。

        :param team_number: 队伍编号（1, 2, 3, 4 等）
        :param json_path: team.json 文件的路径（默认: "team.json"）
        :return: 队伍的 style（字符串），如果队伍不存在或没有 style 字段，则返回空字符串
        """
        # 读取 team.json 文件
        try:
            json_path = join(CONFIG_DIR, json_path)
            with open(json_path, "r", encoding="utf-8") as f:
                teams = json.load(f)
        except Exception as e:
            print(f"无法加载队伍配置：{e}")
            return ""

        # 构造队伍名称（如 "Team1", "Team2" 等）
        team_name = f"Team{team_number}"

        # 获取对应队伍的 style
        team_data = teams.get(team_name, {})
        style = team_data.get("style", "")

        return style


    def get_team_by_index(index: int, json_path: str = "team.json") -> int:
        """
        根据传入的数字返回要使用的队伍编号。

        :param index: 传入的数字（从 0 开始）
        :param json_path: team.json 文件的路径（默认: "team.json"）
        :return: 队伍编号（1, 2, 3, 4 等）
        """
        json_path = join(CONFIG_DIR, json_path)
        # 读取 team.json 文件
        with open(json_path, "r", encoding="utf-8") as f:
            teams = json.load(f)

        offset = teams.get("TeamOffset")
        
        # 过滤出 enabled 为 true 的队伍
        enabled_teams = [team_name for team_name, team_data in teams.items() if (type(team_data) != int and team_data.get("enabled", False))]
        
        # 计算有效队伍的数量
        num_enabled_teams = len(enabled_teams)
        
        # 如果没有任何有效队伍，返回 -1
        if num_enabled_teams == 0:
            return -1
        
        # 计算传入数字对应的队伍索引
        team_index = (index + offset) % num_enabled_teams
        
        # 获取对应的队伍名称（如 "Team1", "Team2" 等）
        team_name = enabled_teams[team_index]
        
        # 提取队伍编号（去掉 "Team" 前缀）
        team_number = int(team_name.replace("Team", ""))
        
        return team_number
    

    @custom_action_dict.register
    def get_team_name_by_index(index: int, json_path: str = "team.json") -> int:
        """
        根据传入的数字返回要使用的队伍名字。

        :param index: 传入的数字（从 0 开始）
        :param json_path: team.json 文件的路径（默认: "team.json"）
        :return: 队伍编号（1, 2, 3, 4 等）
        """
        # 读取 team.json 文件
        json_path = join(CONFIG_DIR, json_path)
        with open(json_path, "r", encoding="utf-8") as f:
            teams = json.load(f)

        offset = teams.get("TeamOffset")
        
        # 过滤出 enabled 为 true 的队伍
        enabled_teams = [team_name for team_name, team_data in teams.items() if (type(team_data) != int and team_data.get("enabled", False))]
        
        # 计算有效队伍的数量
        num_enabled_teams = len(enabled_teams)
        
        # 如果没有任何有效队伍，返回 -1, 不应存在
        if num_enabled_teams == 0:
            raise IndexError("No Enabled Team")

        
        # 计算传入数字对应的队伍索引
        team_index = (index + offset) % num_enabled_teams
        
        # 获取对应的队伍名称（如 "Team1", "Team2" 等）
        team_name = enabled_teams[team_index]
        
        
        return team_name

    
    @custom_action_dict.register 
    def clear_and_edit_team_member_selections(**kwargs):
        # skip selection
        eye.captureScreenShot()
        if (eye.templateMactchExist("team_selection_1212.png", recognize_area=[1410, 665, 150, 80])):
            mk.pressKey("enter")
            return
        
        # clear selection
        mk.moveClick([1440, 650], rest_time=1.5)
        eye.captureScreenShot()
        if (eye.templateMactchExist("reset_deployment_order.png", recognize_area=[555, 395, 500, 160])):
            mk.pressKey("enter", rest_time=1)



        # select
        team_index = get_team_by_index(kwargs.get("executed_time"))
        members = get_sorted_members_by_team(team_index)

        for sinner in members:
            mk.moveClick(sinner_place[sinner])
        mk.mouseBackHome()
        mk.pressKey("enter")
        


    def get_sorted_members_by_team(team_number: int, json_path = "team.json") -> list[str]:
        """
        根据队伍编号获取按序号升序排列的字符串列表（人物名称）。

        :param team_number: 队伍编号（1, 2, 3, 4 等）
        :param json_path: team.json 文件的路径（默认: "team.json"）
        :return: 按序号升序排列的人物名称列表，如果队伍不存在或没有数据，则返回空列表
        """
        # 读取 team.json 文件
        try:
            json_path = join(CONFIG_DIR, json_path)
            with open(json_path, "r", encoding="utf-8") as f:
                teams = json.load(f)
        except Exception as e:
            print(f"无法加载队伍配置：{e}")
            return []

        # 构造队伍名称（如 "Team1", "Team2" 等）
        team_name = f"Team{team_number}"

        # 获取对应队伍的数据
        team_data = teams.get(team_name, {})

        # 过滤掉非人物字段（如 "enabled", "style" 等）
        characters = [
            (name, order) for name, order in team_data.items()
            if (type(team_data) != int and isinstance(order, int) and name in sinner_name)  # 只保留 order 是整数的字段
        ]

        # 按 order 升序排序
        sorted_characters = sorted(characters, key=lambda x: x[1])

        # 提取排序后的人物名称
        sorted_members = [name for name, _ in sorted_characters]

        return sorted_members
    
    
    def search_place_sell_gift(gift_places:list, target_pic:list):
        for c in gift_places:
            while True:
                mk.moveClick(c)
                eye.captureScreenShot()
                sellable = True
                if (eye.templateMactchExist("shop_vestige.png", recognize_area=[290, 240, 400, 200])):
                    sellable = True
                else:
                    for gift in target_pic:
                        if (gift == "shop_enhance_keywordless.png" and eye.templateMactchExist("shop_sell_ego_resource.png", recognize_area=[180, 450, 540, 260])):
                            sellable = True
                            break
                        if (eye.templateMactchExist(gift, recognize_area=[290, 240, 310, 200], threshold=0.7)):
                            sellable = False
                            break

                if (sellable and eye.templateMactchExist("shop_triangle.png", recognize_area=[1285, 150, 60, 50])):
                    mk.pressKey("enter", press_count=2, rest_time=1)
                    sleep(2)
                    continue
                
                break

    


    @custom_action_dict.register
    def sell_unwanted_ego_gift(**kwargs):
        mk.moveClick([505, 540], rest_time=1)
        team_index = get_team_by_index(kwargs.get("executed_time"))
        team_style = get_style_by_team(team_index)

        target_pic = []
        if (team_style == "Bleed"):
            target_pic.append("shop_enhance_bleed.png")
        elif(team_style == "Burn"):
            target_pic.append("shop_enhance_burn.png")
        elif(team_style == "Charge"):
            target_pic.append("shop_enhance_charge.png")
        elif(team_style == "Poise"):
            target_pic.append("shop_enhance_poise.png")
        elif(team_style == "Rupture"):
            target_pic.append("shop_enhance_rupture.png")
        elif(team_style == "Sinking"):
            target_pic.append("shop_enhance_sinking.png")
        elif(team_style == "Tremor"):
            target_pic.append("shop_enhance_tremor.png")
        else:
            raise ValueError("Unknown Style: %s", team_style)

        target_pic.append("shop_enhance_keywordless.png")
        target_pic.append("shop_enhanced_keywordless.png")

        gift_places = []
        x = 860
        y = 370
        y = 370
        x_step = 115
        y_step = 120
        for i in range(3):
            for j in range(5):
                gift_places.append([x + j*x_step, y + i*y_step])



        while True:
            search_place_sell_gift(gift_places, target_pic)
            eye.captureScreenShot()
            if (not eye.templateMactchExist("shop_scroll_block.png", recognize_area=[1375, 310, 55, 370])):
                break
            if (len(gift_places) != 10):
                gift_places = gift_places[5:]
            if (not eye.templateMactchExist("shop_scroll_block.png", recognize_area=[1375, 600, 55, 80])):
                mk.scroll([0,-1], 5, rest_time=0.2)
            else:
                break
         
            
        mk.pressKey("esc", rest_time=2)
        mk.mouseBackHome()

    style_refresh = {
                    "Burn":[420, 415],
                    "Bleed":[610, 415],
                    "Tremor":[800, 415],
                    "Rupture":[990, 415],
                    "Sinking":[1180, 415],
                    "Poise":[420, 590],
                    "Charge":[610, 590],
                     }
    def refresh_according_to_team_style(team_style:str):
        mk.moveClick([1435, 200], rest_time=0.5)
        mk.moveClick(style_refresh[team_style])
        mk.moveClick([990, 745], rest_time=3)   
        mk.mouseBackHome()


    
    @custom_action_dict.register
    def purchase_wanted_ego_gift(**kwargs):
        eye.captureScreenShot()
        if eye.templateMactchExist("shop_heal_sinner_not_enough_cost.png", recognize_area=[180, 600, 160, 90]):
            lalc_logger.log_task("DEBUG", "purchase_wanted_ego_gift", "FAILED", "Not Enough Cost")
            return

        team_index = get_team_by_index(kwargs.get("executed_time"))
        team_style = get_style_by_team(team_index)

        goods_places = [[985, 365], [1175, 365], [1365, 365], [785, 550], [985, 550], [1175, 550]]

        target_pic = []

        if (team_style == "Bleed"):
            target_pic.append("shop_purchase_bleed.png")
        elif(team_style == "Burn"):
            target_pic.append("shop_purchase_burn.png")
        elif(team_style == "Charge"):
            target_pic.append("shop_purchase_charge.png")
        elif(team_style == "Poise"):
            target_pic.append("shop_purchase_poise.png")
        elif(team_style == "Rupture"):
            target_pic.append("shop_purchase_rupture.png")
        elif(team_style == "Sinking"):
            target_pic.append("shop_purchase_sinking.png")
        elif(team_style == "Tremor"):
            target_pic.append("shop_purchase_tremor.png")
        else:
            raise ValueError("Unknown team style: %s" % (team_style))
        
        target_pic.append("shop_purchase_keywordless.png")

        purchased_count = 0
        round_count = 0

        while(True):
            for place in goods_places:
                if goods_places.index(place) < purchased_count:
                    continue
                mk.moveClick(place, rest_time=1)
                eye.captureScreenShot()
                if (eye.templateMactchExist("purchase_ego_gift.png", recognize_area=[500, 230, 400, 60])):
                    for gift in target_pic:
                        if (gift == "shop_purchase_keywordless.png" and eye.templateMactchExist("shop_purchase_ego_resource.png", recognize_area=[655, 305, 520, 300])):
                            continue
                        if (eye.templateMactchExist(gift, recognize_area=[575, 405, 60, 60])):
                            mk.moveClick([945, 660], rest_time=1)
                            mk.pressKey("enter", press_count=2, rest_time=0.3)
                            purchased_count += 1
                            break
                    mk.pressKey("enter", press_count=1, rest_time=0.4)
                else:
                    mk.pressKey("enter", press_count=2, rest_time=0.4)
                    continue
                
                eye.captureScreenShot()
                if eye.templateMactchExist("shop_heal_sinner_not_enough_cost.png", recognize_area=[180, 600, 160, 90]):
                    lalc_logger.log_task("DEBUG", "purchase_wanted_ego_gift", "FAILED", "Not Enough Cost")
                    return

            eye.screenshotOcr(recognize_area=[665, 190, 160, 55])
            rest_cost = eye.ocrGetFirstNum()
            if (purchased_count>2 or rest_cost < (450 + 75*purchased_count)):
                break
            
            if (rest_cost >= (540 + round_count*300)):
                refresh_according_to_team_style(team_style=team_style)
            else:
                mk.moveClick([1260, 200], rest_time=3)
            
            round_count += 1



    
    def search_place_enhance_ego(gift_places:list, target_pic:list, gift_recognize_area:list):
        fake_enhance_count = 3 # reduce the waste of time for the last ego gift can not be enhanced
        eye.captureScreenShot()
        gift_places += eye.templateMultiMatch("shop_enhance_left_bottom_corner.png", threshold=0.7, recognize_area=gift_recognize_area)

        for c in gift_places:
            if (fake_enhance_count <= 0):
                lalc_logger.log_task("DEBUG", "search_place_enhance_ego", "INTERRUPTED", "Due to too many fake enhanceable.")
                break
            c[0] += 20
            mk.moveClick(c, rest_time=0.2)
            eye.captureScreenShot()
            enhance_able = False

            if (not eye.templateMactchExist("shop_triangle.png", recognize_area=[1285, 150, 60, 50])):
                continue

            for gift in target_pic:
                if (eye.templateMactchExist(gift, recognize_area=[290, 240, 310, 200])):
                    enhance_able = True
                    break
            
            if (enhance_able):
                mk.pressKey("enter", press_count=1, rest_time=1)
                fake_enhance_count -= 1
                eye.captureScreenShot()
                if (eye.templateMactchExist("power_up.png", recognize_area=[820, 735, 330, 100])):
                    continue
                if (eye.templateMactchExist("shop_you_need.png", recognize_area=[365, 655, 300, 80])):
                    mk.pressKey("esc", rest_time=0.5)
                    continue
                mk.pressKey("enter", press_count=1, rest_time=2)
                fake_enhance_count = 3
                
                mk.pressKey("enter", press_count=1, rest_time=1)
                eye.captureScreenShot()
                if (eye.templateMactchExist("power_up.png", recognize_area=[820, 735, 330, 100])):
                    continue
                if (eye.templateMactchExist("shop_you_need.png", recognize_area=[365, 655, 300, 80])):
                    mk.pressKey("esc", rest_time=0.5)
                    continue
                mk.pressKey("enter", press_count=1, rest_time=2)
            
            eye.captureScreenShot()
            if (not eye.templateMactchExist("power_up.png", recognize_area=[820, 735, 330, 100])):
                mk.pressKey("esc", rest_time=1)



    @custom_action_dict.register
    def enhance_wanted_ego_gift(**kwargs):
        eye.captureScreenShot()
        if eye.templateMactchExist("shop_heal_sinner_not_enough_cost.png", recognize_area=[180, 600, 160, 90]):
            lalc_logger.log_task("DEBUG", "enhance_wanted_ego_gift", "FAILED", "Not Enough Cost")
            return
        mk.moveClick([215,540], rest_time=1)

        team_index = get_team_by_index(kwargs.get("executed_time"))
        team_style = get_style_by_team(team_index)

        target_pic = []
        if (team_style == "Bleed"):
            target_pic.append("shop_enhance_bleed.png")
        elif(team_style == "Burn"):
            target_pic.append("shop_enhance_burn.png")
        elif(team_style == "Charge"):
            target_pic.append("shop_enhance_charge.png")
        elif(team_style == "Poise"):
            target_pic.append("shop_enhance_poise.png")
        elif(team_style == "Rupture"):
            target_pic.append("shop_enhance_rupture.png")
        elif(team_style == "Sinking"):
            target_pic.append("shop_enhance_sinking.png")
        elif(team_style == "Tremor"):
            target_pic.append("shop_enhance_tremor.png")
        else:
            raise ValueError("Unknown Style: %s", team_style)

        target_pic.append("shop_enhance_keywordless.png")

        gift_places = []
        x = 860
        y = 370
        gift_places.append([x, y]) # first place
        # x_step = 115
        # y_step = 120
        # for i in range(3):
        #     for j in range(5):
        #         gift_places.append([x + j*x_step, y + i*y_step])

        gift_recognize_area = [0, 0, 0, 0]
        while True:
            search_place_enhance_ego(gift_places, target_pic, gift_recognize_area=gift_recognize_area)
            eye.captureScreenShot()
            if (not eye.templateMactchExist("shop_scroll_block.png", recognize_area=[1375, 310, 55, 370])):
                break
            gift_places.clear()
            # if (len(gift_places) != 10):
            #     gift_places = gift_places[5:]
            if (not eye.templateMactchExist("shop_scroll_block.png", recognize_area=[1375, 600, 55, 80])):
                mk.scroll([0,-1], 5, rest_time=0.2)
                gift_recognize_area = [790, 425, 640, 290]
            else:
                break
        
        mk.moveClick([1450, 860], rest_time=1)
        # mk.pressKey("esc", rest_time=1)
        mk.mouseBackHome()

    @custom_action_dict.register
    def heal_all_sinner(**kwargs):
        eye.captureScreenShot()
        if eye.templateMactchExist("shop_heal_sinner_not_enough_cost.png", recognize_area=[180, 600, 160, 90]):
            lalc_logger.log_task("DEBUG", "heal_all_sinner", "FAILED", "Not Enough Cost")
            return
        mk.moveClick([255, 640], rest_time=2)
        eye.captureScreenShot()
        if eye.templateMactchExist("heal_sinners.png", recognize_area=[125, 60, 325, 110]):
            mk.moveClick([1280, 460], rest_time=2)
            mk.moveClick([1415, 860], rest_time=2)
        
        mk.mouseBackHome()

    @custom_action_dict.register
    def select_theme_pack(**kwargs):
        eye.captureScreenShot()
        eye.screenshotOcr(recognize_area=[210, 580, 1200, 80])
        
        simple_keyword = theme_pack_manager.get_keywords_by_weight(1)
        hard_keyword = theme_pack_manager.get_keywords_by_weight(100)

        if find_choose_simple_theme_pack(simple_keyword):
            sleep(4)
            return
        
        if find_hard_theme_pack(hard_keyword):
            mk.moveClick([1370, 100])
            sleep(4)

            eye.captureScreenShot()
            eye.screenshotOcr(recognize_area=[210, 580, 1200, 80])
            if find_choose_simple_theme_pack(simple_keyword):
                sleep(4)
                return
            
        mk.mouseBackHome()

        

    
    def find_choose_simple_theme_pack(simple_keyword:list):
        lalc_logger.log_task("DEBUG", "find_choose_simple_theme_pack", "STARTED", "")
        for keyword in simple_keyword:
            center = eye.queryOcrDict(keyword)
            if center != None:
                mk.dragMouse([center[0], center[1], center[0], center[1]+400])
                return True
            
        return False

    def find_hard_theme_pack(hard_keyword:list):
        lalc_logger.log_task("DEBUG", "find_hard_theme_pack", "STARTED", "")
        for keyword in hard_keyword:
            center = eye.queryOcrDict(keyword)
            if center != None:
                # mk.dragMouse([center[0], center[1], center[0], center[1]+400])
                return True
            
        return False

    @custom_action_dict.register
    def claim_previous_reward(**kwargs):
        raise ValueError("请自行确认之前的收益。 | Please claim your reward.")


    @custom_action_dict.register
    def network_unstable_stop(**kwargs):
        raise ValueError("网络不稳定，请自行重启。 | Please restart due to the unstable network.")

    @custom_action_dict.register
    def remind_assemble_enkephalin_modules(**kwargs):
        raise ValueError("脑啡肽模组不足，请自行合成并确认奖励。 | Do not have enough enkephalin modules, assemble it and claim the rewards plz.")


    
task_dict = initJsonTask()