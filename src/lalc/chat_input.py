"""聊天输入框：输入法确认不发送，文本按可见行数增高。"""

import math

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QApplication
from qfluentwidgets import PlainTextEdit, setCustomStyleSheet, themeColor


class ChatInput(PlainTextEdit):
    """保留原生输入法处理，只在非组合输入的普通 Enter 时请求发送。"""

    sendRequested = Signal()
    focusChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._composing = False
        self._committed = False
        self.layer.hide()
        style = ('ChatInput, ChatInput:hover, ChatInput:focus, ChatInput:disabled '
                 '{ border: none; background: transparent; }')
        setCustomStyleSheet(self, style, style)
        self.setCursorWidth(0)
        self._caret_visible = True
        self._caret_timer = QTimer(self)
        self._caret_timer.timeout.connect(self.blink_caret)
        self.cursorPositionChanged.connect(self.reset_caret)
        self.textChanged.connect(self.reset_caret)
        self.setMinimumWidth(0)
        self.textChanged.connect(self.adjust_height)
        self.document().documentLayout().documentSizeChanged.connect(self.adjust_height)
        self.adjust_height()

    def reset_caret(self):
        """编辑或移动后立即显示光标，沿用系统闪烁周期。"""
        self._caret_visible = True
        self._caret_timer.stop()
        interval = QApplication.cursorFlashTime()
        if self.hasFocus() and interval > 0:
            self._caret_timer.start(max(1, interval // 2))
        self.viewport().update()

    def blink_caret(self):
        self._caret_visible = not self._caret_visible
        self.viewport().update()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.reset_caret()
        self.focusChanged.emit()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self._caret_timer.stop()
        self.viewport().update()
        self.focusChanged.emit()

    def paintEvent(self, event):
        """单独绘制主题色光标，不改变正文颜色或文本格式。"""
        super().paintEvent(event)
        if self.hasFocus() and not self.isReadOnly() and not self._composing and self._caret_visible:
            rect = self.cursorRect()
            rect.setWidth(3)
            painter = QPainter(self.viewport())
            painter.setClipRect(event.rect())
            painter.fillRect(rect, themeColor())

    def inputMethodEvent(self, event):
        self._composing = bool(event.preeditString())
        # 组合输入的位置与候选光标交给 Qt，避免覆盖输入法的预编辑文本。
        self.setCursorWidth(3 if self._composing else 0)
        if event.commitString():
            # 某些输入法在提交候选后还会投递同周期 Return，不能将其当作发送。
            self._committed = True
            QTimer.singleShot(0, self.clear_commit)
        super().inputMethodEvent(event)
        self.reset_caret()

    def clear_commit(self):
        self._committed = False

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._composing or self._committed:
                event.accept()
                return
            if event.modifiers() & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier):
                self.insertPlainText('\n')
                event.accept()
                return
            if event.modifiers() == Qt.KeyboardModifier.NoModifier:
                if not event.isAutoRepeat():
                    self.sendRequested.emit()
                event.accept()
                return
        super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.adjust_height()

    def adjust_height(self, *_):
        lines = self.document().documentLayout().documentSize().height()
        height = min(176, max(56, math.ceil(lines * self.fontMetrics().lineSpacing()) + 16))
        if self.height() != height:
            self.setFixedHeight(height)
