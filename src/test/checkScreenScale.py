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
import tkinter as tk
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
        scale = width / widthScale * 100
        msg = "屏幕状况 (排除缩放后)宽x高 缩放： " + str(width) + " x " + str(height) + " " + str(int(scale)) + "%"
        myLog("debug", msg)
        if(not(scale > 149 and scale < 151)):
            msg += "\n最好将缩放调整至150%\n否则稳定性难以保障"
            myLog("warning", msg)
            top = tk.Tk()
            top.geometry('0x0+999999+0')
            showinfo("缩放警告", msg)
            top.destroy()



