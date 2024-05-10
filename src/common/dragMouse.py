# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2024/02/26 23:22
* File  : dragMouse.py
* Project   :LixAssistantLimbusCompany
* Function  :让鼠标拖拽
'''
import time
from ctypes import *
from globalVar import screenWidth, screenHeigh
from src.common.picLocate import getSinCenXY
from src.common.getPic import winCap
from src.log.myLog import myLog
from src.common.myTime import mySleep



class POINT(Structure):
        _fields_ = [
                ("x", c_ulong),
                ("y", c_ulong)
                ]
        
MOUSEEVENTF_LEFTDOWN = 0x0002 
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000       

def change_speed(cx, x, walkX):
        if abs(walkX) < 20:
                walkX *= 2

        elif abs(cx - x) >= 1000:
                if(abs(walkX) < 600):
                        walkX *= 2
                        
        elif abs(cx - x) >= 500:
                if(abs(walkX) > 500):
                        walkX /= 2
                        
        elif abs(cx - x) >= 300:
                if(abs(walkX) > 200):
                        walkX /= 2

        elif abs(cx - x) >= 100:
                if(abs(walkX) > 100):
                        walkX /= 2

        if ((x - cx) * walkX < 0):
                walkX *= -1
        
        return walkX

def drag_to(from_x, from_y, target_x, target_y):
        # 排除缩放干扰
        windll.user32.SetProcessDPIAware()

        #移动到起始位置
        windll.user32.SetCursorPos(from_x ,from_y)
        
        mySleep(1)

        # 鼠标左键按下
        windll.user32.mouse_event(MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0) 

        fx = from_x * 65535 / screenWidth
        fy = from_y * 65535 / screenHeigh
        tx = target_x * 65535 / screenWidth
        ty = target_y * 65535 / screenHeigh

        walk_x = 1
        walk_y = 1

        if (tx - fx < 0):
                walk_x = -1
        if (ty - fy < 0):
                walk_y = -1

        count = 0

        mySleep(0.5)

        while ((abs(fx - tx) >= 100 or abs(fy - ty) >= 100) and count < 30000):
                if (abs(fx - tx) >= 100):
                        fx += walk_x
                if (abs(fy - ty) >= 100):
                        fy += walk_y
                windll.user32.mouse_event(MOUSEEVENTF_ABSOLUTE |MOUSEEVENTF_MOVE, int(fx), int(fy), 0, 0)
                change_speed(fx, tx, walk_x)
                change_speed(fy, ty, walk_y)
                #print(str(fx) + " " + str(fy) + " " + str(walk_x) + " " + str(walk_y) + " " + str(tx) + " " + str(ty))
                count += 1

        # 设置鼠标左键释放，完成点击事件
        windll.user32.mouse_event(MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def drag_mouse(img_model_path, changeX, changeY):
        # 排除缩放干扰
        windll.user32.SetProcessDPIAware()

        x = changeX
        y = changeY

        # 调整适应绝对坐标
        
        x *= 65535 / screenWidth
        y *= 65535 / screenHeigh
        
        x = int(x)
        y = int(y)
        time.sleep(1)
        # 鼠标左键按下
        windll.user32.mouse_event(MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0) 
        
        #获取鼠标位置
        point = POINT()
        windll.user32.GetCursorPos(byref(point))

        (fromX, fromY) = (point.x, point.y)
        fromX *= 65535 / screenWidth
        fromY *= 65535 / screenHeigh
        fromX = int(fromX)
        fromY = int(fromY)

        # 预移动，避免卡顿闪移
        windll.user32.mouse_event(MOUSEEVENTF_ABSOLUTE |MOUSEEVENTF_MOVE, int(fromX) + 10, int(fromY) + 10, 0, 0)

        center = getSinCenXY(img_model_path, 0.7)
        if center == None:
                msg = "Can't Drag " + img_model_path
                myLog("debug",msg)
                return
        
        picX = lambda cx: cx * 65535 / screenWidth
        picY = lambda cy: cy * 65535 / screenHeigh

        cx = picX(center[0])
        cy = picY(center[1])


        # 移动鼠标指针
        if x > picX(center[0]):
                walkX = 16
        else:
                walkX = -16
        
        if y > picY(center[1]):
                walkY = 16
        else:
                walkY = -16

        cx = picX(center[0])
        cy = picY(center[1])

        flag = True
        noneTime = 0
        i = 0
        while flag:
                flag = False
                if abs(cx - x) >= 100 or abs(cy - y) >= 100:
                        flag = True
                        # 速度
                        if(i < 4):
                                i += 1
                                time.sleep(0.0001)
                        else:
                                walkX = change_speed(cx, x, walkX)
                                walkY = change_speed(cy, y, walkY)           
                        # 方向
                        if (cx > x and walkX > 0) or (cx < x and walkX < 0):
                                walkX *= -1
                        if (cy > y and walkY > 0) or (cy < y and walkY < 0):
                                walkY *= -1
                                
                # 移动并更新
                if abs(cx - x) >= 50:
                        fromX += walkX
                if abs(cx - y) >= 50:
                        fromY += walkY
                print("x ", x, " y ", y, " cx ", cx, " cy ", cy, " WalkX ", walkX, " walkY ", walkY )
                windll.user32.mouse_event(MOUSEEVENTF_ABSOLUTE |MOUSEEVENTF_MOVE, int(fromX), int(fromY), 0, 0)

                winCap()
                center = getSinCenXY(img_model_path, 0.7)
                if center != None:
                        noneTime = 0
                        cx = picX(center[0])
                        cy = picY(center[1])
                else:
                        noneTime += 1
                        if noneTime >= 80:
                                msg = "Can't find " + img_model_path + ". Stop Drag!"
                                myLog("debug",msg)
                                return
                # time.sleep(0.000000001)
                #time.sleep(1)
        #time.sleep(3)  # 微小的停顿来模拟人类行为

        # 设置鼠标左键释放，完成点击事件
        windll.user32.mouse_event(MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

        '''windll.user32.GetCursorPos(byref(point))
        (x, y) = (point.x, point.y)
        print(str(x) + " " + str(y))'''