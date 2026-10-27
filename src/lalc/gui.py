from __future__ import annotations

import json
import sys
import asyncio
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
    QTabWidget, QComboBox, QMessageBox, QListWidget, QStackedWidget,
)

from .application import ApplicationService, StartError, default_data_root
from .errors import result_diagnostics
from .lifecycle import ApplicationLifecycle, run_application


class StateBridge(QObject):
    """把状态与未处理错误投递回 GUI 主线程。"""

    changed = Signal(dict)
    fatal = Signal(str)


class ErrorDialog(QDialog):
    """直接展示可选择、可复制的完整原始错误，不把 traceback 折叠隐藏。"""

    def __init__(self, message: str, details: str, *, fatal: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, not fatal)
        self.setWindowTitle("致命错误 / Fatal error" if fatal else "操作失败 / Operation failed")
        self.resize(900, 600)
        layout = QVBoxLayout(self)
        label = QLabel(message)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(label)
        self.details = QPlainTextEdit(details)
        self.details.setReadOnly(True)
        layout.addWidget(self.details)
        copy = QPushButton("复制错误信息 / Copy error")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(message + "\n\n" + details))
        layout.addWidget(copy)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)




class MainWindow(QMainWindow):
    """通过正式 ApplicationService 启动和观察任意逻辑入口。"""

    operation_event = Signal(dict)

    def __init__(self, service: ApplicationService, lifecycle: ApplicationLifecycle | None = None,
                 *, host=None, coordinator=None) -> None:
        super().__init__()
        self.service = service
        self.lifecycle = lifecycle or ApplicationLifecycle()
        self.coordinator = coordinator
        self._pause_notice_shown = False
        self._reported_run = None
        self._fatal_reported = False
        self.trial_dialog = None
        from .developer import DeveloperHost
        from .developer_gui import CapturePage, SettingsPage, RepairPage
        self.host = host or DeveloperHost(service, Path.cwd() / "candidate")
        self.jobs = []
        self.owns_run = False
        self.closing = False
        self.close_timer = QTimer(self)
        self.close_timer.setInterval(100)
        self.close_timer.timeout.connect(self._finish_close)
        self.setWindowTitle("LALC — Developer")
        self.resize(1050, 900)
        root = QWidget()
        layout = QVBoxLayout(root)
        self.runner_manifest = QComboBox()
        self.runner_manifest.addItem("使用 Default", None)
        self.runner_selection_error = None
        try:
            selected = self.host.runner_selection()
            if selected is not None:
                self.runner_manifest.addItem(selected, selected)
                self.runner_manifest.setCurrentIndex(1)
        except Exception as error:
            self.runner_selection_error = str(error)
        for item in self.host.manager.list_manifests():
            if self.runner_manifest.findData(item["manifest_id"]) < 0:
                self.runner_manifest.addItem(item["manifest_id"], item["manifest_id"])
        self.runner_manifest.currentIndexChanged.connect(self._runner_selected)
        layout.addWidget(QLabel("Developer Selected Manifest（不修改 Default 或 Candidate 来源）"))
        layout.addWidget(self.runner_manifest)
        self.runner_notice = QLabel(self.runner_selection_error or "所选版本用于后续开发试运行。")
        self.runner_notice.setWordWrap(True)
        layout.addWidget(self.runner_notice)
        self.refresh_manifest_button = QPushButton("刷新 Manifest")
        self.refresh_manifest_button.clicked.connect(self._refresh_runner)
        layout.addWidget(self.refresh_manifest_button)
        self.trial_button = QPushButton("试运行所选 Plan")
        self.trial_button.clicked.connect(lambda: self._interact(self.start_selected_plan))
        layout.addWidget(self.trial_button)
        self.tabs = QTabWidget()
        self.capture_page = CapturePage(self)
        self.settings_page = SettingsPage(self)
        self.repair_page = RepairPage(self)
        self.operation_event.connect(self.repair_page.show_event)
        for page, name in ((self.capture_page, "Capture"), (self.settings_page, "Agent Settings"),
                           (self.repair_page, "Agent Repair")):
            self.tabs.addTab(page, name)
        self.repair_page.set_manifests(self.host.manager.list_manifests())
        layout.addWidget(self.tabs)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.notifications = NotificationList()
        layout.addWidget(self.notifications)
        self.setCentralWidget(root)
        self.render_state(service.state)

    def launch(self, operation, done=None):
        """后台服务完成清理后再恢复交互，错误保留原始异常链。"""
        from .developer_gui import Operation
        if self.jobs or self.closing:
            return
        job = Operation(operation, self)
        outcome = {}
        job.succeeded.connect(lambda value: outcome.update(value=value))
        job.failed.connect(lambda error: outcome.update(error=error))
        def finished():
            self.jobs.remove(job)
            self.render_state(self.service.state)
            if "error" in outcome and not (self.closing and isinstance(outcome["error"], asyncio.CancelledError)):
                def fail():
                    raise outcome["error"]
                self._interact(fail)
            elif done and not self.closing:
                self._interact(lambda: done(outcome.get("value")))
            job.deleteLater()
        job.finished.connect(finished)
        self.jobs.append(job)
        self.render_state(self.service.state)
        job.start()

    def cancel_operation(self):
        for job in self.jobs:
            job.cancel()

    def _runner_selected(self):
        self.runner_selection_error = None
        identity = self.runner_manifest.currentData()
        def saved(_):
            self._refresh_runner()
        def operation():
            try:
                self.host.select_runner(identity)
            except Exception as error:
                self.runner_selection_error = str(error)
                raise
        self.launch(operation, saved)

    def start_selected_plan(self):
        """显式运行 Developer 所选已发布版本；不改变 Default。"""
        if self.runner_selection_error:
            raise ValueError(self.runner_selection_error)
        identity = self.host.runner_selection() or self.host.manager.default_manifest_id()
        if identity is None:
            raise ValueError("请先选择已发布 Manifest。")
        self.service.start_plan(manifest_id=identity)
        self.owns_run = True
        self.render_state(self.service.state)

    def _refresh_runner(self):
        identity = self.runner_manifest.currentData()
        def operation():
            manifests = self.host.manager.list_manifests()
            try:
                self.service._loaded_manifest(identity)
                return manifests, None
            except Exception as error:
                return manifests, str(error)
        def done(values):
            manifests, error = values
            self.runner_manifest.blockSignals(True)
            self.runner_manifest.clear()
            self.runner_manifest.addItem("使用 Default", None)
            for item in manifests:
                self.runner_manifest.addItem(item["manifest_id"], item["manifest_id"])
            index = self.runner_manifest.findData(identity)
            if index < 0 and identity is not None:
                self.runner_manifest.addItem(identity, identity)
                index = self.runner_manifest.count() - 1
            self.runner_manifest.setCurrentIndex(max(0, index))
            self.runner_manifest.blockSignals(False)
            self.runner_selection_error = error
            self.runner_notice.setText(error or "Selected 仅用于后续试运行；不改变 Default 或 Candidate。")
            self.repair_page.set_manifests(manifests)
            self.render_state(self.service.state)
        self.launch(operation, done)

    def closeEvent(self, event):
        """退出等待取消、输入释放、日志和子进程清理，期间保持事件循环。"""
        active = bool(self.jobs) or (self.owns_run and self.service.state["phase"] == "running")
        if active:
            event.ignore()
            if not self.closing:
                answer = QMessageBox.question(self, "退出", "取消当前任务，等待输入释放和日志保存后退出？")
                if answer != QMessageBox.StandardButton.Yes:
                    return
                self.closing = True
                self.service.stop()
                self.cancel_operation()
                self.render_state(self.service.state)
                self.status.setText("正在停止，等待输入释放、日志保存和 pi 回收…")
                self.close_timer.start()
            return
        self.close_timer.stop()
        event.accept()
        if self.coordinator is not None:
            self.coordinator.closed(self)

    def _finish_close(self):
        if not self.jobs and (not self.owns_run or self.service._thread is None or not self.service._thread.is_alive()):
            self.close()

    def shutdown(self):
        """事件循环退出后的最终兜底；正常关闭已在响应式等待中完成清理。"""
        self.service.stop()
        self.cancel_operation()
        for job in self.jobs:
            job.wait()
        self.service.shutdown()

    def _interact(self, operation) -> None:
        """交互层统一接住操作错误，记录原始异常并允许修正后继续操作。"""

        try:
            operation()
        except Exception as error:
            from .agent_diagnostics import error_details, details_text
            from .agent_repair import RepairLog
            settings_page = getattr(self, "settings_page", None)
            keys = {*self.host.secrets.values(), settings_page.key.text() if settings_page else None,
                    *((draft.get("key") for draft in settings_page.provider_drafts.values()) if settings_page else ())} - {None, ""}
            conversation = self.host.conversation
            if conversation:
                keys.update(conversation.log.keys)
            page = self.tabs.currentWidget() if hasattr(self, "tabs") else None
            panel = getattr(page, "diagnostics", None)
            log = conversation.log if page is not None and page is getattr(self, "repair_page", None) and conversation else None
            if panel and log is None:
                log = RepairLog(self.service.data_root, category="agent-diagnostics")
                log.keys.update(keys)
            context = {"log_path": str(log.path)} if log else {}
            value = error_details(error, "interaction", context, keys)
            if isinstance(error, StartError):
                from .agent_diagnostics import redact
                value["related_errors"] = redact(error.errors, keys)
            self.service.logger.error("Interaction failed: %s", value)
            if log:
                log.record({"type": "gui_error", **value})
            if panel:
                panel.add_error(value)
            ErrorDialog(value["message"], details_text(value), parent=self).open()

    @Slot(str)
    def fatal_error(self, details: str) -> None:
        """GUI 主线程显示致命错误；关闭后退出，禁止继续运行。"""

        if self._fatal_reported:
            return
        self._fatal_reported = True
        self.setEnabled(False)
        if self.service._gate is not None:
            self.service._gate.stop()
        self.lifecycle.present_fatal(details)

    @Slot(dict)
    def render_state(self, state: dict) -> None:
        trial = bool((state.get("entry") or {}).get("developer_trial"))
        if (trial or self.owns_run) and state["phase"] == "running":
            self.owns_run = True
            if self.trial_dialog is None:
                from .developer_gui import TrialDialog
                self.trial_dialog = TrialDialog(self.service, self)
                self.trial_dialog.show()
            self.trial_dialog.render(state)
        elif self.trial_dialog is not None:
            self.trial_dialog.done(QDialog.DialogCode.Accepted)
            self.trial_dialog.deleteLater()
            self.trial_dialog = None
        if state["phase"] == "finished":
            if self.owns_run and not trial:
                result = state.get("result") or {}
                self.notifications.notify("执行完成" if result.get("status") == "completed" and result.get("all_tasks_succeeded") else "执行完成，含失败任务" if result.get("status") == "completed" else "执行中断", result_diagnostics(result))
            self.owns_run = False
            result = state.get("result") or {}
            if result.get("fatal"):
                self.fatal_error(result_diagnostics(result))
        busy = state["phase"] == "running" or bool(state.get("activity")) or bool(self.jobs) or self.closing
        self.status.setText("当前活动：" + (state.get("activity") or ("运行中" if state["phase"] == "running" else "空闲")))
        self.trial_button.setEnabled(not busy and not self.runner_selection_error)
        self.runner_manifest.setEnabled(not busy)
        self.refresh_manifest_button.setEnabled(not busy)
        for page in (self.capture_page, self.settings_page, self.repair_page):
            page.render(busy)


class NotificationList(QWidget):
    """统一应用内持久通知；多条共存，仅由用户关闭，不跨进程保留。"""

    def __init__(self):
        super().__init__()
        self.messages = QVBoxLayout(self)
        self.messages.setContentsMargins(0, 0, 0, 0)

    def notify(self, message: str, details: str = "") -> None:
        row = QWidget()
        layout = QHBoxLayout(row)
        label = QLabel(message)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(label, 1)
        if details:
            button = QPushButton("详情")
            button.clicked.connect(lambda: ErrorDialog(message, details, parent=self).open())
            layout.addWidget(button)
        close = QPushButton("关闭")
        close.clicked.connect(row.deleteLater)
        layout.addWidget(close)
        self.messages.addWidget(row)


class UserWindow(MainWindow):
    """用户只选择 Default 并运行其唯一 Plan；普通配置不占用游戏。"""

    def __init__(self, service, lifecycle=None, *, host, coordinator):
        # 共用窗口清理/后台操作和脱敏错误处理，用户页面独立构建。
        QMainWindow.__init__(self)
        self.service, self.host, self.coordinator = service, host, coordinator
        self.lifecycle = lifecycle or ApplicationLifecycle()
        self.jobs = []
        self.owns_run = False
        self.closing = False
        self._reported_run = None
        self._fatal_reported = False
        self.trial_dialog = None
        self.close_timer = QTimer(self)
        self.close_timer.setInterval(100)
        self.close_timer.timeout.connect(self._finish_close)
        self.setWindowTitle("LALC")
        self.resize(950, 680)
        root = QWidget()
        layout = QHBoxLayout(root)
        self.navigation = QListWidget()
        self.navigation.addItems(["Dashboard", "General Settings"])
        self.navigation.setMaximumWidth(190)
        layout.addWidget(self.navigation)
        self.pages = QStackedWidget()
        layout.addWidget(self.pages, 1)
        dashboard = QWidget()
        dash = QHBoxLayout(dashboard)
        left = QVBoxLayout()
        dash.addLayout(left, 1)
        self.manifest_label = QLabel()
        self.manifest_label.setWordWrap(True)
        left.addWidget(self.manifest_label)
        self.manifest_button = QPushButton("选择 Default Manifest")
        self.manifest_button.clicked.connect(self.choose_manifest)
        left.addWidget(self.manifest_button)
        self.start_button = QPushButton("开始运行")
        self.start_button.clicked.connect(lambda: self._interact(self.start_plan))
        left.addWidget(self.start_button)
        self.status = QLabel()
        self.status.setWordWrap(True)
        left.addWidget(self.status)
        self.notifications = NotificationList()
        left.addWidget(self.notifications)
        left.addStretch()
        information = QLabel("")
        information.setWordWrap(True)
        information.setAlignment(Qt.AlignmentFlag.AlignTop)
        dash.addWidget(information, 1)
        self.pages.addWidget(dashboard)
        settings = QWidget()
        options = QVBoxLayout(settings)
        developer = QPushButton("打开 Developer GUI")
        developer.clicked.connect(self.open_developer)
        options.addWidget(developer)
        options.addWidget(QLabel("Developer 用于观察、Candidate 开发与发布后试运行。"))
        options.addWidget(QLabel("运行时自动修复当前不可用。"))
        options.addStretch()
        self.pages.addWidget(settings)
        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.navigation.setCurrentRow(0)
        self.setCentralWidget(root)
        self.render_state(service.state)

    def open_developer(self):
        QMessageBox.information(self, "Developer GUI", "此界面供开发者观察、编辑 Candidate 和试运行。")
        self.coordinator.open_window(True)

    def choose_manifest(self):
        """每次打开重新枚举；选择只改变后续 Run 的 Default。"""
        dialog = QDialog(self)
        dialog.setWindowTitle("选择 Default Manifest")
        layout = QVBoxLayout(dialog)
        choices = QComboBox()
        for item in self.host.manager.list_manifests():
            choices.addItem(item["manifest_id"], item["manifest_id"])
        choices.setCurrentIndex(max(0, choices.findData(self.host.manager.default_manifest_id())))
        layout.addWidget(choices)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        if dialog.exec() == QDialog.DialogCode.Accepted and choices.currentData():
            def select():
                result = self.host.manager.set_default(choices.currentData())
                if not result.ok:
                    raise ValueError("; ".join(error.message for error in result.errors))
                self.render_state(self.service.state)
            self._interact(select)

    def start_plan(self):
        """固定 Default 的本次运行，并将清理职责归属当前窗口。"""
        self.service.start_plan()
        self.owns_run = True
        self.render_state(self.service.state)

    @Slot(dict)
    def render_state(self, state):
        if not hasattr(self, "start_button"):
            return
        busy = state["phase"] == "running" or bool(state.get("activity")) or self.closing
        self.manifest_label.setText("Default Manifest：" + (state["default_manifest_id"] or "未选择"))
        self.start_button.setEnabled(not busy)
        self.start_button.setToolTip("当前活动尚未结束" if busy else "执行 Default 的唯一 Python Plan")
        self.status.setText("运行已暂停" if state["paused"] else "运行中" if state["phase"] == "running" else "空闲")
        if self.owns_run and state["phase"] == "running":
            if self.trial_dialog is None:
                from .developer_gui import TrialDialog
                self.trial_dialog = TrialDialog(self.service, self)
                self.trial_dialog.setWindowTitle("运行")
                self.trial_dialog.show()
            self.trial_dialog.render(state)
        elif self.owns_run and state["phase"] == "finished":
            if self.trial_dialog is not None:
                self.trial_dialog.done(QDialog.DialogCode.Accepted)
                self.trial_dialog.deleteLater()
                self.trial_dialog = None
            self.owns_run = False
            result = state.get("result") or {}
            if result.get("fatal"):
                self.fatal_error(result_diagnostics(result))
            else:
                message = ("执行完成" if result.get("all_tasks_succeeded") else "执行完成，含失败任务") if result.get("status") == "completed" else "执行中断"
                self.notifications.notify(message, result_diagnostics(result))


class GuiCoordinator:
    """应用持有唯一服务和宿主；窗口可独立关闭或重新打开。"""

    def __init__(self, service, lifecycle):
        from .developer import DeveloperHost
        self.service, self.lifecycle = service, lifecycle
        self.host = DeveloperHost(service, Path.cwd() / "candidate")
        self.user = None
        self.developer = None

    def open_window(self, developer=False):
        """复用已有窗口；已关闭的窗口可在同一服务上重新创建。"""
        name = "developer" if developer else "user"
        window = getattr(self, name)
        if window is None:
            window = MainWindow(self.service, self.lifecycle, host=self.host, coordinator=self) if developer else UserWindow(
                self.service, self.lifecycle, host=self.host, coordinator=self)
            setattr(self, name, window)
        window.showNormal()
        window.raise_()
        window.activateWindow()
        return window

    def render_state(self, state):
        for window in (self.user, self.developer):
            if window is not None:
                window.render_state(state)

    def closed(self, window):
        if window is self.user:
            self.user = None
        elif window is self.developer:
            self.developer = None
        window.deleteLater()
        if self.user is None and self.developer is None:
            QApplication.instance().quit()

    def shutdown(self):
        for window in (self.user, self.developer):
            if window is not None:
                window.shutdown()
        self.service.shutdown()


def run_gui(lifecycle: ApplicationLifecycle | None = None, *, developer=False) -> int:
    """归并重复 GUI 入口，在唯一事件循环内持有双窗口。"""
    if lifecycle is None:
        return run_application(lambda owner: run_gui(owner, developer=developer))
    from .gui_instance import GuiInstance
    app = QApplication.instance() or QApplication(sys.argv)
    instance = GuiInstance()
    if instance.forward(developer):
        return 0
    bridge = StateBridge()
    service = ApplicationService(default_data_root(), on_change=bridge.changed.emit)
    coordinator = GuiCoordinator(service, lifecycle)
    instance.listen(coordinator.open_window)
    app.setQuitOnLastWindowClosed(False)
    bridge.changed.connect(coordinator.render_state)
    bridge.fatal.connect(lambda details: (coordinator.user or coordinator.developer).fatal_error(details)
                         if coordinator.user or coordinator.developer else lifecycle.present_fatal(details))
    lifecycle.dispatch_fatal = bridge.fatal.emit
    def shutdown():
        try:
            coordinator.shutdown()
            result = service.state.get("result") or {}
            if result.get("fatal"):
                lifecycle.present_fatal(result_diagnostics(result))
        finally:
            instance.close()
    lifecycle.shutdown = shutdown
    coordinator.open_window(developer)
    return app.exec()
