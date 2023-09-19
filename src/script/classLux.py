'''
* Author: LuYaoQi
* Time  : 2023/9/18 17:06
* File  : classself.py  
* Project   :LixAssistantLimbusCompany
* Function  :经验本与纽本交互的类
'''
from src.script.classScript import _mainScript
from src.common import getPic, autoFindOrClick as afc
from src.script.battle import dailyBattlePart
from src.common.myTime import myTimeSleep
from src.script.myWait import myWait
from src.script.classScript import checkAndExit
from src.log.nbLog import myLog, beginAndFinishLog


class _Luxcavation(_mainScript):
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
        self.EXPFinishCount = 0
        loopCount = 0
        while(self.EXPFinishCount < self.EXPCount):
            self.errorRetry()
            if not self.EXPPart():
                loopCount += 1
                if loopCount > 0:
                    if loopCount > 3:
                        myLog("warning","死循环！下一个任务")
                        #离开进入函数
                        self.EXPCount = 0
            else:
                loopCount = 0

            if(self.EXPPrize()):
                self.EXPFinishCount += 1
                msg = "已完成 " + str(self.EXPFinishCount) + " 次经验本EXP任务"
                myLog("info", msg)
                
            myTimeSleep(1)


    @checkAndExit
    @beginAndFinishLog
    def ScriptTaskThread(self):
        '''打完一次纽本的流程'''
        self.ThreadFinishCount = 0
        loopCount = 0
        while(self.ThreadFinishCount < self.ThreadCount):
            
            self.errorRetry()
            if not self.ThreadPart():
                loopCount += 1
                if loopCount > 0:
                    if loopCount > 3:
                        myLog("warning","死循环！下一个任务")
                        #离开进入函数
                        self.ThreadCount = 0
            else:
                loopCount = 0

            if(self.ThreadPrize()):
                self.ThreadFinishCount += 1
                msg = "已完成 " + str(self.ThreadFinishCount) + " 次纽本Thread任务"
                myLog("info", msg)

            myTimeSleep(1)


    @checkAndExit
    @beginAndFinishLog
    def EXPOrThreadPrepareBattle(self):
        '''负责进入副本后选人到进入战斗
        :param result:是否成功进入战斗
        '''
        result = False
        i = 1
        myTimeSleep(2)
        getPic.winCap()
        while(not afc.autoFind("./pic/team/FullTeam55.png", "FullTeam5/5", 0.992) and\
            afc.autoSinClick("./pic/team/Announcer.png", "prepareBattle")):
            if(i > 12):
                i = 1
            if(i < 7):
                addX = i * 140
                addY = 0
            else:
                addX = (i - 6) * 140
                addY = 200

            getPic.winCap()
            afc.autoSinClick("./pic/team/Announcer.png", "Member", addX, addY, 0.2)
            getPic.winCap()
            i += 1
            
        getPic.winCap()
        afc.autoSinClick("./pic/team/Announcer.png", "ToBattle", 1000, 400, 5)
        getPic.winCap()
        if(afc.autoFind("./pic/Wait.png", "Wait Sign")):
                myWait()

        getPic.winCap()
        if(afc.autoSinClick("./pic/battle/Start.png", "Start") or\
        afc.autoSinClick("./pic/battle/WinRate.png", "WinRate") or\
        afc.autoFind("./pic/battle/battlePause.png", "Fighting Sign")):
            result = True
        return result
        

    
    def EXPPart(self):
        '''统筹了完成一次经验本所有流程
        :param result:是否成功进入战斗部分并完成一次循环
        '''
        getPic.winCap()
        result = False
        result = self.EXPEnter()
        getPic.winCap()
        if(afc.autoFind("./pic/Wait.png", "Wait Sign")):
            myWait()
        dailyBattlePart()
        return result


    
    def EXPEnter(self):
        '''从主界面进入经验本流程
        :param result:是否成功进入战斗部分
        '''

        #是否进入到战斗（核心步骤）中
        result = False
        getPic.winCap()
        switch = afc.autoFind("./pic/team/Announcer.png", "prepareBattle")
        if not switch:
            afc.autoSinClick("./pic/initMenu/drive.png", "Drive")
            getPic.winCap()
            afc.autoSinClick("./pic/luxcavation/luxcavationEntrance.png", "luxcavationEntrance")
            getPic.winCap()
            afc.autoSinClick("./pic/luxcavation/EXPHard.png", "EXPHard", 0, 0, 3)
        result = self.EXPOrThreadPrepareBattle()
        return result



    
    def EXPPrize(self):
        '''经验本结算
        :param result:是否成功结算
        '''
        result = False
        
        if afc.autoFind("./pic/Wait.png", "WaitSign"):
            myWait()
        elif afc.autoSinClick("./pic/battle/levelUpConfirm.png", "LevelUpConfirm"):
            result =True
            self.ScriptBackToInitMenu()
        elif afc.autoSinClick("./pic/battle/confirm.png", "Confirm"):
            result = True
            self.ScriptBackToInitMenu()
        return result
        
        

    
    def ThreadPart(self):
        '''统筹了完成一次纽本所有流程
        :param result:是否成功进入战斗部分并完成一次循环
        '''

        getPic.winCap()
        result = False
        result = self.ThreadEnter()
        if(result):
            getPic.winCap()
            if(afc.autoFind("./pic/Wait.png", "Wait Sign")):
                myWait()
        dailyBattlePart()
        return result


    
    def ThreadEnter(self):
        '''从主界面进入纽本流程
        :param result:是否成功进入战斗部分
        '''
        
        result = False
        getPic.winCap()
        switch = afc.autoFind("./pic/team/Announcer.png", "prepareBattle")
        if not switch:
            afc.autoSinClick("./pic/initMenu/drive.png", "Drive")
            getPic.winCap()
            afc.autoSinClick("./pic/luxcavation/luxcavationEntrance.png", "luxcavationEntrance")
            getPic.winCap()
            afc.autoSinClick("./pic/luxcavation/ThreadEntrance.png", "ThreadEntrance")
            getPic.winCap()
            afc.autoSinClick("./pic/luxcavation/Enter.png", "Enter")
            getPic.winCap()
            afc.autoSinClick("./pic/luxcavation/ThreadHard.png", "ThreadHard", 0, 0, 3)
        result = self.EXPOrThreadPrepareBattle()
        return result


    
    def ThreadPrize(self):
        '''纽本结算
        :param result:是否成功结算
        '''
        result = False
        if afc.autoFind("./pic/Wait.png", "WaitSign"):
            myWait()
        elif afc.autoSinClick("./pic/battle/levelUpConfirm.png", "LevelUpConfirm"):
            result =True
            self.ScriptBackToInitMenu()
        elif afc.autoSinClick("./pic/battle/confirm.png", "Confirm"):
            result = True
            self.ScriptBackToInitMenu()
        return result
    

