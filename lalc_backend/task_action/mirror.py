from workflow.task_execution import *
import cv2
import numpy as np
from recognize.ocr_interface import get_provider

@TaskExecution.register("mirror_select_event_effect")
def exec_mirror_select_event_effect(self, node: TaskNode, func):
    tmp_sc = input_handler.capture_screenshot()
    logger.info("尝试选取事件 buff", tmp_sc)
    choices = recognize_handler.template_match(tmp_sc, "select_event_effect_choice")
    if len(choices) > 0:
        input_handler.click(*choices[0][:2])
        time.sleep(0.5)
        input_handler.click(640, 520)


@TaskExecution.register("mirror_defeat")
def exec_mirror_defeat(self, node: TaskNode, func):
    logger.info("镜牢刷取失败", input_handler.capture_screenshot())
    input_handler.click(770, 450)
    time.sleep(0.5)
    input_handler.click(650, 525)

    while (
        len(
            recognize_handler.template_match(
                input_handler.capture_screenshot(), "defeat"
            )
        )
        == 0
    ):
        time.sleep(0.5)
        continue

    for _ in range(4):
        input_handler.key_press("enter")
        time.sleep(1)
    self.exec_wait_disappear(get_task("wait_connecting_disappear"))
    for _ in range(3):
        input_handler.key_press("enter")
        time.sleep(1)

    if (
        len(
            recognize_handler.template_match(
                input_handler.capture_screenshot(), "exploration_reward"
            )
        )
        > 0
    ):
        logger.debug("检测到结算失败，启动放弃奖励", input_handler.capture_screenshot())
        input_handler.click(395, 550)
        time.sleep(1)
        input_handler.key_press("enter")


@TaskExecution.register("mirror_victory")
def exec_mirror_victory(self, node: TaskNode, func):
    # 重置镜牢部署缓存（新镜像run需要重新选人）
    self._mirror_deployment_done = False
    logger.info("处理镜牢胜利结算", input_handler.capture_screenshot())
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
def exec_mirror_select_floor_ego_gift(self, node: TaskNode, func):
    logger.info("选择楼层EGO饰品", input_handler.capture_screenshot())
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
    prefer_gifts.difference_update(
        gift_block_list
    )  # 黑名单优先,不过前端应该不会发生冲突
    all_gift_names = [x[0] for x in get_images_by_tag("ego_gifts")]
    max_ego_gifts_radio = get_max_radio_of_ego_gifts()

    tmp_screenshot = input_handler.capture_screenshot()
    cur_gifts = get_provider().detect_text(
        tmp_screenshot, region=[90, 170, 1090, 40]
    )
    prefer_cur_gifts = []

    for gift in cur_gifts:
        tmp = difflib.get_close_matches(gift[0], all_gift_names, cutoff=0.8)
        if len(tmp) == 0:
            logger.warning(f"识别异常：识别不出饰品文字{gift[0]}")
            continue

        if tmp[0] in prefer_gifts:
            logger.info(f"检测到有倾向的饰品{tmp}")
            prefer_cur_gifts.append((tmp, gift[1], gift[2]))

    acquire_and_owned = get_provider().detect_text(
        tmp_screenshot, region=[110, 120, 1090, 60]
    )

    # 分类 acquire_and_owned 中的文本
    owned_positions = [item for item in acquire_and_owned if item[0] == "Owned"]
    acquire_gifts = [
        item for item in acquire_and_owned if "Acquire E.G.O Gift" in item[0]
    ]

    # 将 acquire gifts 分成两类
    acquire_with_owned = []  # 左边有 Owned 的 Acquire E.G.O Gift
    acquire_without_owned = []  # 左边没有 Owned 的 Acquire E.G.O Gift

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
    prefer_gift_without_owned = []  # 左边没有 Owned 的礼物

    for gift in prefer_cur_gifts:
        gift_x = gift[1]  # gift 格式为 (text, x, y, score)
        # 检查是否有 Owned 在其左侧 -200 范围内
        has_owned_on_left = any(
            owned[1] < gift_x and gift_x - owned[1] <= 200 for owned in owned_positions
        )

        if not has_owned_on_left:
            prefer_gift_without_owned.append(gift)

    select_orders = [
        *prefer_gift_without_owned,
        *acquire_without_owned,
        *acquire_with_owned,
    ]

    # 用一个临时变量村template acquire ego gift的结果，if 这个长度为 0 就log记录一下，说明识别异常了，如果不为0 就取第一个
    last_acquire_ego_gift = None
    if len(select_orders) == 0:
        logger.debug("没有检测到倾向的饰品和可选的 Acquire E.G.O Gift，准备检测是否有 Acquire E.G.O Gift", tmp_screenshot)
        tmp = recognize_handler.template_match(tmp_screenshot, "acquire_ego_gift")
        if len(tmp) == 0:
            logger.warning(
                "跨层选 EGO 识别异常：识别不出 Acquire E.G.O Gift 模板", tmp_screenshot
            )
        else:
            last_acquire_ego_gift = tmp[0]
            select_orders.append(
                (
                    "last_acquire",
                    *last_acquire_ego_gift,
                )
            )

    

    # 筛选出x坐标与其他点x坐标差值的点，从前往后保留第一个
    filtered_select_orders = []
    for point in select_orders:
        x, y = point[1], point[2]  # 假设坐标在元组的第二、三个元素
        is_duplicate = False

        for existing_point in filtered_select_orders:
            existing_x = existing_point[1]
            if abs(x - existing_x) < 100:
                is_duplicate = True
                break

        if not is_duplicate:
            filtered_select_orders.append(point)

    logger.debug(
        f"selected_orders:{select_orders}; filtered_select_orders:{filtered_select_orders}; prefer_gift_without_owned: {prefer_gift_without_owned}; acquire_without_owned:{acquire_without_owned}; acquire_with_owned:{acquire_with_owned}; last_acquire_ego_gift:{last_acquire_ego_gift};"
    )

    for choice in filtered_select_orders[::-1]:
        input_handler.click(choice[1], choice[2] + 20)
        time.sleep(0.5)

    input_handler.click(1130, 580)
    self.exec_wait_disappear(get_task("wait_connecting_disappear"))


@TaskExecution.register("mirror_select_encounter_reward_card")
def exec_mirror_select_encounter_reward_card(self, node: TaskNode, func):
    logger.info("选择奖励卡", input_handler.capture_screenshot())
    reward_cards = [
        "cost_card",
        "starlight_card",
        "cost_ego_gift_card",
        "ego_gift_card",
        "ego_resource_card",
    ]
    tmp_screenshot = input_handler.capture_screenshot()
    for card in reward_cards:
        res = recognize_handler.template_match(tmp_screenshot, card)
        if len(res) > 0:
            input_handler.click(res[0][0], res[0][1])
            logger.info(
                f"Reward Card 选择了 {card}", input_handler.capture_screenshot()
            )
            break
    input_handler.key_press("enter")
    self.exec_wait_disappear(get_task("wait_connecting_disappear"))


enhance_sell_place = [(x, y) for y in range(260, 441, 90) for x in range(680, 1041, 90)]


@TaskExecution.register("mirror_shop_enhance_ego_gifts")
def exec_mirror_shop_enhance_ego_gifts(self, node: TaskNode, func):
    # 检查配置是否启用此功能
    cfg_type = node.get_param("cfg_type")
    cfg = self._get_using_cfg(cfg_type)
    cfg_index = self._get_using_cfg_index(cfg_type)

    # 检查是否启用增强EGO饰品功能
    enable_enhance = cfg.get("enable_enhance_ego_gifts", True)
    if not enable_enhance:
        logger.info("根据配置跳过EGO饰品升级")
        # 点击 leave，为离开商店做准备
        input_handler.click(1120, 670)
        return

    input_handler.click(160, 390)
    time.sleep(1)
    if (
        len(
            recognize_handler.template_match(
                input_handler.capture_screenshot(), "enhance_ego_gift"
            )
        )
        == 0
    ):
        logger.warning(
            "无法进入升级区域，放弃饰品升级", input_handler.capture_screenshot()
        )
        return

    logger.info("强化EGO饰品")
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
    prefer_gifts.difference_update(
        gift_block_list
    )  # 黑名单优先,不过前端应该不会发生冲突
    all_gift_names = [x[0] for x in get_images_by_tag("ego_gifts")]
    max_ego_gifts_radio = get_max_radio_of_ego_gifts()
    logger.debug(f"本次倾向升级饰品名单：{prefer_gifts}")

    # enhance_target_style_icons = []
    # for style in prefer_gift_styles:
    #     enhance_target_style_icons.append("enhance_icon_"+style)

    need_more_money = 0

    def enhance_cur_gift():
        cur_gift = get_provider().detect_text(
            input_handler.capture_screenshot(), region=[280, 150, 300, 130]
        )
        if len(cur_gift) == 0:
            logger.warning(
                f"识别异常：饰品升级区域识别不出文字",
                input_handler.capture_screenshot(),
            )
            return
        cur_gift_name = cur_gift[0][0]
        tmp = difflib.get_close_matches(cur_gift_name, all_gift_names, cutoff=0.8)
        if len(tmp) == 0:
            logger.info(f"识别异常：在已有饰品中找不到饰品文字{cur_gift_name}")
            return
        cur_gift_name = tmp[0]
        nonlocal need_more_money

        if cur_gift_name in prefer_gifts:
            input_handler.key_press("enter")
            time.sleep(1)
            tmp_screenshot = input_handler.capture_screenshot()
            if (
                len(
                    recognize_handler.template_match(
                        tmp_screenshot, "more_cost_to_enhance_this_ego_gift"
                    )
                )
                > 0
            ):
                logger.info("缺钱不能升级，提前退出")
                input_handler.click(500, 590)
                need_more_money += 1
                return
            if (
                len(
                    recognize_handler.template_match(
                        tmp_screenshot, "cost_to_enhance_this_ego_gift"
                    )
                )
                == 0
            ):
                logger.info("总之不能升级，提前退出")
                return
            input_handler.key_press("enter")
            self.exec_wait_disappear(get_task("wait_connecting_disappear"))
            time.sleep(0.5)

            input_handler.key_press("enter")
            time.sleep(1)
            tmp_screenshot = input_handler.capture_screenshot()
            if (
                len(
                    recognize_handler.template_match(
                        tmp_screenshot, "more_cost_to_enhance_this_ego_gift"
                    )
                )
                > 0
            ):
                logger.info("缺钱不能升级，提前退出")
                input_handler.click(500, 590)
                need_more_money += 1
                return
            if (
                len(
                    recognize_handler.template_match(
                        tmp_screenshot, "cost_to_enhance_this_ego_gift"
                    )
                )
                == 0
            ):
                logger.info("总之不能升级，提前退出")
                return
            input_handler.key_press("enter")
            self.exec_wait_disappear(get_task("wait_connecting_disappear"))
            time.sleep(0.5)

    detect_places = [590, 180, 560, 350]
    first_page = True
    while True:
        tmp_screenshot = input_handler.capture_screenshot()
        enhance_pos = recognize_handler.precise_template_match(
            tmp_screenshot, "mirror_shop_ego_gift_corner_unselect", mask=detect_places
        )
        enhance_cur_gift()
        for x, y, _ in enhance_pos:
            input_handler.click(x + 20, y - 20)
            enhance_cur_gift()
            if need_more_money >= 2:
                break

        if need_more_money >= 2:
            break

        # 退出条件：要么检测不到滑块，要么滑块在最底下
        slider = recognize_handler.template_match(
            tmp_screenshot, "slider", mask=[1080, 190, 80, 360]
        )
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
    input_handler.click(1120, 670)


replace_skill_map = {
    1: (300, 330),
    2: (630, 330),
    3: (960, 330),
}


keyword_refresh_map = {
    "Burn": (330, 290),
    "Bleed": (480, 290),
    "Tremor": (630, 290),
    "Rupture": (780, 290),
    "Sinking": (930, 290),
    "Poise": (330, 430),
    "Charge": (480, 430),
    "Slash": (630, 430),
    "Pierce": (780, 430),
    "Blunt": (930, 430),
}


@TaskExecution.register("mirror_shop_replace_skill_and_purchase_ego_gifts")
def exec_mirror_shop_replace_skill_and_purchase_ego_gifts(self, node: TaskNode, func):
    # 检查配置是否启用此功能
    cfg_type = node.get_param("cfg_type")
    cfg = self._get_using_cfg(cfg_type)
    cfg_index = self._get_using_cfg_index(cfg_type)

    # 检查是否启用替换技能和购买EGO饰品功能
    enable_replace_and_purchase = cfg.get(
        "enable_replace_skill_purchase_ego_gifts", True
    )
    if not enable_replace_and_purchase:
        logger.info("根据配置跳过技能替换和EGO饰品购买")
        return

    logger.info("替换技能并购买EGO饰品")
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
    prefer_gifts.difference_update(
        gift_block_list
    )  # 黑名单优先,不过前端应该不会发生冲突
    all_gift_names = [x[0] for x in get_images_by_tag("ego_gifts")]
    max_ego_gifts_radio = get_max_radio_of_ego_gifts()
    need_to_replace_skill = cfg["mirror_replace_skill"][cfg_index]
    logger.debug(
        f"本次倾向购买饰品名单：{prefer_gifts};\n本次倾向替换技能人员：{need_to_replace_skill}"
    )

    def exec_replace_skill() -> bool:
        replaced = False
        if len(need_to_replace_skill) == 0:
            return replaced

        name_of_who_can_replace = get_provider().detect_text(
            tmp_screenshot, region=[535, 320, 165, 50]
        )
        if len(name_of_who_can_replace) > 0:
            name_of_who_can_replace = name_of_who_can_replace[0]

            skill_order = None
            for name in need_to_replace_skill.keys():
                print(name)
                if name == "Ryoshu":
                    check_name = "Ry"
                else:
                    check_name = name
                if check_name in name_of_who_can_replace[0]:
                    logger.info(
                        f"检测到罪人{name}可以且应该做技能替换, 匹配值{check_name}"
                    )
                    input_handler.click(
                        name_of_who_can_replace[1], name_of_who_can_replace[2] - 80
                    )
                    skill_order = need_to_replace_skill[name][::-1]
                    time.sleep(1)
                    break

            if skill_order:
                logger.debug(f"该罪人技能替换顺序：{skill_order}")
                for i in skill_order:
                    pos = replace_skill_map[i]
                    input_handler.click(*pos)
                logger.info(
                    f"确认执行该罪人的技能替换", input_handler.capture_screenshot()
                )
                time.sleep(1)
                input_handler.click(790, 535)
                time.sleep(1)
                input_handler.click(790, 535)
                replaced = True
                self.exec_wait_disappear(get_task("wait_connecting_disappear"))
        else:
            logger.warning("替换技能名字识别异常，跳过技能替换部分")
        return replaced
    
    """
    左键点击 - 客户区坐标: (619, 272)
    左键点击 - 客户区坐标: (778, 266)
    左键点击 - 客户区坐标: (931, 267)
    左键点击 - 客户区坐标: (1084, 264)
    左键点击 - 客户区坐标: (618, 422)
    左键点击 - 客户区坐标: (779, 423)
    左键点击 - 客户区坐标: (931, 430)
    左键点击 - 客户区坐标: (1079, 423)
    for i in range(2):
        for j in range(4):
            print(f"{[620 + j*160, 270 + i*150]},")
    """
    shop_purchase_places = [
        [620, 270],
        [780, 270],
        [940, 270],
        [1100, 270],
        [620, 420],
        [780, 420],
        [940, 420],
        [1100, 420],
    ]

    def exec_purchase_ego_gifts():
        # 【优化】先模板匹配已购标识，跳过已购槽位的 OCR
        purcased_list = get_provider().detect_text(
            tmp_screenshot, region=[535, 200, 650, 40]
        )
        other_line_purchased = get_provider().detect_text(
            tmp_screenshot, region=[535, 355, 650, 40]
        )
        purcased_list.extend(other_line_purchased)

        gifts = get_provider().detect_text(
            tmp_screenshot, region=[535, 325, 650, 50]
        )
        gifts.sort(key=lambda x : x[1])
        other_line_gifts = get_provider().detect_text(
            tmp_screenshot, region=[535, 480, 650, 50]
        )
        other_line_gifts.sort(key=lambda x : x[1])
        gifts.extend(other_line_gifts)
        # 由于 MD7 开始，商店购买的商品会自动后移，而不是原地不动，所以需要建立映射进/>行位置的变化。
        for i in range(len(gifts)):
            gifts[i] = (*gifts[i], i)
            # gifts[i] 现在是 (text, x, y, conf, i) 的元组

        # 前两行能买的买完了
        if len(gifts) == len(purcased_list):
            logger.info("买了全部饰品，结束回合", input_handler.capture_screenshot())
            return False

        while purcased_list:
            purchased = purcased_list.pop()
            for gift in gifts:
                if (
                    purchased[2] < gift[2] < purchased[2] + 150
                    and abs(purchased[1] - gift[1]) < 50
                ):
                    gifts.remove(gift)

        # logger.info(prefer_gifts)
        purchased_count_in_this_turn = 0
        for gift in gifts:
            tmp = difflib.get_close_matches(gift[0], all_gift_names, cutoff=0.8)
            if len(tmp) == 0:
                if not ("Replace" in gift[0]) and not (
                    "Skill" in gift[0]
                ):  # 排除技能替换的警告
                    logger.warning(f"识别异常：识别不出饰品文字{gift[0]},详情：{gift}")
                continue
            gift_name = tmp[0]
            # name_radio = difflib.SequenceMatcher(None, gift[0], gift_name).ratio()
            # if name_radio < 1:
            #     logger.info("检测到饰品 %s，经修复得 %s，相似度：%f" % (gift[0], gift_name, name_radio))
            if gift_name in prefer_gifts:
                input_handler.click(*shop_purchase_places[gift[-1]-purchased_count_in_this_turn])
                logger.info(
                    f"检测到可买并购买饰品 {gift_name}",
                    input_handler.capture_screenshot(),
                )
                time.sleep(1)
                input_handler.click(740, 480)
                time.sleep(0.3)
                # 检测 connecting 是否出现：不出现 = 经费不足，跳过
                connecting = recognize_handler.template_match(
                    input_handler.capture_screenshot(), "connecting", mask=[1000, 0, 300, 200]
                )
                if len(connecting) == 0:
                    logger.info(f"购买 {gift_name} 无响应（可能经费不足），跳过本轮回购")
                    break
                self.exec_wait_disappear(get_task("wait_connecting_disappear"))
                time.sleep(0.5)
                input_handler.click(650, 535)
                time.sleep(1)
                purchased_count_in_this_turn += 1
        return True

    loop_count = 0
    while True:
        tmp_screenshot = input_handler.capture_screenshot()
        logger.info("开始一轮技能替换&饰品购买", tmp_screenshot)
        is_replace_skill_sold_out = (
            len(
                recognize_handler.template_match(
                    tmp_screenshot, "shop_purchased", mask=[550, 200, 140, 50]
                )
            )
            > 0
        )
        if not is_replace_skill_sold_out:
            if exec_replace_skill():
                continue

        can_purchase = exec_purchase_ego_gifts()

        cur_money = get_provider().detect_text(
            input_handler.capture_screenshot(), region=[568, 100, 100, 80]
        )
        if len(cur_money) > 0:
            try:
                cur_money = int(cur_money[0][0])
            except Exception as e:
                logger.warning(f"{node.name} 获取现钱发生错误[{e}]，就当现在没有钱")
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
                input_handler.click(
                    *keyword_refresh_map[
                        prefer_gift_styles[loop_count % len(prefer_gift_styles)]
                    ]
                )
            time.sleep(0.5)
            input_handler.click(780, 570)
            self.exec_wait_disappear(get_task("wait_connecting_disappear"))
            time.sleep(1)
            loop_count += 1

    is_replace_skill_sold_out = (
        len(
            recognize_handler.template_match(
                tmp_screenshot, "shop_purchased", mask=[550, 200, 140, 50]
            )
        )
        > 0
    )
    name_of_who_can_replace = get_provider().detect_text(
        tmp_screenshot, region=[535, 320, 165, 50]
    )
    if (
        not is_replace_skill_sold_out
        and len(name_of_who_can_replace) > 0
        and len(need_to_replace_skill) > 0
    ):
        # 没有实现技能替换且还没使用过的情况就看是否是免费普通刷新，是的话再点击普通刷新试试
        cfg_type = node.get_param("cfg_type")
        cfg = self._get_using_cfg(cfg_type)
        cfg_index = self._get_using_cfg_index(cfg_type)
        for star in cfg["mirror_team_stars"][cfg_index]:
            if "0" in star:
                logger.info(
                    "检测到有免费普通刷新和剩余技能替换次数，再尝试最后一次刷新和技能替换"
                )
                input_handler.click(1000, 120)
                self.exec_wait_disappear(get_task("wait_connecting_disappear"))
                tmp_screenshot = input_handler.capture_screenshot()
                exec_replace_skill()
                break


fuse_ego_gift_style_map = {
    "Burn": (330, 290),
    "Bleed": (480, 290),
    "Tremor": (630, 290),
    "Rupture": (780, 290),
    "Sinking": (930, 290),
    "Poise": (330, 430),
    "Charge": (480, 430),
    "Slash": (630, 430),
    "Pierce": (780, 430),
    "Blunt": (930, 430),
}


@TaskExecution.register("mirror_shop_fuse_ego_gifts")
def exec_mirror_shop_fuse_ego_gifts(self, node: TaskNode, func):
    # 检查配置是否启用此功能
    cfg_type = node.get_param("cfg_type")
    cfg = self._get_using_cfg(cfg_type)
    cfg_index = self._get_using_cfg_index(cfg_type)

    # 检查是否启用融合EGO饰品功能
    enable_fuse = cfg.get("enable_fuse_ego_gifts", True)
    if not enable_fuse:
        logger.info("根据配置跳过EGO饰品融合")
        return

    logger.info("融合EGO饰品")
    # 确保 EGO 数量够了进合成
    input_handler.click(280, 390)
    time.sleep(1)
    if (
        len(
            recognize_handler.template_match(
                input_handler.capture_screenshot(), "fuse_ego_gift"
            )
        )
        == 0
    ):
        return
    # 选择主体系对应的饰品合成
    while (
        len(
            recognize_handler.template_match(
                input_handler.capture_screenshot(), "fusion_keyword_selection"
            )
        )
        == 0
    ):
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
    prefer_gifts.difference_update(
        gift_block_list
    )  # 黑名单优先,不过前端应该不会发生冲突
    useless_gifts = set()
    useless_gifts.update(x[0] for x in get_images_by_tag("ego_gifts"))
    useless_gifts.difference_update(prefer_gifts)
    logger.debug(f"本次无用饰品名单：{useless_gifts}")
    detect_places = [590, 180, 560, 350]
    first_page = True
    while True:
        tmp_screenshot = input_handler.capture_screenshot()
        logger.info("开始一轮饰品融合", tmp_screenshot)
        can_fuse = False
        for gift_name in useless_gifts:
            res = recognize_handler.template_match(
                tmp_screenshot,
                gift_name,
                mask=detect_places,
                screenshot_scale=1,
                threshold=0.88,
            )
            if len(res) > 0:
                logger.info("融合，检测到无用饰品：%s" % gift_name)
                input_handler.click(res[0][0], res[0][1])
                time.sleep(1)
                if (
                    len(
                        recognize_handler.template_match(
                            input_handler.capture_screenshot(),
                            "empty_fuse_gift_place",
                            mask=[140, 270, 150, 150],
                        )
                    )
                    == 0
                ):
                    can_fuse = True
                    break

        if can_fuse:
            logger.info("凑齐三个可合成饰品", input_handler.capture_screenshot())
            input_handler.click(785, 590)
            time.sleep(1)
            input_handler.click(785, 590)
            time.sleep(0.5)
            self.exec_wait_disappear(get_task("wait_connecting_disappear"))
            time.sleep(1)
            logger.info("饰品融合结果记录", input_handler.capture_screenshot())
            input_handler.key_press("enter")
            continue

        # 退出条件：要么检测不到滑块，要么滑块在最底下
        slider = recognize_handler.template_match(
            tmp_screenshot, "slider", mask=[1080, 190, 80, 360]
        )
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
def exec_mirror_shop_heal_sinner(self, node: TaskNode, func):
    logger.info("镜牢商店治疗罪人")
    cur_money = get_provider().detect_text(
        input_handler.capture_screenshot(), region=[568, 100, 100, 80]
    )
    if len(cur_money) > 0:
        try:
            cur_money = int(cur_money[0][0])
        except Exception as e:
            logger.warning(f"{node.name} 获取现钱发生错误[{e}]，就当现在没有钱")
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
        logger.info("镜牢商店尝试进行全体治疗", input_handler.capture_screenshot())
        input_handler.click(1020, 330)
        time.sleep(0.5)
        self.exec_wait_disappear(get_task("wait_connecting_disappear"))
        time.sleep(0.5)
        input_handler.click(1120, 650)
        time.sleep(1)
    else:
        logger.info("根据设置跳过镜牢商店治疗")


from utils.get_save_mirror_legend import get_and_save_mirror_path_node
from utils.get_save_mirror_path import get_and_save_mirror_path

default_node_scores = {
        "node_event": 20,
        "node_regular_encounter": 9,
        "node_elite_encounter": 2,
        "node_focused_encounter": 1,
        "node_abnormality_encounter": 0,
        "node_shop": 0,
        "node_boss_encounter": 0,
        "train_head": 0,
        "node_empty": -100,
    }
# ── 节点类型枚举 ────────────────────────────────────────────────────────────
class NodeType:
    """镜牢节点类型，与 mirror_cfg.json 中的 node_scores 键名对应。"""
    EVENT = "node_event"
    """事件节点（问号图标）"""
    REGULAR = "node_regular_encounter"
    """普通战斗（暗纹、无代币）"""
    ELITE = "node_elite_encounter"
    """精英战斗（亮纹、有代币）"""
    FOCUSED = "node_focused_encounter"
    """聚焦战斗（复杂花纹、高代币）"""
    ABNORMALITY = "node_abnormality_encounter"
    """异想体战斗"""
    SHOP = "node_shop"
    """商店"""
    BOSS = "node_boss_encounter"
    """Boss战"""


def _classify_node_type(
    gray_crop: np.ndarray,
    is_event: bool,
) -> str:
    """
    根据节点图标的亮度特征分类节点类型。
    
    原理（基于 162 张实际截图分析）:
    - 事件节点: 通过 template matching 判断（问号图标）
    - 普通战斗: 图标暗（mean < 55），无白色高亮区域
    - 精英战斗: 中等亮度（55 ≤ mean < 100），有部分亮纹
    - 聚焦/高难: 高亮度（mean ≥ 100），亮纹密集，通常有代币数字
    - Boss: 极高亮度，中央复杂花纹
    
    参数:
        gray_crop: 灰度图的节点图标区域 (h, w)
        is_event: 是否已通过模板匹配识别为事件节点
    
    返回:
        NodeType 的键名字符串
    """
    if is_event:
        return NodeType.EVENT
    
    mean_bright = float(gray_crop.mean())
    std_val = float(gray_crop.std())
    # 亮像素占比（值 > 200 的像素比例）
    bright_ratio = float(np.sum(gray_crop > 200)) / gray_crop.size
    
    # 分类逻辑（基于实际数据统计）
    if mean_bright >= 100 or bright_ratio > 0.15:
        return NodeType.FOCUSED  # 高亮 → 聚焦/高难战斗
    elif mean_bright >= 55 or bright_ratio > 0.05:
        return NodeType.ELITE  # 中等亮度 → 精英战斗
    else:
        return NodeType.REGULAR  # 暗 → 普通战斗


def _analyze_token_reward(gray_full: np.ndarray, click_cx: int, click_cy: int) -> int:
    """
    检测节点上方的代币奖励数字。
    
    代币位置：在节点图标上方约 25-50 像素处，区域约 40x25。
    通过寻找高亮小区域推断是否存在代币。
    
    原理:
    - 代币数字通常为白色/亮色数字，在深色背景上显著
    - 对我们来说，只需要知道"是否有代币"以及估算数量级
    - 通过亮像素比例和聚集度判断
    
    参数:
        gray_full: 全屏灰度图
        click_cx, click_cy: 节点点击坐标（图标中心）
    
    返回:
        估算的代币数量（0 = 无代币，15, 25, 40 等为常见值）
    """
    # 代币区域：节点图标上方 25~50px, 以 click_cx 为中心 ±25px
    y1 = max(0, click_cy - 58)
    y2 = max(0, click_cy - 25)
    x1 = max(0, click_cx - 30)
    x2 = min(gray_full.shape[1], click_cx + 30)
    
    if y2 <= y1 or x2 <= x1:
        return 0
    
    token_region = gray_full[y1:y2, x1:x2]
    if token_region.size == 0:
        return 0
    
    # 亮像素占比
    _, binary = cv2.threshold(token_region, 200, 255, cv2.THRESH_BINARY)
    bright_pct = float(np.sum(binary > 0)) / token_region.size
    
    if bright_pct > 0.08:
        # 有可见代币 → 根据亮像素密集度估算数量级
        if bright_pct > 0.25:
            return 40   # 高代币（精英/聚焦）
        elif bright_pct > 0.15:
            return 25   # 中等代币
        else:
            return 15   # 低代币
    return 0  # 无代币


def _score_node(
    row: dict,
    mirror_cfg: dict,
    gray_full: np.ndarray,
) -> float:
    """
    综合评分：节点类型权重 × 代币奖励加成。
    
    从 mirror_cfg["node_scores"] 读取各类型权重，
    加上代币奖励作为额外得分。
    """
    node_type = row.get("node_type", NodeType.REGULAR)
    node_scores = mirror_cfg.get("node_scores", {})
    base_score = node_scores.get(node_type, 5)
    
    # 代币奖励加成（每 10 代币 +1 分）
    token = row.get("token_reward", 0)
    token_bonus = token / 10.0
    
    total = base_score + token_bonus
    row["score"] = total
    return total


@TaskExecution.register("mirror_select_next_node")
def exec_mirror_select_next_node(self, node: TaskNode, func):
    """
    快速镜牢节点寻路（高斯平滑偏差法 + 亮度分类 + 代币权重）
    
    原理:
    1. 31x31 高斯平滑抹掉小物体 → 偏差检测节点存在
    2. 亮度分析分类节点类型（普通/精英/聚焦/事件）
    3. 代币奖励区域分析（节点上方的数字）
    4. 综合评分排序：类型权重 + 代币加成
    """
    import random
    import time
    
    tmp_screenshot = input_handler.capture_screenshot()
    logger.info("选择下一个镜牢节点（增强模式：亮度+代币评分）")
    
    # 1. train_head 偏移校准
    train_head = recognize_handler.template_match(tmp_screenshot, "train_head")
    if len(train_head) > 0 and train_head[0][1] < 300:
        input_handler.swipe(460, 270, 460, 340)
        tmp_screenshot = input_handler.capture_screenshot()
    
    # 2. 转为 numpy（彩 + 灰度）
    ss_rgb = np.array(tmp_screenshot).astype(np.float32)
    if len(ss_rgb.shape) == 2:
        ss_rgb = np.stack([ss_rgb, ss_rgb, ss_rgb], axis=-1)
    gray_full = cv2.cvtColor(np.array(tmp_screenshot), cv2.COLOR_RGB2GRAY) if hasattr(cv2, 'COLOR_RGB2GRAY') else \
                np.array(tmp_screenshot.convert('L')).astype(np.uint8)
    
    # 3. 高斯平滑
    bg = cv2.GaussianBlur(ss_rgb, (31, 31), 0)
    
    # 4. 3 条路径的候选区域
    rows = [
        {"name": "上", "click": (710, 110), "y": 80,  "h": 130},
        {"name": "中", "click": (710, 330), "y": 290, "h": 130},
        {"name": "下", "click": (710, 540), "y": 500, "h": 130},
    ]
    col_x = [660, 920]
    col_w = 140
    
    mirror_cfg = self._get_using_cfg("mirror")
    
    # 5. 检测+分类+评分
    row_scores = []
    for row in rows:
        # 5a. 高斯偏差检测（确定是否有节点）
        devs = []
        gray_devs = []
        for cx in col_x:
            crop = ss_rgb[row["y"]:row["y"]+row["h"], cx:cx+col_w, :]
            crop_bg = bg[row["y"]:row["y"]+row["h"], cx:cx+col_w, :]
            ch_devs = np.mean(np.abs(crop - crop_bg), axis=(0, 1))
            diff = np.max(ch_devs)  # 取响应最强通道
            devs.append(diff)
            
            # 同时计算灰度偏差（辅助判断）
            crop_g = gray_full[row["y"]:row["y"]+row["h"], cx:cx+col_w]
            bg_g = cv2.GaussianBlur(crop_g.astype(np.float32), (31, 31), 0)
            gray_devs.append(float(np.mean(np.abs(crop_g.astype(np.float32) - bg_g))))
        
        max_dev = max(devs)
        has_node = max_dev > 12.0
        
        # 5b. 如果检测到节点，提取图标区域做分类
        node_type = NodeType.REGULAR
        is_event = False
        token_reward = 0
        mean_bright = 0.0
        bright_ratio = 0.0
        
        if has_node:
            cx, cy = row["click"]
            # 图标裁剪区域
            icon_y1 = row["y"] + 30   # 图标在行区域内偏下
            icon_y2 = min(row["y"] + row["h"], row["y"] + 115)
            icon_x1 = max(0, cx - 35)
            icon_x2 = min(gray_full.shape[1], cx + 50)
            
            if icon_y2 > icon_y1 and icon_x2 > icon_x1:
                gray_icon = gray_full[icon_y1:icon_y2, icon_x1:icon_x2]
                if gray_icon.size > 0:
                    mean_bright = float(gray_icon.mean())
                    
                    # 事件节点检测（问号图标）
                    icon_mask_list = [icon_x1, icon_y1, icon_x2 - icon_x1, icon_y2 - icon_y1]
                    try:
                        event_matches = recognize_handler.template_match(
                            tmp_screenshot, "node_event", mask=icon_mask_list, threshold=0.6
                        )
                        is_event = len(event_matches) > 0
                    except Exception:
                        is_event = False
                    
                    # 5c. 亮度分类
                    bright_ratio = float(np.sum(gray_icon > 200)) / max(gray_icon.size, 1)
                    node_type = _classify_node_type(gray_icon, is_event)
                    
                    # 5d. 代币检测
                    token_reward = _analyze_token_reward(gray_full, cx, cy)
        
        row_entry = {
            "name": row["name"],
            "click": row["click"],
            "dev": max_dev,
            "has_node": has_node,
            "node_type": node_type,
            "is_event": is_event,
            "token_reward": token_reward,
            "mean_bright": mean_bright,
            "bright_ratio": bright_ratio,
        }
        if has_node:
            _score_node(row_entry, mirror_cfg, gray_full)
        row_scores.append(row_entry)
    
    # 日志输出
    detail_strs = []
    for r in row_scores:
        if r["has_node"]:
            tname = r["node_type"].replace("node_", "")
            token_s = f"💰{r['token_reward']}" if r['token_reward'] > 0 else ""
            detail_strs.append(
                f'{r["name"]}={r["dev"]:.1f}({tname}){token_s}'
                f' 评分={r.get("score", 0):.0f}'
            )
        else:
            detail_strs.append(f'{r["name"]}=空')
    logger.info(f"节点检测+评分: {detail_strs}")
    
    # 6. 筛选有节点的行，按评分排序
    available = [r for r in row_scores if r["has_node"]]
    if available:
        available.sort(key=lambda r: -r.get("score", 0))
    
    # 7. 兜底
    if not available:
        dev_strs = [f"{r['name']}={r['dev']:.1f}" for r in row_scores]
        logger.warning(f"所有行均未检测到节点 (deviations: {dev_strs})，按偏差排序兜底")
        available = sorted(row_scores, key=lambda r: -r["dev"])
    
    next_node_exist = False
    
    # 8. 点击尝试
    for row in available:
        cx, cy = row["click"]
        ox = random.randint(-12, 12)
        oy = random.randint(-8, 8)
        logger.debug(f"尝试点击 {row['name']}: ({cx+ox},{cy+oy})")
        
        input_handler.click(cx + ox, cy + oy)
        time.sleep(0.8)
        
        if (
            len(
                recognize_handler.template_match(
                    input_handler.capture_screenshot(), "node_enter"
                )
            )
            > 0
        ):
            input_handler.key_press("enter")
            next_node_exist = True
            logger.info(
                f"成功进入节点: {row['name']} "
                f"(类型={row.get('node_type','?')}, "
                f"评分={row.get('score',0):.0f})"
            )
            break
        else:
            logger.debug(f"路径 {row['name']} 不可达，尝试下一条")
    
    # 9. 回退 train_head
    if not next_node_exist:
        train_head = recognize_handler.template_match(tmp_screenshot, "train_head")
        if len(train_head) > 0:
            cx, cy = train_head[0][:2]
            ox = random.randint(-10, 10)
            oy = random.randint(-8, 8)
            input_handler.click(cx + ox, cy + oy)
            time.sleep(0.8)
            if (
                len(
                    recognize_handler.template_match(
                        input_handler.capture_screenshot(), "node_enter"
                    )
                )
                > 0
            ):
                input_handler.key_press("enter")
                next_node_exist = True
                logger.info("通过 train_head 回退进入节点")
    
    # 10. 寻路异常
    if not next_node_exist:
        logger.warning(
            "快速寻路失败，所有路径均不可达",
            input_handler.capture_screenshot(),
        )
        return (node.name, None, get_task("back_to_init_page").get_next)


@TaskExecution.register("mirror_select_theme_pack")
def exec_mirror_theme_pack(self, node: TaskNode, func):
    logger.info("选择镜牢主题包", input_handler.capture_screenshot())

    res_name = ""
    res_pos = None
    theme_pack_cfg = self._get_using_cfg("theme_pack")

    theme_packs = sorted(
        theme_pack_cfg.items(),
        key=lambda theme_pack: theme_pack[1]["weight"],
        reverse=True,
    )
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
            if recognize_handler.template_match(
                tmp_screenshot, "hard_mode"
            ):
                input_handler.click(905, 50)
                logger.info("现需要刷取普通镜牢，检测到镜牢开启困难模式，正在关闭")
                time.sleep(5)
                continue
        else:
            if recognize_handler.template_match(
                tmp_screenshot, "normal_mode"
            ):
                input_handler.click(905, 50)
                logger.info("现需要刷取困难镜牢，检测到镜牢开启普通模式，正在关闭")
                time.sleep(5)
                continue

        theme_pack_new = recognize_handler.template_match(
            tmp_screenshot, "mirror_theme_pack_new"
        )
        if len(theme_pack_new) > 0:
            logger.info("检测到未探索的卡包，优先探索")
            res_pos = theme_pack_new
            res_name = "New Theme Pack's Name"
            break

        for theme_pack_name, val in theme_packs:
            cur_weight = val["weight"]
            tmp = recognize_handler.template_match(
                tmp_screenshot, theme_pack_name, mask_template=[20, 20, 130, 290]
            )
            if len(tmp) > 0:
                logger.info(f"检测到卡包 {theme_pack_name},权重：{cur_weight}")
                if not res_pos or cur_weight > theme_pack_cfg[res_name]["weight"]:
                    res_pos = tmp
                    res_name = theme_pack_name
                    if cur_weight > 10:
                        stop = True

        if refresh:
            stop = True

        if not stop and not refresh:
            logger.info("没有找到权值大于基准值（10）的卡包，点击刷新")
            refresh = True
            input_handler.click(1080, 50)
            time.sleep(0.5)
            self.exec_wait_disappear(get_task("wait_connecting_disappear"))
            time.sleep(3)
            res_name = ""
            res_pos = None

    if not res_pos:
        res_pos = recognize_handler.template_match(
            input_handler.capture_screenshot(), "theme_pack_detail"
        )
        logger.warning("没有检测到已知主题包，尝试启动随机选择")
    if len(res_pos) == 0:
        logger.error(
            "主题包检测异常，已有模板匹配失败，且随机选择也失败了，这里跳过选择"
        )
        return

    if res_name in theme_pack_cfg:
        logger.info(
            f"最后选择到了卡包：{res_name}, 对应权重：{theme_pack_cfg[res_name]['weight']}",
            input_handler.capture_screenshot(),
        )
    else:
        logger.info(
            f"最后选择到了卡包：{res_name}, 但本次执行中未找到，临时赋予权重：-999, 下次执行将自动进入配置",
            input_handler.capture_screenshot(),
        )

    input_handler.swipe(
        res_pos[0][0], res_pos[0][1], res_pos[0][0], res_pos[0][1] + 400
    )


@TaskExecution.register("mirror_gift_search")
def exec_mirror_gift_search(self, node: TaskNode, func):
    logger.info("搜索镜牢礼物", input_handler.capture_screenshot())
    # TODO 完善 gift search
    # 现在暂时只是 refuse gift
    input_handler.click(900, 600)
    time.sleep(1)
    input_handler.key_press("enter")


@TaskExecution.register("mirror_select_initial_ego_gift")
def exec_mirror_select_initial_ego_gift(self, node: TaskNode, func):
    cfg_type = node.get_param("cfg_type")
    cfg = self._get_using_cfg(cfg_type)
    cfg_index = self._get_using_cfg_index(cfg_type)
    team_style = cfg["mirror_team_styles"][cfg_index]
    initial_ego_styles = {
        "Burn": (200, 250),
        "Bleed": (350, 250),
        "Tremor": (500, 250),
        "Rupture": (650, 250),
        "Sinking": (200, 450),
        "Poise": (350, 450),
        "Charge": (500, 450),
        "Slash": (650, 450),
        "Pierce": (200, 450),
        "Blunt": (350, 450),
    }
    if team_style == "Pierce" or team_style == "Blunt":
        input_handler.swipe(430, 470, 430, 240)
        time.sleep(0.5)
    input_handler.click(*initial_ego_styles[team_style])
    time.sleep(0.5)
    for i in cfg["mirror_team_initial_ego_orders"][cfg_index]:
        match i:
            case 1:
                input_handler.click(830, 270)
            case 2:
                input_handler.click(830, 370)
            case 3:
                input_handler.click(830, 470)
            case _:
                raise Exception(f"发现非法初始 ego 顺序选项：{i}")
        time.sleep(0.5)
    logger.info("选择初始EGO饰品", input_handler.capture_screenshot())
    for _ in range(4):
        input_handler.key_press("enter")
        time.sleep(0.5)
        self.exec_wait_disappear(get_task("wait_connecting_disappear"))


@TaskExecution.register("mirror_choose_star")
def exec_mirror_choose_star(self, node: TaskNode, func):
    star_pos = [
        (200, 190),
        (400, 190),
        (600, 190),
        (800, 190),
        (1000, 190),
        (200, 410),
        (400, 410),
        (600, 410),
        (800, 410),
        (1000, 410),
    ]
    plus = (0, 150)
    plusplus = (80, 150)
    cfg_type = node.get_param("cfg_type")
    cfg = self._get_using_cfg(cfg_type)
    cfg_index = self._get_using_cfg_index(cfg_type)
    for star_str in cfg["mirror_team_stars"][cfg_index]:
        star_index = int(star_str[0])
        # logger.info(star_index)
        origin_click_pos = star_pos[star_index]
        input_handler.click(*origin_click_pos)
        time.sleep(0.5)
        if len(star_str) == 1:
            continue
        elif len(star_str) == 2:
            click_pos = (origin_click_pos[0] + plus[0], origin_click_pos[1] + plus[1])
            input_handler.click(*click_pos)
            time.sleep(0.5)
        elif len(star_str) == 3:
            click_pos = (
                origin_click_pos[0] + plusplus[0],
                origin_click_pos[1] + plusplus[1],
            )
            input_handler.click(*click_pos)
            time.sleep(0.5)
        else:
            raise Exception("非法 star str：%s" % star_str)
    logger.info("选择镜牢星光", input_handler.capture_screenshot())
    input_handler.click(1190, 670)
    time.sleep(2)
    input_handler.click(735, 535)
