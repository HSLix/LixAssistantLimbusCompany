"""
状态定义 — 游戏屏幕枚举 + 屏指纹 + UI坐标常量
"""
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional


class GameState(Enum):
    """游戏状态枚举。
    
    每个值对应一个可识别的游戏屏幕/阶段。
    """
    # ── 启动 ────────────────────────────────────────
    INIT = auto()
    """初始化：连接游戏窗口"""
    MAIN_MENU = auto()
    """主菜单（main_circle_center / touch_to_start 后）"""
    
    # ── 日常：脑啡肽 ────────────────────────────────
    ENKEPHALIN_PAGE = auto()
    """脑啡肽/驱动兑换页面"""
    ENKEPHALIN_CHECK = auto()
    """检查是否有足够的脑啡肽，准备充值"""
    ENKEPHALIN_RECHARGE = auto()
    """狂气充值脑啡肽弹窗"""
    ENKEPHALIN_MODULE = auto()
    """脑啡肽→模块兑换"""
    
    # ── 日常：Luxcavation 选关 ───────────────────────
    LUXCAVATION_PAGE = auto()
    """Luxcavation 主页面（EXP / Thread 入口）"""
    EXP_STAGE_SELECT = auto()
    """经验本选关页"""
    THREAD_STAGE_SELECT = auto()
    """纽本选关页"""
    
    # ── 队伍选择 ─────────────────────────────────────
    TEAM_SELECT = auto()
    """队伍选择页面（EXP/Thread/Mirror 通用）"""
    BATTLE_PREP = auto()
    """战斗准备页面（选人 + 开始战斗）"""
    
    # ── 战斗 ─────────────────────────────────────────
    BATTLE = auto()
    """战斗中"""
    BATTLE_RESULT = auto()
    """战斗结算（Victory / Defeat）"""
    
    # ── 镜牢 ─────────────────────────────────────────
    MIRROR_ENTRY = auto()
    """镜牢入口（inferno 按钮）"""
    MIRROR_ENTER_DUNGEON = auto()
    """进入地牢选择"""
    MIRROR_RESUME = auto()
    """继续上次镜牢"""
    MIRROR_THEME_SELECT = auto()
    """主题包选择"""
    MIRROR_STAR_SELECT = auto()
    """星光选择"""
    MIRROR_INIT_GIFT = auto()
    """初始 EGO 饰品选择"""
    MIRROR_GIFT_SEARCH = auto()
    """饰品搜索（跳过/确认）"""
    MIRROR_FLOOR_LOOP = auto()
    """镜牢楼层循环：道中"""
    MIRROR_NODE_SELECT = auto()
    """选择下一个道中节点"""
    MIRROR_EVENT = auto()
    """事件阶段"""
    MIRROR_SHOP = auto()
    """商店阶段"""
    MIRROR_SHOP_SUPER = auto()
    """豪华商店阶段"""
    MIRROR_REWARD_CARD = auto()
    """战斗后奖励卡选择"""
    MIRROR_FLOOR_GIFT = auto()
    """楼层 EGO 饰品选择"""
    MIRROR_EGO_GIFT_GET = auto()
    """获取 EGO 饰品确认"""
    MIRROR_VICTORY = auto()
    """镜牢胜利结算"""
    MIRROR_DEFEAT = auto()
    """镜牢战败结算"""
    
    # ── 通行证/奖励 ──────────────────────────────────
    REWARD_PAGE = auto()
    """奖励页面（通行证入口）"""
    PASS_MISSION = auto()
    """通行证任务页面"""
    COIN_COLLECT = auto()
    """收集金币/奖励确认"""
    
    # ── 终结 ─────────────────────────────────────────
    END = auto()
    """流水线结束"""


# ══════════════════════════════════════════════════════
# 屏指纹定义
# ══════════════════════════════════════════════════════

@dataclass
class ScreenFingerprint:
    """轻量屏指纹：只在少数关键位置采样像素值，判断当前在哪个屏。
    
    替换旧的 template_match 轮询验证（一次跑 6-8 个模板）。
    每个采样点检查 10×10 区域的均值和标准差。
    """
    name: str
    regions: list[dict] = field(default_factory=list)
    # regions = [
    #     {"x": 825, "y": 625, "w": 20, "h": 30, "mean_min": 60, "mean_max": 100},
    # ]


# 预定义屏指纹（运行时注册，这里先放定义）
SCREEN_FINGERPRINTS: dict[GameState, ScreenFingerprint] = {}


# ══════════════════════════════════════════════════════
# UI 坐标常量（1280×720 分辨率）
# ══════════════════════════════════════════════════════

UI_POSITIONS: dict[str, tuple[int, int] | list[tuple[int, int]]] = {
    # ── 主菜单 ──
    "menu.enkephalin":          (825, 634),   # 脑啡肽按钮
    "menu.mail":                (1145, 141),  # 邮件（basic.json 已验证）
    "menu.limbus_pass":         (1070, 230),  # 通行证（reward.json 已验证）
    
    # ── Luxcavation ──
    "lux.luxcavation":          (440, 160),   # 进入 luxcavation（经验/纽通用）
    "lux.skip_battle":          (750, 490),   # 扫荡按钮
    "lux.stage_first":          (640, 360),   # 默认第一个关卡
    
    # ── 镜牢入口 ──
    "mirror.enter":             (510, 310),   # 进入镜牢
    "mirror.enter_dungeon":     (510, 310),   # 进入地牢确认
    "mirror.hard_mode":         (905, 50),    # 困难/普通切换
    "mirror.theme_refresh":     (1080, 50),   # 刷新主题包
    "mirror.theme_free_refresh":(1000, 120),  # 免费刷新
    "mirror.theme_paid_refresh":(1140, 120),  # 付费刷新
    "mirror.theme_confirm_refresh":(780, 570),  # 刷新确认
    
    # ── 队伍选择 ──
    "team.slot_0": (130, 315),  "team.slot_1": (130, 355),
    "team.slot_2": (130, 390),  "team.slot_3": (130, 430),
    "team.slot_4": (130, 465),  "team.slot_5": (130, 500),
    "team.reset":               (1140, 480),  # 重置部署
    "team.start_battle":        (1140, 590),  # 开始战斗
    "team.deploy_mirror":       (1140, 590),  # 镜牢部署确认
    
    # ── 罪人坐标 ──
    "sinner.Yi Sang":    (290, 240),  "sinner.Faust":        (420, 240),
    "sinner.Don Quixote":(550, 240),  "sinner.Ryoshu":       (680, 240),
    "sinner.Meursault":  (810, 240),  "sinner.Hong Lu":      (940, 240),
    "sinner.Heathcliff": (290, 440),  "sinner.Ishmael":      (420, 440),
    "sinner.Rodion":     (550, 440),  "sinner.Sinclair":     (680, 440),
    "sinner.Outis":      (810, 440),  "sinner.Gregor":       (940, 440),
    
    # ── 脑啡肽兑换 ──
    "enkephalin.recharge_open": (630, 230),  # 打开充值弹窗
    "enkephalin.module_click":  (500, 230),  # 切换到模块兑换
    "enkephalin.module_buy":    (800, 330),  # 确认兑换
    "enkephalin.check_charge":  (390, 650),  # 检查是否需充值
    
    # ── 初始 EGO 饰品 ──
    "init_gift.slot_1":  (830, 270),  "init_gift.slot_2":  (830, 370),
    "init_gift.slot_3":  (830, 470),
    "init_gift.Burn":    (200, 250),  "init_gift.Bleed":  (350, 250),
    "init_gift.Tremor":  (500, 250),  "init_gift.Rupture": (650, 250),
    "init_gift.Sinking": (200, 450),  "init_gift.Poise":   (350, 450),
    "init_gift.Charge":  (500, 450),
    
    # ── 星光选择 ──
    "star.confirm":              (1190, 670),
    "star.enter":               (735, 535),
    
    # ── 商店 ──
    "shop.heal_all":            (200, 470),
    "shop.heal_confirm":        (1020, 330),
    "shop.heal_close":          (1120, 650),
    "shop.fuse_tab":            (280, 390),
    "shop.enhance_tab":         (160, 390),
    "shop.purchase_confirm":    (740, 480),
    "shop.purchase_confirm2":   (650, 535),
    "shop.leave":               (1120, 670),
    "shop.close_confirm":       (500, 590),
    
    # ── 商店饰品槽位 ──
    "shop.gift_r1c1":  (620, 270),  "shop.gift_r1c2":  (780, 270),
    "shop.gift_r1c3":  (940, 270),  "shop.gift_r1c4":  (1100, 270),
    "shop.gift_r2c1":  (620, 420),  "shop.gift_r2c2":  (780, 420),
    "shop.gift_r2c3":  (940, 420),  "shop.gift_r2c4":  (1100, 420),
    
    # ── 技能替换 ──
    "shop.replace_1":  (300, 330),  "shop.replace_2":  (630, 330),
    "shop.replace_3":  (960, 330),  "shop.replace_confirm":  (790, 535),
    
    # ── 关键词筛选（商店刷新） ──
    "keyword.Burn": (330, 290),   "keyword.Bleed":   (480, 290),
    "keyword.Tremor":(630, 290),  "keyword.Rupture":  (780, 290),
    "keyword.Sinking":(930, 290), "keyword.Poise":    (330, 430),
    "keyword.Charge": (480, 430), "keyword.Slash":    (630, 430),
    "keyword.Pierce": (780, 430), "keyword.Blunt":    (930, 430),
    "keyword.confirm_refresh":   (780, 570),
    "keyword.free_refresh":      (1000, 120),
    "keyword.paid_refresh":      (1140, 120),
    
    # ── 奖励卡选择 ──
    "reward_card.confirm":      (640, 530),
    "victory.decline":          (395, 550),
    
    # ── 战败 ──
    "defeat.return_lobby":      (770, 450),
    "defeat.confirm":           (650, 525),
}
