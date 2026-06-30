"""
OCR 抽象接口层 — 模型无关的文字识别抽象。

目的：
  - 将 OCR 从 RapidOCR 具体实现解耦
  - 允许运行时切换 OCR 引擎（RapidOCR / PaddleOCR / Tesseract / 云端 API）
  - 统一返回值格式，消除各 handler 对返回格式的假设

当前实现：RapidOcrProvider（包装已有的 rapid_ocr.py）
未来可添加：PaddleOcrProvider, TesseractProvider, CloudOcrProvider
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Callable
from PIL import Image


# ══════════════════════════════════════════════════════
# 统一返回值
# ══════════════════════════════════════════════════════

@dataclass
class OcrResult:
    """单条 OCR 检测结果"""
    text: str
    """识别的文字内容"""
    x: int
    """文字中心横坐标（像素）"""
    y: int
    """文字中心纵坐标（像素）"""
    confidence: float
    """置信度 0~1"""
    bbox: Optional[list] = None
    """边界框 [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]"""


# ══════════════════════════════════════════════════════
# 抽象接口
# ══════════════════════════════════════════════════════

class OcrProvider(ABC):
    """OCR 引擎抽象基类。
    
    所有 OCR 实现必须实现这两个方法。
    返回值统一为 list[OcrResult]，按置信度降序排列。
    """
    
    @abstractmethod
    def detect_text(self, image: Image.Image, region: Optional[list] = None,
                    min_confidence: float = 0.3) -> list[OcrResult]:
        """检测图像中所有文字。
        
        Args:
            image: PIL Image（全屏截图或裁剪区域）
            region: [x, y, w, h] 可选裁剪区域
            min_confidence: 最低置信度阈值
        
        Returns:
            按置信度降序排列的检测结果列表
        """
        ...
    
    @abstractmethod
    def find_text(self, image: Image.Image, target: str, region: Optional[list] = None,
                  min_confidence: float = 0.5, partial: bool = True) -> list[OcrResult]:
        """在图像中查找指定文字。
        
        Args:
            image: PIL Image
            target: 要查找的文字（含/不含被查找文字）
            region: [x, y, w, h] 可选裁剪区域
            min_confidence: 最低置信度阈值
            partial: True=子串匹配, False=精确匹配
        
        Returns:
            匹配的文字结果（按置信度降序）
        """
        ...
    
    @property
    @abstractmethod
    def name(self) -> str:
        """引擎名称，用于日志和配置"""
        ...


# ══════════════════════════════════════════════════════
# 工厂
# ══════════════════════════════════════════════════════

class OcrProviderFactory:
    """OCR 引擎工厂。
    
    register() 注册实现类
    create()  创建实例
    
    用法：
        OcrProviderFactory.register("rapidocr", RapidOcrProvider)
        provider = OcrProviderFactory.create("rapidocr")
    """
    
    _providers: dict[str, type[OcrProvider]] = {}
    
    @classmethod
    def register(cls, name: str, provider_cls: type[OcrProvider]):
        cls._providers[name] = provider_cls
    
    @classmethod
    def create(cls, name: str = "rapidocr", **kwargs) -> OcrProvider:
        if name not in cls._providers:
            available = list(cls._providers.keys())
            raise ValueError(
                f"未知 OCR 引擎: '{name}'。可用: {available}"
            )
        return cls._providers[name](**kwargs)
    
    @classmethod
    def list_available(cls) -> list[str]:
        return list(cls._providers.keys())


# ══════════════════════════════════════════════════════
# RapidOCR 实现
# ══════════════════════════════════════════════════════

class RapidOcrProvider(OcrProvider):
    """RapidOCR 实现（包装现有的 rapid_ocr.py）。
    
    兼容：
    - Windows: rapidocr 包
    - Linux:  rapidocr_onnxruntime 包
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self._engine = None
        self._config_path = config_path
        self._load_engine()
    
    def _load_engine(self):
        """延迟加载 RapidOCR 引擎（避免模块级 import 失败）。"""
        from recognize.utils import pil_to_cv2
        self._pil_to_cv2 = pil_to_cv2
        
        import cv2
        self._cv2 = cv2
        
        try:
            from rapidocr import RapidOCR
            self._engine = RapidOCR(
                config_path=self._config_path
            ) if self._config_path else RapidOCR()
        except ImportError:
            try:
                from rapidocr_onnxruntime import RapidOCR
                self._engine = RapidOCR(
                    config_path=self._config_path
                ) if self._config_path else RapidOCR()
            except ImportError:
                raise ImportError(
                    "RapidOCR 未安装。请安装: pip install rapidocr 或 rapidocr_onnxruntime"
                )
    
    @property
    def name(self) -> str:
        return "rapidocr"
    
    def detect_text(self, image: Image.Image, region: Optional[list] = None,
                    min_confidence: float = 0.3) -> list[OcrResult]:
        """检测图像中所有文字。
        
        内部处理：
        - 裁剪 region（如果有）
        - CLAHE 增强（和原 rapid_ocr.py 一致）
        - RapidOCR 推理
        - 合并相邻文本
        """
        import numpy as np
        
        # 1. 裁剪
        if region:
            x, y, w, h = region
            img = image.crop((x, y, x + w, y + h))
        else:
            img = image
        
        # 2. 转灰度 + CLAHE
        img_cv = self._pil_to_cv2(img, grayscale=True)
        clahe = self._cv2.createCLAHE(clipLimit=2, tileGridSize=(16, 16))
        img_cv = clahe.apply(img_cv)
        
        # 3. 推理
        result = self._engine(img_cv)
        if result is None or result.boxes is None:
            return []
        
        # 4. 组装结果
        results = []
        for box, text, conf in zip(result.boxes, result.txts, result.scores):
            box_np = np.array(box, dtype=np.float32)
            cx = int(box_np[:, 0].mean())
            cy = int(box_np[:, 1].mean())
            
            # 如果有 region 裁剪，还原坐标到原图空间
            if region:
                cx += region[0]
                cy += region[1]
            
            if conf >= min_confidence:
                results.append(OcrResult(
                    text=text,
                    x=cx, y=cy,
                    confidence=float(conf),
                    bbox=box.tolist() if hasattr(box, 'tolist') else box,
                ))
        
        # 按置信度降序
        results.sort(key=lambda r: -r.confidence)
        return results
    
    def find_text(self, image: Image.Image, target: str, region: Optional[list] = None,
                  min_confidence: float = 0.5, partial: bool = True) -> list[OcrResult]:
        """在图像中查找指定文字。"""
        all_texts = self.detect_text(image, region=region, min_confidence=min_confidence)
        
        if partial:
            matched = [r for r in all_texts if target in r.text]
        else:
            matched = [r for r in all_texts if r.text == target]
        
        return matched


# ══════════════════════════════════════════════════════
# 全局实例
# ══════════════════════════════════════════════════════

# 注册默认引擎
OcrProviderFactory.register("rapidocr", RapidOcrProvider)

# 运行时可通过 set_provider() 替换
_global_provider: Optional[OcrProvider] = None


def get_provider() -> OcrProvider:
    """获取全局 OCR provider 实例（延迟创建）。
    
    可通过 set_provider() 替换为其他实现。
    """
    global _global_provider
    if _global_provider is None:
        _global_provider = OcrProviderFactory.create("rapidocr")
    return _global_provider


def set_provider(provider: OcrProvider):
    """替换全局 OCR provider。"""
    global _global_provider
    _global_provider = provider


# ══════════════════════════════════════════════════════
# 性能基准
# ══════════════════════════════════════════════════════

def benchmark_ocr(provider: Optional[OcrProvider] = None, 
                  test_regions: Optional[list[tuple[str, list]]] = None) -> dict:
    """对指定区域运行 OCR 基准测试。
    
    测量每个区域调用的耗时时长。
    返回 {region_name: {"time_ms": float, "text_count": int, "texts": list}}
    """
    import time
    from input.input_handler import input_handler
    
    provider = provider or get_provider()
    if test_regions is None:
        test_regions = [
            ("全屏", None),
            ("战斗人数", [1130, 500, 100, 50]),
            ("脑啡肽充值", [680, 300, 120, 45]),
            ("商店金额", [568, 100, 100, 80]),
            ("楼层饰品名", [90, 170, 1090, 40]),
        ]
    
    results = {}
    screenshot = input_handler.capture_screenshot()
    
    for name, region in test_regions:
        t0 = time.perf_counter()
        texts = provider.detect_text(screenshot, region=region)
        elapsed = (time.perf_counter() - t0) * 1000
        
        results[name] = {
            "time_ms": round(elapsed, 1),
            "text_count": len(texts),
            "texts": [t.text for t in texts[:5]],
        }
    
    return results
