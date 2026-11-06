"""General Settings 分享向导；四类别审查、资源冲突及统一人工提交。"""

from pathlib import Path
import time
from typing import TypeVar, Callable, cast

from PySide6.QtCore import Qt, Signal, Slot, QEventLoop
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QStackedWidget, QWidget,
    QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator, QListWidget, QListWidgetItem,
    QScrollArea, QFileDialog, QMessageBox, QProgressBar, QApplication)
from qfluentwidgets import (BodyLabel, TitleLabel, PushButton, PrimaryPushButton, PlainTextEdit,
                            CheckBox, ComboBox, SegmentedWidget)

from .i18n import tr
from .developer_gui import Operation
from .file_content import file_operation, image_preview, content_bytes, ResourceUnknown, content_hash, require_memory

from .page_packages import PageSnapshot
from .page_preview import PagePreviewDialog, PreviewRequest
from .sharing import (KINDS, SharingPackage, asset_files, build_export, catalog, image_size,
    import_selected, inspect_objects, installed_page, page_selection_errors, save_package,
    sharing_activity, strict_json)
from .user_pages import check_page_registration


class SharingWorker(Operation):
    """复用已有后台任务生命周期；文件操作的取消只在安全检查点生效。"""
    progress = Signal(object)
    allow_unknown_space = False
    result = None
    error = None

    def run(self):
        last = [0.0]
        def progress(done, total, name):
            now = time.monotonic()
            if now - last[0] >= .05 or total and done == total:
                last[0] = now
                self.progress.emit((done, total, name))
        with file_operation(lambda: self.cancel_requested, progress, allow_unknown_space=self.allow_unknown_space):
            try:
                self.result = self.operation()
            except BaseException as error:
                self.error = error


T = TypeVar("T")


def sharing_task(parent, operation: Callable[[], T], *, allow_unknown_space=False) -> T:
    """模态进度窗保持事件循环响应；取消须等 Worker 停止、完成清理再关闭。"""
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    quit_on_close = app.quitOnLastWindowClosed()
    app.setQuitOnLastWindowClosed(False)
    worker = SharingWorker(operation)
    worker.allow_unknown_space = allow_unknown_space or getattr(parent, "allow_unknown_space", False)
    class ProgressDialog(QDialog):
        @Slot(object)
        def update_progress(self, value):
            done, total, name = value
            if total:
                bar.setRange(0, 1000)
                bar.setValue(int(done * 1000 / total))
            label.setText(tr("Processing: {0}").format(name) if name else tr("Checking files and available resources…"))
        def reject(self):
            worker.cancel()
            cancel.setEnabled(False)
            label.setText(tr("Cancelling…"))
        def closeEvent(self, event):
            if worker.isRunning():
                self.reject()
                event.ignore()
            else:
                super().closeEvent(event)
    dialog = ProgressDialog(parent)
    dialog.setWindowTitle(tr("Processing sharing files"))
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    dialog.resize(520, 160)
    layout = QVBoxLayout(dialog)
    label = notice(tr("Checking files and available resources…"))
    layout.addWidget(label)
    bar = QProgressBar()
    bar.setRange(0, 0)
    layout.addWidget(bar)
    cancel = PushButton(tr("Cancel"))
    cancel.clicked.connect(dialog.reject)
    layout.addWidget(cancel)
    worker.progress.connect(dialog.update_progress)
    worker.finished.connect(dialog.accept)
    worker.start()
    dialog.show()
    # 保持取消／绘制事件可用，即使宿主此前退出过 Qt 的嵌套模态循环。
    while not worker.wait(5):
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 5)
    app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 5)
    dialog.accept()
    worker.progress.disconnect(dialog.update_progress)
    dialog.deleteLater()
    app.setQuitOnLastWindowClosed(quit_on_close)
    error, result = worker.error, worker.result
    worker.error = worker.result = None
    worker.operation = lambda: None
    worker.deleteLater()
    if error is not None:
        if isinstance(error, ResourceUnknown) and str(error).startswith("无法获取磁盘") and not worker.allow_unknown_space:
            if QMessageBox.question(parent, tr("Disk capacity unknown"),
                    tr("Available disk space could not be checked. Continue anyway? Writes may fail."),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                parent.allow_unknown_space = True
                return sharing_task(parent, operation, allow_unknown_space=True)
        raise error
    return cast(T, result)


def title(kind):
    return {"workflow": tr("Workflow"), "assets": tr("Assets"),
            "pages": tr("Extension Pages"), "history": tr("Agent History")}[kind]


def notice(text):
    label = BodyLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


def details(text=""):
    box = PlainTextEdit()
    box.setReadOnly(True)
    box.setPlainText(text)
    return box


def tree_items(tree):
    iterator = QTreeWidgetItemIterator(tree)
    while iterator.value():
        yield iterator.value()
        iterator += 1


def asset_tree(names):
    """目录节点批量选择，单独叶节点表示本层逻辑组，兼容父层也有图片。"""
    tree = QTreeWidget()
    tree.setHeaderHidden(True)
    nodes = {}
    for name in sorted(names):
        parent, prefix = tree.invisibleRootItem(), ""
        for segment in name.split("/"):
            prefix = prefix + "/" + segment if prefix else segment
            if prefix not in nodes:
                node = QTreeWidgetItem(parent, [segment])
                node.setFlags(node.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate)
                nodes[prefix] = node
            parent = nodes[prefix]
        leaf = QTreeWidgetItem(parent, [tr("Images and tags")])
        leaf.setData(0, Qt.ItemDataRole.UserRole, name)
        leaf.setFlags(leaf.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        leaf.setCheckState(0, Qt.CheckState.Checked)
    tree.expandToDepth(1)
    return tree


def check_list(names, checked):
    widget = QListWidget()
    for name in names:
        item = QListWidgetItem(name, widget)
        item.setData(Qt.ItemDataRole.UserRole, name)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
    return widget


def selected_list(widget):
    return [widget.item(index).data(Qt.ItemDataRole.UserRole) for index in range(widget.count())
            if widget.item(index).checkState() == Qt.CheckState.Checked]


class ExportDialog(QDialog):
    """选择对象后冻结实际文件，第二步只审阅该快照并保存 ZIP。"""

    def __init__(self, window):
        super().__init__(window)
        self.window_host, self.manager = window, window.host.manager
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowTitle(tr("Export Package"))
        self.resize(920, 720)
        layout = QVBoxLayout(self)
        layout.addWidget(TitleLabel(tr("Export Package")))
        self.step = notice(tr("Step 1 of 2 · Select contents"))
        layout.addWidget(self.step)
        layout.addWidget(notice(tr("Only selected objects are shared. Assets are independent of Workflow. Agent History is off by default.")))
        layout.addWidget(notice(tr("Assets are selected by default. Deselect groups you do not want to share.")))
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)
        first = QWidget()
        choices = QVBoxLayout(first)
        self.selectors = {}
        available = catalog(self.manager)
        self.select_tabs, panels = SegmentedWidget(), QStackedWidget()
        tabs = self.select_tabs
        choices.addWidget(tabs)
        choices.addWidget(panels, 1)
        for kind in KINDS:
            tabs.addItem(kind, title(kind))
            widget = asset_tree(available[kind]) if kind == "assets" else check_list(available[kind], False)
            self.selectors[kind] = widget
            panel = QWidget()
            column = QVBoxLayout(panel)
            buttons = QHBoxLayout()
            for label, checked in ((tr("Select all"), True), (tr("Select none"), False)):
                button = PushButton(label)
                button.clicked.connect(lambda _, widget=widget, checked=checked: self.set_export_selection(widget, checked))
                buttons.addWidget(button)
            column.addLayout(buttons)
            column.addWidget(widget, 1)
            panels.addWidget(panel)
            widget.itemChanged.connect(lambda *_: self.export_counts())
        tabs.currentItemChanged.connect(lambda key: panels.setCurrentIndex(KINDS.index(key)))
        tabs.setCurrentItem("workflow")
        self.stack.addWidget(first)
        self.review = details()
        self.stack.addWidget(self.review)
        layout.addWidget(notice(tr("Privacy warning: conversations, screenshots, paths, source and resources may contain private information. No privacy scan is performed. Check before sharing.")))
        row = QHBoxLayout()
        self.back = PushButton(tr("Back"))
        self.back.clicked.connect(self.go_back)
        self.back.hide()
        row.addWidget(self.back)
        row.addStretch()
        cancel = PushButton(tr("Cancel"))
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        self.next = PrimaryPushButton(tr("Review contents"))
        self.next.clicked.connect(self.advance)
        row.addWidget(self.next)
        layout.addLayout(row)
        self.objects = None
        self.export_counts()

    def reject(self):
        self.objects = None
        super().reject()

    def export_counts(self):
        selection = self.selection()
        for kind, widget in self.selectors.items():
            count = sum(item.data(0, Qt.ItemDataRole.UserRole) is not None for item in tree_items(widget)) if kind == "assets" else widget.count()
            self.select_tabs.setItemText(kind, title(kind) + f" ({len(selection[kind])}/{count})")

    def set_export_selection(self, widget, checked):
        widget.blockSignals(True)
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        if isinstance(widget, QTreeWidget):
            for item in tree_items(widget):
                if item.data(0, Qt.ItemDataRole.UserRole) is not None:
                    item.setCheckState(0, state)
        else:
            for index in range(widget.count()):
                widget.item(index).setCheckState(state)
        widget.blockSignals(False)
        self.export_counts()

    def selection(self):
        result = {kind: selected_list(widget) for kind, widget in self.selectors.items() if kind != "assets"}
        result["assets"] = [item.data(0, Qt.ItemDataRole.UserRole) for item in tree_items(self.selectors["assets"])
                            if item.data(0, Qt.ItemDataRole.UserRole) is not None and item.checkState(0) == Qt.CheckState.Checked]
        return result

    def go_back(self):
        self.stack.setCurrentIndex(0)
        self.objects = None
        self.back.hide()
        self.step.setText(tr("Step 1 of 2 · Select contents"))
        self.next.setText(tr("Review contents"))

    def advance(self):
        try:
            if self.objects is None:
                selection = self.selection()
                self.objects = sharing_task(self, lambda: build_export(self.manager, selection))
                lines = []
                for obj in self.objects:
                    lines.append(f"{title(obj['kind'])} · {obj['id']}")
                    if obj["kind"] == "history":
                        lines.append(tr("Candidate and page drafts are snapshots taken at export time, not per-round versions."))
                        if "snapshot-info.json" in obj["files"]:
                            lines.append(strict_json(obj["files"]["snapshot-info.json"])["captured_at"])
                        if "missing-evidence.json" in obj["files"]:
                            lines.append(tr("Missing evidence: {0}").format(strict_json(obj["files"]["missing-evidence.json"])["missing"]))
                    lines.extend(f"  {name}  ({len(content)} bytes)" for name, content in sorted(obj["files"].items()))
                self.review.setPlainText("\n".join(lines))
                self.stack.setCurrentIndex(1)
                self.step.setText(tr("Step 2 of 2 · Review and save"))
                self.next.setText(tr("Save ZIP…"))
                self.back.show()
                return
            filename, _ = QFileDialog.getSaveFileName(self, tr("Save shared package"), "lalc-sharing.zip", "ZIP (*.zip)")
            if filename:
                sharing_task(self, lambda: save_package(self.objects, filename))
                self.objects = None
                self.accept()
        except InterruptedError:
            return
        except Exception as error:
            QMessageBox.warning(self, tr("Export failed"), self.window_host.clean_details(str(error)))


class ImportedPageReview:
    """只适配已检查的导入页面，不创建 Developer Session 或提前安装。"""

    def __init__(self, root, obj):
        self.root, self.obj = root, obj

    def package_path(self, filename, scope="installed"):
        return installed_page(self.root, filename)

    def check_registration(self, snapshot, page_id, task_id):
        target = installed_page(self.root, snapshot["filename"])
        check_page_registration(self.root / "pages", target if target.is_file() else target / "page.py", page_id, task_id)


class ImportDialog(QDialog):
    """查看、选择、静态检查、页面 Review 和最终确认分别记录。"""

    def __init__(self, window, package):
        super().__init__(window)
        self.window_host, self.manager, self.package = window, window.host.manager, package
        self.allow_unknown_space = getattr(window, "allow_unknown_space", False)
        self.selected = {obj["number"] for obj in package.objects}
        self.reviewed, self.review_failed, self.asset_actions = {}, {}, {}
        self.viewed, self.checks = set(), {}
        self.by_kind = {kind: [obj for obj in package.objects if obj["kind"] == kind] for kind in KINDS}
        self.selection_counts = {}
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowTitle(tr("Import Package"))
        self.resize(1080, 800)
        layout = QVBoxLayout(self)
        layout.addWidget(TitleLabel(tr("Import Package")))
        layout.addWidget(notice(package.path.name))
        self.counter = notice("")
        layout.addWidget(self.counter)
        self.tabs, self.stack = SegmentedWidget(), QStackedWidget()
        layout.addWidget(self.tabs)
        layout.addWidget(self.stack, 1)
        self.workflow_combo = ComboBox()
        self.workflow_select = CheckBox(tr("Import this Manifest"))
        self.workflow_details = details()
        workflow = self.panel("workflow")
        workflow.addWidget(self.workflow_combo)
        workflow.addWidget(self.workflow_select)
        workflow.addWidget(self.workflow_details, 1)
        for obj in self.by_kind["workflow"]:
            self.workflow_combo.addItem(obj["id"], userData=obj["number"])
        self.workflow_combo.currentIndexChanged.connect(self.render_workflow)
        self.workflow_select.toggled.connect(lambda value: self.choose(self.workflow_combo.currentData(), value))
        assets = self.panel("assets")
        self.asset_count = notice("")
        assets.addWidget(self.asset_count)
        actions = QHBoxLayout()
        for label, action in ((tr("Replace all conflicts"), "replace"), (tr("Skip all conflicts"), "skip")):
            button = PushButton(label)
            button.clicked.connect(lambda _, action=action: self.asset_action(action))
            actions.addWidget(button)
        assets.addLayout(actions)
        row = QHBoxLayout()
        self.assets = asset_tree([obj["id"] for obj in self.by_kind["assets"]])
        row.addWidget(self.assets, 1)
        self.asset_side = QVBoxLayout()
        self.asset_summary = notice(tr("Select an Asset to inspect conflicts."))
        self.asset_side.addWidget(self.asset_summary)
        self.asset_more = PushButton(tr("Show conflict details"))
        self.asset_more.setCheckable(True)
        self.asset_side.addWidget(self.asset_more)
        self.asset_detail_widget = QWidget()
        self.asset_detail_layout = QVBoxLayout(self.asset_detail_widget)
        self.asset_displayed = None
        self.asset_scroll = QScrollArea()
        self.asset_scroll.setWidgetResizable(True)
        self.asset_scroll.setWidget(self.asset_detail_widget)
        self.asset_scroll.hide()
        self.asset_more.toggled.connect(self.asset_scroll.setVisible)
        self.asset_more.toggled.connect(self.render_asset)
        self.asset_side.addWidget(self.asset_scroll, 1)
        row.addLayout(self.asset_side, 2)
        assets.addLayout(row, 1)
        self.assets.itemChanged.connect(self.asset_changed)
        self.assets.currentItemChanged.connect(self.render_asset)
        pages = self.panel("pages")
        page_row = QHBoxLayout()
        self.pages = check_list([obj["id"] for obj in self.by_kind["pages"]], True)
        page_row.addWidget(self.pages, 1)
        page_side = QVBoxLayout()
        self.page_details = details()
        page_side.addWidget(self.page_details, 1)
        self.review_page = PushButton(tr("Review Page…"))
        self.review_page.clicked.connect(self.open_page_review)
        page_side.addWidget(self.review_page)
        page_side.addWidget(notice(tr("Review runs page Python in this application. Approval does not install it. Unreviewed pages require an extra installation confirmation.")))
        page_row.addLayout(page_side, 2)
        pages.addLayout(page_row)
        self.pages.itemChanged.connect(lambda item: self.choose(self.number("pages", item.data(Qt.ItemDataRole.UserRole)), item.checkState() == Qt.CheckState.Checked))
        self.pages.currentRowChanged.connect(self.render_page)
        history = self.panel("history")
        self.histories = check_list([obj["id"] for obj in self.by_kind["history"]], True)
        history.addWidget(notice(tr("Imported history is read-only external knowledge. Conversations, baseline, Candidate and page drafts cannot restore a Session or replay tools.")))
        history.addWidget(self.histories, 1)
        self.history_details = details()
        history.addWidget(self.history_details, 1)
        self.histories.itemChanged.connect(lambda item: self.choose(self.number("history", item.data(Qt.ItemDataRole.UserRole)), item.checkState() == Qt.CheckState.Checked))
        self.histories.currentRowChanged.connect(self.render_history)
        self.error_box = notice("")
        layout.addWidget(self.error_box)
        self.trust = CheckBox(tr("I understand imported code and records are untrusted."))
        self.trust.toggled.connect(self.update_state)
        layout.addWidget(self.trust)
        controls = QHBoxLayout()
        recheck = PushButton(tr("Recheck"))
        recheck.clicked.connect(self.recheck)
        controls.addWidget(recheck)
        controls.addStretch()
        cancel = PushButton(tr("Cancel"))
        cancel.clicked.connect(self.reject)
        controls.addWidget(cancel)
        self.commit = PrimaryPushButton(tr("Import Selected"))
        self.commit.clicked.connect(self.submit)
        controls.addWidget(self.commit)
        layout.addLayout(controls)
        self.tabs.currentItemChanged.connect(self.visit)
        self.recheck()
        first = next(kind for kind in KINDS if self.by_kind[kind])
        self.tabs.setCurrentItem(first)
        self.visit(first)
        if self.pages.count():
            self.pages.setCurrentRow(0)
        if self.histories.count():
            self.histories.setCurrentRow(0)
        self.result_data = None

    def done(self, result):
        self.checks.clear()
        super().done(result)

    def panel(self, kind):
        self.tabs.addItem(kind, title(kind))
        widget = QWidget()
        layout = QVBoxLayout(widget)
        row = QHBoxLayout()
        self.selection_counts[kind] = notice("")
        row.addWidget(self.selection_counts[kind], 1)
        for label, checked in ((tr("Select all"), True), (tr("Select none"), False)):
            button = PushButton(label)
            button.clicked.connect(lambda _, kind=kind, checked=checked: self.set_kind_selected(kind, checked))
            row.addWidget(button)
        layout.addLayout(row)
        self.stack.addWidget(widget)
        return layout

    def set_kind_selected(self, kind, checked):
        numbers = {obj["number"] for obj in self.by_kind[kind]}
        self.selected.update(numbers) if checked else self.selected.difference_update(numbers)
        self.sync_selection()
        self.render_workflow()
        self.update_state()

    def number(self, kind, identity):
        return next((obj["number"] for obj in self.by_kind[kind] if obj["id"] == identity), None)

    def choose(self, number, checked):
        if number is not None:
            self.selected.add(number) if checked else self.selected.discard(number)
        self.update_state()

    def visit(self, kind):
        self.stack.setCurrentIndex(KINDS.index(kind))
        self.viewed.add(kind)
        self.update_state()

    def recheck(self):
        try:
            old = self.checks
            self.checks = sharing_task(self, lambda: inspect_objects(self.manager, self.package))
            for obj in self.package.objects:
                number = obj["number"]
                if old.get(number, {}).get("before") != self.checks[number].get("before"):
                    self.reviewed.pop(number, None)
                    self.asset_actions.pop(number, None)
            self.inspection_error = ""
        except Exception as error:
            self.inspection_error = self.window_host.clean_details(str(error))
        self.render_workflow()
        self.render_page()
        self.render_history()
        self.render_asset()
        self.update_state()

    def object_text(self, obj):
        check = self.checks.get(obj["number"], {})
        lines = [obj["id"], *check.get("errors", [])]
        if obj["kind"] == "workflow":
            lines.extend([tr("Destination: {0}").format(self.manager.manifests_dir / f"{check.get('manifest_id', obj['id'])}.json"),
                          tr("No Default change or automatic execution. Assets are imported separately.")])
            if check.get("uuid_conflict"):
                lines.append(tr("UUID occupied. Proposed new UUID: {0}").format(check["manifest_id"]))
        elif obj["kind"] == "pages":
            lines.extend([tr("Destination: {0}").format(self.manager.data_root / "pages" / Path(obj["id"]).stem),
                          tr("Declared page identity: {0}").format(check.get("declarations", {})),
                          tr("Unreviewed runtime identity, loading and interface are not verified. Existing settings are kept. Reload manually after installation.")])
            if obj["number"] in self.reviewed:
                lines.append(tr("Reviewed page identity: {0}").format(self.reviewed[obj["number"]]["page_id"]))
        elif obj["kind"] == "history":
            lines.append(tr("Destination: {0}").format(self.manager.data_root / "knowledge/imported-agent-history" / check.get("content_hash", "")))
        lines.append(tr("Files (including dependencies):"))
        lines.extend(f"{name} · {record['size']} bytes · {record['sha256']}" for name, record in sorted(obj["files"].items()))
        return "\n".join(lines)

    def render_workflow(self, *_):
        number = self.workflow_combo.currentData()
        self.workflow_select.blockSignals(True)
        self.workflow_select.setChecked(number in self.selected)
        self.workflow_select.setEnabled(number is not None)
        self.workflow_select.blockSignals(False)
        obj = next((obj for obj in self.by_kind["workflow"] if obj["number"] == number), None)
        self.workflow_details.setPlainText(self.object_text(obj) if obj else tr("No contents in this category."))

    def page_object(self):
        row = self.pages.currentRow()
        return self.by_kind["pages"][row] if row >= 0 else None

    def render_page(self, *_):
        obj = self.page_object()
        self.review_page.setEnabled(obj is not None and not self.checks.get(obj["number"], {}).get("errors"))
        self.page_details.setPlainText(self.object_text(obj) if obj else tr("No contents in this category."))

    def render_history(self, *_):
        row = self.histories.currentRow()
        self.history_details.setPlainText(self.object_text(self.by_kind["history"][row]) if row >= 0 else tr("No contents in this category."))

    def asset_changed(self, item, _):
        identity = item.data(0, Qt.ItemDataRole.UserRole)
        if identity is not None:
            self.choose(self.number("assets", identity), item.checkState(0) == Qt.CheckState.Checked)

    def asset_action(self, action):
        self.asset_actions = {number: action for number, check in self.checks.items() if check.get("conflict")}
        self.render_asset()
        self.update_state()

    def render_asset(self, *_):
        if not hasattr(self, "asset_detail_layout"):
            return
        while self.asset_detail_layout.count():
            item = self.asset_detail_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        current = self.assets.currentItem()
        identity = current.data(0, Qt.ItemDataRole.UserRole) if current else None
        if identity != self.asset_displayed:
            self.asset_more.setChecked(False)
            self.asset_displayed = identity
        obj = next((obj for obj in self.by_kind["assets"] if obj["id"] == identity), None)
        if obj is None:
            self.asset_summary.setText(tr("Select an Asset to inspect conflicts."))
            return
        check = self.checks.get(obj["number"], {})
        try:
            old = asset_files(self.manager.data_root, identity) or {}
            new = self.package.files(obj)
            changed = [name for name in sorted(set(old) | set(new)) if old.get(name) != new.get(name)]
            action = self.asset_actions.get(obj["number"])
            self.asset_summary.setText(tr("{0}: {1} changed files. Action: {2}").format(identity, len(changed), tr("Replace") if action == "replace" else tr("Skip") if action == "skip" else "—"))
            if not self.asset_more.isChecked():
                return
            self.asset_detail_layout.addWidget(notice("\n".join(changed) or tr("Same content")))
            def prepare_previews():
                previews, used = {}, 0
                for files in (old, new):
                    for name, content in files.items():
                        if name == "asset-tag.json" or content_hash(content) in previews:
                            continue
                        try:
                            preview = image_preview(content, (240, 160))
                            require_memory((used + len(preview)) * 4)
                            used += len(preview)
                            previews[content_hash(content)] = preview
                        except InterruptedError:
                            raise
                        except (OSError, ValueError):
                            previews[content_hash(content)] = None
                return previews
            try:
                previews = sharing_task(self, prepare_previews)
            except InterruptedError:
                self.asset_more.setChecked(False)
                return
            for name in sorted(set(old) | set(new)):
                if name == "asset-tag.json":
                    self.asset_detail_layout.addWidget(notice(name))
                    for label, files in ((tr("Current images"), old), (tr("Imported images"), new)):
                        self.asset_detail_layout.addWidget(notice(label + ": " + files.get(name, b"").decode("utf-8", errors="replace")))
                    continue
                row = QHBoxLayout()
                for label, files in ((tr("Current images"), old), (tr("Imported images"), new)):
                    content = files.get(name)
                    column = QWidget()
                    column_layout = QVBoxLayout(column)
                    caption = notice(label + "\n" + name[:12] + "…" + name[-8:])
                    caption.setToolTip(name)
                    column_layout.addWidget(caption)
                    widget = notice(tr("Not included"))
                    widget.setMinimumHeight(170)
                    widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    column_layout.addWidget(widget)
                    if content:
                        try:
                            preview = previews.get(content_hash(content))
                            if preview is None:
                                raise ValueError("Preview unavailable")
                            pixmap = QPixmap()
                            pixmap.loadFromData(preview)
                            widget.setPixmap(pixmap.scaled(240, 160, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                            widget.setToolTip(label + "\n" + name)
                            widget.setAccessibleName(label + " " + name)
                        except Exception:
                            widget.setText(label + ": " + tr("Image preview unavailable"))
                    row.addWidget(column)
                holder = QWidget()
                holder.setLayout(row)
                self.asset_detail_layout.addWidget(holder)
        except Exception as error:
            self.asset_summary.setText(self.window_host.clean_details(str(error)))

    def update_state(self, *_):
        if not hasattr(self, "commit"):
            return
        for kind in KINDS:
            self.tabs.setItemText(kind, title(kind) + (" 🔴" if self.by_kind[kind] and kind not in self.viewed else ""))
            self.selection_counts[kind].setText(tr("{0}/{1} selected").format(sum(obj["number"] in self.selected for obj in self.by_kind[kind]), len(self.by_kind[kind])))
        nonempty = {kind for kind in KINDS if self.by_kind[kind]}
        self.counter.setText(tr("{0}/{1} categories viewed").format(len(self.viewed & nonempty), len(nonempty)))
        errors = [self.inspection_error] if getattr(self, "inspection_error", "") else []
        conflicts = 0
        for obj in self.package.objects:
            number = obj["number"]
            check = self.checks.get(number, {})
            if check.get("conflict"):
                conflicts += 1
                if number in self.selected and number not in self.asset_actions:
                    errors.append(tr("Choose Replace all conflicts or Skip all conflicts for Assets."))
            if number in self.selected:
                errors.extend(check.get("errors", []))
                if number in self.review_failed:
                    errors.append(self.review_failed[number])
        if self.checks:
            try:
                extra = page_selection_errors(self.manager, self.package, self.checks, self.selected, self.reviewed)
                errors.extend(message for messages in extra.values() for message in messages)
            except Exception as error:
                errors.append(self.window_host.clean_details(str(error)))
        count = sum(len(check.get("changed_files", [])) for check in self.checks.values() if check.get("conflict"))
        self.asset_count.setText(tr("Asset conflicts: {0} groups, {1} files").format(conflicts, count))
        self.assets.blockSignals(True)
        for item in tree_items(self.assets):
            identity = item.data(0, Qt.ItemDataRole.UserRole)
            if identity is not None:
                check = self.checks.get(self.number("assets", identity), {})
                status = tr("Check failed") if check.get("errors") else tr("Conflict") if check.get("conflict") else tr("Same content") if check.get("same") else tr("New")
                action = self.asset_actions.get(self.number("assets", identity))
                if action:
                    status += " · " + (tr("Replace") if action == "replace" else tr("Skip"))
                item.setText(0, tr("Images and tags") + " — " + status)
        self.assets.blockSignals(False)
        self.pages.blockSignals(True)
        for index, obj in enumerate(self.by_kind["pages"]):
            number = obj["number"]
            status = tr("Review failed") if number in self.review_failed else tr("Reviewed") if number in self.reviewed else tr("Not reviewed")
            name = self.checks.get(number, {}).get("declarations", {}).get("PAGE_NAME", obj["id"])
            name = name[:80] if isinstance(name, str) else obj["id"]
            self.pages.item(index).setText((name + " · " if name != obj["id"] else "") + obj["id"] + " — " + status)
        self.pages.blockSignals(False)
        self.error_box.setText("\n".join(dict.fromkeys(errors)))
        self.commit.setEnabled(bool(self.selected) and nonempty <= self.viewed and not errors and self.trust.isChecked())

    def open_page_review(self):
        obj = self.page_object()
        if obj is None:
            return
        number = obj["number"]
        check = self.checks[number]
        if check["errors"]:
            return
        package = check["package"]
        snapshot = {"filename": obj["id"], "replace": check["before"] is not None,
                    "source": content_bytes(package.files["page.py"]), "package": package, "sha256": package.sha256}
        request = PreviewRequest(ImportedPageReview(self.manager.data_root, obj), snapshot,
            tr("Imported page package. Check code, resources and effects on existing settings. Approval is only for this version."),
            ("sharing", number), data_root=self.manager.data_root, review_only=True)
        dialog = PagePreviewDialog(request, self.window_host)
        if dialog.ready:
            dialog.exec()
        result = request.result or {}
        if result.get("status") == "reviewed":
            self.reviewed[number] = {**result, "before": check["before"]}
            self.review_failed.pop(number, None)
        elif result.get("status") == "preview_failed":
            self.review_failed[number] = result["error"]
        self.render_page()
        self.update_state()

    def submit(self):
        self.update_state()
        if not self.commit.isEnabled():
            return
        for obj in self.by_kind["workflow"]:
            check = self.checks[obj["number"]]
            if obj["number"] in self.selected and check.get("uuid_conflict"):
                message = tr("Manifest UUID {0} is already occupied and cannot be overwritten. New UUID {1} has been allocated for this import. Continue?").format(obj["id"], check["manifest_id"])
                if QMessageBox.question(self, tr("Manifest UUID already used"), message, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                    return
        unreviewed = [obj["id"] for obj in self.by_kind["pages"] if obj["number"] in self.selected and obj["number"] not in self.reviewed]
        if unreviewed:
            message = tr("Install these pages without Review? Runtime identity, loading and interface have not been verified; they may fail after reload.") + "\n\n" + "\n".join(unreviewed)
            if QMessageBox.question(self, tr("Unreviewed pages"), message, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return
        try:
            self.result_data = sharing_task(self, lambda: import_selected(self.manager, self.package, self.checks, self.selected,
                asset_actions=self.asset_actions, reviewed=self.reviewed, allow_unreviewed=bool(unreviewed)))
            lines = [tr("Completed: {0}").format(len(self.result_data["completed"]))]
            for item in self.result_data["completed"]:
                status = {"skipped": tr("Skipped"), "imported": tr("Imported"), "installed": tr("Installed")}.get(item.get("status"), item.get("manifest_id", item.get("path", "")))
                lines.append(f"{title(item['kind'])} · {item['id']} · {status}")
            if self.result_data["failed"]:
                failed = self.result_data["failed"]
                lines.extend([tr("Failed: {0}").format(f"{title(failed['kind'])} · {failed['id']} · {failed['error']}"),
                              tr("Not processed: {0}").format(", ".join(title(item["kind"]) + " · " + item["id"] for item in self.result_data["unprocessed"]))])
            if any(item.get("reload_required") for item in self.result_data["completed"]):
                lines.append(tr("Pages were installed. Reload the application manually to use them."))
            QMessageBox.information(self, tr("Import results"), self.window_host.clean_details("\n".join(lines)))
            if self.result_data["failed"]:
                for obj in self.package.objects:
                    if any(item["kind"] == obj["kind"] and item["id"] == obj["id"] for item in self.result_data["completed"]):
                        self.selected.discard(obj["number"])
                self.sync_selection()
                self.recheck()
            else:
                self.accept()
        except Exception as error:
            QMessageBox.warning(self, tr("Import failed"), self.window_host.clean_details(str(error)))
            self.recheck()

    def sync_selection(self):
        for kind, widget in (("pages", self.pages), ("history", self.histories)):
            widget.blockSignals(True)
            for index, obj in enumerate(self.by_kind[kind]):
                widget.item(index).setCheckState(Qt.CheckState.Checked if obj["number"] in self.selected else Qt.CheckState.Unchecked)
            widget.blockSignals(False)
        self.assets.blockSignals(True)
        for item in tree_items(self.assets):
            identity = item.data(0, Qt.ItemDataRole.UserRole)
            if identity is not None:
                item.setCheckState(0, Qt.CheckState.Checked if self.number("assets", identity) in self.selected else Qt.CheckState.Unchecked)
        self.assets.blockSignals(False)


def open_sharing(window, *, exporting):
    """活动互斥覆盖选择、Review 和提交；退出任意路径释放锁及暂存资料。"""
    if window.jobs or window.closing:
        raise ValueError(tr("An operation has not finished."))
    with sharing_activity(window.service):
        if exporting:
            ExportDialog(window).exec()
        else:
            filename, _ = QFileDialog.getOpenFileName(window, tr("Choose shared package"), "", "ZIP (*.zip)")
            if filename:
                try:
                    package = sharing_task(window, lambda: SharingPackage(filename, window.service.data_root))
                except InterruptedError:
                    return
                try:
                    ImportDialog(window, package).exec()
                finally:
                    package.close()
