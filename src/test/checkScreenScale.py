# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/10/10 17:11
* File  : checkScreenScale.py    
* Project   :LixAssistantLimbusCompany
* Function  :检查屏幕分辨率是否符合要求        
'''

from ctypes import windll
from src.log.myLog import myLog
from tkinter.messagebox import showinfo
from os import _exit



def checkScreenScale():
        '''在屏蔽缩放前，检查缩放率是否为150%，否则弹出提示并退出'''
        
        user32 = windll.user32
        gdi32 = windll.gdi32
        dc = user32.GetDC(None)
        widthScale = gdi32.GetDeviceCaps(dc, 8)  # 分辨率缩放后的宽度
        heightScale = gdi32.GetDeviceCaps(dc, 10)  # 分辨率缩放后的高度
        width = gdi32.GetDeviceCaps(dc, 118)  # 原始分辨率的宽度
        height = gdi32.GetDeviceCaps(dc, 117)  # 原始分辨率的高度
        scale = width / widthScale
        msg = "屏幕状况 (排除缩放后)宽x高 缩放： " + str(width) + " x " + str(height) + " " + str(int(scale * 100)) + "%"
        myLog("debug", msg)
        if(not(scale > 1.49 and scale < 1.51)):
            msg += "\n请设置屏幕的缩放为150%后再启动程序"
            myLog("warning", msg)
            showinfo("异常报告", msg)
            _exit(0)



