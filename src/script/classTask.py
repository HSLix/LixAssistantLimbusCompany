# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/11/25 22:46
* File  : classTask.py
* Project   :LixAssistantLimbusCompany
* Function  :将脚本任务抽象为一个类
'''
from src.common.autoFindOrClick import autoFind, autoMulClick, autoSinClick
from src.common.pressKey import pressKey
from src.common.getPic import winCap
from src.error.myError import userStopError
from src.log.myLog import myLog


import globalVar



class _task():
    '''在这里做前后台的切换'''
    __slots__ = ()
    
    def single_target_click(self,img_model_path, name, addX=0, addY=0,waitTime = 0.9, clickCount = 1, correctRate = 0.7):
        return autoSinClick(img_model_path, name, addX, addY,waitTime, clickCount, correctRate)

    def press_key(self,key):
        pressKey(key)

    def multiple_target_click(self,img_model_path, name, addX=0, addY=0,waitTime = 0.5, clickCount = 1, correctRate = 0.7):
        return autoMulClick(img_model_path, name, addX, addY,waitTime, clickCount, correctRate)

    def cap_win(self):
        winCap()

    def is_find(self,img_model_path, name, correctRate = 0.7):
        return autoFind(img_model_path, name, correctRate)

def beginAndFinishLog(func):
    '''一个任务开始与结束的日志'''
    def wrapper(*args, **kw):
        msg = "Begin " + func.__name__
        myLog("info", msg)

        #真正函数
        func(*args, **kw)

        msg = "Finish " + func.__name__
        myLog("info", msg)
    return wrapper

def checkAndExit(func):
    '''检查globalVar.exitCode符合条件结束该线程（程序）'''

    def wrapper(*args, **kw):
        if(globalVar.exitCode != 0):
            raise userStopError("用户主动终止程序")

        # 真正函数
        func(*args, **kw)

        if(globalVar.exitCode != 0):
            raise userStopError("用户主动终止程序")

    return wrapper
    
   

