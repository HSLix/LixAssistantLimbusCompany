# coding: utf-8
from pynput import mouse, keyboard
from pynput.mouse import Button
from time import sleep
from random import uniform

from .game_window import initMouseBasePoint, initMouseHomePoint
from globals import ignoreScaleAndDpi



mk = None

def get_mouse_keyboard():
    global mk
    if (mk is None):
        mk = MOUSE_KEYBOARD()
    return mk


def random_offset(origin_val, left_offset=0.05, right_offset=0.1):
    """
    此函数用于生成一个随机数, 该随机数会在 origin_val + left_offset 和 origin_val + right_offset 之间

    :param left_offset: 随机数向左偏移值
    :param right_offset: 随机数向右偏移值
    :return: 包含两个随机数的列表
    """
    return float(uniform(origin_val-left_offset, origin_val+right_offset))


class MOUSE_KEYBOARD:
    def __init__(self):
        self.kb = keyboard.Controller()
        self.ms = mouse.Controller()
        self.mouse_basepoint = [0, 0]
        self.mouse_homepoint = initMouseHomePoint()
        # ignoreScaleAndDpi()

    def mouseBackHome(self):
        self.ms.position = (self.mouse_homepoint[0], self.mouse_homepoint[1])

        
    def updateMouseBasepoint(self):
        self.mouse_basepoint = initMouseBasePoint()
    
    
    def dragMouse(self, coordinate:list, drag_time:float = 0.6):
        """
        从按住鼠标起点坐标到终点坐标移动
        """
        start_x, start_y, end_x, end_y = self.mouse_basepoint[0]+coordinate[0], self.mouse_basepoint[1]+coordinate[1], self.mouse_basepoint[0]+coordinate[2], self.mouse_basepoint[1]+coordinate[3]
        # 移动鼠标到起始位置
        self.ms.position = (start_x, start_y)
        # 按下鼠标左键
        self.ms.press(Button.left)

        drag_time = random_offset(drag_time, 0.1, 0.5)
        # 计算总步数
        steps = int(drag_time*100)
        if (steps == 0):
            steps = 1
        # 计算每一步的时间间隔
        interval =  drag_time / steps
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
            sleep(random_offset(interval, 0.002, 0.002))

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
            sleep(random_offset(0.1))
            self.ms.release(Button.left)
            sleep(random_offset(rest_time))

    def scroll(self, offset:list, scroll_count:int = 1, rest_time:float=0.1):
        """
        模拟鼠标滚动
        offset: [0,-1]即下滚动一单位，也就是滚动一下滚轮的效果
        scroll_count: 滚动次数，默认一次
        rest_time: 滚动后的休息时间，默认 0.1 s，滚动次数为 0 时不生效
        """
        for _ in range(scroll_count):
            self.ms.scroll(offset[0], offset[1])
            sleep(random_offset(rest_time, right_offset=0.05, left_offset=rest_time-0.005))

    


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
            sleep(random_offset(0.1))
            self.kb.release(middle_key)
            sleep(random_offset(rest_time))

    def listenMouse(self):
        """
        坐标测试
        """
        self.updateMouseBasepoint()
        def on_click(x, y, button, pressed):
            # 监听鼠标点击事件
            if pressed:
                print(f"鼠标点击: ({x - self.mouse_basepoint[0]}, {y - self.mouse_basepoint[1]}), 按钮: {button}")


        # 滚动监听
        def on_scroll(x, y, dx, dy):
            print('{0}滚动中... 从({1},{2})滚动({3},{4})'.format('向下：' if dy < 0 else '向上：', x, y, dx, dy))


        # 滚动监听
        def on_scroll(x, y, dx, dy):
            print('{0}滚动中... 从({1},{2})滚动({3},{4})'.format('向下：' if dy < 0 else '向上：', x, y, dx, dy))

        def on_press(key):
            # 按下任意键时停止监听
            print("检测到按键，停止监听鼠标点击。")
            return False  # 返回 False 停止监听键盘
        
        

        print("Start Listenning")

        # 启动鼠标点击监听
        mouse_listener = mouse.Listener(on_click=on_click, on_scroll=on_scroll)
        mouse_listener = mouse.Listener(on_click=on_click, on_scroll=on_scroll)
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

    
