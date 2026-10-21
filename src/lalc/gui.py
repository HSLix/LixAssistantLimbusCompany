from __future__ import annotations

import json
import sys

from PySide6.QtCore import QObject, Signal, Slot, Qt
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

    def __init__(self, service: ApplicationService, lifecycle: ApplicationLifecycle | None = None) -> None:
        super().__init__()
        self.service = service
        self.lifecycle = lifecycle or ApplicationLifecycle()
        self._pause_notice_shown = False
        self._reported_run = None
        self._fatal_reported = False
        self.setWindowTitle("LALC")
        self.resize(820, 620)
        root = QWidget()
        layout = QVBoxLayout(root)
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
        self.start_button.clicked.connect(self._start)
        self.pause_button.clicked.connect(self._toggle_pause)
        self.stop_button.clicked.connect(lambda: self._interact(self.service.stop))
        for button in (self.start_button, self.pause_button, self.stop_button):
            controls.addWidget(button)
        layout.addLayout(controls)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.pause_notice = QLabel()
        self.pause_notice.setWordWrap(True)
        layout.addWidget(self.pause_notice)
        self.trace = QPlainTextEdit()
        self.trace.setReadOnly(True)
        layout.addWidget(self.trace)
        self.setCentralWidget(root)
        self.render_state(service.state)

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
        inputs = json.loads(self.inputs.toPlainText())
        if type(inputs) is not dict:
            raise ValueError("输入必须是 JSON 对象。")
        self.service.start(self.entry.text().strip(), inputs)

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
        self.start_button.setEnabled(state["phase"] != "running")
        self.pause_button.setEnabled(state["phase"] == "running" and not state.get("resume_pending", False))
        self.stop_button.setEnabled(state["phase"] == "running")


def run_gui(lifecycle: ApplicationLifecycle | None = None) -> int:
    """建立 GUI；进程启动与最终报告由同一生命周期入口负责。"""

    if lifecycle is None:
        return run_application(lambda owner: run_gui(owner))
    app = QApplication.instance() or QApplication(sys.argv)
    bridge = StateBridge()
    service = ApplicationService(default_data_root(), on_change=bridge.changed.emit)
    def shutdown() -> None:
        service.shutdown()
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
