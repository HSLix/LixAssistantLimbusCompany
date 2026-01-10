from workflow.task_execution import *

@TaskExecution.register("mirror_defeat")
def exec_mirror_defeat(self, node:TaskNode, func):
    logger.log("镜牢刷取失败", input_handler.capture_screenshot())
    input_handler.click(770, 450)
    input_handler.click(650, 525)

    while len(recognize_handler.template_match(input_handler.capture_screenshot(), "defeat")) == 0:
        time.sleep(0.5)
        continue

    for _ in range(4):
        input_handler.key_press("enter")
        time.sleep(1)
    self.exec_wait_disappear(get_task("wait_connecting_disappear"))
    for _ in range(3):
        input_handler.key_press("enter")
        time.sleep(1)
    
    if len(recognize_handler.template_match(input_handler.capture_screenshot(), "exploration_reward")) > 0:
        logger.debug("检测到结算失败，启动放弃奖励", input_handler.capture_screenshot())
        input_handler.click(395, 550)
        time.sleep(1)
        input_handler.key_press("enter")


@TaskExecution.register("mirror_victory")
def exec_mirror_victory(self, node:TaskNode, func):
    logger.log("处理镜牢胜利结算", input_handler.capture_screenshot())
    mirror_cfg = self._get_using_cfg("mirror")
    accept_reward = mirror_cfg["accept_reward"]

    if accept_reward:
        for _ in range(4):
            input_handler.key_press("enter")
            time.sleep(1)
        self.exec_wait_disappear(get_task("wait_connecting_disappear"))
        for _ in range(3):
            input_handler.key_press("enter")
            time.sleep(1)
    else:
        # 不领取奖励
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

    # 筛选出x坐标与其他点x坐标差值>=50的点，从前往后保留第一个
    filtered_select_orders = []
    for point in select_orders:
        x, y = point[1], point[2]  # 假设坐标在元组的第二、三个元素
        is_duplicate = False
        
        for existing_point in filtered_select_orders:
            existing_x = existing_point[1]
            if abs(x - existing_x) < 50:
                is_duplicate = True
                break
        
        if not is_duplicate:
            filtered_select_orders.append(point)

    logger.debug(f"selected_orders:{select_orders}; filtered_select_orders:{filtered_select_orders}; prefer_gift_without_owned: {prefer_gift_without_owned}; acquire_without_owned:{acquire_without_owned}; acquire_with_owned:{acquire_with_owned}; last_acquire_ego_gift:{last_acquire_ego_gift};")
    
    for choice in filtered_select_orders[::-1]:
        input_handler.click(choice[1], choice[2]+20)
        time.sleep(0.5)

    input_handler.click(1130, 580)
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
    # 检查配置是否启用此功能
    cfg_type = node.get_param("cfg_type")
    cfg = self._get_using_cfg(cfg_type)
    cfg_index = self._get_using_cfg_index(cfg_type)
    
    # 检查是否启用增强EGO饰品功能
    enable_enhance = cfg.get("enable_enhance_ego_gifts", True)
    if not enable_enhance:
        logger.log("根据配置跳过EGO饰品升级")
        # 点击 leave，为离开商店做准备
        input_handler.click(1120, 640)
        return
    
    input_handler.click(160, 390)
    time.sleep(1)
    if len(recognize_handler.template_match(input_handler.capture_screenshot(), "enhance_ego_gift")) == 0:
        logger.log("无法进入升级区域，放弃饰品升级", input_handler.capture_screenshot(), level="WARNING")
        return

    logger.log("强化EGO饰品")
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
    # 检查配置是否启用此功能
    cfg_type = node.get_param("cfg_type")
    cfg = self._get_using_cfg(cfg_type)
    cfg_index = self._get_using_cfg_index(cfg_type)
    
    # 检查是否启用替换技能和购买EGO饰品功能
    enable_replace_and_purchase = cfg.get("enable_replace_skill_purchase_ego_gifts", True)
    if not enable_replace_and_purchase:
        logger.log("根据配置跳过技能替换和EGO饰品购买")
        return
    
    logger.log("替换技能并购买EGO饰品")
    cfg_type = node.get_param("cfg_type")
    cfg, cfg_index = self._get_using_cfg(cfg_type), self._get_using_cfg_index(cfg_type)
    
    left_money_for_enhance = cfg["mirror_stop_purchase_gift_money"]

    prefer_gift_styles = cfg["mirror_team_ego_gift_styles"][cfg_index]
    prefer_gifts = set()
    for style in prefer_gift_styles:
        gift_tag = "ego_gifts_" + style
        prefer_gifts.update(x[0] for x in get_images_by_tag(gift_tag))
    
    mirror_team_style = cfg["mirror_team_styles"][cfg_index]
    gift_allow_list = cfg["mirror_team_ego_allow_list"][cfg_index]
    gift_block_list = cfg["mirror_team_ego_block_list"][cfg_index]
    prefer_gifts.update(gift_allow_list)
    prefer_gifts.difference_update(gift_block_list) # 黑名单优先,不过前端应该不会发生冲突
    all_gift_names = [x[0] for x in get_images_by_tag("ego_gifts")]
    max_ego_gifts_radio = get_max_radio_of_ego_gifts()
    logger.debug(f"本次倾向购买饰品名单：{prefer_gifts}")

    def exec_replace_skill() -> bool:
        replaced = False
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
                replaced = True
                self.exec_wait_disappear(get_task("wait_connecting_disappear"))
        else:
            logger.log("替换技能名字识别异常，跳过技能替换部分", level="WARNING")
        return replaced
    
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
            if exec_replace_skill():
                continue

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
            if len(prefer_gift_styles) == 0:
                input_handler.click(*keyword_refresh_map[mirror_team_style])
            else:
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
    # 检查配置是否启用此功能
    cfg_type = node.get_param("cfg_type")
    cfg = self._get_using_cfg(cfg_type)
    cfg_index = self._get_using_cfg_index(cfg_type)
    
    # 检查是否启用融合EGO饰品功能
    enable_fuse = cfg.get("enable_fuse_ego_gifts", True)
    if not enable_fuse:
        logger.log("根据配置跳过EGO饰品融合")
        return
    
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
            res = recognize_handler.template_match(tmp_screenshot, gift_name, mask=detect_places, screenshot_scale=1, threshold=0.9)
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

    res_name = ""
    res_pos = None
    theme_pack_cfg = self._get_using_cfg("theme_pack")

    theme_packs = sorted(theme_pack_cfg.items(), key=lambda theme_pack:theme_pack[1]["weight"], reverse=True)
    stop = False
    refresh = False
    while not stop:
        # 识别并命名主题包
        detect_and_save_theme_pack(input_handler.capture_screenshot()) 
        
        tmp_screenshot = input_handler.capture_screenshot()

        # 从mirror配置中获取mirror_mode
        mirror_cfg = self._get_using_cfg("mirror")
        mirror_mode = mirror_cfg.get("mirror_mode", "normal")  # 默认为normal模式
        
        # 只有在mirror_mode为"normal"时才检测困难模式并切换
        if mirror_mode == "normal":
            if recognize_handler.template_match(tmp_screenshot, "hard_mode") or recognize_handler.template_match(tmp_screenshot, "hard_clear_bonus"):
                input_handler.click(905, 50)
                logger.log("现需要刷取普通镜牢，检测到镜牢开启困难模式，正在关闭")
                time.sleep(5)
                continue
        else:
            if recognize_handler.template_match(tmp_screenshot, "normal_mode") or recognize_handler.template_match(tmp_screenshot, "normal_clear_bonus"):
                input_handler.click(905, 50)
                logger.log("现需要刷取困难镜牢，检测到镜牢开启普通模式，正在关闭")
                time.sleep(5)
                continue

        theme_pack_new = recognize_handler.template_match(tmp_screenshot, "mirror_theme_pack_new")
        if len(theme_pack_new) > 0:
            logger.log("检测到未探索的卡包，优先探索")
            res_pos = theme_pack_new
            res_name = "New Theme Pack's Name"
            break
        
        for theme_pack_name, val in theme_packs:
            cur_weight = val["weight"]
            tmp = recognize_handler.template_match(tmp_screenshot, theme_pack_name)
            if len(tmp) > 0:
                logger.log(f"检测到卡包 {theme_pack_name},权重：{cur_weight}")
                if not res_pos or cur_weight > theme_pack_cfg[res_name]["weight"]:
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
        logger.log("没有检测到已知主题包，启动随机选择")
    if len(res_pos) == 0:
        logger.log("主题包检测异常，已有模板匹配失败，且随机选择也失败了，这里跳过选择", level="ERROR")
        return
    
    if res_name in theme_pack_cfg:
        logger.log(f"最后选择到了卡包：{res_name}, 对应权重：{theme_pack_cfg[res_name]['weight']}", input_handler.capture_screenshot())
    else:
        logger.log(f"最后选择到了卡包：{res_name}, 但本次执行中未找到，临时赋予权重：-999, 下次执行将自动进入配置", input_handler.capture_screenshot())
    
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
    