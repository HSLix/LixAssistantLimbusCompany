# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/11/25 22:46
* File  : classTask.py
* Project   :LixAssistantLimbusCompany
* Function  :将脚本任务抽象为一个类
'''
from src.common.autoFindOrClick import autoFind, autoMulClick, autoSinClick,clickAndDragTo,pure_click, pure_click_and_darg
from src.common.pressKey import pressKey
from src.common.getPic import winCap
from src.error.myError import userStopError
from src.log.myLog import myLog


import globalVar



class _task():
    '''在这里做前后台的切换'''
    __slots__ = ()

    def click_locate(self, cx, cy, name, wait_time = 0.9, clickCount = 1):
        pure_click(cx, cy, name, wait_time, clickCount)

    def click_locate_and_drag_to(self, begin_x, begin_y, end_x, end_y, name, wait_time = 0.9):
        pure_click_and_darg(begin_x, begin_y, end_x, end_y, name, wait_time)
    
    def single_target_click(self,img_model_path, name, addX=0, addY=0,waitTime = 0.8, clickCount = 1, correctRate = 0.75):
        """
        输入一个图片模板，自动点击截图中一个
        :param img_model_path: 图片模板相对坐标
        :param name:当前进程名字/代号
        :param addX:x坐标偏移，默认为0
        :param addY:y坐标偏移，默认为0
        :param waitTime:点击一次后的等待时间
        :param clickCount:点击次数，默认为1
        :param correctRate:准确率，0.7起步会比较准确
        :return: 是否完成点击
        """
        return autoSinClick(img_model_path, name, addX, addY,waitTime, clickCount, correctRate)

    def press_key(self,key, waitTime = 0.3, pressCount = 1):
        i = pressCount
        while i > 0:
            pressKey(key, waitTime)
            i -= 1

    def multiple_target_click(self,img_model_path, name, addX=0, addY=0,waitTime = 0.5, clickCount = 1, correctRate = 0.75):
        """
        输入一个图片模板，自动点击截图中多个
        :param img_model_path: 图片模板相对坐标
        :param name:当前进程名字/代号
        :param addX:x坐标偏移，默认为0
        :param addY:y坐标偏移，默认为0
        :param waitTime:点击一次后的等待时间
        :param clickCount:点击次数，默认为1
        :param correctRate:准确率，0.7起步会比较准确
        :return: 是否完成点击
        """
        return autoMulClick(img_model_path, name, addX, addY,waitTime, clickCount, correctRate)

    def cap_win(self):
        '''
        截屏函数，并将图片保存为screenshot.png
        '''
        winCap()

    def is_find(self,img_model_path, name, correctRate = 0.7):
        """
        输入一个图片模板，自动点击
        :param img_model_path: 图片模板相对坐标
        :param name:当前进程名字/代号
        :param correctRate:准确率，0.7起步会比较准确
        :param return: 是否在截屏中找到目标模板
        """
        return autoFind(img_model_path, name, correctRate)

    def click_drag_to(self,img_model_path, name, changeX = 0, changeY = 0, addX=0, addY=0,waitTime = 0.9, correctRate = 0.7):
        """
        输入一个图片模板，自动点击截图中一个
        :param img_model_path: 图片模板相对坐标
        :param name:当前进程名字/代号
        :param changeX:x坐标拖拽，默认为0
        :param changeY:y坐标拖拽，默认为0
        :param addX:x坐标偏移，默认为0
        :param addY:y坐标偏移，默认为0
        :param waitTime:点击一次后的等待时间
        :param correctRate:准确率，0.7起步会比较准确
        :return: 是否完成点击
        """
        return clickAndDragTo(img_model_path, name, changeX, changeY, addX, addY,waitTime, correctRate)


def beginAndFinishLog(func):
    '''一个任务开始与结束的日志'''
    def wrapper(*args, **kw):
        msg = "Begin " + func.__name__
        myLog("info", msg)

        #真正函数
        result = func(*args, **kw)

        msg = "Finish " + func.__name__
        myLog("info", msg)
        return result
    return wrapper

def checkAndExit(func):
    '''检查globalVar.exitCode符合条件结束该线程（程序）'''

    def wrapper(*args, **kw):

        if(globalVar.exitCode == -1):
            raise userStopError("用户主动终止程序")

        # 真正函数
        result = func(*args, **kw)

        if(globalVar.exitCode == -1):
            raise userStopError("用户主动终止程序")

        return result
    return wrapper
    
   

