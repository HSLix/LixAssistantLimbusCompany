"""Developer GUI 的真实后台操作、截图预览、配置和连续修复页面。"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import Qt, QThread, Signal, QRect, QTimer
from PySide6.QtGui import QImage, QPainter, QPixmap, QPen, QFontDatabase
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QFileDialog,
    QMessageBox, QDialog, QDialogButtonBox,
)

from qfluentwidgets import (
    BodyLabel as QLabel, PushButton as QPushButton, LineEdit as QLineEdit,
    PlainTextEdit as QPlainTextEdit, SpinBox as QSpinBox, ComboBox as QComboBox,
    CheckBox as QCheckBox,
)

from .i18n import tr

from .repair_chat import RepairChat
from .agent_settings import load_settings, save_settings, save_selection, settings_snapshot
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


class TrialDialog(QDialog):
    """试运行的模态日志窗口；阻止主界面操作，显示时不抢游戏焦点。"""

    def __init__(self, service, parent):
        super().__init__(parent)
        self.service = service
        self.setWindowTitle(tr('Agent trial'))
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.resize(760, 480)
        layout = QVBoxLayout(self)
        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        layout.addWidget(self.logs)
        controls = QHBoxLayout()
        self.pause = button(tr('Pause'), lambda: service.resume() if service.state["paused"] else service.pause(), controls)
        self.stop = button(tr('Stop'), service.stop, controls)
        layout.addLayout(controls)
        self.sequence = 0
        self.pause_notice = QLabel()
        self.pause_notice.setWordWrap(True)
        layout.addWidget(self.pause_notice)
        self._pause_notice_shown = False

    def render(self, state):
        for record in state["trace"]:
            if record["sequence"] > self.sequence:
                self.logs.appendPlainText(json.dumps(record, ensure_ascii=False))
                self.sequence = record["sequence"]
        info = state.get("pause_info")
        if info:
            instruction = tr("Resuming checks the current Step's condition.") if info["has_condition"] else tr('Resuming restarts the current Step.')
            if not info.get("restart_step", True):
                instruction = tr('Resuming continues Workflow observation and scheduling.')
            self.pause_notice.setText(f"{info['reason']}\n{info['description']}\n{instruction}")
            if not self._pause_notice_shown:
                self._pause_notice_shown = True
                self.logs.appendPlainText(info.get("traceback", ""))
                self.parentWidget().showNormal()
                self.parentWidget().raise_()
                self.parentWidget().activateWindow()
        else:
            self._pause_notice_shown = False
            self.pause_notice.clear()
        self.pause.setText(tr('Resume') if state["paused"] else tr('Pause'))
        self.pause.setEnabled(not state.get("resume_pending", False))

    def reject(self):
        """Escape 不关闭运行窗口；停止通过执行器完成。"""

    def closeEvent(self, event):
        event.ignore()


class CropView(QWidget):
    """缩放只影响展示；拖动端点映射回原始像素并夹紧到客户区。"""

    selected = Signal(dict)

    def __init__(self):
        super().__init__()
        self.image = QImage()
        self.region = None
        self.anchor = None
        self.setMouseTracking(True)
        self.magnifier = QLabel(self)
        self.magnifier.setFixedSize(165, 187)
        self.magnifier.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.magnifier.hide()
        self.setMinimumSize(320, 180)
        self.setAutoFillBackground(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def set_image(self, pixels, size):
        self.magnifier.hide()
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

    def update_magnifier(self, point):
        """原图像素邻域按最近邻放大；边缘补底色，指针像素始终对准十字。"""
        if self.image.isNull() or not self.image_rect().contains(point.toPoint()):
            self.magnifier.hide()
            return
        x, y = self.pixel(point)
        x, y = min(x, self.image.width() - 1), min(y, self.image.height() - 1)
        area = QRect(x - 16, y - 16, 33, 33).intersected(self.image.rect())
        canvas = QPixmap(165, 187)
        canvas.fill(Qt.GlobalColor.black)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawImage(QRect((area.x() - x + 16) * 5, (area.y() - y + 16) * 5,
                                area.width() * 5, area.height() * 5), self.image, area)
        painter.setPen(QPen(Qt.GlobalColor.yellow, 1))
        painter.drawRect(80, 80, 5, 5)
        painter.drawLine(82, 0, 82, 77)
        painter.drawLine(0, 82, 77, 82)
        painter.drawLine(87, 82, 164, 82)
        painter.drawLine(82, 87, 82, 164)
        painter.drawText(QRect(0, 165, 165, 22), Qt.AlignmentFlag.AlignCenter, f"({x}, {y}) · 5×")
        painter.end()
        self.magnifier.setPixmap(canvas)
        self.magnifier.move(0 if point.x() > self.width() / 2 else self.width() - 165,
                            0 if point.y() > self.height() / 2 else max(0, self.height() - 187))
        self.magnifier.show()
        self.magnifier.raise_()

    def leaveEvent(self, event):
        self.magnifier.hide()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self.update_magnifier(event.position())
        if event.button() == Qt.MouseButton.LeftButton and self.image_rect().contains(event.position().toPoint()):
            self.region = None
            self.anchor = self.pixel(event.position())
            self.selected.emit({})
            self.update()

    def mouseMoveEvent(self, event):
        self.update_magnifier(event.position())
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
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, tr('Capture a screenshot, then drag to select an area'))
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
        self.capture_button = button(tr('Capture screenshot'), self.capture, controls)
        button(tr('Refresh coordinate tracking'), self.refresh, controls)
        button(tr('Open Asset directory'), self.open_assets, controls)
        layout.addLayout(controls)
        sizing = QHBoxLayout()
        self.window_width, self.window_height = QSpinBox(), QSpinBox()
        for label, control, value in ((tr('Client width (px)'), self.window_width, 1280),
                                      (tr('Height (px)'), self.window_height, 720)):
            control.setRange(1, 32768)
            control.setValue(value)
            sizing.addWidget(QLabel(label))
            sizing.addWidget(control)
        self.resize_button = button(tr('Resize window'), self.resize_window, sizing)
        layout.addLayout(sizing)
        self.resize_result = QLabel(tr('Window position, stacking order and focus are preserved. Capture a new screenshot after resizing.'))
        self.resize_result.setWordWrap(True)
        layout.addWidget(self.resize_result)
        self.coordinates = QLabel(tr('Refresh the window to track coordinates.'))
        layout.addWidget(self.coordinates)
        self.instructions = QLabel(tr('1. Capture a screenshot. 2. Drag with the left mouse button to select an area (drag again to replace). 3. Enter a name and tags, then preview and save.'))
        self.instructions.setWordWrap(True)
        self.instructions.setStyleSheet("QLabel { background: #fff3cd; color: #332700; padding: 10px; font-weight: bold; }")
        layout.addWidget(self.instructions)
        self.view = CropView()
        layout.addWidget(self.view, 1)
        self.region_label = QLabel(tr('No selection'))
        self.view.selected.connect(lambda r: self.region_label.setText(
            tr('Selected: origin ({0}, {1}), size {2} × {3} original pixels').format(r['x'], r['y'], r['width'], r['height']) if r else tr('No selection. Drag with the left mouse button.')))
        layout.addWidget(self.region_label)
        self.name = QLineEdit()
        self.name.setPlaceholderText(tr('Full Asset logical name, e.g. ui/claim'))
        self.tags = QLineEdit()
        self.tags.setPlaceholderText(tr('E.g. en, default; comma-separated, leave empty for no tags'))
        layout.addWidget(QLabel(tr('Full Asset logical name')))
        layout.addWidget(self.name)
        layout.addWidget(QLabel(tr('Tags (optional, comma-separated)')))
        layout.addWidget(self.tags)
        self.save_button = button(tr('Preview and confirm save'), self.save, layout)
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.poll)

    def resize_window(self):
        width, height = self.window_width.value(), self.window_height.value()
        def done(result):
            before, after = result["before"], result["after"]
            self.resize_result.setText(tr('Target: {0} × {1}; before: {2} × {3}; actual: {4} × {5} px').format(width, height, before['width'], before['height'], after['width'], after['height']))
        self.window.launch(lambda: self.host.resize_window(width, height), done)

    def capture(self):
        def shown(preview):
            self.view.set_image(preview[0], preview[1])
            self.region_label.setText(tr('Screenshot captured. Select an area.'))
        self.window.launch(self.host.capture, shown)

    def refresh(self):
        def refresh():
            self.show_coordinates(self.host.refresh_coordinates())
            self.timer.start()
        self.window._interact(refresh)

    def show_coordinates(self, value):
        self.coordinates.setText(tr('Client physical pixels: ({0}, {1})').format(value['x'], value['y']) + ("" if value["inside"] else tr(' — outside client area')))

    def poll(self):
        try:
            self.show_coordinates(self.host.coordinates())
        except Exception as error:
            self.timer.stop()
            self.coordinates.setText(str(error))

    def open_assets(self):
        """首次打开时创建 Asset 目录，创建或系统打开失败仍交给统一错误弹窗。"""
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        def open_directory():
            path = self.host.service.asset_library.root
            path.mkdir(parents=True, exist_ok=True)
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
            dialog.setWindowTitle(tr('Confirm Asset save'))
            body = QVBoxLayout(dialog)
            body.addWidget(QLabel(tr('{0}\nTags: {1}\nOriginal pixel region: {2}').format(name, json.dumps(tags, ensure_ascii=False), region)))
            label = QLabel()
            label.setPixmap(QPixmap.fromImage(QImage.fromData(content)).scaled(640, 400, Qt.AspectRatioMode.KeepAspectRatio))
            body.addWidget(label)
            controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
            controls.accepted.connect(dialog.accept)
            controls.rejected.connect(dialog.reject)
            body.addWidget(controls)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.window.launch(lambda: self.host.save_crop(name, region, tags, preview=snapshot),
                                   lambda value: self.region_label.setText(tr('Saved: {0}').format(value['image_path'])))
        self.window._interact(preview)

    def render(self, busy):
        for control in (self.capture_button, self.save_button, self.resize_button, self.window_width, self.window_height):
            control.setEnabled(not busy)
            control.setToolTip(tr('A run, Agent or other operation has not finished') if busy else "")


def open_directory(window, path):
    """打开本地目录，目录缺失或系统拒绝时统一报错。"""
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
    def operation():
        if not path.is_dir() or not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.absolute()))):
            raise ValueError(f"目录尚不存在或无法打开：{path}")
    window._interact(operation)


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
        self.details_button = button(tr('View error details'), self.show_error, row)
        self.copy_button = button(tr('Copy details'), self.copy_error, row)
        button(tr('Open log directory'), self.open_logs, row)
        button(tr('Open application log directory'), lambda: self.open_directory(window.service.data_root / "logs"), row)
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
        self.errors.addItem(tr('Round {0} · {1}: {2}').format(details.get('round', '—'), details.get('stage', 'error'), details['message']), userData=details)
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
        open_directory(self.window, path)


class SettingsPage(QWidget):
    """只显示凭据是否设置；明文输入仅用于覆盖，不回读旧密钥。"""

    def __init__(self, window, *, side="developer"):
        super().__init__()
        self.window, self.host = window, window.host
        self.side = side
        self.loading = True
        self.dirty = False
        self.revision = 0
        layout = QVBoxLayout(self)
        self.provider = QComboBox()
        self.provider.addItem("llama.cpp", userData="llama.cpp")
        self.provider.addItem("DeepSeek", userData="deepseek")
        self.form_provider = "llama.cpp"
        layout.addWidget(QLabel(tr('Provider')))
        layout.addWidget(self.provider)
        self.url, self.model = QLineEdit(), QLineEdit()
        self.limit = QSpinBox()
        self.limit.setRange(2, 2147483647)
        self.key = None
        if side == "developer":
            self.key = QLineEdit()
            self.key.setEchoMode(QLineEdit.EchoMode.Password)
            self.key.setPlaceholderText(tr('API Key: leave empty to keep the existing key'))
        for label, control in ((tr('Base URL'), self.url), (tr('Model'), self.model)):
            layout.addWidget(QLabel(label))
            layout.addWidget(control)
        self.secret_state = QLabel()
        if self.key is not None:
            layout.addWidget(self.secret_state)
            layout.addWidget(QLabel("API Key"))
            layout.addWidget(self.key)
            key_layout = layout
        else:
            key_layout = QHBoxLayout()
            key_layout.addWidget(self.secret_state, 1)
            self.key_button = button(tr('Set API key'), self.set_api_key, key_layout)
            layout.addLayout(key_layout)
        self.clear_button = button(tr('Clear API key'), lambda: self.window._interact(lambda: self.save(clear=True)), key_layout)
        self.advanced = QWidget()
        advanced = QVBoxLayout(self.advanced)
        advanced.setContentsMargins(0, 0, 0, 0)
        if side == "user":
            self.advanced_button = QPushButton(tr('Advanced Settings'))
            self.advanced_button.setCheckable(True)
            self.advanced_button.toggled.connect(self.advanced.setVisible)
            layout.addWidget(self.advanced_button)
            self.advanced.hide()
        advanced.addWidget(QLabel(tr('Maximum model requests per message')))
        advanced.addWidget(self.limit)
        self.deepseek_options = QWidget()
        options = QVBoxLayout(self.deepseek_options)
        options.setContentsMargins(0, 0, 0, 0)
        self.thinking = QCheckBox(tr('Enable thinking'))
        self.thinking.setChecked(True)
        self.effort = QComboBox()
        for effort in ("low", "high", "max"):
            self.effort.addItem(effort, userData=effort)
        self.effort.setCurrentIndex(1)
        options.addWidget(self.thinking)
        options.addWidget(QLabel(tr('Reasoning effort')))
        options.addWidget(self.effort)
        advanced.addWidget(self.deepseek_options)
        self.thinking.toggled.connect(self.effort.setEnabled)
        self.thinking.toggled.connect(self.invalidate)
        self.effort.currentIndexChanged.connect(self.invalidate)
        self.deepseek_options.hide()
        self.output_limit = QComboBox()
        self.output_limit.addItem(tr('Use server default'), userData="server_default")
        advanced.addWidget(QLabel(tr('Maximum output per request')))
        advanced.addWidget(self.output_limit)
        layout.addWidget(self.advanced)
        row = QHBoxLayout()
        self.connection_button = button(tr('Test connection'), lambda: self.check(False), row)
        self.model_button = button(tr('Check model loading status'), lambda: self.check(True), row)
        layout.addLayout(row)
        self.check_status = QLabel(tr('Not checked. Checks only query; they do not load models or send inference requests.'))
        self.check_status.setWordWrap(True)
        self.check_status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.check_status)
        if side == "developer":
            self.diagnostics = DiagnosticPanel(window, self.host.service.data_root / "agent-diagnostics")
            layout.addWidget(self.diagnostics)
        self.notice = QLabel(tr("Windows: credentials use the current user's DPAPI. Other platforms: credentials remain in memory for this GUI session only."))
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        layout.addStretch()
        for control in (self.url, self.model, self.key):
            if control is not None:
                control.textChanged.connect(self.invalidate)
        self.provider.currentIndexChanged.connect(self.switch_provider)
        self.limit.valueChanged.connect(self.invalidate)
        self.window._interact(self.reload)
        for control in (self.url, self.model, self.key):
            if control is not None:
                control.editingFinished.connect(self.auto_save)
        self.limit.valueChanged.connect(self.auto_save)
        for control in (self.effort, self.output_limit):
            control.currentIndexChanged.connect(self.auto_save)
        self.thinking.toggled.connect(self.auto_save)

    def pending_key(self):
        """仅提供当前输入用于检查和脱敏，不回读已有密钥。"""
        return self.key.text() if self.key is not None else ""

    def set_api_key(self):
        """密钥只在输入弹窗存活期间保留，成功保存后关闭。"""
        dialog = QDialog(self)
        dialog.setWindowTitle(tr('Set API key'))
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        layout = QVBoxLayout(dialog)
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText(tr('Enter a new API key'))
        layout.addWidget(self.key)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.key.textChanged.connect(lambda text: buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(bool(text.strip())))
        layout.addWidget(buttons)
        def confirm():
            def operation():
                self.save(secret=self.pending_key())
                dialog.accept()
            self.window._interact(operation)
        def finished():
            self.key.clear()
            self.key = None
        buttons.accepted.connect(confirm)
        buttons.rejected.connect(dialog.reject)
        dialog.finished.connect(finished)
        dialog.open()

    def invalidate(self, *_):
        if self.loading:
            return
        self.dirty = True
        self.revision += 1
        self.check_status.setText(tr('Settings changed. Check again; previous results remain in the logs.'))

    def values(self):
        value = {"provider": self.provider.currentData(), "base_url": self.url.text(),
                 "model": self.model.text() or None, "max_requests": self.limit.value(),
                 "output_limit": self.output_limit.currentData()}
        if value["provider"] == "deepseek":
            value.update(thinking=self.thinking.isChecked(), reasoning_effort=self.effort.currentData())
        return value

    def auto_save(self, *_):
        if not self.loading and self.dirty and self.isEnabled():
            self.window._interact(self.save)

    def submit(self):
        """交接/重载前提交尚未失焦的输入；禁用表单不回写旧配置。"""
        if self.side == "user" and self.key is not None:
            raise ValueError(tr('Confirm or cancel API key entry first'))
        if self.dirty and self.isEnabled():
            self.save()

    def switch_provider(self):
        """先保存旧平台输入，再保存本侧选择，失败保留旧表单。"""
        if self.loading:
            return
        provider = self.provider.currentData()
        self.provider.blockSignals(True)
        self.provider.setCurrentIndex(self.provider.findData(self.form_provider))
        self.provider.blockSignals(False)
        def switch():
            self.submit()
            save_selection(self.host.service.data_root, self.side, provider)
            self.reload()
        self.window._interact(switch)

    def check(self, model):
        """测试当前表单快照；编辑期间完成的旧检查不得冒充当前配置结果。"""
        values, revision = self.values(), self.revision
        key = self.pending_key() or None
        self.check_status.setText(tr('Checking model status…') if model else tr('Testing connection…'))
        def operation():
            with self.host.service.activity("Agent Settings 检查"):
                frozen, actual_key = settings_snapshot(SimpleNamespace(**values, ask_api_key=False),
                    self.host.service.data_root, key=key, temporary_keys=self.host.secrets)
                return check_settings(self.host.service.data_root, frozen, key=actual_key,
                                      check_model=model, snapshot=True)
        def done(result):
            if self.side == "developer":
                self.diagnostics.set_path(result["log_path"])
                if not result["ok"]:
                    self.diagnostics.add_error(result["error"])
            if revision != self.revision:
                self.check_status.setText(tr('Settings changed during the check. Check again; this result was saved to the logs.'))
            else:
                message = result["message"]
                if result["ok"]:
                    if not model:
                        message = tr("Connected and authenticated; model list available ({0} entries). Inference was not tested.").format(result.get("model_count", "—"))
                    elif values["provider"] == "deepseek":
                        message = tr("deepseek-flash is available and supports images. Inference was not tested.")
                    else:
                        status = result.get("model_status", "unknown")
                        label = {"loaded": tr("Loaded"), "unloaded": tr("Not loaded"),
                                 "loading": tr("Loading"), "unknown": tr("Status unavailable")}.get(status, status)
                        message = tr("Model status: {0} ({1}). Inference was not tested.").format(label, status)
                self.check_status.setText((tr('Error: ') if not result["ok"] else "") + message)
            if not result["ok"]:
                if self.side == "developer":
                    if revision == self.revision:
                        self.diagnostics.show_error()
                else:
                    from .gui import ErrorDialog
                    message = result["message"] if revision == self.revision else tr('The previous configuration check failed. Settings have changed; check again.')
                    ErrorDialog(message, details_text(result["error"]), parent=self.window).open()
        self.window.launch(operation, done)

    def reload(self):
        self.loading = True
        try:
            value = load_settings(self.host.service.data_root, side=self.side, for_use=False)
            self.provider.setCurrentIndex(self.provider.findData(value["provider"]))
            self.form_provider = value["provider"]
            self.deepseek_options.setVisible(value["provider"] == "deepseek")
            self.model.setReadOnly(value["provider"] == "deepseek")
            self.model_button.setText(tr('Check model availability') if value["provider"] == "deepseek" else tr('Check model loading status'))
            self.thinking.setChecked(value["thinking"])
            self.effort.setCurrentIndex(self.effort.findData(value["reasoning_effort"]))
            self.url.setText(value["base_url"])
            self.model.setText(value["model"] or "")
            self.limit.setValue(value["max_requests"])
            if self.key is not None:
                self.key.clear()
            self.show_secret(value)
            self.dirty = False
        finally:
            self.loading = False

    def show_secret(self, value):
        configured = bool(self.host.secrets.get(value["provider"])) or bool(value["secret_name"])
        self.secret_state.setText(tr('API Key: set') if configured else tr('API Key: not set'))

    def save(self, *, clear=False, secret=None):
        """本地保存不占用后台活动队列；失败保留表单和未保存状态。"""
        if not self.isEnabled():
            return
        value = self.values()
        secret = self.pending_key() if secret is None else secret
        saved = save_settings(self.host.service.data_root, value, secret=secret, clear=clear,
                              side=self.side, temporary_keys=self.host.secrets)
        self.loading = True
        try:
            if self.side == "developer":
                self.key.clear()
            self.dirty = False
            self.show_secret(saved)
        finally:
            self.loading = False
        self.revision += 1
        if secret or clear:
            self.check_status.setText(tr('Settings changed. Check again; previous results remain in the logs.'))
        coordinator = getattr(self.window, "coordinator", None)
        if coordinator is not None:
            coordinator.refresh_agent()
        return saved

    def render(self, busy):
        self.clear_button.setEnabled(not self.window.closing)
        self.connection_button.setEnabled(not busy)
        self.model_button.setEnabled(not busy)


class RepairPage(QWidget):
    """分轮连续对话与工作区入口；Diff、校验、Publish 和 Default 分开操作。"""

    def __init__(self, window):
        super().__init__()
        self.window, self.host = window, window.host
        self.images = []
        self.tool_errors = {}
        self.controls = []
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self.baseline = QComboBox()
        row.addWidget(self.baseline)
        self.controls.append(button(tr('Refresh Manifests'), self.refresh_manifests, row))
        self.controls.append(button(tr('Initialize / rebuild Candidate'), self.initialize, row))
        layout.addLayout(row)
        row = QHBoxLayout()
        self.controls.append(button(tr("New Conversation"), self.new, row))
        self.workspace_button = button(tr('Open Agent workspace'), self.open_workspace, row)
        self.pages_button = button(tr('Open external settings page directory'), self.open_pages, row)
        layout.addLayout(row)
        self.identity = QLabel(tr('No conversation started'))
        layout.addWidget(self.identity)
        self.diagnostics = DiagnosticPanel(window, self.host.service.data_root / "agent-interactions")
        layout.addWidget(self.diagnostics)
        self.chat = RepairChat()
        layout.addWidget(self.chat, 1)
        self.message = QPlainTextEdit()
        self.message.setPlaceholderText(tr('Enter a question, error or next instruction; text-only messages are supported'))
        self.message.setMaximumHeight(85)
        layout.addWidget(self.message)
        row = QHBoxLayout()
        self.attach = button(tr('Attach images'), self.attach_image, row)
        self.controls.append(self.attach)
        self.controls.append(button(tr('Clear attachments'), self.clear_image, row))
        self.controls.append(button(tr('Send'), self.send, row))
        self.cancel_button = button(tr('Cancel round'), window.cancel_operation, row)
        layout.addLayout(row)
        self.request_progress = QLabel(tr('Conversation round: not started; model requests this round: 0'))
        layout.addWidget(self.request_progress)
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        row = QHBoxLayout()
        for text, callback in ((tr('View cumulative Diff'), self.show_diff), (tr('Validate'), self.validate),
                               (tr('Publish'), self.publish), (tr('Set Default'), self.set_default)):
            self.controls.append(button(text, callback, row))
        layout.addLayout(row)

    def refresh_manifests(self):
        self.window.launch(self.host.manager.list_manifests, self.set_manifests)

    def set_manifests(self, values):
        previous = self.baseline.currentData()
        self.baseline.clear()
        for value in values:
            self.baseline.addItem(value["manifest_id"], userData=value["manifest_id"])
        index = self.baseline.findData(previous)
        if index >= 0:
            self.baseline.setCurrentIndex(index)

    def open_pages(self):
        """打开实际页面发现目录；首次使用时创建空目录，不重载页面。"""
        def operation():
            path = self.host.service.data_root / "pages"
            path.mkdir(parents=True, exist_ok=True)
            open_directory(self.window, path)
        self.window._interact(operation)

    def open_workspace(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        def operation():
            if not self.host.candidate.is_dir():
                raise ValueError("请先明确初始化 Candidate，再打开 Agent 工作区。")
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.host.candidate))):
                raise ValueError(f"无法打开 Agent 工作区：{self.host.candidate}")
        self.window._interact(operation)

    def initialize(self):
        identity = self.baseline.currentData()
        if identity is None:
            self.status.setText(tr('Refresh and select a base Manifest first.'))
            return
        exists = self.host.candidate.exists() and any(self.host.candidate.iterdir())
        if exists or self.host.conversation is not None:
            response = QMessageBox.question(self, tr('Rebuild Candidate'), tr('Success replaces the non-empty Candidate and starts a new conversation; the previous conversation and artifacts are retained. Continue?'))
            if response != QMessageBox.StandardButton.Yes:
                return
        def done(_):
            self.chat.clear()
            self.tool_errors.clear()
            self.request_progress.setText(tr('Conversation round: not started; model requests this round: 0'))
            self.diagnostics.errors.clear()
            self.diagnostics.set_path(self.host.conversation.log.path)
            self.identity.setText(tr('Conversation: {0}\nCandidate rebuilt; log: {1}').format(self.host.conversation.log.path.name, self.host.conversation.log.path))
        self.window.launch(lambda: self.host.initialize(identity, replace=exists), done)

    def new(self):
        def action():
            conversation = self.host.new_conversation()
            self.chat.clear()
            self.tool_errors.clear()
            self.request_progress.setText(tr('Conversation round: not started; model requests this round: 0'))
            self.diagnostics.errors.clear()
            self.diagnostics.set_path(conversation.log.path)
            self.clear_image()
            self.message.clear()
            self.identity.setText(tr('Conversation: {0}\nLog: {1}').format(conversation.log.path.name, conversation.log.path))
        self.window._interact(action)

    def attach_image(self):
        names, _ = QFileDialog.getOpenFileNames(self, tr('Choose images (multiple selection allowed)'), "", tr('All files (*)'))
        if names:
            self.images.extend(Path(name) for name in names)
            self.attach.setText(tr('{0} images attached').format(len(self.images)))
            self.attach.setToolTip("\n".join(str(path) for path in self.images))

    def clear_image(self):
        self.images = []
        self.attach.setText(tr('Attach images'))
        self.attach.setToolTip("")

    def send(self):
        def action():
            message = self.message.toPlainText().strip()
            if not message:
                raise ValueError("消息不能为空。")
            if self.host.conversation is None:
                self.host.new_conversation()
            conversation = self.host.conversation
            self.diagnostics.set_path(conversation.log.path)
            images = list(self.images)
            args = SimpleNamespace(pi="pi", ask_api_key=False)
            limit = load_settings(self.host.service.data_root)["max_requests"]
            self.request_progress.setText(tr('Conversation round: {0}; model requests this round: 0/{1}').format(conversation.log.group + 1, limit))
            self.chat.add_message("你", message, conversation.log.group + 1)
            self.identity.setText(tr('Conversation: {0}\nLog: {1}').format(conversation.log.path.name, conversation.log.path))
            self.message.clear()
            self.clear_image()
            def operation():
                return conversation.run(message, args, images=images, key=None,
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
            self.chat.add_message("Agent", str(answer.get("message", "")),
                                  result.get("round", self.host.conversation.log.group if self.host.conversation else 0))
        summary = tr('Error: ') + result["error"] if result.get("error") else tr('Round ended: ') + result["reason"]
        self.status.setText(tr('{0}; actual requests: {1}').format(summary, result['requests']))

    def show_event(self, event):
        value = event["event"]
        kind, number = value.get("type"), event.get("round", 0)
        if kind == "lalc_request":
            self.request_progress.setText(tr('Conversation round: {0}; model requests this round: {1}/{2}').format(number, value['requests'], value.get('request_limit', '—')))
            self.status.setText(tr('Model requests sent: {0}').format(value['requests']))
        elif kind == "final_answer_retry":
            self.diagnostics.add_error(value["diagnostics"])
            self.status.setText(tr('Invalid final response format; requesting a new response. Remaining requests: {0}.').format(value['requests_remaining']))
        elif kind == "pi_version_warning":
            self.chat.add_message("系统", "WARNING: " + value["message"], number)
        elif kind in {"tool_execution_start", "tool_execution_end", "repair_tool", "validation"}:
            if kind == "validation" and value.get("source") == "manual":
                return
            identity = value.get("toolCallId", f"event-{len(self.chat.entries)}")
            name = value.get("toolName") or value.get("name") or "validate"
            entry = self.chat.upsert_tool(number, identity, name, kind, value)
            if kind == "tool_execution_start":
                self.status.setText(tr('Calling tool: ') + name)
            if entry["failed"]:
                host = entry["events"].get("repair_tool", {}).get("result", {}).get("details", {})
                validation = entry["events"].get("validation", {})
                details = {**host, "message": host.get("message") or host.get("error") or
                           ("候选校验失败，请查看错误详情。" if name == "validate" else "工具执行失败：" + name),
                           "stage": "validation" if name == "validate" else "tool:" + name,
                           "round": number, "toolCallId": identity, "events": dict(entry["events"]),
                           "log_path": str(self.host.conversation.log.path) if self.host.conversation else None}
                if validation:
                    details["errors"] = validation.get("errors", [])
                key = (number, identity)
                if key not in self.tool_errors:
                    self.tool_errors[key] = self.diagnostics.errors.count()
                    self.diagnostics.add_error(details)
                else:
                    self.diagnostics.errors.setItemData(self.tool_errors[key], details)
                    self.diagnostics.select_error()
                self.status.setText(tr('Error: ') + details["message"] + tr('; details are available, processing continues this round.'))

    def show_diff(self):
        self.window.launch(self.host.diff, self.open_diff)

    def open_diff(self, value):
        """只在主动审阅时打开固定基线 Diff，不阻塞对话页面。"""
        dialog = QDialog(self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.setWindowTitle(tr('Cumulative Diff (fixed Candidate baseline)'))
        dialog.resize(900, 650)
        dialog.setSizeGripEnabled(True)
        layout = QVBoxLayout(dialog)
        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        text.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        text.setPlainText(value or tr('No changes'))
        layout.addWidget(text)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.close)
        layout.addWidget(buttons)
        self.diff_dialog = dialog
        dialog.show()

    def validate(self):
        def done(value):
            self.show_event({"round": self.host.conversation.log.group if self.host.conversation else 0,
                             "event": {"type": "validation", **value, "toolCallId": f"manual-{len(self.chat.entries)}"}})
            if not value.get("ok"):
                self.diagnostics.show_error()
        self.window.launch(self.host.validate, done)

    def publish(self):
        self.window.launch(self.host.publish, lambda identity: self.chat.add_message("系统", tr('Published new Manifest: ') + identity + tr('; Default is unchanged.')))

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
            control.setToolTip(tr('The current activity has not finished') if busy else "")
        self.baseline.setEnabled(not busy)
        self.cancel_button.setEnabled(self.window.service.state.get("activity") == "Agent")
