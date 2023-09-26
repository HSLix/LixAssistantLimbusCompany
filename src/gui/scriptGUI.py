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


@beginAndFinishLog
def scriptGUI():
    '''调用图形化函数'''
    #图形操作窗口
    gui = myGUI()

    # 测试识图
    tryClick("./pic/team/EmptyTeam03.png", "1", 0, 0, 1, 1, 0.99)
    
    gui.showWin()
    

