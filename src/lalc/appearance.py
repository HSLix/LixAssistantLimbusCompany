"""让原生 Qt 与 Fluent 控件共享同一有效主题。"""

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QColor, QPalette
from qfluentwidgets import Theme, qconfig, setTheme


DARK_WINDOW = "#151a21"
DARK_SURFACE = "#222a34"
DARK_ACCENT = "#9ac7e5"


class Appearance(QObject):
    """应用级主题，使用 Qt 的系统主题通知更新两个窗口及扩展页。"""

    def __init__(self, app):
        super().__init__(app)
        self.hints = app.styleHints()
        self.selection = "system"
        self.hints.colorSchemeChanged.connect(self.system_changed)

    def apply(self, selection):
        """显式主题覆盖原生外观，跟随系统时清除该覆盖。"""
        self.selection = selection
        scheme = {"system": Qt.ColorScheme.Unknown, "light": Qt.ColorScheme.Light,
                  "dark": Qt.ColorScheme.Dark}[selection]
        self.hints.setColorScheme(scheme)
        self.update_fluent(self.hints.colorScheme() if selection == "system" else scheme)

    def system_changed(self, scheme):
        if self.selection == "system":
            self.update_fluent(scheme)

    def update_fluent(self, scheme):
        app = self.parent()
        dark = scheme == Qt.ColorScheme.Dark
        palette = QPalette()
        if dark:
            palette = QPalette(QColor("#2e3845"), QColor(DARK_WINDOW))
            for role, color in {
                QPalette.ColorRole.Base: DARK_SURFACE,
                QPalette.ColorRole.AlternateBase: "#272f3a",
                QPalette.ColorRole.Link: DARK_ACCENT,
                QPalette.ColorRole.LinkVisited: "#cbb9e9",
                QPalette.ColorRole.Highlight: "#3a5870",
            }.items():
                palette.setColor(role, QColor(color))
        # 清除浅色的自定义角色，让 Qt 恢复平台当前调色板。
        app.setPalette(palette)
        theme = Theme.DARK if dark else Theme.LIGHT
        accent = QColor(DARK_ACCENT) if dark else qconfig.themeColor.defaultValue
        if qconfig.theme != theme or qconfig.get(qconfig.themeMode) != theme or qconfig.get(qconfig.themeColor) != accent:
            qconfig.set(qconfig.themeColor, accent, save=False)
            setTheme(theme)


def apply_appearance(app, selection):
    """每个 QApplication 只连接一次系统外观通知。"""
    appearance = getattr(app, "_lalc_appearance", None)
    if appearance is None:
        appearance = app._lalc_appearance = Appearance(app)
    appearance.apply(selection)
