# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/11/27 21:13
* File  : globalVar.py
* Project   :LixAssistantLimbusCompany
* Function  :储存要用到的全局变量
'''
from src.error.myError import noSuchGlobalVarError
from src.log.myLog import myLog

def init():
    global exeCfg
    global exeResult
    global version
    global exitCode

# 执行程序所需参数
exeCfg = {"EXPCount": 0, "ThreadCount": 0, "MirrorCount": 0, "ActivityCount": 0,
            "WinSwitch": 0, "PrizeSwitch": 0, "MirrorSwitch": 0 , "LunacyToEnkephalinSwitch": 0}

# 程序执行结果
exeResult = {"EXPFinishCount":0, "ThreadFinishCount":0, "MirrorFinishCount":0, "ActivityFinishCount":0}

# 版本
# 样例：V2.1.9_Realease
version = "V2.1.10_Realease"


# 退出状态
exitCode = 0

