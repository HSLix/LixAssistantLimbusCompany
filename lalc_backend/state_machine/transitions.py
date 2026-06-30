"""
状态转换引擎 — 确定性的状态机驱动

用转换表驱动流水线，替换旧 error_handler / circle_center 轮询。
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable, Any, Union
import time
import logging

from .states import GameState, UI_POSITIONS


# ══════════════════════════════════════════════════════
# 动作类型
# ══════════════════════════════════════════════════════

class ActionType(Enum):
    CLICK = "click"
    """点击固定坐标"""
    KEY = "key"
    """键盘按键"""
    SLEEP = "sleep"
    """等待指定秒数"""
    HANDLER = "handler"
    """调用已有的 @register handler"""
    VERIFY = "verify"
    """轻量验证（屏指纹）"""
    TEMPLATE = "template_match"
    """模板匹配验证（fallback）"""
    SWIPE = "swipe"
    """滑动"""
    SEQUENCE = "sequence"
    """依次执行多个子动作"""
    SCROLL_RIGHT = "scroll_right"
    """向右滑到底（经验本选关），帧差异检测尾部"""
    SCROLL_DOWN = "scroll_down"
    """向下滑到底（纽本选难度），帧差异检测尾部"""


@dataclass
class Action:
    """一个原子操作"""
    type: ActionType
    params: dict = field(default_factory=dict)
    desc: str = ""
    
    @classmethod
    def click(cls, pos_key: str, desc: str = ""):
        """从 UI_POSITIONS 取坐标点击"""
        return cls(ActionType.CLICK, {"pos_key": pos_key}, desc)
    
    @classmethod
    def click_xy(cls, x: int, y: int, desc: str = ""):
        """直接指定坐标点击"""
        return cls(ActionType.CLICK, {"x": x, "y": y}, desc)
    
    @classmethod
    def key(cls, key: str, desc: str = ""):
        return cls(ActionType.KEY, {"key": key}, desc)
    
    @classmethod
    def sleep(cls, seconds: float, desc: str = ""):
        return cls(ActionType.SLEEP, {"seconds": seconds}, desc)
    
    @classmethod
    def handler(cls, name: str, desc: str = ""):
        """调用已注册的 @TaskExecution.register(name) handler"""
        return cls(ActionType.HANDLER, {"handler_name": name}, desc)
    
    @classmethod
    def swipe(cls, x1: int, y1: int, x2: int, y2: int, desc: str = ""):
        return cls(ActionType.SWIPE, {"x1": x1, "y1": y1, "x2": x2, "y2": y2}, desc)
    
    @classmethod
    def sequence(cls, actions: list["Action"], desc: str = ""):
        return cls(ActionType.SEQUENCE, {"actions": actions}, desc)
    
    @classmethod
    def scroll_right(cls, desc: str = "向右滑到底"):
        """向右滑到底（经验本选关），帧差异检测尾部"""
        return cls(ActionType.SCROLL_RIGHT, {
            "direction": "right",
            "swipe_start": [940, 310],
            "swipe_end": [590, 310],
            "max_swipes": 8,
            "diff_threshold": 5.0,
            "click_after": None,  # 滑动后点击的位置 (x, y)，None=不点
        }, desc)
    
    @classmethod
    def scroll_down(cls, desc: str = "向下滑到底"):
        """向下滑到底（纽本选难度），帧差异检测尾部"""
        return cls(ActionType.SCROLL_DOWN, {
            "direction": "down",
            "swipe_start": [650, 430],
            "swipe_end": [650, 325],
            "max_swipes": 6,
            "diff_threshold": 5.0,
            "click_after": None,
        }, desc)


# ══════════════════════════════════════════════════════
# 转换定义
# ══════════════════════════════════════════════════════

@dataclass
class Transition:
    """一条状态转换规则"""
    from_state: GameState
    to_state: GameState
    action: Action
    timeout: float = 30.0
    """此动作的最大等待时间（秒）"""
    retry_on_error: bool = True
    """失败时是否重试"""
    max_retries: int = 3
    """最大重试次数"""
    verify_template: Optional[str] = None
    """可选：用模板匹配验证到达目标状态"""


# ══════════════════════════════════════════════════════
# 日常流水线转换表
# ══════════════════════════════════════════════════════
# 这是核心！定义了一次日常 + 镜牢的确定性流程。
# 引擎按此表格逐条执行，不再轮询。

def build_daily_flow(check_config: dict) -> list[Transition]:
    """根据配置构建当次运行的转换表。
    
    check_config 包含每个任务的执行次数：
    {
        "exp_count": 0..N,
        "thread_count": 0..N,
        "mirror_count": 0..N,
    }
    """
    flow = []
    
    # ── 启动 ──
    flow.append(Transition(
        GameState.INIT, GameState.MAIN_MENU,
        Action.handler("init_limbus_window", "初始化游戏窗口"),
        timeout=60.0,
    ))
    
    # ── 脑啡肽流程 ──
    flow.extend(_build_enkephalin_flow())
    
    # ── EXP 本 ──
    if check_config.get("exp_count", 0) > 0:
        flow.extend(_build_luxcavation_flow("exp"))
    
    # ── 纽本 ──
    if check_config.get("thread_count", 0) > 0:
        flow.extend(_build_luxcavation_flow("thread"))
    
    # ── 镜牢 ──
    mirror_count = check_config.get("mirror_count", 0)
    if mirror_count > 0:
        flow.extend(_build_mirror_entry_flow())
        # 首次进入第一个节点
        flow.append(Transition(
            GameState.MIRROR_GIFT_SEARCH, GameState.MIRROR_NODE_SELECT,
            Action.handler("mirror_select_next_node", "选择第一个道中节点"),
            timeout=20.0,
        ))
        # 每层流程（自动循环回 MIRROR_NODE_SELECT）
        single_floor = _build_mirror_floor_flow()
        for i in range(mirror_count):
            flow.extend(single_floor)
        # 最后一层末端：去掉循环边（MIRROR_EGO_GIFT_GET→MIRROR_NODE_SELECT）
        # 改为桥接到胜利结算
        last_t = flow[-1]
        if last_t.from_state == GameState.MIRROR_EGO_GIFT_GET and last_t.to_state == GameState.MIRROR_NODE_SELECT:
            flow[-1] = Transition(
                GameState.MIRROR_EGO_GIFT_GET, GameState.MIRROR_VICTORY,
                Action.sleep(3, "等待 victory 结算出现"),
                timeout=10.0,
            )
        # 胜利结算流程
        flow.extend(_build_mirror_victory_flow())
    
    # ── 奖励 ──
    flow.extend(_build_reward_flow())
    
    # ── 结束 ──
    flow.append(Transition(
        _last_state(flow), GameState.END,
        Action(ActionType.SLEEP, {"seconds": 0}),
    ))
    
    return flow


def _build_enkephalin_flow() -> list[Transition]:
    """脑啡肽：主菜单 → 兑换 → 充值（可选）→ 模块"""
    return [
        Transition(GameState.MAIN_MENU, GameState.ENKEPHALIN_PAGE,
                   Action.click("menu.enkephalin", "主菜单→脑啡肽页"),
                   timeout=5.0),
        Transition(GameState.ENKEPHALIN_PAGE, GameState.ENKEPHALIN_CHECK,
                   Action.click("enkephalin.check_charge", "检查是否需要充值"),
                   timeout=3.0),
        Transition(GameState.ENKEPHALIN_CHECK, GameState.ENKEPHALIN_RECHARGE,
                   Action.handler("recharge_enkephalin", "狂气充值脑啡肽"),
                   timeout=60.0, retry_on_error=False),  # OCR 在里面做
        Transition(GameState.ENKEPHALIN_RECHARGE, GameState.ENKEPHALIN_MODULE,
                   Action.handler("get_enkephalin_module", "脑啡肽→模块兑换"),
                   timeout=15.0),
        Transition(GameState.ENKEPHALIN_MODULE, GameState.MAIN_MENU,
                   Action.key("esc", "回主菜单"),
                   timeout=3.0),
    ]


def _build_luxcavation_flow(dungeon_type: str) -> list[Transition]:
    """EXP 或 Thread 本：从主菜单进入 → 扫荡/战斗 → 回到主菜单
    
    选关方式：
      - EXP：向右滑到底（帧差异检测），点击最后一个关卡的"进入"
      - Thread：点击今日副本 → 向下滑到底（帧差异检测），点击最高难度
    """
    is_exp = dungeon_type == "exp"
    stage_name = "经验" if is_exp else "纽"
    
    flow = [
        # 主菜单 → luxcavation 页
        Transition(GameState.MAIN_MENU, GameState.LUXCAVATION_PAGE,
                   Action.click("lux.luxcavation", f"主菜单→luxcavation（{stage_name}）"),
                   timeout=5.0),
    ]
    
    if is_exp:
        # EXP：向右滑到底 → 点击最后一个关卡
        flow.append(Transition(
            GameState.LUXCAVATION_PAGE, GameState.EXP_STAGE_SELECT,
            Action.scroll_right("EXP 向右滑到底选最后一个关卡"),
            timeout=30.0,
        ))
        # 然后走队伍选择（复用旧 handler 的坐标逻辑）
        flow.append(Transition(
            GameState.EXP_STAGE_SELECT, GameState.TEAM_SELECT,
            Action.click_xy(440, 480, "点击最后一个关卡的进入按钮"),
            timeout=5.0,
        ))
    else:
        # Thread：先点今日副本 → 向下滑到底
        flow.append(Transition(
            GameState.LUXCAVATION_PAGE, GameState.THREAD_STAGE_SELECT,
            Action.click("lux.stage_first", "点击今日副本入口"),
            timeout=5.0,
        ))
        flow.append(Transition(
            GameState.THREAD_STAGE_SELECT, GameState.TEAM_SELECT,
            Action.scroll_down("纽本向下滑到底选最高难度"),
            timeout=25.0,
        ))
    
    # 队伍选择 + 战斗准备 + 战斗 + 结算
    flow.extend([
        Transition(GameState.TEAM_SELECT, GameState.BATTLE_PREP,
                   Action.handler(f"{dungeon_type}_ready_to_battle", f"{stage_name}战斗准备"),
                   timeout=15.0),
        Transition(GameState.BATTLE_PREP, GameState.BATTLE,
                   Action.handler(f"{dungeon_type}_battle", f"{stage_name}战斗"),
                   timeout=120.0),
        Transition(GameState.BATTLE, GameState.BATTLE_RESULT,
                   Action.handler("wait_disappear", "等待战斗结束"),
                   timeout=120.0),
        Transition(GameState.BATTLE_RESULT, GameState.MAIN_MENU,
                   Action.handler(f"{dungeon_type}_victory", f"{stage_name}结算"),
                   timeout=10.0),
    ])
    
    return flow


def _build_mirror_entry_flow() -> list[Transition]:
    """镜牢入口：主菜单 → 主题/星光/初始饰品选择"""
    return [
        Transition(GameState.MAIN_MENU, GameState.MIRROR_ENTRY,
                   Action.click("mirror.enter", "主菜单→镜牢入口"),
                   timeout=5.0),
        Transition(GameState.MIRROR_ENTRY, GameState.MIRROR_ENTER_DUNGEON,
                   Action.click("mirror.enter_dungeon", "进入地牢"),
                   timeout=10.0),
        Transition(GameState.MIRROR_ENTER_DUNGEON, GameState.MIRROR_THEME_SELECT,
                   Action.handler("mirror_select_theme_pack", "选择主题包"),
                   timeout=30.0),
        Transition(GameState.MIRROR_THEME_SELECT, GameState.MIRROR_STAR_SELECT,
                   Action.handler("mirror_choose_star", "选择星光"),
                   timeout=15.0),
        Transition(GameState.MIRROR_STAR_SELECT, GameState.MIRROR_INIT_GIFT,
                   Action.handler("mirror_select_initial_ego_gift", "选择初始饰品"),
                   timeout=20.0),
        Transition(GameState.MIRROR_INIT_GIFT, GameState.MIRROR_GIFT_SEARCH,
                   Action.handler("mirror_gift_search", "跳过/确认饰品搜索"),
                   timeout=10.0),
    ]


def _build_mirror_floor_flow() -> list[Transition]:
    """镜牢单层流程：从 MIRROR_NODE_SELECT 开始，到 MIRROR_EGO_GIFT_GET 结束。
    
    不含"回到节点选择"的循环边——循环由外层 build_daily_flow 处理。
    这样做的好处：单层流程本身是线性的，N 层直接拼接。
    """
    return [
        Transition(GameState.MIRROR_NODE_SELECT, GameState.MIRROR_EVENT,
                   Action.handler("event_loop", "处理事件"),
                   verify_template="event_skip",
                   timeout=60.0),
        Transition(GameState.MIRROR_EVENT, GameState.MIRROR_SHOP,
                   Action.handler("mirror_shop_entry", "进入商店"),
                   verify_template="mirror_shop",
                   timeout=5.0),
        Transition(GameState.MIRROR_SHOP, GameState.MIRROR_REWARD_CARD,
                   Action.sequence([
                       Action.handler("mirror_shop_heal_sinner", "商店治疗"),
                       Action.handler("mirror_shop_fuse_ego_gifts", "饰品融合"),
                       Action.handler("mirror_shop_replace_skill_and_purchase_ego_gifts", "购买+替换"),
                       Action.handler("mirror_shop_enhance_ego_gifts", "饰品强化"),
                       Action.key("enter", "离开商店确认"),
                   ], "商店完整流程"),
                   timeout=120.0),
        Transition(GameState.MIRROR_REWARD_CARD, GameState.MIRROR_FLOOR_GIFT,
                   Action.handler("mirror_select_encounter_reward_card", "奖励卡选择"),
                   timeout=15.0),
        Transition(GameState.MIRROR_FLOOR_GIFT, GameState.MIRROR_EGO_GIFT_GET,
                   Action.handler("mirror_select_floor_ego_gift", "楼层饰品选择"),
                   timeout=15.0),
        Transition(GameState.MIRROR_EGO_GIFT_GET, GameState.MIRROR_NODE_SELECT,
                   Action.click("reward_card.confirm", "确认饰品获取，继续下一层"),
                   timeout=5.0),
    ]


def _build_mirror_victory_flow() -> list[Transition]:
    """镜牢胜利结算"""
    return [
        Transition(GameState.MIRROR_VICTORY, GameState.MAIN_MENU,
                   Action.handler("mirror_victory", "镜牢胜利结算"),
                   timeout=30.0),
        Transition(GameState.MAIN_MENU, GameState.MAIN_MENU,
                   Action.handler("mirror_check", "镜牢完成检查"),
                   timeout=5.0),
    ]


def _build_reward_flow() -> list[Transition]:
    """通行证奖励收集"""
    return [
        Transition(GameState.MAIN_MENU, GameState.REWARD_PAGE,
                   Action.click("menu.limbus_pass", "主菜单→通行证"),
                   timeout=5.0),
        Transition(GameState.REWARD_PAGE, GameState.PASS_MISSION,
                   Action.handler("confirm_all_coins", "收集奖励硬币"),
                   timeout=30.0),
        Transition(GameState.PASS_MISSION, GameState.MAIN_MENU,
                   Action.key("esc", "回主菜单"),
                   timeout=5.0),
    ]


def _last_state(flow: list[Transition]) -> GameState:
    """取转换表中最后一个状态的 to_state"""
    return flow[-1].to_state if flow else GameState.INIT
