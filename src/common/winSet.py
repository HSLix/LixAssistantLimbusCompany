# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/9/16 9:25
* File  : winSet.py       
* Project   :LixAssistantLimbusCompany
* Function  :对游戏窗口进行操作
'''
from ctypes import windll
from ctypes.wintypes import HWND

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0X0002
SWP_NOZORDER = 0x0004

def move_window(handle: HWND, x: int, y: int):
    """移动窗口到坐标(x, y)

    Args:
        handle (HWND): 窗口句柄
        x (int): 横坐标
        y (int): 纵坐标
    """
    # 排除缩放干扰
    windll.user32.SetProcessDPIAware()
    windll.user32.SetWindowPos(handle, 0, x, y, 0, 0, SWP_NOSIZE | SWP_NOZORDER)

def resize_window(handle: HWND, width: int, height: int):
    """设置窗口大小为width × height

    Args:
        handle (HWND): 窗口句柄
        width (int): 宽
        height (int): 高
    """
    # 排除缩放干扰
    windll.user32.SetProcessDPIAware()
    windll.user32.SetWindowPos(handle, 0, 0, 0, width, height, SWP_NOMOVE | SWP_NOZORDER)