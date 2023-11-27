# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/10/10 17:11
* File  : checkAdmin.py    
* Project   :LixAssistantLimbusCompany
* Function  :检查当前程序是否以管理员模式运行      
'''

from ctypes import windll
from src.log.myLog import myLog
from tkinter.messagebox import showinfo
from sys import executable, version_info
from os import _exit
from src.common.myTime import mySleep



def checkAdmin():
        '''检查当前程序是否以管理员模式运行    '''
        
        if windll.shell32.IsUserAnAdmin():
            #图形操作窗口
            myLog("info","Already got Admin")
        else:
            if version_info[0] == 3:
                result = windll.shell32.ShellExecuteW(None, "runas", executable, __file__, None, 1)
                if(result <= 32):
                    myLog("error","Can't get Admin")
                    showinfo("异常报告", "无管理员权限，软件很可能不能正常运作")
                else:
                    myLog("info","Agree to get Admin, Restart!")
                    # mySleep(0.9)
            _exit(0)


