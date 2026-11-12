"""Developer GUI 的真实后台操作、截图预览、配置和连续修复页面。"""

from __future__ import annotations

import asyncio
import json
from html import escape
import sys
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import Qt, QThread, Signal, QRect, QTimer, QSize, QPoint
from PySide6.QtGui import QImage, QPainter, QPixmap, QPen, QFontDatabase
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QFileDialog, QListWidgetItem, QAbstractItemView, QSizePolicy, QStyle,
    QMessageBox, QDialog, QDialogButtonBox,
)

from qfluentwidgets import (
    BodyLabel as QLabel, PushButton as QPushButton, LineEdit as QLineEdit,
    PlainTextEdit as QPlainTextEdit, SpinBox as QSpinBox, ComboBox as QComboBox,
    CheckBox as QCheckBox, ListWidget as QListWidget, SegmentedWidget,
    TransparentToolButton, PrimaryToolButton, FluentIcon, RoundMenu, Action, TextBrowser,
    CustomStyleSheet, setStyleSheet as setFluentStyleSheet,
)

from .run_logs import LIVE_LOG_LIMIT
from .i18n import tr
from .run_log_gui import log_colors, log_time

from .repair_chat import RepairChat, chat_title, process_text_parts
from .chat_input import ChatInput
from .agent_settings import load_settings, save_settings, save_selection, settings_snapshot, settings_document, save_options
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


class FeedbackDialog(QDialog):
    """非模态人工反馈；窗口关闭只跳过，取消按钮结束发起轮次。"""

    def __init__(self, request, window):
        super().__init__(window)
        self.request = request
        self.setWindowTitle(tr('Waiting for feedback'))
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.resize(640, 420)
        layout = QVBoxLayout(self)
        content = QPlainTextEdit()
        content.setAccessibleName(tr('Agent request'))
        content.setReadOnly(True)
        content.setPlainText(request.message)
        layout.addWidget(content)
        notice = QLabel(tr('Feedback does not verify game state or approve installation. Empty confirmation is allowed.'))
        notice.setWordWrap(True)
        layout.addWidget(notice)
        self.reply = QPlainTextEdit()
        self.reply.setAccessibleName(tr('Your feedback (optional)'))
        self.reply.setPlaceholderText(tr('Your feedback (optional)'))
        layout.addWidget(self.reply)
        controls = QHBoxLayout()
        self.confirm = button(tr('Confirm'), lambda: self.respond('confirmed'), controls)
        self.skip = button(tr('Skip'), self.reject, controls)
        self.cancel = button(tr('Cancel round'), self.cancel_round, controls)
        layout.addLayout(controls)
        self.window = window
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.expire)
        self.timer.start(50)

    def respond(self, status):
        self.request.finish(status, self.reply.toPlainText())
        self.close()

    def reject(self):
        self.request.finish('skipped')
        super().reject()

    def closeEvent(self, event):
        self.request.finish('skipped')
        super().closeEvent(event)

    def cancel_round(self):
        """先请求轮次取消再作废反馈，不把取消记成 Skip。"""
        if not self.request.done.is_set():
            self.window.cancel_operation()
            self.request.close()
        self.close()

    def expire(self):
        if self.request.done.is_set():
            self.close()


def _run_log_entry(record):
    """仅投影业务日志与用户可见运行状态，不改写原始 Trace。"""
    event = record.get("event")
    if event == "component_log":
        level = record.get("level", "info").lower()
        return (level, str(record.get("message", ""))) if level in {"info", "warning", "error"} else None
    states = {
        "run_started": ("info", tr("Run started")),
        "run_paused": ("warning", tr("Run paused")),
        "paused_by_user": ("warning", tr("Run paused")),
        "run_resumed": ("info", tr("Run resumed")),
        "input_resumed": ("info", tr("Run resumed")),
        "input_resume_requested": ("info", tr("Resume requested")),
        "input_resume_rejected": ("warning", tr("Resume rejected")),
        "run_cancel_requested": ("warning", tr("Stop requested")),
        "component_failed": ("error", tr("Execution failed")),
        "execution_anomaly": ("error", tr("Execution failed")),
        "safe_task_termination": ("warning", tr("Task terminated")),
        "step_reinvocation_failed": ("error", tr("Execution failed")),
    }
    if event == "run_finished":
        result = record.get("result", {})
        if result.get("status") in {"success", "completed"} and result.get("all_tasks_succeeded", True):
            return "info", tr("Execution completed")
        reason = result.get("failure_message") or result.get("reason", "")
        return "error", tr("Execution interrupted") + (f": {reason}" if reason else "")
    if event not in states:
        return None
    level, message = states[event]
    reason = record.get("failure_message") or record.get("reason", "")
    return level, message + (f": {reason}" if reason else "")


class TrialDialog(QDialog):
    """试运行的模态日志窗口；阻止主界面操作，显示时不抢游戏焦点。"""

    def __init__(self, service, parent):
        super().__init__(parent)
        self.service = service
        self.setObjectName("running-dialog")
        setFluentStyleSheet(self, CustomStyleSheet(self).setCustomStyleSheet(
            'QDialog#running-dialog { background-color: #f3f3f3; }',
            'QDialog#running-dialog { background-color: #202020; }'))
        self.setWindowTitle(tr('Agent trial'))
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.resize(760, 480)
        layout = QVBoxLayout(self)
        self.history_notice = QLabel(tr("Showing the latest 300 entries. See Logs for earlier entries."))
        self.history_notice.setWordWrap(True)
        self.history_notice.hide()
        layout.addWidget(self.history_notice)
        self.logs = TextBrowser()
        self.logs.setOpenLinks(False)
        self.logs.setOpenExternalLinks(False)
        self.logs.anchorClicked.connect(self.show_log_details)
        self.log_records = {}
        layout.addWidget(self.logs)
        controls = QHBoxLayout()
        self.pause = button(tr('Pause'), lambda: service.resume() if service.status["paused"] else service.pause(), controls)
        controls.addWidget(QLabel(tr('Global shortcut: Ctrl Alt P')))
        self.stop = button(tr('Stop'), service.stop, controls)
        layout.addLayout(controls)
        self.sequence = 0
        self.pause_notice = QLabel()
        self.pause_notice.setWordWrap(True)
        layout.addWidget(self.pause_notice)
        self._pause_notice_shown = False

    def render(self, state):
        for record in state.get("log_records", state.get("trace", ())):
            if record["sequence"] <= self.sequence:
                continue
            self.sequence = record["sequence"]
            entry = _run_log_entry(record)
            if entry is not None:
                self.append_log(record, *entry)
        if state.get("logs_trimmed"):
            self.history_notice.show()
        self.trim_logs()
        info = state.get("pause_info")
        if info:
            instruction = tr("Resuming checks the current Step's condition.") if info["has_condition"] else tr('Resuming restarts the current Step.')
            if not info.get("restart_step", True):
                instruction = tr('Resuming continues Workflow observation and scheduling.')
            instruction = info.get("resume_description", instruction)
            self.pause_notice.setText(f"{info['reason']}\n{info['description']}\n{instruction}")
            if not self._pause_notice_shown:
                self._pause_notice_shown = True
                self.parentWidget().showNormal()
                self.parentWidget().raise_()
                self.parentWidget().activateWindow()
        else:
            self._pause_notice_shown = False
            self.pause_notice.clear()
        self.pause.setText(tr('Resume') if state["paused"] else tr('Pause'))
        self.pause.setEnabled(not state.get("resume_pending", False))

    def append_log(self, record, level, message):
        """以可选中文本显示等级色块；用户回看时不强制滚到底部。"""
        sequence = record["sequence"]
        self.log_records[sequence] = record
        bar = self.logs.verticalScrollBar()
        following = bar.value() >= bar.maximum() - 4
        position = bar.value()
        self.logs.append(self.log_html(record, level, message))
        bar.setValue(bar.maximum() if following else position)

    @staticmethod
    def log_html(record, level, message):
        """将原始日志转义为色块，详情仅由保留的本地序号索引打开。"""
        background, foreground = log_colors(level)
        sequence = record["sequence"]
        name = escape(str(record.get("logical_name") or tr("Run")))
        timestamp = escape(log_time(record.get("recorded_at")))
        body = escape(message).replace("\n", "<br>")
        return (
            f'<table width="100%" cellspacing="0" cellpadding="8" bgcolor="{background}">'
            f'<tr><td style="color:{foreground}"><b>{level.upper()} · {name}</b> · {timestamp}<br>{body}<br>'
            f'<a style="color:{foreground}" href="{sequence}">{escape(tr("View details"))}</a>'
            '</td></tr></table><br>'
        )

    def trim_logs(self):
        """按整条色块裁剪到近期窗口；保留回看项偏移，已移除项退到最早记录。"""
        if len(self.log_records) <= LIVE_LOG_LIMIT:
            return
        bar = self.logs.verticalScrollBar()
        following = bar.value() >= bar.maximum() - 4
        anchor, offset = None, 0
        document = self.logs.document()
        layout = document.documentLayout()
        for sequence, frame in zip(self.log_records, document.rootFrame().childFrames()):
            rect = layout.frameBoundingRect(frame)
            if rect.bottom() > bar.value():
                anchor, offset = sequence, bar.value() - rect.top()
                break
        self.log_records = dict(list(self.log_records.items())[-LIVE_LOG_LIMIT:])
        self.logs.setHtml("".join(self.log_html(record, *_run_log_entry(record))
                                  for record in self.log_records.values()))
        self.history_notice.show()
        document.documentLayout().documentSize()
        if following:
            bar.setValue(bar.maximum())
        elif anchor in self.log_records:
            index = list(self.log_records).index(anchor)
            frames = document.rootFrame().childFrames()
            bar.setValue(round(document.documentLayout().frameBoundingRect(frames[index]).top() + offset))
        else:
            bar.setValue(0)

    def show_log_details(self, url):
        """沿用现有详情弹窗，原始字段与异常栈仅在用户请求时显示。"""
        if not url.toString().isdecimal():
            return
        record = self.log_records.get(int(url.toString()))
        if record is None:
            return
        from .gui import ErrorDialog
        _, message = _run_log_entry(record)
        dialog = ErrorDialog(message, json.dumps(record, ensure_ascii=False, indent=2), error=False, parent=self)
        dialog.setWindowTitle(tr("View details"))
        dialog.details_button.setChecked(True)
        dialog.open()

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


class OcrView(CropView):
    """在原图展示识别框；标注不写回截图像素或影响框选。"""

    def __init__(self, *, color=Qt.GlobalColor.green, line_width=2):
        super().__init__()
        self.items = []
        self.color, self.line_width = color, line_width

    def paintEvent(self, event):
        super().paintEvent(event)
        rect = self.image_rect()
        if rect.isEmpty():
            return
        painter = QPainter(self)
        painter.setPen(QPen(self.color, self.line_width))
        sx, sy = rect.width() / self.image.width(), rect.height() / self.image.height()
        for number, item in enumerate(self.items, 1):
            box = item["box"]
            outline = QRect(rect.x() + round(box["x"] * sx), rect.y() + round(box["y"] * sy),
                            max(1, round(box["width"] * sx)), max(1, round(box["height"] * sy)))
            painter.drawRect(outline)
            label = QRect(outline.x(), max(rect.y(), outline.y() - 22), 24 + len(str(number)) * 8, 22)
            painter.fillRect(label, Qt.GlobalColor.black)
            painter.drawText(label, Qt.AlignmentFlag.AlignCenter, str(number))


class OcrPage(QWidget):
    """独立静态截图的 OCR 测试；框选结束自动替换本次结果。"""

    def __init__(self, window):
        super().__init__()
        self.window, self.host = window, window.host
        self.snapshot = None
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.capture_button = button(tr('Capture screenshot'), self.capture, controls)
        self.full_button = button(tr('Recognize full image'), lambda: self.recognize(), controls)
        layout.addLayout(controls)
        instructions = QLabel(tr('Capture to recognize all text. Drag on the image to recognize a region; results replace the previous ones. Korean is not supported.'))
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        self.view = OcrView()
        self.view.selected.connect(lambda region: self.recognize(region) if region else None)
        layout.addWidget(self.view, 3)
        self.results = QPlainTextEdit()
        self.results.setReadOnly(True)
        self.results.setAccessibleName(tr('OCR results'))
        layout.addWidget(self.results, 1)

    def clear_results(self):
        self.view.items = []
        self.view.update()
        self.results.clear()

    def capture(self):
        self.clear_results()
        def shown(snapshot):
            self.snapshot = snapshot
            self.view.set_image(snapshot[0], snapshot[1])
            self.recognize()
        self.window.launch(lambda: self.host.capture(update_preview=False), shown)

    def recognize(self, region=None):
        """松开框选后才启动后台识别；出错保留原图但不保留旧结果。"""
        if self.snapshot is None:
            return
        self.clear_results()
        self.view.region = dict(region) if region else None
        snapshot = self.snapshot
        def shown(result):
            self.view.items = result["items"]
            self.view.update()
            self.results.setPlainText("\n".join(f'{number}. {item["text"]}'
                for number, item in enumerate(result["items"], 1)) or tr('No text recognized.'))
        self.window.launch(lambda: self.host.recognize_preview(snapshot, region), shown)

    def render(self, busy):
        self.capture_button.setEnabled(not busy)
        self.full_button.setEnabled(not busy and self.snapshot is not None)
        self.view.setEnabled(not busy)


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
            def shown(result):
                content, matches = result
                self.show_save_preview(name, tags, region, snapshot, content, matches)
            self.window.launch(lambda: self.host.match_crop_preview(snapshot, region), shown)
        self.window._interact(preview)

    def show_save_preview(self, name, tags, region, snapshot, content, matches):
        """编号展示同图匹配；仅确认后保存固定原始像素，覆盖层不进入模板。"""
        dialog = QDialog(self)
        dialog.setWindowTitle(tr('Confirm Asset save'))
        body = QVBoxLayout(dialog)
        body.addWidget(QLabel(tr('{0}\nTags: {1}\nOriginal pixel region: {2}').format(name, json.dumps(tags, ensure_ascii=False), region)))
        label = QLabel()
        label.setPixmap(QPixmap.fromImage(QImage.fromData(content)).scaled(640, 200, Qt.AspectRatioMode.KeepAspectRatio))
        body.addWidget(label)
        view = OcrView(color=Qt.GlobalColor.red, line_width=1)
        view.set_image(snapshot[0], snapshot[1])
        view.items = [{"box": match} for match in matches]
        view.setEnabled(False)
        body.addWidget(view, 3)
        results = QPlainTextEdit()
        results.setReadOnly(True)
        results.setAccessibleName(tr('Template match scores (threshold: 0.8)'))
        results.setPlainText(tr('Template match scores (threshold: 0.8)') + "\n" + (
            "\n".join(f'{number}. {match["score"]!r}' for number, match in enumerate(matches, 1))
            or tr('No matches.')))
        body.addWidget(results, 1)
        dialog.resize(900, 720)
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        controls.accepted.connect(dialog.accept)
        controls.rejected.connect(dialog.reject)
        body.addWidget(controls)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.window.launch(lambda: self.host.save_crop(name, region, tags, preview=snapshot),
                               lambda value: self.region_label.setText(tr('Saved: {0}').format(value['image_path'])))

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
        button(tr('Open Agent log directory'), self.open_logs, row)
        button(tr('Open LALC log directory'), lambda: self.open_directory(window.service.data_root / "logs"), row)
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
        self.global_controls = {}
        option_labels = ({"history_enabled": tr('Allow searching Agent history'),
                          "knowledge_enabled": tr('Allow querying external knowledge')} if side == "developer" else {
            "automatic_repair_default": tr('Automatically use the repaired version after normal completion'),
            "runtime_feedback_enabled": tr('Allow requesting human feedback'),
        })
        for name, label in option_labels.items():
            control = QCheckBox(label)
            self.global_controls[name] = control
            layout.addWidget(control)
            control.toggled.connect(lambda value, name=name: self.change_option(name, value))
        if side == "user":
            layout.addWidget(QLabel(tr('Maximum consecutive recoveries')))
            control = QSpinBox()
            control.setRange(1, 2147483647)
            self.global_controls["recovery_limit"] = control
            layout.addWidget(control)
            control.valueChanged.connect(lambda value: self.change_option("recovery_limit", value))
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
        for label, control in ((tr('Base URL'), self.url), (tr('Model'), self.model)):
            layout.addWidget(QLabel(label))
            layout.addWidget(control)
        self.secret_state = QLabel()
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
        advanced.addWidget(QLabel(tr('Maximum model requests per recovery') if side == "user"
                                 else tr('Maximum model requests per message')))
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
        for control in (self.url, self.model):
            control.textChanged.connect(self.invalidate)
        self.provider.currentIndexChanged.connect(self.switch_provider)
        self.limit.valueChanged.connect(self.invalidate)
        self.window._interact(self.reload)
        for control in (self.url, self.model):
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
        if self.key is not None:
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
            document = settings_document(self.host.service.data_root)
            for name, control in self.global_controls.items():
                if isinstance(control, QCheckBox):
                    control.setChecked(document[name])
                else:
                    control.setValue(document[name])
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

    def change_option(self, name, value):
        """保存独立开关，不触发模型请求或覆盖 provider 表单。"""
        if not self.loading:
            self.window._interact(lambda: save_options(self.host.service.data_root, **{name: value}))

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


class SessionHistory(QListWidget):
    """复用一个悬停菜单按钮；右键或键盘菜单键也可管理当前会话。"""

    menuRequested = Signal(str, QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.menu_identity = None
        self.menu_button = TransparentToolButton(FluentIcon.MORE, self.viewport())
        self.menu_button.setFixedSize(28, 28)
        self.menu_button.setToolTip(tr('Session settings'))
        self.menu_button.setAccessibleName(tr('Session settings'))
        self.menu_button.hide()
        style = 'SessionHistory::item { padding-right: 36px; }'
        CustomStyleSheet(self).setCustomStyleSheet(style, style)
        self.menu_button.clicked.connect(lambda: self.menuRequested.emit(
            self.menu_identity, self.menu_button.mapToGlobal(self.menu_button.rect().bottomLeft())))
        self.verticalScrollBar().valueChanged.connect(lambda *_: self.menu_button.hide())

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        item = self.itemAt(event.position().toPoint())
        if item is None:
            self.menu_button.hide()
            return
        self.menu_identity = item.data(Qt.ItemDataRole.UserRole)
        rect = self.visualItemRect(item)
        self.menu_button.move(rect.right() - 32, rect.center().y() - 14)
        self.menu_button.show()
        self.menu_button.raise_()

    def leaveEvent(self, event):
        self.menu_button.hide()
        super().leaveEvent(event)

    def contextMenuEvent(self, event):
        item = self.itemAt(event.pos()) if event.reason() != event.Reason.Keyboard else self.currentItem()
        if item is not None:
            self.menuRequested.emit(item.data(Qt.ItemDataRole.UserRole),
                                    self.viewport().mapToGlobal(self.visualItemRect(item).center()))
        event.accept()

    def clear(self):
        self.menu_button.hide()
        self.menu_identity = None
        super().clear()


class RepairPage(QWidget):
    """统一 Session 工作台；未发送的准备状态不创建或重建 Candidate。"""

    def __init__(self, window):
        super().__init__()
        self.window, self.host = window, window.host
        self.session = None
        self.history_reader = None
        self.history_rounds = []
        self.images, self.manifest_references = [], []
        self.tool_errors, self.titles = {}, {}
        self.session_menu = self.rename_dialog = None
        self._round_running = False
        self._page_preview_requests = []
        self._auto_collapsed = False
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(16)
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(260)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        row.addWidget(QLabel(tr('Sessions')))
        row.addStretch()
        self.refresh_button = TransparentToolButton(FluentIcon.SYNC, self)
        self.refresh_button.setToolTip(tr('Refresh Sessions'))
        self.refresh_button.setAccessibleName(tr('Refresh Sessions'))
        self.refresh_button.clicked.connect(self.refresh_sessions)
        row.addWidget(self.refresh_button)
        side.addLayout(row)
        self.new_button = button(tr('New Chat'), self.new, side)
        self.history = SessionHistory()
        self.history.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.history.itemClicked.connect(self.open_session)
        self.history.menuRequested.connect(self.open_session_menu)
        side.addWidget(self.history, 1)
        layout.addWidget(self.sidebar)
        main = QWidget()
        main.setMinimumWidth(0)
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        self.history_button = TransparentToolButton(FluentIcon.MENU, self)
        self.history_button.setAccessibleName(tr('Toggle chat history'))
        self.history_button.setToolTip(tr('Toggle chat history'))
        self.history_button.clicked.connect(self.toggle_history)
        top.addWidget(self.history_button)
        top.addStretch()
        self.mode = SegmentedWidget(self)
        self.mode.setFixedWidth(240)
        self.mode.addItem('Construct', 'Construct', icon=FluentIcon.CODE)
        self.mode.addItem('Repair', 'Repair', icon=FluentIcon.DEVELOPER_TOOLS)
        self.mode.setCurrentItem('Repair')
        top.addWidget(self.mode)
        top.addStretch()
        self.context_button = TransparentToolButton(FluentIcon.SETTING, self)
        self.context_button.setAccessibleName(tr('Chat context'))
        self.context_button.setToolTip(tr('Chat context'))
        self.context_button.clicked.connect(lambda: self.source_panel.setVisible(self.source_panel.isHidden()))
        self.source_label = QLabel()
        self.source_label.setMaximumWidth(300)
        top.addWidget(self.source_label)
        top.addWidget(self.context_button)
        main_layout.addLayout(top)
        centered = QHBoxLayout()
        centered.setContentsMargins(0, 0, 0, 0)
        centered.addStretch(1)
        self.column = QWidget()
        self.column.setMinimumWidth(0)
        self.column.setMaximumWidth(920)
        self.column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        body = QVBoxLayout(self.column)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(10)
        centered.addWidget(self.column, 100)
        centered.addStretch(1)
        main_layout.addLayout(centered, 1)
        layout.addWidget(main, 1)
        title_row = QHBoxLayout()
        self.identity = QLabel(tr('New Chat'))
        self.identity.setTextFormat(Qt.TextFormat.PlainText)
        self.identity.setMinimumWidth(0)
        self.identity.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        title_row.addWidget(self.identity, 1)
        self.mode_badge = QLabel()
        title_row.addWidget(self.mode_badge)
        body.addLayout(title_row)
        self.session_uuid = QLabel()
        self.session_uuid.setTextFormat(Qt.TextFormat.PlainText)
        self.session_uuid.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.session_uuid.hide()
        body.addWidget(self.session_uuid)
        self.source_panel = QWidget()
        source_layout = QHBoxLayout(self.source_panel)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.addWidget(QLabel(tr('Source Manifest')))
        self.baseline = QComboBox()
        self.baseline.setMinimumWidth(0)
        self.baseline.currentIndexChanged.connect(self.update_source_label)
        source_layout.addWidget(self.baseline, 1)
        body.addWidget(self.source_panel)
        self.source_panel.hide()
        self.diagnostics = DiagnosticPanel(window, self.host.service.data_root / 'developer-sessions')
        self.diagnostics.setParent(self)
        self.diagnostics.hide()
        self.chat = RepairChat()
        self.chat.olderRequested.connect(self.load_older_history)
        self.chat.setMinimumSize(0, 80)
        self.chat.setStyleSheet('QTextBrowser { border: none; background: transparent; }')
        body.addWidget(self.chat, 1)
        self.raw_timer = QTimer(self)
        self.raw_timer.setSingleShot(True)
        self.raw_timer.setInterval(50)
        self.raw_timer.timeout.connect(self.flush_raw_output)
        self.raw_pending = ''
        self.clear_raw_output()
        self.status = QLabel(self)
        self.status.setMinimumWidth(0)
        self.status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.hide()
        self.composer = QWidget()
        self.composer.setObjectName('chatComposer')
        self.composer.setStyleSheet('#chatComposer { background: rgba(128,128,128,0.07); border: 1px solid rgba(128,128,128,0.25); border-radius: 18px; }')
        composer_layout = QVBoxLayout(self.composer)
        composer_layout.setContentsMargins(12, 8, 12, 10)
        composer_layout.setSpacing(4)
        self.message = ChatInput()
        self.message.setPlaceholderText(tr('Message the Agent…'))
        self.message.setStyleSheet('QPlainTextEdit { border: none; background: transparent; }')
        self.message.sendRequested.connect(self.send)
        composer_layout.addWidget(self.message)
        self.attachment_notice = QLabel()
        self.attachment_notice.setWordWrap(True)
        self.attachment_notice.hide()
        composer_layout.addWidget(self.attachment_notice)
        row = QHBoxLayout()
        self.attach = TransparentToolButton(FluentIcon.ADD, self)
        self.attach.setAccessibleName(tr('Attachments'))
        self.attach.setToolTip(tr('Attachments'))
        self.attach.clicked.connect(self.open_attachment_menu)
        row.addWidget(self.attach)
        row.addStretch()
        self.more_button = TransparentToolButton(FluentIcon.MORE, self)
        self.more_button.setAccessibleName(tr('More developer tools'))
        self.more_button.setToolTip(tr('More developer tools'))
        self.more_button.clicked.connect(self.open_more_menu)
        row.addWidget(self.more_button)
        self.send_button = PrimaryToolButton(FluentIcon.UP, self)
        self.send_button.setFixedSize(36, 36)
        self.send_button.clicked.connect(self.send_or_cancel)
        row.addWidget(self.send_button)
        composer_layout.addLayout(row)
        body.addWidget(self.composer)
        self.request_progress = QLabel(self)
        self.request_progress.hide()
        self.build_menus()
        self.mode.currentItemChanged.connect(self.update_source)
        self.message.textChanged.connect(lambda: self.update_actions(self.is_busy()))
        self.diagnostics.errors.currentIndexChanged.connect(lambda: self.update_actions(self.is_busy()))
        self.refresh_sessions()
        self.set_manifests(self.host.manager.list_manifests())
        self.show_empty_chat()

    def set_status(self, text, tooltip=None):
        """保留状态读取接口，将可见状态统一呈现在当前轮回复顶部。"""
        self.status.setText(text)
        self.status.setToolTip(text if tooltip is None else tooltip)
        number = self.host.conversation.log.group if self.host.conversation else 0
        self.chat.set_activity(text, number, self.status.toolTip())

    def clear_raw_output(self):
        """只丢弃尚未完成的流式缓冲，完整生成过程随回复保留。"""
        self.raw_timer.stop()
        self.raw_pending = ''
        activity = self.chat.activity()
        changed = bool(activity['pending'])
        activity['pending'] = ''
        if not activity['timeline']:
            activity['expanded'] = False
        if changed:
            self.chat.render()

    def flush_raw_output(self):
        """展开时合并绘制，滚动规则沿用聊天记录。"""
        if self.chat.activity()['expanded']:
            self.chat.render()

    def update_raw_output(self, content, number=None):
        """流式内容属于当前轮折叠区，完整消息到达时替换为保留记录。"""
        if number is not None:
            self.chat.activity_round = number
        text = '\n\n'.join(process_text_parts(content))
        if not text or text == self.raw_pending:
            return
        first = not self.raw_pending
        self.raw_pending = text
        activity = self.chat.activity()
        activity['pending'] = text
        if first:
            self.chat.render()
        elif activity['expanded'] and not self.raw_timer.isActive():
            self.raw_timer.start()

    def is_busy(self):
        state = self.window.service.status
        return bool(self.window.jobs) or bool(state.get('activity')) or state['phase'] == 'running' or self.window.closing

    def build_menus(self):
        """菜单只改变入口位置；所有操作继续走原宿主校验和活动边界。"""
        self.attachment_menu = RoundMenu(parent=self)
        self.image_action = Action(tr('Attach images'), self)
        self.image_action.triggered.connect(self.attach_image)
        self.reference_action = Action(tr('Attach Manifests'), self)
        self.reference_action.triggered.connect(self.attach_manifests)
        self.clear_action = Action(tr('Clear attachments'), self)
        self.clear_action.triggered.connect(self.clear_image)
        self.attachment_menu.addActions([self.image_action, self.reference_action, self.clear_action])
        self.more_menu = RoundMenu(parent=self)
        workspace = RoundMenu(tr('Workspace and pages'), self)
        logs = RoundMenu(tr('Logs and diagnostics'), self)
        self.logs_menu = logs
        development = RoundMenu(tr('Development and validation'), self)
        self.more_menu.addMenu(workspace)
        self.more_menu.addMenu(logs)
        self.more_menu.addMenu(development)
        self.workspace_action = Action(tr('Open Agent workspace'), self)
        self.workspace_action.triggered.connect(self.open_workspace)
        self.page_drafts_action = Action(tr('Open Session page drafts'), self)
        self.page_drafts_action.triggered.connect(self.open_page_drafts)
        self.pages_action = Action(tr('Open external settings page directory'), self)
        self.pages_action.triggered.connect(self.open_pages)
        self.knowledge_action = Action(tr('Open external knowledge directory'), self)
        self.knowledge_action.triggered.connect(self.open_knowledge)
        self.skills_action = Action(tr('Open Skills directory'), self)
        self.skills_action.triggered.connect(self.open_skills)
        workspace.addActions([self.workspace_action, self.page_drafts_action, self.pages_action, self.knowledge_action, self.skills_action])
        self.logs_action = Action(tr('Open Agent log directory'), self)
        self.logs_action.triggered.connect(self.diagnostics.open_logs)
        self.app_logs_action = Action(tr('Open LALC log directory'), self)
        self.app_logs_action.triggered.connect(lambda: self.diagnostics.open_directory(self.window.service.data_root / 'logs'))
        logs.addActions([self.logs_action, self.app_logs_action])
        self.error_menu = RoundMenu(tr('View error details'), self)
        self.error_actions = []
        self.error_action = Action(tr('View error details'), self)
        self.error_action.setEnabled(False)
        logs.addAction(self.error_action)
        self.copy_action = Action(tr('Copy details'), self)
        self.copy_action.triggered.connect(self.diagnostics.copy_error)
        logs.addAction(self.copy_action)
        self.diff_action = Action(tr('View cumulative Diff'), self)
        self.diff_action.triggered.connect(self.show_diff)
        self.validate_action = Action(tr('Validate'), self)
        self.validate_action.triggered.connect(self.validate)
        self.publish_action = Action(tr('Publish'), self)
        self.publish_action.triggered.connect(self.publish)
        development.addActions([self.diff_action, self.validate_action, self.publish_action])

    def open_attachment_menu(self):
        self.update_actions(self.is_busy())
        self.attachment_menu.exec(self.attach.mapToGlobal(self.attach.rect().topLeft()))

    def open_more_menu(self):
        self.logs_menu.removeMenu(self.error_menu)
        self.logs_menu.removeAction(self.error_action)
        self.error_menu.clear()
        for action in self.error_actions:
            action.deleteLater()
        self.error_actions.clear()
        for index in range(self.diagnostics.errors.count()):
            action = Action(self.diagnostics.errors.itemText(index), self.error_menu)
            self.error_actions.append(action)
            action.triggered.connect(lambda checked=False, index=index: self.show_saved_error(index))
            self.error_menu.addAction(action)
        if self.error_actions:
            self.logs_menu.addMenu(self.error_menu)
        else:
            self.logs_menu.addAction(self.error_action)
        self.update_actions(self.is_busy())
        self.more_menu.exec(self.more_button.mapToGlobal(self.more_button.rect().topLeft()))

    def show_saved_error(self, index):
        self.diagnostics.errors.setCurrentIndex(index)
        self.diagnostics.show_error()

    def update_actions(self, busy):
        has_candidate = self.session is not None and self.host.candidate.is_dir()
        self.page_drafts_action.setEnabled(has_candidate and self.session.mode == 'Construct' and not busy)
        for action in (self.workspace_action, self.diff_action, self.validate_action, self.publish_action):
            action.setEnabled(has_candidate and not busy)
        self.pages_action.setEnabled(not busy)
        self.knowledge_action.setEnabled(not busy)
        self.logs_action.setEnabled(self.diagnostics.path.is_dir())
        self.app_logs_action.setEnabled((self.window.service.data_root / 'logs').is_dir())
        self.copy_action.setEnabled(self.diagnostics.errors.currentData() is not None)
        self.error_menu.menuAction().setEnabled(bool(self.diagnostics.errors.count()))
        for action in (self.image_action, self.reference_action):
            action.setEnabled(not busy)
        self.clear_action.setEnabled(not busy and bool(self.images or self.manifest_references))
        running = self._round_running and bool(self.window.jobs)
        cancelling = running and any(job.cancel_requested for job in self.window.jobs)
        if cancelling:
            self.clear_raw_output()
            self.set_status(tr('Cancelling…'))
            self.status.setToolTip(self.status.text())
        if running:
            self.send_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
            title = tr('Cancelling…') if cancelling else tr('Cancel round')
            self.send_button.setEnabled(not cancelling)
        else:
            self.send_button.setIcon(FluentIcon.UP)
            title = tr('Send')
            self.send_button.setEnabled(not busy and bool(self.message.toPlainText().strip()))
        self.send_button.setAccessibleName(title)
        self.send_button.setToolTip(title + ('\n' + self.request_progress.text() if self.request_progress.text() else ''))

    def send_or_cancel(self):
        if self._round_running and self.window.jobs:
            if not any(job.cancel_requested for job in self.window.jobs):
                self.window.cancel_operation()
        else:
            self.send()

    def toggle_history(self):
        self._auto_collapsed = False
        self.sidebar.setVisible(self.sidebar.isHidden())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.width() < 700 and not self.sidebar.isHidden():
            self.sidebar.hide()
            self._auto_collapsed = True
        elif self.width() >= 700 and self._auto_collapsed:
            self.sidebar.show()
            self._auto_collapsed = False

    def show_empty_chat(self):
        self.chat.setHtml('<p style="color:#808080;text-align:center">' + tr('Start a new chat. Choose a mode and set the source in Chat context.') + '</p>')

    def update_attachment_notice(self):
        attached = bool(self.images or self.manifest_references)
        self.attachment_notice.setVisible(attached)
        self.attachment_notice.setText(tr('{0} images · {1} Manifest references').format(len(self.images), len(self.manifest_references)))
        details = '\n'.join([*(str(path) for path in self.images), *self.manifest_references])
        self.attach.setToolTip(details or tr('Attachments'))
        self.attachment_notice.setToolTip(details)

    def update_source_label(self):
        """已有 Session 显示固定来源；新对话显示当前选择。"""
        if self.session is not None:
            source = json.loads((self.session.path / 'session.json').read_text())['source_manifest_id']
        else:
            source = self.baseline.currentData()
        text = tr('Based on Manifest: {0}').format(source or tr('None'))
        self.source_label.setText(text)
        self.source_label.setToolTip(text)

    def update_source(self):
        self.update_source_label()
        self.baseline.setItemText(0, tr('Blank (Construct only)') if self.mode.currentRouteKey() == 'Construct'
                                  else tr('Select a published Manifest'))

    def set_manifests(self, values):
        previous = self.baseline.currentData()
        self.baseline.clear()
        self.baseline.addItem(tr('Select a published Manifest'), userData=None)
        for value in values:
            self.baseline.addItem(value['manifest_id'], userData=value['manifest_id'])
        index = self.baseline.findData(previous)
        if previous is not None and index < 0:
            self.baseline.addItem(previous, userData=previous)
            index = self.baseline.count() - 1
        self.baseline.setCurrentIndex(max(0, index))
        self.update_source()

    def saved_title(self, path):
        """复用只读标题解析；忙会话由列表刷新使用已有缓存。"""
        from .developer_session import saved_session_title
        return saved_session_title(path, self.titles)

    def open_session_menu(self, identity, position):
        """菜单开启和执行都检查忙状态，避免对话框期间活动变化绕过门槛。"""
        if self.is_busy():
            return
        if self.session_menu is not None:
            self.session_menu.close()
            self.session_menu.deleteLater()
        menu = RoundMenu(parent=self)
        rename = Action(tr('Rename'), menu)
        remove = Action(tr('Delete'), menu)
        rename.triggered.connect(lambda: self.window._interact(lambda: self.rename_session(identity)))
        remove.triggered.connect(lambda: self.window._interact(lambda: self.delete_session(identity)))
        menu.addAction(rename)
        menu.addAction(remove)
        self.session_menu = menu
        menu.exec(position)

    def rename_session(self, identity):
        """名称只进入会话展示元数据，保存成功后才更新界面。"""
        if self.is_busy():
            return
        from .developer_session import DeveloperSession
        session = DeveloperSession(self.window.service, identity, entry='gui')
        title, _ = self.saved_title(session.path)
        dialog = QDialog(self)
        dialog.setWindowTitle(tr('Rename Session'))
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        layout = QVBoxLayout(dialog)
        editor = QLineEdit(dialog)
        metadata = json.loads((session.path / 'session.json').read_text(encoding='utf-8'))
        editor.setText(metadata.get('title', title))
        editor.setAccessibleName(tr('Session title'))
        layout.addWidget(editor)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        save = buttons.button(QDialogButtonBox.StandardButton.Save)
        save.setEnabled(bool(editor.text().strip()))
        editor.textChanged.connect(lambda text: save.setEnabled(bool(text.strip()) and not self.is_busy()))
        layout.addWidget(buttons)
        def confirm():
            if self.is_busy():
                return
            title = editor.text()
            def renamed(_):
                if self.rename_dialog is dialog:
                    dialog.accept()
                self.titles.pop(identity, None)
                self.refresh_sessions()
            self.window.launch(lambda: session.rename(title), renamed)
        buttons.accepted.connect(confirm)
        buttons.rejected.connect(dialog.reject)
        self.rename_dialog = dialog
        dialog.finished.connect(lambda *_: setattr(self, 'rename_dialog', None))
        dialog.open()
        editor.selectAll()
        editor.setFocus()

    def delete_session(self, identity):
        """确认后后台删除私有数据，当前会话删除完成才回到空白准备状态。"""
        if self.is_busy():
            return
        answer = QMessageBox.warning(self, tr('Delete Session'),
            tr('Delete this Session and its conversation, attachments and unpublished drafts? This cannot be undone.'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
        if answer != QMessageBox.StandardButton.Yes or self.is_busy():
            return
        from .developer_session import DeveloperSession
        session = DeveloperSession(self.window.service, identity, entry='gui')
        def done(remaining):
            self.titles.pop(identity, None)
            if self.session is not None and self.session.identity == identity:
                self.new()
            else:
                self.refresh_sessions()
            if remaining is not None:
                QMessageBox.warning(self, tr('Delete Session'),
                    tr('Session removed, but some files could not be deleted: {0}').format(remaining))
        self.window.launch(session.delete, done)

    def refresh_sessions(self):
        """列表只读取不可变身份；打开时在锁内校验并恢复全部状态。"""
        root = self.window.service.data_root / 'developer-sessions'
        self.history.clear()
        if root.is_symlink():
            self.set_status(tr('Invalid Session directory'))
            return
        if root.exists():
            paths = (path for path in root.iterdir() if not path.name.startswith('.'))
            for path in sorted(paths, key=lambda item: item.lstat().st_mtime, reverse=True):
                try:
                    if path.is_symlink() or (path / 'session.json').is_symlink():
                        raise ValueError('Session symlink')
                    value = json.loads((path / 'session.json').read_text())
                    if value['mode'] not in {'Construct', 'Repair'}:
                        raise ValueError('Invalid Session mode')
                    try:
                        title, full = self.saved_title(path)
                    except OSError:
                        title, full = self.titles.get(path.name, (tr('Chat in use'), ''))
                    mode_label = '🛠 Construct' if value['mode'] == 'Construct' else '🔧 Repair'
                    label = f"{title or tr('New Chat')}\n{mode_label}"
                except (ValueError, OSError, KeyError, TypeError):
                    label = tr('Unavailable Session')
                    full = ''
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, path.name)
                item.setToolTip((full + '\n' if full else '') + path.name)
                item.setSizeHint(QSize(240, 66))
                self.history.addItem(item)
                if self.session and self.session.identity == path.name:
                    self.history.setCurrentItem(item)
        if self.session:
            title, full = self.titles.get(self.session.identity, ('', ''))
            self.session_uuid.setText(self.session.identity)
            self.session_uuid.show()
            self.identity.setText(title or tr('New Chat'))
            self.identity.setToolTip((full + '\n' if full else '') + self.session.identity)
        if hasattr(self, 'baseline'):
            self.set_manifests(self.window.host.manager.list_manifests())

    def new(self):
        if self.window.jobs or self.window.service.status.get('activity') or self.window.service.status['phase'] == 'running':
            return
        self.clear_raw_output()
        self.session = None
        self.history_reader = None
        self.history_rounds = []
        self.host = self.window.host
        self.chat.clear()
        self.tool_errors.clear()
        self.diagnostics.errors.clear()
        self.message.clear()
        self.clear_image()
        self.identity.setText(tr('New Chat'))
        self.identity.setToolTip('')
        self.session_uuid.clear()
        self.session_uuid.hide()
        self.source_panel.hide()
        self.show_empty_chat()
        self.request_progress.setText(tr('Conversation round: not started; model requests this round: 0'))
        self.set_status('')
        self.status.setToolTip('')
        self.refresh_sessions()
        self.baseline.setCurrentIndex(0)
        self.render(False)

    def open_session(self, item):
        if self.window.jobs or self.window.service.status.get('activity') or self.window.service.status['phase'] == 'running':
            return
        from .developer_session import DeveloperSession
        identity = item.data(Qt.ItemDataRole.UserRole)
        def operation():
            session = DeveloperSession(self.window.service, identity, entry='gui')
            session.host.secrets = self.window.host.secrets
            session.conversation(load_history=False)
            from .agent_log import RoundEventReader
            reader = RoundEventReader(session.host.conversation.log.root / 'events.jsonl')
            reader.refresh()
            rows = reader.read(max(reader.rounds)) if reader.rounds else []
            return session, reader, rows
        self.window.launch(operation, lambda value: self.activate_session(
            value[0], history_reader=value[1], history_rows=value[2]))

    def activate_session(self, session, *, restore_history=True, history_reader=None, history_rows=None):
        self.clear_raw_output()
        self.session, self.host = session, session.host
        self.history_reader = history_reader
        self.history_rounds = []
        self.mode.setCurrentItem(session.mode)
        metadata = json.loads((session.path / 'session.json').read_text())
        self.set_manifests(self.host.manager.list_manifests())
        self.baseline.setCurrentIndex(max(0, self.baseline.findData(metadata['source_manifest_id'])))
        self.identity.setToolTip(session.identity)
        self.mode_badge.setText(('🛠 Construct' if session.mode == 'Construct' else '🔧 Repair'))
        self.diagnostics.set_path(self.host.conversation.log.path)
        if restore_history:
            self.reload_history(history_rows)
        self.refresh_sessions()
        self.render(bool(self.window.jobs))

    def reload_history(self, rows=None):
        """优先呈现最新完整轮次；旧轮次上滚时读取，不重复恢复模型历史。"""
        if self.session is None:
            return
        self.clear_raw_output()
        from .agent_log import RoundEventReader, read_json
        with self.host.candidate_lock():
            events_path = self.host.conversation.log.root / 'events.jsonl'
            if self.history_reader is None:
                self.history_reader = RoundEventReader(events_path)
            if rows is None:
                self.history_reader.refresh()
            self.history_rounds = sorted(self.history_reader.rounds)
            latest = self.history_rounds.pop() if self.history_rounds else None
            if rows is None:
                rows = self.history_reader.read(latest) if latest is not None else []
            number = self.host.conversation.log.group
            result_path = events_path.parent / f'round-{number}/result.json'
            result = read_json(result_path) if result_path.exists() else None
            if result is not None:
                result.setdefault('requests', self.host.conversation.log.requests)
        self.chat.batch_render = True
        self.chat.clear()
        self.tool_errors.clear()
        self.diagnostics.errors.clear()
        self.replay_history(rows)
        self.chat.render()
        self.chat.verticalScrollBar().setValue(self.chat.verticalScrollBar().maximum())
        self.request_progress.setText(tr('Conversation round: {0}; model requests this round: {1}/{2}').format(
            self.host.conversation.log.group, self.host.conversation.log.requests,
            load_settings(self.host.service.data_root)['max_requests']))
        if not self.window.jobs and not self.window.closing:
            if result is not None:
                self.show_result_status(result)
            else:
                self.set_status('')
                self.status.setToolTip('')
        self.refresh_sessions()

    def load_older_history(self):
        """补载上一轮并补偿新增高度，保持原来正在阅读的内容位置。"""
        if not self.history_rounds or self.chat.batch_render or self.window.jobs:
            return
        number = self.history_rounds[-1]
        def operation():
            with self.host.candidate_lock():
                return self.history_reader.read(number)
        def loaded(rows):
            self.history_rounds.pop()
            bar = self.chat.verticalScrollBar()
            cursor = self.chat.cursorForPosition(QPoint(0, 0))
            position = cursor.position()
            top = self.chat.cursorRect(cursor).top()
            characters = self.chat.document().characterCount()
            count = len(self.chat.entries)
            self.replay_history(rows)
            self.chat.entries[:] = self.chat.entries[count:] + self.chat.entries[:count]
            self.chat.render(follow=False)
            cursor.setPosition(position + self.chat.document().characterCount() - characters)
            bar.setValue(bar.value() + self.chat.cursorRect(cursor).top() - top)
        self.window.launch(operation, loaded)

    def replay_history(self, rows):
        """批量合并持久事件，工具关联与原始输出沿用实时呈现逻辑。"""
        from .agent_repair import final_answer, FORMAT_RETRY_PREFIX
        from .agent_prompts import user_message_text
        activity_round = self.chat.activity_round
        self._replaying = True
        self.chat.batch_render = True
        try:
            for row in rows:
                value, number = row['event'], row.get('round', 0)
                kind = value.get('type')
                if kind == 'session_message':
                    text = '\n'.join(part.get('text', '') for part in value['message'].get('content', []) if part.get('type') == 'text')
                    if not text.startswith(('开发者执行完整校验：', '开发者已 Publish 完整草稿', FORMAT_RETRY_PREFIX)):
                        self.chat.add_message('你', user_message_text(text), number)
                elif kind == 'message_end' and value.get('message', {}).get('role') == 'assistant':
                    self.chat.remember_message(number, value['message'].get('content', []))
                    try:
                        text = final_answer(value['message'])['message']
                    except ValueError:
                        text = ''
                    if text:
                        self.chat.add_message('Agent', text, number)
                elif kind == 'manual_publish':
                    self.chat.add_message('系统', tr('Published new Manifest: ') + value['manifest_id'] + tr('; Default is unchanged.'), number)
                elif kind in {'repair_error', 'gui_error'}:
                    self.diagnostics.add_error(value)
                elif kind == 'round_interrupted':
                    self.chat.add_message('系统', tr('Interrupted; results may be unknown. No operations replayed.'), number)
                else:
                    self.show_event(row)
        finally:
            self._replaying = False
            self.chat.batch_render = False
            self.chat.activity_round = activity_round

    def open_pages(self):
        """打开正式页面目录，不把页面加入 Candidate 或自动重载。"""
        def operation():
            path = self.host.service.data_root / 'pages'
            path.mkdir(parents=True, exist_ok=True)
            open_directory(self.window, path)
        self.window._interact(operation)

    def open_skills(self):
        """打开持久化 Skill 源目录；首次初始化沿用默认内容和路径校验。"""
        from .agent_skills import initialize_skills
        def operation():
            path = initialize_skills(self.window.service.data_root)
            open_directory(self.window, path)
        self.window._interact(operation)

    def open_knowledge(self):
        """固定资料目录缺失时创建空目录，不要求先初始化开发会话。"""
        from .knowledge import knowledge_root
        def operation():
            path = knowledge_root(self.window.service.data_root, create=True)
            open_directory(self.window, path)
        self.window._interact(operation)

    def open_workspace(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        def operation():
            if self.session is None or not self.host.candidate.is_dir():
                raise ValueError('请先发送首条消息初始化 Candidate。')
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.host.candidate))):
                raise ValueError(f'无法打开 Agent 工作区：{self.host.candidate}')
        self.window._interact(operation)

    def attach_image(self):
        names, _ = QFileDialog.getOpenFileNames(self, tr('Choose images (multiple selection allowed)'), '', tr('All files (*)'))
        if names:
            self.images.extend(Path(name) for name in names)
            self.update_attachment_notice()

    def attach_manifests(self):
        def action():
            from .manifest_reference import ManifestReference
            values = ManifestReference(self.window.host.manager).list(limit=200)
            dialog = QDialog(self)
            dialog.setWindowTitle(tr('Attach Manifests'))
            dialog.resize(560, 420)
            layout = QVBoxLayout(dialog)
            choices = QListWidget()
            choices.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
            layout.addWidget(choices)
            offset = 0
            while True:
                for value in values['items']:
                    item = QListWidgetItem(value['manifest_id'])
                    choices.addItem(item)
                    item.setSelected(value['manifest_id'] in self.manifest_references)
                if values['next_offset'] is None:
                    break
                offset = values['next_offset']
                values = ManifestReference(self.window.host.manager).list(offset=offset, limit=200)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.manifest_references = [item.text() for item in choices.selectedItems()]
                self.update_attachment_notice()
        self.window._interact(action)

    def clear_image(self):
        self.images, self.manifest_references = [], []
        self.update_attachment_notice()

    def send(self):
        """冻结本次输入；创建与执行在同一后台作业，禁止中途切换 Session。"""
        def action():
            if self.window.jobs:
                return
            from .developer_session import DeveloperSession
            message = self.message.toPlainText().strip()
            if not message:
                raise ValueError('消息不能为空。')
            session = self.session
            mode, source = self.mode.currentRouteKey(), self.baseline.currentData()
            images, references = list(self.images), list(self.manifest_references)
            if session is None and mode == 'Repair' and source is None:
                self.source_panel.show()
                self.baseline.setFocus()
                raise ValueError(tr('Repair requires a published source Manifest.'))
            def operation():
                current = session or DeveloperSession.create(self.window.service, source, mode=mode, entry='gui')
                current.host.secrets = self.window.host.secrets
                conversation = current.host.conversation or current.conversation()
                self.window.operation_event.emit({'event': {'type': 'workbench_session', 'session': current,
                    'message': message, 'round': conversation.log.group + 1}})
                return conversation.run(message, SimpleNamespace(pi='pi', ask_api_key=False), images=images,
                                        manifest_references=references, on_event=self.window.operation_event.emit,
                                        on_feedback=self.window.feedback_requested.emit,
                                        on_page_preview=self.window.page_preview_requested.emit)
            self._round_running = True
            self._page_preview_requests = []
            self.window.launch(operation, self.answered)
            self.window.jobs[-1].finished.connect(self.finish_page_installations)
        self.window._interact(action)

    def answered(self, result):
        self.chat.stop_work()
        expanded = {number: activity['expanded'] for number, activity in self.chat.activities.items()}
        self.reload_history()
        for number, activity in self.chat.activities.items():
            activity['expanded'] = expanded.get(number, False)
        self.chat.render()
        answer = result.get("answer", {})
        if result.get("diagnostics"):
            details = result['diagnostics']
            match = next((i for i in reversed(range(self.diagnostics.errors.count()))
                          if all(self.diagnostics.errors.itemData(i).get(key) == value
                                 for key, value in details.items() if key != 'budget_exhausted')), None)
            if match is None:
                self.diagnostics.add_error(details)
            else:
                self.diagnostics.errors.setItemData(match, {**self.diagnostics.errors.itemData(match), **details})
                self.diagnostics.select_error()
            self.diagnostics.show_error()
        elif result.get("error"):
            self.diagnostics.add_error({"message": result["error"], "stage": result["reason"],
                                        "round": result.get("round"), "log_path": result.get("log_path")})
            self.diagnostics.show_error()
        if result.get('reason') == 'answered':
            text = str(answer.get('message', ''))
            number = result.get('round', self.host.conversation.log.group if self.host.conversation else 0)
            if not any(row.get('role') == 'Agent' and row.get('text') == text and row.get('round') == number
                       for row in self.chat.entries):
                self.chat.add_message('Agent', text, number)
        self.show_result_status(result)
        self.update_actions(self.is_busy())

    def finish_page_installations(self):
        """轮次后台作业清理后汇总实际安装，取消或失败也提示；历史恢复不触发。"""
        requests, self._page_preview_requests = self._page_preview_requests, []
        if self.window.closing or not any(
                request.result and request.result.get('status') in {'installed', 'availability_changed'} for request in requests):
            return
        from .page_preview import PageInstalledDialog
        self.window.page_installed_dialog = PageInstalledDialog(self.window)
        self.window.page_installed_dialog.show()

    def show_result_status(self, result):
        """实时收尾和历史恢复共用结果摘要，不弹窗或修改聊天及运行状态。"""
        summary = tr('Error: ') + result['error'] if result.get('error') else {
            'answered': tr('Round complete'), 'user_cancelled': tr('Round cancelled'),
            'host_interrupted': tr('Interrupted; results may be unknown. No operations replayed.'),
        }.get(result.get('reason'), tr('Round incomplete'))
        self.set_status(summary, tr('{0}; actual requests: {1}').format(summary, result.get('requests', 0)))

    def open_page_drafts(self):
        def action():
            from .page_drafts import PageDrafts
            drafts = PageDrafts(self.session)
            drafts.root.mkdir(parents=True, exist_ok=True)
            self.diagnostics.open_directory(drafts.root)
        self.window._interact(action)

    def show_page_preview(self, request):
        """只接当前 Construct 活动；迟到请求不能重新取得安装许可。"""
        chat = self.host.conversation
        if (request.done.is_set() or self.window.closing or not self.window.jobs or chat is None
                or self.session is None or self.session.mode != 'Construct'
                or ('page_set_enabled' if hasattr(request, 'enabled') else 'page_preview') not in chat.allowed
                or any(job.cancel_requested for job in self.window.jobs)
                or request.identity[:2] != (chat.log.identity, chat.log.group)):
            request.close()
            return
        from .page_preview import PagePreviewDialog, PageAvailabilityDialog
        try:
            dialog = (PageAvailabilityDialog if hasattr(request, 'enabled') else PagePreviewDialog)(request, self.window)
            if (dialog.ready and not request.done.is_set() and not self.window.closing
                    and not any(job.cancel_requested for job in self.window.jobs)):
                self.page_preview_dialog = dialog
                self._page_preview_requests.append(request)
                dialog.show()
            else:
                request.close()
                dialog.deleteLater()
        except BaseException:
            request.close()
            raise

    def show_feedback(self, request):
        """只展示当前活动轮次；取消后排队到达的旧请求直接作废。"""
        chat = self.host.conversation
        if (request.done.is_set() or self.window.closing or not self.window.jobs or chat is None
                or any(job.cancel_requested for job in self.window.jobs)
                or request.identity[:2] != (chat.log.identity, chat.log.group)):
            request.close()
            return
        self.feedback_dialog = FeedbackDialog(request, self.window)
        self.feedback_dialog.show()
        self.set_status(tr('Waiting for feedback'))

    def show_event(self, event):
        value = event["event"]
        kind, number = value.get("type"), event.get("round", 0)
        live = (not getattr(self, '_replaying', False) and not self.window.closing
                and not any(job.cancel_requested for job in self.window.jobs))
        if kind == 'raw_output':
            if live and self._round_running:
                self.update_raw_output(value.get('content', []), number)
            return
        if kind == 'message_end' and value.get('message', {}).get('role') == 'assistant':
            self.chat.remember_message(number, value['message'].get('content', []))
        if kind in {'message_end', 'tool_execution_start', 'repair_error', 'round_finished',
                    'round_interrupted', 'final_answer_retry', 'agent_settled'}:
            self.clear_raw_output()
        status = None
        if kind == 'workbench_session':
            identity = value['session'].identity
            if not self.titles.get(identity, ('', ''))[0]:
                self.titles[identity] = chat_title(value['session'].host.conversation.log.clean(value['message']))
            self.activate_session(value['session'], restore_history=False)
            self.chat.add_message('你', value['message'], value['round'])
            self.chat.start_work(value['round'])
            self.message.clear()
            self.clear_image()
            return
        if kind == "lalc_request":
            self.request_progress.setText(tr('Conversation round: {0}; model requests this round: {1}/{2}').format(number, value['requests'], value.get('request_limit', '—')))
            status = tr('Agent is responding…')
        elif kind == "repair_error":
            self.diagnostics.add_error(value)
        elif kind == "final_answer_retry":
            self.chat.format_retry(number)
            status = tr('Invalid final response format; requesting a new response. Remaining requests: {0}.').format(value['requests_remaining'])
        elif kind in {"pi_version_warning", "skill_warning"}:
            self.chat.add_message("系统", "WARNING: " + value["message"], number)
        elif kind in {"tool_execution_start", "tool_execution_end", "repair_tool", "validation"}:
            if kind == "validation" and value.get("source") == "manual" and not getattr(self, "_replaying", False):
                return
            identity = value.get("toolCallId", f"event-{len(self.chat.entries)}")
            name = value.get("toolName") or value.get("name") or "validate"
            entry = self.chat.upsert_tool(number, identity, name, kind, value)
            if kind == "tool_execution_start":
                status = tr('Calling tool: ') + name
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
                status = tr('Error: ') + details["message"] + tr('; details are available, processing continues this round.')
        if live and status is not None:
            self.set_status(status)
            self.status.setToolTip(status)
        self.update_actions(self.is_busy())

    def show_diff(self):
        if self.session is None:
            return
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
        if self.session is None:
            return
        def done(value):
            self.reload_history()
            if not value.get("ok"):
                self.diagnostics.show_error()
        self.window.launch(self.host.validate, done)

    def publish(self):
        if self.session is None:
            return
        self.window.launch(self.host.publish, lambda identity: self.reload_history())

    def render(self, busy):
        if self.session_menu is not None:
            for action in self.session_menu.actions():
                action.setEnabled(not busy)
        if self.rename_dialog is not None:
            editor = self.rename_dialog.findChild(QLineEdit)
            buttons = self.rename_dialog.findChild(QDialogButtonBox)
            buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(not busy and bool(editor.text().strip()))
            buttons.button(QDialogButtonBox.StandardButton.Cancel).setEnabled(not busy)
        if not self.window.jobs:
            self.clear_raw_output()
            if self._round_running and self.status.text() == tr('Cancelling…'):
                self.set_status(tr('Round cancelled'))
                self.status.setToolTip(self.status.text())
            self._round_running = False
            self.chat.stop_work()
        for control in (self.new_button, self.refresh_button, self.history, self.message, self.attach):
            control.setEnabled(not busy)
        preparing = self.session is None
        self.mode.setVisible(preparing)
        self.mode.setEnabled(preparing and not busy)
        self.mode_badge.setVisible(not preparing)
        self.context_button.setVisible(preparing)
        self.context_button.setEnabled(preparing and not busy)
        self.baseline.setEnabled(preparing and not busy)
        if not preparing:
            self.source_panel.hide()
        self.update_actions(busy)
