"""Developer GUI 的真实后台操作、截图预览、配置和连续修复页面。"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import Qt, QThread, Signal, QRect, QTimer
from PySide6.QtGui import QImage, QPainter, QPixmap, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QPlainTextEdit,
    QSpinBox, QListWidget, QListWidgetItem, QAbstractItemView, QComboBox, QFileDialog,
    QMessageBox, QDialog, QDialogButtonBox,
)

from .agent_settings import load_settings, save_settings
from .agent_diagnostics import check_settings, details_text


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
        self.setAutoFillBackground(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def set_image(self, pixels, size):
        self.image = QImage(pixels, size[0], size[1], size[0] * 4, QImage.Format.Format_ARGB32).copy()
        self.region = None
        self.anchor = None
        self.selected.emit({})
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
            self.region = None
            self.anchor = self.pixel(event.position())
            self.selected.emit({})
            self.update()

    def mouseMoveEvent(self, event):
        if self.anchor is None or self.image.isNull():
            return
        x, y = self.pixel(event.position())
        ax, ay = self.anchor
        self.region = {"x": min(x, ax), "y": min(y, ay), "width": abs(x - ax), "height": abs(y - ay)}
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self.anchor is None:
            return
        self.mouseMoveEvent(event)
        self.anchor = None
        if self.region and self.region["width"] and self.region["height"]:
            self.selected.emit(dict(self.region))
        else:
            self.region = None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.image_rect()
        if rect.isEmpty():
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "截图后拖动框选原图区域")
            return
        painter.drawImage(rect, self.image)
        if self.region:
            r = self.region
            outline = QRect(rect.x() + round(r["x"] * rect.width() / self.image.width()),
                                   rect.y() + round(r["y"] * rect.height() / self.image.height()),
                                   round(r["width"] * rect.width() / self.image.width()),
                                   round(r["height"] * rect.height() / self.image.height()))
            painter.setPen(QPen(Qt.GlobalColor.black, 4))
            painter.drawRect(outline)
            painter.setPen(QPen(Qt.GlobalColor.yellow, 2, Qt.PenStyle.DashLine))
            painter.drawRect(outline)


def button(text, callback, layout):
    control = QPushButton(text)
    control.clicked.connect(callback)
    layout.addWidget(control)
    return control


def capture_tags(text: str) -> list[str]:
    """接收逗号分隔标签和旧 JSON 列表，保留顺序及重复项。"""
    from .assets import AssetLibrary
    text = text.strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            return AssetLibrary.tags(json.loads(text))
        except json.JSONDecodeError:
            # 允许用户直观输入 [en, default]；带引号的输入仍要求合法 JSON。
            if not text.endswith("]") or any(c in text for c in '\"\''):
                raise ValueError('标签格式不正确。请用英文逗号分隔，例如 en, default；留空表示无标签。') from None
            text = text[1:-1].strip()
    if any(c in text for c in '[]\"\''):
        raise ValueError('标签格式不正确。请用英文逗号分隔，例如 en, default。')
    tags = [tag.strip() for tag in text.split(",")] if text else []
    if any(not tag for tag in tags):
        raise ValueError("标签不能为空，请删除多余的逗号；无标签请将输入框留空。")
    return AssetLibrary.tags(tags)


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
        self.instructions = QLabel("① 点击截图　② 在图上按住鼠标左键拖动框选（再次拖动会替换旧框）　③ 填写名称与标签，预览并保存")
        self.instructions.setWordWrap(True)
        self.instructions.setStyleSheet("QLabel { background: #fff3cd; color: #332700; padding: 10px; font-weight: bold; }")
        layout.addWidget(self.instructions)
        self.view = CropView()
        layout.addWidget(self.view, 1)
        self.region_label = QLabel("尚未框选")
        self.view.selected.connect(lambda r: self.region_label.setText(
            f"已框选：起点 ({r['x']}, {r['y']})，大小 {r['width']} × {r['height']} 原始像素" if r else "尚未框选，请按住鼠标左键拖动。"))
        layout.addWidget(self.region_label)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Asset 完整逻辑名，例如 ui/claim")
        self.tags = QLineEdit()
        self.tags.setPlaceholderText("例如 en, default；用英文逗号分隔，无标签留空")
        layout.addWidget(QLabel("Asset 完整逻辑名"))
        layout.addWidget(self.name)
        layout.addWidget(QLabel("标签（可选，用英文逗号分隔）"))
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
            if (not self.view.region or self.view.anchor is not None or self.host.preview is None
                    or not self.view.region["width"] or not self.view.region["height"]):
                raise ValueError("请先截图并框选区域。")
            region = dict(self.view.region)
            name, tags = self.name.text().strip(), capture_tags(self.tags.text())
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


class DiagnosticPanel(QWidget):
    """保留本页错误详情与证据位置；关闭弹窗后仍可重开、复制和打开目录。"""

    def __init__(self, window, root):
        super().__init__()
        self.window = window
        self.path = root
        layout = QVBoxLayout(self)
        self.errors = QComboBox()
        layout.addWidget(self.errors)
        row = QHBoxLayout()
        self.details_button = button("查看错误详情", self.show_error, row)
        self.copy_button = button("复制详情", self.copy_error, row)
        button("打开日志目录", self.open_logs, row)
        button("打开应用日志目录", lambda: self.open_directory(window.service.data_root / "logs"), row)
        layout.addLayout(row)
        self.location = QLabel(str(root))
        self.location.setTextFormat(Qt.TextFormat.PlainText)
        self.location.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.location.setWordWrap(True)
        layout.addWidget(self.location)
        self.errors.currentIndexChanged.connect(self.select_error)
        self.select_error()

    def set_path(self, path):
        self.path = Path(path)
        self.location.setText(str(self.path))

    def add_error(self, details):
        self.errors.addItem(f"第 {details.get('round', '—')} 轮 · {details.get('stage', 'error')}：{details['message']}", details)
        self.errors.setCurrentIndex(self.errors.count() - 1)

    def select_error(self, *_):
        details = self.errors.currentData()
        self.details_button.setEnabled(details is not None)
        self.copy_button.setEnabled(details is not None)
        if details and details.get("log_path"):
            self.set_path(details["log_path"])

    def show_error(self):
        from .gui import ErrorDialog
        details = self.errors.currentData()
        if details:
            ErrorDialog(details["message"], details_text(details), parent=self).open()

    def copy_error(self):
        from PySide6.QtWidgets import QApplication
        details = self.errors.currentData()
        if details:
            QApplication.clipboard().setText(details_text(details))

    def open_logs(self):
        self.open_directory(self.path)

    def open_directory(self, path):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        def operation():
            if not path.is_dir() or not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.absolute()))):
                raise ValueError(f"日志目录尚不存在或无法打开：{path}")
        self.window._interact(operation)


class SettingsPage(QWidget):
    """只显示凭据是否设置；明文输入仅用于覆盖，不回读旧密钥。"""

    def __init__(self, window):
        super().__init__()
        self.window, self.host = window, window.host
        self.revision = 0
        layout = QVBoxLayout(self)
        self.provider = QComboBox()
        self.provider.addItem("llama.cpp", "llama.cpp")
        layout.addWidget(QLabel("服务商（Provider）"))
        layout.addWidget(self.provider)
        self.url, self.model = QLineEdit(), QLineEdit()
        self.limit = QSpinBox()
        self.limit.setRange(2, 2147483647)
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("API Key：空输入保留已有值")
        for label, control in (("Base URL", self.url), ("Model", self.model), ("每条消息模型请求上限", self.limit), ("API Key", self.key)):
            layout.addWidget(QLabel(label))
            layout.addWidget(control)
        self.output_limit = QComboBox()
        self.output_limit.addItem("使用服务端默认值", "server_default")
        layout.addWidget(QLabel("单次输出上限"))
        layout.addWidget(self.output_limit)
        self.secret_state = QLabel()
        layout.addWidget(self.secret_state)
        self.save_button = button("保存设置", self.save, layout)
        self.clear_button = button("明确清除 API Key", lambda: self.save(clear=True), layout)
        row = QHBoxLayout()
        self.connection_button = button("测试连接", lambda: self.check(False), row)
        self.model_button = button("检查模型加载状态", lambda: self.check(True), row)
        layout.addLayout(row)
        self.check_status = QLabel("尚未检查；检查只查询，不加载模型或发送推理请求。")
        self.check_status.setWordWrap(True)
        self.check_status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.check_status)
        self.diagnostics = DiagnosticPanel(window, self.host.service.data_root / "agent-diagnostics")
        layout.addWidget(self.diagnostics)
        self.notice = QLabel("Windows：凭据使用当前用户 DPAPI。其他平台：凭据仅在本次 GUI 内存中保留。")
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        layout.addStretch()
        for control in (self.url, self.model, self.key):
            control.textChanged.connect(self.invalidate)
        self.provider.currentIndexChanged.connect(self.invalidate)
        self.limit.valueChanged.connect(self.invalidate)
        self.window._interact(self.reload)

    def invalidate(self, *_):
        self.revision += 1
        self.check_status.setText("设置已变更，请重新检查；旧结果仅保留在日志中。")

    def values(self):
        return {"provider": self.provider.currentData(), "base_url": self.url.text().strip(),
                "model": self.model.text().strip() or None, "max_requests": self.limit.value(),
                "output_limit": self.output_limit.currentData()}

    def check(self, model):
        """测试当前表单快照；编辑期间完成的旧检查不得冒充当前配置结果。"""
        values, revision = self.values(), self.revision
        key = self.key.text() or self.host.secret
        self.check_status.setText("正在检查模型状态…" if model else "正在测试连接…")
        def operation():
            with self.host.service.activity("Agent Settings 检查"):
                return check_settings(self.host.service.data_root, values, key=key, check_model=model)
        def done(result):
            self.diagnostics.set_path(result["log_path"])
            if not result["ok"]:
                self.diagnostics.add_error(result["error"])
            if revision != self.revision:
                self.check_status.setText("检查期间设置已变更，请重新检查；本次结果已保存到日志。")
                return
            self.check_status.setText(("错误：" if not result["ok"] else "") + result["message"])
            if not result["ok"]:
                self.diagnostics.show_error()
        self.window.launch(operation, done)

    def reload(self):
        value = load_settings(self.host.service.data_root)
        self.provider.setCurrentIndex(self.provider.findData(value["provider"]))
        self.url.setText(value["base_url"])
        self.model.setText(value["model"] or "")
        self.limit.setValue(value["max_requests"])
        self.show_secret(value)

    def show_secret(self, value):
        configured = bool(self.host.secret) or bool(value["secret_name"])
        self.secret_state.setText("API Key：已设置" if configured else "API Key：未设置")

    def save(self, *, clear=False):
        value = self.values()
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
            self.invalidate()
            self.key.clear()
            self.show_secret(saved)
        self.window.launch(operation, done)

    def render(self, busy):
        self.save_button.setEnabled(not busy)
        self.clear_button.setEnabled(not busy)
        self.connection_button.setEnabled(not busy)
        self.model_button.setEnabled(not busy)


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
        for text, callback in (("New Conversation", self.new), ("刷新文件", self.refresh_files)):
            self.controls.append(button(text, callback, row))
        layout.addLayout(row)
        self.files = QListWidget()
        self.files.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.files.setMaximumHeight(110)
        layout.addWidget(self.files)
        self.identity = QLabel("尚未开始对话")
        layout.addWidget(self.identity)
        self.diagnostics = DiagnosticPanel(window, self.host.service.data_root / "agent-interactions")
        layout.addWidget(self.diagnostics)
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
        self.request_progress = QLabel("对话轮次：尚未开始；本轮模型请求：0")
        layout.addWidget(self.request_progress)
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
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
        self.files.clear()
        if not self.host.candidate.exists():
            return
        try:
            for name in candidate_files(self.host.candidate):
                if "plan.json" not in Path(name).parts:
                    item = QListWidgetItem(name)
                    self.files.addItem(item)
        except Exception as error:
            self.status.setText(str(error))

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
            self.request_progress.setText("对话轮次：尚未开始；本轮模型请求：0")
            self.diagnostics.errors.clear()
            self.diagnostics.set_path(self.host.conversation.log.path)
            self.diff.clear()
            self.refresh_files()
            self.identity.setText(f"对话：{self.host.conversation.log.path.name}\nCandidate 已重建；日志：{self.host.conversation.log.path}")
        self.window.launch(lambda: self.host.initialize(identity, replace=exists), done)

    def new(self):
        def action():
            conversation = self.host.new_conversation()
            self.chat.clear()
            self.request_progress.setText("对话轮次：尚未开始；本轮模型请求：0")
            self.diagnostics.errors.clear()
            self.diagnostics.set_path(conversation.log.path)
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
            self.diagnostics.set_path(conversation.log.path)
            image = self.image.read_bytes() if self.image else None
            args = SimpleNamespace(pi="pi", ask_api_key=False)
            limit = load_settings(self.host.service.data_root)["max_requests"]
            self.request_progress.setText(f"对话轮次：{conversation.log.group + 1}；本轮模型请求：0/{limit}")
            self.chat.appendPlainText("你：" + message)
            self.identity.setText(f"对话：{conversation.log.path.name}\n日志：{conversation.log.path}")
            self.message.clear()
            self.clear_image()
            def operation():
                return conversation.run(message, args, image=image, key=self.host.secret,
                                        on_event=self.window.operation_event.emit)
            self.window.launch(operation, self.answered)
        self.window._interact(action)

    def answered(self, result):
        answer = result.get("answer", {})
        if result.get("diagnostics"):
            self.diagnostics.add_error(result["diagnostics"])
            self.diagnostics.show_error()
        elif result.get("error"):
            self.diagnostics.add_error({"message": result["error"], "stage": result["reason"],
                                        "round": result.get("round"), "log_path": result.get("log_path")})
            self.diagnostics.show_error()
        elif result["reason"] == "answered":
            self.chat.appendPlainText("Agent：" + str(answer.get("message", "")))
        summary = "错误：" + result["error"] if result.get("error") else "本轮结束：" + result["reason"]
        self.status.setText(f"{summary}；实际请求 {result['requests']} 次")
        self.refresh_files()
        self.show_diff()

    def show_event(self, event):
        value = event["event"]
        kind = value.get("type")
        if kind == "lalc_request":
            self.request_progress.setText(f"对话轮次：{event.get('round', '—')}；本轮模型请求："
                                          f"{value['requests']}/{value.get('request_limit', '—')}")
        # 手动校验由完成回调显示，日志事件可能在首次发送后也经信号送达。
        if kind == "validation" and value.get("source") == "manual":
            return
        if kind == "final_answer_retry":
            self.diagnostics.add_error(value["diagnostics"])
            self.status.setText(f"最终回复格式错误，正在要求重新生成；剩余请求 {value['requests_remaining']} 次。")
        if kind == "validation" and not value.get("ok"):
            self.diagnostics.add_error({"message": "候选校验失败，请查看错误详情。", "stage": "validation",
                                        "errors": value.get("errors", []), "round": event.get("round"),
                                        "log_path": str(self.host.conversation.log.path) if self.host.conversation else None})
            self.status.setText("错误：候选校验失败；Candidate 和对话已保留。")
        if kind == "tool_execution_end" and value.get("isError"):
            self.diagnostics.add_error({"message": "工具执行失败：" + value.get("toolName", "unknown"),
                                        "stage": "tool:" + value.get("toolName", "unknown"), "event": value,
                                        "round": event.get("round"),
                                        "log_path": str(self.host.conversation.log.path) if self.host.conversation else None})
            self.status.setText("错误：工具执行失败，可查看详情；本轮继续处理。")
        if kind == "repair_tool" and value.get("result", {}).get("isError"):
            details = value["result"].get("details", {})
            self.diagnostics.add_error({**details, "message": details.get("message") or details.get("error") or "工具执行失败",
                                        "stage": "tool:" + value["name"], "round": event.get("round"),
                                        "log_path": str(self.host.conversation.log.path) if self.host.conversation else None})
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
                if kind == "validation":
                    shown = {"ok": value["ok"], "errors": value.get("errors", [])}
                self.chat.appendPlainText(("Validator：" if kind == "validation" else "")
                                          + json.dumps(shown, ensure_ascii=False))

    def show_diff(self):
        self.window.launch(self.host.diff, self.diff.setPlainText)

    def validate(self):
        def done(value):
            self.show_event({"event": {"type": "validation", **value}})
            if not value.get("ok"):
                self.diagnostics.show_error()
        self.window.launch(self.host.validate, done)

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
