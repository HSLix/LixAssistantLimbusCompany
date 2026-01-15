from workflow.task_execution import *





@TaskExecution.register("choose_team")
def exec_choose_team(self, node: TaskNode, func):
    logger.info("选择队伍")
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
    logger.info("完成选择队伍", input_handler.capture_screenshot())
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
    logger.info("准备战斗", input_handler.capture_screenshot())
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
        logger.info(f"[警告] OCR 获取队伍人数信息时出现错误：{e}，已使用默认值 selected=0, all=1")

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
        
        # 遍历team_order中指定的成员
        for member in team_order:
            if member in team_order_map:
                input_handler.click(*team_order_map[member])
        
        # 找出未被team_order包含的成员
        remaining_members = []
        for member in team_order_map:
            if member not in team_order:
                remaining_members.append(member)
        
        # 按顺序选择未被选中的成员
        for member in remaining_members:
            input_handler.click(*team_order_map[member])
    
    input_handler.click(1140, 590)
    




@TaskExecution.register("get_enkephalin_module")
def exec_get_enkephalin_module(self, node: TaskNode, func):
    logger.info("获取脑啡肽模块", input_handler.capture_screenshot())
    input_handler.click(500, 230)
    time.sleep(1)
    input_handler.click(800, 330)
    time.sleep(1)
    input_handler.key_press("enter")
    self.exec_wait_disappear(get_task("wait_connecting_disappear"))
    input_handler.key_press("esc")
    


@TaskExecution.register("recharge_enkephalin")
def exec_recharge_enkephalin(self, node: TaskNode, func):
    logger.info("充值脑啡肽", input_handler.capture_screenshot())
    input_handler.click(630, 230)
    time.sleep(1)
    res = recognize_handler.detect_text_in_image(input_handler.capture_screenshot(), mask=[680, 300, 120, 45])
    try:
        index = str.find(res[0][0], "/")
    except IndexError:
        logger.info("检测已购买次数失败，当作已购买十次", input_handler.capture_screenshot(), "WARNING")
        already_purchase_count = 10
    else:
        already_purchase_count = int(res[0][0][:index])

    cfg = self._get_using_cfg("other_task")
    while already_purchase_count < cfg["lunary_purchase_target"]:
        input_handler.key_press('enter')
        time.sleep(1)
        self.exec_wait_disappear(get_task("wait_connecting_disappear"))
        already_purchase_count += 1
        logger.info(f"购买了一次狂气, 还剩{cfg['lunary_purchase_target'] - already_purchase_count}")
    
