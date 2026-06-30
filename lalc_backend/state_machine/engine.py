"""
状态机引擎 — 替代旧 _worker() 轮询循环

核心思路：
  1. 从转换表读取当前状态的动作
  2. 执行动作（点击/按键/调用 handler）
  3. 等动作完成
  4. 转移到下一个状态
  5. 错误拦截器每 5s 运行一次（不占每 tick 开销）

不再：每 1.1s 截图 → 6 次模板匹配 → 全空 → 继续
"""
import time
import logging
from typing import Optional

from input.input_handler import input_handler
from recognize.img_recognizer import recognize_handler
from workflow.task_node import TaskNode
from workflow.task_registry import get_task

from .states import GameState, UI_POSITIONS
from .transitions import Transition, Action, ActionType
from .interceptor import ErrorInterceptor
from .supervisor import Supervisor, DEFAULT_CONFIGS
from .supervisor import EscalationLevel

class MachineContext:
    """状态机上下文：持有共享配置 + 执行环境。
    
    对应旧的 TaskExecution 实例（self 上挂了一堆 cfg 和 handler）。
    在状态机模式下，pipeline 把一个 TaskExecution 实例传过来。
    """
    def __init__(self, task_execution, shared_params):
        self.task_execution = task_execution  # TaskExecution 实例
        self.shared_params = shared_params
        self._mirror_deployment_done = False
        self._enkephalin_purchase_count = 0  # 代替 OCR 读购买次数


class GameStateMachine:
    """确定性状态机引擎。
    
    用法：
        machine = GameStateMachine(context)
        machine.run(flow_table)
    
    flow_table 由 build_daily_flow() 根据配置生成。
    """
    
    def __init__(self, context: MachineContext, supervisor: Optional[Supervisor] = None):
        self.ctx = context
        self.te = context.task_execution  # shortcut
        self.logger = logging.getLogger(__name__)
        self.interceptor = ErrorInterceptor()
        self.supervisor = supervisor or Supervisor()  # 监督层
        self._current_state: GameState = GameState.INIT
        
    def run(self, transitions: list[Transition]) -> Optional[str]:
        """运行状态机直到 END 或出错。
        
        Args:
            transitions: 转换表（由 build_daily_flow 生成）
        
        Returns:
            None 正常完成
            str  错误节点名（传给原有 error_handler 兜底）
        """
        idx = 0
        while idx < len(transitions):
            t = transitions[idx]
            self._current_state = t.from_state
            
            # 0a. 监督器：进入此状态
            state_name = t.from_state.name
            if not self.supervisor.before_state(state_name):
                # 监督器说跳过
                idx += 1
                continue
            
            # 0b. 错误拦截器定时触发（只在每个状态切换时检查）
            if idx % 3 == 0:  # 每 3 个状态检查一次 ≈ 每 5-15s
                err_state = self.interceptor.tick()
                if err_state:
                    self.logger.warning(f"错误拦截器触发: {err_state}")
                    self._handle_error(err_state)
            
            # 1. 执行动作
            state_start = time.time()
            success = self._execute_action(t.action, t.timeout)
            duration = time.time() - state_start
            
            # 1a. 监督器：退出此状态
            self.supervisor.after_state(state_name, success, duration)
            
            # 1b. 失败处理 + 升级检测
            if not success and t.retry_on_error:
                if self.supervisor.should_escalate(state_name):
                    msg = self.supervisor.escalate(state_name)
                    self.logger.warning(f"[升级] {msg}")
                    # 根据升级等级决定行为
                    escalate_lv = self.supervisor.get_config(state_name).escalate_level
                    if escalate_lv == EscalationLevel.STOP:
                        return state_name  # 终止流水线
                    elif escalate_lv == EscalationLevel.SKIP:
                        idx += 1
                        continue
                    # ESCALATE 或 RETRY：继续重试
                
                for attempt in range(t.max_retries):
                    self.logger.info(f"重试 {attempt+1}/{t.max_retries}: {t.action.desc}")
                    time.sleep(1)
                    state_start = time.time()
                    success = self._execute_action(t.action, t.timeout)
                    duration = time.time() - state_start
                    self.supervisor.after_state(state_name, success, duration)
                    if success:
                        break
                    
                    if self.supervisor.should_escalate(state_name):
                        msg = self.supervisor.escalate(state_name)
                        escalate_lv = self.supervisor.get_config(state_name).escalate_level
                        if escalate_lv == EscalationLevel.STOP:
                            return state_name
                        elif escalate_lv == EscalationLevel.SKIP:
                            idx += 1
                            break
            
            if not success and not t.retry_on_error:
                self.logger.warning(f"动作失败（不重试）: {t.action.desc}")
                # 跳到下一个状态，不卡死
            
            # 2. 验证到达目标状态（可选）
            if t.verify_template and success:
                self._verify_state(t.verify_template, t.timeout)
            
            # 3. 目标状态 = 来自转换表
            idx += 1
        
        self.logger.info("状态机完成")
        return None
    
    def _execute_action(self, action: Action, timeout: float) -> bool:
        """执行一个原子动作，返回是否成功"""
        try:
            match action.type:
                case ActionType.CLICK:
                    if "pos_key" in action.params:
                        pos = UI_POSITIONS.get(action.params["pos_key"])
                        if pos is None:
                            self.logger.error(f"未知坐标键: {action.params['pos_key']}")
                            return False
                        x, y = pos
                    elif "x" in action.params:
                        x, y = action.params["x"], action.params["y"]
                    else:
                        return False
                    self.logger.info(f"Click ({x}, {y}) | {action.desc}")
                    input_handler.click(x, y)
                    
                case ActionType.KEY:
                    key = action.params["key"]
                    self.logger.info(f"Key '{key}' | {action.desc}")
                    input_handler.key_press(key)
                    
                case ActionType.SLEEP:
                    secs = action.params["seconds"]
                    self.logger.info(f"Sleep {secs}s | {action.desc}")
                    time.sleep(secs)
                    
                case ActionType.SWIPE:
                    p = action.params
                    self.logger.info(f"Swipe ({p['x1']},{p['y1']})→({p['x2']},{p['y2']}) | {action.desc}")
                    input_handler.swipe(p["x1"], p["y1"], p["x2"], p["y2"])
                    
                case ActionType.SCROLL_RIGHT | ActionType.SCROLL_DOWN:
                    self._execute_scroll(action)
                    
                case ActionType.HANDLER:
                    handler_name = action.params["handler_name"]
                    self.logger.info(f"Handler '{handler_name}' | {action.desc}")
                    self._call_handler(handler_name)
                    
                case ActionType.SEQUENCE:
                    self.logger.info(f"Sequence ({len(action.params['actions'])} steps) | {action.desc}")
                    for sub in action.params["actions"]:
                        self._execute_action(sub, timeout)
                        
                case _:
                    self.logger.warning(f"未知动作类型: {action.type}")
                    return False
                    
            return True
            
        except Exception as e:
            self.logger.error(f"动作执行失败: {e}")
            return False
    
    def _execute_scroll(self, action: Action):
        """执行惰性滚动操作（SCROLL_RIGHT / SCROLL_DOWN）。
        
        用 ScrollHelper 的帧差异检测滑动到尾部，然后点击固定位置。
        """
        try:
            from state_machine.scroll_helper import ScrollHelper
        except ImportError:
            self.logger.warning("ScrollHelper 导入失败，降级为普通滑动")
            p = action.params
            sw = p["swipe_start"]
            se = p["swipe_end"]
            for _ in range(p.get("max_swipes", 3)):
                input_handler.swipe(*sw, *se)
                time.sleep(0.3)
            return
        
        helper = ScrollHelper(input_handler)
        p = action.params
        
        helper.scroll_to_tail(
            direction=p["direction"],
            swipe_start=tuple(p["swipe_start"]),
            swipe_end=tuple(p["swipe_end"]),
            max_swipes=p.get("max_swipes", 8),
            diff_threshold=p.get("diff_threshold", 5.0),
        )
        
        # 滑动后点击（如果有指定）
        click_after = p.get("click_after")
        if click_after:
            self.logger.info(f"  滑动后点击 {click_after}")
            input_handler.click(*click_after)
    
    def _call_handler(self, handler_name: str):
        """调用已注册的 @TaskExecution.register(handler_name) handler。
        
        从 self.te.handlers 中查找并调用。
        模拟旧 pipeline 的 execute() 调用方式。
        """
        handler = self.te.handlers.get(handler_name)
        if handler is None:
            self.logger.error(f"Handler '{handler_name}' 未注册")
            # fallback: 尝试作为 task node 执行
            task = get_task(handler_name)
            if task:
                handler = self.te.handlers.get(task.action.name)
                if handler:
                    handler(task, task.do_action)
                    return
            return
        
        # 构造一个虚拟 TaskNode 供 handler 使用
        # 旧 handler 签名: handler(self, node, func)
        # self 是 TaskExecution 实例 → 已绑定到 self.te
        # 我们需要创建一个最少信息的 TaskNode
        from workflow.task_node import TaskNode
        dummy_node = TaskNode(handler_name, handler_name)
        dummy_node.set_param("cfg_type", self._infer_cfg_type(handler_name))
        
        # 调用
        handler(dummy_node, dummy_node.do_action)
    
    def _infer_cfg_type(self, handler_name: str) -> str:
        """从 handler 名推断 cfg_type"""
        if "mirror" in handler_name:
            return "mirror"
        if "exp" in handler_name:
            return "exp"
        if "thread" in handler_name:
            return "thread"
        if "recharge" in handler_name or "enkephalin" in handler_name:
            return "other_task"
        if "theme" in handler_name:
            return "theme_pack"
        return "mirror"  # 默认
    
    def _verify_state(self, template_name: str, timeout: float):
        """用模板匹配验证到达目标状态，超时则跳过"""
        deadline = time.time() + min(timeout, 10.0)
        while time.time() < deadline:
            res = recognize_handler.template_match(
                input_handler.capture_screenshot(), template_name
            )
            if len(res) > 0:
                return
            time.sleep(0.5)
    
    def _handle_error(self, error_state: str):
        """处理错误状态。
        
        旧 error_handler 做的事：
        - 检查各种弹窗模板
        - 点击确认/重试
        - 按 Escape
        
        这里直接调用旧 error_handler 路由。
        """
        task = get_task("error_handler")
        if task:
            handler = self.te.handlers.get(task.action.name)
            if handler:
                handler(task, task.do_action)
