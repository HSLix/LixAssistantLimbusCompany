"""
popup_handler — 基于 RapidOCR 的通用游戏弹窗处理器。

核心思路：
  不再依赖模板图片逐一匹配弹窗，而是用 OCR 识别全屏文字，
  匹配预定义的错误模式关键词 → 分类弹窗类型 → 推断按钮位置 → 返回可执行结果。

设计原则：
  - 纯函数，无状态，无副作用（不截图、不点击），方便离线验证
  - 按钮位置通过 OCR 返回的 bounding box 推断，不依赖固定坐标
  - 中英文通用，不依赖特定语言 UI

用法（离线测试）：
    from popup_handler import analyze_screenshot
    from PIL import Image
    result = analyze_screenshot(Image.open("test_screenshot.png"))
    if result:
        print(result.popup_type, result.click_target, result.matched_text)
"""

from __future__ import annotations

import os
import random
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import cv2
import numpy as np
from PIL import Image

# ── RapidOCR 初始化（兼容 Windows rapidocr 和 Linux rapidocr_onnxruntime） ──
try:
    from recognize.rapid_ocr import img_ocr as _rapid_ocr_instance
except (ImportError, ModuleNotFoundError):
    # Fallback 1: try direct rapidocr import
    try:
        from rapidocr import RapidOCR as _RapidOCR
    except ImportError:
        # Fallback 2: rapidocr-onnxruntime package
        try:
            from rapidocr_onnxruntime import RapidOCR as _RapidOCR
        except ImportError:
            _RapidOCR = None

    if _RapidOCR is not None:
        _base_dir = os.path.dirname(__file__)
        _yaml_path = os.path.join(_base_dir, "recognize", "rapidocr.yaml")
        if not os.path.exists(_yaml_path):
            _yaml_path = os.path.join(_base_dir, "rapidocr.yaml")
        try:
            _rapid_ocr_instance = _RapidOCR(config_path=_yaml_path) if os.path.exists(_yaml_path) else _RapidOCR()
        except (TypeError, ValueError):
            # Config may have null model_path entries that crash on some RapidOCR builds
            _rapid_ocr_instance = _RapidOCR()
    else:
        _rapid_ocr_instance = None

try:
    from recognize.utils import pil_to_cv2
except ImportError:
    from utils import pil_to_cv2  # fallback


# ── 弹窗类型枚举 ────────────────────────────────────────────────────────


class PopupType(Enum):
    """弹窗分类结果。"""
    RETRY = "retry"
    """需要点击"重试"按钮（网络临时波动等）"""
    CLOSE = "close"
    """需要点击"关闭"按钮（游戏必须重启的情况）"""
    MAINTENANCE = "maintenance"
    """服务器维护中，需要停止并等待"""
    UPDATE = "update"
    """客户端需要手动更新"""
    DOWNLOAD = "download"
    """需要确认下载数据"""
    REWARD = "reward"
    """奖励领取确认"""
    CONNECTING = "connecting"
    """正在重连（无弹窗，仅在操作栏显示）"""
    UNKNOWN = "unknown"
    """未识别"""


# ── 输出数据结构 ────────────────────────────────────────────────────────


@dataclass
class PopupResult:
    """一次弹窗分析的结果。"""
    popup_type: PopupType = PopupType.UNKNOWN
    """弹窗分类"""
    confidence: float = 0.0
    """整体置信度 (0~1)"""
    click_target: tuple[int, int] = (0, 0)
    """建议点击的屏幕坐标 (x, y)"""
    matched_text: str = ""
    """命中最高的匹配文字"""
    text_bbox: tuple[int, int, int, int] = (0, 0, 0, 0)
    """匹配文字的 bounding box (x, y, w, h)"""
    all_texts: list[tuple[str, int, int, float]] = field(default_factory=list)
    """全量 OCR 结果，供调试"""


# ── 错误模式定义 ────────────────────────────────────────────────────────
#
# 每条规则：(关键词列表, 弹窗类型, 按钮方位)
#   - 关键词支持正则，大小写不敏感
#   - 按钮方位: "below" 表示在文字下方固定偏移, "label" 表示要找按钮上的文字点击

_PATTERNS: list[tuple[list[str], PopupType, str]] = [
    # ── 需要重试 ──
    (["try again", "retry", "再试一次?", "重试"], PopupType.RETRY, "label"),
    (["server error", "server.*occurred", "服务器错误", "服务错误"], PopupType.RETRY, "label"),
    # ── 需要关闭重启 ──
    (["cannot operate", "cannot play", "无法操作"], PopupType.CLOSE, "label"),
    (["network is unstable", "network.*unstable", "网络不稳定", "网络连接不稳定"], PopupType.CLOSE, "label"),
    (["try later", "稍后重试", "稍后再试"], PopupType.CLOSE, "label"),
    # ── 维护 ──
    (["maintenance", "维护"], PopupType.MAINTENANCE, "label"),
    # ── 需要更新 ──
    (["not up to date", "app update", "version update", "新版本", "更新"], PopupType.UPDATE, "label"),
    # ── season 标签上的 "update" 不算 ──
    (["download data", "下载数据"], PopupType.DOWNLOAD, "label"),
    # ── 奖励确认 ──
    (["rewards? acquired", "领取奖励", "奖励确认"], PopupType.REWARD, "below"),
    # ── 重连状态（无弹窗，顶部/底部状态栏文字） ──
    (["connecting", "reconnect", "reconnecting", "now loading", "loading", "加载", "重连", "重新连接"], PopupType.CONNECTING, "label"),
]

_CONFIDENCE_THRESHOLD = 0.5
"""弹窗分类置信度阈值。低于此值的匹配视为误报。"""

RETRY_COOLDOWN_SECONDS = 5
"""点击 Retry 后需要等待的冷却时间（秒），期间不要重复点击。"""

# 弹窗类型优先级（数字越大越优先）
# CLOSE > MAINTENANCE > RETRY > 其他
_TYPE_PRIORITY: dict[PopupType, int] = {
    PopupType.CLOSE: 10,
    PopupType.MAINTENANCE: 8,
    PopupType.RETRY: 6,
    PopupType.UPDATE: 4,
    PopupType.DOWNLOAD: 4,
    PopupType.REWARD: 2,
    PopupType.CONNECTING: 1,
}

# 已知按钮标签 → 推断为点击目标
_BUTTON_LABELS: list[str] = [
    "try again", "retry", "重试", "再试",
    "close", "ok", "confirm", "确定", "确认", "关闭",
]

# 点击随机偏移半径（像素）— 避免像素级精确点击
_CLICK_JITTER = 15

# 弹窗文字与按钮之间的典型 Y 间距（像素），当按钮靠推断时使用
_BUTTON_Y_OFFSET = 55
# 按钮在弹窗中横跨的典型宽度
_BUTTON_HALF_WIDTH = 60
# 按钮文字与弹窗主体间的允许 Y 间距范围（像素）
_BUTTON_DY_RANGE = (10, 150)


# ── 核心函数 ────────────────────────────────────────────────────────────


def _ocr_full(screenshot: Image.Image) -> list[dict]:
    """
    对截图做 OCR，返回带 bbox 的完整结果。

    返回:
      [
        {"text": "try again", "cx": 640, "cy": 400,
         "conf": 0.95, "bbox": (580, 380, 700, 420)},
        ...
      ]
    其中 bbox = (x_min, y_min, x_max, y_max)。
    """
    img_cv = pil_to_cv2(screenshot, grayscale=False)
    # 转灰度 + CLAHE 增强（和 rapid_ocr.py 一致）
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2, tileGridSize=(16, 16))
    enhanced = clahe.apply(gray)

    result = _rapid_ocr_instance(enhanced)

    # Handle different RapidOCR API formats
    # Format 1 (rapidocr pypi): object with .boxes / .txts / .scores
    # Format 2 (rapidocr-onnxruntime): tuple (merged_list, [elapse...])
    #   where merged_list[i] = [box_4points, text_str, confidence_float]
    # Format 3 (some builds): tuple ([boxes], [texts], [scores])
    if hasattr(result, 'boxes'):
        dt_boxes = result.boxes
        texts = result.txts
        scores = result.scores
    elif isinstance(result, (list, tuple)):
        if len(result) == 2 and isinstance(result[1], (list, tuple)):
            # format 2: rapidocr-onnxruntime style
            merged = result[0]
            if merged is None or len(merged) == 0:
                return []
            dt_boxes = []
            texts = []
            scores = []
            for entry in merged:
                if len(entry) >= 3:
                    dt_boxes.append(entry[0])
                    texts.append(entry[1])
                    scores.append(entry[2])
        elif len(result) >= 3:
            # format 3: raw tuple
            dt_boxes, texts, scores = result[:3]
        else:
            raise TypeError(f"Unexpected RapidOCR result length: {len(result)}")
    else:
        raise TypeError(f"Unexpected RapidOCR result type: {type(result)}")

    if dt_boxes is None or len(dt_boxes) == 0:
        return []

    items = []
    for i in range(len(dt_boxes)):
        box = np.array(dt_boxes[i], dtype=np.float32)
        xs = box[:, 0]
        ys = box[:, 1]
        x_min, x_max = int(xs.min()), int(xs.max())
        y_min, y_max = int(ys.min()), int(ys.max())
        cx = int(xs.mean())
        cy = int(ys.mean())
        items.append({
            "text": texts[i].strip() if texts and i < len(texts) else "",
            "cx": cx,
            "cy": cy,
            "conf": float(scores[i]) if scores and i < len(scores) else 0.0,
            "bbox": (x_min, y_min, x_max, y_max),
        })

    return items


def _classify(items: list[dict]) -> Optional[PopupResult]:
    """
    遍历 OCR 结果，匹配预定义错误模式。
    返回匹配度最高的 PopupResult，或 None（无匹配）。
    评分 = OCR置信度 × 关键词覆盖率 × 类型优先级（CLOSE > MAINTENANCE > RETRY > 其他）
    """
    best: Optional[PopupResult] = None
    best_score = 0.0

    for item in items:
        text_lower = item["text"].lower()
        for keywords, popup_type, btn_mode in _PATTERNS:
            for kw in keywords:
                if re.search(kw, text_lower):
                    coverage = len(kw) / max(len(text_lower), 1)
                    priority = _TYPE_PRIORITY.get(popup_type, 1)
                    score = item["conf"] * coverage * priority
                    if score > best_score:
                        best_score = score
                        best = PopupResult(
                            popup_type=popup_type,
                            confidence=score,
                            matched_text=item["text"],
                            text_bbox=item["bbox"],
                        )
                    break  # 一条规则内只匹配第一个关键词


    return best


def _jitter(x: int, y: int, radius: int = _CLICK_JITTER) -> tuple[int, int]:
    """给点击坐标加随机偏移，避免像素级精确。"""
    dx = random.randint(-radius, radius)
    dy = random.randint(-radius, radius)
    return (x + dx, y + dy)


def _locate_button(items: list[dict], result: PopupResult) -> tuple[int, int]:
    """
    根据弹窗分析结果，确定按钮点击坐标。
    策略:
      0. 如果匹配到的文字本身是按钮标签，直接点它（最常见：Retry / Try Again 就是按钮）
      1. 否则在 OCR 结果中找弹窗下方的按钮文字，优先匹配弹窗类型对应的按钮
      2. 如果还找不到，从弹窗主体文字的 bbox 底部垂直偏移推断
    """
    x_min, y_min, x_max, y_max = result.text_bbox
    popup_cx = (x_min + x_max) // 2
    popup_bottom = y_max

    # 策略 0: 匹配的文字本身就是按钮 → 直接点它
    matched_text_lower = (result.matched_text or "").lower().strip()
    if any(label == matched_text_lower for label in _BUTTON_LABELS):
        return _jitter(popup_cx, (y_min + y_max) // 2)

    # 策略 1: 找按钮文字，优先匹配同类型的按钮
    # 映射：CLOSE → ["close", "ok", "确定"…], RETRY → ["retry", "try again", "重试"…]
    type_primary_labels: dict[PopupType, set[str]] = {
        PopupType.CLOSE: {"close", "ok", "确定", "确认", "关闭"},
        PopupType.RETRY: {"retry", "try again", "重试", "再试"},
    }
    primary = type_primary_labels.get(result.popup_type, set())

    candidates: list[tuple[dict, int, bool]] = []  # (item, dy, is_primary)
    for item in items:
        text_lower = item["text"].lower()
        for label in _BUTTON_LABELS:
            if label in text_lower:
                dy = item["cy"] - popup_bottom
                if _BUTTON_DY_RANGE[0] < dy < _BUTTON_DY_RANGE[1]:
                    is_primary = (label in primary)
                    candidates.append((item, abs(dy), is_primary))
                break  # 一个 item 只匹配一次

    if candidates:
        # 先按 is_primary 排序（True 优先），再按 dy 排序
        candidates.sort(key=lambda x: (not x[2], x[1]))
        btn = candidates[0][0]
        return _jitter(btn["cx"], btn["cy"])
    # 策略 2: 从弹窗底部 + 固定偏移
    return _jitter(popup_cx, popup_bottom + _BUTTON_Y_OFFSET)


def analyze_screenshot(
    screenshot: Image.Image,
    *,
    center_only: bool = True,
    center_margin: int = 200,
) -> Optional[PopupResult]:
    """
    分析一张游戏截图，识别错误弹窗并返回操作建议。

    参数:
        screenshot: PIL Image，游戏窗口截图。
        center_only: 是否只分析屏幕中央区域（弹窗通常居中），省 OCR 耗时。
        center_margin: 中央区域在垂直方向上的扩展像素。

    返回:
        PopupResult 或 None（未识别到已知弹窗）。
    """
    w, h = screenshot.size

    # 裁剪中央区域（弹窗通常居中）
    if center_only:
        crop_top = max(0, h // 2 - center_margin)
        crop_bot = min(h, h // 2 + center_margin)
        roi = screenshot.crop((0, crop_top, w, crop_bot))
    else:
        crop_top = 0
        roi = screenshot

    # OCR
    items = _ocr_full(roi)

    # 把 ROI 坐标映射回原图坐标
    for item in items:
        item["cy"] += crop_top
        x1, y1, x2, y2 = item["bbox"]
        item["bbox"] = (x1, y1 + crop_top, x2, y2 + crop_top)

    # 分类
    result = _classify(items)
    if result is None:
        return None
    if result.confidence < _CONFIDENCE_THRESHOLD:
        return None

    # 定位按钮
    click_x, click_y = _locate_button(items, result)
    result.click_target = (click_x, click_y)
    result.all_texts = [(it["text"], it["cx"], it["cy"], it["conf"]) for it in items]

    return result


# ── 便捷包装 ────────────────────────────────────────────────────────────


def classify_and_click(
    screenshot: Image.Image,
    input_handler_instance=None,
) -> Optional[PopupResult]:
    """
    分析截图 → 如果识别到弹窗 → 点击按钮。

    适合在 pipeline 中直接调用。
    传入 input_handler 实例以执行点击，默认用全局 input_handler。

    返回:
        PopupResult（已执行点击）或 None（无弹窗）。
    """
    result = analyze_screenshot(screenshot)
    if result is None or result.popup_type == PopupType.UNKNOWN:
        return None

    if input_handler_instance is None:
        from input.input_handler import input_handler as _ih
        input_handler_instance = _ih

    input_handler_instance.click(*result.click_target)
    return result


# ── 离线测试入口 ────────────────────────────────────────────────────────


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(f"用法: python {sys.argv[0]} <截图路径> [center_only=1]")
        sys.exit(1)

    path = sys.argv[1]
    center = sys.argv[2] != "0" if len(sys.argv) > 2 else True

    img = Image.open(path)
    print(f"分析截图: {path}  ({img.size})")

    result = analyze_screenshot(img, center_only=center)
    if result is None:
        print("→ 未识别到已知弹窗")
        print()
        # 兜底：打印所有识别的文字
        print("--- 全量 OCR 结果 ---")
        items = _ocr_full(img)
        for it in items:
            print(f"  [{it['conf']:.2f}] {it['text']}  @({it['cx']},{it['cy']})  bbox={it['bbox']}")
    else:
        print(f"→ 识别: {result.popup_type.value}")
        print(f"  置信度: {result.confidence:.3f}")
        print(f"  匹配文字: \"{result.matched_text}\"")
        print(f"  文字位置: {result.text_bbox}")
        print(f"  建议点击: {result.click_target}")
        print()
        print("--- 全量 OCR 结果 ---")
        for text, cx, cy, conf in result.all_texts:
            print(f"  [{conf:.2f}] {text}  @({cx},{cy})")
