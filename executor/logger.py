# coding: utf-8
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime

from globals import LOG_DIR

class LALCLogger:
    def __init__(self):
        # 初始化日志记录器
        self.logger = logging.getLogger('lalc_logger')
        self.logger.setLevel(logging.DEBUG)  # 设置日志记录器的最低级别

        # 日志格式
        log_format = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')

        # 获取当前日期
        current_date = datetime.now().strftime("%y-%m-%d")

        # 全量日志（DEBUG及以上级别）
        debug_log_filename = f"{LOG_DIR}/{current_date}_task_debug.log"
        self.debug_handler = TimedRotatingFileHandler(
            debug_log_filename, when='midnight', interval=1, backupCount=7,encoding="utf-8"
        )
        self.debug_handler.setFormatter(log_format)
        self.debug_handler.setLevel(logging.DEBUG)

        # INFO及以上级别日志
        info_log_filename = f"{LOG_DIR}/{current_date}_task_info.log"
        self.info_handler = TimedRotatingFileHandler(
            info_log_filename, when='midnight', interval=1, backupCount=7,encoding="utf-8"
        )
        self.info_handler.setFormatter(log_format)
        self.info_handler.setLevel(logging.INFO)


        # WARNING及以上级别日志
        Warning_log_filename = f"{LOG_DIR}/{current_date}_task_warning.log"
        self.warning_handler = TimedRotatingFileHandler(
            Warning_log_filename, when='midnight', interval=1, backupCount=7,encoding="utf-8"
        )
        self.warning_handler.setFormatter(log_format)
        self.warning_handler.setLevel(logging.WARNING)

        # 添加处理器
        self.logger.addHandler(self.debug_handler)
        self.logger.addHandler(self.info_handler)
        self.logger.addHandler(self.warning_handler)

    def log_task(self, level, task_name, status, msg=''):
        """
        记录任务日志
        :param level: 日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL）
        :param task_name: 任务名称
        :param status: 任务状态（如 STARTED, COMPLETED, FAILED 等）
        :param msg: 附加信息
        """
        log_msg = f"[{task_name}] {status}"
        if msg:
            log_msg += f" | {msg}"

        # 根据日志级别调用对应的日志方法
        if level == 'DEBUG':
            self.logger.debug(log_msg)
        elif level == 'INFO':
            self.logger.info(log_msg)
        elif level == 'WARNING':
            self.logger.warning(log_msg)
        elif level == 'ERROR':
            self.logger.error(log_msg)
        elif level == 'CRITICAL':
            self.logger.critical(log_msg)
        else:
            self.logger.error(f"Unexpected log_level:{level}")

        # 确保日志实时写入文件
        for handler in self.logger.handlers:
            handler.flush()

# 单例日志对象
lalc_logger = LALCLogger()