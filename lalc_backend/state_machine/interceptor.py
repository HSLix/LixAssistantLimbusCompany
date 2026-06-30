"""
错误拦截器 — 替换旧每 tick 的模板匹配轮询

原理：
  旧方案：每个 pipeline tick（每 1.1s）都截图 → 匹配 6-8 个错误模板 → 全空 → 继续
  新方案：只在关键操作后检查，用截图 hash 变化判断是否卡住。
  
  卡住检测流程：
    1. 每 N 个状态切换，截一张图
    2. 与上一次截图比较差异（SSIM / RMSE）
    3. 如果画面不动超过 stuck_threshold 秒 → 触发旧 error_handler
    4. 旧 error_handler 跑模板匹配 + OCR 检测弹窗
"""
import time
import logging
from typing import Optional
import hashlib


class ErrorInterceptor:
    """轻量错误拦截器。
    
    不每 tick 检查。只在以下情况触发：
    1. 状态切换计数到达阈值（默认 5）
    2. 屏幕卡住检测（连续 N 秒截图不变，差异 < threshold）
    3. 旧 OCR 弹窗 handler 主动触发
    """
    
    def __init__(self, check_interval: int = 5, stuck_threshold: float = 30.0,
                 diff_threshold: float = 2.0):
        """
        Args:
            check_interval: 每多少次状态切换截一张图比较
            stuck_threshold: 屏幕卡住秒数阈值
            diff_threshold: 帧差异阈值（RMSE），低于此值认为画面没变
        """
        self.logger = logging.getLogger(__name__)
        self.check_interval = check_interval
        self.stuck_threshold = stuck_threshold
        self.diff_threshold = diff_threshold
        self._tick_count = 0
        self._last_hash: Optional[str] = None
        self._last_hash_time: float = 0.0
        self._stuck_start: Optional[float] = None
        self._last_error_check: float = 0.0
        self._error_check_cooldown: float = 5.0
    
    def tick(self) -> Optional[str]:
        """每状态切换调用一次。
        
        Returns:
            None 一切正常
            str  "stuck"（画面不动超过阈值，需要触发错误处理）
        """
        self._tick_count += 1
        if self._tick_count % self.check_interval != 0:
            return None
        
        now = time.time()
        if now - self._last_error_check < self._error_check_cooldown:
            return None
        self._last_error_check = now
        
        return self._detect_stuck()
    
    def _detect_stuck(self) -> Optional[str]:
        """检测屏幕是否卡住。
        
        用快速截图 hash 判断画面是否长时间不变。
        如果超时 → 返回 "stuck" 触发旧 error_handler。
        """
        try:
            from input.input_handler import input_handler
            current = input_handler.capture_screenshot()
            
            # 快速 hash（取中心区域前 1KB 的 md5）
            import io
            buf = io.BytesIO()
            # 只计算画面中心 400x300 区域的 hash（去 UI 边框）
            w, h = current.size
            cx, cy = w // 2, h // 2
            region = current.crop((cx - 200, cy - 150, cx + 200, cy + 150))
            region.save(buf, format='PNG')
            current_hash = hashlib.md5(buf.getvalue()).hexdigest()
            
            now = time.time()
            
            if self._last_hash is not None and current_hash == self._last_hash:
                # 画面没变
                if self._stuck_start is None:
                    self._stuck_start = now
                elif now - self._stuck_start >= self.stuck_threshold:
                    self.logger.warning(
                        f"[拦截器] 画面卡住 {now - self._stuck_start:.0f}s "
                        f"(阈值 {self.stuck_threshold}s)，触发错误处理"
                    )
                    self._stuck_start = None
                    return "stuck"
            else:
                # 画面有变化 → 重置卡住计时
                self._stuck_start = None
            
            self._last_hash = current_hash
            self._last_hash_time = now
            
        except Exception as e:
            self.logger.warning(f"[拦截器] 截图检测异常: {e}")
        
        return None
    
    def force_check(self) -> Optional[str]:
        """强制全量错误检查（由外部逻辑或 OCR 弹窗后调用）。"""
        self._stick_start = None
        return "stuck"  # 强制触发旧错误处理
