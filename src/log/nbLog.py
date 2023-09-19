'''
* Author: LuYaoQi
* Time  : 2023/9/18 14:34
* File  : nbLog.py
* Project   :LixAssistantLimbusCompany
* Function  :日志记录
'''

from nb_log import get_logger


'''记录debug及以上级别日志'''
debugLogger =  get_logger("debugLogger", 
                          log_path = "D:\Code\LimbusCompanyAssistant\log",
                          log_level_int = 10, 
                          is_add_stream_handler=False, 
                          log_filename = "debugLog.log", 
                          formatter_template = 2,
                          log_file_handler_type = 1)


'''记录warning及以上级别日志'''
warningLogger =  get_logger("warningLogger", 
                          log_path = "D:\Code\LimbusCompanyAssistant\log",
                          log_level_int = 30, 
                          is_add_stream_handler=False, 
                          log_filename = "warningLog.log", 
                          formatter_template = 2,
                          log_file_handler_type = 1)



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
        warningLogger.debug(msg)
    elif(type == "info"):
        debugLogger.info(msg)
        warningLogger.info(msg)
    elif(type == "warning"):
        debugLogger.warning(msg)
        warningLogger.warning(msg)
    elif(type == "error"):
        debugLogger.error(msg)
        warningLogger.error(msg)
    elif(type == "critical"):
        debugLogger.critical(msg)
        warningLogger.critical(msg)



