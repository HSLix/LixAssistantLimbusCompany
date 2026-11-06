"""同进程页面双实例审查；仅人工批准快照可写正式目录。"""

from contextlib import ExitStack
import threading

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QHBoxLayout, QScrollArea, QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, PushButton, PrimaryPushButton, PlainTextEdit, SegmentedWidget, TitleLabel

from .i18n import tr
from .page_drafts import MemorySettings
from .file_content import content_bytes
from .page_packages import materialized_page, snapshot_page
from .user_pages import UserSettings, create_business_page, load_page_module


class PreviewRequest:
    """绑定 Session / 轮次与源码快照；取消和批准只能有一个生效。"""

    def __init__(self, drafts, snapshot, summary, identity, *, data_root=None, review_only=False):
        self.drafts, self.snapshot, self.summary, self.identity = drafts, snapshot, summary, identity
        self.data_root = data_root if data_root is not None else drafts.session.host.service.data_root
        self.review_only = review_only
        self.done = threading.Event()
        self.lock = threading.Lock()
        self.result = None

    def finish(self, result=None, *, action=None):
        with self.lock:
            if self.done.is_set():
                return False
            self.result = action() if action is not None else result
            self.done.set()
            return True

    def close(self):
        self.finish()


class PageInstalledDialog(QDialog):
    """安装完成单独提示；主动重启先等待当前操作取消和清理。"""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowTitle(tr('Page installed'))
        layout = QVBoxLayout(self)
        self.message = BodyLabel(tr('Page installation is complete. Restart LALC to apply the changes.'))
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        controls = QHBoxLayout()
        self.cancel = PushButton(tr('Cancel'))
        self.cancel.clicked.connect(self.reject)
        self.restart = PrimaryPushButton(tr('Restart now'))
        self.restart.clicked.connect(self.restart_now)
        controls.addWidget(self.cancel)
        controls.addWidget(self.restart)
        layout.addLayout(controls)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.wait_for_restart)
        self.finished.connect(lambda: self.timer.stop())

    def restart_now(self):
        """不绕过重载门控；先请求结束活动，再由定时器等待清理。"""
        coordinator = self.window.coordinator
        self.windows = tuple(window for window in (coordinator.user, coordinator.developer) if window)
        self.restart.setEnabled(False)
        self.message.setText(tr('Finishing current operations before restarting LALC…'))
        for window in self.windows:
            window.cancel_operation()
        self.window.service.stop()
        self.timer.start(50)

    def wait_for_restart(self):
        service = self.window.service
        if (any(window.closing for window in self.windows) or self.window.coordinator.reloading):
            self.reject()
            return
        if (any(window.jobs for window in self.windows) or service.state.get('activity')
                or service.state['phase'] == 'running'
                or service._thread is not None and service._thread.is_alive()):
            return
        self.timer.stop()
        self.window._interact(self.window.coordinator.request_reload)
        self.accept()


class PagePreviewDialog(QDialog):
    """加载成功后才显示三 Tab 审批；配置只在内存，批准绑定固定快照。"""

    def __init__(self, request, window):
        super().__init__(window)
        self.request, self.window = request, window
        self.errors = {}
        self.current = self.proposed = None
        self.current_hash = None
        self.packages = ExitStack()
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowTitle(tr('Review settings page'))
        self.resize(1000, 720)
        layout = QVBoxLayout(self)
        layout.addWidget(TitleLabel(tr('Review settings page')))
        filename = BodyLabel(request.snapshot['filename'])
        filename.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(filename)
        self.tabs = SegmentedWidget(self)
        self.stack = QStackedWidget(self)
        layout.addWidget(self.tabs)
        layout.addWidget(self.stack, 1)
        self.current_column = self.tab('current', tr('Current'))
        self.proposed_column = self.tab('proposed', tr('Proposed'))
        review = self.tab('review', tr('Review'))
        self.review_summary = PlainTextEdit()
        self.review_summary.setReadOnly(True)
        self.review_summary.setPlainText(request.summary)
        review.addWidget(self.review_summary, 1)
        self.review_details = PlainTextEdit()
        self.review_details.setReadOnly(True)
        self.review_details.setMaximumHeight(240)
        review.addWidget(self.review_details)
        self.tabs.currentItemChanged.connect(lambda key: self.stack.setCurrentIndex(('current', 'proposed', 'review').index(key)))
        self.tabs.setCurrentItem('proposed')
        self.notice = BodyLabel(tr('Review the proposed page. Use Current and Review for comparison and details.'))
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        self.status = BodyLabel(tr('Trial configuration is discarded. Installation keeps existing settings; reload the application afterwards.'))
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        controls = QHBoxLayout()
        self.install_button = PrimaryPushButton(tr('Install this version'))
        if request.review_only:
            self.install_button.setText(tr('Approve this version'))
        self.install_button.setEnabled(False)
        self.install_button.clicked.connect(self.install)
        self.close_button = PushButton(tr('Close without installing'))
        if request.review_only:
            self.close_button.setText(tr('Close without approving'))
        self.close_button.clicked.connect(self.reject)
        self.cancel = PushButton(tr('Cancel round'))
        self.cancel.clicked.connect(self.reject if request.review_only else self.cancel_round)
        if request.review_only:
            self.cancel.setText(tr('Cancel'))
            self.status.setText(tr('Approval records this package version. Import Selected installs it later.'))
        for button in (self.install_button, self.close_button, self.cancel):
            controls.addWidget(button)
        layout.addLayout(controls)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.expire)
        # 只加载一次，成功实例直接交给审批；失败窗口从不显示。
        self.ready = self.load_pages()
        if self.ready and not request.done.is_set():
            self.timer.start(50)
            QApplication.instance().installEventFilter(self)
        else:
            self.ready = False
            self.packages.close()
            self.deleteLater()

    def tab(self, key, title):
        self.tabs.addItem(key, title)
        container = QWidget()
        column = QVBoxLayout(container)
        column.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        self.stack.addWidget(scroll)
        return column

    def show_error(self, column, side, error):
        message = self.clean_error(error)
        self.errors[side] = message
        text = PlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText(message)
        column.addWidget(text)

    def clean_error(self, error):
        if self.request.review_only:
            return self.window.clean_details(f"{type(error).__name__}: {error}")
        from .agent_diagnostics import redact
        host = self.request.drafts.session.host
        keys = {value for value in host.secrets.values() if value}
        if host.conversation:
            keys.update(host.conversation.log.keys)
        return redact(f"{type(error).__name__}: {error}", keys)

    def fail_preview(self, side, error):
        """失败直接结算到同轮工具，不显示审批或要求人手关闭。"""
        message = self.clean_error(error)
        self.errors[side] = message
        snapshot = self.request.snapshot
        self.request.finish({'status': 'preview_failed', 'filename': snapshot['filename'],
                             'sha256': snapshot['sha256'], 'error': message,
                             'stage': 'page_preview:' + side, 'errors': dict(self.errors)})
        return False

    def load_pages(self):
        """Qt 主线程先准备拟安装页，再加载旧侧；不调用 submit 或重复创建。"""
        if self.request.done.is_set():
            return False
        request, drafts = self.request, self.request.drafts
        snapshot = request.snapshot
        try:
            value = UserSettings(request.data_root).value
        except Exception as error:
            return self.fail_preview('settings', error)
        try:
            path = self.packages.enter_context(materialized_page(snapshot['package']))
            self.proposed = create_business_page(path, *load_page_module(path, snapshot['source']), MemorySettings(value))
            self.proposed_column.addWidget(self.proposed.widget)
            drafts.check_registration(snapshot, self.proposed.page_id, self.proposed.task_id)
        except Exception as error:
            return self.fail_preview('proposed', error)
        if request.done.is_set():
            return False
        try:
            current = drafts.package_path(snapshot['filename'], 'installed')
            if current.exists():
                package = snapshot_page(current, freeze=False)
                path = self.packages.enter_context(materialized_page(package))
                self.current_hash = package.sha256
                self.current = create_business_page(path, *load_page_module(path, content_bytes(package.files['page.py'])), MemorySettings(value))
                self.current_column.addWidget(self.current.widget)
            else:
                self.current_column.addWidget(BodyLabel(tr('New page; no installed page exists.')))
        except Exception as error:
            self.show_error(self.current_column, 'current', error)
        current_id = self.current.page_id if self.current else '—'
        current_task = self.current.task_id if self.current and self.current.task_id else '—'
        self.review_details.setPlainText('\n'.join([
            tr('File: {0}').format(snapshot['filename']),
            tr('Session: {0}').format(request.identity[0]),
            tr('Proposed page ID: {0}').format(self.proposed.page_id),
            tr('Proposed task ID: {0}').format(self.proposed.task_id or '—'),
            tr('Proposed SHA-256: {0}').format(snapshot['sha256']),
            tr('Current page ID: {0}').format(current_id),
            tr('Current task ID: {0}').format(current_task),
            tr('Current SHA-256: {0}').format(self.current_hash or '—'),
            tr('Page loading was checked. Configuration and Plan compatibility are reviewed by the Agent.'),
        ]))
        self.install_button.setEnabled(True)
        return not request.done.is_set()

    def eventFilter(self, watched, event):
        blocked_event = event.type() in {QEvent.Type.WindowBlocked,
                                        QEvent.Type.MouseButtonPress, QEvent.Type.NonClientAreaMouseButtonPress}
        if (blocked_event and isinstance(watched, QWidget) and watched is not self
                and not self.isAncestorOf(watched) and self.isVisible()
                and (event.type() != QEvent.Type.WindowBlocked or watched.isWindow())):
            self.notice.setText(tr('Finish or close the page review before using other LALC windows.'))
            QTimer.singleShot(0, self.emphasize)
            if event.type() in {QEvent.Type.MouseButtonPress, QEvent.Type.NonClientAreaMouseButtonPress}:
                return True
        return super().eventFilter(watched, event)

    def emphasize(self):
        if not self.request.done.is_set() and self.isVisible():
            self.raise_()
            self.activateWindow()
            QApplication.alert(self)

    def install(self):
        """批准和提交在同一次结算内完成；失败保留窗口及原正式页。"""
        if self.proposed is None or not self.install_button.isEnabled() or self.request.done.is_set():
            return
        if any(job.cancel_requested for job in self.window.jobs) or self.window.closing:
            self.request.close()
            self.close()
            return
        try:
            if self.request.review_only:
                self.request.finish({"status": "reviewed", "sha256": self.request.snapshot["sha256"],
                    "page_id": self.proposed.page_id, "task_id": self.proposed.task_id})
            else:
                self.request.finish(action=lambda: {
                    **self.request.drafts.install(self.request.snapshot, self.proposed.page_id, self.proposed.task_id),
                    "errors": dict(self.errors)})
        except Exception as error:
            message = self.clean_error(error)
            self.errors["install"] = message
            self.status.setText(message)
            return
        self.close()

    def reject(self):
        self.finish_closed()
        super().reject()

    def finish_closed(self):
        self.request.finish({"status": "not_installed", "filename": self.request.snapshot["filename"],
                             "sha256": self.request.snapshot["sha256"], "errors": dict(self.errors)})
        QApplication.instance().removeEventFilter(self)
        self.timer.stop()
        self.packages.close()

    def closeEvent(self, event):
        self.finish_closed()
        super().closeEvent(event)

    def cancel_round(self):
        if not self.request.done.is_set():
            self.window.cancel_operation()
            self.request.close()
        self.close()

    def expire(self):
        if self.request.done.is_set():
            self.close()
