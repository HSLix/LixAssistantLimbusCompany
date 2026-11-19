"""供日志和其他页面共用的原图标注；坐标始终使用原始图像像素。"""

from __future__ import annotations

from math import atan2, cos, sin, pi, isfinite
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtCore import QRectF


def action_annotations(record: dict) -> list[dict]:
    """从正式动作参数与返回值提取标注，不推测失败动作已完成。"""
    name, inputs = record.get("logical_name"), record.get("inputs", {})
    if not isinstance(inputs, dict):
        return []
    if name == "control.click":
        point = inputs.get("centerxy") or (inputs.get("x"), inputs.get("y"))
        if isinstance(point, (list, tuple)) and len(point) == 2 and all(type(v) is int for v in point):
            return [{"kind": "cross", "x": point[0], "y": point[1]}]
    if name == "control.drag" and all(type(inputs.get(key)) is int for key in ("x", "y", "end_x", "end_y")):
        return [{"kind": "arrow", **{key: inputs[key] for key in ("x", "y", "end_x", "end_y")}}]
    if name in {"observe.match_asset", "observe.match_feature"} and isinstance(record.get("return_value"), list):
        return [{"kind": "box", "number": i, **{key: item[key] for key in ("x", "y", "width", "height")}}
                for i, item in enumerate(record["return_value"], 1) if isinstance(item, dict)
                and all(type(item.get(key)) in {int, float} and isfinite(item[key]) for key in ("x", "y", "width", "height"))]
    result = record.get("return_value")
    if name == "observe.ocr" and isinstance(result, dict) and isinstance(result.get("items"), list):
        keys = ("x", "y", "width", "height")
        return [{"kind": "box", "text": item["text"], **{key: box[key] for key in keys}}
                for item in result["items"] if isinstance(item, dict) and isinstance(item.get("text"), str)
                and isinstance(box := item.get("box"), dict) and all(type(box.get(key)) is int for key in keys)]
    return []


def paint_annotations(painter, target: QRectF, image_size, annotations: list[dict]) -> None:
    """在目标区域按比例绘制十字线、编号框和细红箭头，不改动原图。"""
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QPen

    width, height = image_size
    if width <= 0 or height <= 0 or target.isEmpty():
        return
    sx, sy = target.width() / width, target.height() / height
    def point(x, y):
        return QPointF(target.left() + x * sx, target.top() + y * sy)
    painter.save()
    painter.setClipRect(target)
    painter.setRenderHint(painter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#ff4040"), 1.2))
    for item in annotations:
        x, y = point(item["x"], item["y"]).toTuple()
        if item["kind"] == "cross":
            painter.drawLine(QPointF(target.left(), y), QPointF(target.right(), y))
            painter.drawLine(QPointF(x, target.top()), QPointF(x, target.bottom()))
        elif item["kind"] == "box":
            painter.drawRect(QRectF(x, y, item["width"] * sx, item["height"] * sy))
            text = item.get("text", str(item.get("number", "")))
            label_width = min(target.width(), painter.fontMetrics().horizontalAdvance(text) + 8) if "text" in item else 32
            label = QRectF(min(x, target.right() - label_width), y, label_width, 20)
            painter.fillRect(label, QColor("#a0000000"))
            painter.drawText(label, Qt.AlignmentFlag.AlignCenter, text)
        elif item["kind"] == "arrow":
            end = point(item["end_x"], item["end_y"])
            painter.drawLine(QPointF(x, y), end)
            angle = atan2(end.y() - y, end.x() - x)
            for delta in (-pi / 6, pi / 6):
                painter.drawLine(end, QPointF(end.x() - 9 * cos(angle + delta), end.y() - 9 * sin(angle + delta)))
    painter.restore()


def draw_preview_annotations(image, original_size, annotations: list[dict]) -> None:
    """为 Agent 的 JPEG 预览绘制框、文字和点击坐标，无需启动 GUI。"""
    from os import environ
    from pathlib import Path

    from PIL import ImageDraw, ImageFont

    draw = ImageDraw.Draw(image)
    sx, sy = image.width / original_size[0], image.height / original_size[1]
    color = "#ff4040"
    font = None
    for item in annotations:
        x, y = round(item["x"] * sx), round(item["y"] * sy)
        if item["kind"] == "cross":
            draw.line((0, y, image.width - 1, y), fill=color, width=2)
            draw.line((x, 0, x, image.height - 1), fill=color, width=2)
        elif item["kind"] == "box":
            right = round((item["x"] + item["width"]) * sx)
            bottom = round((item["y"] + item["height"]) * sy)
            if right < x or bottom < y:
                continue
            draw.rectangle((x, y, right, bottom), outline=color, width=2)
            if font is None:
                # OCR 标签可能含 CJK 字符，优先使用系统提供的字体。
                candidates = (
                    Path(environ.get("SystemRoot", "C:/Windows")) / "Fonts/msyh.ttc",
                    Path("/System/Library/Fonts/STHeiti Medium.ttc"),
                    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
                )
                font_path = next((path for path in candidates if path.is_file()), None)
                font = ImageFont.truetype(str(font_path), 13) if font_path else ImageFont.load_default(size=13)
            label = item.get("text", str(item.get("number", "")))
            width = min(image.width, round(draw.textlength(label, font=font)) + 8)
            left = max(0, min(x, image.width - width))
            draw.rectangle((left, y, left + width, y + 19), fill="#282828")
            draw.text((left + 4, y + 2), label, fill=color, font=font)
