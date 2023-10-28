# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/9/16 9:25
* File  : main.py
* Project   :LixAssistantLimbusCompany
* Function  :主体函数入口
'''

from src.gui.scriptGUI import scriptGUI
#from src.common import getPic, autoFindOrClick as afc
from win32event import CreateMutex
from win32api import GetLastError
from sys import exit





if __name__ == '__main__':

    # 互斥锁
    mutex = CreateMutex(None, False, 'LALC.Running')
    if GetLastError() > 0:
        exit(0)

    
    
    #图形化操作界面
    scriptGUI()









