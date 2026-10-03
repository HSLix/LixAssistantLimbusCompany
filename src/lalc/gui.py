from __future__ import annotations

import json
import sys

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from .application import ApplicationService, StartError, default_data_root


class StateBridge(QObject):
    changed = Signal(dict)


class MainWindow(QMainWindow):
    """通过正式 ApplicationService 启动和观察任意逻辑入口。"""

    def __init__(self, service: ApplicationService) -> None:
        super().__init__()
        self.service = service
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
        self.render_state(service.state)

    def _start(self) -> None:
        try:
            inputs = json.loads(self.inputs.toPlainText())
            if type(inputs) is not dict:
                raise ValueError("输入必须是 JSON 对象。")
            self.service.start(self.entry.text().strip(), inputs)
        except (json.JSONDecodeError, ValueError, StartError) as error:
            QMessageBox.warning(self, "无法开始", str(error))

    def _toggle_pause(self) -> None:
        if self.service.state["paused"]:
            self.service.resume()
        else:
            self.service.pause()

    def render_state(self, state: dict) -> None:
        self.status.setText(
            f"状态：{state['phase']}  |  暂停：{state['paused']}  |  "
            f"Default Manifest：{state['default_manifest_id']}  |  "
            f"Base Manifest：{state['base_manifest_id']}  |  "
            f"Working Manifest：{state['working_manifest_id']}  |  Run ID：{state['run_id']}"
        )
        self.trace.setPlainText("\n".join(json.dumps(item, ensure_ascii=False) for item in state["trace"]))
        self.pause_button.setText("继续" if state["paused"] else "暂停")
        self.start_button.setEnabled(state["phase"] != "running")
        self.pause_button.setEnabled(state["phase"] == "running")
        self.stop_button.setEnabled(state["phase"] == "running")


def run_gui() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    bridge = StateBridge()
    service = ApplicationService(default_data_root(), on_change=bridge.changed.emit)
    window = MainWindow(service)
    bridge.changed.connect(window.render_state)
    window.show()
    return app.exec()
