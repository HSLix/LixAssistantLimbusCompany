"""User GUI 数据与清理页及永久删除确认。"""

from threading import Event

from PySide6.QtCore import QSignalBlocker, QThreadPool, Qt, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QAbstractItemView, QHBoxLayout, QListWidgetItem, QTableWidgetItem, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel, CalendarPicker, CaptionLabel, CardWidget, ComboBox, FluentIcon,
    ListWidget, MessageBoxBase, Pivot, PrimaryPushButton, PushButton,
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

    def __init__(self, parent=None):
        super().__init__(parent)
        line = QHBoxLayout(self)
        line.setContentsMargins(16, 10, 16, 10)
        self.labels = []
        for _ in range(3):
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

    def __init__(self, plan, dates, parent):
        super().__init__(parent)
        logs = plan.category == "logs"
        self.widget.setMinimumWidth(550)
        title = tr("Permanently delete {0} run logs?") if logs else tr("Permanently delete {0} workflow versions?")
        self.viewLayout.addWidget(SubtitleLabel(title.format(len(plan.rows))))
        self.viewLayout.addWidget(CaptionLabel(dates))
        totals = Totals(self)
        if logs:
            imported = sum(row["imported"] for row in plan.rows)
            counts = [(tr("Local logs"), tr("{0} logs").format(len(plan.rows) - imported)),
                      (tr("Imported logs"), tr("{0} logs").format(imported))]
        else:
            counts = [(tr("Workflow versions"), tr("{0} versions").format(len(plan.rows))),
                      (tr("Unreferenced sources"), tr("{0} sources").format(len(plan.sources)))]
        totals.update_values([*counts, (tr("Estimated space freed"), _size(plan.size))])
        self.viewLayout.addWidget(totals)
        items = ListWidget()
        items.setAccessibleName(tr("Items to delete"))
        items.setFixedHeight(min(150, 39 * len(plan.rows) + 8))
        for row in plan.rows:
            if logs:
                text = f"{_log_name(row)}   ·   {_size(row['size'])}"
            else:
                text = f"{row['key'][:8]}   ·   {row['notes'].splitlines()[0] if row['notes'] else _date(row['date'])}"
            item = QListWidgetItem(text)
            item.setToolTip(row["notes"] if not logs else text)
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
        retained = (tr("Usage summaries, Workflow Ledger and Agent sessions are kept.") if logs else
                    tr("Default, latest and sources referenced by retained versions are kept."))
        warning = (tr("Deleted detailed logs and screenshots cannot be recovered.") if logs else
                   tr("Deleted versions cannot be selected for runs or rollback."))
        self.viewLayout.addWidget(BodyLabel(retained))
        notice = BodyLabel(warning)
        notice.setStyleSheet("color: #c64b42;")
        self.viewLayout.addWidget(notice)
        self.yesButton.setText(tr("Delete permanently"))
        self.yesButton.setStyleSheet("QPushButton {background:#a5322b;color:white;}"
                                     "QPushButton:hover {background:#902923;}"
                                     "QPushButton:focus {border:2px solid #ec9a95;}")
        self.yesButton.setAutoDefault(False)
        self.yesButton.setDefault(False)
        self.cancelButton.setText(tr("Cancel"))
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
        self.offset, self.serial = 0, 0
        self.generation = 0
        self.tasks = {}
        self.size_cancelled = Event()
        self.destroyed.connect(lambda *_: self.size_cancelled.set())
        self.loading, self.busy, self.previewing = False, False, False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 22, 28, 24)
        layout.setSpacing(14)
        layout.addWidget(TitleLabel(tr("Data & Cleanup")))
        self.tabs = Pivot(self)
        titles = (tr("Run logs"), tr("Workflow versions"), tr("Components"), tr("Asset inventory"))
        for key, title in zip(self.CATEGORIES, titles):
            self.tabs.addItem(key, title, onClick=lambda *_, key=key: self.switch_category(key))
        self.tabs.setCurrentItem(self.category)
        layout.addWidget(self.tabs)
        self.totals = Totals(self)
        layout.addWidget(self.totals)

        controls = QHBoxLayout()
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
        for picker in (self.start, self.end):
            picker.dateChanged.connect(self.filter_changed)
        controls.addWidget(self.dates)
        self.search = SearchLineEdit()
        self.search.setFixedWidth(250)
        self.search.textChanged.connect(self.filter_changed)
        controls.addWidget(self.search)
        controls.addStretch(1)
        self.filter = ComboBox()
        self.filter.currentIndexChanged.connect(self.filter_changed)
        controls.addWidget(self.filter)
        refresh = PushButton(FluentIcon.SYNC, tr("Refresh"))
        refresh.clicked.connect(self.refresh)
        controls.addWidget(refresh)
        layout.addLayout(controls)
        self.note = CaptionLabel()
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
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
        layout.addWidget(self.table, 1)
        footer = QHBoxLayout()
        self.status = BodyLabel()
        self.status.setWordWrap(True)
        footer.addWidget(self.status, 1)
        self.select_all = PushButton(tr("Select filtered results"))
        self.select_all.clicked.connect(self.toggle_all)
        footer.addWidget(self.select_all)
        self.previous = PushButton(tr("Previous"))
        self.previous.clicked.connect(lambda: self.go_to(self.offset - self.PAGE_SIZE))
        footer.addWidget(self.previous)
        self.next = PushButton(tr("Next"))
        self.next.clicked.connect(lambda: self.go_to(self.offset + self.PAGE_SIZE))
        footer.addWidget(self.next)
        self.preview_button = PrimaryPushButton(tr("Preview cleanup"))
        self.preview_button.clicked.connect(self.preview)
        footer.addWidget(self.preview_button)
        layout.addLayout(footer)
        self.configure()

    def configure(self):
        logs, versions, components, assets = (self.category == key for key in self.CATEGORIES)
        self.sort_column = 3 if logs else 2 if versions else 3
        self.descending = True
        self.dates.setVisible(logs or versions)
        self.search.setVisible(components or assets)
        search = tr("Search Component name or version") if components else tr("Search Asset name")
        self.search.setPlaceholderText(search)
        self.search.setAccessibleName(search)
        self.filter.setVisible(not assets)
        entries = ([tr("All sources"), tr("Local"), tr("Imported")] if logs else
                   [tr("All versions"), tr("Eligible for cleanup"), tr("Protected")] if versions else
                   [tr("All roles"), tr("Plan"), tr("Task Workflow"), tr("Subworkflow"), tr("Step"), tr("Recovery Rule")])
        with QSignalBlocker(self.search), QSignalBlocker(self.filter):
            self.search.clear()
            self.filter.clear()
            self.filter.addItems(entries)
        self.select_all.setVisible(logs or versions)
        self.preview_button.setVisible(logs or versions)

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def switch_category(self, category):
        if category != self.category:
            self.category = category
            self.configure()
            self.refresh()

    def submit(self, operation, callback, kind):
        self.serial += 1
        task = ReadTask(self.serial, operation)
        self.tasks[self.serial] = (task, self.generation, callback, kind)
        task.signals.done.connect(self.completed, Qt.ConnectionType.QueuedConnection)
        QThreadPool.globalInstance().start(task)

    @Slot(int, object)
    def completed(self, identity, result):
        _, generation, callback, kind = self.tasks.pop(identity)
        if generation != self.generation:
            return
        if kind == "inventory":
            self.loading = False
        elif kind == "preview":
            self.previewing = False
        if isinstance(result, Exception):
            self.note.setText(tr("Data operation failed: {0}").format(tr(str(result))))
            self.note.show()
            self.render_actions()
        else:
            callback(result)

    def refresh(self):
        self.generation += 1
        self.size_cancelled.set()
        self.size_cancelled = Event()
        self.rows, self.filtered, self.selected = [], [], set()
        self.eligible_keys.clear()
        self.loading, self.previewing = True, False
        self.note.setText(tr("Loading data…"))
        self.note.show()
        self.totals.update_values([("", "—")] * 3)
        self.go_to(0)
        category = self.category
        self.submit(lambda: self.data.inventory(category, with_usage=False),
                    lambda result: self.show_inventory(result, collecting_usage=category in {"manifests", "components"}),
                    "inventory")

    def show_inventory(self, result, *, collecting_usage=False, offset=0):
        self.rows, invalid = result
        rows = self.rows
        if self.category == "logs":
            imported = sum(row["imported"] for row in rows)
            values = [(tr("Local logs"), tr("{0} logs").format(len(rows) - imported)),
                      (tr("Imported logs"), tr("{0} logs").format(imported)),
                      (tr("Detailed log size"), _size(None if rows else 0))]
            notice = tr("Calculating detailed log size…") if rows else ""
        elif self.category == "manifests":
            values = [(tr("Published versions"), tr("{0} versions").format(len(rows))),
                      (tr("Protected versions"), tr("{0} versions").format(sum(row["default"] or row["latest"] for row in rows))),
                      (tr("Referenced Component versions"), tr("{0} sources").format(len({digest for row in rows for _, digest in row["members"]})))]
            notice = tr("Run counts cover available local logs and usage summaries.")
        elif self.category == "components":
            values = [(tr("Logical names"), tr("{0} names").format(len({row["name"] for row in rows if row["name"]}))),
                      (tr("Component source versions"), tr("{0} sources").format(len({row["key"] for row in rows}))),
                      (tr("Versions with recorded calls"), "—" if collecting_usage and rows else
                       tr("{0} sources").format(len({row["key"] for row in rows if row["count"]})))]
            notice = tr("Calls are counted by source version from available local logs and usage summaries.")
        else:
            values = [(tr("Asset names"), tr("{0} names").format(len(rows))),
                      (tr("Template images"), tr("{0} images").format(sum(row["count"] for row in rows))),
                      (tr("Image size"), _size(sum(row["size"] for row in rows)))]
            notice = tr("Last match is read from the Asset usage index.")
        self.totals.update_values(values)
        if collecting_usage and rows:
            notice = tr("Calculating usage from local Run history…")
        if invalid:
            notice = (notice + " " + tr("{0} records could not be read. Statistics may be incomplete.").format(invalid)).strip()
        self.note.setText(notice)
        self.note.setVisible(bool(notice))
        self.filter_changed()
        if offset:
            self.go_to(min(offset, max(0, (len(self.filtered) - 1) // self.PAGE_SIZE * self.PAGE_SIZE)))
        if self.category == "logs" and rows:
            cancelled = self.size_cancelled
            self.submit(lambda: self.data.log_sizes(rows, cancelled=cancelled),
                        lambda sizes: self.show_log_sizes(sizes, invalid), "sizes")
        elif collecting_usage and rows:
            category = self.category
            self.submit(lambda: self.data.inventory(category),
                        lambda result: self.show_inventory(result, offset=self.offset), "usage")

    def show_log_sizes(self, sizes, unreadable):
        """补齐空间估算时保留日期、选择与当前分页。"""
        for row in self.rows:
            row["size"] = sizes.get(row["key"])
        missing = len(self.rows) - len(sizes)
        value = _size(sum(sizes.values())) if sizes else "—"
        if missing and sizes:
            value = tr("{0} (partial)").format(value)
        self.totals.labels[2][1].setText(value)
        notice = ""
        if unreadable:
            notice = tr("{0} records could not be read. Statistics may be incomplete.").format(unreadable)
        if missing:
            notice = (notice + " " + tr("Size unavailable for {0} run logs.").format(missing)).strip()
        self.note.setText(notice)
        self.note.setVisible(bool(notice))
        if self.sort_column == 5:
            self.sort_rows()
        self.go_to(self.offset)

    def clear_dates(self):
        self.start.reset()
        self.end.reset()
        self.filter_changed()

    def eligible(self, row):
        if self.category == "logs":
            return row["date"] is not None
        return self.category == "manifests" and not (row["default"] or row["latest"])

    def filter_changed(self):
        start, end = self.start.date, self.end.date
        choice = self.filter.currentIndex()
        term = self.search.text().casefold().strip() if self.search.isVisible() else ""
        rows = []
        for row in self.rows:
            if self.category in {"logs", "manifests"}:
                stamp = row["date"]
                if start.isValid() or end.isValid():
                    if stamp is None:
                        continue
                    date = stamp.astimezone().date()
                    if (start.isValid() and date < start.toPython()) or (end.isValid() and date > end.toPython()):
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
        self.go_to(0)

    def sort_by(self, column):
        if self.category == "logs" and column in (0, 6) or self.category == "manifests" and column == 0:
            return
        self.descending = not self.descending if column == self.sort_column else False
        self.sort_column = column
        self.sort_rows()
        self.go_to(0)

    def sort_rows(self):
        fields = {
            "logs": (None, "run_id", "imported", "date", "status", "size"),
            "manifests": (None, "notes", "date", "count", "last", "latest"),
            "components": ("name", "key", "references", "count", "last"),
            "assets": ("key", "count", "size", "last"),
        }
        field = fields[self.category][self.sort_column]
        known = [row for row in self.filtered if row[field] is not None]
        known.sort(key=lambda row: row[field], reverse=self.descending)
        self.filtered = known + [row for row in self.filtered if row[field] is None]

    def go_to(self, offset):
        self.offset = max(0, offset)
        rows = self.filtered[self.offset:self.offset + self.PAGE_SIZE]
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
            headers = ("", tr("Version / release notes"), tr("Release date"), tr("Run count"), tr("Last used"), tr("Cleanup status"))
            widths = (35, 246, 145, 102, 152, 120)
            values = [(None, f"{row['key'][:8]}   {row['notes'].splitlines()[0] if row['notes'] else ''}",
                       _date(row["date"]) + (f" · {tr('File date')}" if row["file_date"] else ""),
                       _count(row["count"]), _date(row["last"], True),
                       " · ".join(label for flag, label in ((row["default"], tr("Default")), (row["latest"], tr("Latest")),
                                  (not self.eligible(row), tr("Protected"))) if flag) or tr("Eligible for cleanup"))
                      for row in rows]
        elif self.category == "components":
            headers = (tr("Component"), tr("Source version"), tr("Referenced by"), tr("Calls"), tr("Last used"))
            widths = (258, 133, 120, 105, 160)
            values = [(row["name"] or tr("Unknown name"), row["key"].removeprefix("sha256:")[:8],
                       str(row["references"]), _count(row["count"]), _date(row["last"], True)) for row in rows]
        else:
            headers = (tr("Asset name"), tr("Template images"), tr("Size"), tr("Last match"))
            widths = (320, 135, 130, 160)
            values = [(row["key"], str(row["count"]), _size(row["size"]), _date(row["last"], True)) for row in rows]
        with QSignalBlocker(self.table):
            self.table.clear()
            self.table.setColumnCount(len(headers))
            self.table.setHorizontalHeaderLabels(headers)
            header = self.table.horizontalHeader()
            header.setSortIndicator(self.sort_column, Qt.SortOrder.DescendingOrder if self.descending else Qt.SortOrder.AscendingOrder)
            header.setSortIndicatorShown(True)
            self.table.setRowCount(len(rows))
            for column, width in enumerate(widths):
                self.table.setColumnWidth(column, width)
            for index, (row, cells) in enumerate(zip(rows, values)):
                for column, text in enumerate(cells):
                    item = QTableWidgetItem(text or "")
                    if text is None:
                        item.setCheckState(Qt.CheckState.Checked if row["key"] in self.selected else Qt.CheckState.Unchecked)
                        if not self.eligible(row):
                            item.setFlags(item.flags() & ~(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable))
                    elif self.category in {"components", "manifests"} and column == 1:
                        item.setToolTip(row["key"] + ("\n" + row["notes"] if row.get("notes") else ""))
                    elif self.category == "logs" and column == 6:
                        item.setForeground(QColor("#39b9cc" if self.palette().window().color().lightness() < 128 else "#005fa8"))
                    self.table.setItem(index, column, item)
        self.render_actions()

    def selection_changed(self, item):
        if item.column() or self.category not in {"logs", "manifests"}:
            return
        row = self.filtered[self.offset + item.row()]
        if self.eligible(row):
            if item.checkState() == Qt.CheckState.Checked:
                self.selected.add(row["key"])
            else:
                self.selected.discard(row["key"])
        self.render_actions()

    def toggle_all(self):
        self.selected = set() if self.eligible_keys == self.selected else self.eligible_keys.copy()
        self.go_to(self.offset)

    def render_actions(self, busy=None):
        if busy is not None:
            self.busy = busy
        mutable = self.category in {"logs", "manifests"}
        available = self.eligible_keys
        self.preview_button.setEnabled(bool(self.selected) and not (self.busy or self.loading or self.previewing))
        self.select_all.setEnabled(bool(available))
        self.select_all.setText(tr("Clear selection") if available and available == self.selected else tr("Select filtered results"))
        self.previous.setVisible(self.offset > 0)
        self.next.setVisible(self.offset + self.PAGE_SIZE < len(self.filtered))
        count = len(self.filtered)
        text = tr("{0} results · {1} selected").format(count, len(self.selected)) if mutable else tr("{0} results").format(count)
        if count > self.PAGE_SIZE:
            text += "   " + tr("Showing {0}–{1}").format(self.offset + 1, min(self.offset + self.PAGE_SIZE, count))
        if mutable and self.busy:
            text += "   " + tr("Cleanup is unavailable during an activity.")
        self.status.setText(text)

    def open_details(self, row, column):
        if self.category == "logs" and column == 6:
            key = self.filtered[self.offset + row]["key"]
            self.window.switchTo(self.window.log_page)
            self.window.log_page.open_log(key)

    def preview(self):
        keys = tuple(row["key"] for row in self.filtered if row["key"] in self.selected)
        category = self.category
        start, end = (picker.date.toString(Qt.DateFormat.ISODate) if picker.date.isValid() else tr("Any date")
                      for picker in (self.start, self.end))
        self.previewing = True
        self.render_actions()
        self.submit(lambda: self.data.preview(category, keys),
                    lambda plan: self.confirm(plan, tr("{0} to {1} · Local dates").format(start, end)), "preview")

    def confirm(self, plan, dates):
        if (not self.isVisible() or self.busy or self.category != plan.category
                or self.selected != set(plan.keys)):
            self.render_actions()
            return
        dialog = CleanupDialog(plan, dates, self.window)
        if dialog.exec():
            self.window.launch(lambda: self.data.execute(plan), self.cleaned)
        dialog.deleteLater()
        self.render_actions()

    def cleaned(self, retained):
        self.window.log_page.refresh_runs()
        self.window.refresh_manifest_card()
        self.refresh()
        if retained:
            self.window.notifications.notify(tr("Cleanup completed with files remaining"),
                                             tr("Some isolated files remain at {0}").format(retained))
        else:
            self.window.notifications.notify(tr("Cleanup completed"), tr("The selected items were removed."))
