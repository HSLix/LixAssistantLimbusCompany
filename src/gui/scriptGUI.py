# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/9/16 9:25
* File  : scriptGUI.py    
* Project   :LixAssistantLimbusCompany
* Function  :调用图形化交互            
'''
from src.gui.myGUI import myGUI
from src.test.tryClick import tryClick
from src.test.checkScreenScale import checkScreenScale
from src.test.checkAdmin import checkAdmin



def scriptGUI():
    '''申请管理员权限并，调用图形化函数'''
    checkAdmin()
    checkScreenScale()

    # 测试识图
    # tryClick("./pic/initMenu/FirstBuy.png", "26Lunary", 0, 0, 0.7, 1, 0.825)
    
    gui = myGUI()
    gui.showWin()
            
    

    
    
    






