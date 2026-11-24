"""Agent 新会话的来源 Manifest 下拉搜索。"""

import re
from html import escape

from PySide6.QtCore import QEvent, QPoint, QPointF, QSignalBlocker, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QTextCharFormat, QTextLayout
from PySide6.QtWidgets import QListWidgetItem, QVBoxLayout
from qfluentwidgets import (
    BodyLabel, ComboBox, Flyout, FlyoutViewBase, ListItemDelegate, ListWidget,
    SearchLineEdit, getFont, isDarkTheme,
)

from .i18n import tr


ROW_HEIGHT = 50
INDEX_ROLE = Qt.ItemDataRole.UserRole
NOTES_ROLE = Qt.ItemDataRole.UserRole + 1


class ManifestResultDelegate(ListItemDelegate):
    """复用列表的选中样式，分别绘制版本说明和 UUID 的匹配片段。"""

    def __init__(self, view):
        super().__init__(view)
        self.pattern = None

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.text = ''

    def sizeHint(self, option, index):
        return QSize(0, ROW_HEIGHT)

    def paint(self, painter, option, index):
        rect = option.rect.adjusted(12, 0, -12, 0)
        super().paint(painter, option, index)
        notes = index.data(NOTES_ROLE)
        identity = index.data(Qt.ItemDataRole.DisplayRole)
        dark = isDarkTheme()
        primary = QColor('#f5f5f5' if dark else '#242424')
        secondary = QColor('#bcbcbc' if dark else '#5d5d5d')
        painter.save()
        painter.setClipRect(rect)
        if notes:
            self.draw_line(painter, rect, notes, getFont(14), primary, rect.top() + 6)
            self.draw_line(painter, rect, identity, getFont(12), secondary, rect.top() + 26)
        else:
            font = getFont(14)
            y = rect.top() + (rect.height() - QFontMetrics(font).height()) / 2
            self.draw_line(painter, rect, identity, font, primary, y)
        painter.restore()

    def draw_line(self, painter, rect, text, font, color, y):
        metrics = QFontMetrics(font)
        match = self.pattern.search(text) if self.pattern else None
        visible = metrics.elidedText(text, Qt.TextElideMode.ElideRight, rect.width())
        prefix = ''
        if match and visible != text and match.end() > len(visible.removesuffix('…')):
            # 长说明从命中处起展示，避免筛选出一行却看不到它为什么命中。
            prefix = '…' if match.start() else ''
            text = prefix + text[match.start():]
            visible = metrics.elidedText(text, Qt.TextElideMode.ElideRight, rect.width())
        layout = QTextLayout(visible, font)
        matches = []
        if self.pattern:
            style = QTextCharFormat()
            style.setBackground(QColor('#6a501a' if isDarkTheme() else '#ffeeb4'))
            style.setForeground(QColor('#fff2c7' if isDarkTheme() else '#4a3400'))
            end = len(visible if visible == text else visible.removesuffix('…'))
            for match in self.pattern.finditer(visible, len(prefix), end):
                span = QTextLayout.FormatRange()
                # Qt 的文本位置按 UTF-16 计算，发布说明可以含 emoji。
                span.start = len(visible[:match.start()].encode('utf-16-le')) // 2
                span.length = len(match[0].encode('utf-16-le')) // 2
                span.format = style
                matches.append(span)
        layout.setFormats(matches)
        layout.beginLayout()
        layout.createLine().setLineWidth(rect.width())
        layout.endLayout()
        painter.setPen(color)
        layout.draw(painter, QPointF(rect.left(), y))


class ManifestSourceBox(ComboBox):
    """保留 ComboBox 的来源选择，搜索只控制弹层中显示的版本。"""

    def __init__(self):
        super().__init__()
        self.notes = {}
        self.setAccessibleName(tr('Source Manifest'))
        self.panel = FlyoutViewBase()
        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(10, 10, 10, 8)
        layout.setSpacing(5)
        self.search = SearchLineEdit()
        self.search.setPlaceholderText(tr('Search Manifests'))
        self.search.setAccessibleName(tr('Search Manifests'))
        self.search.installEventFilter(self)
        self.results = ListWidget()
        self.results.setAccessibleName(tr('Source Manifest'))
        self.results.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.results.installEventFilter(self)
        self.delegate = ManifestResultDelegate(self.results)
        self.results.setItemDelegate(self.delegate)
        self.empty = BodyLabel(tr('No matching Manifests'))
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setFixedHeight(ROW_HEIGHT)
        for widget in (self.search, self.results, self.empty):
            layout.addWidget(widget)
        self.popup = Flyout(self.panel, self, isDeleteOnClose=False)
        self.popup.installEventFilter(self)
        self.search.textChanged.connect(self.filter_results)
        self.search.returnPressed.connect(lambda: self.choose(self.results.currentItem()))
        self.results.itemClicked.connect(self.choose)
        self.results.itemActivated.connect(self.choose)

    def set_manifests(self, values):
        """刷新下拉数据并按 UUID 找回已有来源。"""
        previous = self.currentData()
        active = self.results.currentItem() if self.popup.isVisible() else None
        focused_text = active.text() if active else None
        placeholder = self.itemText(0) if self.count() else tr('Select a published Manifest')
        self.notes = {value['manifest_id']: value.get('AdditionalMessage', '') for value in values}
        with QSignalBlocker(self):
            self.clear()
            self.addItem(placeholder, userData=None)
            for identity in self.notes:
                self.addItem(identity, userData=identity)
            index = self.findData(previous)
            if previous is not None and index < 0:
                self.addItem(previous, userData=previous)
                index = self.count() - 1
            self.setCurrentIndex(max(0, index))
        if self.popup.isVisible():
            self.filter_results(self.search.text(), focused_text=focused_text)

    def _toggleComboMenu(self):
        if self.popup.isVisible():
            self.popup.close()
        elif self.count():
            with QSignalBlocker(self.search):
                self.search.clear()
            self.filter_results('')
            self.popup.show()
            self.search.setFocus()

    def filter_results(self, query, *, focused_text=None):
        """保留版本原有排序，空白起点只在未搜索时显示。"""
        query = ' '.join(query.split())
        pattern = re.compile(re.escape(query), re.IGNORECASE) if query else None
        self.delegate.pattern = pattern
        self.results.clear()
        selected_row = 0
        for index in range(self.count()):
            text = self.itemText(index)
            identity = self.itemData(index)
            notes = self.notes.get(identity, '').strip()
            summary = ' '.join(notes.split())
            if pattern and (identity is None or not (pattern.search(text) or pattern.search(summary))):
                continue
            if text == focused_text or (focused_text is None and not pattern and index == self.currentIndex()):
                selected_row = self.results.count()
            item = QListWidgetItem(text)
            item.setData(INDEX_ROLE, index)
            item.setData(NOTES_ROLE, summary)
            item.setData(Qt.ItemDataRole.AccessibleTextRole, f'{summary}\n{text}' if summary else text)
            if notes:
                tooltip = '<br>'.join(escape(line) for line in notes.splitlines())
                item.setToolTip(f'<qt>{tooltip}<br>{escape(text)}</qt>')
            else:
                item.setToolTip(text)
            self.results.addItem(item)
        count = self.results.count()
        self.empty.setVisible(count == 0)
        self.results.setVisible(count > 0)
        self.results.setCurrentRow(selected_row if count else -1)
        self.position_popup(count)

    def position_popup(self, count):
        screen = self.screen().availableGeometry()
        above = self.mapToGlobal(QPoint())
        below = self.mapToGlobal(QPoint(0, self.height()))
        margins = self.popup.layout().contentsMargins()
        self.panel.setFixedWidth(min(max(self.width(), 380), screen.width() - margins.left() - margins.right()))
        self.results.setFixedHeight(max(1, min(count, 5)) * ROW_HEIGHT)
        self.panel.layout().activate()
        size = self.popup.sizeHint()
        self.popup.setFixedSize(size)
        x = max(screen.left(), min(above.x() - margins.left(), screen.right() - size.width() + 1))
        y = below.y() - margins.top()
        if y + size.height() > screen.bottom() and above.y() - screen.top() > screen.bottom() - below.y():
            y = above.y() - size.height() + margins.bottom()
        y = max(screen.top(), min(y, screen.bottom() - size.height() + 1))
        self.popup.move(x, y)

    def choose(self, item):
        if self.popup.isVisible() and self.isEnabled() and item is not None:
            index = item.data(INDEX_ROLE)
            self.popup.close()
            self.setFocus()
            self._onItemClicked(index)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Down):
            if not event.isAutoRepeat():
                self._toggleComboMenu()
            event.accept()
            return
        super().keyPressEvent(event)

    def eventFilter(self, watched, event):
        event_type = event.type()
        if watched is getattr(self, 'popup', None) and event_type == QEvent.Type.MouseButtonPress:
            if self.rect().contains(self.mapFromGlobal(event.globalPosition().toPoint())):
                self.popup.setAttribute(Qt.WidgetAttribute.WA_NoMouseReplay)
        if event_type == QEvent.Type.KeyPress and watched in (self.search, self.results):
            key = event.key()
            if key == Qt.Key.Key_Escape:
                self.popup.close()
                self.setFocus()
                return True
            if watched is self.search and key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                if self.results.count():
                    step = -1 if key == Qt.Key.Key_Up else 1
                    row = max(0, min(self.results.currentRow() + step, self.results.count() - 1))
                    self.results.setCurrentRow(row)
                    self.results.scrollToItem(self.results.currentItem())
                return True
        return super().eventFilter(watched, event)

    def hideEvent(self, event):
        self.popup.close()
        super().hideEvent(event)

    def changeEvent(self, event):
        if event.type() == QEvent.Type.EnabledChange and not self.isEnabled():
            self.popup.close()
        super().changeEvent(event)
