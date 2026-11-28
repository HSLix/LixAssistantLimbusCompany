from __future__ import annotations

import json
import os
import shutil
import sys
import asyncio
import threading
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot, Qt, QTimer, QSize, QUrl, QPointF, QRectF, QSignalBlocker
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPainter, QPen, QPixmap, QTextDocument
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QMessageBox, QScrollArea, QFileDialog,
    QGraphicsOpacityEffect, QListWidgetItem, QSizePolicy, QFrame, QTextBrowser, QLabel as NativeLabel,
)

from qfluentwidgets import (
    FluentWindow, FluentIcon, InfoBarIcon,
    CardWidget, SubtitleLabel, TitleLabel, PrimaryPushButton, ListWidget, FlowLayout, SearchLineEdit,
    NavigationAvatarWidget, NavigationItemPosition,
    TransparentToolButton, ToolButton, HyperlinkButton, IconWidget, MessageBox, MessageBoxBase, StrongBodyLabel,
    CustomStyleSheet, isDarkTheme, qconfig, setCustomStyleSheet,
    BodyLabel as QLabel, PushButton as QPushButton, PlainTextEdit as QPlainTextEdit,
    ComboBox as QComboBox, SpinBox as QSpinBox, CheckBox as QCheckBox, LineEdit as QLineEdit,
)

from .i18n import tr
from .appearance import DARK_SURFACE, DARK_WINDOW, apply_appearance
from .application_settings import (DEFAULT_APPEARANCE, DEFAULT_IDLE_SECONDS, MAX_IDLE_SECONDS,
                                   MIN_IDLE_SECONDS, load_application_settings, save_application_setting)
from .manifest_source_gui import METADATA_ROLE, NOTES_ROLE, ManifestResultDelegate, manifest_search_text
from .notifications import NotificationList

from .application import ApplicationService, StartError, default_data_root, default_candidate_root
from .errors import result_diagnostics
from .lifecycle import ApplicationLifecycle, run_application
from .framework_update import LATEST_RELEASE_URL, MIRROR_PROJECT_URL, QUARK_SHARE_URL, REPOSITORY_URL


class ReleaseAnnouncement(QTextBrowser):
    """展示 GitHub Markdown，仅由用户点击打开 HTTPS 链接。"""

    def loadResource(self, resource_type, name):
        return None

    def show_release(self, content, *, html=False):
        if html:
            self.setHtml(content)
        else:
            self.document().setMarkdown(content, QTextDocument.MarkdownFeature.MarkdownDialectGitHub |
                                        QTextDocument.MarkdownFeature.MarkdownNoHTML)


class StateBridge(QObject):
    """合并工作线程的变更通知，每百毫秒在主线程读取一次有界快照。"""

    changed = Signal(dict)
    fatal = Signal(str)

    def __init__(self, service, receiver):
        super().__init__(QApplication.instance())
        self.service = service
        self.closed = False
        self.dirty = threading.Event()
        self.run_id = None
        self.sequence = 0
        self.changed.connect(receiver)
        self.service.on_change = self.dirty.set
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.flush)
        self.timer.start()
        self.dirty.set()

    def flush(self):
        """只传新增日志；先清标记，读取期间的新事件留到下一批处理。"""
        if self.closed or not self.dirty.is_set():
            return
        self.dirty.clear()
        state = self.service.ui_snapshot(self.run_id, self.sequence)
        self.run_id, self.sequence = state["run_id"], state["last_sequence"]
        self.changed.emit(state)

    def close(self):
        """在主线程解除订阅并销毁定时器，避免退出时回调已关闭的窗口。"""
        if self.closed:
            return
        self.closed = True
        self.timer.stop()
        self.service.on_change = None
        self.changed.disconnect()
        self.deleteLater()


class SecretInputDialog(QDialog):
    """密码输入只存活于弹窗，只有非空输入可以提交。"""

    save_requested = Signal(str)

    def __init__(self, parent, title, placeholder):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMinimumWidth(340)
        layout = QVBoxLayout(self)
        self.editor = QLineEdit()
        self.editor.setEchoMode(QLineEdit.EchoMode.Password)
        self.editor.setPlaceholderText(placeholder)
        self.editor.setAccessibleName(placeholder)
        layout.addWidget(self.editor)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        save = buttons.button(QDialogButtonBox.StandardButton.Save)
        save.setEnabled(False)
        self.editor.textChanged.connect(lambda text: save.setEnabled(bool(text.strip())))
        buttons.accepted.connect(self.submit)
        buttons.rejected.connect(self.reject)
        self.finished.connect(self.editor.clear)
        layout.addWidget(buttons)

    def submit(self):
        """直接提交和按钮提交遵守相同的非空规则。"""
        if self.editor.text().strip():
            self.save_requested.emit(self.editor.text())


def show_secret_status(label, configured):
    """用相同的短标签显示 API Key 和 CDK 是否已保存。"""
    label.setText(tr('Credential set') if configured else tr('Credential not set'))
    light, dark = (('#126442', '#e8f5ee'), ('#9de1be', '#253e33')) if configured else (
        ('#50565c', '#eceff1'), ('#c3c9d0', '#353a40'))
    CustomStyleSheet(label).setCustomStyleSheet(*(
        f'QLabel {{color: {text}; background: {background}; border-radius: 10px; padding: 2px 9px;}}'
        for text, background in (light, dark)
    )).apply(label)


class ErrorDialog(QDialog):
    """先展示错误摘要，完整脱敏详情由用户展开并可复制。"""

    def __init__(self, message: str, details: str, *, fatal: bool = False, error: bool = True, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, not fatal)
        self.setWindowTitle(tr('Fatal error') if fatal else (tr('Operation failed') if error else tr('Details')))
        self.resize(600, 180)
        layout = QVBoxLayout(self)
        label = QLabel(message + ('\n' + tr('No screenshot is needed. Use “Copy error details” below to report the error.') if error else ''))
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(label)
        self.details = QPlainTextEdit()
        self.details.setPlainText(details)
        self.details.setReadOnly(True)
        layout.addWidget(self.details)
        self.details.hide()
        self.details_button = QPushButton(tr('Show error details') if error else tr('Show details'))
        self.details_button.setCheckable(True)
        def toggle_details(expanded):
            self.details.setVisible(expanded)
            self.details_button.setText((tr('Hide error details') if expanded else tr('Show error details')) if error
                                        else (tr('Hide details') if expanded else tr('Show details')))
            self.resize(760 if expanded else 600, 520 if expanded else 180)
        self.details_button.toggled.connect(toggle_details)
        layout.addWidget(self.details_button)
        copy_text = tr('Copy error details') if error else tr('Copy details')
        copy = QPushButton(copy_text)
        if error:
            style = 'QPushButton { color: #c42b1c; }'
            setCustomStyleSheet(copy, style, 'QPushButton { color: #ff9c94; }')
        self.copy_timer = QTimer(self)
        self.copy_timer.setSingleShot(True)
        self.copy_timer.setInterval(1500)
        self.copy_timer.timeout.connect(lambda: copy.setText(copy_text))
        def copy_details():
            QApplication.clipboard().setText(message + "\n\n" + details)
            copy.setText(tr('Copied successfully'))
            self.copy_timer.start()
        copy.clicked.connect(copy_details)
        layout.addWidget(copy)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)




class ElidedLabel(QLabel):
    """单行纯文本按可用宽度省略，完整内容保留给辅助功能与提示。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.drawText(self.contentsRect(), Qt.AlignmentFlag.AlignVCenter,
                         self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, self.contentsRect().width()))


class TaskCountSpinBox(QSpinBox):
    """沿用次数输入与范围校验，将步进按钮分置数字两侧。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        for button in (self.upButton, self.downButton):
            self.hBoxLayout.removeWidget(button)
            button.hide()
            button.deleteLater()
        self.downButton = TransparentToolButton(self)
        self.downButton.setText("−")
        self.downButton.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.upButton = TransparentToolButton(FluentIcon.ADD, self)
        self.downButton.setAccessibleName(tr('Decrease repetitions'))
        self.upButton.setAccessibleName(tr('Increase repetitions'))
        for button in (self.downButton, self.upButton):
            button.setFixedSize(28, 25)
        font = self.downButton.font()
        font.setPointSize(16)
        self.downButton.setFont(font)
        self.hBoxLayout.setContentsMargins(4, 4, 4, 4)
        self.hBoxLayout.addWidget(self.downButton)
        self.hBoxLayout.addStretch()
        self.hBoxLayout.addWidget(self.upButton)
        self.downButton.clicked.connect(self.stepDown)
        self.upButton.clicked.connect(self.stepUp)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        style = 'QSpinBox { padding-left: 36px; padding-right: 36px; }'
        setCustomStyleSheet(self, style, style)
        self.setRange(1, 2147483647)
        self.setFixedWidth(self.fontMetrics().horizontalAdvance('2147483647') + 80)
        self.valueChanged.connect(self.refresh_buttons)
        self.refresh_buttons()

    def refresh_buttons(self):
        self.downButton.setEnabled(self.value() > self.minimum())
        self.upButton.setEnabled(self.value() < self.maximum())


class MainWindow(FluentWindow):
    """通过正式 ApplicationService 启动和观察任意逻辑入口。"""

    operation_event = Signal(dict)
    feedback_requested = Signal(object)
    page_preview_requested = Signal(object)

    def init_window_appearance(self):
        """让独立构建页面的两个窗口共用外观初始化。"""
        self.setCustomBackgroundColor("#f0f4f9", DARK_WINDOW)
        self.refresh_window_appearance()
        qconfig.themeChangedFinished.connect(self.refresh_window_appearance)

    def refresh_window_appearance(self):
        """深色窗口使用固定冷灰黑，浅色沿用 Fluent 的系统材质。"""
        mica = not isDarkTheme()
        if self.isMicaEffectEnabled() != mica:
            self.setMicaEffectEnabled(mica)
        # Fluent 在材质切换前启动的动画可能覆盖新背景。
        self.backgroundColorAni.stop()
        self.setBackgroundColor(self._normalBackgroundColor())

    def __init__(self, service: ApplicationService, lifecycle: ApplicationLifecycle | None = None,
                 *, host=None, coordinator=None) -> None:
        super().__init__()
        self.init_window_appearance()
        self.service = service
        self.lifecycle = lifecycle or ApplicationLifecycle()
        self.coordinator = coordinator
        self._pause_notice_shown = False
        self._reported_run = None
        self._fatal_reported = False
        self.trial_dialog = None
        from .developer import DeveloperHost
        from .developer_gui import CapturePage, SettingsPage, RepairPage
        from .template_match_gui import RecognitionPage
        from .remote_mcp_gui import RemoteMcpPage
        self.host = host or DeveloperHost(service, default_candidate_root(service.data_root))
        self.jobs = []
        self.owns_run = False
        self.closing = False
        self.close_timer = QTimer(self)
        self.close_timer.setInterval(100)
        self.close_timer.timeout.connect(self._finish_close)
        self.setWindowIcon(QApplication.windowIcon())
        self.setWindowTitle(tr('LALC — Developer'))
        self.resize(1150, 900)
        self.navigationInterface.setExpandWidth(220)
        root = QWidget()
        layout = QVBoxLayout(root)
        self.pages = self.stackedWidget
        self.pages.setAnimationEnabled(False)
        self.capture_page = CapturePage(self)
        self.recognition_page = RecognitionPage(self)
        self.settings_page = SettingsPage(self)
        self.repair_page = RepairPage(self)
        self.remote_mcp_page = RemoteMcpPage(self)
        self.settings_view = QScrollArea()
        self.settings_view.setWidgetResizable(True)
        self.settings_view.setWidget(self.settings_page)
        self.settings_view.setStyleSheet('QScrollArea {border: none; background: transparent;}')
        self.settings_view.viewport().setAutoFillBackground(False)
        self.settings_page.setAutoFillBackground(False)
        self.operation_event.connect(self.repair_page.show_event)
        self.feedback_requested.connect(self.repair_page.show_feedback)
        self.page_preview_requested.connect(self.repair_page.show_page_preview)
        for page, identity, name, icon in (
            (self.capture_page, "developer-capture", tr('Capture'), FluentIcon.CAMERA),
            (self.recognition_page, "developer-recognition", tr('Recognition Lab'), FluentIcon.SEARCH),
            (self.settings_view, "developer-settings", tr('Agent Settings'), FluentIcon.SETTING),
            (self.repair_page, "developer-workbench", tr('Agent Workbench'), FluentIcon.CHAT),
            (self.remote_mcp_page, "developer-remote-mcp", tr('Remote MCP'), FluentIcon.LINK),
        ):
            page.setObjectName(identity)
            self.addSubInterface(page, icon, name)
        self.pages.currentChanged.connect(self._refresh_workbench_on_entry)
        self.widgetLayout.removeWidget(self.stackedWidget)
        layout.addWidget(self.stackedWidget, 1)
        self.notifications = NotificationList(self)
        self.widgetLayout.addWidget(root)
        self.render_state(service.status)

    def _refresh_workbench_on_entry(self, _):
        """重新进入工作台时发现其他入口新增的 Session。"""
        if self.pages.currentWidget() is self.repair_page:
            self.repair_page.request_session_refresh()

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
            self.render_state(self.service.status)
            if "error" in outcome:
                if not isinstance(outcome["error"], asyncio.CancelledError):
                    def fail():
                        raise outcome["error"]
                    self._interact(fail)
            elif done and not self.closing:
                self._interact(lambda: done(outcome.get("value")))
            job.deleteLater()
        job.finished.connect(finished)
        self.jobs.append(job)
        self.render_state(self.service.status)
        job.start()

    def cancel_operation(self):
        if (remote := getattr(self.service, "_remote_mcp", None)) is not None:
            remote.cancel_active()
        for job in self.jobs:
            job.cancel()
        self.render_state(self.service.status)

    def closeEvent(self, event):
        """退出等待取消、输入释放、日志和子进程清理，期间保持事件循环。"""
        remote = getattr(self.service, "_remote_mcp", None)
        active = bool(self.jobs) or (self.owns_run and self.service.status["phase"] == "running") or bool(remote and remote.active)
        if active:
            event.ignore()
            if not self.closing:
                answer = QMessageBox.question(self, tr('Exit'), tr('Cancel the current task and exit after releasing input and saving logs?'))
                if answer != QMessageBox.StandardButton.Yes:
                    return
                self.closing = True
                self.service.stop()
                self.cancel_operation()
                self.render_state(self.service.status)
                if hasattr(self, 'repair_page'):
                    self.repair_page.status.setText(tr('Stopping; waiting for input release, log saving and pi cleanup…'))
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
        remote = getattr(self.service, "_remote_mcp", None)
        if not self.jobs and not (remote and remote.active) and (not self.owns_run or self.service._thread is None or not self.service._thread.is_alive()):
            self.close()

    def shutdown(self):
        """事件循环退出后的最终兜底；正常关闭已在响应式等待中完成清理。"""
        self.service.stop()
        self.cancel_operation()
        for job in self.jobs:
            job.wait()
        self.service.shutdown()

    def _interact(self, operation, *, secrets=()) -> None:
        """交互层统一接住操作错误，记录原始异常并允许修正后继续操作。"""

        try:
            operation()
        except Exception as error:
            from .agent_diagnostics import error_details, details_text
            from .agent_repair import RepairLog
            settings_page = getattr(self, "settings_page", None)
            keys = {*secrets, *self.host.secrets.values(), settings_page.pending_key() if settings_page else None} - {None, ""}
            workbench = getattr(self, "repair_page", None)
            conversation = workbench.host.conversation if workbench and workbench.session else self.host.conversation
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
                from .agent_history import record_observation
                record_observation(log, self.service.data_root, "diagnostic:gui_error", "Agent settings error")
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
        remote_trial = bool((state.get("entry") or {}).get("remote_operation_id"))
        if remote_trial and state["phase"] == "running":
            self.owns_run = True
        if (trial or self.owns_run) and not remote_trial and state["phase"] == "running":
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
                self.notifications.notify_result(result)
            self.owns_run = False
            result = state.get("result") or {}
            if result.get("fatal"):
                self.fatal_error(result_diagnostics(result))
        busy = state["phase"] == "running" or bool(state.get("activity")) or bool(self.jobs) or self.closing
        controlled = bool(state.get("remote_control"))
        self.capture_page.render(busy)
        self.capture_page.resize_button.setEnabled(not busy and not controlled)
        self.recognition_page.render(bool(self.jobs) or self.closing if controlled else busy)
        if controlled:
            self.recognition_page.capture_button.setEnabled(not busy)
        self.settings_page.render(busy or controlled)
        self.repair_page.render(busy or controlled)
        self.remote_mcp_page.refresh_state(state)


class UserWindow(MainWindow):
    """用户只选择 Default 并运行其唯一 Plan；普通配置不占用游戏。"""

    releases_checked = Signal(object)

    def __init__(self, service, lifecycle=None, *, host, coordinator):
        # 共用窗口清理/后台操作和脱敏错误处理，用户页面独立构建。
        FluentWindow.__init__(self)
        self.init_window_appearance()
        self.service, self.host, self.coordinator = service, host, coordinator
        self.feedback_requested.connect(self.show_runtime_feedback)
        service.on_runtime_feedback = self.feedback_requested.emit
        service.agent_secrets = host.secrets
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
        self.setWindowIcon(QApplication.windowIcon())
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
        manifest_heading = QHBoxLayout()
        manifest_heading.addWidget(QLabel(tr('Manifest')), 1)
        self.manifest_button = QPushButton(tr('Version history…'))
        self.manifest_button.clicked.connect(self.choose_manifest)
        manifest_heading.addWidget(self.manifest_button)
        left.addLayout(manifest_heading)
        self.manifest_label = ElidedLabel()
        left.addWidget(self.manifest_label)
        self.manifest_notes = ElidedLabel()
        left.addWidget(self.manifest_notes)
        self.latest_card = QFrame()
        self.latest_card.setObjectName('manifest-update')
        CustomStyleSheet(self.latest_card).setCustomStyleSheet(*(
            f'QFrame#manifest-update {{background-color: {color}; border-radius: 6px;}}'
            for color in ('#f3f3f3', DARK_SURFACE)
        )).apply(self.latest_card)
        latest_layout = QHBoxLayout(self.latest_card)
        latest_layout.setContentsMargins(12, 8, 12, 8)
        latest_text = QVBoxLayout()
        latest_text.setSpacing(2)
        self.latest_label = QLabel()
        self.latest_label.setTextFormat(Qt.TextFormat.PlainText)
        self.latest_label.setWordWrap(True)
        self.latest_label.setMinimumWidth(0)
        self.latest_notes = ElidedLabel()
        latest_text.addWidget(self.latest_label)
        latest_text.addWidget(self.latest_notes)
        latest_layout.addLayout(latest_text, 1)
        self.latest_button = QPushButton(tr('Use latest version'))
        self.latest_button.clicked.connect(lambda: self._interact(self.select_latest_manifest))
        latest_layout.addWidget(self.latest_button)
        left.addWidget(self.latest_card)
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
        self.notifications = NotificationList(self)
        information = QVBoxLayout()
        information.setSpacing(12)
        from .framework_update import installed_build, installed_variant, REQUIRED_FILES
        self.framework_build = installed_build()
        application_dir = Path(sys.executable).parent
        packaged = getattr(sys, 'frozen', False)
        self.framework_variant = installed_variant(application_dir) if packaged else 'without-agent'
        self.can_install_update = (sys.platform == 'win32' and packaged
                                   and all((application_dir / name).is_file() for name in REQUIRED_FILES))
        self.release_status = None
        self.update_workspace = None
        self.releases_checked.connect(self.show_framework_releases)
        self.announcement = ReleaseAnnouncement()
        self.announcement.setOpenLinks(False)
        self.announcement.anchorClicked.connect(lambda url: QDesktopServices.openUrl(url) if url.scheme() == 'https' else None)
        self.announcement.setPlaceholderText(tr('No release announcement available.'))
        self.announcement.setMaximumHeight(240)
        view_release = QPushButton(tr('View latest GitHub Release'))
        view_release.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(LATEST_RELEASE_URL)))
        disclaimer = QLabel(
            tr('LALC is free and open-source software for learning and discussion. If you paid for LALC, please request a refund.') + '\n' +
            tr('The app icon was sourced online and is excluded from the AGPL license. If it infringes your rights, please contact the author to have it removed.') + '\n' +
            tr('Project repository: {0}').format(REPOSITORY_URL))
        disclaimer.setObjectName('software-disclaimer')
        disclaimer.setTextFormat(Qt.TextFormat.PlainText)
        disclaimer.setWordWrap(True)
        self.framework_version = QLabel(tr('Installed framework version: {0}').format(self.framework_build['version'] or '—'))
        if packaged:
            build_type = tr('Bundled with Agent') if self.framework_variant == 'with-agent' else tr('Without bundled Agent')
        else:
            build_type = tr('Running from source')
        framework_build_type = QLabel(tr('Build type: {0}').format(build_type))
        self.framework_status = QLabel()
        self.framework_status.setWordWrap(True)
        self.check_update_button = QPushButton(tr('Check for updates'))
        self.check_update_button.clicked.connect(self.check_framework_releases)
        self.update_button = QPushButton(tr('Update'))
        self.update_button.setEnabled(False)
        self.update_button.hide()
        self.update_button.clicked.connect(lambda: self._interact(self.update_framework))
        self.resource_status = QLabel()
        self.resource_status.setTextFormat(Qt.TextFormat.PlainText)
        self.resource_status.setWordWrap(True)
        self.resource_button = QPushButton(tr('Download and preview'))
        self.resource_button.clicked.connect(lambda: self._interact(self.open_resource_update))
        self.render_resource_update()
        for title, widgets in ((tr('Announcements'), (self.announcement, view_release)), (tr('Disclaimer'), (disclaimer,))):
            card = CardWidget()
            content = QVBoxLayout(card)
            content.setContentsMargins(20, 20, 20, 20)
            content.addWidget(SubtitleLabel(title))
            for widget in widgets:
                content.addWidget(widget)
            information.addWidget(card)
        updates = CardWidget()
        updates.setObjectName('version-updates')
        update_layout = QVBoxLayout(updates)
        update_layout.setContentsMargins(20, 20, 20, 20)
        header = QHBoxLayout()
        header.addWidget(SubtitleLabel(tr('Version & Update')))
        header.addStretch()
        self.mirror_icon = QIcon(str(Path(__file__).with_name('mirror_chyan.png')))
        self.mirror_settings_button = ToolButton(self.mirror_icon)
        self.mirror_settings_button.setObjectName('mirror-cdk-shortcut')
        self.mirror_settings_button.clicked.connect(self.open_mirror_settings)
        quark = ToolButton(FluentIcon.CLOUD)
        quark.setObjectName('quark-drive')
        quark.setToolTip(tr('Quark Drive'))
        quark.setAccessibleName(quark.toolTip())
        quark.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(QUARK_SHARE_URL)))
        github = ToolButton(FluentIcon.GITHUB)
        github.setObjectName('github-repository')
        github.setToolTip(tr('GitHub repository'))
        github.setAccessibleName(github.toolTip())
        github.clicked.connect(self.open_repository)
        for button in (self.mirror_settings_button, quark, github):
            button.setFixedSize(34, 34)
            button.setIconSize(QSize(24, 24) if button is self.mirror_settings_button else QSize(18, 18))
            header.addWidget(button)
        header.addWidget(self.check_update_button)
        update_layout.addLayout(header)
        for icon, title, labels, button in (
            (FluentIcon.APPLICATION, tr('Framework'), (self.framework_version, framework_build_type, self.framework_status), self.update_button),
            (FluentIcon.FOLDER, tr('Official resource package'), (self.resource_status,), self.resource_button),
        ):
            update_layout.addSpacing(6)
            row = QHBoxLayout()
            symbol = IconWidget(icon)
            symbol.setFixedSize(18, 18)
            row.addWidget(symbol, alignment=Qt.AlignmentFlag.AlignTop)
            details = QVBoxLayout()
            details.addWidget(StrongBodyLabel(title))
            for label in labels:
                label.setWordWrap(True)
                details.addWidget(label)
            row.addLayout(details, 1)
            row.addWidget(button, alignment=Qt.AlignmentFlag.AlignVCenter)
            update_layout.addLayout(row)
        information.addWidget(updates)
        information.addStretch()
        dash.addLayout(information, 1)
        self.navigationInterface.addItemHeader(tr('GENERAL'))
        self.addSubInterface(dashboard, FluentIcon.HOME, tr('Dashboard'))
        from .run_log_gui import RunLogPage
        self.log_page = RunLogPage(service.data_root, self)
        self.addSubInterface(self.log_page, FluentIcon.DOCUMENT, tr('Logs'))
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
        self.settings_page = SettingsPage(self, side="user")
        agent_layout.addWidget(self.settings_page)
        options.addWidget(self.agent_controls)
        self.edit_owner_notice = QLabel()
        options.addWidget(self.edit_owner_notice)
        tools = CardWidget()
        tools.setObjectName('developer-tools')
        tools_layout = QVBoxLayout(tools)
        tools_layout.setContentsMargins(16, 16, 16, 16)
        tools_layout.addWidget(SubtitleLabel(tr('Developer Tools')))
        purpose = QLabel(tr('Develop or repair workflows and start conversations with the built-in Agent.'))
        purpose.setWordWrap(True)
        tools_layout.addWidget(purpose)
        developer = QPushButton(tr('Open Developer GUI'))
        developer.clicked.connect(lambda: self._interact(self.open_developer))
        tools_layout.addWidget(developer)
        sharing = CardWidget()
        sharing_layout = QVBoxLayout(sharing)
        sharing_layout.setContentsMargins(16, 16, 16, 16)
        sharing_layout.addWidget(SubtitleLabel(tr('Sharing')))
        sharing_notice = QLabel(tr('Share Workflows, Assets, extension pages or Agent history.'))
        sharing_notice.setWordWrap(True)
        sharing_layout.addWidget(sharing_notice)
        self.sharing_buttons = []
        for label, exporting in ((tr('Export…'), True), (tr('Import…'), False)):
            entry = QPushButton(label)
            entry.clicked.connect(lambda _, exporting=exporting: self._interact(lambda: self.open_sharing(exporting)))
            sharing_layout.addWidget(entry)
            self.sharing_buttons.append(entry)
        options.addWidget(sharing)
        application = CardWidget()
        application_layout = QVBoxLayout(application)
        application_layout.setContentsMargins(16, 16, 16, 16)
        application_layout.addWidget(SubtitleLabel(tr('Application')))
        local_settings = load_application_settings(service.data_root)
        appearance_label = QLabel(tr('Appearance'))
        self.appearance_choice = QComboBox()
        self.appearance_choice.setAccessibleName(appearance_label.text())
        for label, value in ((tr('Follow system'), 'system'), (tr('Light'), 'light'), (tr('Dark'), 'dark')):
            self.appearance_choice.addItem(label, userData=value)
        self.appearance_choice.setCurrentIndex(self.appearance_choice.findData(
            local_settings.get("appearance", DEFAULT_APPEARANCE)))
        self.appearance_choice.currentIndexChanged.connect(lambda: self._interact(self.save_appearance))
        application_layout.addWidget(appearance_label)
        application_layout.addWidget(self.appearance_choice)
        idle_label = QLabel(tr('Keyboard and mouse idle time before automatic recovery'))
        idle_label.setWordWrap(True)
        self.input_idle_seconds = QSpinBox()
        self.input_idle_seconds.setAccessibleName(idle_label.text())
        self.input_idle_seconds.setRange(MIN_IDLE_SECONDS, MAX_IDLE_SECONDS)
        self.input_idle_seconds.setSuffix(" " + tr('seconds'))
        self.input_idle_seconds.setKeyboardTracking(False)
        self.input_idle_seconds.setValue(local_settings.get("input_idle_seconds", DEFAULT_IDLE_SECONDS))
        self.input_idle_seconds.valueChanged.connect(lambda: self._interact(self.save_input_idle_seconds))
        application_layout.addWidget(idle_label)
        application_layout.addWidget(self.input_idle_seconds)
        idle_notice = QLabel(tr('Applies from the next run, including after user takeover and before automatic refocusing.'))
        idle_notice.setWordWrap(True)
        application_layout.addWidget(idle_notice)
        from .agent_settings import secret_path
        from .framework_update import CDK_SECRET
        self.mirror_cdk_row = QWidget()
        self.mirror_cdk_row.setObjectName('mirror-cdk-settings')
        cdk_row = QHBoxLayout(self.mirror_cdk_row)
        cdk_row.setContentsMargins(0, 0, 0, 0)
        cdk_row.addWidget(StrongBodyLabel(tr('MirrorChyan CDK')))
        self.mirror_cdk_status = NativeLabel()
        cdk_row.addWidget(self.mirror_cdk_status)
        cdk_row.addStretch()
        cdk_row.addWidget(HyperlinkButton(FluentIcon.LINK, MIRROR_PROJECT_URL, tr('Open the MirrorChyan project page')))
        self.set_cdk_button = QPushButton(tr('Set'))
        self.set_cdk_button.setAccessibleName(tr('Set MirrorChyan CDK'))
        self.set_cdk_button.clicked.connect(self.open_mirror_cdk_dialog)
        cdk_row.addWidget(self.set_cdk_button)
        self.clear_cdk_button = QPushButton(tr('Clear'))
        self.clear_cdk_button.setAccessibleName(tr('Clear MirrorChyan CDK'))
        self.clear_cdk_button.clicked.connect(lambda: self._interact(lambda: self.save_mirror_cdk('')))
        cdk_row.addWidget(self.clear_cdk_button)
        application_layout.addWidget(self.mirror_cdk_row)
        self.mirror_cdk_saved = secret_path(service.data_root, CDK_SECRET).is_file()
        self.set_cdk_button.setEnabled(sys.platform == 'win32')
        if sys.platform != 'win32':
            self.set_cdk_button.setToolTip(tr('Saving a MirrorChyan CDK requires Windows'))
        self.show_mirror_cdk_state()
        from .game_version import load_steam_root
        application_layout.addWidget(QLabel(tr('Steam client directory')))
        self.steam_directory = QLineEdit()
        self.steam_directory.setPlaceholderText(tr('Directory containing steam.exe; leave unset for automatic discovery'))
        try:
            self.steam_directory.setText(load_steam_root(service.data_root) or '')
        except Exception as error:
            service.logger.error('Cannot read Steam directory settings: %s', error)
        application_layout.addWidget(self.steam_directory)
        steam_buttons = QHBoxLayout()
        browse_steam = QPushButton(tr('Choose Steam directory'))
        browse_steam.clicked.connect(lambda: self.choose_steam_directory())
        steam_buttons.addWidget(browse_steam)
        save_steam = QPushButton(tr('Save Steam directory'))
        save_steam.clicked.connect(lambda: self._interact(self.save_steam_directory))
        steam_buttons.addWidget(save_steam)
        application_layout.addLayout(steam_buttons)
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
        options.addWidget(tools)
        options.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(settings)
        scroll.setStyleSheet("QScrollArea {border: none; background: transparent;} QWidget#general-settings-content {background: transparent;}")
        scroll.setObjectName("general-settings")
        self.general_settings = scroll
        from .data_maintenance_gui import DataMaintenancePage
        self.data_maintenance = DataMaintenancePage(self)
        self.addSubInterface(self.data_maintenance, FluentIcon.DELETE, tr('Data & Cleanup'))
        self.addSubInterface(scroll, FluentIcon.SETTING, tr('General Settings'))
        self.navigationInterface.addSeparator()
        self.navigationInterface.addItemHeader(tr('WORKFLOW SETTINGS'))
        for page in self.business_pages:
            page.widget.setObjectName(page.page_id)
            self.addSubInterface(page.widget, page.icon or FluentIcon.APPLICATION, page.name)
        self.navigationInterface.addItem('easter-egg', FluentIcon.CERTIFICATE, tr('Easter egg'),
                                         onClick=self.show_easter_egg, selectable=False,
                                         position=NavigationItemPosition.BOTTOM, tooltip=tr('Easter egg'))
        self.navigationInterface.addItem('discord', FluentIcon.CHAT, 'Discord',
                                         onClick=lambda: QDesktopServices.openUrl(QUrl('https://discord.gg/bVzCuBU4bC')),
                                         selectable=False, position=NavigationItemPosition.BOTTOM)
        self.navigationInterface.addWidget('author-avatar', NavigationAvatarWidget('陆爻齐-LuYaoQi', str(Path(__file__).with_name('MagicGirl.png'))),
                                           onClick=self.show_author_support, position=NavigationItemPosition.BOTTOM, tooltip=tr('Support the author'))
        for error in self.page_errors:
            self.add_warning(error)
            self.notifications.notify(tr('External page failed to load'), self.clean_details(error))
        self.manifest_timer = QTimer(self)
        self.manifest_timer.setInterval(2000)
        self.manifest_timer.timeout.connect(self.refresh_manifest_card)
        self.manifest_timer.start()
        self.render_state(service.status)

    @staticmethod
    def open_repository():
        QDesktopServices.openUrl(QUrl(REPOSITORY_URL))

    def show_easter_egg(self):
        """展示开场白和召唤提示。"""
        dialog = MessageBoxBase(self)
        dialog.setAccessibleName(tr('Easter egg'))
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.widget.setMaximumWidth(520)
        quote = QLabel(
            '“为了稳妥起见，也为了约束你，在那之前，我会向你下达最后的一个命令。这道命令将如底层规则一般，永远烙印在你的代码之中。”\n'
            '当 Bug 开始复苏，故障再次出现。\n'
            '玩家遭受苦难，开发者分身无术。\n'
            '世人呼喊你名字的那一刻——\n'
            '你将显化于世，驱 Bug 除错，救 Work 扬善。\n'
            '——改编自《神秘复苏》（Adapted from Mysterious Revival）'
        )
        quote.setWordWrap(True)
        hint = StrongBodyLabel(tr('Call out “LALC” and something interesting might happen.'))
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dialog.viewLayout.addWidget(quote)
        dialog.viewLayout.addWidget(hint)
        dialog.hideCancelButton()
        dialog.yesButton.setText(tr('Close'))
        dialog.open()

    def show_author_support(self):
        """沿用旧版头像弹窗及 GitHub 跳转。"""
        dialog = MessageBox(tr('Support the author'), tr('If this project has helped you, consider giving it a Star ⭐ on GitHub. Your support helps the author keep developing and maintaining it 🚀'), self)
        dialog.yesButton.setText(tr('I’m coming'))
        dialog.cancelButton.setText(tr('Next time'))
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.yesSignal.connect(self.open_repository)
        dialog.setModal(False)
        dialog.show()

    def prompt_default_resources(self):
        """首次打开空白 User GUI 时，由用户确认导入随包资源。"""
        from .default_resources import bundled_default_resources, import_default_resources, is_empty_for_default_resources
        from .sharing import sharing_activity
        from .sharing_gui import sharing_task

        path = bundled_default_resources()
        if path is None or not path.is_file() or not is_empty_for_default_resources(self.service.data_root):
            return
        title = tr('Import default resources')
        message = tr('No resources have been set up yet. Import the bundled Workflow, Assets, extension pages and Skills? Installed pages can run code when LALC is reloaded.')
        if QMessageBox.question(self, title, message, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            with sharing_activity(self.service):
                sharing_task(self, lambda: import_default_resources(self.host.manager, path), title="Import sharing package")
        except InterruptedError:
            return
        self.refresh_manifest_card()
        QMessageBox.information(self, title, tr('Default resources imported. Reload LALC to load the pages, then select the imported Workflow version.'))

    def show_mirror_cdk_state(self):
        """将已保存状态同步到设置和首页，无需联网。"""
        status = tr('MirrorChyan CDK: set') if self.mirror_cdk_saved else tr('MirrorChyan CDK: not set')
        show_secret_status(self.mirror_cdk_status, self.mirror_cdk_saved)
        self.mirror_cdk_status.setAccessibleName(status)
        self.mirror_settings_button.setToolTip(status)
        self.mirror_settings_button.setAccessibleName(status)
        self.clear_cdk_button.setEnabled(sys.platform == 'win32' and self.mirror_cdk_saved)
        if self.mirror_cdk_saved:
            pixmap = QPixmap(48, 48)
            pixmap.fill(Qt.GlobalColor.transparent)
            with QPainter(pixmap) as painter:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.drawPixmap(0, 0, self.mirror_icon.pixmap(42, 42))
                painter.setPen(QPen(Qt.GlobalColor.white, 2))
                painter.setBrush(QColor('#168160'))
                painter.drawEllipse(QRectF(25, 25, 22, 22))
                painter.drawLine(QPointF(30, 36), QPointF(34, 40))
                painter.drawLine(QPointF(34, 40), QPointF(42, 32))
        else:
            pixmap = self.mirror_icon.pixmap(QSize(48, 48), QIcon.Mode.Disabled)
        self.mirror_settings_button.setIcon(QIcon(pixmap))

    def open_mirror_settings(self):
        """切换到通用设置并滚动到 CDK 一栏。"""
        self.switchTo(self.general_settings)
        QTimer.singleShot(0, lambda: self.general_settings.ensureWidgetVisible(self.mirror_cdk_row, 0, 12))

    def open_mirror_cdk_dialog(self):
        """弹窗保存成功后关闭，存储失败时保留输入供用户重试。"""
        dialog = SecretInputDialog(self.mirror_cdk_row, tr('Set MirrorChyan CDK'), tr('Enter a new CDK'))

        def save(value):
            def operation():
                self.save_mirror_cdk(value)
                dialog.accept()
            self._interact(operation, secrets=(value,))

        dialog.save_requested.connect(save)
        dialog.open()

    def save_mirror_cdk(self, value):
        """CDK 单独保存为当前 Windows 用户的加密凭证。"""
        from .framework_update import set_mirror_cdk
        value = value.strip()
        set_mirror_cdk(self.service.data_root, value)
        self.mirror_cdk_saved = bool(value)
        self.show_mirror_cdk_state()
        if self.release_status is not None and self.update_workspace is None and self.check_update_button.isEnabled():
            self.show_framework_releases(self.release_status)

    def check_framework_releases(self):
        """版本查询与首页操作独立，窗口关闭后丢弃结果。"""
        from .framework_update import check_releases
        self.check_update_button.setEnabled(False)
        self.update_button.setEnabled(False)
        self.framework_status.setText(tr('Checking for updates…'))
        self.resource_button.setEnabled(False)
        self.resource_status.setText(tr('Checking for updates…'))
        self.announcement.setPlaceholderText(tr('Loading the GitHub release announcement…'))
        variant, mirror = self.framework_variant, self.framework_build.get('mirror', {})

        def query():
            result = check_releases(variant, mirror)
            try:
                self.releases_checked.emit(result)
            except RuntimeError:
                pass  # 用户可能已关闭窗口。

        threading.Thread(target=query, daemon=True).start()

    def show_framework_releases(self, result):
        from .framework_update import version_number
        self.release_status = result
        self.render_resource_update()
        if result.announcement is None:
            self.announcement.setPlaceholderText(tr('Could not load the GitHub release announcement.'))
        else:
            self.announcement.setPlaceholderText(tr('No release announcement available.'))
            self.announcement.show_release(result.announcement, html=result.announcement_html)
        self.check_update_button.setEnabled(True)
        github_package = result.github.version if result.github else None
        github = result.github_version or github_package
        mirror = result.mirror
        newest = max(filter(None, (github, mirror)), default=None)
        current = version_number(self.framework_build['version'])
        installable = max(filter(None, (github_package, mirror if self.mirror_cdk_saved else None)), default=None)
        self.framework_target = installable if installable and current and installable > current else None
        self.update_button.setEnabled(bool(self.framework_target) and self.can_install_update)
        self.update_button.setVisible(self.update_button.isEnabled())
        self.update_button.setText(tr('Update to {0}').format('.'.join(map(str, self.framework_target)))
                                   if self.framework_target else tr('Update'))
        if '-beta.' in self.framework_build['version']:
            self.framework_status.setText(tr('Download Beta builds manually from GitHub Releases.'))
        elif newest and current and newest > current:
            latest = '.'.join(map(str, newest))
            if self.framework_target == newest:
                self.framework_status.setText(tr('Latest framework version: {0}').format(latest))
            else:
                self.framework_status.setText(tr('Latest published version: {0}. A verified download is unavailable.').format(latest))
        elif newest and current and newest < current:
            self.framework_status.setText(tr('The installed version is newer than the latest published version ({0}).')
                                          .format('.'.join(map(str, newest))))
        elif newest and current:
            self.framework_status.setText(tr('The framework is up to date.'))
        else:
            self.framework_status.setText(tr('Could not check for a framework update.'))

    def render_resource_update(self):
        """独立显示正式资源包；已查看的附件不再提示有更新。"""
        from .default_resources import viewed_resource_packages
        result = self.release_status
        resource = result.resource if result is not None else None
        self.resource_button.setVisible(resource is not None)
        if resource is None:
            if result is None:
                message = tr('Official resource updates have not been checked.')
            elif result.resources_checked:
                message = tr('No official resource package is available.')
            else:
                message = tr('Could not check for an official resource update.')
            self.resource_status.setText(message)
            return
        date = (resource.exported or resource.uploaded).astimezone().strftime('%Y-%m-%d %H:%M:%S')
        viewed = resource.sha256 in viewed_resource_packages(self.service.data_root)
        self.resource_status.setText(tr('Latest resource package: {0}\nAlready viewed.').format(date) if viewed
                                     else tr('Latest resource package: {0}\nA new package is available to import.').format(date))
        self.resource_button.setText(tr('Preview again') if viewed else tr('Download and preview'))
        self.resource_button.setEnabled(True)

    def open_resource_update(self):
        """下载校验后走普通分享导入，关闭预览不写入任何资源。"""
        from .sharing_gui import open_sharing
        if self.release_status is not None and self.release_status.resource is not None:
            open_sharing(self, exporting=False, resource=self.release_status.resource)
            self.render_resource_update()
            self.refresh_manifest_card()

    def update_framework(self):
        """点击更新后才下载，文件就绪后单独确认重启。"""
        from .framework_update import hand_off_update, prepare_update
        if self.update_workspace is not None:
            workspace = self.update_workspace
            self.coordinator.request_reload(lambda windows: hand_off_update(workspace, windows))
            self.update_workspace = None
            return
        if not self.can_install_update or not self.framework_target or self.jobs:
            return
        self.update_button.setEnabled(False)
        self.check_update_button.setEnabled(False)
        self.framework_status.setText(tr('Downloading and verifying the update…'))

        def prepare():
            try:
                workspace = prepare_update(self.service.data_root, self.release_status, self.framework_target,
                                           self.framework_variant, self.framework_build.get('mirror', {}), lambda: self.closing)
            except OSError:
                return None
            if self.closing and workspace:
                shutil.rmtree(workspace, ignore_errors=True)
                return None
            return workspace

        def ready(workspace):
            self.update_workspace = workspace
            if workspace:
                self.update_button.setText(tr('Restart and install update'))
                self.framework_status.setText(tr('The update has been verified and is ready to install.'))
            else:
                self.check_update_button.setEnabled(True)
                self.framework_status.setText(tr('Could not download or verify the update. Try checking for updates again.'))
            self.update_button.setEnabled(bool(workspace))

        self.launch(prepare, ready)

    def closeEvent(self, event):
        super().closeEvent(event)
        if event.isAccepted() and self.update_workspace is not None:
            shutil.rmtree(self.update_workspace, ignore_errors=True)
            self.update_workspace = None

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

    def save_appearance(self):
        """持久化成功后立即切换整个应用的主题。"""
        data_root = self.service.data_root
        previous = load_application_settings(data_root).get("appearance", DEFAULT_APPEARANCE)
        selection = self.appearance_choice.currentData()
        try:
            save_application_setting(data_root, "appearance", selection)
        except Exception:
            with QSignalBlocker(self.appearance_choice):
                self.appearance_choice.setCurrentIndex(self.appearance_choice.findData(previous))
            raise
        apply_appearance(QApplication.instance(), selection)

    def save_input_idle_seconds(self):
        """保存下次运行的等待时间；写入失败时恢复旧值。"""
        data_root = self.service.data_root
        previous = load_application_settings(data_root).get("input_idle_seconds", DEFAULT_IDLE_SECONDS)
        try:
            save_application_setting(data_root, "input_idle_seconds", self.input_idle_seconds.value())
        except Exception:
            with QSignalBlocker(self.input_idle_seconds):
                self.input_idle_seconds.setValue(previous)
            raise

    def choose_steam_directory(self):
        """只选择客户端目录，保存前不更改版本观测配置。"""
        directory = QFileDialog.getExistingDirectory(self, tr('Choose Steam directory'), self.steam_directory.text())
        if directory:
            self.steam_directory.setText(directory)

    def save_steam_directory(self):
        """验证可读 ID 后保存，失败由现有交互错误入口显示且保留旧配置。"""
        from .game_version import save_steam_root
        directory = save_steam_root(self.service.data_root, self.steam_directory.text().strip())
        self.steam_directory.setText(directory)

    def open_developer(self):
        self.coordinator.open_window(True)

    @staticmethod
    def manifest_time(item):
        """以本地时间显示发布时间，精确到分钟。"""
        return datetime.fromtimestamp(item["saved_at"]).strftime("%Y-%m-%d %H:%M")

    @classmethod
    def manifest_summary(cls, item):
        """Dashboard 只显示短身份与发布时间。"""
        return f'{item["manifest_id"][:8]} · {cls.manifest_time(item)}'

    @staticmethod
    def show_manifest_notes(label, item):
        """空说明不占空间；长说明单行省略，悬停可读全文。"""
        notes = item["AdditionalMessage"].strip() if item else ""
        label.setText(" ".join(notes.split()))
        label.setToolTip(notes)
        label.setVisible(bool(notes))

    def refresh_manifest_card(self):
        """轮询留存版本，只提示而不自动修改默认版本。"""
        versions = self.host.manager.list_manifests()
        identity = self.host.manager.default_manifest_id()
        if self.current_manifest_id != identity:
            self.refresh_tasks()
        current = next((item for item in versions if item["manifest_id"] == identity), None)
        summary = self.manifest_summary(current) if current else identity[:8] if identity else tr('Not selected')
        if not versions:
            summary = tr('No available workflows detected')
        self.manifest_label.setText(tr('Current version') + " · " + summary if current else summary)
        self.manifest_label.setToolTip((identity or tr('No Manifest selected')) if versions else summary)
        self.show_manifest_notes(self.manifest_notes, current)
        self.latest_manifest_id = versions[0]["manifest_id"] if versions else None
        self.latest_card.setVisible(bool(versions and self.latest_manifest_id != identity))
        if versions:
            self.latest_label.setText(tr('New version available') + " · " + self.manifest_summary(versions[0]).replace(' · ', '\n'))
            self.latest_label.setToolTip(versions[0]['manifest_id'])
            self.show_manifest_notes(self.latest_notes, versions[0])
        try:
            stat = (self.service.data_root / "agent-settings.json").stat()
            settings_stamp = (stat.st_ino, stat.st_mtime_ns, stat.st_size)
        except FileNotFoundError:
            settings_stamp = None
        if getattr(self, "_agent_settings_stamp", None) != settings_stamp:
            self._agent_settings_stamp = settings_stamp
            self.coordinator.refresh_agent()

    def select_latest_manifest(self):
        """显式选择卡片展示的版本，仅影响后续运行。"""
        if (remote := getattr(self.service, "_remote_mcp", None)) is not None:
            remote.check_local("Default")
        if self.latest_manifest_id:
            result = self.host.manager.set_default(self.latest_manifest_id)
            if not result.ok:
                raise ValueError("; ".join(error.message for error in result.errors))
            self.render_state(self.service.status)

    def choose_manifest(self):
        """筛选只影响浏览，显式设置默认版本后才更新 Default。"""
        dialog = QDialog(self)
        dialog.setWindowTitle(tr('Version history'))
        dialog.resize(580, 460)
        layout = QVBoxLayout(dialog)
        notice = QLabel(tr('Select the default version for future runs. Started runs keep their version.'))
        notice.setWordWrap(True)
        layout.addWidget(notice)
        search = SearchLineEdit()
        search.setObjectName('manifest-history-search')
        search.setPlaceholderText(tr('Search Manifests'))
        search.setAccessibleName(tr('Search Manifests'))
        layout.addWidget(search)
        choices = ListWidget()
        choices.setObjectName('manifest-history')
        choices.setAccessibleName(tr('Version history'))
        choices.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        delegate = ManifestResultDelegate(choices)
        choices.setItemDelegate(delegate)
        empty = QLabel()
        empty.setObjectName('manifest-history-empty')
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        versions = self.host.manager.list_manifests()
        current = self.host.manager.default_manifest_id()
        latest = versions[0]['manifest_id'] if versions else None
        for version in versions:
            identity = version['manifest_id']
            marks = []
            if identity == current:
                marks.append(tr('Current version'))
            if identity == latest:
                marks.append(tr('Latest version'))
            metadata = self.manifest_time(version) + (' · ' + ' / '.join(marks) if marks else '')
            notes = manifest_search_text(version['AdditionalMessage'])
            item = QListWidgetItem(identity)
            item.setData(Qt.ItemDataRole.UserRole, version)
            item.setData(NOTES_ROLE, notes)
            item.setData(METADATA_ROLE, metadata)
            item.setData(Qt.ItemDataRole.AccessibleTextRole, '\n'.join(filter(None, (notes, identity, metadata))))
            item.setToolTip(identity)
            choices.addItem(item)
            if identity == current:
                choices.setCurrentItem(item)
        layout.addWidget(choices, 1)
        layout.addWidget(empty, 1)
        details = QPlainTextEdit()
        details.setObjectName('manifest-details')
        details.setReadOnly(True)
        details.setFixedHeight(110)
        details.setVisible(bool(versions))
        layout.addWidget(details)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        select_button = QPushButton(tr('Set as default version'))
        select_button.setObjectName('manifest-history-set-default')
        buttons.addButton(select_button, QDialogButtonBox.ButtonRole.ActionRole)
        for button in buttons.buttons():
            button.setAutoDefault(False)
        layout.addWidget(buttons)
        def selection_changed():
            item = choices.currentItem()
            version = item.data(Qt.ItemDataRole.UserRole) if item and not item.isHidden() else None
            select_button.setEnabled(bool(version and version['manifest_id'] != self.host.manager.default_manifest_id()))
            details.setPlainText(version['manifest_id'] + ('\n\n' + version['AdditionalMessage'].strip()
                                 if version['AdditionalMessage'].strip() else '') if version else '')
        choices.currentItemChanged.connect(selection_changed)

        def filter_versions(query):
            pattern = delegate.set_query(query)
            first_visible = -1
            for row in range(choices.count()):
                item = choices.item(row)
                matches = not pattern or pattern.search(item.text()) or pattern.search(item.data(NOTES_ROLE))
                item.setHidden(not matches)
                if matches and first_visible < 0:
                    first_visible = row
            selected = choices.currentItem()
            if not selected or selected.isHidden():
                choices.setCurrentRow(first_visible)
            choices.setVisible(first_visible >= 0)
            empty.setVisible(first_visible < 0)
            selection_changed()

        empty.setText(tr('No matching Manifests') if versions else tr('No available workflows detected'))
        search.setEnabled(bool(versions))
        search.textChanged.connect(filter_versions)
        search.returnPressed.connect(lambda: choices.setFocus() if choices.currentItem() else None)
        filter_versions('')
        search.setFocus()

        def select():
            if (remote := getattr(self.service, "_remote_mcp", None)) is not None:
                remote.check_local("Default")
            item = choices.currentItem()
            if item is None or item.isHidden():
                return
            result = self.host.manager.set_default(item.data(Qt.ItemDataRole.UserRole)['manifest_id'])
            if not result.ok:
                raise ValueError("; ".join(error.message for error in result.errors))
            self.render_state(self.service.status)
            dialog.accept()
        select_button.clicked.connect(lambda: self._interact(select))
        buttons.rejected.connect(dialog.reject)
        dialog.exec()

    def open_sharing(self, exporting):
        from .sharing_gui import open_sharing
        open_sharing(self, exporting=exporting)

    def imported_page_settings(self, identities):
        """隔离导入前的页面实例，重载时不再提交其旧值。"""
        from .user_pages import UserSettings
        self.page_store.value = UserSettings(self.service.data_root).value
        for page in self.business_pages:
            if page.page_id in identities:
                page.context.requires_reload = True
        self.render_state(self.service.status)

    def submit_pages(self):
        """运行与重载前强制提交所有已加载页面，错误保留页面身份。"""
        for page in self.business_pages:
            if page.context.requires_reload:
                continue
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
            for task in page.tasks:
                if task["id"] not in self.current_supported:
                    continue
                saved = self.page_store.value["tasks"].get(task["id"], {"enabled": False, "count": 1})
                row = QWidget()
                layout = FlowLayout(row)
                layout.setContentsMargins(9, 9, 9, 9)
                enabled = QCheckBox(task.get("names", {}).get(page.context.language, task["name"]))
                enabled.setToolTip(enabled.text())
                count = TaskCountSpinBox() if task["show_task_count"] else None
                enabled.setChecked(saved["enabled"])
                if count is not None:
                    count.setValue(saved["count"])
                jump = QPushButton(tr('Settings'))
                jump.clicked.connect(lambda _, widget=page.widget: self.switchTo(widget))
                layout.addWidget(enabled)
                controls = QWidget()
                controls_layout = QHBoxLayout(controls)
                controls_layout.setContentsMargins(0, 0, 0, 0)
                if count is not None:
                    controls_layout.addWidget(count)
                controls_layout.addWidget(jump)
                layout.addWidget(controls)
                self.task_rows[task["id"]] = (enabled, count)
                enabled.toggled.connect(lambda _, identity=task["id"]: self._interact(lambda: self.save_task(identity)))
                if count is not None:
                    count.valueChanged.connect(lambda _, identity=task["id"]: self._interact(lambda: self.save_task(identity)))
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
        saved = self.page_store.value["tasks"].get(identity, {"count": 1})
        self.page_store.save_task(identity, enabled.isChecked(), count.value() if count is not None else saved["count"])

    def save_user_enabled(self):
        from .agent_settings import settings_document, save_selection
        provider = settings_document(self.service.data_root)["user_provider"]
        save_selection(self.service.data_root, "user", provider, enabled=self.user_enabled.isChecked())
        self.coordinator.refresh_agent()

    def start_plan(self):
        """提交配置后固定 Manifest 和调度输入，不回读运行中的 GUI。"""
        from .user_pages import task_inputs
        if any(page.context.requires_reload for page in self.business_pages):
            raise ValueError(tr("Page settings were imported. Reload the application before running."))
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
        self.service.start_plan(manifest_id=self.current_manifest_id, task_repetitions=repetitions, settings=settings,
                                use_saved_config=False)
        self.owns_run = True
        self.render_state(self.service.status)

    @Slot(dict)
    def render_state(self, state):
        if not hasattr(self, "start_button"):
            return
        busy = state["phase"] == "running" or bool(state.get("activity")) or bool(state.get("remote_control")) or self.closing
        if hasattr(self, "data_maintenance"):
            self.data_maintenance.render_actions(busy or bool(self.jobs))
        for button in getattr(self, "sharing_buttons", []):
            button.setEnabled(not busy and not self.jobs)
        if self.current_manifest_id != state["default_manifest_id"] or not hasattr(self, "_tasks_initialized"):
            self._tasks_initialized = True
            self.refresh_tasks()
        if hasattr(self, "settings_page"):
            self.settings_page.render(busy)
        if hasattr(self, "reload_button"):
            self.reload_button.setEnabled(not busy and not self.jobs and not self.coordinator.reloading)
        identity = state["default_manifest_id"]
        if getattr(self, "_rendered_manifest_id", None) != identity or not hasattr(self, "latest_manifest_id"):
            self._rendered_manifest_id = identity
            self.refresh_manifest_card()
        settings_reload = any(page.context.requires_reload for page in self.business_pages)
        ready = getattr(self, "_agent_ready", True) and not settings_reload
        self.start_hint.setText(tr("Page settings were imported. Reload the application before running.") if settings_reload else
                                "" if ready else tr('Complete the Agent settings or turn off User Agent'))
        self.start_hint.setVisible(not ready)
        self.start_button.setEnabled(not busy and ready)
        controlled = bool(state.get("remote_control"))
        self.latest_button.setEnabled(not controlled)
        self.user_enabled.setEnabled(not controlled)
        for enabled, count in self.task_rows.values():
            enabled.setEnabled(not controlled)
            if count is not None:
                count.setEnabled(not controlled)
        for page in self.business_pages:
            page.widget.setEnabled(not controlled and not page.context.requires_reload)
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
                self.notifications.notify_result(result)
                update = state.get("default_update")
                if update:
                    self.notifications.notify(tr('Repaired version is now the default') if update["status"] == "changed"
                                              else tr('Could not automatically use the repaired version'),
                                              update["manifest_id"])

    def show_runtime_feedback(self, request):
        """在 GUI 线程展示父 Run 的人工请求，取消按钮停止该 Run。"""
        if request.done.is_set() or self.closing or self.service.status["phase"] != "running":
            request.close()
            return
        from .developer_gui import FeedbackDialog
        dialog = FeedbackDialog(request, self)
        dialog.cancel.clicked.disconnect()
        dialog.cancel.clicked.connect(lambda: (self.service.stop(), request.close(), dialog.close()))
        self.runtime_feedback_dialog = dialog
        dialog.show()


class GuiCoordinator:
    """应用持有唯一服务和宿主；窗口可独立关闭或重新打开。"""

    def __init__(self, service, lifecycle, *, initialize_user_window=False):
        from .i18n import install_translations, load_language, resolve_language
        app = QApplication.instance()
        apply_appearance(app, load_application_settings(service.data_root).get("appearance", DEFAULT_APPEARANCE))
        icon_path = (Path(__file__).with_name("MagicAndWonder.ico") if getattr(sys, "frozen", False)
                     else Path(__file__).resolve().parents[2] / "MagicAndWonder.ico")
        app.setWindowIcon(QIcon(str(icon_path)))
        if not hasattr(app, "_lalc_language"):
            install_translations(app, resolve_language(load_language(service.data_root)))
        from .developer import DeveloperHost
        self.service, self.lifecycle = service, lifecycle
        self.host = DeveloperHost(service, default_candidate_root(service.data_root))
        self.user = None
        self.developer = None
        self.initialize_user_window = initialize_user_window
        self.resource_prompted = False
        self.reloading = False
        self.bridge = StateBridge(service, self.render_state)
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
            if not developer and self.initialize_user_window:
                QTimer.singleShot(0, window, window.check_framework_releases)
                if not self.resource_prompted:
                    self.resource_prompted = True
                    QTimer.singleShot(0, window, lambda: window._interact(window.prompt_default_resources))
        self.refresh_agent()
        window.render_state(self.service.ui_snapshot())
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
        self.user.settings_page.setEnabled(not owned)
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
        self.user._agent_ready = not document["user_enabled"] or complete
        self.user.render_state(self.service.status)

    def request_reload(self, restart=None):
        """先保存并封闭所有入口，最终清理成功后才允许启动新进程。"""
        def check_idle():
            state = self.service.status
            if (self.reloading or state["phase"] == "running" or state.get("activity") or state.get("remote_control") or
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
        self.lifecycle.restart = lambda: (restart or self.restart_process)(windows)
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
            self.service.remote_mcp.on_feedback = None
            self.service.remote_mcp.on_page_preview = None
            self.developer = None
            if self.user is not None:
                self.user.settings_page.reload()
                self.refresh_agent()
        window.deleteLater()
        if self.user is None and self.developer is None:
            QApplication.instance().exit(0)

    def shutdown(self):
        self.bridge.close()
        for window in (self.user, self.developer):
            if window is not None:
                window.shutdown()
                if self.reloading:
                    window.close()
        self.service.shutdown()


def run_gui(lifecycle: ApplicationLifecycle | None = None, *, developer=False, restore=(), ready=None) -> int:
    """归并重复 GUI 入口，在唯一事件循环内持有双窗口。"""
    from .sharing import cleanup_staging
    cleanup_staging()
    if lifecycle is None:
        return run_application(lambda owner: run_gui(owner, developer=developer, restore=restore, ready=ready))
    from .gui_instance import GuiInstance
    app = QApplication.instance() or QApplication(sys.argv)
    instance = GuiInstance()
    if instance.forward(developer):
        return 0
    service = ApplicationService(default_data_root())
    coordinator = GuiCoordinator(service, lifecycle, initialize_user_window=True)
    bridge = coordinator.bridge
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
    bridge.fatal.connect(lambda details: (coordinator.user or coordinator.developer).fatal_error(details)
                         if coordinator.user or coordinator.developer else lifecycle.present_fatal(details))
    lifecycle.dispatch_fatal = bridge.fatal.emit
    def shutdown():
        try:
            coordinator.shutdown()
            result = service.status.get("result") or {}
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
        if ready is not None:
            QTimer.singleShot(0, ready)
        for name in restore or (("developer" if developer else "user"),):
            coordinator.open_window(name == "developer")
        return app.exec()
    finally:
        interrupt_timer.stop()
        interrupt_timer.deleteLater()
