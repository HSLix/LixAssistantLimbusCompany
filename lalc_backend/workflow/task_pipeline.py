try:
    from workflow.task_registry import get_task, init_tasks
    from workflow.task_execution import TaskExecution
except ImportError:
    import sys 
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from workflow.task_execution import TaskExecution
    from workflow.task_registry import get_task, init_tasks

import threading




class TaskPipeline:
    """
    任务流水线，负责从任务的开始节点流水线执行到next为空
    实现基于函数栈的新任务处理机制
    """
    def __init__(self):
        # 内部维护一个栈，存储的内容是"函数"（这里指任务节点的 do_action 和 get_next）
        init_tasks()
        self.task_stack = []
        self.task_execution = None
        self.continue_run = threading.Event()
        self.continue_run.set()  # 默认设置为运行状态

    def refresh_target_count(self, share_params: dict):
        """
        根据 share params 的内容，把几个 target count 的值给覆盖一下，这是以前版本的做法。
        但这个方法不优雅，目前 check 节点由于属于路由的范畴，所以暂且放在 task node，但路由的功能能否从 task node 分离也还需要探讨
        """
        for check_name, cfg_name in [("exp_check", "exp_cfg"), ("thread_check", "thread_cfg"), ("mirror_check", "mirror_cfg")]:
            check_task = get_task(check_name)
            check_task.set_param("target_count", share_params[cfg_name]["check_node_target_count"])
            if check_task.get_param("target_count") == 0:
                check_task.get_param("disable_node").enable = False
        # get_task("exp_check").set_param("target_count", share_params["exp_cfg"]["check_node_target_count"])
        # get_task("thread_check").
        # set_param("target_count", share_params["thread_cfg"]["check_node_target_count"])
        # get_task("mirror_check").set_param("target_count", share_params["mirror_cfg"]["check_node_target_count"])

    def add_start_task(self, task_name: str, share_params: dict):
        """
        清空任务栈，并添加起始任务
        """
        # 初始化执行类
        self.task_execution = TaskExecution(share_params)

        # 清空任务栈
        self.task_stack.clear()
        
        # 使用 task registry 的 get_task 获取 TaskNode
        task_node = get_task(task_name)
        
        # 获取该节点的 do_action 和 get_next 函数
        self.pre_task_name, do_action_func, get_next_func = task_node.name, task_node.do_action, task_node.get_next
        
        # 按压栈规则压入（先 get_next，再 do_action）
        if get_next_func is not None:
            self.task_stack.append(get_next_func)
        if do_action_func is not None:
            self.task_stack.append(do_action_func)

        self.refresh_target_count(share_params=share_params)

    def run(self):
        """
        主循环不断 pop 栈顶的函数并执行它（无参数）
        """
        self.continue_run.set() # 用于外界编辑暂停
        while self.task_stack and self.continue_run.is_set():
            # print(self.task_stack)
            # pop 栈顶的函数
            func = self.task_stack.pop()
            
            # 执行函数（无参数）
            cur_task_name, do_action_func, *get_next_func = self.task_execution.execute(self.pre_task_name, func)
            self.pre_task_name = cur_task_name

            # 压栈规则：先压 get_next_func，再压 do_action_func
            # 现在这样，就会按传值从左向右执行
            # 如果某个函数是 None，则不压入

            for next_func in reversed(get_next_func):
                if next_func is not None:
                    self.task_stack.append(next_func)
            if do_action_func is not None:
                self.task_stack.append(do_action_func)

        print("Pipeline 结束")
        
    def pause(self):
        """
        暂停任务执行
        """
        self.continue_run.clear()
        
    def resume(self):
        """
        恢复任务执行
        """
        if not self.continue_run.is_set():
            self.continue_run.set()
            self.run()
        else:
            print("程序还没停止，错误地调用了 resume")
        
    def stop(self):
        """
        停止任务执行
        """
        # 清空任务栈以停止执行
        self.task_stack.clear()
        # 确保设置为运行状态，以便下次可以重新开始
        self.continue_run.set()

if __name__ == "__main__":
    from input.input_handler import input_handler
    from utils.config_manager import initialize_configs
    
    task_pipeline = TaskPipeline()
    
    # 初始化配置管理器
    config_manager = initialize_configs()
    
    # 从配置管理器加载配置
    exp_cfg = config_manager.get_exp_config()
    thread_cfg = config_manager.get_thread_config()
    mirror_cfg = config_manager.get_mirror_config()
    other_task_cfg = config_manager.get_other_task_config()
    theme_pack_cfg = config_manager.get_theme_pack_config()
    
    # 保存配置
    # config_manager.save_configs()
    
    share_params = {
        "exp_cfg": exp_cfg,
        "thread_cfg": thread_cfg,
        "mirror_cfg": mirror_cfg,
        "other_task_cfg": other_task_cfg,
        "theme_pack_cfg": theme_pack_cfg,
    }
    
    task_pipeline.add_start_task("main", share_params)
    task_pipeline.run()