"""GUI 人工反馈的单次请求；跨线程只结算一次，结束后旧回调失效。"""

import threading


class FeedbackRequest:
    """绑定发起会话与轮次；取消不转换成 Confirm 或 Skip。"""

    def __init__(self, message, identity):
        self.message = message
        self.identity = identity
        self._lock = threading.Lock()
        self.done = threading.Event()
        self.result = None

    def finish(self, status, text=""):
        """仅首个有效答复可提交；空字符串是合法确认。"""
        if status not in {"confirmed", "skipped"} or not isinstance(text, str):
            raise ValueError("无效的人工反馈。")
        with self._lock:
            if self.done.is_set():
                return False
            self.result = {"status": status, "text": text if status == "confirmed" else ""}
            self.done.set()
            return True

    def close(self):
        """作废未完成请求，防止迟到答复在下一轮生效。"""
        with self._lock:
            self.done.set()
