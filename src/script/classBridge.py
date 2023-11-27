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

from src.script.scheme import scriptTasks








class _bridgeGuiAndScript(Thread):
    '''传递信息并作为一个可报告运行结果的线程'''
    __slots__ = ("exception", "exc_traceback", "LunacyToEnkephalin", "EXPCount",
                 "ThreadCount", "MirrorCount", "InitSwitch",
                 "PrizeSwitch", "MirrorSwitch", "ActivityCount",
                 "EXPFinishCount", "ThreadFinishCount", "MirrorFinishCount", "ActivityFinishCount")

    def __init__(self):
        '''构造函数'''
        super(_bridgeGuiAndScript, self).__init__()
        global exitCode
        exitCode = 0
        self.exception = None
        self.exc_traceback = ''
        
        
        

    def run(self):
        '''捕捉错误并更改exitCode'''
        lock = Lock()
        global exitCode
        exitCode = 0

        # myLog("debug", "ExitCode：" + str(exitCode))

        try:
            self._run()
        except screenScaleError as e:
            with lock:
                exitCode = 13
            self.exception = e
        except previousClaimRewardError as e:
            with lock:
                exitCode = 12
            self.exception = e
        except userStopError as e:
            with lock:
                exitCode = -1
            self.exception = e
        except mirrorInProgressError as e:
            with lock:
                exitCode = 11
            self.exception = e
        except noSavedPresetsError as e:
            with lock:
                exitCode = 10
            self.exception = e
        except unexpectNumError as e:
            with lock:
                exitCode = 9
            self.exception = e
        except cannotOperateGameError as e:
            with lock:
                exitCode = 8
            self.exception = e
        except netWorkUnstableError as e:
            with lock:
                exitCode = 7
            self.exception = e
        except backMainWinError as e:
            with lock:
                exitCode = 6
            self.exception = e
        except withOutGameWinError as e:
            with lock:
                exitCode = 5
            self.exception = e
        except notWaitError as e:
            with lock:
                exitCode = 4
            self.exception = e
        except withOutPicError as e:
            with lock:
                exitCode = 3
            self.exception = e
        except withOutAdminError as e:
            with lock:
                exitCode = 2
            self.exception = e
        except Exception as e:
            with lock:
                exitCode = 1
            self.exception = e
        finally:
            self.exc_traceback = ''.join(
                format_exception(*exc_info()))

    def kill(self):
        '''终止函数'''
        '''判定为正常终止'''
        global exitCode
        exitCode = -1

    @staticmethod
    def getExitCode():
        '''exitCode向外传值接口'''
        global exitCode
        return exitCode

    def _run(self):
        '''脚本内容'''
        scriptTasks()

