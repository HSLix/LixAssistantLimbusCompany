"""Mirror Dungeons 设置页：任务次数 + 结算奖励处理 + 镜牢队伍使用顺序。"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    FluentIcon,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    isDarkTheme,
)

PAGE_ID = "mirror.settings"
PAGE_NAME = "Mirror Dungeons"
PAGE_NAMES = {"zh_CN": "镜牢", "en_US": "Mirror Dungeons"}
# 页面图标：镜牢副本探索（肉鸽玩法），使用 qfluentwidgets 的 Game 图标
PAGE_ICON = FluentIcon.GAME

# 任务 ID 必须出现在 Plan 模块级字面量 SUPPORTED_TASK_IDS 中，Dashboard 才会显示
TASKS = [
    {
        "id": "mirror",
        "name": "Mirror Dungeons",
        "show_task_count": True,
        "names": {"zh_CN": "镜牢（Mirror Dungeons）", "en_US": "Mirror Dungeons"},
    },
]

# 结算弹窗处理方式：最右 Claim（领取） / 最左 Give Up Rewards（不领取）
REWARD_MODES = (
    ("claim", "领取奖励（Claim）", "Claim rewards"),
    ("give_up", "不领取奖励（Give Up Rewards）", "Give Up Rewards (do not claim)"),
)
# 未保存过配置时默认「领取」
DEFAULT_REWARD_MODE = "claim"

# 队伍数量与「队伍配置」页一致：那边编辑每个队伍的罪人与镜牢饰品配置，这里只选使用顺序
MAX_TEAMS = 40
DEFAULT_TEAM = 1
# 新字段保存有序队伍列表（如 [3, 8, 12]）；旧字段 mirror_team 继续保存顺序里的第一个队伍，
# 工作流据此读取该队伍的镜牢饰品配置，因此旧配置和旧工作流都不需要改动
TEAMS_KEY = "mirror_teams"
TEAM_KEY = "mirror_team"
# 主页只展示有限个队伍徽章，其余折叠成一行提示，避免撑高镜牢配置主页
CHIPS_PER_ROW = 6
MAX_CHIPS = 12


def _team_name(context, team: int) -> str:
    """队伍显示名，与「队伍配置」页保持一致（队伍 1 ~ 队伍 40）。"""
    return context.translate(f"队伍 {team}", f"Team {team}")


def _team_number(value) -> int:
    """把配置里的队伍值转成 1~MAX_TEAMS 的整数，非法值返回 0。"""
    text = str(value).strip()
    if not text.isdigit():
        return 0
    team = int(text)
    return team if 1 <= team <= MAX_TEAMS else 0


def _restore_teams(config) -> list[int]:
    """读入已保存的有序队伍列表；没有新字段时退回旧的单个队伍序号。"""
    raw = config.get(TEAMS_KEY)
    teams: list[int] = []
    if isinstance(raw, list):
        for value in raw:
            team = _team_number(value)
            if team and team not in teams:
                teams.append(team)
    elif raw is None:
        team = _team_number(config.get(TEAM_KEY))
        if team:
            teams.append(team)
    return teams[:MAX_TEAMS]


def _caption_color() -> str:
    """次要文字颜色，跟随主题，避免深色/浅色主题下看不清。"""
    return "#b8a98e" if isDarkTheme() else "#6b5f4b"


def _card_style() -> str:
    """主页队伍卡片样式：浅色主题用浅底深字，深色主题用深底浅字。"""
    if isDarkTheme():
        return (
            "QFrame#mirrorTeamCard { border: 1px solid #4a4034; border-radius: 10px;"
            " background-color: #1d1712; }"
        )
    return (
        "QFrame#mirrorTeamCard { border: 1px solid #ded3bf; border-radius: 10px;"
        " background-color: #fbf7ef; }"
    )


def _chip_style() -> str:
    """已选队伍徽章样式（圆角小标签）。"""
    if isDarkTheme():
        return (
            "QLabel { background-color: #2e2618; color: #ecdfc4; border: 1px solid #5a4a33;"
            " border-radius: 11px; padding: 2px 10px; font-size: 12px; }"
        )
    return (
        "QLabel { background-color: #f0e8d8; color: #2f2619; border: 1px solid #ddceb2;"
        " border-radius: 11px; padding: 2px 10px; font-size: 12px; }"
    )


def _list_style() -> str:
    """弹窗内两个列表的样式：边框加圆角，行高略微放大，列表本身可滚动。"""
    if isDarkTheme():
        return (
            "QListWidget { border: 1px solid #4a4034; border-radius: 8px;"
            " background-color: #17130f; }"
            "QListWidget::item { padding: 5px 8px; }"
            "QListWidget::item:selected { background-color: #3a2d1a; color: #ffe9b5; }"
        )
    return (
        "QListWidget { border: 1px solid #ded3bf; border-radius: 8px;"
        " background-color: #ffffff; }"
        "QListWidget::item { padding: 5px 8px; }"
        "QListWidget::item:selected { background-color: #e9dec9; color: #2f2619; }"
    )


class TeamPickerDialog(QDialog):
    """双栏队伍选择器：左侧可用队伍（可搜索、点击勾选），右侧已选队伍（可拖拽排序）。"""

    def __init__(self, context, selected, parent=None):
        super().__init__(parent)
        self._context = context
        self._teams: list[int] = list(selected)
        self.setWindowTitle(context.translate("选择队伍", "Select teams"))
        self.setMinimumSize(760, 560)
        self._build_ui()
        self._render_available()
        for team in self._teams:
            self._append_order_item(team)
        self._sync_from_order()

    # ---------- 构建界面 ----------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)

        head = QHBoxLayout()
        title = BodyLabel(
            self._context.translate(
                "选择参与镜牢的队伍，并调整使用顺序", "Pick teams for Mirror Dungeons and set the order"
            )
        )
        head.addWidget(title, 1)
        self._counter = QLabel("")
        self._counter.setStyleSheet(f"color: {_caption_color()}; font-size: 12px;")
        head.addWidget(self._counter, 0)
        root.addLayout(head)

        columns = QHBoxLayout()
        columns.setSpacing(14)
        columns.addLayout(self._build_available_column(), 1)
        columns.addLayout(self._build_order_column(), 1)
        root.addLayout(columns, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        cancel = PushButton(self._context.translate("取消", "Cancel"))
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)
        confirm = PrimaryPushButton(self._context.translate("确定", "OK"))
        confirm.clicked.connect(self.accept)
        footer.addWidget(confirm)
        root.addLayout(footer)

    def _build_available_column(self):
        """左栏：可用队伍，搜索框 + 可滚动列表，点击行即勾选/取消。"""
        column = QVBoxLayout()
        column.setSpacing(6)
        column.addWidget(BodyLabel(self._context.translate("可用队伍", "Available teams")))
        self._search = LineEdit(self)
        self._search.setPlaceholderText(
            self._context.translate("按编号或名称搜索…", "Search by number or name…")
        )
        self._search.textChanged.connect(self._render_available)
        column.addWidget(self._search)

        self._available_list = QListWidget(self)
        self._available_list.setStyleSheet(_list_style())
        self._available_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._available_list.setMinimumHeight(360)
        self._available_list.itemClicked.connect(self._toggle_team)
        column.addWidget(self._available_list, 1)

        hint = QLabel(
            self._context.translate(
                "点击队伍即加入右侧；再次点击取消。",
                "Click a team to add it on the right; click again to remove it.",
            )
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {_caption_color()}; font-size: 12px;")
        column.addWidget(hint)
        return column

    def _build_order_column(self):
        """右栏：已选队伍，按使用顺序展示，可拖拽、上移/下移、移除或清空。"""
        column = QVBoxLayout()
        column.setSpacing(6)

        head = QHBoxLayout()
        head.addWidget(
            BodyLabel(self._context.translate("已选队伍（执行顺序）", "Selected teams (usage order)"))
        )
        head.addStretch(1)
        self._clear_button = PushButton(self._context.translate("清空", "Clear"))
        self._clear_button.clicked.connect(self._clear_all)
        head.addWidget(self._clear_button)
        column.addLayout(head)

        self._order_list = QListWidget(self)
        self._order_list.setStyleSheet(_list_style())
        self._order_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._order_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._order_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._order_list.setDropIndicatorShown(True)
        self._order_list.setMinimumHeight(360)
        self._order_list.model().rowsMoved.connect(self._on_rows_moved)
        self._order_list.currentRowChanged.connect(self._update_buttons)
        column.addWidget(self._order_list, 1)

        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        self._up_button = PushButton(self._context.translate("↑ 上移", "↑ Up"))
        self._up_button.clicked.connect(lambda: self._move_current(-1))
        buttons.addWidget(self._up_button)
        self._down_button = PushButton(self._context.translate("↓ 下移", "↓ Down"))
        self._down_button.clicked.connect(lambda: self._move_current(1))
        buttons.addWidget(self._down_button)
        self._remove_button = PushButton(self._context.translate("移除", "Remove"))
        self._remove_button.clicked.connect(self._remove_current)
        buttons.addWidget(self._remove_button)
        buttons.addStretch(1)
        column.addLayout(buttons)

        hint = QLabel(
            self._context.translate(
                "可直接拖拽调整顺序，或用上移/下移精调；移除只影响本次镜牢使用顺序。",
                "Drag to reorder, or fine-tune with Up/Down. Removing only affects this mirror run order.",
            )
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {_caption_color()}; font-size: 12px;")
        column.addWidget(hint)
        return column

    # ---------- 左栏：可用队伍 ----------
    def _available_text(self, team: int) -> str:
        """左侧一行文字：已选队伍前面带勾选标记，未选留出同样宽度。"""
        marker = "✓" if team in self._teams else "　"
        return f"{marker}  {_team_name(self._context, team)}"

    def _matches_query(self, team: int, query: str) -> bool:
        """按编号或名称匹配：纯数字按编号包含匹配，其余按中英文名称匹配。"""
        if not query:
            return True
        if query.isdigit():
            return query in str(team)
        name = _team_name(self._context, team).lower()
        return query in name or query in str(team)

    def _style_available_item(self, item: QListWidgetItem, selected: bool) -> None:
        """已选队伍加粗，配合勾选标记一起表示选中状态。"""
        font = item.font()
        font.setBold(selected)
        item.setFont(font)

    def _render_available(self, *args):
        """按搜索词重建左侧列表；搜索变化时滚动位置可以回到顶部。"""
        query = self._search.text().strip().lower()
        self._available_list.clear()
        for team in range(1, MAX_TEAMS + 1):
            if not self._matches_query(team, query):
                continue
            item = QListWidgetItem(self._available_text(team))
            item.setData(Qt.ItemDataRole.UserRole, team)
            self._style_available_item(item, team in self._teams)
            self._available_list.addItem(item)

    def _refresh_available_marks(self):
        """只刷新左侧文字的勾选标记，不重建列表，保持滚动位置。"""
        for row in range(self._available_list.count()):
            item = self._available_list.item(row)
            team = int(item.data(Qt.ItemDataRole.UserRole))
            item.setText(self._available_text(team))
            self._style_available_item(item, team in self._teams)

    def _toggle_team(self, item: QListWidgetItem):
        """点击左侧队伍：未选则追加到执行顺序末尾，已选则从右侧移除。"""
        team = int(item.data(Qt.ItemDataRole.UserRole))
        if team in self._teams:
            row = self._order_row(team)
            if row >= 0:
                self._order_list.takeItem(row)
        else:
            self._append_order_item(team)
        self._sync_from_order()

    # ---------- 右栏：已选队伍 ----------
    def _append_order_item(self, team: int):
        """把一个队伍追加到右侧列表末尾，序号由 _renumber_order 统一刷新。"""
        item = QListWidgetItem(_team_name(self._context, team))
        item.setData(Qt.ItemDataRole.UserRole, team)
        self._order_list.addItem(item)

    def _order_row(self, team: int) -> int:
        """返回队伍在右侧列表中的行号，找不到返回 -1。"""
        for row in range(self._order_list.count()):
            if int(self._order_list.item(row).data(Qt.ItemDataRole.UserRole)) == team:
                return row
        return -1

    def _renumber_order(self):
        """按当前行序刷新「1. 队伍 N」前缀。"""
        for row in range(self._order_list.count()):
            item = self._order_list.item(row)
            team = int(item.data(Qt.ItemDataRole.UserRole))
            item.setText(f"{row + 1}. {_team_name(self._context, team)}")

    def _on_rows_moved(self, *args):
        """拖拽完成后延后同步，避免在模型移动过程中改文字。"""
        QTimer.singleShot(0, self._sync_from_order)

    def _move_current(self, delta: int):
        """把当前行上移或下移一位并保持选中。"""
        row = self._order_list.currentRow()
        target = row + delta
        if row < 0 or not 0 <= target < self._order_list.count():
            return
        item = self._order_list.takeItem(row)
        self._order_list.insertItem(target, item)
        self._order_list.setCurrentRow(target)
        self._sync_from_order()

    def _remove_current(self):
        """移除右侧当前选中的队伍。"""
        row = self._order_list.currentRow()
        if row < 0:
            return
        self._order_list.takeItem(row)
        if self._order_list.count():
            self._order_list.setCurrentRow(min(row, self._order_list.count() - 1))
        self._sync_from_order()

    def _clear_all(self):
        """清空已选队伍，左侧勾选状态同步取消。"""
        if self._order_list.count() == 0:
            return
        self._order_list.clear()
        self._sync_from_order()

    def _sync_from_order(self):
        """以右侧列表的实际顺序为准，同步已选队伍、序号、计数与按钮可用状态。"""
        self._teams = [
            int(self._order_list.item(row).data(Qt.ItemDataRole.UserRole))
            for row in range(self._order_list.count())
        ]
        self._renumber_order()
        self._refresh_available_marks()
        self._counter.setText(
            self._context.translate(
                f"{len(self._teams)} / {MAX_TEAMS} 已选择", f"{len(self._teams)} / {MAX_TEAMS} selected"
            )
        )
        self._update_buttons()

    def _update_buttons(self, *args):
        """按当前行位置决定上移/下移/移除/清空是否可用。"""
        row = self._order_list.currentRow()
        count = self._order_list.count()
        self._up_button.setEnabled(row > 0)
        self._down_button.setEnabled(0 <= row < count - 1)
        self._remove_button.setEnabled(row >= 0)
        self._clear_button.setEnabled(count > 0)

    def selected_teams(self) -> list[int]:
        """返回用户确认后的有序队伍列表。"""
        return list(self._teams)


class MirrorPage(QWidget):
    """Mirror Dungeons 设置页：结算弹窗处理方式与镜牢队伍使用顺序。"""

    def __init__(self, context):
        super().__init__()
        self._context = context
        config = context.load(
            {
                "reward_mode": DEFAULT_REWARD_MODE,
                TEAM_KEY: DEFAULT_TEAM,
                TEAMS_KEY: None,
            }
        )
        self._teams = _restore_teams(config)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(
            BodyLabel(context.translate("镜牢结算奖励处理", "Mirror dungeon reward handling"))
        )
        layout.addWidget(
            BodyLabel(
                context.translate(
                    "Exploration Reward 弹窗点击哪个按钮：",
                    "Which button to click in the Exploration Reward popup:",
                )
            )
        )
        self._combo = ComboBox(self)
        for _, zh_name, en_name in REWARD_MODES:
            self._combo.addItem(context.translate(zh_name, en_name))
        self._combo.setCurrentIndex(
            self._index_of(str(config.get("reward_mode") or DEFAULT_REWARD_MODE))
        )
        layout.addWidget(self._combo)

        layout.addWidget(self._build_team_card())

        note = BodyLabel(
            context.translate(
                "饰品流派与三个饰品的点击顺序仍在「队伍配置」页按队伍编辑；"
                "此处只决定本次镜牢用哪些队伍、按什么顺序，工作流读取顺序里的第一个队伍。",
                "The gift keyword and the three-gift click order are still edited per team on the "
                "Team Presets page. This page only decides which teams are used and in what order; "
                "the workflow reads the first team of the order.",
            )
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)

        self._refresh_team_section()

    # ---------- 主页队伍卡片 ----------
    def _build_team_card(self) -> QWidget:
        """主页简要展示：已选数量、顺序徽章与「选择队伍…」入口。"""
        card = QFrame(self)
        card.setObjectName("mirrorTeamCard")
        card.setStyleSheet(_card_style())
        outer = QVBoxLayout(card)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(10)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        texts.addWidget(BodyLabel(self._context.translate("队伍使用顺序", "Team usage order")))
        self._count_label = QLabel("")
        self._count_label.setStyleSheet(f"color: {_caption_color()}; font-size: 12px;")
        texts.addWidget(self._count_label)
        head.addLayout(texts, 1)
        self._select_button = PushButton(self._context.translate("选择队伍…", "Select teams…"))
        self._select_button.clicked.connect(self._open_picker)
        head.addWidget(self._select_button, 0, Qt.AlignmentFlag.AlignTop)
        outer.addLayout(head)

        self._chips_layout = QVBoxLayout()
        self._chips_layout.setSpacing(4)
        outer.addLayout(self._chips_layout)
        return card

    def _clear_chips(self):
        """清空旧的徽章行，重新按当前选择渲染。"""
        while self._chips_layout.count():
            entry = self._chips_layout.takeAt(0)
            row = entry.layout()
            if row is not None:
                while row.count():
                    cell = row.takeAt(0)
                    widget = cell.widget()
                    if widget is not None:
                        widget.setParent(None)
                        widget.deleteLater()
                row.deleteLater()
                continue
            widget = entry.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _render_chips(self):
        """把已选队伍渲染成「序号. 队伍 N」徽章，每行若干枚，超出部分折叠成提示。"""
        self._clear_chips()
        if not self._teams:
            empty = QLabel(
                self._context.translate(
                    "（尚未选择队伍，运行时会按队伍 1 处理）",
                    "(no team selected yet; the workflow falls back to Team 1)",
                )
            )
            empty.setWordWrap(True)
            empty.setStyleSheet(f"color: {_caption_color()}; font-size: 12px;")
            self._chips_layout.addWidget(empty)
            return

        shown = self._teams[:MAX_CHIPS]
        for start in range(0, len(shown), CHIPS_PER_ROW):
            row = QHBoxLayout()
            row.setSpacing(6)
            for team in shown[start : start + CHIPS_PER_ROW]:
                order = self._teams.index(team) + 1
                chip = QLabel(f"{order}. {_team_name(self._context, team)}")
                chip.setStyleSheet(_chip_style())
                row.addWidget(chip)
            row.addStretch(1)
            self._chips_layout.addLayout(row)

        extra = len(self._teams) - len(shown)
        if extra > 0:
            tail = QLabel(
                self._context.translate(
                    f"…另有 {extra} 个队伍，点「选择队伍…」查看全部",
                    f"…and {extra} more team(s); click Select teams… to see all",
                )
            )
            tail.setWordWrap(True)
            tail.setStyleSheet(f"color: {_caption_color()}; font-size: 12px;")
            self._chips_layout.addWidget(tail)

    def _refresh_team_section(self):
        """刷新主页队伍卡片上的数量文字与顺序徽章。"""
        self._count_label.setText(
            self._context.translate(
                f"已选择 {len(self._teams)} 个队伍", f"{len(self._teams)} team(s) selected"
            )
        )
        self._render_chips()

    def _open_picker(self):
        """打开双栏选择器；只有点「确定」才写回，取消或关闭保持原配置。"""
        dialog = TeamPickerDialog(self._context, self._teams, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._teams = dialog.selected_teams()
            self._refresh_team_section()

    @staticmethod
    def _index_of(mode: str) -> int:
        """返回配置值对应的下拉序号，未知值退回默认（领取）。"""
        for index, (value, _, _) in enumerate(REWARD_MODES):
            if value == mode:
                return index
        return MirrorPage._index_of_default()

    @staticmethod
    def _index_of_default() -> int:
        """返回默认配置值对应的下拉序号。"""
        for index, (value, _, _) in enumerate(REWARD_MODES):
            if value == DEFAULT_REWARD_MODE:
                return index
        return 0

    def submit(self) -> dict:
        """提交结算弹窗处理方式、有序队伍列表，以及供工作流读取的第一个队伍。"""
        return {
            "reward_mode": REWARD_MODES[self._combo.currentIndex()][0],
            "mirror_team": self._teams[0] if self._teams else DEFAULT_TEAM,
            "mirror_teams": list(self._teams),
        }


def create_page(context):
    """返回 Mirror Dungeons 设置页实例。"""
    return MirrorPage(context)
