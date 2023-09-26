# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/9/16 9:25
* File  : main.py
* Project   :LixAssistantLimbusCompany
* Function  :迅速截屏并保存
'''

from win32gui import GetDesktopWindow, GetWindowDC, GetWindowRect, ReleaseDC, DeleteObject
from win32ui import CreateDCFromHandle, CreateBitmap
from ctypes import windll
from win32con import SRCCOPY
from numpy import fromstring
from cv2 import cvtColor, COLOR_BGRA2BGR, imwrite
from threading import Lock
from src.log.nbLog import myLog


lock = Lock()


def winCap():
    '''
    截屏函数，并将图片保存为screenshot.png
    '''
    
    global lock
    with lock:
        # 排除缩放干扰
        windll.user32.SetProcessDPIAware()

        
        myLog("debug","Get Pic")
        hdesktop = GetDesktopWindow()

        width = GetWindowRect(hdesktop)[2]
        height = GetWindowRect(hdesktop)[3]
        # 获取窗口的设备上下文DC(Device Context)
        desktop_dc = GetWindowDC(hdesktop)
        # 根据窗口的DC创建一个内存中的DC
        img_dc = CreateDCFromHandle(desktop_dc)

        # 创建一个设备兼容的DC
        mem_dc = img_dc.CreateCompatibleDC()

        # 创建一个位图对象准备保存图片
        screenshot = CreateBitmap()
        screenshot.CreateCompatibleBitmap(img_dc, width, height)
        mem_dc.SelectObject(screenshot)

        mem_dc.BitBlt((0, 0), (width, height), img_dc, (0, 0), SRCCOPY)

        bmpinfo = screenshot.GetInfo()
        bmpstr = screenshot.GetBitmapBits(True)

        img = fromstring(bmpstr, dtype='uint8')
        img.shape = (bmpinfo['bmHeight'], bmpinfo['bmWidth'], 4)

        src = cvtColor(img, COLOR_BGRA2BGR)
        imwrite("./pic/screenshot.png", src)

        # 删除内存中的DC对象，释放资源
        mem_dc.DeleteDC()
        img_dc.DeleteDC()
        ReleaseDC(hdesktop, desktop_dc)

        # 删除位图对象以便释放资源
        DeleteObject(screenshot.GetHandle())

        #简单压缩
        #simpleCompress()




