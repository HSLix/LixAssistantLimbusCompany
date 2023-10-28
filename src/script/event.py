# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/9/16 9:25
* File  : event.py
* Project   :LixAssistantLimbusCompany
* Function  :处理有Skip键的事件
'''
from src.common import getPic, autoFindOrClick as afc
from src.common.myTime import myTimeSleep
from src.log.nbLog import beginAndFinishLog


@beginAndFinishLog
def eventPart():
    '''处理含skip的一切事件
    :param condition: 是否有skip
    '''
    condition = True
    while(condition):
        
        getPic.winCap()
        afc.autoSinClick("./pic/event/Skip.png", "Skip", 0, 0, 0.3, 3)
        
        #对判定事件的处理，优先择高概率
        getPic.winCap()
        if(afc.autoFind("./pic/event/ChooseCheck.png","ChooseCheck")):
            if(afc.autoSinClick("./pic/event/veryhigh.png", "VeryHigh") or\
                afc.autoSinClick("./pic/event/high.png", "High")or\
                afc.autoSinClick("./pic/event/Normal.png", "Normal")or\
                afc.autoSinClick("./pic/event/Low.png", "Low")or\
                afc.autoSinClick("./pic/event/VeryLow.png", "VeryLow")):
                getPic.winCap()
                afc.autoSinClick("./pic/event/Commence.png", "Commence")
                myTimeSleep(3)

        #事件出口
        getPic.winCap()
        afc.autoSinClick("./pic/event/Continue.png", "Continue")
        afc.autoSinClick("./pic/event/Proceed.png", "Proceed")
        afc.autoSinClick("./pic/event/ToBattle.png", "ToBattle!")

        #没有点到事件出口的情况下跳转到对应异想体的专门处理
        if(afc.autoFind("./pic/event/Choices.png","Choices")):
            copeWithWhateverEvent()

        if(afc.autoSinClick("./pic/event/Leave.png", "Leave")):
            getPic.winCap()
            afc.autoSinClick("./pic/mirror/mirror2/whiteConfirm.png", "Confirm")
        myTimeSleep(1)

        if(not afc.autoFind("./pic/event/Skip.png", "Skip")):
            condition = False


def copeWithWhateverEvent():
    '''获取事件类型，并做相应点击选择'''
    state = judWhatEvent()
    if(state == 0):
        eventChoice(2)
        eventChoice(1)
    elif(state == 1):
        eventChoice(1)
    elif(state == 2):
        eventChoice(2)
    elif(state == 3):
        eventChoice(2)
    elif(state == 4):
        eventChoice(1)
        eventChoice(2)


def judWhatEvent():
    '''
    从截屏判断事件类型
    :param eventNum:事件类型代号
    '''
    eventNum = 0
    if(afc.autoFind("./pic/encounter/UnDeadMechine1.png", "UnDeadMechine1", 0.9)):
        eventNum = 1
    elif(afc.autoFind("./pic/encounter/UnDeadMechine2.png", "UnDeadMechine2", 0.9)):
        eventNum = 2
    elif(afc.autoFind("./pic/encounter/PinkShoes.png", "PinkShoes", 0.9)):
        eventNum = 3
    elif(afc.autoFind("./pic/encounter/RedKillClock.png", "RedKillClock", 0.9)):
        eventNum = 4
    


    return eventNum


def eventChoice(switch = 0):
    '''包装了事件三个选择的点击位置'''
    if(switch == 1):
        afc.autoSinClick("./pic/event/Skip.png", "TheFirstChoice", 150, -100, 1.5)
    elif(switch == 2):
        afc.autoSinClick("./pic/event/Skip.png", "TheSecondChoice", 150, 0, 1.5)
    elif(switch == 3):
        afc.autoSinClick("./pic/event/Skip.png", "TheThirdChoice", 150, 100, 1.5)



