"""User GUI 运行日志页：固定读取快照、虚拟列表、按视口解码与稳定标注。"""

from collections import OrderedDict
from datetime import datetime
from threading import Event
from pathlib import Path

from PySide6.QtCore import (QAbstractListModel, QModelIndex, QObject, QRunnable, QRectF,
                            QSize, Qt, QThreadPool, QTimer, QSignalBlocker, QEvent, Signal, Slot)
from PySide6.QtGui import QColor, QImage, QPainter, QTextLayout, QTextOption, QShortcut, QKeySequence
from PySide6.QtWidgets import (QApplication, QAbstractItemView, QDialog, QHBoxLayout, QListView, QListWidget,
                               QListWidgetItem, QFileDialog, QMessageBox, QStyledItemDelegate, QVBoxLayout, QWidget)
from qfluentwidgets import BodyLabel, CheckBox, LineEdit, PushButton, SegmentedWidget, CardWidget, isDarkTheme

from .work_files import WorkDirectory
from .file_content import FileContent, image_preview
from .i18n import tr
from .image_annotations import action_annotations, paint_annotations
from .run_logs import read_page, snapshot
from .run_log_sharing import list_logs, export_log, import_log


def log_colors(level: str) -> tuple[str, str]:
    """运行窗口和历史日志共用等级色块，保持深浅主题文字可读。"""
    dark = isDarkTheme()
    return {
        "info": ("#17334a", "#d5eaff") if dark else ("#eaf4ff", "#163b60"),
        "warning": ("#493919", "#ffe3a1") if dark else ("#fff4d6", "#604600"),
        "error": ("#4b2529", "#ffd8dd") if dark else ("#fde9eb", "#861b2b"),
        "debug": ("#303030", "#dedede") if dark else ("#f0f0f0", "#404040"),
    }[level]


def log_time(value: str | None) -> str:
    """将事件时间按本机时区显示到秒；旧记录缺失或损坏时不虚构时间。"""
    if not isinstance(value, str):
        return "—"
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OverflowError):
        return "—"


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
        background, foreground = log_colors(row["level"])
        painter.fillRect(option.rect.adjusted(4, 4, -4, -4), QColor(background))
        painter.setPen(QColor(foreground))
        record = row["record"]
        painter.save()
        painter.setClipRect(QRectF(rect.x(), rect.y(), max(0, rect.width() - 110), 22))
        painter.drawText(rect.x(), rect.y() + 14,
                         f"{log_time(record.get('recorded_at'))}  [{row['level'].upper()}]  {record.get('logical_name', '')}")
        painter.restore()
        painter.setPen(QColor("#009faa"))
        painter.drawText(QRectF(rect.right() - 105, rect.y(), 105, 22),
                         Qt.AlignmentFlag.AlignRight, tr("Copy details"))
        painter.setPen(QColor(foreground))
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
            painter.setPen(QColor(foreground))
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
        if (option.rect.right() - 117 <= event.position().x() <= option.rect.right() - 12
                and 8 <= event.position().y() - option.rect.y() < 30):
            self.page.copy_log(index)
            return True
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
        self.read_root, self.selected_key, self.entries = root, None, {}
        self.run_entries = []
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
        self.runs.setSpacing(4)
        self.runs.setStyleSheet("QListWidget {border: none; background: transparent;}")
        self.runs.itemClicked.connect(self.select_run)
        self.runs.itemActivated.connect(self.select_run)
        self.runs.verticalScrollBar().valueChanged.connect(self.runs_scrolled)
        self.runs.viewport().installEventFilter(self)
        self.runs.installEventFilter(self)
        sidebar = CardWidget()
        sidebar.setFixedWidth(270)
        side = QVBoxLayout(sidebar)
        heading = QHBoxLayout()
        heading.addWidget(BodyLabel(tr('Run records')), 1)
        self.import_button = PushButton(tr('Import'))
        self.import_button.clicked.connect(self.import_zip)
        heading.addWidget(self.import_button)
        side.addLayout(heading)
        self.source_filter = SegmentedWidget()
        self.source_mode = 'all'
        for key, title in (('all', tr('All')), ('local', tr('Local')), ('imported', tr('Import'))):
            self.source_filter.addItem(key, title)
        self.source_filter.setCurrentItem('all')
        self.source_filter.currentItemChanged.connect(self.select_source)
        side.addWidget(self.source_filter)
        side.addWidget(self.runs, 1)
        body.addWidget(sidebar)
        self.view = QListView()
        self.view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.view.verticalScrollBar().setSingleStep(20)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.model = LogModel(self)
        self.view.setModel(self.model)
        self.delegate = LogDelegate(self)
        self.view.setItemDelegate(self.delegate)
        self.view.activated.connect(self.toggle_details)
        self.copy_shortcut = QShortcut(QKeySequence.StandardKey.Copy, self.view)
        self.copy_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.copy_shortcut.activated.connect(lambda: self.copy_log(self.view.currentIndex()))
        self.view.verticalScrollBar().valueChanged.connect(self.scrolled)
        detail_card = CardWidget()
        details = QVBoxLayout(detail_card)
        header = QHBoxLayout()
        self.run_title = BodyLabel()
        self.run_title.setTextFormat(Qt.TextFormat.PlainText)
        header.addWidget(self.run_title, 1)
        self.export_button = PushButton(tr('Export'))
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export_zip)
        header.addWidget(self.export_button)
        details.addLayout(header)
        details.addWidget(self.view, 1)
        body.addWidget(detail_card, 1)
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

    def copy_log(self, index):
        """复制单条日志的完整文字，折叠和图片解码状态不影响正文。"""
        if not index.isValid():
            return
        row = self.model.rows[index.row()]
        record = row["record"]
        header = f"{log_time(record.get('recorded_at'))}  [{row['level'].upper()}]  {record.get('logical_name', '')}"
        QApplication.clipboard().setText(header + "\n" + row["text"])
        self.status.setText(tr("Copied successfully"))

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
        self.refresh_runs()

    def select_source(self, key):
        """切换列表来源，不混用本机与导入日志身份。"""
        self.source_mode = key
        self.refresh_runs()

    def refresh_runs(self, *_):
        """按来源过滤并按原始运行时间排序，导入身份独立于本机编号。"""
        source = self.source_mode
        self.listing_serial = getattr(self, 'listing_serial', 0) + 1
        serial = self.listing_serial
        def shown(entries):
            if serial != self.listing_serial:
                return
            self.run_entries = [entry for entry in entries
                                if source == 'all' or entry['imported'] == (source == 'imported')]
            self.entries = {}
            self.runs.clear()
            self.append_runs()
            if self.runs.count() and self.runs.currentRow() < 0:
                self.runs.setCurrentRow(0)
                self.select_run(self.runs.item(0))
            elif not self.runs.count():
                self.invalidate()
                self.model.replace([])
                self.run_id = self.selected_key = self.boundary = None
                self.run_title.clear()
                self.export_button.setEnabled(False)
                self.status.setText(tr('No run logs'))
        self.submit(lambda: list_logs(self.root), shown)

    def runs_scrolled(self, value):
        """用户滚到列表底部时追加下一批，不切换右侧运行。"""
        bar = self.runs.verticalScrollBar()
        if bar.maximum() > 0 and value == bar.maximum():
            self.append_runs()

    def eventFilter(self, watched, event):
        """首批不足以产生滚动条时，仍允许滚轮和键盘请求较旧记录。"""
        if self.runs.verticalScrollBar().maximum() == 0:
            if (watched is self.runs.viewport() and event.type() == QEvent.Type.Wheel
                    and event.angleDelta().y() < 0):
                self.append_runs()
            elif (watched is self.runs and event.type() == QEvent.Type.KeyPress
                    and event.key() in (Qt.Key.Key_Down, Qt.Key.Key_PageDown, Qt.Key.Key_End)
                    and self.runs.currentRow() == self.runs.count() - 1):
                self.append_runs()
        return super().eventFilter(watched, event)

    def append_runs(self):
        """每批创建十条列表项，阻止插入引起的滚动信号递归加载。"""
        # shortcut: 排序仍需后台扫描完整时间目录，目录扫描成为瓶颈时再引入可重建索引。
        with QSignalBlocker(self.runs.verticalScrollBar()):
            start = self.runs.count()
            for entry in self.run_entries[start:start + 10]:
                self.entries[entry['key']] = entry
                title = tr('Log No.{0}').format(entry['run_id'])
                stamp = log_time(entry['started_at'])
                item = QListWidgetItem(title + '\n' + (stamp[:13] if stamp != '—' else stamp)
                                       + (' · ' + tr('Imported') if entry['imported'] else ''))
                item.setFont(self.run_title.font())
                item.setSizeHint(QSize(230, 76))
                item.setData(Qt.ItemDataRole.UserRole, entry['key'])
                self.runs.addItem(item)
                if entry['key'] == self.selected_key:
                    self.runs.setCurrentItem(item)

    def import_zip(self):
        """选择后直接检查并导入，取消或失败不留下半成品。"""
        from .sharing_gui import sharing_task
        path, _ = QFileDialog.getOpenFileName(self, tr('Import log'), '', 'ZIP (*.zip)')
        if not path:
            return
        try:
            sharing_task(self, lambda: import_log(self.root, path))
            self.source_filter.setCurrentItem('all')
            self.source_mode = 'all'
            self.refresh_runs()
            QMessageBox.information(self, tr('Import log'), tr('Log imported successfully'))
        except InterruptedError:
            pass
        except Exception as error:
            QMessageBox.warning(self, tr('Import log'), str(error))

    def export_zip(self):
        """先压缩固定快照，再由系统保存对话框选择目标，安全替换文件。"""
        from .sharing_gui import sharing_task
        from .file_content import FileContent, checkpoint, require_disk, write_content
        if self.run_id is None:
            return
        root, identity = self.read_root, self.run_id
        try:
            boundary = snapshot(root, identity)
            with WorkDirectory() as directory:
                archive = Path(directory) / 'log.zip'
                sharing_task(self, lambda: export_log(root, identity, archive, boundary))
                destination, _ = QFileDialog.getSaveFileName(self, tr('Export log'), f'log-{identity}.zip', 'ZIP (*.zip)')
                if destination:
                    def save():
                        target = Path(destination)
                        from .page_packages import real_directory
                        real_directory(target.parent)
                        if target.is_symlink():
                            raise ValueError('ZIP destination must not be a link.')
                        content = FileContent.from_path(archive)
                        require_disk([(target.parent, len(content))])
                        with WorkDirectory(dir=target.parent) as pending:
                            output = Path(pending) / 'log.zip'
                            write_content(output, content)
                            checkpoint()
                            output.replace(target)
                    sharing_task(self, save)
        except InterruptedError:
            pass
        except Exception as error:
            QMessageBox.warning(self, tr('Export log'), str(error))

    def select_run(self, item):
        """选择运行才检查文件；当前快照有追加时等待用户接受。"""
        key = item.data(Qt.ItemDataRole.UserRole)
        entry = self.entries[key]
        identity = entry['run_id']
        changed = key != self.selected_key
        self.read_root = root = entry['root']
        self.run_title.setText(tr('Log No.{0}').format(identity) + '\n' + log_time(entry['started_at'])
                               + (' · ' + tr('Imported') if entry['imported'] else ''))
        self.export_button.setEnabled(True)
        self.debounce.stop()
        self.invalidate()
        old = self.boundary if not changed else None
        if changed:
            self.boundary = None
            self.model.replace([])
        self.run_id, self.selected_key = identity, key
        self.loading = True
        cancelled = self.cancelled
        def check():
            boundary = snapshot(root, identity)
            if old is None or boundary[:2] != old[:2] or boundary[2] < old[2] or (boundary != old and boundary[2] == old[2]):
                return boundary, "reset"
            if boundary == old:
                return boundary, "same"
            result = read_page(root, identity, boundary, start=old[2], reverse=False,
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
        root, identity, boundary, options, cancelled = self.read_root, self.run_id, self.boundary, self.options(), self.cancelled
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
        root, identity, boundary, cancelled = self.read_root, self.run_id, self.boundary, self.cancelled
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
