import win32gui
import win32api
import win32con
import time
import random
import ctypes

from input.game_click import (
    background_press,
    background_release,
    foreground_press,
    foreground_release,
)


def background_long_press(hwnd, x, y, duration=3):
    """
    后台长按：按下鼠标，保持指定时间后释放
    :param hwnd: 窗口句柄
    :param x: x坐标（客户端坐标）
    :param y: y坐标（客户端坐标）
    :param duration: 按下后到释放前的间隔时间（秒），默认3秒
    :return: 操作是否成功
    """
    if not hwnd or not win32gui.IsWindow(hwnd):
        return False

    try:
        # 发送鼠标按下消息
        background_press(hwnd, x, y)

        # 保持按下一段时间
        time.sleep(duration)

        # 发送鼠标释放消息
        background_release(hwnd, x, y)

        return True

    except Exception as e:
        raise e


def foreground_long_press(hwnd, x, y, duration=3):
    """
    前台长按：按下鼠标，保持指定时间后释放
    :param hwnd: 窗口句柄
    :param x: x坐标（客户端坐标）
    :param y: y坐标（客户端坐标）
    :param duration: 按下后到释放前的间隔时间（秒），默认3秒
    :return: 操作是否成功
    """
    if not hwnd or not win32gui.IsWindow(hwnd):
        return False

    try:
        # 发送鼠标按下消息
        foreground_press(hwnd, x, y)

        # 保持按下一段时间
        time.sleep(duration)

        # 发送鼠标释放消息
        foreground_release(hwnd, x, y)

        return True

    except Exception as e:
        raise e


if __name__ == "__main__":
    # 测试函数：需要先运行main.py获取hwnd
    import ctypes

    ctypes.windll.shcore.SetProcessDpiAwareness(2)
    from input.game_window import (
        set_window_size,
        find_game_window,
        set_background_focus,
    )

    try:
        hwnd = find_game_window()
        print(f"成功连接游戏窗口，句柄: {hwnd}")
        set_window_size(hwnd)
        # 测试后台长按
        print("测试后台长按（3秒）...")
        time.sleep(1)
        set_background_focus(hwnd)
        background_long_press(hwnd, 850, 660, duration=3)
        print("长按测试完成")

    except Exception as e:
        print(f"长按测试失败: {str(e)}")
