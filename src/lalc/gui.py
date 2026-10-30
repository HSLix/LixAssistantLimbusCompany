from __future__ import annotations

import json
import os
import sys
import asyncio
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot, Qt, QTimer, QSize
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QMessageBox, QScrollArea,
    QGraphicsOpacityEffect,
)

from qfluentwidgets import (
    FluentWindow, FluentIcon, InfoBar, InfoBarIcon, InfoBarPosition,
    CardWidget, SubtitleLabel, TitleLabel, PrimaryPushButton,
    TransparentToolButton, IconWidget, MessageBox,
    BodyLabel as QLabel, PushButton as QPushButton, PlainTextEdit as QPlainTextEdit,
    ComboBox as QComboBox, SpinBox as QSpinBox, CheckBox as QCheckBox,
)

from .i18n import activity_text, tr

from .application import ApplicationService, StartError, default_data_root, default_candidate_root
from .errors import result_diagnostics
from .lifecycle import ApplicationLifecycle, run_application


class StateBridge(QObject):
    """把状态与未处理错误投递回 GUI 主线程。"""

    changed = Signal(dict)
    fatal = Signal(str)


class ErrorDialog(QDialog):
    """先展示错误摘要，完整脱敏详情由用户展开并可复制。"""

    def __init__(self, message: str, details: str, *, fatal: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, not fatal)
        self.setWindowTitle(tr('Fatal error') if fatal else tr('Operation failed'))
        self.resize(600, 180)
        layout = QVBoxLayout(self)
        label = QLabel(message)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(label)
        self.details = QPlainTextEdit()
        self.details.setPlainText(details)
        self.details.setReadOnly(True)
        layout.addWidget(self.details)
        self.details.hide()
        self.details_button = QPushButton(tr('Show error details'))
        self.details_button.setCheckable(True)
        def toggle_details(expanded):
            self.details.setVisible(expanded)
            self.details_button.setText(tr('Hide error details') if expanded else tr('Show error details'))
            self.resize(760 if expanded else 600, 520 if expanded else 180)
        self.details_button.toggled.connect(toggle_details)
        layout.addWidget(self.details_button)
        copy = QPushButton(tr('Copy error'))
        copy.clicked.connect(lambda: QApplication.clipboard().setText(message + "\n\n" + details))
        layout.addWidget(copy)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)




class MainWindow(FluentWindow):
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
        self.host = host or DeveloperHost(service, default_candidate_root(service.data_root))
        self.jobs = []
        self.owns_run = False
        self.closing = False
        self.close_timer = QTimer(self)
        self.close_timer.setInterval(100)
        self.close_timer.timeout.connect(self._finish_close)
        self.setWindowTitle(tr('LALC — Developer'))
        self.resize(1150, 900)
        self.navigationInterface.setExpandWidth(220)
        root = QWidget()
        layout = QVBoxLayout(root)
        self.runner_manifest = QComboBox()
        self.runner_manifest.addItem(tr('Use Default'), userData=None)
        self.runner_selection_error = None
        try:
            selected = self.host.runner_selection()
            if selected is not None:
                self.runner_manifest.addItem(selected, userData=selected)
                self.runner_manifest.setCurrentIndex(1)
        except Exception as error:
            self.runner_selection_error = str(error)
        for item in self.host.manager.list_manifests():
            if self.runner_manifest.findData(item["manifest_id"]) < 0:
                self.runner_manifest.addItem(item["manifest_id"], userData=item["manifest_id"])
        self.runner_manifest.currentIndexChanged.connect(self._runner_selected)
        layout.addWidget(QLabel(tr('Developer Selected Manifest (does not change Default or Candidate source)')))
        layout.addWidget(self.runner_manifest)
        self.runner_notice = QLabel(self.runner_selection_error or tr('The selected version is used for subsequent developer trials.'))
        self.runner_notice.setWordWrap(True)
        layout.addWidget(self.runner_notice)
        self.refresh_manifest_button = QPushButton(tr('Refresh Manifests'))
        self.refresh_manifest_button.clicked.connect(self._refresh_runner)
        layout.addWidget(self.refresh_manifest_button)
        self.trial_button = QPushButton(tr('Trial selected Plan'))
        self.trial_button.clicked.connect(lambda: self._interact(self.start_selected_plan))
        layout.addWidget(self.trial_button)
        self.pages = self.stackedWidget
        self.pages.setAnimationEnabled(False)
        self.capture_page = CapturePage(self)
        self.settings_page = SettingsPage(self)
        self.repair_page = RepairPage(self)
        self.settings_view = QScrollArea()
        self.settings_view.setWidgetResizable(True)
        self.settings_view.setWidget(self.settings_page)
        self.operation_event.connect(self.repair_page.show_event)
        for page, identity, name, icon in (
            (self.capture_page, "developer-capture", tr('Capture'), FluentIcon.CAMERA),
            (self.settings_view, "developer-settings", tr('Agent Settings'), FluentIcon.SETTING),
            (self.repair_page, "developer-repair", tr('Agent Repair'), FluentIcon.CHAT),
        ):
            page.setObjectName(identity)
            self.addSubInterface(page, icon, name)
        self.repair_page.set_manifests(self.host.manager.list_manifests())
        self.widgetLayout.removeWidget(self.stackedWidget)
        layout.addWidget(self.stackedWidget, 1)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.notifications = NotificationList()
        layout.addWidget(self.notifications)
        self.widgetLayout.addWidget(root)
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
            self.runner_manifest.addItem(tr('Use Default'), userData=None)
            for item in manifests:
                self.runner_manifest.addItem(item["manifest_id"], userData=item["manifest_id"])
            index = self.runner_manifest.findData(identity)
            if index < 0 and identity is not None:
                self.runner_manifest.addItem(identity, userData=identity)
                index = self.runner_manifest.count() - 1
            self.runner_manifest.setCurrentIndex(max(0, index))
            self.runner_manifest.blockSignals(False)
            self.runner_selection_error = error
            self.runner_notice.setText(error or tr('Selected is used for subsequent trials; Default and Candidate remain unchanged.'))
            self.repair_page.set_manifests(manifests)
            self.render_state(self.service.state)
        self.launch(operation, done)

    def closeEvent(self, event):
        """退出等待取消、输入释放、日志和子进程清理，期间保持事件循环。"""
        active = bool(self.jobs) or (self.owns_run and self.service.state["phase"] == "running")
        if active:
            event.ignore()
            if not self.closing:
                answer = QMessageBox.question(self, tr('Exit'), tr('Cancel the current task and exit after releasing input and saving logs?'))
                if answer != QMessageBox.StandardButton.Yes:
                    return
                self.closing = True
                self.service.stop()
                self.cancel_operation()
                self.render_state(self.service.state)
                if hasattr(self, "status"):
                    self.status.setText(tr('Stopping; waiting for input release, log saving and pi cleanup…'))
                self.close_timer.start()
            return
        self.close_timer.stop()
        if hasattr(self, "settings_page") and self.settings_page.isEnabled():
            self._interact(self.settings_page.submit)
            if self.settings_page.dirty:
                event.ignore()
                return
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
            keys = {*self.host.secrets.values(), settings_page.pending_key() if settings_page else None} - {None, ""}
            conversation = self.host.conversation
            if conversation:
                keys.update(conversation.log.keys)
            page = self.pages.currentWidget() if hasattr(self, "pages") else None
            if page is getattr(self, "settings_view", None) or page is getattr(self, "general_settings", None):
                page = self.settings_page
            panel = getattr(page, "diagnostics", None)
            log = conversation.log if page is not None and page is getattr(self, "repair_page", None) and conversation else None
            if (panel or page is settings_page) and log is None:
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
                self.notifications.notify(tr('Execution completed') if result.get("status") == "completed" and result.get("all_tasks_succeeded") else tr('Execution completed with failed tasks') if result.get("status") == "completed" else tr('Execution interrupted'), result_diagnostics(result))
            self.owns_run = False
            result = state.get("result") or {}
            if result.get("fatal"):
                self.fatal_error(result_diagnostics(result))
        busy = state["phase"] == "running" or bool(state.get("activity")) or bool(self.jobs) or self.closing
        self.status.setText(tr('Current activity: ') + (activity_text(state["activity"]) if state.get("activity") else (tr('Running') if state["phase"] == "running" else tr('Idle'))))
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
        bar = InfoBar(InfoBarIcon.INFORMATION, message, "", duration=-1,
                      position=InfoBarPosition.NONE, parent=self)
        bar.titleLabel.setTextFormat(Qt.TextFormat.PlainText)
        bar.contentLabel.setTextFormat(Qt.TextFormat.PlainText)
        if details:
            button = QPushButton(tr('Details'), bar)
            button.clicked.connect(lambda: ErrorDialog(message, details, parent=self.window()).open())
            bar.addWidget(button)
        self.messages.addWidget(bar)
        bar.show()


class UserWindow(MainWindow):
    """用户只选择 Default 并运行其唯一 Plan；普通配置不占用游戏。"""

    def __init__(self, service, lifecycle=None, *, host, coordinator):
        # 共用窗口清理/后台操作和脱敏错误处理，用户页面独立构建。
        FluentWindow.__init__(self)
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
        self.resize(1100, 800)
        self.navigationInterface.setExpandWidth(220)
        self.pages = self.stackedWidget
        self.pages.setAnimationEnabled(False)
        dashboard = QWidget()
        dashboard.setObjectName("dashboard")
        dash = QHBoxLayout(dashboard)
        execution = CardWidget()
        left = QVBoxLayout(execution)
        left.setContentsMargins(20, 20, 20, 20)
        left.setSpacing(12)
        dash.addWidget(execution, 1)
        left.addWidget(TitleLabel(tr('Execution')))
        left.addWidget(QLabel(tr('Manifest')))
        manifest_row = QHBoxLayout()
        self.manifest_label = QLabel()
        self.manifest_label.setMinimumWidth(0)
        manifest_row.addWidget(self.manifest_label, 1)
        self.manifest_button = QPushButton(tr('Choose Manifest'))
        self.manifest_button.clicked.connect(self.choose_manifest)
        manifest_row.addWidget(self.manifest_button)
        left.addLayout(manifest_row)
        from .user_pages import UserSettings, discover_pages
        if coordinator.page_state is None:
            store = UserSettings(service.data_root)
            pages, errors = discover_pages(service.data_root / "pages", store)
            coordinator.page_state = (store, pages, errors)
        self.page_store, self.business_pages, self.page_errors = coordinator.page_state
        self.warning_history = coordinator.warning_history
        self.current_manifest_id = None
        self.current_supported = ()
        self.task_rows = {}
        self.warning_button = TransparentToolButton(FluentIcon.INFO)
        self.warning_button.setIconSize(QSize(16, 16))
        self.warning_button.setFixedSize(28, 28)
        warning_opacity = QGraphicsOpacityEffect(self.warning_button)
        warning_opacity.setOpacity(0.7)
        self.warning_button.setGraphicsEffect(warning_opacity)
        self.warning_button.setAccessibleName(tr('Task and page notices'))
        self.warning_button.clicked.connect(self.show_warnings)
        self.warning_button.hide()
        task_heading = QHBoxLayout()
        task_heading.addWidget(SubtitleLabel(tr('Task Repetitions')), 1)
        task_heading.addWidget(self.warning_button)
        left.addLayout(task_heading)
        self.task_warning = QLabel()
        self.task_warning.setWordWrap(True)
        self.task_warning.setTextFormat(Qt.TextFormat.PlainText)
        self.task_warning.hide()
        left.addWidget(self.task_warning)
        if self.warning_history:
            self.add_warning(self.warning_history[0])
        self.task_scroll = QScrollArea()
        self.task_scroll.setWidgetResizable(True)
        self.task_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.task_list = QWidget()
        self.task_list.setObjectName("task-list")
        self.task_layout = QVBoxLayout(self.task_list)
        self.task_scroll.setWidget(self.task_list)
        self.task_scroll.setStyleSheet("QScrollArea {border: none; background: transparent;} QWidget#task-list {background: transparent;}")
        left.addWidget(self.task_scroll, 1)
        self.agent_status = QPushButton()
        self.agent_status.clicked.connect(self.show_agent_settings)
        left.addWidget(self.agent_status)
        self.start_hint = QLabel()
        self.start_hint.setWordWrap(True)
        left.addWidget(self.start_hint)
        self.start_button = PrimaryPushButton(tr('Start Plan'))
        self.start_button.clicked.connect(lambda: self._interact(self.start_plan))
        left.addWidget(self.start_button)
        self.notifications = NotificationList()
        left.addWidget(self.notifications)
        information = QVBoxLayout()
        information.setSpacing(12)
        for title, message in ((tr('Announcements'), tr('Announcements are not connected yet')), (tr('Disclaimer'), tr('The software disclaimer is not connected yet')),
                               (tr('Version & Update'), tr('Version information and updates are not connected yet'))):
            card = CardWidget()
            content = QVBoxLayout(card)
            content.setContentsMargins(20, 20, 20, 20)
            content.addWidget(SubtitleLabel(title))
            label = QLabel(message)
            label.setWordWrap(True)
            content.addWidget(label)
            if title == tr('Version & Update'):
                self.update_button = QPushButton(tr('Update'))
                self.update_button.setEnabled(False)
                content.addWidget(self.update_button)
            information.addWidget(card)
        information.addStretch()
        dash.addLayout(information, 1)
        self.navigationInterface.addItemHeader(tr('GENERAL'))
        self.addSubInterface(dashboard, FluentIcon.HOME, tr('Dashboard'))
        settings = QWidget()
        settings.setObjectName("general-settings-content")
        options = QVBoxLayout(settings)
        options.setContentsMargins(20, 20, 20, 20)
        options.setSpacing(16)
        options.addWidget(TitleLabel(tr('General Settings')))
        from .developer_gui import SettingsPage
        from .agent_settings import settings_document
        self.agent_controls = CardWidget()
        agent_layout = QVBoxLayout(self.agent_controls)
        agent_layout.setContentsMargins(16, 16, 16, 16)
        heading = QHBoxLayout()
        heading.addWidget(SubtitleLabel(tr('User Agent')), 1)
        self.user_enabled = QCheckBox(tr('Enable User Agent'))
        self.user_enabled.setChecked(settings_document(service.data_root)["user_enabled"])
        self.user_enabled.toggled.connect(lambda _: self._interact(self.save_user_enabled))
        heading.addWidget(self.user_enabled)
        agent_layout.addLayout(heading)
        self.agent_summary = QLabel()
        agent_layout.addWidget(self.agent_summary)
        agent_layout.addWidget(QLabel(tr('Runtime automatic repair is not implemented yet.')))
        self.settings_page = SettingsPage(self, side="user")
        agent_layout.addWidget(self.settings_page)
        options.addWidget(self.agent_controls)
        self.edit_owner_notice = QLabel()
        options.addWidget(self.edit_owner_notice)
        tools = CardWidget()
        tools_layout = QVBoxLayout(tools)
        tools_layout.setContentsMargins(16, 16, 16, 16)
        tools_layout.addWidget(SubtitleLabel(tr('Developer Tools')))
        purpose = QLabel(tr('For observation, Candidate development and trials after publication.'))
        purpose.setWordWrap(True)
        tools_layout.addWidget(purpose)
        developer = QPushButton(tr('Open Developer GUI'))
        developer.clicked.connect(lambda: self._interact(self.open_developer))
        tools_layout.addWidget(developer)
        options.addWidget(tools)
        application = CardWidget()
        application_layout = QVBoxLayout(application)
        application_layout.setContentsMargins(16, 16, 16, 16)
        application_layout.addWidget(SubtitleLabel(tr('Application')))
        from .i18n import load_language
        application_layout.addWidget(QLabel(tr("Interface language")))
        self.language_choice = QComboBox()
        for label, language in ((tr("Follow system"), "system"), ("简体中文", "zh_CN"), ("English", "en_US")):
            self.language_choice.addItem(label, userData=language)
        self.language_choice.setCurrentIndex(self.language_choice.findData(load_language(service.data_root)))
        self.language_choice.currentIndexChanged.connect(lambda: self._interact(self.save_gui_language))
        application_layout.addWidget(self.language_choice)
        language_notice = QLabel(tr("Language changes take effect after reloading the entire application."))
        language_notice.setWordWrap(True)
        application_layout.addWidget(language_notice)
        self.reload_button = QPushButton(tr('Save and reload the entire application'))
        self.reload_button.clicked.connect(lambda: self._interact(self.coordinator.request_reload))
        application_layout.addWidget(self.reload_button)
        for title, path in ((tr('Open application log directory'), service.data_root / "logs"),
                            (tr('Open Agent check log directory'), service.data_root / "agent-diagnostics")):
            entry = QPushButton(title)
            entry.clicked.connect(lambda _, path=path: self.open_directory(path))
            application_layout.addWidget(entry)
        options.addWidget(application)
        options.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(settings)
        scroll.setStyleSheet("QScrollArea {border: none; background: transparent;} QWidget#general-settings-content {background: transparent;}")
        scroll.setObjectName("general-settings")
        self.general_settings = scroll
        self.addSubInterface(scroll, FluentIcon.SETTING, tr('General Settings'))
        self.navigationInterface.addSeparator()
        self.navigationInterface.addItemHeader(tr('WORKFLOW SETTINGS'))
        for page in self.business_pages:
            page.widget.setObjectName(page.page_id)
            self.addSubInterface(page.widget, page.icon or FluentIcon.APPLICATION, page.name)
        for error in self.page_errors:
            self.add_warning(error)
            self.notifications.notify(tr('External page failed to load'), self.clean_details(error))
        self.render_state(service.state)

    def show_agent_settings(self):
        """从首页进入设置并定位到 Agent 卡片。"""
        self.switchTo(self.general_settings)
        QTimer.singleShot(0, lambda: self.general_settings.ensureWidgetVisible(self.agent_controls, 0, 12))

    def open_directory(self, path):
        """日志入口沿用现有目录打开与统一错误处理。"""
        from .developer_gui import open_directory
        open_directory(self, path)

    def save_gui_language(self):
        """保存失败恢复已落盘选择，不影响当前进程语言或运行快照。"""
        from .i18n import load_language, save_language
        previous = load_language(self.service.data_root)
        try:
            save_language(self.service.data_root, self.language_choice.currentData())
        except Exception:
            self.language_choice.blockSignals(True)
            self.language_choice.setCurrentIndex(self.language_choice.findData(previous))
            self.language_choice.blockSignals(False)
            raise

    def open_developer(self):
        QMessageBox.information(self, tr('Developer GUI'), tr('This interface is for developer observation, Candidate editing and trials.'))
        self.coordinator.open_window(True)

    def choose_manifest(self):
        """每次打开重新枚举；选择只改变后续 Run 的 Default。"""
        dialog = QDialog(self)
        dialog.setWindowTitle(tr('Choose Default Manifest'))
        layout = QVBoxLayout(dialog)
        choices = QComboBox()
        for item in self.host.manager.list_manifests():
            choices.addItem(item["manifest_id"], userData=item["manifest_id"])
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

    def submit_pages(self):
        """运行与重载前强制提交所有已加载页面，错误保留页面身份。"""
        for page in self.business_pages:
            try:
                page.context.save(page.widget.submit())
            except Exception as error:
                raise ValueError(tr('Page {0} ({1}) failed to submit: {2}').format(page.name, page.page_id, error)) from error

    def clean_details(self, text):
        from .agent_diagnostics import redact
        keys = set(self.host.secrets.values())
        if self.host.conversation:
            keys.update(self.host.conversation.log.keys)
        if hasattr(self, "settings_page") and self.settings_page.pending_key():
            keys.add(self.settings_page.pending_key())
        return redact(text, keys)

    def add_warning(self, message):
        message = self.clean_details(message)
        if message not in self.warning_history:
            self.warning_history.append(message)
        self.warning_button.show()

    def show_warnings(self):
        title = tr('Task and page notices') if self.task_warning.text() else tr('Previous notices (no current configuration issues)')
        dialog = MessageBox(title, "\n\n".join(self.warning_history), self)
        dialog.cancelButton.hide()
        dialog.yesButton.setText(tr('Close'))
        dialog.open()

    def refresh_tasks(self):
        """任务匹配保持原规则；空状态中性展示，实际异常与历史提示分开。"""
        from .user_pages import task_inputs
        issues = [self.clean_details(error) for error in self.page_errors]
        self.current_manifest_id = self.host.manager.default_manifest_id()
        self.current_supported = ()
        if self.current_manifest_id:
            result = self.host.manager.load(self.current_manifest_id)
            if result.ok:
                self.current_supported = next(component.supported_task_ids for component in
                    result.loaded.components.values() if component.role == "automation_plan")
            else:
                for error in result.errors:
                    self.add_warning(error.message)
                    issues.append(self.clean_details(error.message))
                if getattr(self, "_failed_manifest", None) != self.current_manifest_id:
                    self._failed_manifest = self.current_manifest_id
                    message = tr('Manifest failed to load')
                    details = self.clean_details("\n".join(error.message for error in result.errors))
                    ErrorDialog(message, details, parent=self).open()
            if result.ok:
                self._failed_manifest = None
        while self.task_layout.count():
            item = self.task_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        self.task_rows = {}
        for page in self.business_pages:
            if page.task_id not in self.current_supported:
                continue
            saved = self.page_store.value["tasks"].get(page.task_id, {"enabled": False, "count": 1})
            row = QWidget()
            layout = QHBoxLayout(row)
            enabled, count = QCheckBox(page.name), QSpinBox()
            enabled.setChecked(saved["enabled"])
            count.setRange(1, 2147483647)
            count.setValue(saved["count"])
            jump = QPushButton(tr('Settings'))
            jump.clicked.connect(lambda _, widget=page.widget: self.switchTo(widget))
            layout.addWidget(enabled)
            layout.addWidget(count)
            layout.addWidget(jump)
            self.task_rows[page.task_id] = (enabled, count)
            enabled.toggled.connect(lambda _, identity=page.task_id: self._interact(lambda: self.save_task(identity)))
            count.editingFinished.connect(lambda identity=page.task_id: self._interact(lambda: self.save_task(identity)))
            self.task_layout.addWidget(row)
        if not self.task_rows and (not self.current_manifest_id or result.ok):
            empty_state = QWidget()
            empty_layout = QHBoxLayout(empty_state)
            empty_layout.setSpacing(8)
            icon = IconWidget(FluentIcon.INFO.icon(color=QColor("#808080")))
            icon.setFixedSize(16, 16)
            empty_layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
            empty = QLabel(tr('Choose a Manifest first.') if not self.current_manifest_id else
                           tr('No tasks match the current Manifest and loaded settings pages.'))
            empty.setWordWrap(True)
            empty_layout.addWidget(empty, 1)
            self.task_layout.addWidget(empty_state)
        self.task_layout.addStretch()
        _, _, warnings = task_inputs(self.business_pages, self.current_supported, self.page_store)
        # 未选 Manifest 或未声明循环任务是空状态，不改变底层 warning/次数契约。
        if self.current_manifest_id and self.current_supported:
            issues.extend(self.clean_details(warning) for warning in warnings)
        for issue in issues:
            self.add_warning(issue)
        self.task_warning.setText("\n".join(dict.fromkeys(issues)))
        self.task_warning.setVisible(bool(issues))
        self.warning_button.setIcon(InfoBarIcon.WARNING if issues else
                                    FluentIcon.INFO.icon(color=QColor("#808080")))
        self.warning_button.setToolTip(self.task_warning.text() if issues else tr('View previous notices (no current configuration issues)'))
        self.warning_button.setVisible(bool(issues or self.warning_history))

    def save_task(self, identity):
        enabled, count = self.task_rows[identity]
        self.page_store.save_task(identity, enabled.isChecked(), count.value())

    def save_user_enabled(self):
        from .agent_settings import settings_document, save_selection
        provider = settings_document(self.service.data_root)["user_provider"]
        save_selection(self.service.data_root, "user", provider, enabled=self.user_enabled.isChecked())
        self.coordinator.refresh_agent()

    def start_plan(self):
        """提交配置后固定 Manifest 和调度输入，不回读运行中的 GUI。"""
        from .user_pages import task_inputs
        from .agent_settings import settings_document, load_settings, configuration_complete
        if settings_document(self.service.data_root)["user_enabled"]:
            self.settings_page.submit()
            value = load_settings(self.service.data_root, side="user", for_use=False)
            if not configuration_complete(value, temporary_keys=self.host.secrets):
                raise ValueError(tr('Complete the Agent settings or turn off User Agent'))
        for identity in self.task_rows:
            self.save_task(identity)
        self.submit_pages()
        self.refresh_tasks()
        repetitions, settings, _ = task_inputs(self.business_pages, self.current_supported, self.page_store)
        self.service.start_plan(manifest_id=self.current_manifest_id, task_repetitions=repetitions, settings=settings)
        self.owns_run = True
        self.render_state(self.service.state)

    @Slot(dict)
    def render_state(self, state):
        if not hasattr(self, "start_button"):
            return
        busy = state["phase"] == "running" or bool(state.get("activity")) or self.closing
        if self.current_manifest_id != state["default_manifest_id"] or not hasattr(self, "_tasks_initialized"):
            self._tasks_initialized = True
            self.refresh_tasks()
        if hasattr(self, "settings_page"):
            self.settings_page.render(busy)
        if hasattr(self, "reload_button"):
            self.reload_button.setEnabled(not busy and not self.jobs and not self.coordinator.reloading)
        identity = state["default_manifest_id"]
        self.manifest_label.setText("Default · " + identity[:8] + "…" if identity else tr('Not selected'))
        self.manifest_label.setToolTip(identity or tr('No Manifest selected'))
        from .agent_settings import settings_document, load_settings, configuration_complete
        enabled = settings_document(self.service.data_root)["user_enabled"]
        complete = configuration_complete(load_settings(self.service.data_root, side="user", for_use=False),
                                          temporary_keys=self.host.secrets)
        ready = not enabled or complete
        self.start_hint.setText("" if ready else tr('Complete the Agent settings or turn off User Agent'))
        self.start_hint.setVisible(not ready)
        self.start_button.setEnabled(not busy and ready)
        self.start_button.setToolTip(tr('The current activity has not finished') if busy else
                                    tr("Run the Default Manifest's Python Plan") if ready else self.start_hint.text())
        if self.owns_run and state["phase"] == "running":
            if self.trial_dialog is None:
                from .developer_gui import TrialDialog
                self.trial_dialog = TrialDialog(self.service, self)
                self.trial_dialog.setWindowTitle(tr('Run'))
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
                message = (tr('Execution completed') if result.get("all_tasks_succeeded") else tr('Execution completed with failed tasks')) if result.get("status") == "completed" else tr('Execution interrupted')
                self.notifications.notify(message, result_diagnostics(result))


class GuiCoordinator:
    """应用持有唯一服务和宿主；窗口可独立关闭或重新打开。"""

    def __init__(self, service, lifecycle):
        from .i18n import install_translations, load_language, resolve_language
        app = QApplication.instance()
        if not hasattr(app, "_lalc_language"):
            install_translations(app, resolve_language(load_language(service.data_root)))
        from .developer import DeveloperHost
        self.service, self.lifecycle = service, lifecycle
        self.host = DeveloperHost(service, default_candidate_root(service.data_root))
        self.user = None
        self.developer = None
        self.reloading = False
        self.warning_history = []
        self.page_state = None

    def open_window(self, developer=False):
        """复用已有窗口；已关闭的窗口可在同一服务上重新创建。"""
        if self.reloading:
            raise ValueError(tr('The application is reloading. Try again later.'))
        name = "developer" if developer else "user"
        window = getattr(self, name)
        if developer and window is None and self.user is not None:
            self.user.settings_page.submit()
        if window is None:
            window = MainWindow(self.service, self.lifecycle, host=self.host, coordinator=self) if developer else UserWindow(
                self.service, self.lifecycle, host=self.host, coordinator=self)
            setattr(self, name, window)
        self.refresh_agent()
        window.showNormal()
        window.raise_()
        window.activateWindow()
        return window

    def refresh_agent(self):
        if self.user is None:
            return
        from .agent_settings import settings_document
        document = settings_document(self.service.data_root)
        owned = self.developer is not None
        self.user.agent_controls.setEnabled(not owned)
        self.user.edit_owner_notice.setText(tr('Edit in Developer GUI') if owned else "")
        self.user.edit_owner_notice.setVisible(owned)
        self.user.user_enabled.blockSignals(True)
        self.user.user_enabled.setChecked(document["user_enabled"])
        self.user.user_enabled.blockSignals(False)
        self.user.settings_page.setVisible(document["user_enabled"])
        from .agent_settings import load_settings, configuration_complete
        complete = configuration_complete(load_settings(self.service.data_root, side="user", for_use=False),
                                          temporary_keys=self.host.secrets)
        status = (tr('Enabled') if document["user_enabled"] else tr('Disabled')) + " · " + (tr('Configured') if complete else tr('Needs configuration'))
        self.user.agent_status.setText(tr("User Agent: {0} · {1}").format(document['user_provider'], status))
        self.user.agent_summary.setText(status)
        self.user.render_state(self.service.state)

    def request_reload(self):
        """先保存并封闭所有入口，最终清理成功后才允许启动新进程。"""
        def check_idle():
            state = self.service.state
            if (self.reloading or state["phase"] == "running" or state.get("activity") or
                    self.service._thread is not None and self.service._thread.is_alive() or
                    any(window.jobs or window.closing for window in (self.user, self.developer) if window)):
                raise ValueError(tr('Cannot reload while either window has an activity or unfinished background operation.'))
        check_idle()
        parent = self.user or self.developer
        if sys.platform != "win32" and self.host.secrets:
            if QMessageBox.question(parent, tr('Reload'), tr('Restarting clears temporary API keys; you will need to enter them again. Continue?')) != QMessageBox.StandardButton.Yes:
                return
        for window in (self.user, self.developer):
            if window is not None:
                window.settings_page.submit()
        if self.user is not None:
            for identity in self.user.task_rows:
                self.user.save_task(identity)
            self.user.submit_pages()
        check_idle()
        windows = tuple(name for name in ("user", "developer") if getattr(self, name) is not None)
        self.reloading = True
        for window in (self.user, self.developer):
            if window is not None:
                window.setEnabled(False)
        self.lifecycle.restart = lambda: self.restart_process(windows)
        QApplication.instance().exit(0)

    @staticmethod
    def restart_process(windows):
        """清理完成后替换当前程序，保留终端启动链；认证不进入启动参数。"""
        command = [sys.executable]
        if not getattr(sys, "frozen", False):
            command += ["-m", "lalc"]
        command.append("--restore-gui=" + ",".join(windows))
        os.execv(command[0], command)

    def render_state(self, state):
        for window in (self.user, self.developer):
            if window is not None:
                window.render_state(state)

    def closed(self, window):
        if window is self.user:
            for page in window.business_pages:
                page.widget.setParent(None)
            self.user = None
        elif window is self.developer:
            self.developer = None
            if self.user is not None:
                self.user.settings_page.reload()
                self.refresh_agent()
        window.deleteLater()
        if self.user is None and self.developer is None:
            QApplication.instance().exit(0)

    def shutdown(self):
        for window in (self.user, self.developer):
            if window is not None:
                window.shutdown()
                if self.reloading:
                    window.close()
        self.service.shutdown()


def run_gui(lifecycle: ApplicationLifecycle | None = None, *, developer=False, restore=()) -> int:
    """归并重复 GUI 入口，在唯一事件循环内持有双窗口。"""
    if lifecycle is None:
        return run_application(lambda owner: run_gui(owner, developer=developer, restore=restore))
    from .gui_instance import GuiInstance
    app = QApplication.instance() or QApplication(sys.argv)
    instance = GuiInstance()
    if instance.forward(developer):
        return 0
    bridge = StateBridge()
    service = ApplicationService(default_data_root(), on_change=bridge.changed.emit)
    coordinator = GuiCoordinator(service, lifecycle)
    def open_requested(developer=False):
        try:
            coordinator.open_window(developer)
        except Exception as error:
            window = coordinator.user or coordinator.developer
            if window is not None:
                def fail():
                    raise error
                window._interact(fail)
            raise
    instance.listen(open_requested)
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
    interrupt_timer = QTimer(app)
    interrupt_timer.setInterval(100)
    interrupt_timer.timeout.connect(lifecycle.process_interrupt)
    interrupt_timer.start()
    try:
        for name in restore or (("developer" if developer else "user"),):
            coordinator.open_window(name == "developer")
        return app.exec()
    finally:
        interrupt_timer.stop()
        interrupt_timer.deleteLater()
