"""窗口级手动关闭通知；浮层不占页面布局，也不持久化运行记录。"""

from datetime import datetime

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QHBoxLayout, QScrollArea, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import (BodyLabel, CardWidget, FluentIcon, PushButton, SimpleCardWidget,
                            TransparentToolButton, setCustomStyleSheet)

from .errors import result_diagnostics
from .i18n import tr


class NotificationCard(CardWidget):
    """显示一条简短结果；详情沿用可复制的原始诊断对话框。"""

    def __init__(self, message, details, kind, summary, parent):
        super().__init__(parent)
        self.message, self.details = message, details
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        heading = QHBoxLayout()
        symbol, color = {"success": ("✓", "#16844a"), "warning": ("⚠", "#b57900"),
                         "error": ("✕", "#c42b1c"), "stopped": ("■", "#777777")}.get(
                             kind, ("ⓘ", "#009faa"))
        icon = BodyLabel(symbol)
        icon.setStyleSheet(f"color: {color}; font-size: 20px;")
        heading.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        self.title_label = BodyLabel(message)
        self.title_label.setTextFormat(Qt.TextFormat.PlainText)
        self.title_label.setWordWrap(True)
        self.title_label.setMaximumHeight(self.title_label.fontMetrics().lineSpacing() * 2 + 4)
        self.title_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.title_label.setToolTip(message)
        heading.addWidget(self.title_label, 1)
        self.badge = PushButton()
        self.badge.setFixedHeight(28)
        badge_style = 'QPushButton {background: #008f93; color: white; border: none; border-radius: 14px; padding: 0 9px;}'
        setCustomStyleSheet(self.badge, badge_style, badge_style)
        self.badge.setToolTip(tr('Expand notifications'))
        self.badge.setAccessibleName(tr('Expand notifications'))
        self.badge.clicked.connect(parent.expand)
        heading.addWidget(self.badge)
        self.close_button = TransparentToolButton(FluentIcon.CLOSE)
        self.close_button.setAccessibleName(tr('Dismiss notification'))
        self.close_button.setToolTip(tr('Dismiss notification'))
        self.close_button.clicked.connect(lambda: parent.dismiss(self))
        heading.addWidget(self.close_button)
        layout.addLayout(heading)
        if summary:
            label = BodyLabel(summary)
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            label.setMaximumHeight(label.fontMetrics().lineSpacing() * 2 + 4)
            label.setToolTip(summary)
            layout.addWidget(label)
        footer = QHBoxLayout()
        self.timestamp = BodyLabel(datetime.now().strftime('%H:%M'))
        footer.addWidget(self.timestamp)
        footer.addStretch()
        if details:
            self.details_button = PushButton(tr('Details'))
            self.details_button.clicked.connect(self.show_details)
            footer.addWidget(self.details_button)
        layout.addLayout(footer)

    def show_details(self):
        from .gui import ErrorDialog
        ErrorDialog(self.message, self.details, error=False, parent=self.window()).open()


class NotificationList(SimpleCardWidget):
    """右下角只呈现最新卡片；展开后有界滚动，阅读中暂存新通知。"""

    def __init__(self, parent):
        super().__init__(parent)
        self.cards = []
        self.pending = []
        self.expanded = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        self.header = QWidget(self)
        header = QHBoxLayout(self.header)
        self.heading = BodyLabel()
        header.addWidget(self.heading, 1)
        self.clear_button = PushButton(tr('Clear all'))
        self.clear_button.clicked.connect(self.clear)
        header.addWidget(self.clear_button)
        self.collapse_button = PushButton(tr('Collapse'))
        self.collapse_button.clicked.connect(self.collapse)
        header.addWidget(self.collapse_button)
        layout.addWidget(self.header)
        self.new_button = PushButton()
        self.new_button.clicked.connect(self.reveal_pending)
        layout.addWidget(self.new_button)
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet('QScrollArea {border: none; background: transparent;}')
        content = QWidget()
        self.messages = QVBoxLayout(content)
        self.messages.setContentsMargins(0, 0, 0, 0)
        self.messages.setSpacing(6)
        self.scroll.setWidget(content)
        # 滚动内容沿用浮层底色，避免出现原生底色的边界。
        content.setAutoFillBackground(False)
        self.scroll.viewport().setAutoFillBackground(False)
        layout.addWidget(self.scroll)
        QApplication.instance().installEventFilter(self)
        self.hide()

    def _normalBackgroundColor(self):
        # 覆盖页面的浮层必须不透明，不能透出下方的文字和控件。
        return QColor('#ffffff')

    def notify(self, message: str, details: str = '', *, kind='information', summary='') -> None:
        """新结果置顶；展开阅读时先隐藏新增卡片，避免改变阅读位置。"""
        card = NotificationCard(message, details, kind, summary, self)
        self.cards.insert(0, card)
        self.messages.insertWidget(0, card)
        if self.expanded:
            self.pending.append(card)
        self.refresh()

    def notify_result(self, result):
        """保留执行结果契约，仅区分完成、失败、手动停止与异常中断的呈现。"""
        if result.get('status') == 'completed':
            if result.get('all_tasks_succeeded'):
                message, kind = tr('Execution completed'), 'success'
            else:
                message, kind = tr('Execution completed with failed tasks'), 'warning'
        elif result.get('reason') == 'user_cancelled':
            message, kind = tr('Execution stopped'), 'stopped'
        else:
            message, kind = tr('Execution interrupted'), 'error'
        self.notify(message, result_diagnostics(result), kind=kind)

    def expand(self):
        self.expanded = True
        self.reveal_pending()

    def collapse(self):
        self.expanded = False
        self.pending.clear()
        self.refresh()

    def reveal_pending(self):
        self.pending.clear()
        self.refresh()
        self.scroll.verticalScrollBar().setValue(0)

    def dismiss(self, card):
        self.cards.remove(card)
        if card in self.pending:
            self.pending.remove(card)
        self.messages.removeWidget(card)
        card.hide()
        card.deleteLater()
        self.refresh()

    def clear(self):
        """仅移除窗口内提醒，不触碰 Run 的留存数据。"""
        for card in self.cards:
            self.messages.removeWidget(card)
            card.hide()
            card.deleteLater()
        self.cards.clear()
        self.pending.clear()
        self.expanded = False
        self.refresh()

    def refresh(self):
        if not self.cards:
            self.expanded = False
            self.hide()
            return
        count = len(self.cards)
        self.heading.setText(tr('Notifications · {count}').format(count=count))
        self.header.setVisible(self.expanded)
        self.new_button.setText(tr('New notifications ({count})').format(count=len(self.pending)))
        self.new_button.setVisible(self.expanded and bool(self.pending))
        for i, card in enumerate(self.cards):
            card.setVisible((self.expanded and card not in self.pending) or (not self.expanded and i == 0))
            card.badge.setText(str(count) if count <= 99 else '99+')
            card.badge.setVisible(not self.expanded and i == 0 and count > 1)
        self.reposition()
        self.show()
        self.raise_()

    def reposition(self):
        """随窗口大小重新锚定；限高面板只在内部滚动。"""
        if not self.cards:
            return
        window = self.parentWidget()
        self.setFixedWidth(max(1, min(400, window.width() - 40)))
        self.layout().activate()
        self.messages.activate()
        height = self.messages.sizeHint().height() + 12
        if self.expanded:
            height += self.header.sizeHint().height() + self.layout().spacing()
            if self.pending:
                height += self.new_button.sizeHint().height() + self.layout().spacing()
        self.setFixedHeight(min(height, max(1, (window.height() - 60) // 2)))
        self.move(window.width() - self.width() - 20, window.height() - self.height() - 20)

    def eventFilter(self, obj, event):
        if obj is self.parentWidget() and event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self.reposition()
            self.raise_()
        if self.expanded and self.isVisible():
            if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
                if isinstance(obj, QWidget) and obj.window() is self.window():
                    self.collapse()
                    return True
            elif event.type() == QEvent.Type.MouseButtonPress:
                if not self.rect().contains(self.mapFromGlobal(event.globalPosition().toPoint())):
                    self.collapse()
        return super().eventFilter(obj, event)
