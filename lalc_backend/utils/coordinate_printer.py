import win32gui
import win32api
import time
import threading
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

def print_coordinate_on_event(hwnd):
    """
    监测鼠标状态，满足以下条件时打印坐标（以游戏窗口客户区左上角为原点）：
    1. 左键点击时
    2. 鼠标5秒未移动时
    3. 用户按下 Ctrl+Q 时停止
    
    注意：坐标系已统一为「客户区坐标」，与 background_click 使用的坐标一致
    """
    # 获取初始鼠标位置（屏幕坐标）
    last_x, last_y = get_cursor_pos()
    last_move_time = time.time()

    print("开始监测坐标（按Ctrl+Q停止）...")
    try:
        while True:
            # 检查键盘输入 - Ctrl+Q 停止程序
            ctrl_state = win32api.GetKeyState(0x11)  # Ctrl键状态
            q_state = win32api.GetKeyState(0x51)     # Q键状态
            
            # 检查是否同时按下 Ctrl 和 Q
            if (ctrl_state < 0) and (q_state < 0):  # < 0 表示按键被按下
                print("检测到 Ctrl+Q，停止坐标监测")
                break

            # 获取当前鼠标状态
            current_x, current_y = get_cursor_pos()
            left_button_state = win32api.GetKeyState(0x01)  # 左键状态

            # 转换为当前客户区坐标（关键：统一坐标系）
            try:
                client_x, client_y = win32gui.ScreenToClient(hwnd, (current_x, current_y))
            except:
                # 窗口无效时跳过
                time.sleep(0.05)
                continue

            # 条件1：左键点击（检测按下瞬间）
            if left_button_state in (-128, -127):  # 按下状态
                print(f"左键点击 - 客户区坐标: ({client_x}, {client_y})")
                last_move_time = time.time()
                last_x, last_y = current_x, current_y
                time.sleep(0.1)  # 防抖

            # 条件2：鼠标5秒未移动（基于屏幕坐标判断是否移动）
            else:
                if (current_x != last_x) or (current_y != last_y):
                    # 鼠标移动，更新状态
                    last_x, last_y = current_x, current_y
                    last_move_time = time.time()
                else:
                    # 鼠标5秒未移动
                    if time.time() - last_move_time >= 5:
                        print(f"鼠标静止 - 客户区坐标: ({client_x}, {client_y})")
                        last_move_time = time.time()  # 重置时间，避免连续打印

            time.sleep(0.05)  # 降低CPU占用

    except KeyboardInterrupt:
        print("停止坐标监测")


# 示例：单独运行时需要先获取窗口句柄
if __name__ == "__main__":
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
    from input.game_window import find_game_window
    
    try:
        # 查找游戏窗口
        hwnd = find_game_window()
        if hwnd:
            print(f"找到游戏窗口，句柄: {hwnd}")
            print_coordinate_on_event(hwnd)
        else:
            print("未找到游戏窗口")
    except Exception as e:
        print(f"程序出错: {e}")