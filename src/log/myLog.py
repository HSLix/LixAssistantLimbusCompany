# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/9/18 14:34
* File  : myLog.py
* Project   :LixAssistantLimbusCompany
* Function  :日志记录
'''

from logging import DEBUG, INFO, WARNING
from kuai_log import get_logger 
from src.error.myError import logTypeError


'''记录debug及以上级别日志'''
debugLogger =  get_logger(name="debugLogger", 
                          log_path = ".\\log",
                          level=DEBUG,
                          is_add_stream_handler=True, 
                          log_filename = "debugLog.log", 
                          is_add_file_handler=True)


'''记录info及以上级别日志'''
infoLogger =  get_logger(name="infoLogger", 
                          log_path = ".\\log",
                          level=INFO,
                          is_add_stream_handler=False, 
                          log_filename = "infoLog.log", 
                          is_add_file_handler=True)


'''记录warning及以上级别日志'''
warningLogger =  get_logger(name="warningLogger", 
                          log_path = ".\\log",
                          level=WARNING,
                          is_add_stream_handler=False, 
                          log_filename = "warningLog.log", 
                          is_add_file_handler=True)



def beginAndFinishLog(func):
    '''一个任务开始与结束的日志'''
    def wrapper(*args, **kw):
        msg = "Begin " + func.__name__
        myLog("info", msg)

        #真正函数
        func(*args, **kw)

        msg = "Finish " + func.__name__
        myLog("info", msg)
    return wrapper



def myLog(type, msg):
    '''对日志函数的小包装
    :param type: 日志级别
    :param msg: 日志信息
    '''
    if(type == "debug"):
        debugLogger.debug(msg)
        infoLogger.debug(msg)
        warningLogger.debug(msg)
    elif(type == "info"):
        debugLogger.info(msg)
        infoLogger.info(msg)
        warningLogger.info(msg)
    elif(type == "warning"):
        debugLogger.warning(msg)
        infoLogger.warning(msg)
        warningLogger.warning(msg)
    elif(type == "error"):
        debugLogger.error(msg)
        infoLogger.error(msg)
        warningLogger.error(msg)
    elif(type == "critical"):
        debugLogger.critical(msg)
        infoLogger.critical(msg)
        warningLogger.critical(msg)
    else:
        raise logTypeError("出现未知类型日志，请及时检查代码")



