"""User GUI 运行日志页：固定读取快照、虚拟列表、按视口解码与稳定标注。"""

from collections import OrderedDict
from threading import Event

from PySide6.QtCore import (QAbstractListModel, QModelIndex, QObject, QRunnable, QRectF,
                            QSize, Qt, QThreadPool, QTimer, Signal, Slot)
from PySide6.QtGui import QColor, QImage, QPainter, QTextLayout, QTextOption
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QHBoxLayout, QListView, QListWidget,
                               QListWidgetItem, QStyledItemDelegate, QVBoxLayout, QWidget)
from qfluentwidgets import BodyLabel, CheckBox, LineEdit, PushButton

from .file_content import FileContent, image_preview
from .i18n import tr
from .image_annotations import action_annotations, paint_annotations
from .run_logs import read_page, snapshot


class _Signals(QObject):
    """把后台读取结果投递到页面所属的 GUI 线程。"""
    done = Signal(int, object)


class _Task(QRunnable):
    """线程池中的一次独立读取，结果由页面代际编号判断是否过期。"""
    def __init__(self, identity, operation):
        super().__init__()
        self.identity, self.operation, self.signals = identity, operation, _Signals()

    def run(self):
        try:
            result = self.operation()
        except Exception as error:
            result = error
        self.signals.done.emit(self.identity, result)


class LogModel(QAbstractListModel):
    """只保留邻近视口的一段日志；离开的页可按字节游标重新读取。"""
    def __init__(self, parent):
        super().__init__(parent)
        self.rows = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid() and role == Qt.ItemDataRole.DisplayRole:
            return self.rows[index.row()]["text"]

    def replace(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()


class LogDelegate(QStyledItemDelegate):
    """绘制固定图片占位；解码只替换像素，展开文字才改变行高。"""
    def __init__(self, page):
        super().__init__(page.view)
        self.page = page

    def geometry(self, row, width, font):
        """先排版三行正文与图片占位，行高不依赖解码完成时机。"""
        width = max(80, width - 24)
        layout = QTextLayout(row["text"].replace("\n", "\u2028"), font)
        option = QTextOption()
        option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        layout.setTextOption(option)
        layout.beginLayout()
        height, count, more = 0, 0, False
        while True:
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(width)
            from PySide6.QtCore import QPointF
            line.setPosition(QPointF(0, height))
            if count == 3 and not row.get("expanded"):
                more = True
                break
            height += line.height()
            count += 1
        layout.endLayout()
        # 溢出行必须定位到可见高度之外，否则默认位置会使它叠在首行。
        image_height = min(520, max(36, width * row["dimensions"][1] / max(1, row["dimensions"][0]))) if row["image"] else 0
        toggle = more or row.get("expanded", False)
        return layout, height, toggle, image_height

    def sizeHint(self, option, index):
        row = self.page.model.rows[index.row()]
        _, height, toggle, image_height = self.geometry(row, self.page.view.viewport().width(), option.font)
        return QSize(100, int(52 + height + (26 if toggle else 0) + image_height + (24 if row["image"] else 0)))

    def paint(self, painter, option, index):
        row = self.page.model.rows[index.row()]
        rect = option.rect.adjusted(12, 8, -12, -8)
        painter.save()
        painter.setClipRect(option.rect)
        painter.setPen(option.palette.text().color())
        record = row["record"]
        painter.drawText(rect.x(), rect.y() + 14,
                         f"{record.get('recorded_at', '')}  [{row['level'].upper()}]  {record.get('logical_name', '')}")
        layout, height, toggle, image_height = self.geometry(row, option.rect.width(), option.font)
        painter.save()
        painter.setClipRect(QRectF(rect.x(), rect.y() + 24, rect.width(), height))
        from PySide6.QtCore import QPointF
        layout.draw(painter, QPointF(rect.x(), rect.y() + 24))
        painter.restore()
        y = rect.y() + 24 + height
        if toggle:
            painter.setPen(QColor("#009faa"))
            painter.drawText(rect.x(), int(y + 18), tr("Collapse details") if row.get("expanded") else tr("Expand details"))
            y += 26
        if row["image"]:
            painter.setPen(option.palette.text().color())
            painter.drawText(rect.x(), int(y + 16), tr("Screenshot") + ": " + str(record.get("debug_image", record).get("captured_at") or "—"))
            target = QRectF(rect.x(), y + 24, rect.width(), image_height)
            image = self.page.images.get(str(row["image"]), "pending")
            if isinstance(image, QImage):
                fitted = image.size().scaled(int(target.width()), int(target.height()), Qt.AspectRatioMode.KeepAspectRatio)
                actual = QRectF(target.x(), target.y(), fitted.width(), fitted.height())
                painter.drawImage(actual, image)
                paint_annotations(painter, actual, row["dimensions"], action_annotations(record))
                self.page.images.move_to_end(str(row["image"]))
            else:
                painter.fillRect(target, option.palette.alternateBase())
                painter.drawText(target, Qt.AlignmentFlag.AlignCenter,
                                 tr("Loading image…") if image == "pending" else tr("Image preview unavailable"))
                if image == "pending":
                    self.page.request_image(row)
        painter.setPen(option.palette.mid().color())
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
        painter.restore()

    def editorEvent(self, event, model, option, index):
        from PySide6.QtCore import QEvent
        if event.type() != QEvent.Type.MouseButtonRelease or event.button() != Qt.MouseButton.LeftButton:
            return False
        row = model.rows[index.row()]
        _, height, toggle, _ = self.geometry(row, option.rect.width(), option.font)
        y = event.position().y() - option.rect.y()
        if toggle and 32 + height <= y < 58 + height:
            anchor = self.page.anchor()
            row["expanded"] = not row.get("expanded", False)
            self.sizeHintChanged.emit(index)
            self.page.restore(anchor)
            return True
        if row["image"] and y >= 32 + height + (26 if toggle else 0) + 24:
            self.page.preview(row)
            return True
        return False


class _Preview(QWidget):
    """在独立大图预览中复用同一组原图坐标标注。"""
    def __init__(self, image, row, parent):
        super().__init__(parent)
        self.image, self.row = image, row
        self.setMinimumSize(320, 180)

    def paintEvent(self, event):
        painter = QPainter(self)
        size = self.image.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        rect = QRectF((self.width() - size.width()) / 2, (self.height() - size.height()) / 2, size.width(), size.height())
        painter.drawImage(rect, self.image)
        paint_annotations(painter, rect, self.row["dimensions"], action_annotations(self.row["record"]))


class RunLogPage(QWidget):
    """只在选择运行时检查更新；分页与条件变化保持阅读锚点。"""
    def __init__(self, root, parent=None):
        super().__init__(parent)
        self.setObjectName("run-logs")
        self.root, self.run_id, self.boundary = root, None, None
        self.cancelled = Event()
        self.generation, self.serial = 0, 0
        self.callbacks, self.tasks = {}, {}
        self.images, self.pending_images = OrderedDict(), set()
        self.loading, self.older_done, self.newer_done = False, False, True
        self.pending_boundary = None
        layout = QVBoxLayout(self)
        filters = QHBoxLayout()
        self.levels = {}
        for level in ("error", "warning", "info", "debug"):
            box = CheckBox(level.upper())
            box.setChecked(level != "debug")
            self.levels[level] = box
            filters.addWidget(box)
            box.toggled.connect(self.filter_changed)
        self.search = LineEdit()
        self.search.setPlaceholderText(tr("Search messages and components"))
        self.search.setAccessibleName(tr("Search messages and components"))
        filters.addWidget(self.search, 1)
        self.only_images = CheckBox(tr("Images only"))
        filters.addWidget(self.only_images)
        self.only_images.toggled.connect(self.filter_changed)
        self.new_logs = PushButton(tr("New logs · Go to latest"))
        self.new_logs.hide()
        self.new_logs.clicked.connect(self.accept_new)
        filters.addWidget(self.new_logs)
        layout.addLayout(filters)
        body = QHBoxLayout()
        self.runs = QListWidget()
        self.runs.setMaximumWidth(220)
        self.runs.itemClicked.connect(self.select_run)
        self.runs.itemActivated.connect(self.select_run)
        body.addWidget(self.runs)
        self.view = QListView()
        self.view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.model = LogModel(self)
        self.view.setModel(self.model)
        self.delegate = LogDelegate(self)
        self.view.setItemDelegate(self.delegate)
        self.view.activated.connect(self.toggle_details)
        self.view.verticalScrollBar().valueChanged.connect(self.scrolled)
        body.addWidget(self.view, 1)
        layout.addLayout(body, 1)
        self.status = BodyLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.debounce = QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(250)
        self.debounce.timeout.connect(self.reload_filter)
        self.search.textChanged.connect(self.filter_changed)
        self.destroyed.connect(lambda *_: self.cancelled.set())

    def submit(self, operation, done):
        """将文件读取移出主线程；旧筛选或旧运行的结果不能覆盖当前页。"""
        self.serial += 1
        identity, generation = self.serial, self.generation
        task = _Task(identity, operation)
        self.tasks[identity] = task
        self.callbacks[identity] = (generation, done)
        task.signals.done.connect(self.completed, Qt.ConnectionType.QueuedConnection)
        QThreadPool.globalInstance().start(task)

    @Slot(int, object)
    def completed(self, identity, result):
        self.tasks.pop(identity, None)
        generation, done = self.callbacks.pop(identity, (None, None))
        if generation != self.generation:
            return
        if isinstance(result, Exception):
            self.loading = False
            self.status.setText(tr("Log unavailable") + ": " + str(result))
        else:
            done(result)

    def invalidate(self):
        self.cancelled.set()
        self.cancelled = Event()
        self.generation += 1
        self.loading = False
        self.pending_images.clear()

    def toggle_details(self, index):
        """键盘回车也能展开正文，图像预览由行内点击进入。"""
        if index.isValid():
            anchor = self.anchor()
            row = self.model.rows[index.row()]
            row["expanded"] = not row.get("expanded", False)
            self.delegate.sizeHintChanged.emit(index)
            self.restore(anchor)

    def showEvent(self, event):
        super().showEvent(event)
        def listing():
            return sorted((int(p.stem) for p in (self.root / "traces").glob("*.jsonl")
                           if p.stem.isdecimal() and int(p.stem) > 0 and not p.is_symlink()), reverse=True)
        def shown(ids):
            self.runs.clear()
            for identity in ids:
                item = QListWidgetItem(f"Run #{identity}")
                item.setData(Qt.ItemDataRole.UserRole, identity)
                self.runs.addItem(item)
                if identity == self.run_id:
                    self.runs.setCurrentItem(item)
            if self.run_id is None and ids:
                self.runs.setCurrentRow(0)
                self.select_run(self.runs.item(0))
            elif not ids:
                self.status.setText(tr("No run logs"))
        self.submit(listing, shown)

    def select_run(self, item):
        """选择运行才检查文件；当前快照有追加时等待用户接受。"""
        identity = item.data(Qt.ItemDataRole.UserRole)
        self.debounce.stop()
        self.invalidate()
        old = self.boundary if identity == self.run_id else None
        if identity != self.run_id:
            self.boundary = None
            self.model.replace([])
        self.run_id = identity
        self.loading = True
        cancelled = self.cancelled
        def check():
            boundary = snapshot(self.root, identity)
            if old is None or boundary[:2] != old[:2] or boundary[2] < old[2] or (boundary != old and boundary[2] == old[2]):
                return boundary, "reset"
            if boundary == old:
                return boundary, "same"
            result = read_page(self.root, identity, boundary, start=old[2], reverse=False,
                               levels=tuple(self.levels), limit=1, cancelled=cancelled)
            return boundary, "new" if result["rows"] else "same"
        def checked(value):
            self.loading = False
            boundary, change = value
            if change == "reset":
                self.boundary = boundary
                self.pending_boundary = None
                self.new_logs.hide()
                self.load_reset()
            elif change == "new":
                self.pending_boundary = boundary
                self.new_logs.show()
            self.view.viewport().update()
        self.submit(check, checked)

    def accept_new(self):
        if self.pending_boundary:
            self.boundary = self.pending_boundary
            self.pending_boundary = None
            self.new_logs.hide()
            self.invalidate()
            self.load_reset()

    def options(self):
        return dict(levels=tuple(k for k, v in self.levels.items() if v.isChecked()),
                    keyword=self.search.text(), images=self.only_images.isChecked())

    def filter_changed(self, *_):
        if self.run_id is not None and self.boundary:
            self.debounce.start()

    def reload_filter(self):
        anchor = self.anchor()
        self.invalidate()
        self.load_reset(anchor)

    def anchor(self):
        index = self.view.indexAt(self.view.viewport().rect().topLeft())
        if not index.isValid() and self.model.rows:
            index = self.model.index(0)
        if not index.isValid():
            return None
        row = self.model.rows[index.row()]
        return row["offset"], row["end"], self.view.visualRect(index).top()

    def restore(self, anchor):
        if anchor is None:
            return
        def move():
            if not self.model.rows:
                return
            i = min(range(len(self.model.rows)), key=lambda n: abs(self.model.rows[n]["offset"] - anchor[0]))
            index = self.model.index(i)
            self.view.scrollTo(index, QAbstractItemView.ScrollHint.PositionAtTop)
            bar = self.view.verticalScrollBar()
            # 收起跨越屏幕的长项时，旧偏移可能超过新高度，至少保留该项的一部分。
            offset = max(anchor[2], 40 - self.view.visualRect(index).height())
            bar.setValue(bar.value() - min(0, offset))
        QTimer.singleShot(0, move)

    def load_reset(self, anchor=None):
        """加载最新或锚点附近的一批；较旧侧无匹配才寻找较新项。"""
        self.loading, self.older_done, self.newer_done = True, False, anchor is None
        root, identity, boundary, options, cancelled = self.root, self.run_id, self.boundary, self.options(), self.cancelled
        self.status.setText(tr("Loading logs…"))
        def load():
            result = read_page(root, identity, boundary, end=anchor[1] if anchor else None, cancelled=cancelled, **options)
            if anchor and not result["rows"] and not cancelled.is_set():
                result = read_page(root, identity, boundary, start=anchor[1], reverse=False, limit=1, cancelled=cancelled, **options)
            return result
        def shown(result):
            self.model.replace(result["rows"])
            self.images.clear()
            self.loading = False
            self.older_done = len(result["rows"]) < 60
            self.report(result)
            if anchor:
                self.restore(anchor)
            else:
                self.view.scrollToTop()
        self.submit(load, shown)

    def report(self, result):
        self.status.setText(tr("Damaged log records skipped") if result["damaged"] else
                            ("" if self.model.rows else tr("No matching logs")))

    def scrolled(self, *_):
        if self.loading or not self.model.rows or self.debounce.isActive():
            return
        bar = self.view.verticalScrollBar()
        if bar.value() >= bar.maximum() - 150 and not self.older_done:
            self.more(True)
        elif bar.value() <= 80 and not self.newer_done:
            self.more(False)

    def more(self, older):
        """双向读取相邻页并淘汰远端行，保留当前顶部日志的屏幕位置。"""
        self.loading = True
        anchor, rows = self.anchor(), self.model.rows
        options = self.options()
        options.update(end=rows[-1]["offset"]) if older else options.update(start=rows[0]["end"], reverse=False)
        root, identity, boundary, cancelled = self.root, self.run_id, self.boundary, self.cancelled
        def shown(result):
            added = result["rows"]
            if older:
                self.older_done = len(added) < 60
                combined = rows + added
                if len(combined) > 240:
                    self.newer_done = False
                combined = combined[-240:]
            else:
                self.newer_done = len(added) < 60
                combined = added + rows
                if len(combined) > 240:
                    self.older_done = False
                combined = combined[:240]
            self.model.replace(combined)
            self.restore(anchor)
            self.loading = False
            self.report(result)
        self.submit(lambda: read_page(root, identity, boundary, cancelled=cancelled, **options), shown)

    def request_image(self, row):
        """仅为可见项排队生成缩略图，缓存限制为十二张。"""
        key = str(row["image"])
        if key in self.pending_images or len(self.pending_images) >= 8:
            return
        self.pending_images.add(key)
        cancelled = self.cancelled
        def load():
            if cancelled.is_set():
                return None
            try:
                return image_preview(FileContent.from_path(row["image"]), (1280, 720))
            except (OSError, ValueError, MemoryError):
                return None
        def shown(content):
            self.pending_images.discard(key)
            decoded = QImage.fromData(content) if content else QImage()
            self.images[key] = None if decoded.isNull() else decoded
            while len(self.images) > 12:
                self.images.popitem(last=False)
            self.view.viewport().update()
        self.submit(load, shown)

    def preview(self, row):
        """后台准备较大预览，复用标注接口且不修改原图。"""
        def shown(content):
            image = QImage.fromData(content)
            dialog = QDialog(self)
            dialog.setWindowTitle(tr("Screenshot"))
            dialog.resize(1000, 700)
            layout = QVBoxLayout(dialog)
            layout.addWidget(_Preview(image, row, dialog))
            dialog.exec()
        self.submit(lambda: image_preview(FileContent.from_path(row["image"]), (3840, 2160)), shown)

    def resizeEvent(self, event):
        anchor = self.anchor()
        super().resizeEvent(event)
        self.view.scheduleDelayedItemsLayout()
        self.restore(anchor)
