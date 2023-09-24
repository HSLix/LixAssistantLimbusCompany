'''
* Author: LuYaoQi
* Time  : 2023/9/16 9:25
* File  : classScript.py
* Project   :LixAssistantLimbusCompany
* Function  :脚本流程归类化
'''
import sys
import traceback
from threading import Thread, Lock
from src.common.getAdmin import getAdmin
from src.common.initWin import initWin
from src.log.nbLog import myLog, beginAndFinishLog
from src.error.myError import *

from src.common import getPic, autoFindOrClick as afc
from src.common.myTime import myTimeSleep
from src.script.myWait import myWait
from src.script.battle import dailyBattlePart
from src.script.event import eventPart





# 退出状态
exitCode = 0 




def checkAndExit(func):
        '''检查ExitCode符合条件结束该线程（程序）'''
        global exitCode
        def wrapper(*args, **kw):
            if(exitCode != 0):
                raise userStopError("用户主动终止程序")

            #真正函数
            func(*args, **kw)

            if(exitCode != 0):
                raise userStopError("用户主动终止程序")
                
        return wrapper


class _mainScript(Thread):
    __slots__ = ("exception", "exc_traceback", "EXPCount",
                 "ThreadCount", "MirrorCount", "InitSwitch",
                 "PrizeSwitch", "MirrorSwitch", "ActivityCount",
                 "EXPFinishCount", "ThreadFinishCount", "MirrorFinishCount", "ActivityFinishCount")
    
    def __init__(self,EXPCount = 0,ThreadCount = 0,MirrorCount = 0, InitSwitch = 0, PrizeSwitch = 0, MirrorSwitch = 0, ActivityCount = 0):
        '''构造函数'''
        super(_mainScript, self).__init__()
        global exitCode
        exitCode = 0
        self.exception = None
        self.exc_traceback = ''
        self.EXPCount = EXPCount   
        self.ThreadCount = ThreadCount
        self.MirrorCount = MirrorCount
        self.InitSwitch = InitSwitch
        self.PrizeSwitch = PrizeSwitch
        self.MirrorSwitch = MirrorSwitch
        self.ActivityCount = ActivityCount



    def run(self):
        '''捕捉错误并更改exitCode'''
        lock = Lock()
        global exitCode
        exitCode = 0
        myLog("debug", "ExitCode：" + str(exitCode))
        try:
            self._run()
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
            self.exc_traceback = ''.join(traceback.format_exception(*sys.exc_info()))

    
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
        self.scriptTasks()


    






    @checkAndExit
    @beginAndFinishLog
    def scriptTasks(self):
        '''一整套脚本流程'''
        # 从子类引入类
        from src.script.classLux import _Luxcavation
        from src.script.classMir import _Mirror
        from src.script.classPrize import _getPrize

        lux = _Luxcavation(self.EXPCount, self.ThreadCount)
        mir = _Mirror(self.MirrorSwitch, self.MirrorCount)
        prize = _getPrize(self.PrizeSwitch)

        # 重置完成次数
        self.EXPFinishCount = 0
        self.ThreadFinishCount = 0
        self.MirrorFinishCount = 0
        self.ActivityFinishCount = -1

        # 全流程
        getAdmin()
        initWin(self.InitSwitch)
        self.ScriptGameStart()
        self.ScriptBackToInitMenu()
        self.buyFirstPai()
        self.convertPai()
        lux.ScriptTaskEXP()
        # 每完成一次任务，获取完成次数
        self.EXPFinishCount = lux.getEXPFinishCount()
        lux.ScriptTaskThread()
        self.ThreadFinishCount = lux.getThreadFinishCount()
        mir.start()
        self.MirrorFinishCount = mir.getMirrorFinishCount()
        prize.getPrize()

        
        
        
        
   


    @checkAndExit
    @beginAndFinishLog
    def ScriptGameStart(self):
        '''进入游戏部分'''
        myTimeSleep(1)
        getPic.winCap()
        loopCount = 0
        while(not afc.autoFind("./pic/initMenu/Window.png", "MainMenuSign", 0.8)):
            
            getPic.winCap()
            if( afc.autoSinClick("./pic/initMenu/FaceTheSinSaveTheEGO.png", "84启动!", 0, 0, 10, 1, 0.998)):
                loopCount = 0
                continue
            elif(afc.autoSinClick("./pic/initMenu/downloadConfirm.png", "downloadConfirm", 0, 0, 1, 1, 0.9)):
                myLog("error","It's too boring to wait! Call me later.")
                raise notWaitError("下载中，程序自动终止，请稍后再启动")
            elif(afc.autoFind("./pic/initMenu/NetWorkUnstable.png", "NetWorkUnstable", 0.8)):
                myLog("error","NetWorkUnstable! Call me later.")
                raise netWorkUnstableError("网络不行，重开罢")
            elif(afc.autoFind("./pic/Wait.png", "Wait Sign")):
                myWait()
                loopCount = 0
            else:
                self.errorRetry()

            loopCount += 1

            if(loopCount > 3):
                
                import sys
                msg = sys._getframe().f_code.co_name + " TimeOut!"
                myLog("warning",msg)
                break

        #签到点击
        afc.autoSinClick("./pic/initMenu/rewardsConfirm.png", "Rewards Acquired")
        afc.autoSinClick("./pic/initMenu/redCross.png", "Red Cross")


    
    @checkAndExit
    @beginAndFinishLog
    def ScriptBackToInitMenu(self):
        '''返回主界面'''
        loopCount = 0
        getPic.winCap()
        while( not afc.autoSinClick("./pic/initMenu/Window.png", "mainMenuSign")):
            
            #战斗或事件中
            if(afc.autoSinClick("./pic/battle/WinRate.png", "battleSign1")or\
            afc.autoSinClick("./pic/battle/Start.png", "battleSign2")):
                dailyBattlePart()
                loopCount = 0
            elif(afc.autoFind("./pic/event/Skip.png", "Skip")):
                # 事件过程
                eventPart()
                loopCount = 0
            elif afc.autoSinClick("./pic/battle/confirm.png", "Confirm"):
                # 战斗结算
                loopCount = 0   
            elif afc.autoSinClick("./pic/battle/Confirm.png", "LevelUpConfirm"):
                # 升级结算
                loopCount = 0
            elif afc.autoSinClick("./pic/scene/QuitScene.png", "QuitScene"):
                # 剧情退出
                getPic.winCap()
                afc.autoSinClick("./pic/scene/SkipScene.png", "SkipScene")
                getPic.winCap()
                afc.autoSinClick("./pic/scene/SkipConfirm.png", "SkipConfirm")
                loopCount = 0
            elif(afc.autoSinClick("./pic/team/LeftArrow.png", "ExitPrepareTeam")):
                # 组队过程中
                loopCount = 0
            elif(afc.autoSinClick("./pic/mirror/mirror2/ego/egoGift.png", "ChooseEgoGift")):
                # 选择ego
                getPic.winCap()
                afc.autoSinClick("./pic/mirror/mirror2/ego/SelectEGOGift.png", "SelectEGOGift", 0, 0, 6)
                loopCount = 0

            #等待加载情况
            if(afc.autoFind("./pic/Wait.png", "Wait Sign")):
                    myWait()

            getPic.winCap()
            #经验本或者纽本的情况
            if(afc.autoFind("./pic/luxcavation/ThreadEntrance.png", "ThreadEntrance")):
                afc.autoSinClick("./pic/goBack/leftArrow.png", "leftArrow")
                loopCount = 0
            #镜牢的情况
            elif(afc.autoFind("./pic/mirror/mirror2/way/mirror2MapSign.png", "mirror2MapSign")\
                or afc.autoFind("./pic/mirror/mirror2/EGOGiftOwned.png", "EGOGiftOwned")):
                afc.autoSinClick("./pic/mirror/mirror2/Gear.png", "ExitGear")
                getPic.winCap()
                afc.autoSinClick("./pic/mirror/mirror2/LeftArrow.png", "ToWindow")
                getPic.winCap()
                afc.autoSinClick("./pic/mirror/mirror2/Confirm.png", "Confirm", 0, 0, 5)
                loopCount = 0
            #在循环里必须有应对错误的情况
            self.errorRetry()
            getPic.winCap()

            #第二次也不行时，一定是出现了脚本中没有的情况
            if loopCount > 2:
                myLog("warning","Can't Find The Way MainMenu. Must be Unknown Situation. Please Restart the Game and the Script")
                raise backMainWinError("无法返回主界面，不能进行下一步")


            loopCount += 1


    @checkAndExit
    @beginAndFinishLog
    def ScriptGetPrize(self,PrizeSwitch):
        '''领取奖励'''
        from src.script.classPrize import _getPrize
        prize = _getPrize()

        
        prize.getPrize(PrizeSwitch)







    @checkAndExit
    @beginAndFinishLog
    def convertPai(self):
        '''将体力转换绿饼'''
        self.ScriptBackToInitMenu()
        getPic.winCap()
        afc.autoSinClick("./pic/initMenu/greenPai.png", "GreenPai")
        getPic.winCap()
        afc.autoSinClick("./pic/initMenu/maxModule.png", "maxModule")
        afc.autoSinClick("./pic/initMenu/confirm.png", "confirm")
        afc.autoSinClick("./pic/initMenu/cancel.png", "cancel")


    @checkAndExit
    @beginAndFinishLog
    def buyFirstPai(self):
        '''每天第一次购买体力'''
        self.ScriptBackToInitMenu()
        getPic.winCap()
        afc.autoSinClick("./pic/initMenu/greenPai.png", "GreenPai")
        getPic.winCap()
        afc.autoSinClick("./pic/initMenu/UseLunary.png", "UseLunary")
        getPic.winCap()
        if(afc.autoFind("./pic/initMenu/FirstBuy.png", "FirstBuy", 0.95)):
            afc.autoSinClick("./pic/initMenu/confirm.png", "confirm")
        afc.autoSinClick("./pic/initMenu/cancel.png", "cancel")


    @checkAndExit
    @beginAndFinishLog
    def errorRetry(self):
        '''
        点击重试按钮，同时监测重试失败并返回错误
        '''
        getPic.winCap() 
        if(afc.autoFind("./pic/error/CannotOperateGame.png", "CannotOperateGame")):
            raise cannotOperateGameError("网络多次重连失败，请重启游戏")
        elif(afc.autoFind("./pic/error/errorOccurred.png", "errorSign")):
            afc.autoSinClick("./pic/error/Retry.png", "Retry", 0, 0, 10)
        




