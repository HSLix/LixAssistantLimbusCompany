from __future__ import annotations

import json
import sys

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from .application import DemoService, default_data_root


class StateBridge(QObject):
    changed = Signal(dict)


class LockedDialog(QDialog):
    def reject(self) -> None:
        pass

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        event.ignore()

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.key() != Qt.Key.Key_Escape:
            super().keyPressEvent(event)


class RuntimeReviewDialog(LockedDialog):
    def __init__(self, service: DemoService, review: dict) -> None:
        super().__init__()
        self.service = service
        self.setWindowTitle("候选 Step 试运行批准")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(review["warning"]))
        evidence = QPlainTextEdit(
            review["source"] + "\n\nManifest:\n" + json.dumps(review["manifest"], ensure_ascii=False, indent=2)
        )
        evidence.setReadOnly(True)
        layout.addWidget(evidence)
        self.feedback = QPlainTextEdit()
        self.feedback.setPlaceholderText("不批准时必须填写反馈")
        layout.addWidget(self.feedback)
        buttons = QHBoxLayout()
        for label, handler in (
            ("批准一次试运行", self._approve),
            ("不批准", self._reject_with_feedback),
            ("终止任务", self._terminate),
        ):
            button = QPushButton(label)
            button.clicked.connect(handler)
            buttons.addWidget(button)
        layout.addLayout(buttons)

    def _approve(self) -> None:
        self.service.decide_runtime("approve")
        self.done(QDialog.DialogCode.Accepted)

    def _reject_with_feedback(self) -> None:
        feedback = self.feedback.toPlainText().strip()
        if not feedback:
            QMessageBox.warning(self, "需要反馈", "请填写不批准原因，供下一 Agent Turn 使用。")
            return
        self.service.decide_runtime("reject", feedback)
        self.done(QDialog.DialogCode.Rejected)

    def _terminate(self) -> None:
        answer = QMessageBox.question(self, "确认终止", "立即终止当前任务和正在运行的候选进程？")
        if answer == QMessageBox.StandardButton.Yes:
            self.service.decide_runtime("terminate")
            self.done(QDialog.DialogCode.Rejected)


class CapabilityApprovalDialog(LockedDialog):
    def __init__(self, service: DemoService, proposal: dict) -> None:
        super().__init__()
        self.service = service
        self.setWindowTitle("永久 Capability 批准")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"候选成功试运行：{'是' if proposal['trial_succeeded'] else '否'}"))
        evidence = QPlainTextEdit(json.dumps(proposal, ensure_ascii=False, indent=2))
        evidence.setReadOnly(True)
        layout.addWidget(evidence)
        buttons = QHBoxLayout()
        approve = QPushButton("批准")
        reject = QPushButton("不批准")
        approve.clicked.connect(lambda: self._decide("approve", QDialog.DialogCode.Accepted))
        reject.clicked.connect(lambda: self._decide("reject", QDialog.DialogCode.Rejected))
        buttons.addWidget(approve)
        buttons.addWidget(reject)
        layout.addLayout(buttons)

    def _decide(self, decision: str, code: QDialog.DialogCode) -> None:
        if not self.isEnabled():
            return
        self.setEnabled(False)
        self.service.decide_capability(decision)
        self.done(code)


class MainWindow(QMainWindow):
    def __init__(self, service: DemoService) -> None:
        super().__init__()
        self.service = service
        self._dialog_phase: str | None = None
        self.setWindowTitle("LALC Architecture Demo")
        self.resize(820, 620)
        root = QWidget()
        layout = QVBoxLayout(root)
        self.scenario = QComboBox()
        self.scenario.addItem("触发可恢复异常", {"supported": False, "amount": 1})
        self.scenario.addItem("普通确定性成功", {"supported": True, "amount": 1})
        layout.addWidget(self.scenario)
        controls = QHBoxLayout()
        self.start_button = QPushButton("开始")
        self.pause_button = QPushButton("暂停")
        self.stop_button = QPushButton("停止")
        self.start_button.clicked.connect(self._start)
        self.pause_button.clicked.connect(self._toggle_pause)
        self.stop_button.clicked.connect(self.service.stop)
        for button in (self.start_button, self.pause_button, self.stop_button):
            controls.addWidget(button)
        layout.addLayout(controls)
        self.status = QLabel()
        layout.addWidget(self.status)
        self.trace = QPlainTextEdit()
        self.trace.setReadOnly(True)
        layout.addWidget(self.trace)
        self.setCentralWidget(root)
        self.render_state(service.snapshot())

    def _start(self) -> None:
        self.service.start(self.scenario.currentData())

    def _toggle_pause(self) -> None:
        if self.service.snapshot()["paused"]:
            self.service.resume()
        else:
            self.service.pause()

    def render_state(self, state: dict) -> None:
        self.status.setText(
            f"状态：{state['phase']}  |  暂停：{state['paused']}  |  "
            f"Active Manifest：{state['active_manifest_id']}  |  "
            f"Working Manifest：{state['working_manifest_id']}  |  剩余 Turn：{state['remaining_turns']}"
        )
        self.trace.setPlainText("\n".join(json.dumps(item, ensure_ascii=False) for item in state["trace"]))
        self.pause_button.setText("继续" if state["paused"] else "暂停")
        self.start_button.setEnabled(state["phase"] in {"idle", "finished"})
        self.stop_button.setEnabled(state["phase"] not in {"idle", "finished", "capability_review"})
        if state["phase"] == "runtime_review" and self._dialog_phase != "runtime_review":
            self._dialog_phase = "runtime_review"
            RuntimeReviewDialog(self.service, state["pending_review"]).exec()
            self._dialog_phase = None
        elif state["phase"] == "capability_review" and self._dialog_phase != "capability_review":
            self._dialog_phase = "capability_review"
            CapabilityApprovalDialog(self.service, state["pending_capability"]).exec()
            self._dialog_phase = None


def run_gui() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    bridge = StateBridge()
    service = DemoService(default_data_root(), on_change=bridge.changed.emit)
    window = MainWindow(service)
    bridge.changed.connect(window.render_state)
    window.show()
    return app.exec()
