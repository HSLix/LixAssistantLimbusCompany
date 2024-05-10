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

# 执行任务的数量和选项所需参数
exeCfg = {"EXPCount": 0, "ThreadCount": 0, "MirrorCount": 0, "ActivityCount": 0,
            "WinSwitch": 0, "PrizeSwitch": 0, "MirrorSwitch": 0 , "LunacyToEnkephalinSwitch": 0}

# 程序执行结果
exeResult = {"EXPFinishCount":0, "ThreadFinishCount":0, "MirrorFinishCount":0, "ActivityFinishCount":0}

# 罪人的对应
sinnerNumber = {"YiSang":1,"Faust":2,"DonQuixote":3,
                "Ryoshu":4,"Meursault":5,"HongLu":6,
                "Heathcliff":7,"Ishmael":8,"Rodion":9,
                "Sinclair":10,"Outis":11,"Gregor":12}

# 选人的顺序
sinnerOrder = []

# 版本
# 样例：V2.1.9_Realease
version = "V2.1.12_Debug"


# 退出状态
exitCode = 0

# 镜牢3关卡，按顺序索图
enemyList = ['EventQuestionMark', 'QuestionMark','Chair', 'Bus', 'Fight', 'EventEncounter',  'Boss','EventBoss' , 'Battle', 'Encounter', 'EventFight', 'EventBattle']

# 用户屏幕分辨率
screenWidth = 2560
screenHeigh = 1600

# 窗口左上角x和y坐标
winLeft = 0
winTop = 0

# 是否刷取饰品
# 在2.1.11起至某版本，仅刷取呼吸器或呼吸烟斗，并只能通过文件config更改
gift_switch = 0