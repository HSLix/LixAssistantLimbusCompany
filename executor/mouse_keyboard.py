# coding: utf-8
from pynput import mouse, keyboard
from pynput.mouse import Button
from time import sleep

from .game_window import initMouseBasePoint
from globals import ignoreScaleAndDpi



mk = None

def get_mouse_keyboard():
    global mk
    if (mk is None):
        mk = MOUSE_KEYBOARD()
    return mk


class MOUSE_KEYBOARD:
    def __init__(self):
        self.kb = keyboard.Controller()
        self.ms = mouse.Controller()
        # ignoreScaleAndDpi()
        

    def updateMouseBasepoint(self):
        self.mouse_basepoint = initMouseBasePoint()
    


    def dragMouse(self, coordinate:list, drag_time:float = 0.3):
        """
        从按住鼠标起点坐标到终点坐标移动
        """
        start_x, start_y, end_x, end_y = self.mouse_basepoint[0]+coordinate[0], self.mouse_basepoint[1]+coordinate[1], self.mouse_basepoint[0]+coordinate[2], self.mouse_basepoint[1]+coordinate[3]
        # 移动鼠标到起始位置
        self.ms.position = (start_x, start_y)
        # 按下鼠标左键
        self.ms.press(Button.left)

        # 计算总步数
        steps = int(drag_time*100)
        # 计算每一步的时间间隔
        interval = drag_time / steps
        # 计算每一步在 x 和 y 方向上的增量
        dx = (end_x - start_x) / steps
        dy = (end_y - start_y) / steps

        # 模拟鼠标移动
        for _ in range(steps):
            # 获取当前鼠标位置
            current_x, current_y = self.ms.position
            # 计算下一个位置
            next_x = current_x + dx
            next_y = current_y + dy
            # 移动鼠标到下一个位置
            self.ms.position = (next_x, next_y)
            # 等待一段时间
            sleep(interval)

        # 移动鼠标到最终位置
        self.ms.position = (end_x, end_y)
        # 释放鼠标左键
        self.ms.release(Button.left)

    def moveClick(self, coordinate:list=[0,0], click_count:int = 1, rest_time:float=0.1):
        """
        以游戏窗口左上角为基点移动鼠标和点击
        """
        self.ms.position = (self.mouse_basepoint[0] + coordinate[0], self.mouse_basepoint[1] + coordinate[1])
        print(f"clicking coordinate on base:{(coordinate[0],  coordinate[1])}")
        # print((self.mouse_basepoint[0] , self.mouse_basepoint[1] ))
        # print((coordinate[0],  coordinate[1]))
        for _ in range(click_count):
            self.ms.press(Button.left)
            sleep(0.1)
            self.ms.release(Button.left)
            sleep(rest_time)


    def pressKey(self, key:str, press_count:int = 1, rest_time:float=0.1):
        """
        模拟键盘按键
        只有 p enter 和 esc
        """
        if (key == "enter"):
            middle_key = keyboard.Key.enter
        elif(key == "esc"):
            middle_key = keyboard.Key.esc
        elif(key == "p"):
            middle_key = key
        else:
            print("Unknown Key!")
            return
        
        for _ in range(press_count):
            self.kb.press(middle_key)
            sleep(0.1)
            self.kb.release(middle_key)
            sleep(rest_time)

    def listenMouse(self):
        """
        坐标测试
        """
        self.updateMouseBasepoint()
        def on_click(x, y, button, pressed):
            # 监听鼠标点击事件
            if pressed:
                print(f"鼠标点击: ({x - self.mouse_basepoint[0]}, {y - self.mouse_basepoint[1]}), 按钮: {button}")

        def on_press(key):
            # 按下任意键时停止监听
            print("检测到按键，停止监听鼠标点击。")
            return False  # 返回 False 停止监听键盘
        
        

        print("Start Listenning")

        # 启动鼠标点击监听
        mouse_listener = mouse.Listener(on_click=on_click)
        mouse_listener.start()

        # 启动键盘监听
        with keyboard.Listener(on_press=on_press) as keyboard_listener:
            keyboard_listener.join()

        # 停止鼠标监听
        mouse_listener.stop()

if __name__ == "__main__":
    ignoreScaleAndDpi()

    
    mk = MOUSE_KEYBOARD()
    # gift_places = []
    # x = 860
    # y = 520
    # x_step = 115
    # y_step = 120
    # for i in range(3):
    #     for j in range(5):
    #        gift_places.append([x + j*x_step, y + i*y_step])
    
    # for c in gift_places:
    #     mk.moveClick(c)

    mk.listenMouse()  
    #dragMouse([100, 100, 100 0, 1000])

    
