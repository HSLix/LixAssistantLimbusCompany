# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/9/16 9:25
* File  : battle.py       
* Project   :LixAssistantLimbusCompany
* Function  :处理进入战斗界面后的交互         
'''

from src.common import getPic, autoFindOrClick as afc
from src.script.event import eventPart
from src.common.myTime import myTimeSleep
from src.script.myWait import myWait


def dailyBattlePart():
    '''日常战斗处理'''
    getPic.winCap()
    loopCount = 0
    while(True):
        getPic.winCap()
        condition = False
        if (afc.autoSinClick("./pic/battle/WinRate.png", "WinRate")):
            getPic.winCap()
            if (afc.autoSinClick("./pic/battle/Start.png", "Start")):
                condition = True
        elif(afc.autoFind("./pic/battle/battlePause.png", "Fighting Sign")):
            myTimeSleep(3)
            condition = True
        elif(afc.autoSinClick("./pic/battle/trianglePause.png", "Continue Fight!")):
            condition = True    
        elif(afc.autoFind("./pic/event/Skip.png", "Skip")):
            eventPart()
            condition = True
        elif(afc.autoFind("./pic/Wait.png", "Wait Sign")):
            myWait()
            condition = True
        myTimeSleep(1)
        if(not condition):
            loopCount += 1
            if(loopCount > 2):
                break
            elif(loopCount > 0):
                if (afc.autoFind("./pic/battle/Gear.png", "FinishingBattle")):
                    condition = True
                    loopCount = 0
        else:
            loopCount = 0

    




    

            