"""
任务执行模块，负责执行具体的操作如点击、键盘输入等
"""
import time
import difflib
import asyncio

from input.input_handler import input_handler
from recognize.img_recognizer import recognize_handler
from recognize.img_registry import get_images_by_tag, get_max_radio_of_ego_gifts
from workflow.task_node import TaskNode
from workflow.task_registry import get_task
from utils.get_save_theme_packs import detect_and_save_theme_pack
from utils.logger import init_logger

logger = init_logger()

# 新增：让 TaskExecution 能把日志推给 Server
_server_to_push = None          # 由 ServerController 启动时注入

def set_server_ref(server):
    global _server_to_push
    _server_to_push = server

class TaskExecution:

    # --------- 类级别：装饰器注册表 ---------
    DECORATED_HANDLERS = {}   # {"click": function, ...}

    @classmethod
    def register(cls, name: str):
        """
        装饰器：注册 register task
        用法：
            @TaskExecution.register("click")
            def exec_click(self, node):
        """
        def decorator(func):
            cls.DECORATED_HANDLERS[name] = func
            return func
        return decorator



    # --------- 初始化：加载所有通过装饰器注册的 handler ---------
    def __init__(self, shared_params):
        self.shared_params = shared_params
        self.exp_cfg = shared_params["exp_cfg"]
        self.thread_cfg = shared_params["thread_cfg"]
        self.mirror_cfg = shared_params["mirror_cfg"]
        self.other_task_cfg = shared_params["other_task_cfg"]
        self.theme_pack_cfg = shared_params["theme_pack_cfg"]
        self.handlers = {}

        # 自动注册所有装饰器登记的函数
        self._register_decorated_handlers()
        logger.log("TaskExecution 初始化完成")

    
    def _get_using_cfg_index(self, cfg_type:str) -> int:
        cfg = self._get_using_cfg(cfg_type)
        using_team_len = len(cfg["team_orders"]) 
        check_node_name = cfg_type + "_check"
        team_no = get_task(check_node_name).get_param("execute_count") 

        return team_no%using_team_len 

    
    def _get_using_cfg(self, cfg_type:str):
        match cfg_type:
            case "exp":
                return self.exp_cfg
            case "thread":
                return self.thread_cfg
            case "mirror":
                return self.mirror_cfg
            case "other_task":
                return self.other_task_cfg
            case "theme_pack":
                return self.theme_pack_cfg
            case _:
                raise Exception(f"出现未知配置类型：{cfg_type}")


    def _register_decorated_handlers(self):
        """
        将所有 @TaskExecution.register() 装饰器注册的函数：
        - 绑定到实例的 self.handlers[name]
        - 同时绑定为 self.exec_{name} 方便直接调用
        """
        for name, func in TaskExecution.DECORATED_HANDLERS.items():
            bound = func.__get__(self, TaskExecution)

            # 加入 handler 表
            self.handlers[name] = bound

            # 自动绑定为 self.exec_click / self.exec_wait_disappear / ...
            setattr(self, f"exec_{name}", bound)


    # --------- 执行入口 ---------
    def execute(self, pre_task_name, func):
        """
        Pipeline pop 出来的 func 会传进来执行
        func = 某个 TaskNode 的 do_action 或 get_next
        返回必须为 tuple: (func_next, ...)
        """
        cur_task = get_task(func.__self__.name)
        
        if func.__name__ == "do_action":
            action_name = cur_task.action.name
        else:
            action_name = "next"
        
        # 修改为：先写本地日志，再推一条 task_log 给 Server
        log_msg = f"任务{{{cur_task.name}}}正在执行：{{{func.__name__}}}-{{{action_name}}}"
        logger.log(log_msg)
        if _server_to_push:
            try:
                # 检查是否有正在运行的事件循环
                asyncio.get_running_loop()
                # 如果有，则可以直接创建任务
                asyncio.create_task(_server_to_push.broadcast_task_log(log_msg))
            except RuntimeError:
                # 如果没有运行的事件循环，则将任务提交到服务器的事件循环中
                asyncio.run_coroutine_threadsafe(_server_to_push.broadcast_task_log(log_msg), _server_to_push.loop)

        if action_name in self.handlers:
            time.sleep(cur_task.get_param("pre_delay"))
            res = self.handlers[action_name](cur_task, func)
            if res is None:
                res = (cur_task.name, None, None)
            time.sleep(cur_task.get_param("post_delay"))
        else:
            res = func()

        # 修改为：先写本地日志，再推一条 task_log 给 Server
        log_msg = f"任务{{{cur_task.name}}}已执行：{{{func.__name__}}}-{{{action_name}}}"
        logger.log(log_msg)
        if _server_to_push:
            try:
                # 检查是否有正在运行的事件循环
                asyncio.get_running_loop()
                # 如果有，则可以直接创建任务
                asyncio.create_task(_server_to_push.broadcast_task_log(log_msg))
            except RuntimeError:
                # 如果没有运行的事件循环，则将任务提交到服务器的事件循环中
                asyncio.run_coroutine_threadsafe(_server_to_push.broadcast_task_log(log_msg), _server_to_push.loop)
            
        return res



# ====== 以下开始写所有 task，全部用装饰器注册 =======
# 如果一个节点的 action 与节点同名，那么下面返回的时候就不要再返回这个 action func 的返回值，否则会无限递归执行该 action
@TaskExecution.register("error_cannot_operate_the_game")
def exec_error_cannot_operate_the_game_window(self, node:TaskNode, func):
    logger.log("开始重启 Limbus")
    # 先尝试关闭现有的Limbus窗口
    input_handler.close_limbus_window()
    time.sleep(2)  # 等待窗口完全关闭
    
    # 重新打开Limbus窗口
    input_handler.open_limbus()
    input_handler.refresh_window_state()
    input_handler.set_window_size()
    logger.log("结束重启 Limbus", input_handler.capture_screenshot())
    
@TaskExecution.register("confirm_all_coins")
def exec_confirm_all_coins(self, node:TaskNode, func):
    logger.log("开始收集日常的奖励")
    for pos in recognize_handler.template_match(input_handler.capture_screenshot(), "reward_coin"):
        input_handler.click(pos[0], pos[1])
        self.exec_wait_disappear(get_task("wait_connecting_disappear"))
    
    input_handler.click(270, 400)
    time.sleep(1)
    logger.log("开始收集周常的奖励")
    for pos in recognize_handler.template_match(input_handler.capture_screenshot(), "reward_coin"):
        input_handler.click(pos[0], pos[1])
        self.exec_wait_disappear(get_task("wait_connecting_disappear"))


@TaskExecution.register("init_limbus_window")
def exec_init_limbus_window(self, node:TaskNode, func):
    logger.log("开始初始化Limbus窗口")
    input_handler.open_limbus()
    input_handler.refresh_window_state()
    input_handler.set_window_size()
    logger.log("结束初始化Limbus窗口", input_handler.capture_screenshot())


@TaskExecution.register("mirror_victory")
def exec_mirror_victory(self, node:TaskNode, func):
    logger.log("处理镜牢胜利结算", input_handler.capture_screenshot())
    cfg = self._get_using_cfg("other_task")
    test_mode = cfg["test_mode"]
    if not test_mode:
        for _ in range(4):
            input_handler.key_press("enter")
            time.sleep(1)
        self.exec_wait_disappear(get_task("wait_connecting_disappear"))
        for _ in range(3):
            input_handler.key_press("enter")
            time.sleep(1)
    else:
        for _ in range(2):
            input_handler.key_press("enter")
            time.sleep(1)
        input_handler.click(395, 550)
        time.sleep(1)
        input_handler.key_press("enter")



@TaskExecution.register("mirror_select_floor_ego_gift")
def exec_mirror_select_floor_ego_gift(self, node:TaskNode, func):
    logger.log("选择楼层EGO饰品", input_handler.capture_screenshot())
    cfg_type = node.get_param("cfg_type")
    cfg, cfg_index = self._get_using_cfg(cfg_type), self._get_using_cfg_index(cfg_type)
    prefer_gift_styles = cfg["mirror_team_ego_gift_styles"][cfg_index]
    prefer_gifts = set()
    for style in prefer_gift_styles:
        gift_tag = "ego_gifts_" + style
        prefer_gifts.update(x[0] for x in get_images_by_tag(gift_tag))
    
    gift_allow_list = cfg["mirror_team_ego_allow_list"][cfg_index]
    gift_block_list = cfg["mirror_team_ego_block_list"][cfg_index]
    prefer_gifts.update(gift_allow_list)
    prefer_gifts.difference_update(gift_block_list) # 黑名单优先,不过前端应该不会发生冲突
    all_gift_names = [x[0] for x in get_images_by_tag("ego_gifts")]
    max_ego_gifts_radio = get_max_radio_of_ego_gifts()

    tmp_screenshot = input_handler.capture_screenshot()
    cur_gifts = recognize_handler.detect_text_in_image(tmp_screenshot, mask=[90, 170, 1090, 40])
    prefer_cur_gifts = []

    for gift in cur_gifts:
        tmp = difflib.get_close_matches(gift[0], all_gift_names, cutoff=0.8)
        if len(tmp) == 0:
            logger.log(f"识别异常：识别不出饰品文字{gift[0]}", level="WARNING")
            continue
    
        if tmp[0] in prefer_gifts:
            logger.log(f"检测到有倾向的饰品{tmp}")
            prefer_cur_gifts.append((tmp, gift[1], gift[2]))
        
    acquire_and_owned = recognize_handler.detect_text_in_image(tmp_screenshot, mask=[110, 120, 1090, 60])

    # 分类 acquire_and_owned 中的文本
    owned_positions = [item for item in acquire_and_owned if item[0] == 'Owned']
    acquire_gifts = [item for item in acquire_and_owned if 'Acquire E.G.O Gift' in item[0]]
    
    # 将 acquire gifts 分成两类
    acquire_with_owned = []      # 左边有 Owned 的 Acquire E.G.O Gift
    acquire_without_owned = []   # 左边没有 Owned 的 Acquire E.G.O Gift
    
    for acquire in acquire_gifts:
        acquire_x = acquire[1]
        # 检查是否有 Owned 在其左侧 -200 范围内
        has_owned_on_left = any(
            owned[1] < acquire_x and acquire_x - owned[1] <= 200 
            for owned in owned_positions
        )
        
        if has_owned_on_left:
            acquire_with_owned.append(acquire)
        else:
            acquire_without_owned.append(acquire)
    
    # 分类 prefer_cur_gifts 模板匹配结果
    prefer_gift_without_owned = []      # 左边没有 Owned 的礼物
    
    for gift in prefer_cur_gifts:
        gift_x = gift[1]  # gift 格式为 (text, x, y, score)
        # 检查是否有 Owned 在其左侧 -200 范围内
        has_owned_on_left = any(
            owned[1] < gift_x and gift_x - owned[1] <= 200 
            for owned in owned_positions
        )
        
        if not has_owned_on_left:
            prefer_gift_without_owned.append(gift)

    last_acquire_ego_gift = ("last_acquire", *(recognize_handler.template_match(tmp_screenshot, "acquire_ego_gift")[0]))
    select_orders = [
        *prefer_gift_without_owned,
        *acquire_without_owned,
        *acquire_with_owned,
        last_acquire_ego_gift
    ]

    final_select = select_orders[0]
    input_handler.click(final_select[1], final_select[2])
    time.sleep(0.5)
    input_handler.key_press("enter")
    self.exec_wait_disappear(get_task("wait_connecting_disappear"))


@TaskExecution.register("mirror_select_encounter_reward_card")
def exec_mirror_select_encounter_reward_card(self, node:TaskNode, func):
    logger.log("选择奖励卡", input_handler.capture_screenshot())
    reward_cards = [
        "cost_card",
        "starlight_card",
        "ego_gift_card",
        "cost_ego_gift_card",
        "ego_resource_card",
    ]
    tmp_screenshot = input_handler.capture_screenshot()
    for card in reward_cards:
        res = recognize_handler.template_match(tmp_screenshot, card)
        if len(res) > 0:
            input_handler.click(res[0][0], res[0][1])
            logger.log(f"Reward Card 选择了 {card}", input_handler.capture_screenshot())
            break
    input_handler.key_press("enter")
    self.exec_wait_disappear(get_task("wait_connecting_disappear"))
    

enhance_sell_place = [
    (x, y) for y in range(260, 441, 90) for x in range(680, 1041, 90) 
]


@TaskExecution.register("mirror_shop_enhance_ego_gifts")
def exec_mirror_shop_enhance_ego_gifts(self, node:TaskNode, func):
    while True:
        input_handler.click(160, 390)
        time.sleep(1)
        if len(recognize_handler.template_match(input_handler.capture_screenshot(), "enhance_ego_gift")) > 0:
            break
    logger.log("强化EGO饰品", input_handler.capture_screenshot())
    cfg_type = node.get_param("cfg_type")
    cfg, cfg_index = self._get_using_cfg(cfg_type), self._get_using_cfg_index(cfg_type)
    prefer_gift_styles = cfg["mirror_team_ego_gift_styles"][cfg_index]
    prefer_gifts = set()
    for style in prefer_gift_styles:
        gift_tag = "ego_gifts_" + style
        prefer_gifts.update(x[0] for x in get_images_by_tag(gift_tag))
    
    gift_allow_list = cfg["mirror_team_ego_allow_list"][cfg_index]
    gift_block_list = cfg["mirror_team_ego_block_list"][cfg_index]
    prefer_gifts.update(gift_allow_list)
    prefer_gifts.difference_update(gift_block_list) # 黑名单优先,不过前端应该不会发生冲突
    all_gift_names = [x[0] for x in get_images_by_tag("ego_gifts")]
    max_ego_gifts_radio = get_max_radio_of_ego_gifts()
    logger.debug(f"本次倾向升级饰品名单：{prefer_gifts}")

    # enhance_target_style_icons = []
    # for style in prefer_gift_styles:
    #     enhance_target_style_icons.append("enhance_icon_"+style)
    
    need_more_money = 0
    def enhance_cur_gift():
        cur_gift = recognize_handler.detect_text_in_image(input_handler.capture_screenshot(), mask=[280, 150, 300, 130])
        if len(cur_gift) == 0:
            logger.log(f"识别异常：饰品升级区域识别不出文字", input_handler.capture_screenshot(), "WARNING")
            return
        cur_gift_name = cur_gift[0][0]
        tmp = difflib.get_close_matches(cur_gift_name, all_gift_names, cutoff=0.8)
        if len(tmp) == 0:
            logger.log(f"识别异常：在已有饰品中找不到饰品文字{cur_gift_name}")
            return
        cur_gift_name = tmp[0]
        nonlocal need_more_money

        if cur_gift_name in prefer_gifts:
            input_handler.key_press("enter")
            time.sleep(1)
            tmp_screenshot = input_handler.capture_screenshot()
            if len(recognize_handler.template_match(tmp_screenshot, "more_cost_to_enhance_this_ego_gift")) > 0:
                logger.log("缺钱不能升级，提前退出")
                input_handler.click(500, 590)
                need_more_money += 1
                return
            if len(recognize_handler.template_match(tmp_screenshot, "cost_to_enhance_this_ego_gift")) == 0:
                logger.log("总之不能升级，提前退出")
                return
            input_handler.key_press("enter")
            self.exec_wait_disappear(get_task("wait_connecting_disappear"))
            time.sleep(0.5)

            input_handler.key_press("enter")
            time.sleep(1)
            tmp_screenshot = input_handler.capture_screenshot()
            if len(recognize_handler.template_match(tmp_screenshot, "more_cost_to_enhance_this_ego_gift")) > 0:
                logger.log("缺钱不能升级，提前退出")
                input_handler.click(500, 590)
                need_more_money += 1
                return
            if len(recognize_handler.template_match(tmp_screenshot, "cost_to_enhance_this_ego_gift")) == 0:
                logger.log("总之不能升级，提前退出")
                return
            input_handler.key_press("enter")
            self.exec_wait_disappear(get_task("wait_connecting_disappear"))
            time.sleep(0.5)

    detect_places = [590, 180, 560, 350]
    first_page = True
    while True:
        tmp_screenshot = input_handler.capture_screenshot()
        enhance_pos = recognize_handler.precise_template_match(tmp_screenshot, "mirror_shop_ego_gift_corner_unselect", mask=detect_places)
        enhance_cur_gift()
        for x, y, _ in enhance_pos:
            input_handler.click(x+20, y-20)
            enhance_cur_gift()
            if need_more_money >= 2:
                break
        
        if need_more_money >= 2:
                break

        # 退出条件：要么检测不到滑块，要么滑块在最底下
        slider = recognize_handler.template_match(tmp_screenshot, "slider", mask=[1080, 190, 80, 360])
        if len(slider) > 0 and slider[0][1] < 440:
            input_handler.swipe(815, 395, 815, 290)
            time.sleep(1)
            if first_page:
                first_page = False
                # detect_places = [590, 390, 560, 140]
                detect_places[1] += 210
                detect_places[3] -= 210
        else:
            break
    input_handler.click(500, 590)
    time.sleep(1)
    # 点击 leave，为离开商店做准备
    input_handler.click(1120, 640)


replace_skill_map = {
    1:(300, 330),
    2:(630, 330),
    3:(960, 330),
}


keyword_refresh_map = {
    'Burn': (330, 290),
    'Bleed': (480, 290),
    'Tremor': (630, 290),
    'Rupture': (780, 290),
    'Sinking': (930, 290),
    'Poise': (330, 430),
    'Charge': (480, 430),
    'Slash': (630, 430),
    'Pierce': (780, 430),
    'Blunt': (930, 430),
}


@TaskExecution.register("mirror_shop_replace_skill_and_purchase_ego_gifts")
def exec_mirror_shop_replace_skill_and_purchase_ego_gifts(self, node:TaskNode, func):
    logger.log("替换技能并购买EGO饰品")
    cfg_type = node.get_param("cfg_type")
    cfg, cfg_index = self._get_using_cfg(cfg_type), self._get_using_cfg_index(cfg_type)
    
    left_money_for_enhance = cfg["mirror_stop_purchase_gift_money"]

    prefer_gift_styles = cfg["mirror_team_ego_gift_styles"][cfg_index]
    prefer_gifts = set()
    for style in prefer_gift_styles:
        gift_tag = "ego_gifts_" + style
        prefer_gifts.update(x[0] for x in get_images_by_tag(gift_tag))
    
    gift_allow_list = cfg["mirror_team_ego_allow_list"][cfg_index]
    gift_block_list = cfg["mirror_team_ego_block_list"][cfg_index]
    prefer_gifts.update(gift_allow_list)
    prefer_gifts.difference_update(gift_block_list) # 黑名单优先,不过前端应该不会发生冲突
    all_gift_names = [x[0] for x in get_images_by_tag("ego_gifts")]
    max_ego_gifts_radio = get_max_radio_of_ego_gifts()
    logger.debug(f"本次倾向购买饰品名单：{prefer_gifts}")

    def exec_replace_skill():
        name_of_who_can_replace = recognize_handler.detect_text_in_image(tmp_screenshot, mask=[535, 320, 165, 50])
        if len(name_of_who_can_replace) > 0:
            name_of_who_can_replace = name_of_who_can_replace[0]
            # cfg_type = node.get_param("cfg_type")
            # cfg, cfg_index = self._get_using_cfg(cfg_type), self._get_using_cfg_index(cfg_type)
            need_to_replace_skill = cfg["mirror_replace_skill"][cfg_index]
            skill_order = None
            for name in need_to_replace_skill.keys():
                if name in name_of_who_can_replace[0]:
                    logger.log(f"检测到罪人{name}可以且应该做技能替换")
                    input_handler.click(name_of_who_can_replace[1], name_of_who_can_replace[2]-80)
                    skill_order = need_to_replace_skill[name][::-1]
                    time.sleep(1)
                    break

            if skill_order:
                logger.debug(f"该罪人技能替换顺序：{skill_order}")
                for i in skill_order:
                    pos = replace_skill_map[i]
                    input_handler.click(*pos)
                logger.log(f"确认执行该罪人的技能替换", input_handler.capture_screenshot())
                input_handler.click(790, 535)
                time.sleep(0.5)
                input_handler.click(790, 535)
                self.exec_wait_disappear(get_task("wait_connecting_disappear"))
        else:
            logger.log("替换技能名字识别异常，跳过技能替换部分", level="WARNING")
    
    def exec_purchase_ego_gifts():
        gifts = recognize_handler.detect_text_in_image(tmp_screenshot, mask=[535, 325, 650, 50])
        other_line_gifts = recognize_handler.detect_text_in_image(tmp_screenshot, mask=[535, 480, 650, 50])
        gifts.extend(other_line_gifts)  

        purcased_list = recognize_handler.detect_text_in_image(tmp_screenshot, mask=[535, 200, 650, 40])
        other_line_purchased = recognize_handler.detect_text_in_image(tmp_screenshot, mask=[535, 355, 650, 40])
        purcased_list.extend(other_line_purchased)

        # 前两行能买的买完了
        if len(gifts) == len(purcased_list):
            logger.log("买了全部饰品，结束回合", input_handler.capture_screenshot())
            return False
        
        while purcased_list:
            purchased = purcased_list.pop()
            for gift in gifts:
                if purchased[2] < gift[2] < purchased[2] + 150 and abs(purchased[1] - gift[1]) < 50:
                    gifts.remove(gift)

        # logger.log(prefer_gifts)
        for gift in gifts:
            tmp = difflib.get_close_matches(gift[0], all_gift_names, cutoff=0.8)
            if len(tmp) == 0:
                if not ("Replace" in gift[0]) and not ("Skill" in gift[0]): # 排除技能替换的警告
                    logger.log(f"识别异常：识别不出饰品文字{gift[0]},详情：{gift}", level="WARNING")
                continue
            gift_name = tmp[0]
            # name_radio = difflib.SequenceMatcher(None, gift[0], gift_name).ratio()
            # if name_radio < 1:
            #     logger.log("检测到饰品 %s，经修复得 %s，相似度：%f" % (gift[0], gift_name, name_radio))
            if gift_name in prefer_gifts:
                input_handler.click(gift[1], gift[2]-80)
                logger.log(f"检测到可买并购买饰品 {gift_name}", input_handler.capture_screenshot())
                time.sleep(1)
                input_handler.click(740, 480)
                time.sleep(0.5)
                self.exec_wait_disappear(get_task("wait_connecting_disappear"))
                time.sleep(0.5)
                input_handler.click(650, 535)
                time.sleep(1)
        return True

    loop_count = 0
    while True:
        tmp_screenshot = input_handler.capture_screenshot()
        logger.log("开始一轮技能替换&饰品购买", tmp_screenshot)
        is_replace_skill_sold_out = len(recognize_handler.template_match(tmp_screenshot, "shop_purchased", mask=[550, 200, 140, 50])) > 0
        if not is_replace_skill_sold_out:
            exec_replace_skill()

        can_purchase = exec_purchase_ego_gifts()
       
        cur_money = recognize_handler.detect_text_in_image(input_handler.capture_screenshot(), mask=[568, 100, 100, 80])
        if len(cur_money) > 0:
            try:
                cur_money = int(cur_money[0][0])
            except Exception as e:
                logger.log(f"{node.name} 获取现钱发生错误[{e}]，就当现在没有钱", level="WARNING")
                cur_money = 0
        else:
            cur_money = 0

        # 刷新 or 停止
        if (not can_purchase) or cur_money <= left_money_for_enhance:
            break
        else:
            input_handler.click(1140, 120)
            time.sleep(1)
            input_handler.click(*keyword_refresh_map[prefer_gift_styles[loop_count%len(prefer_gift_styles)]])
            time.sleep(0.5)
            input_handler.click(780, 570)
            self.exec_wait_disappear(get_task("wait_connecting_disappear"))
            time.sleep(1)
            loop_count += 1


fuse_ego_gift_style_map = {
    'Burn': (330, 290),
    'Bleed': (480, 290),
    'Tremor': (630, 290),
    'Rupture': (780, 290),
    'Sinking': (930, 290),
    'Poise': (330, 430),
    'Charge': (480, 430),
    'Slash': (630, 430),
    'Pierce': (780, 430),
    'Blunt': (930, 430),
}


@TaskExecution.register("mirror_shop_fuse_ego_gifts")
def exec_mirror_shop_fuse_ego_gifts(self, node:TaskNode, func):
    logger.log("融合EGO饰品")
    # 确保 EGO 数量够了进合成
    input_handler.click(280, 390)
    time.sleep(1)
    tmp_screenshot = input_handler.capture_screenshot()
    if len(recognize_handler.template_match(tmp_screenshot, "fuse_ego_gift")) == 0:
        return
    # 选择主体系对应的饰品合成
    input_handler.click(850, 350)
    time.sleep(1)
    cfg_type = node.get_param("cfg_type")
    cfg, cfg_index = self._get_using_cfg(cfg_type), self._get_using_cfg_index(cfg_type)
    mirror_team_styles = cfg["mirror_team_styles"][cfg_index]
    input_handler.click(*fuse_ego_gift_style_map[mirror_team_styles])
    time.sleep(0.5)
    input_handler.click(780, 570)
    time.sleep(1)
    
    prefer_gift_styles = cfg["mirror_team_ego_gift_styles"][cfg_index]
    prefer_gifts = set()
    for style in prefer_gift_styles:
        gift_tag = "ego_gifts_" + style
        prefer_gifts.update(x[0] for x in get_images_by_tag(gift_tag))
    
    gift_allow_list = cfg["mirror_team_ego_allow_list"][cfg_index]
    gift_block_list = cfg["mirror_team_ego_block_list"][cfg_index]
    prefer_gifts.update(gift_allow_list)
    prefer_gifts.difference_update(gift_block_list) # 黑名单优先,不过前端应该不会发生冲突
    useless_gifts = set()
    useless_gifts.update(x[0] for x in get_images_by_tag("ego_gifts"))
    useless_gifts.difference_update(prefer_gifts)
    logger.debug(f"本次无用饰品名单：{useless_gifts}")
    detect_places = [590, 180, 560, 350]
    first_page = True
    while True:
        tmp_screenshot = input_handler.capture_screenshot()
        logger.log("开始一轮饰品融合", tmp_screenshot)
        can_fuse = False
        for gift_name in useless_gifts:
            res = recognize_handler.template_match(tmp_screenshot, gift_name, mask=detect_places, screenshot_scale=1, threshold=0.91)
            if len(res) > 0:
                logger.log("融合，检测到无用饰品：%s" % gift_name)
                input_handler.click(res[0][0], res[0][1])
                time.sleep(1)
                if len(recognize_handler.template_match(input_handler.capture_screenshot(), "empty_fuse_gift_place", mask=[140, 270, 150, 150])) == 0:
                    can_fuse = True
                    break

        if can_fuse:
            logger.log("凑齐三个可合成饰品", input_handler.capture_screenshot())
            input_handler.click(785, 590)
            time.sleep(1)
            input_handler.click(785, 590)
            time.sleep(0.5)
            self.exec_wait_disappear(get_task("wait_connecting_disappear"))
            time.sleep(1)
            logger.log("饰品融合结果记录", input_handler.capture_screenshot())
            input_handler.key_press("enter")
            continue
        
        # 退出条件：要么检测不到滑块，要么滑块在最底下
        slider = recognize_handler.template_match(tmp_screenshot, "slider", mask=[1080, 190, 80, 360])
        if len(slider) > 0 and slider[0][1] < 440:
            input_handler.swipe(815, 395, 815, 290)
            time.sleep(1)
            if first_page:
                first_page = False
                # detect_places = [590, 390, 560, 140]
                detect_places[1] += 210
                detect_places[3] -= 210
        else:
            break

    input_handler.click(500, 590)
 

@TaskExecution.register("mirror_shop_heal_sinner")
def exec_mirror_shop_heal_sinner(self, node:TaskNode, func):
    logger.log("镜牢商店治疗罪人")
    cur_money = recognize_handler.detect_text_in_image(input_handler.capture_screenshot(), mask=[568, 100, 100, 80])
    if len(cur_money) > 0:
        try:
            cur_money = int(cur_money[0][0])
        except Exception as e:
            logger.log(f"{node.name} 获取现钱发生错误[{e}]，就当现在没有钱", level="WARNING")
            cur_money = 0
    else:
        cur_money = 0

    # 刷新 or 停止
    if cur_money <= 100:
        return None

    cfg_type = node.get_param("cfg_type")
    cfg, cfg_index = self._get_using_cfg(cfg_type), self._get_using_cfg_index(cfg_type)
    if cfg["mirror_shop_heal"][cfg_index]:
        input_handler.click(200, 470)
        time.sleep(1)
        logger.log("镜牢商店尝试进行全体治疗", input_handler.capture_screenshot())
        input_handler.click(1020, 330)
        time.sleep(0.5)
        self.exec_wait_disappear(get_task("wait_connecting_disappear"))
        time.sleep(0.5)
        input_handler.click(1120, 650)
        time.sleep(1)
    else:
        logger.log("根据设置跳过镜牢商店治疗")
    


@TaskExecution.register("event_pass_check")
def exec_event_pass_check(self, node:TaskNode, func):
    tmp_screenshot = input_handler.capture_screenshot()
    logger.log("事件通行证检查", tmp_screenshot)
    for s in ["very_high", "high", "normal", "low", "very_low"]:
        res = recognize_handler.template_match(tmp_screenshot, "event_pass_"+s, threshold=0.9)
        if len(res) > 0:
            input_handler.click(res[0][0], res[0][1])
            break
    time.sleep(1)
    input_handler.click(1120, 650)
    


@TaskExecution.register("event_make_choice")
def exec_event_make_choice(self, node:TaskNode, func):
    # 使选项置中
    input_handler.click(1200, 330)
    time.sleep(1)
    tmp_screenshot = input_handler.capture_screenshot()
    logger.log("事件选项处理", tmp_screenshot)
    special_case = False
    
    # 优先选能拿 E.G.O 的
    results = recognize_handler.detect_text_in_image(tmp_screenshot, mask=[670, 140, 620, 500])
    special_phase = ["Select to gain", "Pass to level up", "Pass to gain", "check to gain", "depending on"]
    for res in results:
        if any(phase in res[0] for phase in special_phase):
            logger.log(f"找到优先选项：{res[0]}")
            input_handler.click(res[1], res[2])
            special_case = True
    
    if not special_case:
        # raise Exception("进入了普通情况，请人工检查是否需要补充事件匹配")
        for x, y in [(950, 200), (950, 290), (950, 380), (950, 450)]:
            input_handler.click(x, y)   

    


@TaskExecution.register("mirror_select_next_node")
def exec_mirror_select_next_node(self, node:TaskNode, func):
    # 默认事件，普通战斗优先，其它的节点差不多后
    node_templates = [
        "node_event",
        "node_regular_encounter",
        "node_elite_encounter",
        "node_focused_encounter",
        "node_shop",
        "node_boss_encounter",
        "train_head",
    ]
    tmp_screenshot = input_handler.capture_screenshot()
    logger.log("选择下一个镜牢节点", tmp_screenshot)
    train_head = recognize_handler.template_match(tmp_screenshot, "train_head")
    if len(train_head) > 0 and train_head[0][1]<300:
        input_handler.swipe(460, 270, 460, 340)
        tmp_screenshot = input_handler.capture_screenshot()
    
    next_node_exist = False
    for next_node in node_templates:
        choices = recognize_handler.pyramid_template_match(tmp_screenshot, next_node, mask=[380, 40, 420, 580])
        for choice in choices:
            input_handler.click(choice[0], choice[1])
            time.sleep(1)

            if len(recognize_handler.template_match(input_handler.capture_screenshot(), "node_enter")) > 0:
                input_handler.key_press("enter")
                next_node_exist = True 
                break

        if next_node_exist:
            break

    if not next_node_exist:
        # 启动保底的三点寻位
        logger.log("没能成功识别并点击路径图标，尝试固定点位", input_handler.capture_screenshot(), level="WARNING")
        for x, y in [(710, 330), (710, 110), (710, 540)]:
            input_handler.click(x, y)
            time.sleep(1)
            if len(recognize_handler.template_match(input_handler.capture_screenshot(), "node_enter")) > 0:
                input_handler.key_press("enter")
                next_node_exist = True
                break   
    
    if not next_node_exist:
        # 那么估计是当前的位置因为各种偏移不对
        logger.log("镜牢寻路异常，尝试重启镜牢", input_handler.capture_screenshot(), level="WARNING")
        input_handler.click(1230, 50)
        time.sleep(1)
        input_handler.click(730, 440)
        time.sleep(1)
        input_handler.click(760, 490)
        return (node.name, None, get_task("mirror_entry").get_next)
    


@TaskExecution.register("mirror_select_theme_pack")
def exec_mirror_theme_pack(self, node: TaskNode, func):
    logger.log("选择镜牢主题包", input_handler.capture_screenshot())
    cfg = self._get_using_cfg("other_task")
    test_mode = cfg["test_mode"]

    res_name = ""
    res_pos = None
    cfg = self._get_using_cfg("theme_pack")

    theme_packs = sorted(cfg.items(), key=lambda theme_pack:theme_pack[1]["weight"], reverse=True)
    stop = False
    refresh = False
    while not stop:
        if test_mode:
            # 实验模式下为识别并命名主题包
            detect_and_save_theme_pack(input_handler.capture_screenshot()) 
        
        tmp_screenshot = input_handler.capture_screenshot()
        
        for theme_pack_name, val in theme_packs:
            cur_weight = val["weight"]
            tmp = recognize_handler.template_match(tmp_screenshot, theme_pack_name)
            if len(tmp) > 0:
                logger.log(f"检测到卡包 {theme_pack_name},权重：{cur_weight}")
                if not res_pos or cur_weight > cfg[res_name]["weight"]:
                    res_pos = tmp
                    res_name = theme_pack_name
                    if cur_weight > 10:
                        stop = True

        if refresh:
            stop = True

        if not stop and not refresh:
            logger.log("没有找到权值大于基准值（10）的卡包，点击刷新")
            refresh = True
            input_handler.click(1080, 50)
            time.sleep(0.5)
            self.exec_wait_disappear(get_task("wait_connecting_disappear"))
            time.sleep(3)
            res_name = ""
            res_pos = None


    if not res_pos:
        res_pos = recognize_handler.template_match(input_handler.capture_screenshot(), "theme_pack_detail")
    if len(res_pos) == 0:
        logger.log("主题包检测异常，已有模板匹配失败，且随机选择也失败了，这里跳过选择", level="ERROR")
        return
    
    logger.log(f"最后选择到了卡包：{res_name}, 对应权重：{cfg[res_name]['weight']}", input_handler.capture_screenshot())
    input_handler.swipe(res_pos[0][0], res_pos[0][1], res_pos[0][0], res_pos[0][1]+400)


@TaskExecution.register("mirror_gift_search")
def exec_mirror_gift_search(self, node: TaskNode, func):
    logger.log("搜索镜牢礼物", input_handler.capture_screenshot())
    # TODO 完善 gift search
    # 现在暂时只是 refuse gift
    input_handler.click(900, 600)
    time.sleep(1)
    input_handler.key_press("enter")
    


@TaskExecution.register("mirror_select_initial_ego_gift")
def exec_mirror_select_initial_ego_gift(self, node:TaskNode, func):
    cfg_type = node.get_param("cfg_type")
    cfg = self._get_using_cfg(cfg_type)
    cfg_index = self._get_using_cfg_index(cfg_type)
    team_style = cfg["mirror_team_styles"][cfg_index]
    initial_ego_styles = {
        "Burn":(200, 250), 
        "Bleed":(350, 250), 
        "Tremor":(500, 250), 
        "Rupture":(650, 250), 
        "Sinking":(200, 450), 
        "Poise":(350, 450), 
        "Charge":(500, 450), 
        "Slash":(650, 450),
        "Pierce":(200, 450),
        "Blunt":(350, 450),
        }
    if team_style == "Pierce" or team_style == "Blunt":
        input_handler.swipe(430, 470, 430, 240)
        time.sleep(0.5)
    input_handler.click(*initial_ego_styles[team_style])
    time.sleep(0.5)
    for i in cfg["mirror_team_initial_ego_orders"][cfg_index]:
        match i:
            case 1:
                input_handler.click(980, 270)
            case 2:
                input_handler.click(980, 370)
            case 3:
                input_handler.click(980, 470)
            case _:
                raise Exception(f"发现非法初始 ego 顺序选项：{i}")
        time.sleep(0.5)
    logger.log("选择初始EGO饰品", input_handler.capture_screenshot())
    for _ in range(4):  
        input_handler.key_press("enter")
        time.sleep(0.5)
        self.exec_wait_disappear(get_task("wait_connecting_disappear"))
        
    

@TaskExecution.register("mirror_choose_star")
def exec_mirror_choose_star(self, node: TaskNode, func):
    
    star_pos = [(200, 190), (400, 190), (600, 190), (800, 190), (1000, 190), (200, 410), (400, 410), (600, 410), (800, 410), (1000, 410)]
    plus = (0, 150)
    plusplus = (80, 150)
    cfg_type = node.get_param("cfg_type")
    cfg = self._get_using_cfg(cfg_type)
    cfg_index = self._get_using_cfg_index(cfg_type)
    for star_str in cfg["mirror_team_stars"][cfg_index]:
        star_index = int(star_str[0])
        # logger.log(star_index)
        origin_click_pos = star_pos[star_index]
        input_handler.click(*origin_click_pos)
        time.sleep(0.5)
        if len(star_str) == 1:
            continue
        elif len(star_str) == 2:
            click_pos = (origin_click_pos[0]+plus[0], origin_click_pos[1]+plus[1])
            input_handler.click(*click_pos)
            time.sleep(0.5)
        elif len(star_str) == 3:
            click_pos = (origin_click_pos[0]+plusplus[0], origin_click_pos[1]+plusplus[1])
            input_handler.click(*click_pos)
            time.sleep(0.5)
        else:
            raise Exception("非法 star str：%s" % star_str)
    logger.log("选择镜牢星光", input_handler.capture_screenshot())
    input_handler.click(1190, 670)
    time.sleep(2)
    input_handler.click(735, 535)
    


@TaskExecution.register("choose_team")
def exec_choose_team(self, node: TaskNode, func):
    logger.log("选择队伍")
    cfg_type = node.get_param("cfg_type")
    cfg = self._get_using_cfg(cfg_type)
    cfg_index = self._get_using_cfg_index(cfg_type)
    team_no = cfg["team_indexes"][cfg_index] - 1 # 这里减一是把 1-20 化为 0-19 

    scroll_count = team_no // 6
    scroll_count = max(0, min(scroll_count, 3)) # 确保滚动次数一定合法
    # 划到顶部重置
    for _ in range(2):
        input_handler.swipe(130, 320, 130, 720)
        time.sleep(0.5)
    # ---- 计算点击 index ----
    if team_no < 18:
        click_index = team_no % 6   # 正常三页
    else:
        # 最后一页只有 4、5 两个可点
        click_index = team_no - 14  # 18→4，19→5

    for _ in range(scroll_count):
        input_handler.swipe(130, 500, 130, 270)
        time.sleep(0.5)

    team_click = [(130, 315), (130, 355), (130, 390), (130, 430), (130, 465), (130, 500)]
    input_handler.click(*team_click[click_index])
    logger.log("完成选择队伍", input_handler.capture_screenshot())
    if cfg_type == "mirror":
        time.sleep(0.5)
        input_handler.click(1140, 590)
        time.sleep(1)
        input_handler.key_press("enter")
    
    
team_order_map = {
    "Yi Sang":[290, 240],
    "Faust":[420, 240], 
    "Don Quixote":[550, 240],
    "Ryoshu":[680, 240],
    "Meursault":[810, 240],
    "Hong Lu":[940, 240],
    "Heathcliff":[290, 440],
    "Ishmael":[420, 440],
    "Rodion":[550, 440],
    "Sinclair":[680, 440],
    "Outis":[810, 440],
    "Gregor":[940, 440],
}

@TaskExecution.register("ready_to_battle")
def exec_ready_to_battle(self, node: TaskNode, func):
    logger.log("准备战斗", input_handler.capture_screenshot())
    res = recognize_handler.detect_text_in_image(
        input_handler.capture_screenshot(), mask=[1130, 500, 100, 50],
    )

    # 默认值（OCR 失败时使用）
    selected_count = 0
    all_count = 1

    try:
        # res 至少需要一个元素
        if not res or len(res[0]) < 1:
            raise ValueError("OCR 返回为空")

        text = res[0][0]  # 类似 "11/12"
        index = text.find("/")

        if index == -1:
            raise ValueError(f"OCR 文本格式错误: '{text}'")

        selected_count = int(text[:index])
        all_count = int(text[index + 1:])
    except Exception as e:
        logger.log(f"[警告] OCR 获取队伍人数信息时出现错误：{e}，已使用默认值 selected=0, all=1")

    # 只要数字不等，就需要重置，毕竟也有可能会 11/5
    if selected_count != all_count:
        input_handler.click(1140, 480)
        time.sleep(1)
        if recognize_handler.template_match(input_handler.capture_screenshot(), "reset_deployment_order"):
            input_handler.key_press("enter")
            time.sleep(1)
        # 下一步是转到对应的选人
        cfg_type = node.get_param("cfg_type")
        cfg = self._get_using_cfg(cfg_type)
        cfg_index = self._get_using_cfg_index(cfg_type)

        team_order = cfg["team_orders"][cfg_index]
        for member in team_order:
            input_handler.click(*team_order_map[member])
    
    input_handler.click(1140, 590)
    


@TaskExecution.register("exp_select_stage")
def exec_exp_select_stage(self, node: TaskNode, func):
    logger.log("选择经验副本关卡", input_handler.capture_screenshot())
    cfg = self._get_using_cfg("exp")
    target_stage = cfg["exp_stage"]
    pos = recognize_handler.find_text_in_image(input_handler.capture_screenshot(), target_stage, mask=[250, 180, 1000, 50])
    while len(pos) == 0:
        input_handler.swipe(590, 310, 940, 310)
        time.sleep(0.6)
        pos = recognize_handler.find_text_in_image(input_handler.capture_screenshot(), target_stage, mask=[250, 180, 1000, 50])

    # 选择进入位置
    enter_pos = (pos[0][1]+10, 480)
    skip_battle_pos = (enter_pos[0], 515)

    select_mode = cfg["luxcavation_mode"]

    if select_mode == "enter":
        logger.log(f"[exp_select_stage] 点击 enter: {enter_pos}")
        input_handler.click(*enter_pos)
    elif select_mode == "skip_battle":
        logger.log(f"[exp_select_stage] 点击 skip_battle: {skip_battle_pos}")
        input_handler.click(*skip_battle_pos)
    else:
        raise Exception(f"未知的 exp mode：{select_mode}")

    


@TaskExecution.register("thread_select_stage")
def exec_thread_select_stage(self, node: TaskNode, func):
    logger.log("选择Thread副本关卡", input_handler.capture_screenshot())
    input_handler.click(140, 330)
    time.sleep(1)
    cfg = self._get_using_cfg("thread")
    select_mode = cfg["luxcavation_mode"]

    if select_mode == "enter":
        input_handler.click(370, 480)
    elif select_mode == "skip_battle":
        input_handler.click(370, 515)
    else:
        raise Exception(f"未知的 thread mode：{select_mode}")
    time.sleep(1)

    target_stage = cfg["thread_stage"]
    pos = recognize_handler.find_text_in_image(input_handler.capture_screenshot(), target_stage, mask=[560, 170, 90, 400])
    while len(pos) == 0:
        input_handler.swipe(650, 325, 650, 430)
        time.sleep(0.6)
        pos = recognize_handler.find_text_in_image(input_handler.capture_screenshot(), target_stage, mask=[560, 170, 90, 400])

    input_handler.click(pos[0][1], pos[0][2])

    


@TaskExecution.register("get_enkephalin_module")
def exec_get_enkephalin_module(self, node: TaskNode, func):
    logger.log("获取脑啡肽模块", input_handler.capture_screenshot())
    input_handler.click(500, 230)
    time.sleep(1)
    input_handler.click(800, 330)
    time.sleep(1)
    input_handler.key_press("enter")
    self.exec_wait_disappear(get_task("wait_connecting_disappear"))
    input_handler.key_press("esc")
    


@TaskExecution.register("recharge_enkephalin")
def exec_recharge_enkephalin(self, node: TaskNode, func):
    logger.log("充值脑啡肽", input_handler.capture_screenshot())
    input_handler.click(630, 230)
    time.sleep(1)
    res = recognize_handler.detect_text_in_image(input_handler.capture_screenshot(), mask=[680, 300, 120, 45])
    try:
        index = str.find(res[0][0], "/")
    except IndexError:
        logger.log("检测已购买次数失败，当作已购买十次", input_handler.capture_screenshot(), "WARNING")
        already_purchase_count = 10
    else:
        already_purchase_count = int(res[0][0][:index])

    cfg = self._get_using_cfg("other_task")
    while already_purchase_count < cfg["lunary_purchase_target"]:
        input_handler.key_press('enter')
        time.sleep(1)
        self.exec_wait_disappear(get_task("wait_connecting_disappear"))
        already_purchase_count += 1
        logger.log(f"购买了一次狂气, 还剩{cfg['lunary_purchase_target'] - already_purchase_count}")
    


@TaskExecution.register("click")
def exec_click(self, node: TaskNode, func=None):
    target = node.get_param("target", "")
    target_offset = node.get_param("target_offset", [0, 0])
    if isinstance(target, list):
        click_pos = (
            target[0] + target_offset[0],
            target[1] + target_offset[1]
        )
    elif isinstance(target, str):
        pos = node.get_param("recognize_result")[0]
        click_pos = (
            pos[0] + target_offset[0],
            pos[1] + target_offset[1]
        )
    else:
        raise TypeError(
            f"任务{{{node.name}}}的 params/target 必须是 list 或 str"
        )
    input_handler.click(*click_pos)
    repeat = node.get_param("repeat", 1)
    repeat_interval = max(node.get_param("repeat_interval", 0.2) - 0.5, 0)
    logger.debug(f"执行点击操作: {node.name}, 点了{repeat}次，间隔{repeat_interval}秒")
    for _ in range(repeat-1):
        time.sleep(repeat_interval)
        input_handler.click(*click_pos)
    


@TaskExecution.register("key")
def exec_key(self, node: TaskNode, func=None):
    key = node.get_param("key")
    input_handler.key_press(key)
    repeat = node.get_param("repeat", 1)
    repeat_interval = node.get_param("repeat_interval", 0.3)
    logger.debug(f"执行按键操作: {node.name}, 按了{repeat}次，间隔{repeat_interval}秒")
    for _ in range(repeat-1):
        time.sleep(repeat_interval)
        input_handler.key_press(key)
        
    


@TaskExecution.register("swipe")
def exec_swipe(self, node: TaskNode, func=None):
    begin = node.get_param("begin")
    begin_offset = node.get_param("begin_offset", [0, 0])
    end = node.get_param("end")
    end_offset = node.get_param("end_offset", [0, 0])
    logger.debug(f"执行滑动操作: {node.name}, 从 {begin} 到 {end}")

    if isinstance(begin, str):
        begin = node.get_param("recognize_result")[0]

    input_handler.swipe(
        begin[0] + begin_offset[0],
        begin[1] + begin_offset[1],
        end[0] + end_offset[0],
        end[1] + end_offset[1]
    )
    repeat = node.get_param("repeat", 1)
    repeat_interval = max(node.get_param("repeat_interval", 0.5) - 0.5, 0)
    for _ in range(repeat-1):
        time.sleep(repeat_interval)
        input_handler.swipe(
            begin[0] + begin_offset[0],
            begin[1] + begin_offset[1],
            end[0] + end_offset[0],
            end[1] + end_offset[1]
        )
    


@TaskExecution.register("wait_disappear")
def exec_wait_disappear(self, node: TaskNode, func=None):
    logger.debug(f"等待元素消失: {node.name}")
    check_interval = node.get_param("check_interval", 1)
    template_name = node.get_param("template")
    
    while node.do_recognize(input_handler.capture_screenshot()):
        logger.debug(f"wait {{{template_name}}} disappear")
        time.sleep(check_interval)
    


@TaskExecution.register("wait_appear")
def exec_wait_appear(self, node: TaskNode, func=None):
    logger.debug(f"等待元素出现: {node.name}")
    check_interval = node.get_param("check_interval", 1)
    max_wait_time = node.get_param("max_wait_time", 5)
    template_name = node.get_param("template")
    used_wait_time = 0
    while used_wait_time < max_wait_time and node.do_recognize(input_handler.capture_screenshot()):
        logger.debug(f"wait {{{template_name}}} appear")
        time.sleep(check_interval)
        used_wait_time += check_interval
    


@TaskExecution.register("empty")
def exec_empty(self, node: TaskNode, func=None):
    logger.debug(f"执行空操作: {node.name}")


@TaskExecution.register("report_error")
def exec_report_error(self, node: TaskNode, func=None):
    logger.log(f"报告错误: {node.name}", level="ERROR")
    msg = node.get_param("error_msg")
    raise Exception("任务节点{%s} 报告错误：{%s}" % (node.name, msg))