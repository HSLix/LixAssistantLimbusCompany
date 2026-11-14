"""Luxcavation 设置页：EXP / Thread 的执行次数任务项，以及各自使用的队伍。"""
from PySide6.QtWidgets import QApplication, QGridLayout, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, ComboBox, FluentIcon, TransparentToolButton

PAGE_ID = "luxcavation.settings"
PAGE_NAME = "Luxcavation"
PAGE_NAMES = {"zh_CN": "Luxcavation", "en_US": "Luxcavation"}
# 页面图标：进入副本开始战斗（EXP / Thread 刷取），使用 qfluentwidgets 的 Play 图标
PAGE_ICON = FluentIcon.PLAY

# 任务 ID 必须出现在 Plan 模块级字面量 SUPPORTED_TASK_IDS 中，Dashboard 才会显示
TASKS = [
    {
        "id": "exp",
        "name": "Exp",
        "show_task_count": True,
        "names": {"zh_CN": "经验（Exp）", "en_US": "Exp"},
    },
    {
        "id": "thread",
        "name": "Thread",
        "show_task_count": True,
        "names": {"zh_CN": "线（Thread）", "en_US": "Thread"},
    },
]

# 队伍数量与队伍配置页一致，选择框里放 1..MAX_TEAMS
MAX_TEAMS = 40
DEFAULT_TEAM = 1
# 队伍配置页的 PAGE_ID，同时是页面控件的 objectName，用来定位跳转目标
TEAM_PAGE_ID = "sinners.team_presets"


def _team_index(raw):
    """把保存的队伍序号规范到 1..MAX_TEAMS，非法值退回默认队伍。"""
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_TEAM
    return value if 1 <= value <= MAX_TEAMS else DEFAULT_TEAM


class LuxcavationPage(QWidget):
    """Luxcavation 设置页：EXP 与 Thread 各自使用哪个队伍，并可跳转到队伍配置。"""

    def __init__(self, context):
        super().__init__()
        self._context = context
        config = context.load({"exp_team": DEFAULT_TEAM, "thread_team": DEFAULT_TEAM})

        layout = QVBoxLayout(self)
        layout.addWidget(
            BodyLabel(
                context.translate(
                    "选择每个任务使用的队伍（点击齿轮可跳到队伍配置页面的该队伍）：",
                    "Team used by each task (click the gear to open that team in Team Presets):",
                )
            )
        )
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(10)
        self._exp_combo = self._add_team_row(
            grid, 0, "EXP", _team_index(config.get("exp_team"))
        )
        self._thread_combo = self._add_team_row(
            grid, 1, "Thread", _team_index(config.get("thread_team"))
        )
        grid.setColumnStretch(3, 1)
        layout.addLayout(grid)
        layout.addStretch(1)

    def _add_team_row(self, grid, row, title, team):
        """添加“文字标题：选择框”一行，并在后面放跳转到队伍配置的齿轮按钮。"""
        label = BodyLabel(self._context.translate(f"{title}：", f"{title}:"))
        grid.addWidget(label, row, 0)
        combo = ComboBox(self)
        for index in range(1, MAX_TEAMS + 1):
            combo.addItem(self._context.translate(f"队伍 {index}", f"Team {index}"))
        combo.setCurrentIndex(team - 1)
        combo.setMinimumWidth(150)
        grid.addWidget(combo, row, 1)
        gear = TransparentToolButton(FluentIcon.SETTING, self)
        gear.setToolTip(
            self._context.translate(
                "在队伍配置页面打开这个队伍", "Open this team in Team Presets"
            )
        )
        gear.clicked.connect(
            lambda checked=False, box=combo: self._open_team_page(box.currentIndex() + 1)
        )
        grid.addWidget(gear, row, 2)
        return combo

    def _open_team_page(self, team):
        """跳转到队伍配置页面并定位到指定队伍；该页面不可用时保持当前页面。"""
        window = self.window()
        team_page = None
        if window is not None and callable(getattr(window, "switchTo", None)):
            team_page = window.findChild(QWidget, TEAM_PAGE_ID)
        if team_page is None:
            app = QApplication.instance()
            for top in list(app.topLevelWidgets()) if app is not None else []:
                candidate = top.findChild(QWidget, TEAM_PAGE_ID)
                if candidate is not None and callable(getattr(top, "switchTo", None)):
                    window = top
                    team_page = candidate
                    break
        if team_page is None or not callable(getattr(window, "switchTo", None)):
            return
        window.switchTo(team_page)
        focus = getattr(team_page, "focus_team", None)
        if not callable(focus):
            focus = getattr(team_page, "_select_team", None)
        if callable(focus):
            focus(team - 1)

    def submit(self) -> dict:
        """提交 EXP 与 Thread 各自使用的队伍序号（从 1 开始）。"""
        return {
            "exp_team": self._exp_combo.currentIndex() + 1,
            "thread_team": self._thread_combo.currentIndex() + 1,
        }


def create_page(context):
    """返回 Luxcavation 设置页实例。"""
    return LuxcavationPage(context)
