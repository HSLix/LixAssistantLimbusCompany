"""同进程页面双实例审查；仅人工批准快照可写正式目录。"""

import hashlib
import threading

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QHBoxLayout, QScrollArea, QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, PushButton, PrimaryPushButton, PlainTextEdit, SegmentedWidget, TitleLabel

from .i18n import tr
from .page_drafts import MemorySettings
from .user_pages import UserSettings, create_business_page, load_page_module


class PreviewRequest:
    """绑定 Session / 轮次与源码快照；取消和批准只能有一个生效。"""

    def __init__(self, drafts, snapshot, summary, identity):
        self.drafts, self.snapshot, self.summary, self.identity = drafts, snapshot, summary, identity
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


class PagePreviewDialog(QDialog):
    """加载成功后才显示三 Tab 审批；配置只在内存，批准绑定固定快照。"""

    def __init__(self, request, window):
        super().__init__(window)
        self.request, self.window = request, window
        self.errors = {}
        self.current = self.proposed = None
        self.current_hash = None
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
        self.install_button.setEnabled(False)
        self.install_button.clicked.connect(self.install)
        self.close_button = PushButton(tr('Close without installing'))
        self.close_button.clicked.connect(self.reject)
        self.cancel = PushButton(tr('Cancel round'))
        self.cancel.clicked.connect(self.cancel_round)
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
            value = UserSettings(drafts.session.host.service.data_root).value
        except Exception as error:
            return self.fail_preview('settings', error)
        try:
            path = drafts.path(snapshot['filename'])
            self.proposed = create_business_page(path, *load_page_module(path, snapshot['source']), MemorySettings(value))
            self.proposed_column.addWidget(self.proposed.widget)
            drafts.check_registration(snapshot, self.proposed.page_id, self.proposed.task_id)
        except Exception as error:
            return self.fail_preview('proposed', error)
        if request.done.is_set():
            return False
        try:
            path = drafts.path(snapshot['filename'], 'installed')
            if path.exists():
                content = path.read_bytes()
                self.current_hash = hashlib.sha256(content).hexdigest()
                self.current = create_business_page(path, *load_page_module(path, content), MemorySettings(value))
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
            completed = self.request.finish(action=lambda: {
                **self.request.drafts.install(self.request.snapshot, self.proposed.page_id, self.proposed.task_id),
                "errors": dict(self.errors)})
        except Exception as error:
            message = self.clean_error(error)
            self.errors["install"] = message
            self.status.setText(message)
            return
        if completed:
            self.window.notifications.notify(tr('Page installed'), tr('Reload the application to use the installed page.'))
        self.close()

    def reject(self):
        self.finish_closed()
        super().reject()

    def finish_closed(self):
        self.request.finish({"status": "not_installed", "filename": self.request.snapshot["filename"],
                             "sha256": self.request.snapshot["sha256"], "errors": dict(self.errors)})
        QApplication.instance().removeEventFilter(self)
        self.timer.stop()

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
