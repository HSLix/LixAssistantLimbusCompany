"""队伍配置页：仿照游戏配队页面，配置最多 40 个队伍的出战神人顺序，及每个队伍各自的镜牢配置。"""
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import BodyLabel, ComboBox, FluentIcon, isDarkTheme

PAGE_ID = "sinners.team_presets"
PAGE_NAME = "Team Presets"
PAGE_NAMES = {"zh_CN": "队伍配置", "en_US": "Team Presets"}
# 页面图标：队伍／编队主题，使用 qfluentwidgets 的 People 图标
PAGE_ICON = FluentIcon.PEOPLE

# 纯配置页：不注册任务（任务 id 还必须出现在 Plan 的 SUPPORTED_TASK_IDS 中才能执行）
TASKS = []

MAX_TEAMS = 40
TEAM_SIZE = 12
COLUMNS = 6
BOX_WIDTH = 92
BOX_HEIGHT = 124
ICON_WIDTH = 66
ICON_HEIGHT = 84

# 顺序与游戏 Sinners／配队页面中间的十二个人像框一致（左到右、上到下）
SINNERS = (
    ("yi_sang", "李箱", "Yi Sang", "assets/sinners/yi_sang.png"),
    ("faust", "浮士德", "Faust", "assets/sinners/faust.png"),
    ("don_quixote", "唐吉诃德", "Don Quixote", "assets/sinners/don_quixote.png"),
    ("ryoshu", "良秀", "Ryōshū", "assets/sinners/ryoshu.png"),
    ("meursault", "默尔索", "Meursault", "assets/sinners/meursault.png"),
    ("hong_lu", "鸿璐", "Hong Lu", "assets/sinners/hong_lu.png"),
    ("heathcliff", "希斯克利夫", "Heathcliff", "assets/sinners/heathcliff.png"),
    ("ishmael", "以实玛利", "Ishmael", "assets/sinners/ishmael.png"),
    ("rodion", "罗佳", "Rodion", "assets/sinners/rodion.png"),
    ("sinclair", "辛克莱", "Sinclair", "assets/sinners/sinclair.png"),
    ("outis", "奥提斯", "Outis", "assets/sinners/outis.png"),
    ("gregor", "格里高尔", "Gregor", "assets/sinners/gregor.png"),
)

# 镜牢配置：饰品选择页左侧的流派，第一项表示不选流派，其余值与游戏内流派标题一致
KEYWORDS = (
    ("none", "不选择流派（直接 Refuse Gift）", "No keyword (Refuse Gift)"),
    ("burn", "烧伤（Burn）", "Burn"),
    ("bleed", "流血（Bleed）", "Bleed"),
    ("tremor", "震颤（Tremor）", "Tremor"),
    ("rupture", "破裂（Rupture）", "Rupture"),
    ("sinking", "沉沦（Sinking）", "Sinking"),
    ("poise", "呼吸法（Poise）", "Poise"),
    ("charge", "充能（Charge）", "Charge"),
    ("slash", "斩击（Slash）", "Slash"),
    ("pierce", "贯穿（Pierce）", "Pierce"),
    ("blunt", "打击（Blunt）", "Blunt"),
)
# 队伍没有保存过镜牢配置时默认不选流派
DEFAULT_KEYWORD = "none"

# 右侧三行长条（上→下）模仿游戏饰品选择页右侧的三个饰品，与点击顺序一一对应
SLOT_LABELS = (
    (1, "右侧第 1 个饰品（上）", "Gift 1 (top)"),
    (2, "右侧第 2 个饰品（中）", "Gift 2 (middle)"),
    (3, "右侧第 3 个饰品（下）", "Gift 3 (bottom)"),
)
MAX_SLOTS = 3
SLOT_BOX_WIDTH = 320
SLOT_BOX_HEIGHT = 66
SLOT_BOX_STYLE = (
    "QPushButton { border: 1px solid #b08a4a; border-radius: 8px;"
    " background-color: #241d14; color: #ecdfc4; font-size: 13px;"
    " text-align: left; padding-left: 16px; }"
    "QPushButton:hover { background-color: #33281a; }"
    "QPushButton:pressed { background-color: #4a3a22; }"
)

TEAM_BUTTON_STYLE = (
    "QPushButton { border: 1px solid #5a4a33; border-radius: 4px;"
    " background-color: #1d1712; color: #d8c9ad; text-align: left;"
    " padding-left: 10px; font-size: 12px; }"
    "QPushButton:hover { background-color: #2b241a; }"
    "QPushButton:checked { border: 1px solid #d9a441; background-color: #3a2d1a;"
    " color: #ffe9b5; font-weight: bold; }"
)

SINNER_BUTTON_STYLE = (
    "QToolButton { border: 1px solid #4a4034; border-radius: 6px;"
    " background-color: #17130f; color: #cdbfa7; font-size: 11px; padding: 3px; }"
    "QToolButton:hover { border-color: #b08a4a; }"
    "QToolButton:checked { border: 2px solid #e0b34a; background-color: #33270f;"
    " color: #ffe9b5; font-weight: bold; }"
)


def _label_color():
    """按当前主题给出正文颜色：浅色主题用深色字，深色主题用浅色字，避免看不清。"""
    return "#ecdfc4" if isDarkTheme() else "#2f2619"


def _load_icon(context, relative_path):
    """按包内相对路径载入图片，缺失或读取失败时返回空图标，页面仍可用。"""
    try:
        path = context.resource_path(relative_path)
        if not path.exists():
            return QIcon()
    except Exception:
        return QIcon()
    return QIcon(str(path))


class _SlotBox(QPushButton):
    """镜牢配置里的一条饰品长条，文字显示它在点击顺序里排第几次。"""

    def __init__(self, slot: int, caption: str):
        super().__init__()
        self.slot = slot
        self._caption = caption
        self.setFixedSize(SLOT_BOX_WIDTH, SLOT_BOX_HEIGHT)
        self.setStyleSheet(SLOT_BOX_STYLE)
        self.show_order(0)

    def show_order(self, order_index: int) -> None:
        """按点击顺序刷新长条文字，order_index 为 0 表示本次不点击。"""
        if order_index <= 0:
            self.setText(f"{self._caption}　　　未使用")
        else:
            self.setText(f"{self._caption}　　　第 {order_index} 次点击")


class TeamPresetsPage(QWidget):
    """队伍配置页：左侧队伍列表、中间十二罪人方框、右侧清空选择，下方是当前队伍的镜牢配置。"""

    def __init__(self, context):
        super().__init__()
        self._context = context
        self._text_color = _label_color()
        config = context.load({"teams": [], "active_team": 0})
        self._teams, self._gift_keywords, self._gift_orders = self._restore_teams(
            config.get("teams")
        )
        self._active = self._restore_active(config.get("active_team"))
        self._team_buttons = []
        self._sinner_buttons = {}
        self._slot_boxes = {}
        self._team_scroll = None
        self._build_ui()
        self._refresh()

    # ---------- 构建界面 ----------
    def _build_ui(self):
        root = QVBoxLayout(self)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(12)
        top = QHBoxLayout()
        top.setSpacing(14)
        top.addLayout(self._build_team_column(), 0)
        top.addLayout(self._build_sinner_column(), 1)
        top.addLayout(self._build_side_column(), 0)
        body_layout.addLayout(top, 0)
        body_layout.addWidget(self._build_mirror_section(), 0)
        body_layout.addStretch(1)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

    def _build_team_column(self):
        """左侧：上下滚动的队伍列表，最多 MAX_TEAMS 个。"""
        column = QVBoxLayout()
        column.setSpacing(6)
        column.addWidget(BodyLabel(self._context.translate("队伍列表", "Teams")))
        team_scroll = QScrollArea()
        team_scroll.setWidgetResizable(True)
        team_scroll.setFixedSize(178, 344)
        team_scroll.setFrameShape(QFrame.Shape.NoFrame)
        holder = QWidget()
        holder_layout = QVBoxLayout(holder)
        holder_layout.setContentsMargins(0, 0, 6, 0)
        holder_layout.setSpacing(4)
        for index in range(MAX_TEAMS):
            button = QPushButton()
            button.setCheckable(True)
            button.setFixedHeight(30)
            button.setStyleSheet(TEAM_BUTTON_STYLE)
            button.clicked.connect(
                lambda checked=False, team_index=index: self._select_team(team_index)
            )
            self._team_buttons.append(button)
            holder_layout.addWidget(button)
        holder_layout.addStretch(1)
        team_scroll.setWidget(holder)
        self._team_scroll = team_scroll
        column.addWidget(team_scroll)
        column.addStretch(1)
        return column

    def _build_sinner_column(self):
        """中间：十二个罪人方框，选中后显示其在当前队伍里的出战顺序。"""
        column = QVBoxLayout()
        column.setSpacing(6)
        self._team_label = BodyLabel("")
        column.addWidget(self._team_label)
        holder = QWidget()
        grid = QGridLayout(holder)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(6)
        for position, (sinner_id, zh_name, en_name, resource) in enumerate(SINNERS):
            button = QToolButton()
            button.setCheckable(True)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setFixedSize(BOX_WIDTH, BOX_HEIGHT)
            button.setStyleSheet(SINNER_BUTTON_STYLE)
            button.setIconSize(QSize(ICON_WIDTH, ICON_HEIGHT))
            icon = _load_icon(self._context, resource)
            if not icon.isNull():
                button.setIcon(icon)
            button.clicked.connect(
                lambda checked=False, sinner=sinner_id: self._toggle_sinner(sinner)
            )
            self._sinner_buttons[sinner_id] = (button, zh_name, en_name)
            grid.addWidget(button, position // COLUMNS, position % COLUMNS)
        column.addWidget(holder)
        column.addStretch(1)
        return column

    def _build_side_column(self):
        """右侧：已选顺序紧接清空按钮，按钮贴着上面的列表。"""
        column = QVBoxLayout()
        column.setSpacing(6)
        column.addWidget(BodyLabel(self._context.translate("已选顺序", "Selection order")))
        self._count_label = QLabel()
        self._count_label.setStyleSheet(
            f"color: {self._text_color}; font-size: 12px;"
        )
        column.addWidget(self._count_label)
        self._order_label = QLabel()
        self._order_label.setWordWrap(True)
        self._order_label.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self._order_label.setFixedWidth(150)
        self._order_label.setStyleSheet(
            f"color: {self._text_color}; font-size: 13px;"
        )
        column.addWidget(self._order_label)
        self._clear_button = QPushButton(
            self._context.translate("清空选择", "Clear selection")
        )
        self._clear_button.setFixedWidth(150)
        self._clear_button.clicked.connect(self._clear_selection)
        column.addWidget(self._clear_button)
        column.addStretch(1)
        return column

    def _build_mirror_section(self):
        """下方「镜牢配置」区域：当前队伍的初始 E.G.O 饰品流派与三个饰品的点击顺序。"""
        section = QWidget()
        outer = QVBoxLayout(section)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)
        outer.addWidget(
            BodyLabel(
                self._context.translate(
                    "镜牢配置（当前队伍）：初始 E.G.O 饰品", "Mirror config (current team): initial E.G.O gifts"
                )
            )
        )

        row = QHBoxLayout()
        row.setSpacing(14)
        left_layout = QVBoxLayout()
        left_layout.setSpacing(6)
        left_layout.addWidget(
            BodyLabel(
                self._context.translate(
                    "饰品选择：左侧要点的流派", "Gift selection: keyword on the left"
                )
            )
        )
        self._keyword_combo = ComboBox(section)
        for _, zh_name, en_name in KEYWORDS:
            self._keyword_combo.addItem(self._context.translate(zh_name, en_name))
        self._keyword_combo.setMinimumWidth(230)
        self._keyword_combo.setFixedWidth(230)
        self._keyword_combo.currentIndexChanged.connect(self._keyword_changed)
        left_layout.addWidget(self._keyword_combo)
        hint = QLabel(
            self._context.translate(
                "右侧三个饰品按点击先后顺序点击长条记录（再点一次取消）。\n"
                "顺序为空或流派为「不选择流派」时，工作流直接点 Refuse Gift。",
                "Click the bars on the right in the wanted order (click again to cancel).\n"
                "An empty order or the no-keyword option means the workflow clicks Refuse Gift.",
            )
        )
        hint.setWordWrap(True)
        hint.setFixedWidth(360)
        hint.setStyleSheet(f"color: {self._text_color}; font-size: 12px;")
        left_layout.addWidget(hint)
        left_layout.addStretch(1)
        row.addLayout(left_layout, 1)

        right_layout = QVBoxLayout()
        right_layout.setSpacing(6)
        right_layout.addWidget(
            BodyLabel(
                self._context.translate(
                    "右侧三个饰品的点击顺序", "Click order of the three gifts on the right"
                )
            )
        )
        for slot, zh_name, en_name in SLOT_LABELS:
            box = _SlotBox(slot, self._context.translate(zh_name, en_name))
            box.clicked.connect(lambda checked=False, index=slot: self._toggle_slot(index))
            self._slot_boxes[slot] = box
            right_layout.addWidget(box)
        self._clear_order_button = QPushButton(
            self._context.translate("清空点击顺序", "Clear click order")
        )
        self._clear_order_button.setFixedWidth(SLOT_BOX_WIDTH)
        self._clear_order_button.clicked.connect(self._clear_order)
        right_layout.addWidget(self._clear_order_button)
        right_layout.addStretch(1)
        row.addLayout(right_layout, 0)

        outer.addLayout(row)
        return section

    # ---------- 状态处理 ----------
    def _restore_teams(self, raw):
        """读入已保存的队伍配置，返回罪人顺序、镜牢饰品流派与点击顺序三组数据。

        兼容旧格式（每个队伍只有罪人列表）与新格式（每项是含 sinners、gift_keyword、
        gift_slot_order 的字典），未知或重复的罪人忽略，队伍与配置都补齐到 MAX_TEAMS 个。
        """
        known = [sinner[0] for sinner in SINNERS]
        teams = []
        keywords = []
        orders = []
        if isinstance(raw, list):
            for entry in raw[:MAX_TEAMS]:
                sinners = entry.get("sinners") if isinstance(entry, dict) else entry
                team = []
                if isinstance(sinners, list):
                    for value in sinners:
                        sinner_id = str(value).strip()
                        if sinner_id in known and sinner_id not in team:
                            team.append(sinner_id)
                teams.append(team[:TEAM_SIZE])
                keywords.append(self._restore_keyword(entry))
                orders.append(self._restore_order(entry))
        while len(teams) < MAX_TEAMS:
            teams.append([])
            keywords.append(DEFAULT_KEYWORD)
            orders.append([])
        return teams, keywords, orders

    @staticmethod
    def _restore_keyword(entry) -> str:
        """读入一个队伍保存的镜牢饰品流派，未知值退回不选流派。"""
        if not isinstance(entry, dict):
            return DEFAULT_KEYWORD
        keyword = str(entry.get("gift_keyword") or DEFAULT_KEYWORD).strip().lower()
        if keyword not in [value for value, _, _ in KEYWORDS]:
            return DEFAULT_KEYWORD
        return keyword

    @staticmethod
    def _restore_order(entry) -> list[int]:
        """读入一个队伍保存的饰品点击顺序，忽略非法或重复的序号。"""
        if not isinstance(entry, dict):
            return []
        order: list[int] = []
        raw = entry.get("gift_slot_order")
        if isinstance(raw, list):
            for value in raw:
                text = str(value).strip()
                if not text.isdigit():
                    continue
                slot = int(text)
                if 1 <= slot <= MAX_SLOTS and slot not in order:
                    order.append(slot)
        return order[:MAX_SLOTS]

    @staticmethod
    def _restore_active(raw):
        """读入上次编辑的队伍序号，超出范围时回到第一个队伍。"""
        try:
            index = int(raw)
        except (TypeError, ValueError):
            return 0
        if 0 <= index < MAX_TEAMS:
            return index
        return 0

    def _team_title(self, index):
        """队伍在界面上的显示名。"""
        return self._context.translate(f"队伍 {index + 1}", f"Team {index + 1}")

    def _select_team(self, index):
        """切换正在编辑的队伍。"""
        if 0 <= index < MAX_TEAMS:
            self._active = index
            self._refresh()

    def focus_team(self, index):
        """外部页面跳转时定位到指定队伍：选中它并把左侧列表滚动到可见位置。

        index 从 0 开始，越界时保持当前队伍不变，便于其它页面按需调用。
        """
        try:
            value = int(index)
        except (TypeError, ValueError):
            return
        if not 0 <= value < MAX_TEAMS:
            return
        self._select_team(value)
        if self._team_scroll is not None:
            self._team_scroll.ensureWidgetVisible(self._team_buttons[value], 0, 0)

    def _toggle_sinner(self, sinner_id):
        """点击罪人方框：未选中时排到当前队伍最后，已选中时取消并保持其余顺序。"""
        team = self._teams[self._active]
        if sinner_id in team:
            team.remove(sinner_id)
        else:
            team.append(sinner_id)
        self._refresh()

    def _clear_selection(self):
        """清空当前队伍已选的罪人。"""
        self._teams[self._active] = []
        self._refresh()

    def _keyword_changed(self, index):
        """流派下拉变化时写入当前队伍的镜牢配置。"""
        if 0 <= index < len(KEYWORDS):
            self._gift_keywords[self._active] = KEYWORDS[index][0]

    def _keyword_index(self, keyword):
        """返回流派配置值对应的下拉序号，未知值退回不选流派。"""
        for index, (value, _, _) in enumerate(KEYWORDS):
            if value == keyword:
                return index
        return 0

    def _toggle_slot(self, slot):
        """点击长条：未参与时排到当前队伍点击顺序末尾，已参与时移出并重新编号。"""
        order = self._gift_orders[self._active]
        if slot in order:
            order.remove(slot)
        else:
            order.append(slot)
        self._refresh_mirror()

    def _clear_order(self):
        """清空当前队伍的饰品点击顺序。"""
        self._gift_orders[self._active] = []
        self._refresh_mirror()

    def _refresh_mirror(self):
        """把当前队伍的镜牢配置同步到流派下拉与三行长条。"""
        self._keyword_combo.blockSignals(True)
        self._keyword_combo.setCurrentIndex(
            self._keyword_index(self._gift_keywords[self._active])
        )
        self._keyword_combo.blockSignals(False)
        order = self._gift_orders[self._active]
        for slot, box in self._slot_boxes.items():
            index = order.index(slot) + 1 if slot in order else 0
            box.show_order(index)

    def _order_text(self, team):
        """右侧顺序摘要文本。"""
        if not team:
            return self._context.translate("（未选择任何罪人）", "(no sinner selected)")
        lines = []
        for position, sinner_id in enumerate(team, start=1):
            _, zh_name, en_name = self._sinner_buttons[sinner_id]
            lines.append(f"{position}. {self._context.translate(zh_name, en_name)}")
        return "\n".join(lines)

    def _refresh(self):
        """按当前状态刷新队伍列表、罪人方框、右侧顺序摘要和镜牢配置。"""
        team = self._teams[self._active]
        for index, button in enumerate(self._team_buttons):
            name = self._team_title(index)
            count = len(self._teams[index])
            button.setText(
                self._context.translate(
                    f"{name}　{count}/{TEAM_SIZE}",
                    f"{name}  {count}/{TEAM_SIZE}",
                )
            )
            button.setChecked(index == self._active)

        active_name = self._team_title(self._active)
        self._team_label.setText(
            self._context.translate(
                f"正在编辑：{active_name}", f"Editing: {active_name}"
            )
        )

        for sinner_id, (button, zh_name, en_name) in self._sinner_buttons.items():
            title = self._context.translate(zh_name, en_name)
            if sinner_id in team:
                button.setText(f"{team.index(sinner_id) + 1}. {title}")
                button.setChecked(True)
            else:
                button.setText(title)
                button.setChecked(False)

        self._count_label.setText(
            self._context.translate(
                f"已选 {len(team)} / {TEAM_SIZE}", f"{len(team)} / {TEAM_SIZE} selected"
            )
        )
        self._order_label.setText(self._order_text(team))
        self._refresh_mirror()

    def submit(self) -> dict:
        """提交 40 个队伍的出战顺序、各自的镜牢配置与当前编辑队伍。"""
        return {
            "teams": [
                {
                    "sinners": list(team),
                    "gift_keyword": self._gift_keywords[index],
                    "gift_slot_order": list(self._gift_orders[index]),
                }
                for index, team in enumerate(self._teams)
            ],
            "active_team": self._active,
        }


def create_page(context):
    """返回队伍配置页实例。"""
    return TeamPresetsPage(context)
