'''
* Author: LuYaoQi
* Time  : 2023/9/16 9:25
* File  : initWin.py
* Project   :LixAssistantLimbusCompany
* Function  :初始化游戏窗口的大小，位置，指定窗口，取消窗口最小化
'''

from src.common.winSet import *
import win32gui, win32con
from ctypes import windll
from src.log.nbLog import myLog
from src.error.myError import withOutGameWinError


def initWin(switch = 0):
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
    hWnd = win32gui.FindWindow("UnityWndClass","LimbusCompany")
    if(hWnd != 0):
        result = True
    else:
        myLog("error","Can't Find The Game Window")
        raise withOutGameWinError("没有找到游戏窗口")
    
    # 若最小化，则将其显示
    if win32gui.IsIconic(hWnd):
        win32gui.ShowWindow(hWnd, win32con.SW_SHOWMAXIMIZED)

    # 置顶窗口
    win32gui.SetForegroundWindow(hWnd)

    #大小为1280，720
    if(switch == 0 or switch == 1):
        resize_window(hWnd, 1280, 720)

    #窗口默认至左上角（0，0）
    if(switch == 0 or switch == 2):
        move_window(hWnd, 0, 0)
    
    #回收句柄
    windll.user32.ReleaseDC(hWnd)

    return result