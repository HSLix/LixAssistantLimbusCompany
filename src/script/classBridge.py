# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/9/16 9:25
* File  : classScript.py
* Project   :LixAssistantLimbusCompany
* Function  :作为输入信息与脚本执行的桥梁，传递信息
'''
from sys import exc_info
from traceback import format_exception
from threading import Thread, Lock
from src.error.myError import *
from src.log.myLog import myLog
from src.script.scheme import scriptTasks
import globalVar








class _bridgeGuiAndScript(Thread):
    '''传递信息并作为一个可报告运行结果的线程'''
    __slots__ = ("exception", "exc_traceback", "LunacyToEnkephalin", "EXPCount",
                 "ThreadCount", "MirrorCount", "InitSwitch",
                 "PrizeSwitch", "MirrorSwitch", "ActivityCount",
                 "EXPFinishCount", "ThreadFinishCount", "MirrorFinishCount", "ActivityFinishCount")

    def __init__(self):
        '''构造函数'''
        super(_bridgeGuiAndScript, self).__init__()
        globalVar.exitCode = 0
        self.exception = None
        self.exc_traceback = ''
        
        
        

    def run(self):
        '''捕捉错误并更改globalVar.exitCode'''
        lock = Lock()
        globalVar.exitCode = 0

        # myLog("debug", "globalVar.exitCode：" + str(globalVar.exitCode))

        try:
            self._run()
        except screenScaleError as e:
            with lock:
                globalVar.exitCode = 13
            self.exception = e
        except previousClaimRewardError as e:
            with lock:
                globalVar.exitCode = 12
            self.exception = e
        except userStopError as e:
            with lock:
                globalVar.exitCode = -1
            self.exception = e
        except mirrorInProgressError as e:
            with lock:
                globalVar.exitCode = 11
            self.exception = e
        except noSavedPresetsError as e:
            with lock:
                globalVar.exitCode = 10
            self.exception = e
        except unexpectNumError as e:
            with lock:
                globalVar.exitCode = 9
            self.exception = e
        except cannotOperateGameError as e:
            with lock:
                globalVar.exitCode = 8
            self.exception = e
        except netWorkUnstableError as e:
            with lock:
                globalVar.exitCode = 7
            self.exception = e
        except backMainWinError as e:
            with lock:
                globalVar.exitCode = 6
            self.exception = e
        except withOutGameWinError as e:
            with lock:
                globalVar.exitCode = 5
            self.exception = e
        except notWaitError as e:
            with lock:
                globalVar.exitCode = 4
            self.exception = e
        except withOutPicError as e:
            with lock:
                globalVar.exitCode = 3
            self.exception = e
        except withOutAdminError as e:
            with lock:
                globalVar.exitCode = 2
            self.exception = e
        except Exception as e:
            with lock:
                globalVar.exitCode = 1
            self.exception = e
        finally:
            self.exc_traceback = ''.join(
                format_exception(*exc_info()))
            myLog('error', self.exc_traceback)

    def kill(self):
        '''终止函数'''
        '''判定为用户手动终止'''
        globalVar.exitCode = -1

    @staticmethod
    def getExitCode():
        '''globalVar.exitCode向外传值接口'''
        exitCode = globalVar.exitCode
        return exitCode

    def _run(self):
        '''脚本内容'''
        scriptTasks()

