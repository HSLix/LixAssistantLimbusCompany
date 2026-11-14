"""供日志和其他页面共用的原图标注；坐标始终使用原始图像像素。"""

from math import atan2, cos, sin, pi, isfinite

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPen


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
    return []


def paint_annotations(painter, target: QRectF, image_size, annotations: list[dict]) -> None:
    """在目标区域按比例绘制十字线、编号框和细红箭头，不改动原图。"""
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
            label = QRectF(x, y, 32, 20)
            painter.fillRect(label, QColor("#a0000000"))
            painter.drawText(label, Qt.AlignmentFlag.AlignCenter, str(item["number"]))
        elif item["kind"] == "arrow":
            end = point(item["end_x"], item["end_y"])
            painter.drawLine(QPointF(x, y), end)
            angle = atan2(end.y() - y, end.x() - x)
            for delta in (-pi / 6, pi / 6):
                painter.drawLine(end, QPointF(end.x() - 9 * cos(angle + delta), end.y() - 9 * sin(angle + delta)))
    painter.restore()
