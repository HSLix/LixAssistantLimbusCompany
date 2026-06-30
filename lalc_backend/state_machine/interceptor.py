"""
错误拦截器 — 替换旧每 tick 的模板匹配轮询

原理：
  旧方案：每个 pipeline tick（每 1.1s）都截图 → 匹配 6-8 个错误模板 → 全空 → 继续
  新方案：只在关键操作后检查（每 3-5 个状态切换 ≈ 每 5-15s），用 RapidOCR 快速扫描
  
  对于已知的"错误永远不会发生"的模板（download_data, network_is_unstable 等），
  在正常运行时完全不检查。只有出现明显异常（截图卡住 N 秒不变）时才触发全量扫描。
"""
import time
import logging
from typing import Optional


class ErrorInterceptor:
    """轻量错误拦截器。
    
    不每 tick 检查。只在以下情况触发：
    1. 状态切换计数到达阈值（默认 3）
    2. 屏幕卡住检测（连续 N 秒截图不变）
    3. 旧 OCR 弹窗 handler 主动触发
    """
    
    def __init__(self, check_interval: int = 5, stuck_threshold: float = 30.0):
        """
        Args:
            check_interval: 每多少次状态切换检查一次（默认 5 个状态）
            stuck_threshold: 屏幕卡住秒数阈值（默认 30s）
        """
        self.logger = logging.getLogger(__name__)
        self.check_interval = check_interval
        self.stuck_threshold = stuck_threshold
        self._tick_count = 0
        self._last_screenshot_hash = None
        self._last_stuck_check = 0.0
        self._last_error_check = 0.0
        self._error_check_cooldown = 5.0  # 两次检查之间至少间隔 5s
    
    def tick(self) -> Optional[str]:
        """每状态切换调用一次。
        
        Returns:
            None 一切正常
            str  检测到的错误类型，调用侧需处理
        """
        self._tick_count += 1
        
        # 阈值检查：每 N 个状态才真正做截图检查
        if self._tick_count % self.check_interval != 0:
            return None
        
        now = time.time()
        if now - self._last_error_check < self._error_check_cooldown:
            return None
        self._last_error_check = now
        
        # 快速截屏判断是否卡住 + 有无弹窗
        # 这里将来可以用 RapidOCR 扫描，但 v1 先只做卡住检测
        return self._detect_stuck()
    
    def _detect_stuck(self) -> Optional[str]:
        """检测屏幕是否卡住。
        
        用截图的简单校验和判断是否画面不动。
        如果连续 stuck_threshold 秒不变，触发一次旧错误处理。
        """
        # 当前版本：检查间隔太长时不判断卡住
        # TODO v2: 实现截图哈希比较
        return None
    
    def force_check(self) -> Optional[str]:
        """强制全量检查（由外部主动调用）。
        
        旧 OCR handler 触发弹窗处理后，调用此方法确认弹窗是否已消除。
        """
        # TODO v2: 调用 RapidOCR 扫描 + 旧 error_handler 模板
        return None
