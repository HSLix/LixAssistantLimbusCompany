"""应用共享的本地 OCR；固定模型、串行推理，不接收路径或网络图片。"""

from __future__ import annotations

import hashlib
import importlib.util
import math
import os
import threading
from pathlib import Path
from typing import Any


MODEL_HASHES = {
    "PP-OCRv6_det_small.onnx": "090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f",
    "PP-OCRv6_rec_small.onnx": "6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884",
}
_DET_OPTIONS = ("thresh", "box_thresh", "unclip_ratio", "use_dilation", "score_mode", "max_candidates")
# 单帧 OCR 的算子图很小：onnxruntime 默认按物理核开 intra 线程，多核机器上线程过度订阅只多耗 CPU。
MAX_INTRA_THREADS = 8
INTER_THREADS = 1


def engine_threads(cpu_count: int | None = None) -> tuple[int, int]:
    """返回 (intra_op, inter_op) 线程上限；按核数取一半并封顶 8。

    实测（onnxruntime 1.31.1、rapidocr 3.10.0、PP-OCRv6 det/rec small、2560x1440 整屏与
    条带/局部裁剪、28 逻辑核）：默认 intra=-1 时单帧占约 24 线程、CPU 22–24 s、墙钟 0.94–1.02 s；
    intra=4 时 CPU 5.7–6.4 s、墙钟 0.99–1.18 s；intra=8 时 CPU 10–12 s、墙钟 0.80–1.07 s。
    三档识别文本逐条相同（按行排序后比较）。⇒ 限制线程后 CPU 至少降一半、墙钟不劣化，
    多核机器上同时跑 GUI 与其他识别时余量更大。
    """
    cores = os.cpu_count() if cpu_count is None else cpu_count
    cores = max(1, int(cores or 1))
    return max(1, min(MAX_INTRA_THREADS, cores // 2)), INTER_THREADS


def _check_det_options(options: dict[str, Any] | None) -> None:
    """仅放行有限范围内的检测后处理参数。"""
    if options is None:
        return
    if type(options) is not dict:
        raise ValueError("det_options must be a dictionary.")
    for name, value in options.items():
        match name:
            case "thresh" | "box_thresh":
                valid = type(value) in {int, float} and 0 <= value <= 1
            case "unclip_ratio":
                valid = type(value) in {int, float} and 0 < value <= 10
            case "use_dilation":
                valid = type(value) is bool
            case "score_mode":
                valid = type(value) is str and value in ("fast", "slow")
            case "max_candidates":
                valid = type(value) is int and 1 <= value <= 10000
            case _:
                raise ValueError(f"Unknown OCR det_options key: {name!r}.")
        if not valid:
            raise ValueError(f"Invalid OCR det_options.{name} value.")


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

        intra, inter = engine_threads()
        params = {
            "Global.use_cls": False,
            "Global.text_score": 0.0,
            "Global.log_level": "warning",
            # 线程上限：默认按物理核开线程，小算子图上只增加切换开销（见 engine_threads 实测）。
            "EngineConfig.onnxruntime.intra_op_num_threads": intra,
            "EngineConfig.onnxruntime.inter_op_num_threads": inter,
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
                  min_score: float = 0.0, det_options: dict[str, Any] | None = None,
                  checkpoint) -> dict[str, Any]:
        """识别一张 BGR 内存图；区域越界报错，不纠错、摘要或缓存结果。"""
        import numpy as np
        from .recognition import checked_region

        if type(min_score) not in {int, float} or not math.isfinite(min_score) or not 0 <= min_score <= 1:
            raise ValueError("min_score must be finite and between 0 and 1.")
        _check_det_options(det_options)
        if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3 or not image.size:
            raise ValueError("OCR requires a non-empty uint8 BGR image.")
        area = checked_region(region, image.shape[1], image.shape[0])
        x, y, width, height = (area[key] for key in ("x", "y", "width", "height"))
        checkpoint()
        # SDK 会修改实例上的推理参数，同一实例不能并发使用。
        with self._lock:
            checkpoint()
            detector = None
            default_postprocess = None
            try:
                if self._engine is None:
                    self._engine = self._load_engine()
                if det_options:
                    # 固定版本的 SDK 只支持逐次覆盖部分参数；替换后处理以复用模型并隔离本次设置。
                    detector = self._engine._load_det_model()
                    default_postprocess = detector.postprocess_op
                    settings = {key: self._engine.cfg.Det[key] for key in _DET_OPTIONS}
                    detector.postprocess_op = type(default_postprocess)(**(settings | det_options))
                checkpoint()
                result = self._engine(image[y:y + height, x:x + width].copy(), use_cls=False, text_score=0.0)
            finally:
                if detector is not None:
                    detector.postprocess_op = default_postprocess
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
