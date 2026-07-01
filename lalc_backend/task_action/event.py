from workflow.task_execution import *


# ── 保留旧 handler 空桩（外部引用兼容） ──

@TaskExecution.register("event_pass_check")
def exec_event_pass_check(self, node: TaskNode, func):
    pass


@TaskExecution.register("event_make_choice")
def exec_event_make_choice(self, node: TaskNode, func):
    pass


# ── 固定坐标（1280x720，所有事件UI元素位置不变） ──

_SKIP_POS     = (1130, 644)      # Skip 按钮（右下角，已验证）
_BLANK_POS    = (640, 360)       # 中央空白 —— 推进对话，远离底部按钮区
_COMMENCE_POS = (1120, 650)      # Commence 按钮（已验证）
_CONFIRM_POS  = (640, 530)       # 饰品/奖励确认

# 右上选项固定位（最多4个，从上到下，默认选第一个）
_OPTION_POS = [
    (950, 200), (950, 290), (950, 380), (950, 450),
]

# 概率徽章搜索区域
# 旧 mask=[20, 590, 950, 60] 只覆盖 x=20~970，可能切掉右侧角色
# 扩宽到 x=20~1080，避开右下角的 SKIP(1130,644)/Commence(1120,650)
_PASS_MASK = [20, 585, 1060, 80]


# ── 连点参数 ──

_BLANK_CHUNK   = 8     # 一组连点次数
_MAX_BLANK_RD  = 8     # 最多连续几组空白才截图


# ══════════════════════════════════════════════════════════════

@TaskExecution.register("event_loop")
def exec_event_loop(self, node: TaskNode, func):
    """
    加速事件处理循环。

    事件实际流程（SKIP 只压缩故事，不跳过判定）:
      1. 故事阶段 — 点 SKIP 压缩，无 SKIP 则点空白推进
      2. 选项阶段 — 右上固定位选最优
      3. 判定过渡 — 选完选项 → 点右下空白 2-3 次 → UI 切换
      4. 判定阶段 — 左下选角 → Commence → 等待结果
      5. 结算阶段 — SKIP 跳过结果描述 → 确认奖励

    核心优化：元素固定位 → 精确坐标连点（不截图）；
              只在决策点截图评估。提速约 10x。
    """
    logger.info("进入加速事件循环 v2", input_handler.capture_screenshot())

    start_ts = time.time()
    MAX_DURATION = 180
    blank_round = 0

    while time.time() - start_ts < MAX_DURATION:
        # ════════════════════════════════════════════
        # 阶段 A：快速连点（不截图）
        # ════════════════════════════════════════════
        if blank_round < _MAX_BLANK_RD:
            for _ in range(_BLANK_CHUNK):
                input_handler.click(_BLANK_POS[0], _BLANK_POS[1])
                time.sleep(0.03)
            blank_round += 1
            continue

        # ════════════════════════════════════════════
        # 阶段 B：截图评估
        # ════════════════════════════════════════════
        blank_round = 0
        screenshot = input_handler.capture_screenshot()

        # ---- 1. SKIP（压缩剩余故事 / 跳过判定结果文本） ----
        if recognize_handler.template_match(screenshot, "event_skip"):
            logger.debug("SKIP → 压缩故事/跳过结果文本")
            input_handler.click(_SKIP_POS[0], _SKIP_POS[1])
            time.sleep(0.3)
            continue

        if recognize_handler.template_match(
            screenshot, "event_skip_dark", threshold=0.9
        ):
            logger.debug("SKIP(dark)")
            input_handler.click(_SKIP_POS[0], _SKIP_POS[1])
            time.sleep(0.3)
            continue

        # ---- 2. 选项（固定位，默认选第一个） ----
        if recognize_handler.template_match(screenshot, "event_choices"):
            logger.debug("选项出现 → 选第一个")
            input_handler.click(*_OPTION_POS[0])
            time.sleep(0.3)
            continue

        # ---- 3. 角色判定（概率色块模板匹配） ----
        found_prob = False
        for prob_key in ["very_high", "high", "normal", "low", "very_low"]:
            res = recognize_handler.template_match(
                screenshot,
                "event_pass_" + prob_key,
                mask=_PASS_MASK,
            )
            if res:
                logger.debug(f"判定 → {prob_key} @({res[0][0]},{res[0][1]})")
                input_handler.click(res[0][0], res[0][1])
                found_prob = True
                break

        if found_prob:
            time.sleep(0.3)
            # 点 Commence 发起判定
            input_handler.click(_COMMENCE_POS[0], _COMMENCE_POS[1])
            logger.debug("Commence 发起判定")
            time.sleep(0.5)
            continue

        # ---- 4. 检测 choose_character 横幅 → 点 Commence ----
        if recognize_handler.template_match(
            screenshot, "choose_character_to_perform_the_check"
        ):
            logger.debug("检测到选人横幅 → Commence")
            input_handler.click(_COMMENCE_POS[0], _COMMENCE_POS[1])
            time.sleep(0.5)
            continue

        # ---- 5. 饰品/奖励确认 ----
        if recognize_handler.template_match(screenshot, "ego_gift_get"):
            logger.info("确认饰品/奖励")
            input_handler.click(_CONFIRM_POS[0], _CONFIRM_POS[1])
            time.sleep(0.3)
            continue

        # ---- 6. 等待 connecting 消失 ----
        if recognize_handler.template_match(
            screenshot, "connecting", mask=[1000, 0, 300, 200],
        ):
            logger.debug("connecting 等待")
            for _ in range(60):
                if not recognize_handler.template_match(
                    input_handler.capture_screenshot(),
                    "connecting", mask=[1000, 0, 300, 200],
                ):
                    break
                time.sleep(0.2)
            continue

        # ---- 7. 退出 —— 回到地图/商店 ----
        if any(
            recognize_handler.template_match(
                input_handler.capture_screenshot(), t,
            )
            for t in ["legend", "pack_search", "mirror_shop", "details"]
        ):
            logger.info("事件结束，回到地图")
            break

        # ---- 8. fallback：点 Commence 防卡死 ----
        logger.debug("无命中 → 点 Commence 防卡")
        input_handler.click(_COMMENCE_POS[0], _COMMENCE_POS[1])
        time.sleep(0.3)

    logger.info("加速事件循环结束")
