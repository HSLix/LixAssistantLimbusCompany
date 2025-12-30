import win32gui
import win32api
import win32con
import win32ui  # 添加win32ui导入
import time
import random
import ctypes
from ctypes import wintypes

# 定义Windows API函数和结构体
user32 = ctypes.windll.user32

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def get_cursor_pos():
    """
    使用ctypes调用Windows API获取鼠标位置
    :return: (x, y) 鼠标坐标元组
    """
    point = POINT()
    result = user32.GetCursorPos(ctypes.pointer(point))
    if result:
        return point.x, point.y
    else:
        raise Exception("Failed to get cursor position")

def get_client_rect(hwnd):
    """
    获取窗口客户区尺寸
    :param hwnd: 窗口句柄
    :return: 包含宽度和高度的字典
    """
    client_rect = win32gui.GetClientRect(hwnd)
    return {
        "width": client_rect[2] - client_rect[0],
        "height": client_rect[3] - client_rect[1]
    }

def background_click(hwnd, x, y):
    """
    后台点击,如果检测到鼠标左键已经按下，会先发送释放消息再执行点击
    :param hwnd: 窗口句柄
    :param x: x坐标（客户端坐标）
    :param y: y坐标（客户端坐标）
    :return: 操作是否成功
    """
    if not hwnd or not win32gui.IsWindow(hwnd):
        return False

    try:
        # 使用客户端坐标（相对于客户区左上角）
        click_x = int(x) + random.randint(-3, 3)
        click_y = int(y) + random.randint(-3, 3)

        # 将客户端坐标转换为屏幕坐标
        screen_point = win32gui.ClientToScreen(hwnd, (click_x, click_y))
        screen_x, screen_y = screen_point

        # 使用 MAKELONG 将坐标打包成 lParam
        lparam = win32api.MAKELONG(screen_x, screen_y)
        
        # 保存当前鼠标位置
        origin_x, origin_y = get_cursor_pos()
        
        # 移动鼠标到目标位置
        ctypes.windll.user32.SetCursorPos(screen_x, screen_y)
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam) 

        # 检查鼠标左键状态
        left_button_state = win32api.GetKeyState(win32con.VK_LBUTTON)
        is_left_pressed = left_button_state < 0  # 负数表示按键被按下

        # 如果鼠标左键已经按下，先释放
        if is_left_pressed:
            win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)
            time.sleep(0.01)
        
        # 发送鼠标按下消息
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, 0, lparam)
        time.sleep(0.04 + random.random() * 0.05)
        
        # 发送鼠标释放消息
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)
        time.sleep(0.03 + random.random() * 0.03)
        
        # 恢复鼠标位置
        ctypes.windll.user32.SetCursorPos(origin_x, origin_y)

        return True

    except Exception as e:
        raise e

def background_press(hwnd, x, y):
    """
    后台按下：只发送鼠标按下消息，不释放
    x, y 为客户端坐标（相对于窗口客户区左上角）
    :param hwnd: 窗口句柄
    :param x: x坐标（客户端坐标）
    :param y: y坐标（客户端坐标）
    :return: 操作是否成功
    """
    if not hwnd or not win32gui.IsWindow(hwnd):
        # print(f"错误：窗口句柄无效（hwnd={hwnd}）")
        return False
    
    # set_focus(hwnd)

    try:
        # 使用客户端坐标（相对于客户区左上角）
        click_x = int(x) + random.randint(-3, 3)
        click_y = int(y) + random.randint(-3, 3)

        # 将客户端坐标转换为屏幕坐标，以确保与前台点击的一致性
        screen_point = win32gui.ClientToScreen(hwnd, (click_x, click_y))
        screen_x, screen_y = screen_point

        # 使用 MAKELONG 将坐标打包成 lParam
        lparam = win32api.MAKELONG(screen_x, screen_y)
        
        ctypes.windll.user32.SetCursorPos(screen_x, screen_y)

        # 检查鼠标左键状态
        left_button_state = win32api.GetKeyState(win32con.VK_LBUTTON)
        is_left_pressed = left_button_state < 0  # 负数表示按键被按下
        
        # 如果鼠标左键已经按下，先释放
        if is_left_pressed:
            win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)
            time.sleep(0.01)

        # 发送鼠标按下消息
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, 0, lparam)

        # print(f"后台按下成功：客户端坐标=({click_x}, {click_y})")

        return True

    except Exception as e:
        raise e

def background_release(hwnd, x, y):
    """
    后台释放：只发送鼠标释放消息，不按下
    x, y 为客户端坐标（相对于窗口客户区左上角）
    :param hwnd: 窗口句柄
    :param x: x坐标（客户端坐标）
    :param y: y坐标（客户端坐标）
    :return: 操作是否成功
    """
    if not hwnd or not win32gui.IsWindow(hwnd):
        # print(f"错误：窗口句柄无效（hwnd={hwnd}）")
        return False
    
    # set_focus(hwnd)

    try:
        # 使用客户端坐标（相对于客户区左上角）
        click_x = int(x) + random.randint(-3, 3)
        click_y = int(y) + random.randint(-3, 3)

        # 将客户端坐标转换为屏幕坐标，以确保与前台点击的一致性
        screen_point = win32gui.ClientToScreen(hwnd, (click_x, click_y))
        screen_x, screen_y = screen_point

        # 使用 MAKELONG 将坐标打包成 lParam
        lparam = win32api.MAKELONG(screen_x, screen_y)
        
        ctypes.windll.user32.SetCursorPos(screen_x, screen_y)
        # 发送鼠标释放消息
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)

        # print(f"后台释放成功：客户端坐标=({click_x}, {click_y})")

        return True

    except Exception as e:
        raise e

def foreground_click(hwnd, x, y):
    """
    前台点击：x, y 为客户端坐标
    需要将客户端坐标转换为屏幕坐标
    :param hwnd: 窗口句柄
    :param x: x坐标（客户端坐标）
    :param y: y坐标（客户端坐标）
    :return: 操作是否成功
    """
    if not hwnd or not win32gui.IsWindow(hwnd):
        # print(f"错误：窗口句柄无效（hwnd={hwnd}）")
        return False

    try:
        # 将客户端坐标转换为屏幕坐标
        screen_point = win32gui.ClientToScreen(hwnd, (int(x), int(y)))
        screen_x = screen_point[0] + random.randint(-3, 3)
        screen_y = screen_point[1] + random.randint(-3, 3)

        # 移动鼠标并执行点击
        ctypes.windll.user32.SetCursorPos(screen_x, screen_y)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, screen_x, screen_y, 0, 0)
        time.sleep(0.05 + random.random() * 0.05)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, screen_x, screen_y, 0, 0)

        # print(f"前台点击成功：客户端坐标=({x}, {y}) → 屏幕坐标=({screen_x}, {screen_y})")

        return True

    except Exception as e:
        raise e

def foreground_press(hwnd, x, y):
    """
    前台按下：只按下鼠标，不释放
    x, y 为客户端坐标，需要转换为屏幕坐标
    :param hwnd: 窗口句柄
    :param x: x坐标（客户端坐标）
    :param y: y坐标（客户端坐标）
    :return: 操作是否成功
    """
    if not hwnd or not win32gui.IsWindow(hwnd):
        # print(f"错误：窗口句柄无效（hwnd={hwnd}）")
        return False

    try:
        # 将客户端坐标转换为屏幕坐标
        screen_point = win32gui.ClientToScreen(hwnd, (int(x), int(y)))
        screen_x = screen_point[0] + random.randint(-3, 3)
        screen_y = screen_point[1] + random.randint(-3, 3)

        # 移动鼠标并按下
        ctypes.windll.user32.SetCursorPos(screen_x, screen_y)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, screen_x, screen_y, 0, 0)

        # print(f"前台按下成功：客户端坐标=({x}, {y}) → 屏幕坐标=({screen_x}, {screen_y})")

        return True

    except Exception as e:
        raise e

def foreground_release(hwnd, x, y):
    """
    前台释放：只释放鼠标，不按下
    x, y 为客户端坐标，需要转换为屏幕坐标
    :param hwnd: 窗口句柄
    :param x: x坐标（客户端坐标）
    :param y: y坐标（客户端坐标）
    :return: 操作是否成功
    """
    if not hwnd or not win32gui.IsWindow(hwnd):
        # print(f"错误：窗口句柄无效（hwnd={hwnd}）")
        return False

    try:
        # 将客户端坐标转换为屏幕坐标
        screen_point = win32gui.ClientToScreen(hwnd, (int(x), int(y)))
        screen_x = screen_point[0] + random.randint(-3, 3)
        screen_y = screen_point[1] + random.randint(-3, 3)

        # 移动鼠标并释放
        ctypes.windll.user32.SetCursorPos(screen_x, screen_y)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, screen_x, screen_y, 0, 0)

        # print(f"前台释放成功：客户端坐标=({x}, {y}) → 屏幕坐标=({screen_x}, {screen_y})")

        return True

    except Exception as e:
        raise e



if __name__ == "__main__":
    # 测试函数：需要先运行main.py获取hwnd
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
    from game_window import set_window_size
    from game_window import find_game_window
    from game_window import set_background_focus
    try:
        hwnd = find_game_window()
        print(f"成功连接游戏窗口，句柄: {hwnd}")
        set_window_size(hwnd)
        # 测试后台点击
        print("测试后台点击...")
        time.sleep(1)
        set_background_focus(hwnd)
        background_click(hwnd, 1140, 590)
        # pos = (200, 250)
        # next_x = 150
        # next_y = 200
        # l = []
        # for i in range(2):
        #     for j in range(4):
        #         # background_click(hwnd, pos[0]+(j)*next_x, pos[1]+(i)*next_y)
        #         l.append((pos[0]+(j)*next_x, pos[1]+(i)*next_y))
        # print(l)

    #     for x, y in {"Yi Sang":[290,240], "Faust":[420,240], "Don Quixote":[550,240], "Ryoshu":[680,240], "Meursault":[810,240], "Hong Lu":[940,240],
    # "Heathcliff":[290, 440], "Ishmael":[420, 440], "Rodion":[550, 440], "Sinclair":[680, 440], "Outis":[810, 440], "Gregor":[940, 440]}.values():
            # background_click(hwnd, x, y)
    #         time.sleep(0.3)
        
        # 测试前台点击
        # print("测试前台点击...")
        # foreground_click(hwnd, 880, 690)
        # time.sleep(1)
        
        print("点击测试完成")
        
    except Exception as e:
        print(f"点击测试失败: {str(e)}")