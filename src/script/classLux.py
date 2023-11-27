# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/9/18 17:06
* File  : classself.py  
* Project   :LixAssistantLimbusCompany
* Function  :经验本与纽本交互的类
'''

from src.script.classTask import _task, checkAndExit, beginAndFinishLog
from src.common.myTime import mySleep
from src.log.myLog import myLog

from src.script.classScript import _script


class _Luxcavation(_script):
    '''经验本纽本的类'''
    __slots__ = ("EXPCount", "ThreadCount", "EXPFinishCount", "ThreadFinishCount")

    def __init__(self, EXPCount, ThreadCount):
        self.EXPCount = EXPCount
        self.ThreadCount = ThreadCount
        self.EXPFinishCount = 0
        self.ThreadFinishCount = 0



    def getEXPFinishCount(self):
        '''返回经验本完成次数'''
        return self.EXPFinishCount
    

    def getThreadFinishCount(self):
        '''返回纽本完成次数'''
        return self.ThreadFinishCount


    

    
    @checkAndExit
    @beginAndFinishLog
    def ScriptTaskEXP(self):
        '''打完一次经验本的流程'''
        loopCount = 0
        while(self.EXPFinishCount < self.EXPCount):
            self.errorRetry()
            if not self.EXPPart():
                loopCount += 1
                if loopCount > 0:
                    if loopCount > 3:
                        myLog("warning","Hard to continue! Next Mission!")
                        #离开进入函数
                        self.EXPCount = 0
            else:
                loopCount = 0

            if(self.EXPPrize()):
                self.EXPFinishCount += 1
                msg = "EXP Success " + str(self.EXPFinishCount) + " Times!"
                myLog("info", msg)
                
            mySleep(1)


    @checkAndExit
    @beginAndFinishLog
    def ScriptTaskThread(self):
        '''打完一次纽本的流程'''
        loopCount = 0
        while(self.ThreadFinishCount < self.ThreadCount):
            
            self.errorRetry()
            if not self.ThreadPart():
                loopCount += 1
                if loopCount > 0:
                    if loopCount > 3:
                        myLog("warning","Hard to continue! Next Mission!")
                        #离开进入函数
                        self.ThreadCount = 0
            else:
                loopCount = 0

            if(self.ThreadPrize()):
                self.ThreadFinishCount += 1
                msg = "Thread Success "  + str(self.ThreadFinishCount) + " Times!"
                myLog("info", msg)

            mySleep(1)


    @checkAndExit
    @beginAndFinishLog
    def EXPOrThreadPrepareBattle(self):
        '''负责进入副本后选人到进入战斗
        :param result:是否成功进入战斗
        '''
        result = False
        i = 1
        self.cap_win()
        while(not self.is_find("./pic/team/FullTeam55.png", "FullTeam5/5", 0.94) and\
            self.is_find("./pic/team/Announcer.png", "prepareBattle")):
            if(i > 12):
                i = 1
            if(i < 7):
                addX = i * 140
                addY = 0
            else:
                addX = (i - 6) * 140
                addY = 200

            self.cap_win()
            self.single_target_click("./pic/team/Announcer.png", "Member", addX, addY + 100, 0.2)
            self.cap_win()
            i += 1
            
        self.cap_win()
        self.single_target_click("./pic/team/Announcer.png", "ToBattle", 1000, 400, 5)
        self.cap_win()
        if(self.is_find("./pic/Wait.png", "Wait Sign")):
                self.myWait()

        self.cap_win()
        if(self.single_target_click("./pic/battle/Start.png", "Start", 0, 0, 0.7, 1, 0.7) or\
        self.single_target_click("./pic/battle/WinRate.png", "WinRate") or\
        self.is_find("./pic/battle/battlePause.png", "Fighting Sign")):
            result = True
        return result
        

    
    def EXPPart(self):
        '''统筹了完成一次经验本所有流程
        :param result:是否成功进入战斗部分并完成一次循环
        '''
        self.cap_win()
        result = False
        result = self.EXPEnter()
        self.cap_win()
        if(self.is_find("./pic/Wait.png", "Wait Sign")):
            self.myWait()
        self.allWinRateBattle()
        return result


    
    def EXPEnter(self):
        '''从主界面进入经验本流程
        :param result:是否成功进入战斗部分
        '''

        #是否进入到战斗（核心步骤）中
        result = False
        self.cap_win()
        switch = self.is_find("./pic/team/Announcer.png", "prepareBattle")
        if not switch:
            self.single_target_click("./pic/initMenu/drive.png", "Drive")
            self.cap_win()
            self.single_target_click("./pic/luxcavation/luxcavationEntrance.png", "luxcavationEntrance")
            self.cap_win()
            self.single_target_click("./pic/luxcavation/EXPHard.png", "EXPHard", 0, 0, 3)
        result = self.EXPOrThreadPrepareBattle()
        return result



    
    def EXPPrize(self):
        '''经验本结算
        :param result:是否成功结算
        '''
        result = False
        
        if self.is_find("./pic/Wait.png", "WaitSign"):
            self.myWait()
        elif self.single_target_click("./pic/battle/levelUpConfirm.png", "LevelUpConfirm"):
            result =True
            self.ScriptBackToInitMenu()
        elif self.single_target_click("./pic/battle/confirm.png", "Confirm"):
            result = True
            self.ScriptBackToInitMenu()
        return result
        
        

    
    def ThreadPart(self):
        '''统筹了完成一次纽本所有流程
        :param result:是否成功进入战斗部分并完成一次循环
        '''

        self.cap_win()
        result = False
        result = self.ThreadEnter()
        if(result):
            self.cap_win()
            if(self.is_find("./pic/Wait.png", "Wait Sign")):
                self.myWait()
        self.allWinRateBattle()
        return result


    
    def ThreadEnter(self):
        '''从主界面进入纽本流程
        :param result:是否成功进入战斗部分
        '''
        
        result = False
        self.cap_win()
        switch = self.is_find("./pic/team/Announcer.png", "prepareBattle")
        if not switch:
            self.single_target_click("./pic/initMenu/drive.png", "Drive")
            self.cap_win()
            self.single_target_click("./pic/luxcavation/luxcavationEntrance.png", "luxcavationEntrance")
            self.cap_win()
            self.single_target_click("./pic/luxcavation/ThreadEntrance.png", "ThreadEntrance")
            self.cap_win()
            self.single_target_click("./pic/luxcavation/Enter.png", "Enter")
            self.cap_win()
            self.single_target_click("./pic/luxcavation/ThreadHard.png", "ThreadHard", 0, 0, 3)
        result = self.EXPOrThreadPrepareBattle()
        return result


    
    def ThreadPrize(self):
        '''纽本结算
        :param result:是否成功结算
        '''
        result = False
        if self.is_find("./pic/Wait.png", "WaitSign"):
            self.myWait()
        elif self.single_target_click("./pic/battle/levelUpConfirm.png", "LevelUpConfirm"):
            result =True
            self.ScriptBackToInitMenu()
        elif self.single_target_click("./pic/battle/confirm.png", "Confirm"):
            result = True
            self.ScriptBackToInitMenu()
        return result
    

