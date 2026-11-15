"""Developer GUI 的远程 MCP 管理页；审批复用现有本地对话框。"""

import json

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QMessageBox, QApplication
from qfluentwidgets import BodyLabel, SubtitleLabel, PushButton, LineEdit, SpinBox, ComboBox, PlainTextEdit

from .i18n import tr


class RemoteMcpPage(QWidget):
    """集中服务、本地授权和单个持久工作台，不提供聊天界面。"""

    feedback_requested = Signal(object)
    page_preview_requested = Signal(object)

    def __init__(self, window):
        super().__init__()
        self.host_window = window
        self.remote = window.service.remote_mcp
        self.remote.on_feedback = self.feedback_requested.emit
        self.remote.on_page_preview = self.page_preview_requested.emit
        self.feedback_requested.connect(self.show_feedback)
        self.page_preview_requested.connect(self.show_page_preview)
        self.dialogs = []
        self.signature = None
        self.publish_revision = None
        layout = QVBoxLayout(self)
        layout.addWidget(SubtitleLabel(tr("Remote MCP")))
        hint = BodyLabel(tr("Mac Codex → Tailscale HTTPS → Windows LALC. Conversations stay in Codex."))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.state = BodyLabel()
        self.state.setWordWrap(True)
        self.state.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.state)
        row = QHBoxLayout()
        self.toggle = PushButton(tr("Start MCP service"))
        self.toggle.clicked.connect(lambda: window.launch(self.remote.close if self.remote.enabled else self.start))
        self.allow = PushButton(tr("Allow remote control"))
        self.allow.clicked.connect(lambda: window._interact(self.authorize))
        self.revoke = PushButton(tr("Revoke remote control"))
        self.revoke.clicked.connect(lambda: window._interact(self.remote.revoke))
        for button in (self.toggle, self.allow, self.revoke):
            row.addWidget(button)
        row.addStretch()
        layout.addLayout(row)
        layout.addWidget(SubtitleLabel(tr("Connection")))
        form = QFormLayout()
        self.port = SpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(self.remote.config["port"])
        self.url = LineEdit()
        self.url.setText(self.remote.config["url"])
        self.url.setPlaceholderText("https://windows.example.ts.net/mcp")
        form.addRow(tr("Local port"), self.port)
        form.addRow(tr("Tailscale HTTPS address"), self.url)
        layout.addLayout(form)
        row = QHBoxLayout()
        self.save = PushButton(tr("Save connection"))
        self.save.clicked.connect(lambda: window._interact(lambda: self.remote.configure(self.port.value(), self.url.text().strip())))
        self.token = PushButton(tr("Generate / reset connection token"))
        self.token.clicked.connect(lambda: window._interact(self.reset_token))
        self.copy = PushButton(tr("Copy Codex configuration"))
        self.copy.clicked.connect(lambda: window._interact(self.copy_configuration))
        for button in (self.save, self.token, self.copy):
            row.addWidget(button)
        row.addStretch()
        layout.addLayout(row)
        note = BodyLabel(tr("Configure Tailscale Serve once to forward HTTPS to http://127.0.0.1:<port>. The token is shown only when generated."))
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addWidget(SubtitleLabel(tr("Persistent MCP workbench")))
        self.workspace = BodyLabel()
        self.workspace.setWordWrap(True)
        self.workspace.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.workspace)
        row = QHBoxLayout()
        self.source = ComboBox()
        self.initialize = PushButton(tr("Initialize / replace Candidate"))
        self.initialize.clicked.connect(lambda: window._interact(self.initialize_workspace))
        row.addWidget(self.source, 1)
        row.addWidget(self.initialize)
        layout.addLayout(row)
        row = QHBoxLayout()
        self.pause = PushButton(tr("Pause"))
        self.pause.clicked.connect(lambda: window._interact(self.pause_run))
        self.stop = PushButton(tr("Stop"))
        self.stop.clicked.connect(lambda: window._interact(self.remote.cancel_active))
        row.addWidget(self.pause)
        row.addWidget(self.stop)
        row.addStretch()
        layout.addLayout(row)
        layout.addWidget(SubtitleLabel(tr("Recent remote operations")))
        self.records = PlainTextEdit()
        self.records.setReadOnly(True)
        layout.addWidget(self.records, 1)
        self.refresh_sources()
        self.refresh_state(window.service.status)

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_sources()

    def start(self):
        self.remote.configure(self.port.value(), self.url.text().strip())
        self.remote.open()

    def authorize(self):
        message = tr("Remote code can publish and execute Python with this Windows user's permissions. Validation is not a sandbox. Allow remote development until revoked or LALC exits?")
        if QMessageBox.question(self, tr("Allow remote control"), message) == QMessageBox.StandardButton.Yes:
            self.remote.allow()

    def reset_token(self):
        if QMessageBox.question(self, tr("Reset connection token"), tr("Invalidate the old token, revoke remote control and stop related operations?")) != QMessageBox.StandardButton.Yes:
            return
        token = self.remote.reset_token()
        # 凭据仅在显式本地对话框显示，不发送到运行日志或错误详情。
        from PySide6.QtWidgets import QDialog, QVBoxLayout
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("Connection token — shown once"))
        body = QVBoxLayout(dialog)
        field = LineEdit()
        field.setReadOnly(True)
        field.setText(token)
        body.addWidget(field)
        copy = PushButton(tr("Copy token"))
        copy.clicked.connect(lambda: QApplication.clipboard().setText(token))
        body.addWidget(copy)
        dialog.resize(620, 110)
        dialog.exec()
        field.clear()

    def copy_configuration(self):
        if not self.remote.config["url"]:
            raise ValueError(tr("Save the Tailscale HTTPS address first."))
        text = ('[mcp_servers.lalc]\nurl = ' + json.dumps(self.remote.config["url"]) +
                '\nbearer_token_env_var = "LALC_MCP_TOKEN"\n')
        QApplication.clipboard().setText(text)

    def initialize_workspace(self):
        exists = self.remote.path.exists()
        if exists and QMessageBox.question(self, tr("Replace MCP Candidate"),
                tr("Replace the unpublished Candidate and its baseline? Page drafts, published versions, Assets and operation history are retained.")) != QMessageBox.StandardButton.Yes:
            return
        identity = self.source.currentData()
        self.host_window.launch(lambda: self.remote.initialize(identity, replace=exists))

    def pause_run(self):
        service = self.host_window.service
        service.resume() if service.status["paused"] else service.pause()

    def _valid_request(self, request):
        if self.host_window.closing or not self.remote.authorized or self.remote.pending_request is not request or request.done.is_set():
            request.close()
            return False
        return True

    def show_feedback(self, request):
        if not self._valid_request(request):
            return
        from .developer_gui import FeedbackDialog
        dialog = FeedbackDialog(request, self.host_window)
        self.dialogs.append(dialog)
        dialog.finished.connect(lambda: self.dialogs.remove(dialog) if dialog in self.dialogs else None)
        dialog.show()

    def show_page_preview(self, request):
        if not self._valid_request(request):
            return
        from .page_preview import PagePreviewDialog, PageAvailabilityDialog, PageInstalledDialog
        dialog = (PageAvailabilityDialog if hasattr(request, "enabled") else PagePreviewDialog)(request, self.host_window)
        if not dialog.ready:
            request.close()
            dialog.deleteLater()
            return
        self.dialogs.append(dialog)
        def finished():
            if dialog in self.dialogs:
                self.dialogs.remove(dialog)
            if request.result and request.result.get("status") in {"installed", "availability_changed"}:
                self.host_window.page_installed_dialog = PageInstalledDialog(self.host_window)
                self.host_window.page_installed_dialog.show()
        dialog.finished.connect(finished)
        dialog.show()

    def refresh_state(self, state):
        snapshot = self.remote.snapshot()
        owner = snapshot["controller"]
        run_status = tr("Paused") if state["paused"] else tr("Running") if state["phase"] == "running" else tr("Stopped")
        self.state.setText(tr("Service: {0} · Authorized: {1} · Controller: {2}\nRun: {3} · Operation: {4}").format(
            tr("On") if snapshot["enabled"] else tr("Off"),
            tr("Yes") if snapshot["authorized"] else tr("No"),
            (owner["label"] + " · " + owner["id"]) if owner else tr("None"),
            (str(state["run_id"]) + " · " + run_status) if state["run_id"] else tr("None"), snapshot["operation_id"] or tr("None")))
        if snapshot["failure"]:
            self.state.setText(self.state.text() + "\n" + snapshot["failure"])
        metadata = snapshot["workspace"] or {}
        from .run_log_gui import log_time
        self.workspace.setText(tr("Source Manifest: {0}\nLast used: {1}").format(
            metadata.get("source_manifest_id", tr("Not initialized")),
            log_time(metadata["last_used_at"]) if metadata.get("last_used_at") else tr("Never used")))
        revision = next((row.get("operation_id") for row in reversed(snapshot["recent"])
                         if row.get("tool") == "validate_and_publish"), None)
        if revision != self.publish_revision:
            self.refresh_sources()
            self.publish_revision = revision
        busy = bool(self.host_window.jobs) or bool(state.get("activity")) or state["phase"] == "running"
        self.toggle.setText(tr("Stop MCP service") if snapshot["enabled"] else tr("Start MCP service"))
        self.toggle.setEnabled(not self.host_window.jobs and not snapshot["revoking"])
        self.allow.setEnabled(snapshot["enabled"] and not snapshot["authorized"] and not snapshot["revoking"])
        self.revoke.setEnabled(snapshot["authorized"] or bool(owner))
        for control in (self.port, self.url, self.save):
            control.setEnabled(not snapshot["enabled"] and not owner and not self.host_window.jobs)
        self.token.setEnabled(not self.host_window.jobs)
        self.source.setEnabled(not owner and not busy)
        self.initialize.setEnabled(not owner and not busy and self.source.count() > 1)
        self.pause.setText(tr("Resume") if state["paused"] else tr("Pause"))
        self.pause.setEnabled(bool(owner) and state["phase"] == "running")
        self.stop.setEnabled(bool(owner) and (state["phase"] == "running" or bool(snapshot["operation_id"])))
        self.records.setPlainText("\n".join(json.dumps(row, ensure_ascii=False) for row in snapshot["recent"][-10:]))

    def refresh_sources(self):
        """只在打开页面或实际发布后刷新，运行日志通知不扫描版本目录。"""
        values = self.remote.host.manager.list_manifests()
        signature = [(row["manifest_id"], row["saved_at"]) for row in values]
        if signature != self.signature:
            selected = self.source.currentData()
            self.source.clear()
            self.source.addItem(tr("Latest published Manifest"), userData=None)
            for value in values:
                self.source.addItem(value["manifest_id"], userData=value["manifest_id"])
            self.source.setCurrentIndex(max(0, self.source.findData(selected)))
            self.signature = signature
