import win32gui
import win32api
import time
import random
import ctypes
from ctypes import wintypes
try:
    from input.game_click import background_press, background_release, foreground_press, foreground_release
except ImportError:
    from game_click import background_press, background_release, foreground_press, foreground_release

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

def background_swipe(hwnd, start_x, start_y, end_x, end_y, speed=1):
    """
    后台拖拽：从起点坐标拖拽到终点坐标
    :param hwnd: 窗口句柄
    :param start_x: 起点x坐标（客户端坐标）
    :param start_y: 起点y坐标（客户端坐标）
    :param end_x: 终点x坐标（客户端坐标）
    :param end_y: 终点y坐标（客户端坐标）
    :param speed: 拖拽速度，数值越小越快 
    :return: 操作是否成功
    """
    if not hwnd or not win32gui.IsWindow(hwnd):
        raise Exception(f"错误：窗口句柄无效（hwnd={hwnd}）")
    
    # set_focus(hwnd)

    try:
        # 将客户端坐标转换为屏幕坐标
        screen_start_point = win32gui.ClientToScreen(hwnd, (int(start_x), int(start_y)))
        screen_end_point = win32gui.ClientToScreen(hwnd, (int(end_x), int(end_y)))
        
        # 添加随机偏移
        screen_start_x = screen_start_point[0] + random.randint(-3, 3)
        screen_start_y = screen_start_point[1] + random.randint(-3, 3)
        screen_end_x = screen_end_point[0] + random.randint(-3, 3)
        screen_end_y = screen_end_point[1] + random.randint(-3, 3)
        
        # 计算步长和间隔时间
        steps = int(20 * speed)  # 步数
        sleep_time = 0.01 / speed  # 每步间隔时间

        origin_x, origin_y = get_cursor_pos()
        
        # 使用后台按下函数开始拖拽
        background_press(hwnd, start_x, start_y)
        time.sleep(0.05 + random.random() * 0.05)
        
        # 计算每步的增量
        delta_x = (screen_end_x - screen_start_x) / steps
        delta_y = (screen_end_y - screen_start_y) / steps
        
        # 执行拖拽过程
        for i in range(steps + 1):
            current_x = int(screen_start_x + delta_x * i)
            current_y = int(screen_start_y + delta_y * i)
            ctypes.windll.user32.SetCursorPos(current_x, current_y)
            time.sleep(sleep_time)
        
        time.sleep(0.5)
        # 使用后台释放函数结束拖拽
        background_release(hwnd, end_x, end_y)

        ctypes.windll.user32.SetCursorPos(origin_x, origin_y)

        return True

    except Exception as e:
        raise Exception(f"后台拖拽失败：{str(e)}")


def foreground_swipe(hwnd, start_x, start_y, end_x, end_y, speed=0.25):
    """
    前台拖拽：从起点坐标拖拽到终点坐标
    需要将客户端坐标转换为屏幕坐标
    :param hwnd: 窗口句柄
    :param start_x: 起点x坐标（客户端坐标）
    :param start_y: 起点y坐标（客户端坐标）
    :param end_x: 终点x坐标（客户端坐标）
    :param end_y: 终点y坐标（客户端坐标）
    :param speed: 拖拽速度，数值越小越快 
    :return: 操作是否成功
    """
    if not hwnd or not win32gui.IsWindow(hwnd):
        raise Exception(f"错误：窗口句柄无效（hwnd={hwnd}）")

    try:
        # 将客户端坐标转换为屏幕坐标
        screen_start_point = win32gui.ClientToScreen(hwnd, (int(start_x), int(start_y)))
        screen_end_point = win32gui.ClientToScreen(hwnd, (int(end_x), int(end_y)))
        
        # 添加随机偏移
        screen_start_x = screen_start_point[0] + random.randint(-3, 3)
        screen_start_y = screen_start_point[1] + random.randint(-3, 3)
        screen_end_x = screen_end_point[0] + random.randint(-3, 3)
        screen_end_y = screen_end_point[1] + random.randint(-3, 3)
        
        # 计算步长和间隔时间
        steps = int(20 * speed)  # 步数
        sleep_time = 0.01 / speed  # 每步间隔时间
        
        # 使用前台按下函数开始拖拽
        foreground_press(hwnd, start_x, start_y)
        time.sleep(0.05 + random.random() * 0.05)
        
        # 计算每步的增量
        delta_x = (screen_end_x - screen_start_x) / steps
        delta_y = (screen_end_y - screen_start_y) / steps
        
        # 执行拖拽过程
        for i in range(steps + 1):
            current_x = int(screen_start_x + delta_x * i)
            current_y = int(screen_start_y + delta_y * i)
            
            # 移动鼠标
            ctypes.windll.user32.SetCursorPos(current_x, current_y)
            time.sleep(sleep_time)
        
        time.sleep(0.5)
        # 使用前台释放函数结束拖拽
        foreground_release(hwnd, end_x, end_y)

        return True

    except Exception as e:
        raise Exception(f"前台拖拽失败：{str(e)}")


if __name__ == "__main__":
    # 测试函数：需要先运行main.py获取hwnd
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(2)

    try:
        from game_window import find_game_window, set_background_focus
        hwnd = find_game_window()
        print(f"成功连接游戏窗口，句柄: {hwnd}")
        
        # 测试后台拖拽
        print("测试后台拖拽...")
        set_background_focus(hwnd)
        # for i in range(1):
        #     background_swipe(hwnd, 815, 395, 815, 300, speed=1)
        #     time.sleep(0.5)
        # time.sleep(1)
        background_swipe(hwnd, 130, 320, 130, 720)
        
        # 测试前台拖拽
        # print("测试前台拖拽...")
        # foreground_swipe(hwnd, 130, 500, 130, 320, speed=1.0)
        # time.sleep(1)
        
        print("拖拽测试完成")
        
    except Exception as e:
        print(f"拖拽测试失败: {str(e)}")