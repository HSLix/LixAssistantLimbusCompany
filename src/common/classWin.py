# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/9/24 16:22
* File  : initWin.py
* Project   :LixAssistantLimbusCompany
* Function  :对窗口的统合类
'''

from src.common.winSet import *
import win32gui, win32con
from ctypes import windll
from src.log.nbLog import myLog
from src.error.myError import withOutGameWinError,screenScaleError




class _win():
    __slots__=("initSwitch")

    winLeft = -1
    winTop = -1
    winRight = -1
    winBotton = -1
    hWnd = ""

    def __init__(self, initSwitch = 0):
        self.initSwitch = initSwitch


    def winTask(self):
        '''
        对窗口所有流程的集合
        '''
        # 检查窗口的缩放是否为150%
        # self.checkWin()

        # 初始化窗口的位置的大小
        self.initWin()

        # 获取窗口左上角坐标和右下角坐标
        # 排除缩放干扰
        windll.user32.SetProcessDPIAware()
        _win.winLeft, _win.winTop, _win.winRight, _win.winBottom = win32gui.GetWindowRect(_win.hWnd)





    def checkWin(self):
        '''
        检查屏幕缩放是否符合150%
        '''
        
        user32 = windll.user32
        gdi32 = windll.gdi32
        dc = user32.GetDC(None)
        widthScale = gdi32.GetDeviceCaps(dc, 8)  # 分辨率缩放后的宽度
        heightScale = gdi32.GetDeviceCaps(dc, 10)  # 分辨率缩放后的高度
        width = gdi32.GetDeviceCaps(dc, 118)  # 原始分辨率的宽度
        height = gdi32.GetDeviceCaps(dc, 117)  # 原始分辨率的高度
        scale = width / widthScale
        msg = "屏幕状况 (排除缩放后)宽x高 缩放： " + str(width) + " x " + str(height) + " " + str(scale)
        myLog("debug", msg)
        if(not(scale > 1.49 and scale < 1.51)):
            raise screenScaleError("屏幕缩放不是150%")
        
        




    def initWin(self):
        '''
        初始化游戏窗口
        :param result:初始化结果
        :param hWnd:获取窗口的句柄
        :param switch:初始化窗口选项，配合GUI 
        '''
        #初始化结果失败与否
        result = False

        # 排除缩放干扰
        windll.user32.SetProcessDPIAware()



        # 获取窗口的信息
        _win.hWnd = win32gui.FindWindow("UnityWndClass","LimbusCompany")
        if(_win.hWnd != 0):
            result = True
        else:
            myLog("error","Can't Find The Game Window")
            raise withOutGameWinError("没有找到游戏窗口")
        
        # 若最小化，则将其显示
        if win32gui.IsIconic(_win.hWnd):
            win32gui.ShowWindow(_win.hWnd, win32con.SW_SHOWMAXIMIZED)

        # 置顶窗口
        win32gui.SetForegroundWindow(_win.hWnd)

        #大小为1280，720
        if(self.initSwitch == 0 or self.initSwitch == 1):
            resize_window(_win.hWnd, 1280, 720)

        #窗口默认至左上角（0，0）
        if(self.initSwitch == 0 or self.initSwitch == 2):
            move_window(_win.hWnd, 0, 0)

        
        
        #回收句柄
        windll.user32.ReleaseDC(_win.hWnd)

        return result
    

