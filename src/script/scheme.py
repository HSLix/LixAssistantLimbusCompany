# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/11/25 22:46
* File  : scheme.py
* Project   :LixAssistantLimbusCompany
* Function  :脚本任务流程
'''
from src.script.classLux import _Luxcavation
from src.script.classMir import _Mirror
from src.script.classPrize import _getPrize
from src.script.classTransition import _transition

from src.common.classWin import _win
import globalVar





def scriptTasks():
    '''一整套脚本流程'''
    lux = _Luxcavation(globalVar.exeCfg["EXPCount"], globalVar.exeCfg["ThreadCount"])
    mir = _Mirror(globalVar.exeCfg["MirrorSwitch"], globalVar.exeCfg["MirrorCount"])
    prize = _getPrize(globalVar.exeCfg["PrizeSwitch"])
    win = _win(globalVar.exeCfg["WinSwitch"])
    trans = _transition()

    # 重置完成次数
    globalVar.exeResult["EXPFinishCount"] = 0
    globalVar.exeResult["ThreadFinishCount"] = 0
    globalVar.exeResult["MirrorFinishCount"] = 0
    globalVar.exeResult["ActivityFinishCount"] = 0
    

    # 全流程
    # 初始化游戏窗口
    win.winTask()

    # 从Start界面到主菜单界面
    trans.ScriptGameStart()
    trans.ScriptBackToInitMenu()

    # 狂气购买脑啡肽
    trans.buyEnkephalin()

    # 脑啡肽换饼
    trans.convertPai()

    # EXP
    lux.ScriptTaskEXP()
    # 每完成一次任务，获取完成次数
    globalVar.exeResult["EXPFinishCount"] = lux.getEXPFinishCount()

    # Thread
    lux.ScriptTaskThread()
    globalVar.exeResult["ThreadFinishCount"] = lux.getThreadFinishCount()
    
    # Mirror
    mir.start()
    globalVar.exeResult["MirrorFinishCount"] = mir.getMirrorFinishCount()
    
    # Prize
    prize.getPrize()