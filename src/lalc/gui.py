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
    QTabWidget, QComboBox, QFileDialog, QMessageBox,
)

from .application import ApplicationService, StartError, default_data_root
from .runtime import _exception_fields
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

    def __init__(self, service: ApplicationService, lifecycle: ApplicationLifecycle | None = None) -> None:
        super().__init__()
        self.service = service
        self.lifecycle = lifecycle or ApplicationLifecycle()
        self._pause_notice_shown = False
        self._reported_run = None
        self._fatal_reported = False
        from .developer import DeveloperHost
        from .developer_gui import CapturePage, SettingsPage, RepairPage
        self.host = DeveloperHost(service, Path.cwd() / "candidate")
        self.jobs = []
        self.closing = False
        self.close_timer = QTimer(self)
        self.close_timer.setInterval(100)
        self.close_timer.timeout.connect(self._finish_close)
        self.setWindowTitle("LALC")
        self.resize(820, 620)
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
                self.runner_selection_error = "已恢复 Runner 选择，请刷新 Manifest 与入口以核验可用性。"
        except Exception as error:
            self.runner_selection_error = str(error)
        for item in self.host.manager.list_manifests():
            if self.runner_manifest.findData(item["manifest_id"]) < 0:
                self.runner_manifest.addItem(item["manifest_id"], item["manifest_id"])
        self.runner_manifest.currentIndexChanged.connect(self._runner_selected)
        layout.addWidget(self.runner_manifest)
        self.runner_notice = QLabel()
        self.runner_notice.setWordWrap(True)
        layout.addWidget(self.runner_notice)
        self.refresh_manifest_button = QPushButton("刷新 Manifest 与入口")
        self.refresh_manifest_button.clicked.connect(self._refresh_runner)
        layout.addWidget(self.refresh_manifest_button)
        self.runner_role = QComboBox()
        for label, role in (("Task Workflow", "task_workflow"), ("Subworkflow", "subworkflow"), ("Step", "step"), ("Automation Plan", "automation_plan")):
            self.runner_role.addItem(label, role)
        self.runner_role.currentIndexChanged.connect(self._filter_entries)
        layout.addWidget(self.runner_role)
        self.runner_entries = QComboBox()
        self.runner_entries.currentTextChanged.connect(lambda text: self.entry.setText(text) if hasattr(self, "entry") else None)
        layout.addWidget(self.runner_entries)
        self._entries = []
        self.entry = QLineEdit()
        self.entry.setPlaceholderText("逻辑名，例如 tasks.claim_mail")
        layout.addWidget(self.entry)
        self.inputs = QPlainTextEdit("{}")
        self.inputs.setPlaceholderText("JSON 输入")
        layout.addWidget(self.inputs)
        controls = QHBoxLayout()
        self.start_button = QPushButton("开始")
        self.pause_button = QPushButton("暂停")
        self.stop_button = QPushButton("停止")
        self.start_button.clicked.connect(self._start_background)
        self.pause_button.clicked.connect(self._toggle_pause)
        self.stop_button.clicked.connect(lambda: self._interact(self.service.stop))
        for button in (self.start_button, self.pause_button, self.stop_button):
            controls.addWidget(button)
        layout.addLayout(controls)
        self.plan_path = QLineEdit()
        self.plan_path.setPlaceholderText("Automation Plan 配置文件路径")
        layout.addWidget(self.plan_path)
        choose_plan = QPushButton("选择现有 Plan 文件")
        choose_plan.clicked.connect(self._choose_plan)
        layout.addWidget(choose_plan)
        self.ledger_button = QPushButton("查看 Ledger")
        self.ledger_button.clicked.connect(lambda: self.launch(self.service.ledger_records, lambda value: self.trace.setPlainText(json.dumps(value, ensure_ascii=False, indent=2))))
        layout.addWidget(self.ledger_button)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.pause_notice = QLabel()
        self.pause_notice.setWordWrap(True)
        layout.addWidget(self.pause_notice)
        self.trace = QPlainTextEdit()
        self.trace.setReadOnly(True)
        layout.addWidget(self.trace)
        self.tabs = QTabWidget()
        self.capture_page = CapturePage(self)
        self.settings_page = SettingsPage(self)
        self.repair_page = RepairPage(self)
        self.operation_event.connect(self.repair_page.show_event)
        for page, name in ((self.capture_page, "Capture"), (root, "Runner"), (self.settings_page, "Agent Settings"), (self.repair_page, "Agent Repair")):
            self.tabs.addTab(page, name)
        self.repair_page.set_manifests(self.host.manager.list_manifests())
        self.runner_notice.setText(self.runner_selection_error or "刷新 Manifest 与入口后可按角色选择；也可直接填写逻辑名。")
        self.setCentralWidget(self.tabs)
        self.resize(1050, 900)
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

    def _choose_plan(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 Plan", "", "JSON (*.json)")
        if path:
            self.plan_path.setText(path)

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

    def _refresh_runner(self):
        identity = self.runner_manifest.currentData()
        def operation():
            manifests = self.host.manager.list_manifests()
            try:
                loaded = self.service._loaded_manifest(identity)
                return manifests, [(name, component.role) for name, component in loaded.components.items()], None
            except Exception as error:
                return manifests, [], str(error)
        def done(values):
            manifests, self._entries, error = values
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
            self.runner_notice.setText(error or "所选 Manifest 仅用于后续执行；不改变 Default 或 Candidate。")
            self.repair_page.set_manifests(manifests)
            self._filter_entries()
            self.render_state(self.service.state)
        self.launch(operation, done)

    def _filter_entries(self):
        role = self.runner_role.currentData()
        self.runner_entries.clear()
        self.runner_entries.addItems([name for name, item_role in self._entries if item_role == role])
        self.inputs.setEnabled(role != "automation_plan")
        self.entry.setEnabled(role != "automation_plan")

    def closeEvent(self, event):
        """退出等待取消、输入释放、日志和子进程清理，期间保持事件循环。"""
        active = bool(self.jobs) or self.service.state["phase"] == "running"
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

    def _finish_close(self):
        if not self.jobs and (self.service._thread is None or not self.service._thread.is_alive()):
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
            self.service.logger.exception("Interaction failed")
            details = _exception_fields(error)["traceback"]
            if isinstance(error, StartError):
                details += "".join(item.get("traceback", "") for item in error.errors[1:])
            ErrorDialog(str(error), details, parent=self).open()

    def _start(self) -> None:
        self._interact(self._start_run)

    def _start_run(self) -> None:
        return self._start_request()()

    def _start_background(self):
        self._interact(lambda: self.launch(self._start_request()))

    def _start_request(self):
        """主线程读取控件；后台操作只携带冻结参数，不访问 Qt 控件。"""
        if self.runner_selection_error:
            raise ValueError(self.runner_selection_error + "；请重新选择或清除 Runner Manifest。")
        identity = self.runner_manifest.currentData()
        if self.runner_role.currentData() == "automation_plan":
            path = Path(self.plan_path.text())
            return lambda: self.service.start_plan(path, manifest_id=identity)
        inputs = json.loads(self.inputs.toPlainText().strip() or "{}")
        if type(inputs) is not dict:
            raise ValueError("输入必须是 JSON 对象。")
        name = self.entry.text().strip()
        return lambda: self.service.start(name, inputs, manifest_id=identity)

    def _toggle_pause(self) -> None:
        def toggle() -> None:
            if self.service.state["paused"]:
                self.service.resume()
            else:
                self.service.pause()
        self._interact(toggle)

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
        info = state.get("pause_info")
        if info:
            instruction = "恢复时将检查当前 Step 的 condition。" if info["has_condition"] else \
                "没有 condition，恢复后将从头执行当前 Step。"
            if not info.get("restart_step", True):
                instruction = "恢复后继续 Workflow 的观察与调度。"
            self.pause_notice.setText(f"自动化已暂停：{info['reason']}\n{info['description']}\n{instruction}")
            if not self._pause_notice_shown:
                self._pause_notice_shown = True
                self.showNormal()
                self.raise_()
                self.activateWindow()
        else:
            self._pause_notice_shown = False
            self.pause_notice.clear()
        self.status.setText(
            f"状态：{state['phase']}  |  暂停：{state['paused']}  |  "
            f"Default Manifest：{state['default_manifest_id']}  |  "
            f"Base Manifest：{state['base_manifest_id']}  |  "
            f"Working Manifest：{state['working_manifest_id']}  |  Run ID：{state['run_id']}"
        )
        result = state.get("result") or {}
        diagnostic = (info or {}).get("traceback", "") or result.get("traceback", "")
        if not diagnostic and result.get("reason") == "input_release_failed":
            diagnostic = next((item.get("traceback", "") for item in result.get("items", [])
                               if item.get("failure_code") == "input_release_failed"), "")
        self.trace.setPlainText(diagnostic + "\n" + "\n".join(
            json.dumps(item, ensure_ascii=False) for item in state["trace"]
        ))
        if state["phase"] == "finished" and self._reported_run != state["run_id"]:
            self._reported_run = state["run_id"]
            if result.get("fatal"):
                self.fatal_error(result_diagnostics(result))
            elif (result.get("status") in {"failure", "interrupted"}
                  and result.get("failure_code", result.get("reason")) != "user_cancelled") or any(
                      item.get("result") == "failure" and item.get("failure_code") != "user_cancelled"
                      for item in result.get("items", [])):
                details = result_diagnostics(result)
                self.service.logger.error("Execution failed: %s", details)
                ErrorDialog("执行失败，原始错误信息如下。", details, parent=self).open()
        self.pause_button.setText("继续" if state["paused"] else "暂停")
        busy = state["phase"] == "running" or bool(state.get("activity")) or bool(self.jobs) or self.closing
        self.start_button.setEnabled(not busy and not self.runner_selection_error)
        self.start_button.setToolTip("当前活动尚未结束" if busy else self.runner_selection_error or "")
        self.runner_manifest.setEnabled(not busy)
        self.refresh_manifest_button.setEnabled(not busy)
        for page in (self.capture_page, self.settings_page, self.repair_page):
            page.render(busy)
        self.pause_button.setEnabled(state["phase"] == "running" and not state.get("resume_pending", False))
        self.stop_button.setEnabled(state["phase"] == "running")


def run_gui(lifecycle: ApplicationLifecycle | None = None) -> int:
    """建立 GUI；进程启动与最终报告由同一生命周期入口负责。"""

    if lifecycle is None:
        return run_application(lambda owner: run_gui(owner))
    app = QApplication.instance() or QApplication(sys.argv)
    bridge = StateBridge()
    service = ApplicationService(default_data_root(), on_change=bridge.changed.emit)
    window = None
    def shutdown() -> None:
        if window is None:
            service.shutdown()
        else:
            window.shutdown()
        result = service.state.get("result") or {}
        if result.get("fatal"):
            lifecycle.present_fatal(result_diagnostics(result))
    lifecycle.shutdown = shutdown
    window = MainWindow(service, lifecycle)
    bridge.changed.connect(window.render_state)
    bridge.fatal.connect(window.fatal_error)
    lifecycle.dispatch_fatal = bridge.fatal.emit
    window.show()
    return app.exec()
