# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/9/18 17:48
* File  : classPrize.py   
* Project   :LixAssistantLimbusCompany
* Function  :领取奖励的类          
'''

from src.script.classTask import _task, checkAndExit, beginAndFinishLog
from src.script.classScript import _script

class _getPrize(_script):
    __slots__ = ("PrizeSwitch")
    
    def __init__(self, PrizeSwitch):
        self.PrizeSwitch = PrizeSwitch



    def getPrize(self):
        '''根据奖励选择来执行奖励获取'''
        if(self.PrizeSwitch == 0 or self.PrizeSwitch == 1):
            self.getDayWeekPrize()
        if(self.PrizeSwitch == 0 or self.PrizeSwitch == 2):
            self.receiveMail()



    #从邮箱获取所有东西
    @checkAndExit
    @beginAndFinishLog
    def receiveMail(self):
        '''获取邮件奖励'''
        self.ScriptBackToInitMenu()
        self.cap_win()
        self.single_target_click("./pic/initMenu/Mail.png","Mail")
        self.cap_win()
        self.single_target_click("./pic/initMenu/ReceiveAllMail.png","ReceiveAllMail")
        self.cap_win()
        self.single_target_click("./pic/initMenu/MailConfirm.png","MailConfirm")
        self.cap_win()
        self.single_target_click("./pic/initMenu/CloseMail.png","CloseMail")
        self.ScriptBackToInitMenu()


    #从通行证处拿日常和周常

    @beginAndFinishLog
    def getDayWeekPrize(self):
        '''获取日常和周常的奖励'''
        self.ScriptBackToInitMenu()
        self.cap_win()
        self.single_target_click("./pic/initMenu/Mail.png","Pass", 0, 100, 1.5)
        self.cap_win()
        self.single_target_click("./pic/prize/PassMissions.png","PassMissions")
        self.cap_win()
        self.multiple_target_click("./pic/prize/passCoin.png", "DailyPrize", 100)
        self.single_target_click("./pic/prize/Weekly.png","Weekly")
        self.cap_win()
        self.multiple_target_click("./pic/prize/passCoin.png", "WeeklyPrize", 100)
        self.ScriptBackToInitMenu()
