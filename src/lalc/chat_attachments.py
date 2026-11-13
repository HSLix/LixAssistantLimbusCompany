"""聊天附件元数据、按可见区域加载的托盘及只读图片预览。"""

import json
from pathlib import Path

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QImageReader, QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QDialog, QLabel, QFrame
from qfluentwidgets import PushButton, TransparentToolButton, FluentIcon, BodyLabel, IconWidget, ScrollArea, setCustomStyleSheet

from .agent_log import LogStore
from .i18n import tr

BUTTON_LIGHT = 'PushButton { background-color: #fafafa; color: #202020; }'
BUTTON_DARK = 'PushButton { background-color: #303030; color: #f0f0f0; }'


def draft_attachments(images, references):
    """冻结列表信息；移除卡片不修改磁盘文件或完整版本标识。"""
    return ([{'kind': 'image', 'name': Path(path).name, 'path': Path(path)} for path in images]
            + [{'kind': 'manifest', 'name': identity} for identity in references])


def history_attachments(root, number):
    """只展开附件元数据，避免为绘制卡片解码模型上下文中的全部原图。"""
    root = Path(root)
    store = LogStore(root)
    try:
        record_path = store._path(f'round-{number}/input.json')
        if not record_path.exists():
            return []
        record = json.loads(record_path.read_text(encoding='utf-8'))
        records = store.unpack(record.get('attachments', []))
        references = store.unpack(record.get('manifest_references', []))
        result = []
        for item in records:
            path = None
            filename = item.get('filename', '')
            try:
                # 文件名只允许本轮直属文件，不能借相对路径访问其他轮次或目录。
                if not filename or Path(filename).name != filename:
                    raise ValueError('Invalid attachment filename')
                path = store._path(f'round-{number}/{filename}')
            except (ValueError, TypeError):
                pass
            result.append({'kind': 'image', 'name': str(item.get('original_name', filename)), 'path': path,
                           'log_root': root, 'relative': f'round-{number}/{filename}' if path else None})
        result.extend({'kind': 'manifest', 'name': identity} for identity in references if isinstance(identity, str))
        return result
    except (OSError, ValueError, TypeError, AttributeError):
        return []


def attachment_path(item):
    """历史图片每次读取重新检查路径，拒绝符号链接替换和目录越界。"""
    try:
        if 'log_root' in item:
            return LogStore(item['log_root'])._path(item['relative'])
        return item.get('path')
    except (ValueError, TypeError):
        return None


def thumbnail(item):
    """让解码器按卡片尺寸读取，不为每张可见缩略图保留原图。"""
    path = attachment_path(item)
    if path is None:
        return QPixmap()
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid():
        reader.setScaledSize(size.scaled(QSize(56, 48), Qt.AspectRatioMode.KeepAspectRatio))
    return QPixmap.fromImage(reader.read())


class ImagePreview(QDialog):
    """原图仅在点击时读取，窗口缩放时保持比例适配。"""

    def __init__(self, item, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle(item['name'])
        self.resize(900, 640)
        layout = QVBoxLayout(self)
        self.image = QLabel()
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.image)
        path = attachment_path(item)
        reader = QImageReader(str(path)) if path else QImageReader()
        reader.setAutoTransform(True)
        self.original = QPixmap.fromImage(reader.read())
        self.fit_image()

    def fit_image(self):
        if self.original.isNull():
            self.image.setText(tr('Image unavailable'))
        else:
            self.image.setPixmap(self.original.scaled(
                max(1, self.width() - 24), max(1, self.height() - 24), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_image()


def preview_image(item, parent):
    """预览归属窗口，避免卡片滚出可见区后被一并销毁。"""
    dialog = ImagePreview(item, parent.window())
    dialog.show()
    return dialog


class AttachmentCard(QWidget):
    """卡片点击预览，悬停或键盘聚焦时显示独立删除入口。"""

    removed = Signal()

    def __init__(self, item, removable, parent):
        super().__init__(parent)
        self.item = item
        self.button = PushButton(self)
        setCustomStyleSheet(self.button, BUTTON_LIGHT, BUTTON_DARK)
        name = item['name']
        self.display_name = name
        self.button.setAccessibleName(name)
        self.button.setToolTip(name)
        layout = QHBoxLayout(self.button)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        if item['kind'] == 'image':
            pixmap = thumbnail(item)
            self.icon = QLabel() if not pixmap.isNull() else IconWidget(FluentIcon.PHOTO)
            if not pixmap.isNull():
                self.icon.setPixmap(pixmap)
                self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if pixmap.isNull():
                self.button.setToolTip(name + '\n' + tr('Image unavailable'))
                self.display_name = tr('Image unavailable')
            self.button.clicked.connect(lambda: preview_image(item, self))
        else:
            self.icon = IconWidget(FluentIcon.DOCUMENT)
        self.icon.setFixedSize(56 if item['kind'] == 'image' else 24, 48 if item['kind'] == 'image' else 24)
        self.caption = BodyLabel()
        self.caption.setTextFormat(Qt.TextFormat.PlainText)
        self.caption.setMinimumWidth(0)
        for widget in (self.icon, self.caption):
            widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            layout.addWidget(widget)
        self.remove = TransparentToolButton(FluentIcon.CLOSE, self)
        self.remove.setFixedSize(22, 22)
        self.remove.setToolTip(tr('Remove attachment'))
        self.remove.setAccessibleName(tr('Remove attachment') + ': ' + name)
        self.remove.clicked.connect(self.removed)
        self.removable = removable
        self.remove.hide()
        self.button.installEventFilter(self)
        self.remove.installEventFilter(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.button.setGeometry(self.rect())
        if self.item['kind'] == 'image':
            self.caption.setText(self.caption.fontMetrics().elidedText(
                self.display_name, Qt.TextElideMode.ElideMiddle, max(1, self.width() - 82)))
        else:
            self.caption.setText(tr('Manifest') + '\n' + self.item['name'][:8])
        self.remove.move(self.width() - 23, 1)

    def enterEvent(self, event):
        self.remove.setVisible(self.removable)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.button.hasFocus() and not self.remove.hasFocus():
            self.remove.hide()
        super().leaveEvent(event)

    def eventFilter(self, watched, event):
        from PySide6.QtCore import QEvent, QTimer
        if event.type() == QEvent.Type.FocusIn:
            self.remove.setVisible(self.removable)
        elif event.type() == QEvent.Type.FocusOut:
            QTimer.singleShot(0, self, lambda: self.remove.setVisible(self.removable and (
                self.underMouse() or self.button.hasFocus() or self.remove.hasFocus())))
        return super().eventFilter(watched, event)


class AttachmentTray(QWidget):
    """折叠一行、展开两行滚动；仅为可见行创建图片卡片。"""

    removed = Signal(int)
    geometryChanged = Signal()
    CARD_WIDTH = 174
    CARD_HEIGHT = 72
    GAP = 8

    def __init__(self, parent=None, *, removable=False):
        super().__init__(parent)
        self.items = []
        self.expanded = False
        self.removable = removable
        self.cards = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.scroll = ScrollArea()
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet('QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }')
        self.content = QWidget()
        self.scroll.setWidget(self.content)
        self.scroll.verticalScrollBar().valueChanged.connect(self.show_cards)
        layout.addWidget(self.scroll)
        self.toggle = PushButton(tr('Collapse attachments'))
        self.toggle.clicked.connect(self.toggle_expanded)
        layout.addWidget(self.toggle)
        self.more = PushButton(self.content)
        for button in (self.more, self.toggle):
            setCustomStyleSheet(button, BUTTON_LIGHT, BUTTON_DARK)
        self.more.clicked.connect(self.toggle_expanded)
        self.hide()

    def set_items(self, items):
        self.items = list(items)
        self.expanded = False
        self.clear_cards()
        self.scroll.verticalScrollBar().setValue(0)
        self.setVisible(bool(items))
        self.reflow()

    def clear_cards(self):
        for card in self.cards.values():
            card.hide()
            card.deleteLater()
        self.cards.clear()

    def toggle_expanded(self):
        self.expanded = not self.expanded
        self.reflow()
        self.geometryChanged.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reflow()

    def reflow(self):
        width = max(1, self.width() - (16 if self.expanded else 0))
        columns = max(1, (width + self.GAP) // (self.CARD_WIDTH + self.GAP))
        rows = max(1, (len(self.items) + columns - 1) // columns) if self.expanded else 1
        area_height = min(2, rows) * (self.CARD_HEIGHT + self.GAP) - self.GAP
        self.scroll.setFixedHeight(area_height)
        self.content.resize(width, rows * (self.CARD_HEIGHT + self.GAP) - self.GAP)
        self.toggle.setVisible(self.expanded)
        self.setFixedHeight(area_height + (36 if self.expanded else 0))
        self.columns = columns
        self.show_cards()

    def show_cards(self, *_):
        if not self.items or not hasattr(self, 'columns'):
            self.clear_cards()
            self.more.hide()
            return
        columns = self.columns
        overflow = not self.expanded and len(self.items) > columns
        start = self.scroll.verticalScrollBar().value() // (self.CARD_HEIGHT + self.GAP) * columns if self.expanded else 0
        stop = min(len(self.items), start + columns * 3) if self.expanded else min(len(self.items), columns - int(overflow))
        visible = set(range(start, stop))
        for index in set(self.cards) - visible:
            card = self.cards.pop(index)
            card.hide()
            card.deleteLater()
        card_width = min(self.CARD_WIDTH, self.content.width())
        for index in visible:
            if index not in self.cards:
                card = AttachmentCard(self.items[index], self.removable, self.content)
                card.removed.connect(lambda index=index: self.removed.emit(index))
                self.cards[index] = card
            card = self.cards[index]
            card.setGeometry((index % columns) * (self.CARD_WIDTH + self.GAP),
                             (index // columns) * (self.CARD_HEIGHT + self.GAP), card_width, self.CARD_HEIGHT)
            card.show()
        self.more.setVisible(overflow)
        if overflow:
            self.more.setText(tr('+{0} · Show all').format(len(self.items) - stop))
            self.more.setGeometry((columns - 1) * (self.CARD_WIDTH + self.GAP), 0, card_width, self.CARD_HEIGHT)
