import time
try:
    from input.input_handler import input_handler
    from recognize.img_recognizer import recognize_handler
    # from workflow.task_registry import get_task
except ImportError:
    import sys 
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from input.input_handler import input_handler
    from recognize.img_recognizer import recognize_handler

    # from task_registry import get_task



class TaskNode:
    """
    任务节点类，用于表示工作流中的单个任务节点
    普通任务节点（type=“normal”）负责路由和流程控制，会产生下游节点
    基础任务节点（type=“basic”）负责具体业务执行，是流程的终点
    """
    def __init__(self, name, action, recognition="direct", type="normal", rate_limit=1, enable=True, description="", inverse=False, **kwargs):
        """
        初始化任务节点
        :param name: 任务名
        :param action: 具体任务节点名
        :param description: 任务描述
        """
        self.type = type
        self.name = name
        self.desc = description
        self.recognition = recognition
        self.enable = enable
        self.action = action
        self.inverse = inverse
        self.rate_limit = rate_limit
        self.params = {}
        self.params.update(kwargs)
        self.next = []
        self.interrupt = []

        self.set_param("recognize_result", [])
        self.set_param("pre_delay", self.get_param("pre_delay", 0.3))
        self.set_param("post_delay", self.get_param("post_delay", 0.3))
    
    def get_param(self, key:str, default=None):
        param = self.params.get(key, default)
        if param == None:
            raise ValueError("%s 缺少必要的参数 %s" % (self.name, key))
        return param
    
    def set_param(self, key, val):
        self.params[key] = val

    def get_recognition_params(self):
        """
        根据recognition类型，从 params 中获取需要的变量，返回所需的参数元组
        如果有参数不存在，则
        :return: 所需参数的元组
        """
        if self.recognition == "direct":
            pass
        elif self.recognition == "template_match":
            template = self.get_param("template")
            threshold = self.get_param("threshold", 0.85)
            mask = self.get_param("mask", [0, 0, input_handler.width, input_handler.height])
            return (template, threshold, mask)
        elif self.recognition == "color_template_match":
            template = self.get_param("template")
            threshold = self.get_param("threshold", 0.7)
            mask = self.get_param("mask", [0, 0, input_handler.width, input_handler.height])
            return (template, threshold, mask)
        elif self.recognition == "feature_match":
            template = self.get_param("template")
            threshold = self.get_param("threshold", 0.7)
            mask = self.get_param("mask", [0, 0, input_handler.width, input_handler.height])
            return (template, threshold, mask)
        else:
            raise ValueError(f"未知的recognition类型: {self.recognition}")

    def do_action(self):
        """
        执行任务节点的动作对应节点的路由
        真正实现执行的部分分离到了 TaskExecution 中
        """
        action_task = self.action
        tmp_screenshot = input_handler.capture_screenshot()
        # print("Action recognizer:", self.name, "→", self.action.name, "result:", action_task.do_recognize(tmp_screenshot))
        # 执行该 task node 的 do_recognize()
        if action_task.do_recognize(tmp_screenshot):
            # 如果 do_recognize() 返回 True，返回该 task node 的 (do_action, get_next)
            return (self.name, action_task.do_action, action_task.get_next)
        else:
            # 如果返回 False，返回 (None, None)，并记录 warning 日志
            import logging
            logging.warning("任务节点 do_action 失败")
            return (self.name, None, None)

    def get_next(self):
        """
        获取下一个任务节点
        """
        # 如果当前节点为特殊节点，就采用特殊的获取下个节点方式
        start_time = time.time()
        if self.type == "check":
            res = self.check_node_get_next()
        else:
            res = self.normal_node_get_next()
        used_time = time.time()-start_time
        left_time = self.rate_limit-used_time
        if left_time > 0:
            time.sleep(left_time)
        return res
    
    def normal_node_get_next(self):
        tmp_screenshot = input_handler.capture_screenshot()
        # 按顺序遍历 next 列表
        for next_task in self.next:
            if next_task.do_recognize(tmp_screenshot):
                # 第一个返回 True 的任务节点，立即返回 (do_action, get_next)
                return (self.name, next_task.do_action, next_task.get_next)
        
        # 如果 next 中没有任何一个成功，遍历自身的 interrupt 列表
        for interrupt_task in self.interrupt:
            if interrupt_task.do_recognize(tmp_screenshot):
                # 第一个成功的返回 (do_action, get_next, self.get_next)
                return (self.name, interrupt_task.do_action, interrupt_task.get_next, self.get_next)
        
        # 如果还是没有成功，返回 (None, None)
        return (self.name, None, None)
    

    def check_node_get_next(self):
        """
        检查点的获取下个节点，如果已经执行的次数达到了目标次数，就会跳转到 next，同时会把 origin 的 enable 设置为 False，否则跳到 origin
        """
        if self.get_param("execute_count") == 0:
            self.params["execute_count"] = 1
        else:
            self.params["execute_count"] += 1
        
        if self.get_param("execute_count") < self.get_param("target_count"):
            origin_task = self.get_param("origin")
            return (self.name, origin_task.do_action, origin_task.get_next)
        
        self.params["execute_count"] = 0
        # 检查完成，走正常检测流程
        # origin_task.enable = False
        disable_task = self.get_param("disable_node")
        disable_task.enable = False
        return self.normal_node_get_next()
    
    
    def do_recognize(self, tmp_screenshot) -> bool:
        """
        执行自己的检测函数，并返回检测成功与否
        """
        self.params["recognize_result"].clear()
        res = False
        if self.recognition == "direct":
            res = True
        elif self.recognition == "template_match":
            template, threshold, mask = self.get_recognition_params()
            self.params["recognize_result"] = recognize_handler.template_match(tmp_screenshot, template, threshold, mask=mask)
        elif self.recognition == "color_template_match":
            template, threshold, mask = self.get_recognition_params()
            self.params["recognize_result"] = recognize_handler.color_template_match(tmp_screenshot, template, threshold, mask=mask)
        elif self.recognition == "feature_match":
            template, threshold, mask = self.get_recognition_params()
            self.params["recognize_result"] = recognize_handler.feature_match(tmp_screenshot, template, threshold, mask=mask)
        else:
            raise ValueError("未知 recognition{%s}，无法完成检测动作" % self.recognition)
        res = (res or len(self.get_param("recognize_result")) > 0)
        return self.enable and (res if not self.inverse else not res)


    def __str__(self):
        """
        返回任务节点的字符串表示
        :return: 任务节点信息字符串
        """
        # 避免递归打印，只显示action的名称（如果是TaskNode对象）或action本身
        action_str = str(type(self.action)) + "{" + self.action.name + "}"
        
        # 避免递归打印next和interrupt列表中的TaskNode对象
        next_str = []
        for item in self.next:
            if hasattr(item, 'name'):
                next_str.append(item.name)
            else:
                next_str.append(str(item))
        
        interrupt_str = []
        for item in self.interrupt:
            if hasattr(item, 'name'):
                interrupt_str.append(item.name)
            else:
                interrupt_str.append(str(item))
        
        return f"TaskNode(name='{self.name}', description='{self.desc}', action='{action_str}, next={next_str}, interrupt={interrupt_str}, params={self.params}')"

    def __repr__(self):
        """
        返回任务节点的详细字符串表示
        :return: 任务节点详细信息字符串
        """
        return self.__str__()