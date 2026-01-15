from workflow.task_execution import *

@TaskExecution.register("check_out_update")
def exec_check_out_update(self, node:TaskNode, func):
    old = node.get_param("execute_count", 0)
    node.set_param("execute_count", old + 1)
    logger.info(f"[check_out_update] 节点<{node.name}> 计数 + 1，当前：{old + 1}")


@TaskExecution.register("init_limbus_window")
def exec_init_limbus_window(self, node:TaskNode, func):
    logger.info("开始初始化Limbus窗口")
    input_handler.open_limbus()
    input_handler.refresh_window_state()
    input_handler.set_window_size()
    logger.info("结束初始化Limbus窗口", input_handler.capture_screenshot())


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
    logger.error(f"报告错误: {node.name}")
    msg = node.get_param("error_msg")
    raise Exception("任务节点{%s} 报告错误：{%s}" % (node.name, msg))