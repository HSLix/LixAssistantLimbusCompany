# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/9/16 9:25
* File  : autoFindOrClick
* Project   :LixAssistantLimbusCompany
* Function  :根据传入模板图片识别截图并点击
'''
from random import uniform
from ctypes import windll
import win32api, win32con
from src.common.picLocate import *
from src.common.myTime import myTimeSleep
from src.log.nbLog import myLog





def autoSinClick(img_model_path, name, addX=0, addY=0,waitTime = 0.7, clickCount = 1, correctRate = 0.8):
    """
    输入一个图片模板，自动点击截图中一个
    :param img_model_path: 图片模板相对坐标
    :param name:当前进程名字/代号
    :param addX:x坐标偏移，默认为0
    :param addY:y坐标偏移，默认为0
    :param waitTime:点击一次后的等待时间
    :param clickCount:点击次数，默认为1
    :param correctRate:准确率，0.8起步会比较准确
    :return: 是否完成点击
    """

    
    #随机数点击
    addX += uniform(-10, 10)
    addY += uniform(-10, 10)
    #图像定位
    center = getSinCenXY(img_model_path, correctRate)
    if center == None:
        msg = "Can't Find " + name
        myLog("debug",msg)
        return False
    
    msg = "Auto Clicking " + name
    myLog("debug",msg)
    cx = int(center[0] + addX)
    cy = int(center[1] + addY)

    
    
    try:
        windll.user32.SetCursorPos(cx,cy)
    except:
        myLog("error","The Mouse is used by other man.")
        
    while(clickCount > 0):
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN,cx,cy,0,0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP,cx,cy,0,0)
        clickCount -= 1
        myTimeSleep(waitTime)

    #归零避免妨碍识图
    try:
        windll.user32.SetCursorPos(1,1)
    except:
        myLog("error","The Mouse is used by other man.")
    #win32api.SetCursorPos((1,1))
    return True

def autoMulClick(img_model_path, name, addX=0, addY=0, waitTime = 0.5, clickCount = 1, correctRate = 0.9):
    """
    输入一个图片模板，自动点击截图中一个
    :param img_model_path: 图片模板相对坐标
    :param name:当前进程名字/代号
    :param addX:x坐标偏移，默认为0
    :param addY:y坐标偏移，默认为0
    :param waitTime:点击一次后的等待时间
    :param clickCount:点击次数，默认为1
    :param correctRate:准确率，0.8起步会比较准确
    :return: 是否完成点击
    """
    

    center = getMulCenXY(img_model_path, correctRate)
    if center == None:
        msg = "Can't Find " + name
        myLog("debug",msg)
        return False

    msg = "Auto Clicking " + name
    myLog("debug",msg)
    
    
    targetCount = len(center)
    i = 0
    while clickCount > 0:
            while i < targetCount:
                #随机数点击
                addX += uniform(-10, 10)
                addY += uniform(-10, 10)

                cx = int(center[i + 0] + addX)
                cy = int(center[i + 1] + addY)

                #具体点击实现
                try:
                    windll.user32.SetCursorPos(cx,cy)
                except:
                    myLog("error","The Mouse is used by other man.")
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN,cx,cy,0,0)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP,cx,cy,0,0)
                myTimeSleep(waitTime)
                i += 2
            clickCount -= 1

    #归零避免妨碍识图
    try:
        windll.user32.SetCursorPos(1,1)
    except:
        myLog("error","The Mouse is used by other man.")
    #win32api.SetCursorPos((1,1))
    return True


def autoFind(img_model_path, name, correctRate = 0.9):
    """
    输入一个图片模板，自动点击
    :param img_model_path: 图片模板相对坐标
    :param name:当前进程名字/代号
    :param resetSwitch:设置为1时，找到目标后，鼠标移至目标中心
    :param return: 是否在截屏中找到目标模板
    """

    
    #图像定位
    center = getSinCenXY(img_model_path, correctRate)
    if center == None:
        msg = "Can't Find " + name
        myLog("debug",msg)
        return False
    msg = "Have Found " + name
    myLog("debug",msg)

    return True