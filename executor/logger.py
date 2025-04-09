# coding: utf-8
from logging import getLogger, DEBUG, Formatter, INFO, WARNING, ERROR
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime, timedelta
import os
import glob
from PyQt5.QtCore import pyqtSignal, QObject

from globals import LOG_DIR

class DateOnlyRotatingFileHandler(TimedRotatingFileHandler):
    """自定义处理器，仅按日期分割日志文件，不添加数字后缀"""
    def __init__(self, filename_prefix, when='midnight', interval=1, backupCount=0, encoding=None):
        self.filename_prefix = filename_prefix
        self.log_dir = LOG_DIR
        self.current_date = datetime.now().strftime("%y-%m-%d")
        filename = self._get_current_filename()
        
        os.makedirs(self.log_dir, exist_ok=True)


        # 注意：backupCount设为0表示禁用自动编号
        super().__init__(filename, when=when, interval=interval, 
                        backupCount=0, encoding=encoding)
    
    def _get_current_filename(self):
        """生成带日期的文件名"""
        return f"{self.log_dir}/{self.current_date}_{self.filename_prefix}.log"
    
    def doRollover(self):
        """简化版轮换逻辑：仅关闭当前文件并创建新日期文件"""
        if self.stream:
            self.stream.close()
            self.stream = None
        
        # 更新日期并创建新文件
        self.current_date = datetime.now().strftime("%y-%m-%d")
        self.baseFilename = self._get_current_filename()
        self.stream = self._open()

class LALCLogger(QObject):
    deleteOutdatedLogSignal = pyqtSignal()
    
    def __init__(self, retain_days=7):
        super().__init__()


        self.logger = getLogger('lalc_logger')
        self.logger.setLevel(DEBUG)
        log_format = Formatter('%(asctime)s | %(levelname)s | %(message)s')

        # 初始化处理器（backupCount=0 禁用编号）
        self.debug_handler = DateOnlyRotatingFileHandler(
            "task_debug", when='midnight', backupCount=0, encoding="utf-8"
        )
        self.debug_handler.setFormatter(log_format)
        self.debug_handler.setLevel(DEBUG)

        self.info_handler = DateOnlyRotatingFileHandler(
            "task_info", when='midnight', backupCount=0, encoding="utf-8"
        )
        self.info_handler.setFormatter(log_format)
        self.info_handler.setLevel(INFO)

        self.warning_handler = DateOnlyRotatingFileHandler(
            "task_warning", when='midnight', backupCount=0, encoding="utf-8"
        )
        self.warning_handler.setFormatter(log_format)
        self.warning_handler.setLevel(WARNING)

        self.error_handler = DateOnlyRotatingFileHandler(
            "task_error", when='midnight', backupCount=0, encoding="utf-8"
        )
        self.error_handler.setFormatter(log_format)
        self.error_handler.setLevel(ERROR)

        self.logger.addHandler(self.debug_handler)
        self.logger.addHandler(self.info_handler)
        self.logger.addHandler(self.warning_handler)
        self.logger.addHandler(self.error_handler)

        self.retain_days = retain_days
        # self._clean_old_logs()

    

    def clean_old_logs(self):
        """清理超过retain_days的旧日志"""
        cutoff_date = (datetime.now() - timedelta(days=self.retain_days)).strftime("%y-%m-%d")
        is_delete = False
        for prefix in ["task_debug", "task_info", "task_warning", "task_error"]:
            for log_path in glob.glob(f"{LOG_DIR}/*_{prefix}.log"):
                file_date = os.path.basename(log_path).split("_")[0]
                if file_date < cutoff_date:
                    is_delete = True
                    self.logger.debug("Delete the old log {log_path} Successfully.")
                    os.remove(log_path)
        if (is_delete):
            self.deleteOutdatedLogSignal.emit()

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