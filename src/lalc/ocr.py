"""应用共享的本地 OCR；固定模型、串行推理，不接收路径或网络图片。"""

from __future__ import annotations

import hashlib
import importlib.util
import math
import threading
from pathlib import Path
from typing import Any


MODEL_HASHES = {
    "PP-OCRv6_det_small.onnx": "090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f",
    "PP-OCRv6_rec_small.onnx": "6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884",
}


def model_files() -> dict[str, Path]:
    """只接受固定 wheel 自带模型；识别字典内嵌在已验摘要的 rec 模型中。"""
    spec = importlib.util.find_spec("rapidocr")
    if spec is None or spec.origin is None:
        raise RuntimeError("OCR requires the automation dependencies (rapidocr and onnxruntime).")
    root = Path(spec.origin).parent / "models"
    paths = {}
    for name, expected in MODEL_HASHES.items():
        path = root / name
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != expected:
            raise ValueError(f"OCR model hash mismatch: {name}")
        paths[name] = path
    return paths


class OcrService:
    """首次使用加载模型，复用同一 CPU 实例；返回原图坐标和 JSON 数据。"""

    def __init__(self) -> None:
        self._engine = None
        self._lock = threading.Lock()

    def _load_engine(self):
        """显式使用本地模型，禁用方向分类及 SDK 默认的识别分数过滤。"""
        paths = model_files()
        from rapidocr import EngineType, ModelType, OCRVersion, RapidOCR

        params = {
            "Global.use_cls": False,
            "Global.text_score": 0.0,
            "Global.log_level": "warning",
        }
        for stage, task in (("Det", "det"), ("Rec", "rec")):
            params.update({
                f"{stage}.engine_type": EngineType.ONNXRUNTIME,
                f"{stage}.model_type": ModelType.SMALL,
                f"{stage}.ocr_version": OCRVersion.PPOCRV6,
                f"{stage}.model_path": str(paths[f"PP-OCRv6_{task}_small.onnx"]),
            })
        return RapidOCR(params=params)

    def recognize(self, image, *, region: dict[str, int] | None = None,
                  min_score: float = 0.0, checkpoint) -> dict[str, Any]:
        """识别一张 BGR 内存图；区域越界报错，不纠错、摘要或缓存结果。"""
        import numpy as np
        from .recognition import checked_region

        if type(min_score) not in {int, float} or not math.isfinite(min_score) or not 0 <= min_score <= 1:
            raise ValueError("min_score must be finite and between 0 and 1.")
        if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3 or not image.size:
            raise ValueError("OCR requires a non-empty uint8 BGR image.")
        area = checked_region(region, image.shape[1], image.shape[0])
        x, y, width, height = (area[key] for key in ("x", "y", "width", "height"))
        checkpoint()
        # SDK 会修改实例上的推理参数，同一实例不能并发使用。
        with self._lock:
            checkpoint()
            try:
                if self._engine is None:
                    self._engine = self._load_engine()
                checkpoint()
                result = self._engine(image[y:y + height, x:x + width].copy(), use_cls=False, text_score=0.0)
            finally:
                # 原生推理不能即时中断，返回或抛错前均先检查取消和所有权。
                checkpoint()
        items = []
        if result.boxes is None and result.txts is None and result.scores is None:
            return {"region": area, "items": items}
        if any(value is None for value in (result.boxes, result.txts, result.scores)):
            raise ValueError("OCR returned incomplete recognition results.")
        for polygon, text, score in zip(result.boxes, result.txts, result.scores, strict=True):
            points = np.asarray(polygon, dtype=float)
            score = float(score)
            if (points.shape != (4, 2) or not np.isfinite(points).all()
                    or type(text) is not str or not math.isfinite(score) or not 0 <= score <= 1):
                raise ValueError("OCR returned invalid text, score or polygon.")
            if score < min_score:
                continue
            points = np.rint(points).astype(int)
            points[:, 0] = np.clip(points[:, 0], 0, width - 1) + x
            points[:, 1] = np.clip(points[:, 1], 0, height - 1) + y
            left, top = (int(value) for value in points.min(axis=0))
            right, bottom = (int(value) for value in points.max(axis=0))
            items.append({"text": text, "score": score,
                          "box": {"x": left, "y": top, "width": right - left + 1, "height": bottom - top + 1},
                          "polygon": points.tolist(), "centerxy": [(left + right) // 2, (top + bottom) // 2]})
        checkpoint()
        return {"region": area, "items": items}


ocr_service = OcrService()
