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
from recognize.nn_classifier import (
    classify_mirror_legend,
    classify_mirror_path,
    classify_skill_icon,
)

logger = init_logger()

# 新增：让 TaskExecution 能把日志推给 Server
_server_to_push = None  # 由 ServerController 启动时注入


def set_server_ref(server):
    global _server_to_push
    _server_to_push = server


def get_server_ref():
    if _server_to_push is None:
        logger.error("远程服务器为空")
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
    main_loop = getattr(server, "loop", None)
    if main_loop is None:
        logger.warning("服务器未保存主循环引用")
        return

    if main_loop.is_closed():
        logger.warning("主事件循环已关闭，无法广播消息")
        return

    coro = server.broadcast_task_log(msg)

    try:
        asyncio.run_coroutine_threadsafe(coro, main_loop)
    except RuntimeError as e:
        logger.warning(f"广播消息失败: {str(e)}")


class TaskExecution:
    # --------- 类级别：装饰器注册表 ---------
    DECORATED_HANDLERS = {}  # {"click": function, ...}

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
        self._perf: dict[
            str, dict[str, float | int]
        ] = {}  # handler_name -> {"count": int, "total": float}

        logger.info("TaskExecution 初始化完成")

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

    def _get_using_cfg_index(self, cfg_type: str) -> int:
        cfg = self._get_using_cfg(cfg_type)
        using_team_len = len(cfg["team_orders"])
        check_node_name = cfg_type + "_check"
        team_no = get_task(check_node_name).get_param("execute_count")

        return team_no % using_team_len

    def _get_using_cfg(self, cfg_type: str):
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
            bound = self._timed_handler(name, bound)  # 包计时器
            self.handlers[name] = bound

            # 自动绑定为 self.exec_click / self.exec_wait_disappear / ...
            setattr(self, f"exec_{name}", bound)

    def get_perf_summary(self) -> dict[str, dict[str, float | int]]:
        """
        供 AsyncTaskPipeline 调用，返回性能统计副本，按总耗时降序排列
        """
        # 先复制数据
        perf_copy = self._perf.copy()
        # 为每一项添加平均用时计算
        for _, stats in perf_copy.items():
            if stats["count"] > 0:
                stats["avg"] = stats["total"] / stats["count"]
            else:
                stats["avg"] = 0
        # 按总耗时降序排序
        sorted_items = sorted(
            perf_copy.items(), key=lambda x: x[1]["total"], reverse=True
        )
        # 构建排序后的字典
        return dict(sorted_items)

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
        log_msg = (
            f"任务{{{cur_task.name}}}正在执行：{{{func.__name__}}}-{{{action_name}}}"
        )
        logger.info(log_msg)
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
        log_msg = (
            f"任务{{{cur_task.name}}}执行完成：{{{func.__name__}}}-{{{action_name}}}"
        )
        logger.info(log_msg)
        _safe_broadcast(log_msg)

        return res


# 这是初始化动态注册函数的，不能删
import task_action

# ====== 以下开始写所有 task，全部用装饰器注册 =======
# 如果一个节点的 action 与节点同名，那么下面返回的时候就不要再返回这个 action func 的返回值，否则会无限递归执行该 action

from utils.get_save_skill_icon import get_and_save_skill_icons
from utils.get_save_sinner_avatar import get_and_save_sinner_avatar

need_attention_skill_types = ["hopeless", "struggling", "neutral"]


@TaskExecution.register("battle_winrate")
def exec_battle_winrate(self, node: TaskNode, func):
    input_handler.key_press("p")

    ego_enable = self.other_task_cfg.get("ego_enable", False)
    if not ego_enable:
        logger.debug("由于 ego_enable 配置为 False，跳过战斗胜率检测")
        return

    time.sleep(0.5)
    skill_icon_imgs, skill_icon_coordinate = get_and_save_skill_icons()
    skill_icon_types = classify_skill_icon(skill_icon_imgs)
    skill_icon_type_set = set(skill_icon_types)
    if len(skill_icon_type_set) == 1 and skill_icon_types[0] == "unselected":
        logger.debug(
            "检测到技能全是没有选中的状态（unselected），尝试通过点击和重新开 p 来重回正常的战斗流程",
            input_handler.capture_screenshot(),
        )
        input_handler.click(10, 720)
        time.sleep(1)
        return (node.name, node.do_action)

    # 过滤掉 unselected 类型的技能图标
    filtered_skill_icon_types = []
    filtered_skill_icon_coordinate = []
    for skill_type, coord in zip(skill_icon_types, skill_icon_coordinate):
        if skill_type != "unselected":
            filtered_skill_icon_types.append(skill_type)
            filtered_skill_icon_coordinate.append(coord)

    may_lose_coin_coordinate = []
    for type, icon_place in zip(
        filtered_skill_icon_types, filtered_skill_icon_coordinate
    ):
        if type in need_attention_skill_types:
            may_lose_coin_coordinate.append(icon_place)

    if len(may_lose_coin_coordinate) > 0:
        _, sinner_avatar_coordinate, sinner_avatar_scores = get_and_save_sinner_avatar()

        ego_available = [max(score) >= 110 for score in sinner_avatar_scores]

        # 筛选出有分配到 may lose coin 的 sinner avatar
        sinner_avatar_idx_with_lose_coin = []
        for lose_coin_x, _ in may_lose_coin_coordinate:
            for idx, (sx, _) in enumerate(sinner_avatar_coordinate):
                # 获取当前 sinner avatar 的 x 坐标
                current_sinner_x = sx

                # 获取下一个 sinner avatar 的 x 坐标（如果存在）
                if idx + 1 < len(sinner_avatar_coordinate):
                    next_sinner_x = sinner_avatar_coordinate[idx + 1][0]
                else:
                    # 最后一个 sinner avatar，没有上限
                    next_sinner_x = float("inf")

                # 检查 lose coin 是否属于当前 sinner avatar
                if current_sinner_x <= lose_coin_x < next_sinner_x:
                    if (
                        idx not in sinner_avatar_idx_with_lose_coin
                        and ego_available[idx] == True
                    ):
                        sinner_avatar_idx_with_lose_coin.append(idx)
                    break

        ego_selected = False
        # 启动 EGO
        for idx in sinner_avatar_idx_with_lose_coin:
            input_handler.long_press(*sinner_avatar_coordinate[idx], 3)
            tmp_sc = input_handler.capture_screenshot()
            ego_details = recognize_handler.template_match(
                tmp_sc, "ego_details", mask=[0, 95, 1280, 110]
            )
            logger.info("尝试启用该罪人的 EGO", tmp_sc)

            if len(ego_details) > 0:
                ego_details.sort(key=lambda x: -x[0])
                for detail in ego_details:
                    # 检查该 detail 的 x-200 到 x 内，有没有 to_corrode_0%
                    corrode_elements = recognize_handler.template_match(
                        tmp_sc,
                        "to_corrode_0%",
                        mask=[detail[0] - 200, 95, detail[0], 205],
                    )
                    if len(corrode_elements) == 0:
                        logger.debug(
                            f"发现 EGO detail (x={detail[0]}, y={detail[1]}) 没有 0% 侵蚀选项，可能都有侵蚀风险，跳过本次选择"
                        )
                        continue
                    input_handler.click(detail[0] - 20, detail[1] + 100)
                    time.sleep(0.3)
                    input_handler.click(detail[0] - 20, detail[1] + 100)
                    time.sleep(0.5)
                    if (
                        len(
                            recognize_handler.template_match(
                                input_handler.capture_screenshot(), "ego_details"
                            )
                        )
                        == 0
                    ):
                        ego_selected = True
                        logger.debug("完成一次 EGO 选择")
                        break
            if not ego_selected:
                logger.debug(
                    "检测到尝试选择 EGO 后还没退出选择界面，现直接退出选择界面"
                )
                input_handler.click(*sinner_avatar_coordinate[idx])
            else:
                input_handler.click(30, 700) # 防止卡在选择界面
                logger.warning(
                    "没有找到 EGO 的标识，跳过本次 EGO 选择(可能原因：罪人混乱，识别误差……)"
                )
        if ego_selected:
            input_handler.key_press("p")
            time.sleep(0.3)
            input_handler.key_press("p")
            time.sleep(0.3)
            input_handler.key_press("p")
        logger.info(
            f"检测到可能需要主动触发 EGO; sinner_avatar_idx_with_lose_coin: {sinner_avatar_idx_with_lose_coin}; ego_available:{ego_available}; sinner_avatar_coordinate:{sinner_avatar_coordinate}; sinner_avatar_scores:{sinner_avatar_scores}; may_lose_coin_coordinate : {may_lose_coin_coordinate}; skill_icon_types：{filtered_skill_icon_types}; skill_icon_coordinate: {filtered_skill_icon_coordinate};",
            input_handler.capture_screenshot(),
        )
    else:
        logger.info(
            f"没有检测到均势和劣势拼点，不需要主动触发 EGO; skill_icon_types：{filtered_skill_icon_types}; skill_icon_coordinate: {filtered_skill_icon_coordinate};",
            input_handler.capture_screenshot(),
        )


@TaskExecution.register("back_to_init_page")
def exec_back_to_init_page(self, node: TaskNode, func):
    tmp_screenshot = input_handler.capture_screenshot()
    logger.info("正在尝试返回主页", tmp_screenshot)
    if recognize_handler.template_match(tmp_screenshot, "left_top_arrow"):
        # 对于左上角有箭头的，总之先点了
        pos = recognize_handler.template_match(tmp_screenshot, "left_top_arrow")
        if len(pos) > 0:
            input_handler.click(pos[0][0], pos[0][1])
    elif recognize_handler.template_match(tmp_screenshot, "win_rate"):
        input_handler.click(1230, 45)
        time.sleep(2)
        input_handler.click(640, 400)  # 非镜牢的退出
        input_handler.click(640, 430)  # 镜牢的战斗退出
    elif recognize_handler.template_match(tmp_screenshot, "defeat"):
        input_handler.key_press("enter")
        time.sleep(1)
    elif recognize_handler.template_match(
        tmp_screenshot, "right_top_setting"
    ) or recognize_handler.template_match(tmp_screenshot, "pack_search"):
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
def exec_error_cannot_operate_the_game_window(self, node: TaskNode, func):
    logger.info("开始重启 Limbus")
    # 先尝试关闭现有的Limbus窗口
    input_handler.close_limbus_window()
    time.sleep(2)  # 等待窗口完全关闭

    # 重新打开Limbus窗口
    input_handler.open_limbus()
    input_handler.refresh_window_state()
    input_handler.set_window_size()
    logger.info("结束重启 Limbus", input_handler.capture_screenshot())


@TaskExecution.register("confirm_all_coins")
def exec_confirm_all_coins(self, node: TaskNode, func):
    tmp_sc = input_handler.capture_screenshot()
    logger.info("开始收集日常的奖励", tmp_sc)
    for pos in recognize_handler.template_match(tmp_sc, "reward_coin"):
        input_handler.click(pos[0], pos[1])
        self.exec_wait_disappear(get_task("wait_connecting_disappear"))

    input_handler.click(270, 400)
    time.sleep(1)
    tmp_sc = input_handler.capture_screenshot()
    logger.info("开始收集周常的奖励", tmp_sc)
    for pos in recognize_handler.template_match(tmp_sc, "reward_coin"):
        input_handler.click(pos[0], pos[1])
        self.exec_wait_disappear(get_task("wait_connecting_disappear"))
