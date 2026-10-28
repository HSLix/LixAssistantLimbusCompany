"""进程内的薄启动入口：持有 GUI 生命周期和最终致命错误出口。"""

from __future__ import annotations

import logging
import signal
import sys
import threading
from pathlib import Path
from typing import Callable

from .errors import FATAL_MESSAGE, configure_logging
from .runtime import _exception_fields


class ApplicationLifecycle:
    """把未处理错误统一交给 GUI 主线程，启动失败时保留终端兜底。"""

    def __init__(self) -> None:
        self.failed = False
        self.dispatch_fatal: Callable[[str], None] | None = None
        self._presented = False
        self.pending_details = ""
        self.shutdown: Callable[[], None] | None = None
        self.restart: Callable[[], None] | None = None
        self._interrupt_requested = False

    def request_interrupt(self, signum, frame) -> None:
        """信号处理器只记录请求，避免打断 Qt 回调或在事件过滤器中创建弹窗。"""
        self._interrupt_requested = True

    def process_interrupt(self) -> None:
        """由 GUI 主线程的定时回调统一报告终端中断，重复 Ctrl+C 不重入弹窗。"""
        if self._interrupt_requested:
            self._interrupt_requested = False
            if not self.failed:
                error = KeyboardInterrupt("终端 Ctrl+C 请求退出 / Interrupted by terminal Ctrl+C")
                self.report_fatal(type(error), error, None)

    def report_fatal(self, error_type, error: BaseException, tb) -> None:
        """供主线程和后台线程的异常钩子共用，保留完整原始错误链。"""

        self.failed = True
        logging.getLogger(__name__).critical("Unhandled fatal error", exc_info=(error_type, error, tb))
        details = _exception_fields(error.with_traceback(tb))["traceback"]
        self.pending_details = details
        if self.dispatch_fatal is not None:
            self.dispatch_fatal(details)
        elif threading.current_thread() is threading.main_thread():
            self.present_fatal(details)

    def present_fatal(self, details: str) -> None:
        """只在 GUI 主线程展示一次；报告失败也请求退出已有 GUI。"""

        self.pending_details = ""
        if self._presented:
            return
        self._presented = True
        if not self.failed:
            logging.getLogger(__name__).critical("Fatal execution result: %s", details)
        self.failed = True
        app = None
        try:
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance() or QApplication([])
            from .gui import ErrorDialog

            from .i18n import tr
            ErrorDialog(tr("A fatal error occurred. The application cannot continue.\n"
                           "You can copy the original error information and report it to the developer."),
                        details, fatal=True).exec()
        except Exception:
            logging.getLogger(__name__).exception("Fatal dialog unavailable")
            print(FATAL_MESSAGE, file=sys.stderr)
            print(details, file=sys.stderr)
        finally:
            if app is not None:
                app.exit(1)


def run_application(
    start: Callable[[ApplicationLifecycle], int] | None = None, *, data_root: Path | None = None,
) -> int:
    """在 GUI 导入前建立错误保护；GUI 结束后恢复钩子并结束同一进程。"""

    lifecycle = ApplicationLifecycle()
    previous_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, lifecycle.request_interrupt)
    previous_sys, previous_thread = sys.excepthook, threading.excepthook
    sys.excepthook = lifecycle.report_fatal
    threading.excepthook = lambda args: lifecycle.report_fatal(args.exc_type, args.exc_value, args.exc_traceback)
    try:
        if data_root is None:
            from .application import default_data_root
            data_root = default_data_root()
        configure_logging(data_root)
        if start is None:
            from .gui import run_gui
            start = run_gui
        result = start(lifecycle)
        lifecycle.process_interrupt()

    except (Exception, KeyboardInterrupt) as error:
        lifecycle.report_fatal(type(error), error, error.__traceback__)
        result = 1
    finally:
        lifecycle.dispatch_fatal = None
        try:
            if lifecycle.shutdown is not None:
                lifecycle.shutdown()
        except Exception as error:
            lifecycle.report_fatal(type(error), error, error.__traceback__)
        finally:
            try:
                if lifecycle.pending_details:
                    lifecycle.present_fatal(lifecycle.pending_details)
            finally:
                sys.excepthook, threading.excepthook = previous_sys, previous_thread
                signal.signal(signal.SIGINT, previous_sigint)

    if not lifecycle.failed and lifecycle.restart is not None:
        try:
            lifecycle.restart()
        except Exception as error:
            lifecycle.report_fatal(type(error), error, error.__traceback__)
    return 1 if lifecycle.failed else result
