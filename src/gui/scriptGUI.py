# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/9/16 9:25
* File  : scriptGUI.py    
* Project   :LixAssistantLimbusCompany
* Function  :调用图形化交互            
'''
from src.gui.myGUI import myGUI
from src.log.nbLog import beginAndFinishLog
from src.test.tryClick import tryClick
from ctypes import windll
from src.error.myError import withOutAdminError
from src.log.nbLog import myLog
from src.test.checkScreenScale import checkScreenScale
from src.test.checkAdmin import checkAdmin



@beginAndFinishLog
def scriptGUI():
    '''申请管理员权限并，调用图形化函数'''
    
    checkScreenScale()

    # 测试识图
    tryClick("./pic/team/EmptyTeam05.png", "1", 0, 0, 1, 1, 0.93)
    
    checkAdmin()
    gui = myGUI()
    gui.showWin()
            
    

    
    
    






