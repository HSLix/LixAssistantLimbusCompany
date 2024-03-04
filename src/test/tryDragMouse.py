
import time
from ctypes import *



class POINT(Structure):
        _fields_ = [
                ("x", c_ulong),
                ("y", c_ulong)
                ]
        
MOUSEEVENTF_LEFTDOWN = 0x0002 
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000       
def drag_mouse(changeX, changeY):


        # 排除缩放干扰
        windll.user32.SetProcessDPIAware()

        # 获取鼠标位置
        point = POINT()
        windll.user32.GetCursorPos(byref(point))

        (x, y) = (point.x, point.y)
        print(str(x) + " " + str(y))

        #x = changeX
        #y = changeY

        # 调整适应绝对坐标
        x *= 65535 / 2560
        y *= 65535 / 1600

        x = int(x)
        y = int(y)

        # 鼠标左键按下
        windll.user32.mouse_event(MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0) 
        time.sleep(2) # 微小的停顿来模拟人类行为

        # 移动鼠标指针
        windll.user32.mouse_event(MOUSEEVENTF_ABSOLUTE |MOUSEEVENTF_MOVE, x + 10, y + 10, 0, 0)
        time.sleep(0.5)  # 微小的停顿来模拟人类行为
        windll.user32.mouse_event(MOUSEEVENTF_ABSOLUTE |MOUSEEVENTF_MOVE, x , y , 0, 0)

        # 设置鼠标左键释放，完成点击事件
        windll.user32.mouse_event(MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

        '''windll.user32.GetCursorPos(byref(point))
        (x, y) = (point.x, point.y)
        print(str(x) + " " + str(y))'''


drag_mouse(1000, 1000)