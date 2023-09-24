

from src.script.classScript import _mainScript,checkAndExit
from src.common import getPic, autoFindOrClick as afc
from src.log.nbLog import myLog, beginAndFinishLog

class _getPrize(_mainScript):
    __slots__ = ("prizeSwitch")
    
    def __init__(self, prizeSwitch):
        self.prizeSwitch = prizeSwitch



    def getPrize(self):
        '''根据奖励选择来执行奖励获取'''
        if(self.prizeSwitch == 0 or self.prizeSwitch == 1):
            self.getDayWeekPrize()
        if(self.prizeSwitch == 0 or self.prizeSwitch == 2):
            self.receiveMail()



    #从邮箱获取所有东西
    @checkAndExit
    @beginAndFinishLog
    def receiveMail(self):
        '''获取邮件奖励'''
        self.ScriptBackToInitMenu()
        getPic.winCap()
        afc.autoSinClick("./pic/initMenu/Mail.png","Mail")
        getPic.winCap()
        afc.autoSinClick("./pic/initMenu/ReceiveAllMail.png","ReceiveAllMail")
        getPic.winCap()
        afc.autoSinClick("./pic/initMenu/MailConfirm.png","MailConfirm")
        getPic.winCap()
        afc.autoSinClick("./pic/initMenu/CloseMail.png","CloseMail")
        self.ScriptBackToInitMenu()


    #从通行证处拿日常和周常

    @beginAndFinishLog
    def getDayWeekPrize(self):
        '''获取日常和周常的奖励'''
        self.ScriptBackToInitMenu()
        getPic.winCap()
        afc.autoSinClick("./pic/initMenu/Mail.png","Pass", 0, 100, 1.5)
        getPic.winCap()
        afc.autoSinClick("./pic/prize/PassMissions.png","PassMissions")
        getPic.winCap()
        afc.autoMulClick("./pic/prize/passCoin.png", "DailyPrize", 100)
        afc.autoSinClick("./pic/prize/Weekly.png","Weekly")
        getPic.winCap()
        afc.autoMulClick("./pic/prize/passCoin.png", "WeeklyPrize", 100)
        self.ScriptBackToInitMenu()
