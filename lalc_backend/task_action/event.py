from workflow.task_execution import *


@TaskExecution.register("event_pass_check")
def exec_event_pass_check(self, node:TaskNode, func):
    tmp_screenshot = input_handler.capture_screenshot()
    logger.info("事件判定检查", tmp_screenshot)
    recognized = False
    for s in ["very_high", "high", "normal", "low", "very_low"]:
        res = recognize_handler.template_match(tmp_screenshot, "event_pass_"+s, mask=[20, 590, 950, 60])
        if len(res) > 0:
            recognized = True
            input_handler.click(res[0][0], res[0][1])
            break
    if not recognized:
        logger.debug("事件判定检测失败，启用小唐")
        input_handler.click(210, 650)
    time.sleep(1)
    input_handler.click(1120, 650)
    


@TaskExecution.register("event_make_choice")
def exec_event_make_choice(self, node:TaskNode, func):
    # 使选项置中
    scroll_strip_pos = recognize_handler.template_match(input_handler.capture_screenshot(), "event_scroll_strip")
    if len(scroll_strip_pos) > 0:
        input_handler.click(scroll_strip_pos[0][0], scroll_strip_pos[0][1])
    time.sleep(1)
    tmp_screenshot = input_handler.capture_screenshot()
    logger.info("事件选项处理", tmp_screenshot)
    special_case = False
    
    # 优先选能拿 E.G.O 的
    results = recognize_handler.detect_text_in_image(tmp_screenshot, mask=[670, 140, 620, 500])
    special_phase = ["Select to gain", "Pass to level up", "Pass to gain", "check to gain", "depending on"]
    for res in results:
        if any(phase in res[0] for phase in special_phase):
            logger.info(f"找到优先选项：{res[0]}")
            input_handler.click(res[1], res[2])
            special_case = True
    
    if not special_case:
        # raise Exception("进入了普通情况，请人工检查是否需要补充事件匹配")
        for x, y in [(950, 200), (950, 290), (950, 380), (950, 450)]:
            input_handler.click(x, y)   