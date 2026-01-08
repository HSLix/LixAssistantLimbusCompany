from workflow.task_execution import *



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
    elif select_mode == "skip battle":
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
    elif select_mode == "skip battle":
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

    