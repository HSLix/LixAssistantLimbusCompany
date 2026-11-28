"""User GUI 数据与清理页及永久删除确认。"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import Event

from PySide6.QtCore import QDate, QEvent, QSignalBlocker, QThreadPool, Qt, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QAbstractItemView, QHBoxLayout, QListWidgetItem, QTableWidgetItem, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel, CalendarPicker, CaptionLabel, CardWidget, ComboBox, FluentIcon,
    IndeterminateProgressRing, ListWidget, MessageBoxBase, Pivot, PrimaryPushButton, PushButton,
    SearchLineEdit, SubtitleLabel, TableWidget, TitleLabel,
)

from .data_maintenance import DataMaintenance
from .i18n import tr
from .run_log_gui import ReadTask


def _size(size):
    if size is None:
        return "—"
    for unit, scale in (("GiB", 1024**3), ("MiB", 1024**2), ("KiB", 1024)):
        if size >= scale:
            return f"{size / scale:.1f} {unit}"
    return f"{size} B"


def _date(value, time=False):
    if value is None:
        return tr("Not recorded")
    return value.astimezone().strftime("%Y-%m-%d %H:%M" if time else "%Y-%m-%d")


def _count(value):
    return str(value) if value is not None else "—"


def _log_name(row):
    return tr("Run #{0} · {1}").format(row["run_id"], tr("Imported") if row["imported"] else tr("Local"))


class Totals(CardWidget):
    """同一行展示三项当前类别的总量。"""

    def __init__(self, parent=None, *, columns=3):
        super().__init__(parent)
        line = QHBoxLayout(self)
        line.setContentsMargins(16, 10, 16, 10)
        self.labels = []
        for _ in range(columns):
            column = QVBoxLayout()
            title, value = CaptionLabel(), SubtitleLabel()
            column.addWidget(title)
            column.addWidget(value)
            line.addLayout(column, 1)
            self.labels.append((title, value))

    def update_values(self, values):
        for (title, value), (name, text) in zip(self.labels, values):
            title.setText(name)
            value.setText(str(text))


class CleanupDialog(MessageBoxBase):
    """精确展示本批永久删除的条目、关联源码及预估占用。"""

    def __init__(self, plan, dates, parent, component_names=None):
        super().__init__(parent)
        logs = plan.category == "logs"
        components = plan.category == "components"
        self.widget.setMinimumWidth(550)
        title = {"logs": tr("Permanently delete {0} run logs?"),
                 "manifests": tr("Permanently delete {0} workflow versions?"),
                 "components": tr("Permanently delete {0} unreferenced Component sources?")}
        self.viewLayout.addWidget(SubtitleLabel(title[plan.category].format(len(plan.rows))))
        if not components:
            self.viewLayout.addWidget(CaptionLabel(dates))
        totals = Totals(self, columns=2 if components else 3)
        space = (tr("Estimated space freed"), _size(plan.size))
        if logs:
            imported = sum(row["imported"] for row in plan.rows)
            counts = [(tr("Local logs"), tr("{0} logs").format(len(plan.rows) - imported)),
                      (tr("Imported logs"), tr("{0} logs").format(imported)), space]
        elif components:
            counts = [(tr("Component sources"), tr("{0} sources").format(len(plan.rows))), space]
        else:
            counts = [(tr("Workflow versions"), tr("{0} versions").format(len(plan.rows))),
                      (tr("Unreferenced sources"), tr("{0} sources").format(len(plan.sources))), space]
        totals.update_values(counts)
        self.viewLayout.addWidget(totals)
        items = ListWidget()
        items.setAccessibleName(tr("Items to delete"))
        items.setFixedHeight(min(150, 39 * len(plan.rows) + 8))
        for row in plan.rows:
            if logs:
                text = f"{_log_name(row)}   ·   {_size(row['size'])}"
            elif components:
                names = (component_names or {}).get(row["key"]) or tr("Unknown name")
                text = f"{names}   ·   {row['key'][7:15]}   ·   {_size(row['size'])}"
            else:
                text = f"{row['key'][:8]}   ·   {row['notes'].splitlines()[0] if row['notes'] else _date(row['date'])}"
            item = QListWidgetItem(text)
            item.setToolTip(row["key"] if components else row.get("notes") or text)
            items.addItem(item)
        self.viewLayout.addWidget(items)
        if not logs and plan.sources:
            toggle = PushButton(tr("Show {0} Component sources to be deleted").format(len(plan.sources)))
            toggle.setCheckable(True)
            self.viewLayout.addWidget(toggle)
            sources = ListWidget()
            sources.setAccessibleName(tr("Unreferenced sources"))
            sources.setFixedHeight(min(115, 39 * len(plan.sources) + 8))
            for path, names in plan.sources:
                text = f"{path.stem[:8]}   ·   {', '.join(names)}"
                item = QListWidgetItem(text)
                item.setToolTip(f"{path.name}\n{', '.join(names)}")
                sources.addItem(item)
            sources.hide()
            toggle.toggled.connect(sources.setVisible)
            self.viewLayout.addWidget(sources)
        if logs:
            retained = tr("Usage summaries, Workflow Ledger and Agent sessions are kept.")
            warning = tr("Deleted detailed logs and screenshots cannot be recovered.")
        elif components:
            retained = tr("All workflow versions will be checked for references again before deletion.")
            warning = tr("Deleted Component sources cannot be recovered.")
        else:
            retained = tr("Default, latest and sources referenced by retained versions are kept.")
            warning = tr("Deleted versions cannot be selected for runs or rollback.")
        self.viewLayout.addWidget(BodyLabel(retained))
        notice = BodyLabel(warning)
        notice.setTextColor("#ae3c35", "#ff9c94")
        self.viewLayout.addWidget(notice)
        self.yesButton.setText(tr("Delete permanently"))
        self.yesButton.setMinimumWidth(98)
        self.yesButton.setStyleSheet("QPushButton {background:#a5322b;color:white;}"
                                     "QPushButton:hover {background:#902923;}"
                                     "QPushButton:focus {border:2px solid #ec9a95;}")
        self.yesButton.setAutoDefault(False)
        self.yesButton.setDefault(False)
        self.cancelButton.setText(tr("Cancel"))
        self.cancelButton.setMinimumWidth(60)
        self.cancelButton.setDefault(True)
        for button in (self.yesButton, self.cancelButton):
            self.buttonLayout.removeWidget(button)
        self.buttonLayout.addStretch(1)
        self.buttonLayout.addWidget(self.cancelButton)
        self.buttonLayout.addWidget(self.yesButton)
        self.setTabOrder(self.cancelButton, self.yesButton)

    def showEvent(self, event):
        super().showEvent(event)
        self.cancelButton.setFocus()


@dataclass
class Inventory:
    """一次后台盘点的缓存，包含列表和后续补齐的统计。"""

    rows: list | None = None
    invalid: int = 0
    step: str = "inventory"
    sizes: dict | None = None
    error: Exception | None = None
    cancelled: Event = field(default_factory=Event)


class DataMaintenancePage(QWidget):
    """按类别后台读取，表格分批显示，删除须经固定预览及服务端复核。"""

    PAGE_SIZE = 50
    CATEGORIES = ("logs", "manifests", "components", "assets")

    def __init__(self, window):
        super().__init__(window)
        route = "data-maintenance"
        business_routes = {page.page_id for page in window.business_pages}
        while route in business_routes:
            route += "-"
        self.setObjectName(route)
        self.window = window
        self.data = DataMaintenance(window.service)
        self.category = "logs"
        self.rows, self.filtered, self.selected = [], [], set()
        self.eligible_keys = set()
        self.serial = 0
        self.preview_request = 0
        self.tasks = {}
        self.cache = {}
        self.inventory = None
        self.end_is_default = True
        cache = self.cache

        def cancel_sizes(*_):
            for entry in cache.values():
                entry.cancelled.set()

        self.destroyed.connect(cancel_sizes)
        self.loading, self.busy, self.previewing = False, False, False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 22, 28, 24)
        layout.setSpacing(14)
        layout.addWidget(TitleLabel(tr("Data & Cleanup")))
        self.tabs = Pivot(self)
        self.titles = dict(zip(self.CATEGORIES, (tr("Run logs"), tr("Workflow versions"),
                                               tr("Components"), tr("Asset inventory"))))
        for key, title in self.titles.items():
            self.tabs.addItem(key, title, onClick=lambda *_, key=key: self.switch_category(key))
        self.tabs.setCurrentItem(self.category)
        layout.addWidget(self.tabs)
        self.totals = Totals(self)
        layout.addWidget(self.totals)

        self.controls = QWidget()
        controls = QHBoxLayout(self.controls)
        controls.setContentsMargins(0, 0, 0, 0)
        self.dates = QWidget()
        dates = QHBoxLayout(self.dates)
        dates.setContentsMargins(0, 0, 0, 0)
        self.start, self.end = CalendarPicker(), CalendarPicker()
        self.start.setAccessibleName(tr("Start date"))
        self.end.setAccessibleName(tr("End date"))
        for widget in (BodyLabel(tr("Date")), self.start, BodyLabel(tr("to")), self.end):
            dates.addWidget(widget)
        clear_dates = PushButton(tr("Clear dates"))
        clear_dates.clicked.connect(self.clear_dates)
        dates.addWidget(clear_dates)
        self.end.setDate(QDate.currentDate())
        self.start.dateChanged.connect(self.filter_changed)
        self.end.dateChanged.connect(self.end_date_changed)
        controls.addWidget(self.dates)
        self.search = SearchLineEdit()
        self.search.setFixedWidth(250)
        self.search.textChanged.connect(self.filter_changed)
        controls.addWidget(self.search)
        controls.addStretch(1)
        self.filter = ComboBox()
        self.filter.currentIndexChanged.connect(self.filter_option_changed)
        self.filter.activated.connect(self.sort_assets)
        controls.addWidget(self.filter)
        refresh = PushButton(FluentIcon.SYNC, tr("Refresh"))
        refresh.clicked.connect(self.refresh)
        controls.addWidget(refresh)
        layout.addWidget(self.controls)
        self.hint = QWidget()
        hint = QHBoxLayout(self.hint)
        hint.setContentsMargins(0, 0, 0, 0)
        self.stats_ring = IndeterminateProgressRing()
        self.stats_ring.setFixedSize(18, 18)
        hint.addWidget(self.stats_ring)
        self.note = CaptionLabel()
        self.note.setWordWrap(True)
        hint.addWidget(self.note, 1)
        layout.addWidget(self.hint)
        self.loading_card = CardWidget()
        loading_layout = QVBoxLayout(self.loading_card)
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.setSpacing(12)
        loading_ring = IndeterminateProgressRing()
        loading_ring.setFixedSize(44, 44)
        loading_layout.addWidget(loading_ring, 0, Qt.AlignmentFlag.AlignHCenter)
        self.loading_title = SubtitleLabel()
        loading_layout.addWidget(self.loading_title, 0, Qt.AlignmentFlag.AlignHCenter)
        loading_layout.addWidget(BodyLabel(tr("The list will appear before detailed statistics finish.")),
                                 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.loading_card, 1)
        self.table = TableWidget()
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(7)
        self.table.setWordWrap(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(43)
        self.table.itemChanged.connect(self.selection_changed)
        self.table.cellActivated.connect(self.open_details)
        self.table.cellClicked.connect(self.open_details)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionsClickable(True)
        self.table.horizontalHeader().sectionClicked.connect(self.sort_by)
        self.table.verticalScrollBar().valueChanged.connect(self.scroll_changed)
        self.table.viewport().installEventFilter(self)
        layout.addWidget(self.table, 1)
        self.scroll_note = CaptionLabel()
        layout.addWidget(self.scroll_note)
        self.footer = QWidget()
        footer = QHBoxLayout(self.footer)
        footer.setContentsMargins(0, 0, 0, 0)
        self.status = BodyLabel()
        self.status.setWordWrap(True)
        footer.addWidget(self.status)
        self.select_all = PushButton(tr("Select filtered results"))
        self.select_all.clicked.connect(self.toggle_all)
        footer.addWidget(self.select_all)
        self.quick_select = PushButton()
        self.quick_select.clicked.connect(self.select_quick)
        footer.insertWidget(1, self.quick_select)
        footer.addStretch(1)
        self.preview_button = PrimaryPushButton(tr("Preview cleanup"))
        self.preview_button.clicked.connect(self.preview)
        footer.addWidget(self.preview_button)
        layout.addWidget(self.footer)
        self.configure()
        self.loading_card.hide()

    def configure(self):
        logs, versions, components, assets = (self.category == key for key in self.CATEGORIES)
        self.sort_column = 3 if logs or assets else 2 if versions else 4
        self.descending = True
        self.dates.setVisible(logs or versions)
        self.search.setVisible(components or assets)
        search = tr("Search Component name or version") if components else tr("Search Asset name")
        self.search.setPlaceholderText(search)
        self.search.setAccessibleName(search)
        entries = ([tr("All sources"), tr("Local"), tr("Imported")] if logs else
                   [tr("All versions"), tr("Eligible for cleanup"), tr("Protected")] if versions else
                   [tr("Last match: newest first"), tr("Last match: oldest first")] if assets else
                   [tr("All roles"), tr("Plan"), tr("Task Workflow"), tr("Subworkflow"), tr("Step"), tr("Recovery Rule")])
        with QSignalBlocker(self.search), QSignalBlocker(self.filter):
            self.search.clear()
            self.filter.clear()
            self.filter.addItems(entries)
        self.select_all.setVisible(logs or versions)
        self.quick_select.setVisible(not assets)
        self.quick_select.setText(tr("Select logs older than 3 days") if logs else
                                  tr("Select versions older than 3 days") if versions else
                                  tr("Select unreferenced Components"))
        self.preview_button.setVisible(not assets)

    def showEvent(self, event):
        super().showEvent(event)
        self.update_default_end()
        self.open_inventory()

    def switch_category(self, category):
        if category != self.category:
            self.preview_request += 1
            self.previewing = False
            self.category = category
            self.selected.clear()
            self.configure()
            self.open_inventory()

    def submit(self, operation, callback):
        self.serial += 1
        task = ReadTask(self.serial, operation)
        self.tasks[self.serial] = (task, callback)
        task.signals.done.connect(self.completed, Qt.ConnectionType.QueuedConnection)
        QThreadPool.globalInstance().start(task)

    @Slot(int, object)
    def completed(self, identity, result):
        _, callback = self.tasks.pop(identity)
        callback(result)

    def open_inventory(self):
        if self.category not in self.cache:
            self.refresh()
        elif self.inventory is not self.cache[self.category]:
            self.render_inventory(self.cache[self.category])
        else:
            self.filter_changed(preserve=True)

    def refresh(self):
        """用独立快照刷新当前类别，已作废的任务结果不会替换缓存。"""
        self.update_default_end()
        self.preview_request += 1
        self.previewing = False
        self.selected.clear()
        category = self.category
        self.invalidate_inventory(category)
        entry = self.cache[category] = Inventory()
        self.render_inventory(entry)
        self.submit(lambda: self.data.inventory(category, with_usage=False),
                    lambda result: self.inventory_result(category, entry, result))

    def invalidate_inventory(self, category):
        previous = self.cache.pop(category, None)
        if previous is not None:
            previous.cancelled.set()

    def inventory_result(self, category, entry, result):
        """补齐当前缓存，允许用户切换标签后任务继续完成。"""
        if self.cache.get(category) is not entry:
            return
        step, entry.step = entry.step, ""
        if isinstance(result, Exception):
            entry.error = result
        elif step == "sizes":
            entry.sizes = result
            for row in entry.rows:
                row["size"] = result.get(row["key"])
        else:
            entry.rows, entry.invalid = result
            if step == "inventory" and entry.rows:
                if category == "logs":
                    entry.step = "sizes"
                    self.submit(lambda: self.data.log_sizes(entry.rows, cancelled=entry.cancelled),
                                lambda sizes: self.inventory_result(category, entry, sizes))
                elif category in {"manifests", "components"}:
                    entry.step = "usage"
                    self.submit(lambda: self.data.inventory(category),
                                lambda usage: self.inventory_result(category, entry, usage))
        if self.category == category:
            self.render_inventory(entry, preserve=True)

    def render_inventory(self, entry, *, preserve=False):
        self.inventory = entry
        self.loading = entry.step == "inventory"
        self.loading_title.setText(tr("Loading {0}…").format(self.titles[self.category]))
        self.loading_card.setVisible(self.loading)
        for widget in (self.totals, self.controls, self.table, self.footer):
            widget.setVisible(not self.loading)
        self.rows = entry.rows or []
        rows = self.rows
        if self.category == "logs":
            imported = sum(row["imported"] for row in rows)
            value = "—" if rows and not entry.sizes else _size(sum((entry.sizes or {}).values()))
            if entry.sizes and len(entry.sizes) < len(rows):
                value = tr("{0} (partial)").format(value)
            values = [(tr("Local logs"), tr("{0} logs").format(len(rows) - imported)),
                      (tr("Imported logs"), tr("{0} logs").format(imported)),
                      (tr("Detailed log size"), value)]
            notice = ""
            if entry.sizes is not None and len(entry.sizes) < len(rows):
                notice = tr("Size unavailable for {0} run logs.").format(len(rows) - len(entry.sizes))
        elif self.category == "manifests":
            values = [(tr("Published versions"), tr("{0} versions").format(len(rows))),
                      (tr("Protected versions"), tr("{0} versions").format(sum(row["default"] or row["latest"] for row in rows))),
                      (tr("Referenced Component versions"), tr("{0} sources").format(len({digest for row in rows for _, digest in row["members"]})))]
            notice = tr("Select older versions by last run, or release date when there is no run history.")
        elif self.category == "components":
            values = [(tr("Logical names"), tr("{0} names").format(len({row["name"] for row in rows if row["name"]}))),
                      (tr("Component source versions"), tr("{0} sources").format(len({row["key"] for row in rows}))),
                      (tr("Unreferenced sources"), tr("{0} sources").format(len({row["key"] for row in rows if row["references"] == 0})))]
            notice = tr("Calls are counted by source version from available local logs and usage summaries.")
        else:
            values = [(tr("Asset names"), tr("{0} names").format(len(rows))),
                      (tr("Template images"), tr("{0} images").format(sum(row["count"] for row in rows))),
                      (tr("Image size"), _size(sum(row["size"] for row in rows)))]
            notice = tr("Last match is read from the Asset usage index.")
        self.totals.update_values(values)
        working = entry.step in {"sizes", "usage"}
        self.stats_ring.setVisible(working)
        if working:
            notice = (tr("Calculating detailed log size…") if entry.step == "sizes"
                      else tr("Calculating usage from local Run history…"))
        if entry.invalid:
            notice = (notice + " " + tr("{0} records could not be read. Statistics may be incomplete.").format(entry.invalid)).strip()
        if entry.error is not None:
            notice = tr("Data operation failed: {0}").format(tr(str(entry.error)))
        self.note.setText(notice)
        self.hint.setVisible(not self.loading and bool(notice))
        self.filter_changed(preserve=preserve)

    def update_default_end(self):
        if self.end_is_default and self.end.date != QDate.currentDate():
            with QSignalBlocker(self.end):
                self.end.setDate(QDate.currentDate())

    def end_date_changed(self):
        self.end_is_default = False
        self.filter_changed()

    def clear_dates(self):
        self.start.reset()
        self.end.reset()
        self.end_is_default = False
        self.filter_changed()

    def eligible(self, row):
        if self.category == "logs":
            return row["date"] is not None
        if self.category == "components":
            return row["references"] == 0
        return self.category == "manifests" and not (row["default"] or row["latest"])

    def filter_changed(self, *, preserve=False):
        start, end = (picker.date.toPython() if picker.date.isValid() else None
                      for picker in (self.start, self.end))
        choice = self.filter.currentIndex()
        term = self.search.text().casefold().strip() if self.category in {"components", "assets"} else ""
        rows = []
        for row in self.rows:
            if self.category in {"logs", "manifests"}:
                stamp = row["date"]
                if start or end:
                    if stamp is None:
                        continue
                    date = stamp.astimezone().date()
                    if (start and date < start) or (end and date > end):
                        continue
                if choice > 0:
                    flag = row["imported"] if self.category == "logs" else not self.eligible(row)
                    if flag != (choice == 2):
                        continue
            elif self.category == "components" and choice > 0:
                roles = ("automation_plan", "task_workflow", "sub_workflow", "step", "recovery_rule")
                if row["role"] != roles[choice - 1]:
                    continue
            if term and term not in (str(row.get("name") or "") + " " + str(row["key"])).casefold():
                continue
            rows.append(row)
        self.filtered = rows
        self.eligible_keys = {row["key"] for row in rows if self.eligible(row)}
        self.selected.intersection_update(self.eligible_keys)
        self.sort_rows()
        self.render_table(preserve=preserve)

    def sort_assets(self, choice):
        if self.category == "assets" and choice >= 0:
            if self.sort_column == 3 and self.descending == (choice == 0):
                return
            self.sort_column, self.descending = 3, choice == 0
            self.sort_rows()
            self.render_table()

    def filter_option_changed(self, choice):
        if self.category == "assets":
            self.sort_assets(choice)
        else:
            self.filter_changed()

    def sort_by(self, column):
        if ((self.category == "logs" and column in (0, 6))
                or (self.category in {"manifests", "components"} and column == 0)):
            return
        self.descending = not self.descending if column == self.sort_column else False
        self.sort_column = column
        if self.category == "assets" and column == 3:
            with QSignalBlocker(self.filter):
                self.filter.setCurrentIndex(int(not self.descending))
        self.sort_rows()
        self.render_table()

    def sort_rows(self):
        fields = {
            "logs": (None, "run_id", "imported", "date", "status", "size"),
            "manifests": (None, "notes", "date", "count", "last", "latest"),
            "components": (None, "name", "key", "references", "count", "last"),
            "assets": ("key", "count", "size", "last"),
        }
        field = fields[self.category][self.sort_column]
        known = [row for row in self.filtered if row[field] is not None]
        known.sort(key=lambda row: row[field], reverse=self.descending)
        self.filtered = known + [row for row in self.filtered if row[field] is None]

    def render_table(self, *, preserve=False, append=False):
        """首次只建一批表格项，触底时保留卷动位置并追加。"""
        bar = self.table.verticalScrollBar()
        current = self.table.rowCount()
        first = current if append else 0
        capacity = max(current, self.PAGE_SIZE) if preserve else first + self.PAGE_SIZE
        rows = self.filtered[first:capacity]
        scroll = bar.value() if preserve or append else 0
        details = tr("View log")
        if self.category == "logs":
            headers = ("", tr("Run"), tr("Source"), tr("Start time"), tr("Result"), tr("Size"), "")
            widths = (35, 105, 90, 160, 90, 100, 95)
            values = [(None, tr("Run #{0}").format(row["run_id"]), tr("Imported") if row["imported"] else tr("Local"),
                       _date(row["date"], True),
                       {"completed": tr("Completed"), "success": tr("Success"), "failure": tr("Failed"),
                        "cancelled": tr("Cancelled"), "interrupted": tr("Interrupted"),
                        "unknown": tr("Unknown")}.get(row["status"], tr("Unknown")),
                       _size(row["size"]), details) for row in rows]
        elif self.category == "manifests":
            headers = ("", tr("Version / release notes"), tr("Release date"), tr("Run count"), tr("Last run"), tr("Cleanup status"))
            widths = (35, 246, 145, 102, 152, 120)
            values = [(None, f"{row['key'][:8]}   {row['notes'].splitlines()[0] if row['notes'] else ''}",
                       _date(row["date"]) + (f" · {tr('File date')}" if row["file_date"] else ""),
                       _count(row["count"]), _date(row["last"], True),
                       " · ".join(label for flag, label in ((row["default"], tr("Default")), (row["latest"], tr("Latest")),
                                  (not self.eligible(row), tr("Protected"))) if flag) or tr("Eligible for cleanup"))
                      for row in rows]
        elif self.category == "components":
            headers = ("", tr("Component"), tr("Source version"), tr("Referenced by"), tr("Calls"), tr("Last used"))
            widths = (35, 258, 133, 120, 105, 160)
            values = [(None, row["name"] or tr("Unknown name"), row["key"][7:15],
                       _count(row["references"]), _count(row["count"]), _date(row["last"], True)) for row in rows]
        else:
            headers = (tr("Asset name"), tr("Template images"), tr("Size"), tr("Last match"))
            widths = (320, 135, 130, 160)
            values = [(row["key"], str(row["count"]), _size(row["size"]), _date(row["last"], True)) for row in rows]
        with QSignalBlocker(self.table), QSignalBlocker(bar):
            if not append:
                self.table.clear()
                self.table.setColumnCount(len(headers))
                self.table.setHorizontalHeaderLabels(headers)
                header = self.table.horizontalHeader()
                direction = Qt.SortOrder.DescendingOrder if self.descending else Qt.SortOrder.AscendingOrder
                header.setSortIndicator(self.sort_column, direction)
                header.setSortIndicatorShown(True)
                for column, width in enumerate(widths):
                    self.table.setColumnWidth(column, width)
            self.table.setRowCount(first + len(rows))
            for index, (row, cells) in enumerate(zip(rows, values), first):
                for column, text in enumerate(cells):
                    item = QTableWidgetItem(text or "")
                    if text is None:
                        item.setCheckState(Qt.CheckState.Checked if row["key"] in self.selected else Qt.CheckState.Unchecked)
                        if not self.eligible(row):
                            item.setFlags(item.flags() & ~(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable))
                    elif (self.category, column) in {("manifests", 1), ("components", 2)}:
                        item.setToolTip(row["key"] + ("\n" + row["notes"] if row.get("notes") else ""))
                    elif self.category == "logs" and column == 6:
                        item.setForeground(QColor("#39b9cc" if self.palette().window().color().lightness() < 128 else "#005fa8"))
                    self.table.setItem(index, column, item)
            bar.setValue(scroll)
        self.render_actions()

    def scroll_changed(self, value):
        if self.table.rowCount() < len(self.filtered) and value == self.table.verticalScrollBar().maximum():
            self.render_table(append=True)

    def eventFilter(self, watched, event):
        if (watched is self.table.viewport() and event.type() == QEvent.Type.Wheel
                and event.angleDelta().y() < 0
                and self.table.verticalScrollBar().maximum() == 0
                and self.table.rowCount() < len(self.filtered)):
            self.render_table(append=True)
        return super().eventFilter(watched, event)

    def selection_changed(self, item):
        if item.column() or self.category == "assets":
            return
        row = self.filtered[item.row()]
        if self.eligible(row):
            if item.checkState() == Qt.CheckState.Checked:
                self.selected.add(row["key"])
            else:
                self.selected.discard(row["key"])
            self.set_selection(self.selected)

    def set_selection(self, keys):
        self.selected = keys
        with QSignalBlocker(self.table):
            for index, row in enumerate(self.filtered[:self.table.rowCount()]):
                check = Qt.CheckState.Checked if row["key"] in keys else Qt.CheckState.Unchecked
                self.table.item(index, 0).setCheckState(check)
        self.render_actions()

    def toggle_all(self):
        self.set_selection(set() if self.eligible_keys == self.selected else self.eligible_keys.copy())

    def select_quick(self):
        """按当前筛选整批选择，包含滚动尚未显示的行。"""
        if self.category == "components":
            self.set_selection(self.eligible_keys.copy())
        else:
            cutoff = datetime.now(UTC) - timedelta(days=3)
            self.set_selection({row["key"] for row in self.filtered if row["key"] in self.eligible_keys
                                and (row.get("last") or row["date"]) < cutoff})

    def render_actions(self, busy=None):
        if busy is not None:
            self.busy = busy
        mutable = self.category != "assets"
        available = self.eligible_keys
        self.preview_button.setEnabled(bool(self.selected) and not (self.busy or self.loading or self.previewing))
        self.select_all.setEnabled(bool(available))
        self.select_all.setText(tr("Clear selection") if available and available == self.selected else tr("Select filtered results"))
        usage_ready = self.category != "manifests" or (
            self.inventory is not None and not self.inventory.step and self.inventory.error is None)
        self.quick_select.setEnabled(bool(available) and usage_ready)
        count, shown = len(self.filtered), self.table.rowCount()
        self.scroll_note.setText(tr("Showing {0} of {1} · Scroll down to load more").format(shown, count))
        self.scroll_note.setVisible(shown < count and not self.loading)
        text = tr("{0} results · {1} selected").format(count, len(self.selected)) if mutable else tr("{0} results").format(count)
        if mutable and self.busy:
            text += "   " + tr("Cleanup is unavailable during an activity.")
        self.status.setText(text)

    def open_details(self, row, column):
        if self.category == "logs" and column == 6:
            key = self.filtered[row]["key"]
            self.window.switchTo(self.window.log_page)
            self.window.log_page.open_log(key)

    def preview(self):
        keys = tuple(dict.fromkeys(row["key"] for row in self.filtered if row["key"] in self.selected))
        category = self.category
        start, end = (picker.date.toString(Qt.DateFormat.ISODate) if picker.date.isValid() else tr("Any date")
                      for picker in (self.start, self.end))
        self.previewing = True
        self.preview_request += 1
        request = self.preview_request
        self.render_actions()
        self.submit(lambda: self.data.preview(category, keys),
                    lambda result: self.preview_finished(request, result, tr("{0} to {1} · Local dates").format(start, end)))

    def preview_finished(self, request, result, dates):
        if request != self.preview_request:
            return
        self.previewing = False
        if isinstance(result, Exception):
            self.note.setText(tr("Data operation failed: {0}").format(tr(str(result))))
            self.hint.show()
        else:
            self.confirm(result, dates)
        self.render_actions()

    def confirm(self, plan, dates):
        if (not self.isVisible() or self.busy or self.category != plan.category
                or self.selected != set(plan.keys)):
            return
        component_names = {}
        if plan.category == "components":
            for row in self.rows:
                if row["key"] in self.selected and row["name"]:
                    component_names.setdefault(row["key"], []).append(row["name"])
            component_names = {key: ", ".join(sorted(set(names))) for key, names in component_names.items()}
        dialog = CleanupDialog(plan, dates, self.window, component_names)
        if dialog.exec():
            self.window.launch(lambda: self.data.execute(plan), lambda retained: self.cleaned(plan.category, retained))
        dialog.deleteLater()

    def cleaned(self, category, retained):
        if category == "logs":
            self.window.log_page.refresh_runs()
        if category == "manifests":
            self.window.refresh_manifest_card()
        affected = {"manifests", "components"} if category == "manifests" else {category}
        for key in affected:
            self.invalidate_inventory(key)
        if self.category in affected:
            self.open_inventory()
        if retained:
            self.window.notifications.notify(tr("Cleanup completed with files remaining"),
                                             tr("Some isolated files remain at {0}").format(retained))
        else:
            self.window.notifications.notify(tr("Cleanup completed"), tr("The selected items were removed."))
