"""内存图像的局部模板检测；OCR 和自定义模型检测留待后续实现。"""

from __future__ import annotations

import math

import cv2
import numpy as np


def checked_region(region: dict[str, int] | None, width: int, height: int) -> dict[str, int]:
    """验证客户区像素矩形，不自动裁边或改变调用者指定的范围。"""

    if region is None:
        return {"x": 0, "y": 0, "width": width, "height": height}
    if type(region) is not dict or set(region) != {"x", "y", "width", "height"}:
        raise ValueError("Region requires x, y, width, height.")
    if any(type(value) is not int for value in region.values()):
        raise ValueError("Region coordinates must be integers.")
    x, y, w, h = (region[key] for key in ("x", "y", "width", "height"))
    if min(x, y) < 0 or min(w, h) <= 0 or x + w > width or y + h > height:
        raise ValueError("Region must be non-empty and inside the client area.")
    return dict(region)


def decode_image(content: bytes) -> np.ndarray:
    """从已验哈希的文件字节解码 BGR 图像，失败明确报错。"""

    image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Asset image cannot be decoded.")
    return image


def client_image(pixels: bytes, size: tuple[int, int]) -> np.ndarray:
    """将窗口平台的 BGRA 字节转换为识别用 BGR，不经过截图文件。"""

    width, height = size
    if len(pixels) != width * height * 4:
        raise ValueError("Screenshot byte length does not match its client size.")
    return np.frombuffer(pixels, dtype=np.uint8).reshape(height, width, 4)[:, :, :3].copy()


def detect_template(
    image: np.ndarray, template: np.ndarray, *, region: dict[str, int] | None = None,
    threshold: float = 0.9, nms: bool = True, nms_iou_threshold: float = 0.5,
) -> list[dict[str, int | float]]:
    """返回全部达标客户区矩形；同分按 y、x 排序，NMS 只抑制 IoU 超限框。"""

    for name, value in (("threshold", threshold), ("nms_iou_threshold", nms_iou_threshold)):
        if type(value) not in {int, float} or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"{name} must be finite and between 0 and 1.")
    if type(nms) is not bool:
        raise ValueError("nms must be bool.")
    for value in (image, template):
        if value.dtype != np.uint8 or value.ndim != 3 or value.shape[2] != 3 or not value.size:
            raise ValueError("Detection requires non-empty uint8 BGR images.")
    area = checked_region(region, image.shape[1], image.shape[0])
    x, y, w, h = (area[key] for key in ("x", "y", "width", "height"))
    th, tw = template.shape[:2]
    if tw > w or th > h:
        return []
    crop = image[y:y + h, x:x + w]
    # 全黑模板的归一化分母为零，改用按最大像素误差归一化的平方差。
    if not np.any(template):
        errors = cv2.matchTemplate(crop, template, cv2.TM_SQDIFF) / (template.size * 255.0 ** 2)
    else:
        errors = cv2.matchTemplate(crop, template, cv2.TM_SQDIFF_NORMED)
    scores = np.clip(1.0 - errors, 0.0, 1.0)
    rows, columns = np.where(scores >= threshold)
    order = np.lexsort((columns, rows, -scores[rows, columns]))
    kept: list[dict[str, int | float]] = []
    suppressed = np.zeros(scores.shape, dtype=bool) if nms else None
    for index in order:
        row, column = int(rows[index]), int(columns[index])
        if suppressed is not None:
            if suppressed[row, column]:
                continue
            # 同一模板的框等大，只需在可能重叠的局部网格标记，无须逐框两两比较。
            l, r = max(0, column - tw + 1), min(scores.shape[1], column + tw)
            t, b = max(0, row - th + 1), min(scores.shape[0], row + th)
            overlap = (th - np.abs(np.arange(t, b) - row))[:, None] * (
                tw - np.abs(np.arange(l, r) - column))[None, :]
            suppressed[t:b, l:r] |= overlap / (2 * tw * th - overlap) > nms_iou_threshold
        kept.append({"x": column + x, "y": row + y, "width": tw, "height": th,
                     "score": float(scores[row, column])})
    return kept
