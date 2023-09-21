'''
* Author: LuYaoQi
* Time  : 2023/9/16 9:25
* File  : main.py
* Project   :LixAssistantLimbusCompany
* Function  :主体函数入口
'''

from src.gui.scriptGUI import scriptGUI
#from src.common import getPic, autoFindOrClick as afc
from src.test.tryClick import tryClick
from win32event import CreateMutex
from win32api import GetLastError
from sys import exit



if __name__ == '__main__':
    # 测试识图
    # tryClick("./pic/mirror/mirror2/Mirror2Normal.png", "Mirror2Normal", 0, 0, 1, 1, 0.8)
    
    # 互斥锁
    mutex = CreateMutex(None, False, 'LALC.Running')
    if GetLastError() > 0:
        exit(0)
    
    #图形化操作界面
    scriptGUI()









