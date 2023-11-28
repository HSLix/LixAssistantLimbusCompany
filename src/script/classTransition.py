# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/11/25 22:46
* File  : classTransition.py
* Project   :LixAssistantLimbusCompany
* Function  :负责脚本任务中各任务间过渡的类
'''

from src.script.classScript import _script,checkAndExit,beginAndFinishLog
from src.log.myLog import myLog
from src.error.myError import *
from src.common.myTime import mySleep

import globalVar


class _transition(_script):
    
    @checkAndExit
    @beginAndFinishLog
    def ScriptGameStart(self):
        '''进入游戏部分'''
        mySleep(1)
        self.cap_win()
        loopCount = 0
        while(not self.is_find("./pic/initMenu/Window.png", "MainMenuSign", 0.8)):

            self.cap_win()
            if( self.single_target_click("./pic/login/Clear all caches.png", "Clear all caches", 300, -300, 10, 1)):
                loopCount = 0
                continue
            elif(self.single_target_click("./pic/initMenu/downloadConfirm.png", "downloadConfirm", 0, 0, 1, 1, 0.9)):
                myLog("error", "It's too boring to wait! Call me later.")
                raise notWaitError("下载中，程序自动终止，请稍后再启动")
            elif(self.is_find("./pic/initMenu/NetWorkUnstable.png", "NetWorkUnstable", 0.8)):
                myLog("error", "NetWorkUnstable! Call me later.")
                raise netWorkUnstableError("网络不行，重开罢")
            elif(self.is_find("./pic/Wait.png", "Wait Sign")):
                self.myWait()
                loopCount = 0
            else:
                self.errorRetry()

            loopCount += 1

            if(loopCount > 3):

                import sys
                msg = sys._getframe().f_code.co_name + " TimeOut!"
                myLog("warning", msg)
                break

        # 签到点击
        self.single_target_click("./pic/initMenu/rewardsConfirm.png",
                         "Rewards Acquired")
        self.single_target_click("./pic/initMenu/redCross.png", "Red Cross")

    

    @checkAndExit
    @beginAndFinishLog
    def ScriptGetPrize(self, PrizeSwitch):
        '''领取奖励'''
        from src.script.classPrize import _getPrize
        prize = _getPrize()

        prize.getPrize(PrizeSwitch)

    @checkAndExit
    @beginAndFinishLog
    def convertPai(self):
        '''将体力转换绿饼'''
        self.ScriptBackToInitMenu()
        self.cap_win()
        self.single_target_click("./pic/initMenu/greenPai.png", "GreenPai")
        self.cap_win()
        self.single_target_click("./pic/initMenu/maxModule.png", "maxModule")
        self.single_target_click("./pic/initMenu/confirm.png", "confirm")
        self.single_target_click("./pic/initMenu/cancel.png", "cancel")

    def buyPaiOnce(self):
        '''每天第一次购买体力'''
        self.ScriptBackToInitMenu()
        self.cap_win()
        self.single_target_click("./pic/initMenu/greenPai.png", "GreenPai")
        self.cap_win()
        self.single_target_click("./pic/initMenu/UseLunary.png", "UseLunary")
        self.cap_win()
        if(self.is_find("./pic/initMenu/FirstBuy.png", "26Lunary", 0.85)):
            self.single_target_click("./pic/initMenu/confirm.png", "confirm")
        self.single_target_click("./pic/initMenu/cancel.png", "cancel")
        
    @checkAndExit
    @beginAndFinishLog
    def buyEnkephalin(self):
        '''购买脑啡肽'''
        if globalVar.exeCfg["LunacyToEnkephalinSwitch"] == 1:
            self.buyPaiOnce()
        # 后续可以加入购买多次脑啡肽的功能

    

