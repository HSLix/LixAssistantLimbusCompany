'''
* Author: LuYaoQi
* Time  : 2023/9/16 9:25
* File  : myWait.py
* Project   :LixAssistantLimbusCompany
* Function  :等待游戏中加载界面的结束
'''
from src.common import getPic, autoFindOrClick as afc
from src.common.myTime import myTimeSleep
from src.log.nbLog import beginAndFinishLog


@beginAndFinishLog
def myWait():
    #发现等待中的标志后调用函数
    myTimeSleep(3)
    getPic.winCap()
    while(afc.autoFind("./pic/Wait.png", "Wait Sign")):
        myTimeSleep(3)
        getPic.winCap()