"""聊天输入框：输入法确认不发送，文本按可见行数增高。"""

import math

from PySide6.QtCore import Qt, QTimer, Signal
from qfluentwidgets import PlainTextEdit


class ChatInput(PlainTextEdit):
    """保留原生输入法处理，只在非组合输入的普通 Enter 时请求发送。"""

    sendRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._composing = False
        self._committed = False
        self.setMinimumWidth(0)
        self.textChanged.connect(self.adjust_height)
        self.document().documentLayout().documentSizeChanged.connect(self.adjust_height)
        self.adjust_height()

    def inputMethodEvent(self, event):
        self._composing = bool(event.preeditString())
        if event.commitString():
            # 某些输入法在提交候选后还会投递同周期 Return，不能将其当作发送。
            self._committed = True
            QTimer.singleShot(0, self.clear_commit)
        super().inputMethodEvent(event)

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
