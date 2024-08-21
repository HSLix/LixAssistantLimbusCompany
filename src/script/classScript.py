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

        elif(self.is_find("./pic/error/ServerUnderMaintenance.png", "ServerCloseSign")):
            self.single_target_click("./pic/error/Close.png", "Close")
            raise serverCloseError("服务器维护中")

    @checkAndExit
    @beginAndFinishLog
    def ScriptBackToInitMenu(self):
        '''返回主界面'''
        loopCount = 0
        self.cap_win()
        while(not self.single_target_click("./pic/initMenu/Window.png", "mainMenuSign")):
            
            self.cap_win()

            #在循环里必须有应对错误的情况
            self.errorRetry()

            # 战斗中,完成
            if(self.is_find("./pic/battle/WinRate.png", "battleSign")):
                self.allWinRateBattle()
            
            # 镜本中途的返回主界面
            if self.single_target_click("./pic/back/To Window.png", "To Window"):
                self.cap_win()
                self.single_target_click("./pic/back/whiteBackGroundConfirm.png", "whiteConfirm")
                continue

            # 战斗结算的确认
            self.single_target_click("./pic/back/blackBackGroundConfirm.png", "blackCOnfirm")

            # 在剧情中退出
            if self.single_target_click("./pic/back/SceneSetting.png", "SceneSetting"):
                self.press_key("esc")
                self.cap_win()
                self.single_target_click("./pic/back/whiteBackGroundConfirm.png", "whiteConfirm")
                continue

            # 镜本结算
            if self.single_target_click("./pic/mirror/mirror4/ClaimRewards.png","ClaimRewards"):
                for i in range(5):
                    self.press_key("enter")
                    
            # 在ego选择退出
            if self.single_target_click("./pic/back/settingGear.png", "settingGear"):
                continue


            # 在类似镜牢4选主题包退出
            if (not self.single_target_click("./pic/initMenu/Window.png", "mainMenuSign")
                and self.single_target_click("./pic/mirror/mirror4/way/ThemePack/ThemePackGear.png", "ThemePackGear")):
                continue

            
            # 等待加载情况
            if(self.is_find("./pic/Wait.png", "Wait Sign")):
                self.myWait()   

            if(self.is_find("./pic/back/mainMenuSetting.png", "main menu setting")):
                self.press_key("esc")

            self.cap_win()
            # 退出的通用步骤esc
            self.press_key("esc")

            loopCount += 1
             
            
            # 第二次也不行时，一定是出现了脚本中没有的情况
            if loopCount > 30:
                myLog("warning", "Can't Find The Way MainMenu. Must be Unknown Situation. Please Restart the Game and the Script")
                raise backMainWinError("无法返回主界面，不能进行下一步")



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
                #self.is_find("./pic/battle/WinRate.png", "WinRate")
                self.press_key("enter")
                self.cap_win()
                if (self.single_target_click("./pic/battle/WinRate.png", "WinRate")):
                    self.press_key("enter")
                condition = True
            elif(self.is_find("./pic/battle/battlePause.png", "Fighting Sign")):
                mySleep(2)
                condition = True
            elif(self.is_find("./pic/event/Skip.png", "Skip")):
                self.eventPart()
                condition = True
            elif(self.is_find("./pic/Wait.png", "Wait Sign")):
                self.myWait()
                condition = True
            elif(not self.is_find("./pic/mirror/mirror4/way/mirror4MapSign.png", "mirror4MapSign") 
                    and self.single_target_click("./pic/battle/trianglePause.png", "Continue Fight!")):
                condition = True
            # 接下来是战斗停止的标识
            elif(self.single_target_click("./pic/battle/blackWordConfirm.png", "Level Increased!")):
                break
            elif(self.single_target_click("./pic/battle/confirm.png", "Confirm")):
                break
            elif(self.is_find("./pic/mirror/mirror3/way/mirror3MapSign.png", "mirror3/4MapSign") ):
                break
            elif(self.is_find("./pic/mirror/mirror3/ego/egoGift.png", "ChooseEgoGift")):
                break
            elif(self.is_find("./pic/mirror/mirror4/way/RewardCard/RewardCardSign.png", "RewardCardSign")):
                break

            mySleep(1)
            if(not condition):
                loopCount += 1
                if(loopCount > 10):
                    break
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

            # 点击一定获取ego的事件
            self.cap_win()
            self.single_target_click("./pic/event/PassToGainEGO.png", "PassToGainEGO")
            self.single_target_click("./pic/event/EGOGiftChoice.png", "EGOGiftChoice")

            # 对bus/chair的出口第一时间反应
            self.cap_win()
            if(self.single_target_click("./pic/event/Leave.png", "Leave")):
                self.cap_win()
                self.single_target_click("./pic/mirror/mirror2/whiteConfirm.png", "Confirm")
            
            self.single_target_click("./pic/event/Skip.png", "Skip", 0, 0, 1, 2)

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
            if (self.single_target_click("./pic/event/Continue.png", "Continue") or
            self.single_target_click("./pic/event/Proceed.png", "Proceed") or
            self.single_target_click("./pic/event/ToBattle.png", "ToBattle!") or
            self.single_target_click("./pic/event/CommenceBattle.png", "CommenceBattle")):
                continue

            self.cap_win()
            #没有点到事件出口的情况下跳转到对应异想体的专门处理
            if(self.is_find("./pic/event/Choices.png","Choices")):
                self.copeWithWhateverEvent()

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
        if(self.is_find("./pic/CombatTips.png", "Wait Sign")):
            result = True
        '''if(self.is_find("./pic/Wait.png", "Wait Sign")):
            result = True
        elif(self.is_find("./pic/WholeBlack.png", "WholeBlack", 0.99)):
            result = True'''
        return result




    #满队标准
    def judFullTeam(self):
        '''判断队伍是否人满'''
        result = False
        if(self.is_find("./pic/team/FullTeam66.png", "FullTeam6/6", 0.96)):
            result = True
        return result


    @checkAndExit
    @beginAndFinishLog
    def prepareBattle(self):
        '''准备战斗的流程'''
        self.cap_win()
        i = 1
        #condition = self.judTeamCondition()
        if (not self.judFullTeam()):
            self.single_target_click("./pic/team/ClearSelection.png", "ClearSelection")
            self.press_key('enter')
            self.cap_win()
            self.get_sinner_order()
            while(not self.judFullTeam()):
                #i的归零
                if(i > 12):
                    i = 1
                    myLog("warning","Can't make team full")
                    break
                self.cap_win()
                j = globalVar.sinnerNumber[globalVar.sinnerOrder[i - 1]]
                if(j < 7):
                    addX = j * 140
                    addY = 0
                else:
                    addX = (j - 6) * 140
                    addY = 200

                self.single_target_click("./pic/team/Announcer.png", "Member", addX, addY + 100, 0.2)
                self.cap_win()
                i += 1

        self.press_key("enter")
        mySleep(5)
        # self.single_target_click("./pic/team/Announcer.png", "ToBattle", 1000, 400, 5)
        self.cap_win()
        if(self.is_find("./pic/Wait.png", "Wait Sign", 0.8)):
                self.myWait()

    def get_sinner_order(self):
        # 先读取文件第一行
        with open("./sinner_order.txt", 'r', encoding='utf-8') as f:
            first_line = f.readline().rstrip()
            globalVar.sinnerOrder = first_line.split(",")
            print(globalVar.sinnerOrder)