"""
惰性滚动检测器 — 不 OCR、不模板匹配，通过截图变化判断滑动是否到底。

原理：
  向某一方向连续滑动，每次截图与上一帧对比。
  当画面不再变化（帧差异 < 阈值）→ 已到达尾部。
  无需知道"滑到什么内容"，只需要"画面不动了"。

经验本：向右滑到底 → 点击最后一个关卡入口
纽本：  点今日副本 → 向下滑到底 → 点击最高难度
"""
import time
import logging
from typing import Optional
import numpy as np
from PIL import Image


class ScrollHelper:
    """惰性滚动检测助手。
    
    用法：
        helper = ScrollHelper()
        
        # 向右滑到底（经验本选关）
        final_shot = helper.scroll_to_tail(
            direction="right",
            swipe_start=(940, 310), swipe_end=(590, 310),
            max_swipes=8, diff_threshold=5.0,
        )
        # 点击最右侧可见的关卡入口
        input_handler.click(990, 480)  # 固定的"进入"按钮位置
        
        # 向下滑到底（纽本选难度）
        final_shot = helper.scroll_to_tail(
            direction="down",
            swipe_start=(650, 430), swipe_end=(650, 325),
            max_swipes=6, diff_threshold=5.0,
        )
        # 点击最高难度
        input_handler.click(990, 480)  # 固定的"进入"按钮
    """
    
    def __init__(self, input_handler):
        self.input_handler = input_handler
        self.logger = logging.getLogger(__name__)
    
    def scroll_to_tail(
        self,
        direction: str = "right",
        swipe_start=None,
        swipe_end=None,
        max_swipes: int = 10,
        diff_threshold: float = 5.0,
        region: Optional[list] = None,
        pre_delay: float = 0.3,
        post_delay: float = 0.5,
    ) -> Image.Image:
        """向指定方向滑动直到屏幕不再变化（已到尾部）。
        
        Args:
            direction: 仅用于日志
            swipe_start: (x, y) 滑动起点
            swipe_end: (x, y) 滑动终点
            max_swipes: 最大滑动次数（安全兜底）
            diff_threshold: 帧差异阈值，低于此值视为"画面不动了"
            region: [x, y, w, h] 裁剪区域，只比较这个区域（加速+去噪）
            pre_delay: 滑动前等待
            post_delay: 滑动后等待画面稳定
        
        Returns:
            最后一张截图（尾部状态的画面）
        """
        if swipe_start is None or swipe_end is None:
            raise ValueError("必须指定 swipe_start 和 swipe_end")
        
        prev = None
        last_shot = None
        
        for i in range(max_swipes):
            # 滑动（第一次不滑，先拍一帧）
            if prev is not None:
                self.input_handler.swipe(*swipe_start, *swipe_end)
                time.sleep(post_delay)
            else:
                time.sleep(pre_delay)
            
            current = self.input_handler.capture_screenshot()
            last_shot = current
            
            if prev is not None:
                diff = self._frame_diff(prev, current, region)
                self.logger.info(f"  [滑{i+1}] 帧差异={diff:.1f} 阈值={diff_threshold}")
                
                if diff < diff_threshold:
                    self.logger.info(f"  → 画面已稳定，共滑动{i+1}次，到达尾部")
                    return current
            
            prev = current
        
        self.logger.warning(f"  ⚠️ 已达最大滑动次数({max_swipes})，强制停止")
        return last_shot
    
    def scroll_and_click(
        self,
        direction: str,
        swipe_start,
        swipe_end,
        click_pos: tuple,
        max_swipes: int = 10,
        diff_threshold: float = 5.0,
        region: Optional[list] = None,
    ) -> bool:
        """滚动到底后，点击固定位置。返回是否成功的指示。"""
        final = self.scroll_to_tail(
            direction=direction,
            swipe_start=swipe_start,
            swipe_end=swipe_end,
            max_swipes=max_swipes,
            diff_threshold=diff_threshold,
            region=region,
        )
        # 点击固定位置
        self.input_handler.click(*click_pos)
        return True
    
    @staticmethod
    def _frame_diff(
        im1: Image.Image,
        im2: Image.Image,
        region: Optional[list] = None,
    ) -> float:
        """计算两帧之间的差异度。
        
        原理：两帧灰度图在相同区域的像素绝对值差均值。
        数值越低 → 画面越相似。
        典型值：
          - 完全相同: 0.0
          - 轻微UI变动: 1.0-3.0
          - 大幅场景切换: 20.0-80.0
          - 完全不同的画面: 100.0+
        
        Args:
            im1, im2: PIL Image（全屏截图）
            region: [x, y, w, h] 裁剪区域，None=全屏
        
        Returns:
            差异均值 (0~255)
        """
        # 裁剪
        if region:
            x, y, w, h = region
            im1 = im1.crop((x, y, x + w, y + h))
            im2 = im2.crop((x, y, x + w, y + h))
        
        # 转灰度 + numpy
        arr1 = np.array(im1.convert("L"), dtype=float)
        arr2 = np.array(im2.convert("L"), dtype=float)
        
        # MSE (Mean Squared Error)
        mse = float(np.mean((arr1 - arr2) ** 2))
        # RMSE (Root Mean Squared Error) — 更直观
        rmse = np.sqrt(mse)
        return rmse
    
    @staticmethod
    def image_entropy(im: Image.Image, region: Optional[list] = None) -> float:
        """计算图像的 Shannon 熵。
        
        熵值 = -Σ(p * log2(p))，其中 p 是每个灰度级的概率。
        纯色背景帧数低，内容丰富画面熵值高。
        
        可以用来判断滑动后画面是"卡在空白页"还是"有内容"。
        """
        if region:
            x, y, w, h = region
            im = im.crop((x, y, x + w, y + h))
        
        hist = im.convert("L").histogram()
        total = sum(hist)
        if total == 0:
            return 0.0
        
        entropy = -sum(
            p / total * __import__("math").log2(p / total)
            for p in hist if p > 0
        )
        return entropy
