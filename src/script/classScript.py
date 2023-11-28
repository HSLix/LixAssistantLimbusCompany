# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/11/26
* File  : myGUI.py        
* Project   :LixAssistantLimbusCompany
* Function  :图形化交互界面            
'''

from src.script.classTask import _task, checkAndExit, beginAndFinishLog
from src.log.myLog import myLog
from src.error.myError import *
from src.common.myTime import mySleep
import globalVar

class _script(_task):
    __slots__ = {}
    '''此类会放各个子任务都很可能用得到的部分''' 

    def __init__(self):
       pass 
        
        



    @checkAndExit
    def errorRetry(self):
        '''
        点击重试按钮，同时监测重试失败并返回错误
        '''
        self.cap_win()
        if(self.is_find("./pic/error/CannotOperateGame.png", "CannotOperateGame")):
            raise cannotOperateGameError("网络多次重连失败，请重启游戏")
        elif(self.is_find("./pic/error/errorOccurred.png", "errorSign")):
            self.single_target_click("./pic/error/Retry.png", "Retry", 0, 0, 10)

    @checkAndExit
    @beginAndFinishLog
    def ScriptBackToInitMenu(self):
        '''返回主界面'''
        loopCount = 0
        self.cap_win()
        while(not self.single_target_click("./pic/initMenu/Window.png", "mainMenuSign")):

            # 战斗或事件中
            if(self.is_find("./pic/battle/WinRate.png", "battleSign1") or
               self.is_find("./pic/battle/Start.png", "battleSign2")):
                self.allWinRateBattle()
                loopCount = 0
            elif(self.is_find("./pic/event/Skip.png", "Skip")):
                # 事件过程
                self.eventPart()
                loopCount = 0
            elif self.single_target_click("./pic/battle/confirm.png", "Confirm"):
                # 战斗结算
                loopCount = 0
            elif self.single_target_click("./pic/battle/levelUpConfirm.png", "LevelUpConfirm"):
                # 升级结算
                loopCount = 0
            elif self.single_target_click("./pic/scene/QuitScene.png", "QuitScene"):
                # 剧情退出
                self.cap_win()
                self.single_target_click("./pic/scene/SkipScene.png", "SkipScene")
                self.cap_win()
                self.single_target_click("./pic/scene/SkipConfirm.png", "SkipConfirm")
                loopCount = 0
            elif(self.single_target_click("./pic/team/LeftArrow.png", "ExitPrepareTeam")):
                # 组队过程中
                loopCount = 0
            elif(self.single_target_click("./pic/mirror/mirror2/ego/egoGift.png", "ChooseEgoGift")):
                # 选择ego
                self.cap_win()
                self.single_target_click("./pic/mirror/mirror2/ego/SelectEGOGift.png", "SelectEGOGift", 0, 0, 6)
                loopCount = 0

            # 等待加载情况
            if(self.is_find("./pic/Wait.png", "Wait Sign")):
                self.myWait()

            self.cap_win()
            # 经验本或者纽本的情况
            if(self.is_find("./pic/luxcavation/ThreadEntrance.png", "ThreadEntrance")):
                self.single_target_click("./pic/goBack/leftArrow.png", "leftArrow")
                loopCount = 0
            # 镜牢的情况
            elif(self.is_find("./pic/mirror/mirror2/way/mirror2MapSign.png", "mirror2MapSign")
                 or self.is_find("./pic/mirror/mirror2/EGOGiftOwned.png", "EGOGiftOwned")):
                if self.single_target_click("./pic/mirror/mirror2/Gear.png", "ExitGear"):
                    self.cap_win()
                    self.single_target_click(
                        "./pic/mirror/mirror2/LeftArrow.png", "ToWindow")
                    self.cap_win()
                    self.single_target_click("./pic/mirror/mirror2/whiteConfirm.png", "Confirm", 0, 0, 5)
                    loopCount = 0
                elif self.single_target_click("./pic/mirror/mirror2/ClaimRewards.png","ClaimRewards", 0, 0, 0.7, 1, 0.7):
                    self.cap_win()
                    self.single_target_click("./pic/mirror/mirror2/Receive.png","Receive")
                    self.cap_win()
                    if self.single_target_click("./pic/mirror/mirror2/whiteConfirm.png","FirstConfirm"):
                        self.cap_win()
                        if self.single_target_click("./pic/mirror/mirror2/way/Confirm.png","SecondConfirm"):
                            loopCount = 0
                            
            #在循环里必须有应对错误的情况
            self.errorRetry()
            self.cap_win()

            # 第二次也不行时，一定是出现了脚本中没有的情况
            if loopCount > 2:
                myLog(
                    "warning", "Can't Find The Way MainMenu. Must be Unknown Situation. Please Restart the Game and the Script")
                raise backMainWinError("无法返回主界面，不能进行下一步")


            loopCount += 1

    def allWinRateBattle(self):
        '''全部采用WinRate战斗'''
        self.cap_win()
        loopCount = 0
        while(True):
            self.cap_win()
            condition = False
            if (self.is_find("./pic/battle/WinRate.png", "WinRate") or 
                self.is_find("./pic/battle/Start.png", "StartBattle")):

                self.press_key("p")
                #self.single_target_click("./pic/battle/WinRate.png", "WinRate")
                self.press_key("enter")
                condition = True
            elif(self.is_find("./pic/battle/battlePause.png", "Fighting Sign")):
                mySleep(3)
                condition = True
            elif(self.is_find("./pic/event/Skip.png", "Skip")):
                self.eventPart()
                condition = True
            elif(self.is_find("./pic/Wait.png", "Wait Sign")):
                self.myWait()
                condition = True
            mySleep(1)
            if(not condition):
                loopCount += 1
                if(loopCount > 2):
                    break
                elif(self.single_target_click("./pic/battle/blackWordConfirm.png", "Level Increased!")):
                    loopCount = 0
                elif(self.single_target_click("./pic/battle/trianglePause.png", "Continue Fight!")):
                    loopCount = 0
            else:
                loopCount = 0

        
    @beginAndFinishLog
    def eventPart(self):
        '''处理含skip的一切事件
        :param condition: 是否有skip
        '''
        condition = True
        while(condition):
            
            self.cap_win()
            self.single_target_click("./pic/event/Skip.png", "Skip", 0, 0, 0.3, 3)
            
            #对判定事件的处理，优先择高概率
            self.cap_win()
            if(self.is_find("./pic/event/ChooseCheck.png","ChooseCheck")):
                if(self.single_target_click("./pic/event/veryhigh.png", "VeryHigh") or\
                    self.single_target_click("./pic/event/high.png", "High")or\
                    self.single_target_click("./pic/event/Normal.png", "Normal")or\
                    self.single_target_click("./pic/event/Low.png", "Low")or\
                    self.single_target_click("./pic/event/VeryLow.png", "VeryLow")):
                    self.cap_win()
                    self.single_target_click("./pic/event/Commence.png", "Commence")
                    mySleep(3)

            #事件出口
            self.cap_win()
            self.single_target_click("./pic/event/Continue.png", "Continue")
            self.single_target_click("./pic/event/Proceed.png", "Proceed")
            self.single_target_click("./pic/event/ToBattle.png", "ToBattle!")

            #没有点到事件出口的情况下跳转到对应异想体的专门处理
            if(self.is_find("./pic/event/Choices.png","Choices")):
                self.copeWithWhateverEvent()

            if(self.single_target_click("./pic/event/Leave.png", "Leave")):
                self.cap_win()
                self.single_target_click("./pic/mirror/mirror2/whiteConfirm.png", "Confirm")
            mySleep(1)

            if(not self.is_find("./pic/event/Skip.png", "Skip")):
                condition = False


    def copeWithWhateverEvent(self):
        '''获取事件类型，并做相应点击选择'''
        state = self.judWhatEvent()
        if(state == 0):
            self.eventChoice(2)
            self.eventChoice(1)
        elif(state == 1):
            self.eventChoice(1)
        elif(state == 2):
            self.eventChoice(2)
        elif(state == 3):
            self.eventChoice(2)
        elif(state == 4):
            self.eventChoice(1)
            self.eventChoice(2)


    def judWhatEvent(self):
        '''
        从截屏判断事件类型
        :param eventNum:事件类型代号
        '''
        eventNum = 0
        if(self.is_find("./pic/encounter/UnDeadMechine1.png", "UnDeadMechine1", 0.9)):
            eventNum = 1
        elif(self.is_find("./pic/encounter/UnDeadMechine2.png", "UnDeadMechine2", 0.9)):
            eventNum = 2
        elif(self.is_find("./pic/encounter/PinkShoes.png", "PinkShoes", 0.9)):
            eventNum = 3
        elif(self.is_find("./pic/encounter/RedKillClock.png", "RedKillClock", 0.9)):
            eventNum = 4
        

        return eventNum


    def eventChoice(self,switch = 0):
        '''包装了事件三个选择的点击位置'''
        if(switch == 1):
            self.single_target_click("./pic/event/Skip.png", "TheFirstChoice", 150, -100, 1.5)
        elif(switch == 2):
            self.single_target_click("./pic/event/Skip.png", "TheSecondChoice", 150, 0, 1.5)
        elif(switch == 3):
            self.single_target_click("./pic/event/Skip.png", "TheThirdChoice", 150, 100, 1.5)

    def myWait(self):
        #发现等待中的标志后调用函数
        mySleep(3)
        self.cap_win()
        while(self.waitSign()):
            mySleep(3)
            self.cap_win()


    def waitSign(self):
        result = False
        if(self.is_find("./pic/Wait.png", "Wait Sign")):
            result = True
        elif(self.is_find("./pic/WholeBlack.png", "WholeBlack")):
            result = True
        elif(self.is_find("./pic/CONNECTING.png", "CONNECTING")):
            result = True
        return result

