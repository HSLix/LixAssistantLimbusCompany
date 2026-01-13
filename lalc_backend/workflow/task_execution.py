"""
任务执行模块，负责执行具体的操作如点击、键盘输入等
"""
import time
import difflib
import asyncio
from typing import Callable

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


def get_server_ref():
    if _server_to_push is None:
        logger.log("远程服务器为空", level="WARNING")
        return
    return _server_to_push


def _safe_broadcast(msg: str) -> None:
    """
    线程安全：把消息投递到**主线程**事件循环，然后返回。
    当前线程可以没有循环。
    """
    server = get_server_ref()
    if server is None:
        return
    
    # 获取保存的主循环
    main_loop = getattr(server, 'loop', None)
    if main_loop is None:
        logger.log("服务器未保存主循环引用", level="WARNING")
        return

    if main_loop.is_closed():
        logger.log("主事件循环已关闭，无法广播消息", level="WARNING")
        return

    coro = server.broadcast_task_log(msg)
    
    try:
        asyncio.run_coroutine_threadsafe(coro, main_loop)
    except RuntimeError as e:
        logger.log(f"广播消息失败: {str(e)}", level="WARNING")



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
        
        # ---------- 性能统计 ----------
        self._perf: dict[str, dict[str, float | int]] = {}   # handler_name -> {"count": int, "total": float}
        
        logger.log("TaskExecution 初始化完成")


    def _timed_handler(self, handler_name: str, handler: Callable) -> Callable:
        """
        为每个注册的 handler 包一层计时器
        """
        import time
        def wrapper(*args, **kwargs):
            st = time.perf_counter()
            try:
                return handler(*args, **kwargs)
            finally:
                cost = time.perf_counter() - st
                stat = self._perf.setdefault(handler_name, {"count": 0, "total": 0.0})
                stat["count"] += 1
                stat["total"] += cost
        return wrapper

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
            bound = self._timed_handler(name, bound)   # 包计时器
            self.handlers[name] = bound

            # 自动绑定为 self.exec_click / self.exec_wait_disappear / ...
            setattr(self, f"exec_{name}", bound)


    def get_perf_summary(self) -> dict[str, dict[str, float | int]]:
        """
        供 AsyncTaskPipeline 调用，返回性能统计副本
        """
        return self._perf.copy()


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
        _safe_broadcast(log_msg)

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
        _safe_broadcast(log_msg)
            
        return res


# 这是初始化动态注册函数的，不能删
import task_action

# ====== 以下开始写所有 task，全部用装饰器注册 =======
# 如果一个节点的 action 与节点同名，那么下面返回的时候就不要再返回这个 action func 的返回值，否则会无限递归执行该 action
@TaskExecution.register("back_to_init_page")
def exec_back_to_init_page(self, node:TaskNode, func):
    tmp_screenshot = input_handler.capture_screenshot()
    logger.log("正在尝试返回主页", tmp_screenshot)
    if recognize_handler.template_match(tmp_screenshot, "left_top_arrow"):
        # 对于左上角有箭头的，总之先点了
        pos = recognize_handler.template_match(tmp_screenshot, "left_top_arrow")
        if len(pos) > 0:
            input_handler.click(pos[0][0], pos[0][1])
    elif recognize_handler.template_match(tmp_screenshot, "win_rate"):
        input_handler.click(1230, 45)
        time.sleep(2)
        input_handler.click(640, 430)
    elif recognize_handler.template_match(tmp_screenshot, "right_top_setting") or recognize_handler.template_match(tmp_screenshot, "pack_search"):
        # 先处理主题页（这个的设置好像不同），或其它右上角有设置的，就当是镜牢内的情况
        logger.debug("检测到可能处于镜牢的其它情况，启动从设置返回")
        input_handler.click(1230, 45)
        time.sleep(2)
        input_handler.click(730, 435)
        time.sleep(2)
        input_handler.key_press("enter")
    else:
        logger.debug("没检测到需要特殊处理的情况", tmp_screenshot)
        time.sleep(5)
    time.sleep(1)


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
    tmp_sc = input_handler.capture_screenshot()
    logger.log("开始收集日常的奖励", tmp_sc)
    for pos in recognize_handler.template_match(tmp_sc, "reward_coin"):
        input_handler.click(pos[0], pos[1])
        self.exec_wait_disappear(get_task("wait_connecting_disappear"))
    
    input_handler.click(270, 400)
    time.sleep(1)
    tmp_sc = input_handler.capture_screenshot()
    logger.log("开始收集周常的奖励", tmp_sc)
    for pos in recognize_handler.template_match(tmp_sc, "reward_coin"):
        input_handler.click(pos[0], pos[1])
        self.exec_wait_disappear(get_task("wait_connecting_disappear"))
