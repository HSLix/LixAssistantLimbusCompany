# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/9/16 9:25
* File  : myTime.py       
* Project   :LixAssistantLimbusCompany
* Function  :包装等待函数，便于日志记录      
'''
from time import sleep
from src.log.nbLog import myLog




def myTimeSleep(t):
    '''
    包装了timesleep，方便记录日志  
    '''
    while(t >= 1):
        if(isinstance(t, int)):
            msg = "Waiting! " + str(t) + " Second"
            myLog("debug",msg)
        sleep(0.99)
        t -= 1
    sleep(t)