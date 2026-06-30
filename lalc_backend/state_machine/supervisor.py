"""
监督层 — 处理"模式固定、位置浮动"的操作 + 失败升级通知

解决三个问题：
  1. 浮动操作的可配置限制（最大滑动次数、刷新次数、超时）
  2. 失败统计 + 模式识别（连续失败、长时间无响应）
  3. 超过阈值时通知玩家重新配置

用法：
    from state_machine.supervisor import Supervisor, DEFAULT_CONFIGS
    
    supervisor = Supervisor(configs=DEFAULT_CONFIGS)
    
    # 在状态机引擎中：
    before_state(state_name)  → 返回是否继续
    after_state(state_name, success, duration)
    suggest_adjustment(state_name)  → 玩家提示文本
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time
import logging


class EscalationLevel(Enum):
    """升级级别——失败后的处理方式"""
    RETRY = "retry"
    """自动重试（用于瞬态错误：网络波动、加载慢）"""
    ESCALATE = "escalate"
    """通知玩家（浮动操作找不到目标，需确认配置）"""
    STOP = "stop"
    """停止流水线（严重错误）"""
    SKIP = "skip"
    """跳过此状态继续（非关键操作失败时）"""


@dataclass
class OperationLimit:
    """每种操作的容忍阈值"""
    max_attempts: int = 5
    """最大尝试次数"""
    max_scrolls: int = 6
    """最大拖拽寻找次数（EXP关卡的右滑、纽本的下滑）"""
    timeout: float = 60.0
    """单次操作超时（秒）"""
    retry_delay: float = 1.0
    """重试间隔（秒）"""

    def to_readable(self) -> str:
        return (f"尝试≤{self.max_attempts}次, "
                f"滑动≤{self.max_scrolls}次, "
                f"超时{self.timeout:.0f}s")


@dataclass
class StateRule:
    """单个状态的监督规则"""
    operation: OperationLimit = field(default_factory=OperationLimit)
    escalate_level: EscalationLevel = EscalationLevel.RETRY
    """超过阈值后的处理方式"""
    escalate_after_attempts: int = 3
    """连续失败多少次后升级"""
    escalate_after_seconds: float = 30.0
    """总耗时超过多少秒后升级"""


# ══════════════════════════════════════════════════════
# 默认配置
# ══════════════════════════════════════════════════════

DEFAULT_CONFIGS: dict[str, StateRule] = {
    # 经验本选关：向右滑动找关卡编号
    "EXP_STAGE_SELECT": StateRule(
        operation=OperationLimit(max_scrolls=6, timeout=60.0),
        escalate_level=EscalationLevel.ESCALATE,
        escalate_after_attempts=3,
        escalate_after_seconds=40.0,
    ),
    # 纽本选难度：向下滑动找难度文字
    "THREAD_STAGE_SELECT": StateRule(
        operation=OperationLimit(max_scrolls=4, timeout=45.0),
        escalate_level=EscalationLevel.ESCALATE,
        escalate_after_attempts=3,
        escalate_after_seconds=30.0,
    ),
    # 主题包选择：模板匹配 → 刷新 → 重试
    "MIRROR_THEME_SELECT": StateRule(
        operation=OperationLimit(max_attempts=4, timeout=90.0),
        escalate_level=EscalationLevel.ESCALATE,
        escalate_after_attempts=3,
        escalate_after_seconds=60.0,
    ),
    # 战斗：长时间等（但不应无限等）
    "BATTLE": StateRule(
        operation=OperationLimit(timeout=300.0),  # 5分钟
        escalate_level=EscalationLevel.ESCALATE,
        escalate_after_seconds=240.0,
    ),
    # 商店：综合操作，时间长
    "MIRROR_SHOP": StateRule(
        operation=OperationLimit(timeout=180.0),
        escalate_level=EscalationLevel.RETRY,
        escalate_after_seconds=120.0,
    ),
    # 道中节点选择：不应卡住
    "MIRROR_NODE_SELECT": StateRule(
        operation=OperationLimit(max_attempts=3, timeout=30.0),
        escalate_level=EscalationLevel.ESCALATE,
        escalate_after_attempts=2,
        escalate_after_seconds=20.0,
    ),
}


# ══════════════════════════════════════════════════════
# 统计追踪
# ══════════════════════════════════════════════════════

@dataclass
class StateStats:
    """单个状态的运行统计"""
    name: str
    enter_count: int = 0
    fail_count: int = 0
    total_duration: float = 0.0
    last_duration: float = 0.0
    consecutive_fails: int = 0
    first_enter_time: float = 0.0
    
    @property
    def avg_duration(self) -> float:
        if self.enter_count == 0:
            return 0.0
        return self.total_duration / self.enter_count
    
    @property
    def fail_rate(self) -> float:
        if self.enter_count == 0:
            return 0.0
        return self.fail_count / self.enter_count


# ══════════════════════════════════════════════════════
# 监督器
# ══════════════════════════════════════════════════════

class Supervisor:
    """监督器：监控状态执行、检测异常、升级报警。
    
    设计原则：
    - 不干预正常执行（只在异常时介入）
    - 统计驱动决策（不是凭感觉设阈值）
    - 可配置行为（给玩家留存调整空间）
    """
    
    def __init__(self, configs: Optional[dict[str, StateRule]] = None):
        self.configs = configs or DEFAULT_CONFIGS
        self.logger = logging.getLogger(__name__)
        self._stats: dict[str, StateStats] = {}
        self._escalated: set[str] = set()  # 已升级的状态（避免重复通知）
        self._callbacks: list[callable] = []  # 升级回调
        self._current_state_start: float = 0.0
        self._current_state_name: str = ""
    
    # ── 配置查询 ──
    
    def get_config(self, state_name: str) -> StateRule:
        """获取某个状态的监督规则，不存在则返回默认"""
        return self.configs.get(state_name, StateRule())
    
    def get_operation_config(self, state_name: str) -> OperationLimit:
        return self.get_config(state_name).operation
    
    # ── 状态生命周期 ──
    
    def before_state(self, state_name: str) -> bool:
        """在进入状态前调用。
        
        Returns:
            True 继续执行
            False 跳过此状态（已超过极限）
        """
        self._current_state_name = state_name
        self._current_state_start = time.time()
        
        if state_name not in self._stats:
            self._stats[state_name] = StateStats(name=state_name)
        
        stats = self._stats[state_name]
        stats.enter_count += 1
        
        # 检查：是否已升级且升级级别为 STOP
        if state_name in self._escalated:
            rule = self.get_config(state_name)
            if rule.escalate_level == EscalationLevel.STOP:
                self.logger.warning(f"[监督] {state_name} 已升级为 STOP，跳过")
                return False
        
        return True
    
    def after_state(self, state_name: str, success: bool, duration: float):
        """在状态执行后调用（无论成功与否）。"""
        stats = self._stats.get(state_name)
        if stats is None:
            return
        
        stats.last_duration = duration
        stats.total_duration += duration
        
        if not success:
            stats.fail_count += 1
            stats.consecutive_fails += 1
        else:
            stats.consecutive_fails = 0
    
    # ── 异常检测 ──
    
    def should_escalate(self, state_name: str) -> bool:
        """判断当前状态是否需要升级（通知玩家）。
        
        检查四个维度：
        1. 连续失败次数
        2. 总超时
        3. 单次超时
        4. 当前已运行时间
        """
        if state_name in self._escalated:
            return False  # 已经通知过了
        
        stats = self._stats.get(state_name)
        if stats is None:
            return False
        
        rule = self.get_config(state_name)
        now = time.time()
        elapsed = now - self._current_state_start
        
        # 1. 连续失败次数超限
        if (stats.consecutive_fails >= rule.escalate_after_attempts and
                rule.escalate_after_attempts > 0):
            return True
        
        # 2. 当前状态执行时间超限
        if elapsed >= rule.escalate_after_seconds:
            return True
        
        # 3. 单次操作超时（从 OperationLimit）
        if elapsed >= rule.operation.timeout:
            return True
        
        return False
    
    def escalate(self, state_name: str) -> str:
        """执行升级：标记已通知，返回给玩家的建议文本。"""
        self._escalated.add(state_name)
        stats = self._stats.get(state_name, StateStats(name=state_name))
        rule = self.get_config(state_name)
        
        msg = self._build_escalation_message(state_name, stats, rule)
        self.logger.warning(f"[监督升级] {msg}")
        
        # 触发注册的回调
        for cb in self._callbacks:
            try:
                cb(state_name, msg)
            except Exception as e:
                self.logger.error(f"升级回调失败: {e}")
        
        return msg
    
    def register_callback(self, callback: callable):
        """注册升级事件回调。
        
        callback 签名: callback(state_name: str, message: str)
        """
        self._callbacks.append(callback)
    
    # ── 建议文本 ──
    
    def suggest_adjustment(self, state_name: str) -> str:
        """根据失败统计，给玩家调整建议。"""
        stats = self._stats.get(state_name)
        if stats is None or stats.enter_count == 0:
            return "暂无数据"
        
        rule = self.get_config(state_name)
        msg = self._build_escalation_message(state_name, stats, rule)
        
        # 加建议
        if "EXP" in state_name:
            msg += "\n  建议：检查 exp_stage 配置是否对应已解锁的最新关卡"
        elif "THREAD" in state_name:
            msg += "\n  建议：检查 thread_stage 配置是否为当前开放的最高难度"
        elif "THEME" in state_name:
            msg += "\n  建议：检查 theme_pack 配置中的包名是否与实际匹配，或增加刷新次数"
        elif "BATTLE" in state_name:
            msg += "\n  建议：战斗可能卡住，检查网络或游戏是否响应"
        elif "NODE" in state_name:
            msg += "\n  建议：镜牢节点选择异常，检查是否已到最后一层"
        
        msg += "\n  （可修改 config 中的 OperationLimit 调整阈值）"
        return msg
    
    # ── 内部 ──
    
    def _build_escalation_message(self, state_name: str, 
                                   stats: StateStats, 
                                   rule: StateRule) -> str:
        """构造升级通知消息"""
        op = rule.operation
        return (
            f"[⚠️ 自动操作异常] {state_name}\n"
            f"  已尝试: {stats.enter_count} 次, "
            f"失败: {stats.fail_count} 次\n"
            f"  连续失败: {stats.consecutive_fails} 次\n"
            f"  阈值: {op.to_readable()}\n"
            f"  超时: {stats.last_duration:.1f}s / {op.timeout:.0f}s\n"
            f"  处理方式: {rule.escalate_level.value}"
        )
    
    def get_summary(self) -> str:
        """统计摘要（用于日志输出）"""
        parts = ["[监督统计]"]
        for name, s in sorted(self._stats.items()):
            parts.append(
                f"{name}: 进入{s.enter_count}次 "
                f"失败{s.fail_count}次 "
                f"均时{s.avg_duration:.1f}s "
                f"总时{s.total_duration:.0f}s"
            )
        return " | ".join(parts)
