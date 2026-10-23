"""Developer GUI 的真实后台操作、截图预览、配置和连续修复页面。"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import Qt, QThread, Signal, QRect, QTimer
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QPlainTextEdit,
    QSpinBox, QListWidget, QListWidgetItem, QAbstractItemView, QComboBox, QFileDialog,
    QMessageBox, QDialog, QDialogButtonBox,
)

from .agent_settings import load_settings, save_settings


class Operation(QThread):
    """耗时服务放在后台；协作式取消等待实际清理完成后才报告结束。"""

    succeeded = Signal(object)
    failed = Signal(object)

    def __init__(self, operation, parent=None):
        super().__init__(parent)
        self.operation = operation
        self.loop = None
        self.task = None
        self.cancel_requested = False

    def cancel(self):
        self.cancel_requested = True
        if self.loop and self.task:
            self.loop.call_soon_threadsafe(self.task.cancel)

    def run(self):
        try:
            result = self.operation()
            if asyncio.iscoroutine(result):
                with asyncio.Runner() as runner:
                    self.loop = runner.get_loop()
                    self.task = self.loop.create_task(result)
                    if self.cancel_requested:
                        self.task.cancel()
                    result = self.loop.run_until_complete(self.task)
                    self.task = None
            self.succeeded.emit(result)
        except BaseException as error:
            self.failed.emit(error)
        finally:
            self.loop = None
            self.task = None


class CropView(QWidget):
    """缩放只影响展示；拖动端点映射回原始像素并夹紧到客户区。"""

    selected = Signal(dict)

    def __init__(self):
        super().__init__()
        self.image = QImage()
        self.region = None
        self.anchor = None
        self.setMinimumSize(320, 180)

    def set_image(self, pixels, size):
        self.image = QImage(pixels, size[0], size[1], size[0] * 4, QImage.Format.Format_ARGB32).copy()
        self.region = None
        self.anchor = None
        self.update()

    def image_rect(self):
        if self.image.isNull():
            return QRect()
        scaled = self.image.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        return QRect((self.width() - scaled.width()) // 2, (self.height() - scaled.height()) // 2,
                     scaled.width(), scaled.height())

    def pixel(self, point):
        rect = self.image_rect()
        x = max(0, min(self.image.width(), int((point.x() - rect.x()) * self.image.width() / rect.width())))
        y = max(0, min(self.image.height(), int((point.y() - rect.y()) * self.image.height() / rect.height())))
        return x, y

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.image_rect().contains(event.position().toPoint()):
            self.anchor = self.pixel(event.position())

    def mouseMoveEvent(self, event):
        if self.anchor is None or self.image.isNull():
            return
        x, y = self.pixel(event.position())
        ax, ay = self.anchor
        self.region = {"x": min(x, ax), "y": min(y, ay), "width": abs(x - ax), "height": abs(y - ay)}
        self.update()

    def mouseReleaseEvent(self, event):
        self.mouseMoveEvent(event)
        self.anchor = None
        if self.region and self.region["width"] and self.region["height"]:
            self.selected.emit(dict(self.region))

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.image_rect()
        if rect.isEmpty():
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "截图后拖动框选原图区域")
            return
        painter.drawImage(rect, self.image)
        if self.region:
            r = self.region
            painter.setPen(Qt.GlobalColor.red)
            painter.drawRect(QRect(rect.x() + round(r["x"] * rect.width() / self.image.width()),
                                   rect.y() + round(r["y"] * rect.height() / self.image.height()),
                                   round(r["width"] * rect.width() / self.image.width()),
                                   round(r["height"] * rect.height() / self.image.height())))


def button(text, callback, layout):
    control = QPushButton(text)
    control.clicked.connect(callback)
    layout.addWidget(control)
    return control


class CapturePage(QWidget):
    """明确截图、预览确认后保存同一图；坐标监测不抢焦点。"""

    def __init__(self, window):
        super().__init__()
        self.window, self.host = window, window.host
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.capture_button = button("截图", self.capture, controls)
        button("刷新坐标监测", self.refresh, controls)
        button("打开 Asset 目录", self.open_assets, controls)
        layout.addLayout(controls)
        self.coordinates = QLabel("请刷新窗口以监测坐标。")
        layout.addWidget(self.coordinates)
        self.view = CropView()
        layout.addWidget(self.view, 1)
        self.region_label = QLabel("尚未框选")
        self.view.selected.connect(lambda r: self.region_label.setText(json.dumps(r)))
        layout.addWidget(self.region_label)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Asset 完整逻辑名，例如 ui/claim")
        self.tags = QLineEdit("[]")
        self.tags.setPlaceholderText('JSON 标签列表，例如 ["zh", "mail"]；无标签填 []')
        layout.addWidget(self.name)
        layout.addWidget(self.tags)
        self.save_button = button("预览并确认保存", self.save, layout)
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.poll)

    def capture(self):
        def shown(preview):
            self.view.set_image(preview[0], preview[1])
            self.region_label.setText("截图已固定，请框选。")
        self.window.launch(self.host.capture, shown)

    def refresh(self):
        def refresh():
            self.show_coordinates(self.host.refresh_coordinates())
            self.timer.start()
        self.window._interact(refresh)

    def show_coordinates(self, value):
        self.coordinates.setText(f"客户区物理像素：({value['x']}, {value['y']})" + ("" if value["inside"] else " — 客户区外"))

    def poll(self):
        try:
            self.show_coordinates(self.host.coordinates())
        except Exception as error:
            self.timer.stop()
            self.coordinates.setText(str(error))

    def open_assets(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        def open_directory():
            path = self.host.service.asset_library.root
            if not path.is_dir() or not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.absolute()))):
                raise ValueError(f"无法打开 Asset 目录：{path}")
        self.window._interact(open_directory)

    def save(self):
        def preview():
            if not self.view.region or self.host.preview is None:
                raise ValueError("请先截图并框选区域。")
            region = dict(self.view.region)
            name, tags = self.name.text().strip(), json.loads(self.tags.text())
            from .assets import asset_name
            asset_name(name)
            self.host.service.asset_library.tags(tags)
            snapshot = self.host.preview
            pixels, size, _ = snapshot
            content, _ = self.host.service.asset_library.crop_content(pixels, size, region)
            dialog = QDialog(self)
            dialog.setWindowTitle("确认保存 Asset")
            body = QVBoxLayout(dialog)
            body.addWidget(QLabel(f"{name}\n标签：{json.dumps(tags, ensure_ascii=False)}\n原始像素区域：{region}"))
            label = QLabel()
            label.setPixmap(QPixmap.fromImage(QImage.fromData(content)).scaled(640, 400, Qt.AspectRatioMode.KeepAspectRatio))
            body.addWidget(label)
            controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
            controls.accepted.connect(dialog.accept)
            controls.rejected.connect(dialog.reject)
            body.addWidget(controls)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.window.launch(lambda: self.host.save_crop(name, region, tags, preview=snapshot),
                                   lambda value: self.region_label.setText(f"已保存：{value['image_path']}"))
        self.window._interact(preview)

    def render(self, busy):
        for control in (self.capture_button, self.save_button):
            control.setEnabled(not busy)
            control.setToolTip("Runner、Agent 或其他操作尚未结束" if busy else "")


class SettingsPage(QWidget):
    """只显示凭据是否设置；明文输入仅用于覆盖，不回读旧密钥。"""

    def __init__(self, window):
        super().__init__()
        self.window, self.host = window, window.host
        layout = QVBoxLayout(self)
        self.url, self.model = QLineEdit(), QLineEdit()
        self.limit = QSpinBox()
        self.limit.setRange(2, 2147483647)
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("API Key：空输入保留已有值")
        for label, control in (("Base URL", self.url), ("Model", self.model), ("每条消息模型请求上限", self.limit), ("API Key", self.key)):
            layout.addWidget(QLabel(label))
            layout.addWidget(control)
        self.secret_state = QLabel()
        layout.addWidget(self.secret_state)
        self.save_button = button("保存设置", self.save, layout)
        self.clear_button = button("明确清除 API Key", lambda: self.save(clear=True), layout)
        self.notice = QLabel("Windows：凭据使用当前用户 DPAPI。其他平台：凭据仅在本次 GUI 内存中保留。")
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        layout.addStretch()
        self.window._interact(self.reload)

    def reload(self):
        value = load_settings(self.host.service.data_root)
        self.url.setText(value["base_url"])
        self.model.setText(value["model"] or "")
        self.limit.setValue(value["max_requests"])
        self.show_secret(value)

    def show_secret(self, value):
        configured = bool(self.host.secret) or bool(value["secret_name"])
        self.secret_state.setText("API Key：已设置" if configured else "API Key：未设置")

    def save(self, *, clear=False):
        value = {"base_url": self.url.text().strip(), "model": self.model.text().strip() or None,
                 "max_requests": self.limit.value()}
        secret = self.key.text()
        def operation():
            with self.host.service.activity("Agent Settings"):
                saved = save_settings(self.host.service.data_root, value, secret=secret, clear=clear)
                if clear:
                    self.host.secret = None
                elif secret and sys.platform != "win32":
                    self.host.secret = secret
                return saved
        def done(saved):
            self.key.clear()
            self.show_secret(saved)
        self.window.launch(operation, done)

    def render(self, busy):
        self.save_button.setEnabled(not busy)
        self.clear_button.setEnabled(not busy)


class RepairPage(QWidget):
    """显式文件选择与连续对话；Diff、校验、Publish 和 Default 分开操作。"""

    def __init__(self, window):
        super().__init__()
        self.window, self.host = window, window.host
        self.image = None
        self.controls = []
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self.baseline = QComboBox()
        row.addWidget(self.baseline)
        self.controls.append(button("刷新 Manifest", self.refresh_manifests, row))
        self.controls.append(button("初始化／重建 Candidate", self.initialize, row))
        layout.addLayout(row)
        row = QHBoxLayout()
        for text, callback in (("New Conversation", self.new), ("刷新文件", self.refresh_files),
                               ("全选", self.select_all), ("清空选择", lambda: self.files.clearSelection())):
            self.controls.append(button(text, callback, row))
        layout.addLayout(row)
        self.files = QListWidget()
        self.files.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.files.setMaximumHeight(110)
        layout.addWidget(self.files)
        self.identity = QLabel("尚未开始对话")
        layout.addWidget(self.identity)
        self.chat = QPlainTextEdit()
        self.chat.setReadOnly(True)
        layout.addWidget(self.chat, 1)
        self.message = QPlainTextEdit()
        self.message.setPlaceholderText("输入问题、异常或下一步要求；可纯文字发送")
        self.message.setMaximumHeight(85)
        layout.addWidget(self.message)
        row = QHBoxLayout()
        self.attach = button("附加 PNG", self.attach_image, row)
        self.controls.append(self.attach)
        self.controls.append(button("清除附件", self.clear_image, row))
        self.controls.append(button("发送", self.send, row))
        self.cancel_button = button("取消本轮", window.cancel_operation, row)
        layout.addLayout(row)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.diff = QPlainTextEdit()
        self.diff.setReadOnly(True)
        self.diff.setPlaceholderText("相对 Candidate 固定基线的累计 Diff")
        layout.addWidget(self.diff, 1)
        row = QHBoxLayout()
        for text, callback in (("查看累计 Diff", self.show_diff), ("Validate", self.validate),
                               ("Publish", self.publish), ("设置 Default", self.set_default)):
            self.controls.append(button(text, callback, row))
        layout.addLayout(row)
        self.refresh_files()

    def refresh_manifests(self):
        self.window.launch(self.host.manager.list_manifests, self.set_manifests)

    def set_manifests(self, values):
        previous = self.baseline.currentData()
        self.baseline.clear()
        for value in values:
            self.baseline.addItem(value["manifest_id"], value["manifest_id"])
        index = self.baseline.findData(previous)
        if index >= 0:
            self.baseline.setCurrentIndex(index)

    def refresh_files(self):
        from .developer import candidate_files
        previous = {item.text() for item in self.files.selectedItems()}
        self.files.clear()
        if not self.host.candidate.exists():
            return
        try:
            for name in candidate_files(self.host.candidate):
                if "plan.json" not in Path(name).parts:
                    item = QListWidgetItem(name)
                    self.files.addItem(item)
                    item.setSelected(name in previous)
        except Exception as error:
            self.status.setText(str(error))

    def select_all(self):
        self.files.selectAll()

    def initialize(self):
        identity = self.baseline.currentData()
        if identity is None:
            self.status.setText("请先刷新并选择基础 Manifest。")
            return
        exists = self.host.candidate.exists() and any(self.host.candidate.iterdir())
        if exists or self.host.conversation is not None:
            response = QMessageBox.question(self, "重建 Candidate", "成功后将替换非空 Candidate 并自动开启新对话；原对话与产物保留。继续？")
            if response != QMessageBox.StandardButton.Yes:
                return
        def done(_):
            self.chat.clear()
            self.diff.clear()
            self.refresh_files()
            self.identity.setText(f"对话：{self.host.conversation.log.path.name}\nCandidate 已重建；日志：{self.host.conversation.log.path}")
        self.window.launch(lambda: self.host.initialize(identity, replace=exists), done)

    def new(self):
        def action():
            conversation = self.host.new_conversation()
            self.chat.clear()
            self.clear_image()
            self.message.clear()
            self.identity.setText(f"对话：{conversation.log.path.name}\n日志：{conversation.log.path}")
        self.window._interact(action)

    def attach_image(self):
        name, _ = QFileDialog.getOpenFileName(self, "选择 PNG", "", "PNG (*.png)")
        if name:
            self.image = Path(name)
            self.attach.setText(self.image.name)

    def clear_image(self):
        self.image = None
        self.attach.setText("附加 PNG")

    def send(self):
        def action():
            message = self.message.toPlainText().strip()
            if not message:
                raise ValueError("消息不能为空。")
            if self.host.conversation is None:
                self.host.new_conversation()
            conversation = self.host.conversation
            names = tuple(item.text() for item in self.files.selectedItems())
            image = self.image.read_bytes() if self.image else None
            args = SimpleNamespace(pi="pi", ask_api_key=False)
            self.chat.appendPlainText("你：" + message)
            self.identity.setText(f"对话：{conversation.log.path.name}\n日志：{conversation.log.path}")
            self.message.clear()
            self.clear_image()
            def operation():
                return conversation.run(message, names, args, image=image, key=self.host.secret,
                                        on_event=self.window.operation_event.emit)
            self.window.launch(operation, self.answered)
        self.window._interact(action)

    def answered(self, result):
        answer = result.get("answer", {})
        text = answer.get("message") or result.get("error") or result["reason"]
        self.chat.appendPlainText("Agent：" + str(text))
        self.status.setText(f"本轮结束：{result['reason']}；实际请求 {result['requests']} 次")
        self.refresh_files()
        self.show_diff()

    def show_event(self, event):
        value = event["event"]
        kind = value.get("type")
        if kind == "pi_version_warning":
            self.chat.appendPlainText("WARNING: " + value["message"])
        if kind in {"tool_execution_start", "tool_execution_end", "repair_tool", "validation", "lalc_request", "round_finished"}:
            if kind == "tool_execution_start":
                self.status.setText("正在调用工具：" + value.get("toolName", ""))
            elif kind == "lalc_request":
                self.status.setText(f"已发出模型请求：{value['requests']}")
            elif kind != "round_finished":
                if kind == "repair_tool":
                    shown = {"tool": value["name"], "arguments": value["arguments"],
                             "result": value["result"].get("details"), "isError": value["result"].get("isError", False)}
                elif kind == "tool_execution_end":
                    shown = {"tool": value.get("toolName"), "isError": value.get("isError"),
                             "text": [part.get("text") for part in value.get("result", {}).get("content", []) if part.get("type") == "text"]}
                else:
                    shown = value
                self.chat.appendPlainText(json.dumps(shown, ensure_ascii=False))

    def show_diff(self):
        self.window.launch(self.host.diff, self.diff.setPlainText)

    def validate(self):
        self.window.launch(self.host.validate, lambda value: self.chat.appendPlainText("Validator：" + json.dumps(value, ensure_ascii=False)))

    def publish(self):
        self.window.launch(self.host.publish, lambda identity: self.chat.appendPlainText("已发布新 Manifest：" + identity + "；Default 未改变。"))

    def set_default(self):
        identity = self.baseline.currentData()
        def operation():
            if identity is None:
                raise ValueError("请刷新并选择要设为 Default 的 Manifest。")
            result = self.host.manager.set_default(identity)
            if not result.ok:
                raise ValueError(json.dumps([error.as_dict() for error in result.errors]))
            return identity
        self.window.launch(operation, lambda value: self.status.setText("Default：" + value))

    def render(self, busy):
        for control in self.controls:
            control.setEnabled(not busy)
            control.setToolTip("当前活动尚未结束" if busy else "")
        self.files.setEnabled(not busy)
        self.baseline.setEnabled(not busy)
        self.cancel_button.setEnabled(self.window.service.state.get("activity") == "Agent")
