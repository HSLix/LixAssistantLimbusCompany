import win32gui
import win32con
import time
import ctypes
from ctypes import wintypes

from utils.logger import init_logger


logger = init_logger()


def get_cursor_pos():
    """
    获取当前鼠标位置
    :return: (x, y) 鼠标坐标元组，如果失败则返回 (None, None)
    """
    point = wintypes.POINT()
    result = ctypes.windll.user32.GetCursorPos(ctypes.pointer(point))
    while not result:
        time.sleep(0.1)
        logger.log("鼠标位置获取失败，正在尝试重新获取", level="WARNING")
        result = ctypes.windll.user32.GetCursorPos(ctypes.pointer(point))
    return point.x, point.y
    


def set_background_focus(hwnd)->bool:
    """
    将游戏窗口设置为输入焦点（用于后台操作）
    :param hwnd: 窗口句柄
    :return 是否显示最小化
    """
    res = False
    if hwnd:
        # 如果最小化则显示
        placement = win32gui.GetWindowPlacement(hwnd)
        if placement[1] == win32con.SW_SHOWMINIMIZED:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.5)
            res = True

        # 设置窗口的输入状态
        win32gui.EnableWindow(hwnd, True)

        # 发送激活消息（但不改变Z序）
        win32gui.SendMessage(hwnd, win32con.WM_ACTIVATE, win32con.WA_ACTIVE, 0)

        # 设置焦点状态
        win32gui.SendMessage(hwnd, win32con.WM_SETFOCUS, 0, 0)

    return res


def set_foreground_focus(hwnd):
    """
    将游戏窗口设置为前台焦点（用于前台操作）
    除了显示最小化的窗口外，还会将窗口置于前台并设置键盘焦点
    :param hwnd: 窗口句柄
    :return 是否显示最小化
    """
    res = False
    if hwnd:
        # 如果最小化则显示
        placement = win32gui.GetWindowPlacement(hwnd)
        if placement[1] == win32con.SW_SHOWMINIMIZED:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.5)
            res = True
        
        # 将窗口置于前台
        win32gui.SetForegroundWindow(hwnd)
        
        # 设置窗口为活动窗口
        # win32gui.SetActiveWindow(hwnd)
    return res


def find_game_window(window_title="LimbusCompany", window_class="UnityWndClass"):
    """
    查找游戏窗口句柄
    :param window_title: 窗口标题
    :param window_class: 窗口类名
    :return: 窗口句柄
    """
    hwnd = win32gui.FindWindow(window_class, window_title)
    if not hwnd:
        raise Exception(f"未找到窗口（类: {window_class}, 标题: {window_title}）")
    return hwnd


def enum_child_windows(hwnd):
    """
    枚举指定窗口的所有子窗口句柄
    :param hwnd: 父窗口句柄
    :return: 子窗口句柄列表
    """
    if not hwnd or not win32gui.IsWindow(hwnd):
        return []
    
    child_windows = []
    
    def enum_callback(child_hwnd, extra_list):
        extra_list.append(child_hwnd)
        return True
    
    try:
        win32gui.EnumChildWindows(hwnd, enum_callback, child_windows)
        return child_windows
    except Exception as e:
        raise Exception(f"枚举子窗口失败: {str(e)}")


def set_window_to_top(hwnd, client_width=1280, client_height=720):
    """
    将窗口客户区调整到屏幕顶部，并设置客户区大小
    :param hwnd: 窗口句柄
    :param client_width: 客户区宽度，默认1280
    :param client_height: 客户区高度，默认720
    """
    if not hwnd:
        return
        
    # 获取窗口的边框和标题栏大小
    window_rect = win32gui.GetWindowRect(hwnd)
    client_rect = win32gui.GetClientRect(hwnd)
    
    # 计算窗口边框大小
    border_width = ((window_rect[2] - window_rect[0]) - (client_rect[2] - client_rect[0])) // 2
    caption_height = (window_rect[3] - window_rect[1]) - (client_rect[3] - client_rect[1]) - border_width
    
    # 将窗口移动到屏幕顶部（考虑标题栏高度）
    win32gui.SetWindowPos(
        hwnd,
        win32con.HWND_TOP,
        -border_width, 
        -caption_height,
        client_width + 2 * border_width,
        client_height + caption_height + border_width,
        win32con.SWP_SHOWWINDOW
    )


def set_window_size(hwnd, width=1302, height=776):
    """
    设置窗口大小
    :param hwnd: 窗口句柄
    :param width: 窗口宽度
    :param height: 窗口高度
    """
    if hwnd:
        # 获取窗口当前的位置
        rect = win32gui.GetWindowRect(hwnd)
        x, y = rect[0], rect[1]
        
        # 设置窗口位置和大小
        win32gui.SetWindowPos(
            hwnd, 
            win32con.HWND_TOP, 
            x, y, 
            width, height, 
            win32con.SWP_SHOWWINDOW
        )


def set_window_position(hwnd, x, y):
    """
    设置窗口位置
    :param hwnd: 窗口句柄
    :param x: 窗口左上角x坐标
    :param y: 窗口左上角y坐标
    """
    if hwnd:
        # 获取窗口当前的尺寸
        rect = win32gui.GetWindowRect(hwnd)
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]
        
        # 设置窗口位置和大小
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOP,
            x, y,
            width, height,
            win32con.SWP_SHOWWINDOW
        )


def get_window_size(hwnd):
    """
    获取当前窗口大小
    :param hwnd: 窗口句柄
    :return: (width, height) 元组
    """
    if hwnd:
        rect = win32gui.GetWindowRect(hwnd)
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]
        return (width, height)
    return None


def is_mouse_in_window(hwnd):
    """
    判断鼠标是否在窗口内
    :param hwnd: 窗口句柄
    :return: bool值，鼠标是否在窗口内
    """
    if not hwnd:
        return False
    
    # 获取鼠标当前位置
    mouse_x, mouse_y = get_cursor_pos()
    if mouse_x is None or mouse_y is None:
        return False
    
    # 获取窗口位置和大小
    rect = wintypes.RECT()
    result = ctypes.windll.user32.GetWindowRect(hwnd, ctypes.pointer(rect))
    if not result:
        return False
    left, top, right, bottom = rect.left, rect.top, rect.right, rect.bottom
    
    # 判断鼠标坐标是否在窗口范围内
    return left <= mouse_x <= right and top <= mouse_y <= bottom, mouse_x, mouse_y


def move_mouse_to_top_right_corner(hwnd):
    """
    将鼠标移动到窗口右上角
    :param hwnd: 窗口句柄
    """
    if not hwnd:
        return
    
    # 获取窗口位置和大小
    rect = wintypes.RECT()
    result = ctypes.windll.user32.GetWindowRect(hwnd, ctypes.pointer(rect))
    if not result:
        return
    left, top, right, bottom = rect.left, rect.top, rect.right, rect.bottom
    
    # 计算右上角坐标（稍微向内偏移几个像素，避免边界问题）
    corner_x = right - 5
    corner_y = top + 5
    
    # 移动鼠标到窗口右上角
    ctypes.windll.user32.SetCursorPos(corner_x, corner_y)


def close_window(hwnd):
    """
    关闭指定窗口
    :param hwnd: 窗口句柄
    """
    if hwnd and win32gui.IsWindow(hwnd):
        # 发送WM_CLOSE消息关闭窗口
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)


def close_limbus_window(window_title="LimbusCompany", window_class="UnityWndClass"):
    """
    关闭LimbusCompany游戏窗口
    :param window_title: 窗口标题
    :param window_class: 窗口类名
    :return: 是否成功关闭窗口
    """
    try:
        hwnd = win32gui.FindWindow(window_class, window_title)
        if hwnd and win32gui.IsWindow(hwnd):
            logger.log("正在关闭LimbusCompany窗口")
            # 发送WM_CLOSE消息关闭窗口
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            # 等待窗口关闭
            timeout = 5  # 5秒超时
            while win32gui.IsWindow(hwnd) and timeout > 0:
                time.sleep(0.5)
                timeout -= 0.5
            
            if timeout <= 0:
                logger.log("关闭LimbusCompany窗口超时", level="WARNING")
                return False
            else:
                logger.log("LimbusCompany窗口已关闭")
                return True
        else:
            logger.log("未找到LimbusCompany窗口")
            return True  # 没有窗口也算"关闭成功"
    except Exception as e:
        logger.log(f"关闭LimbusCompany窗口时出错: {str(e)}", level="ERROR")
        return False


if __name__ == "__main__":
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
    # 查找游戏窗口
    hwnd = find_game_window()
    
    if not hwnd:
        print("未找到游戏窗口，请确保游戏正在运行")
        exit(-1)
    
    print(f"找到游戏窗口，句柄: {hwnd}")

    close_limbus_window()
    
    # # 测试枚举子窗口
    # print("测试枚举子窗口...")
    # child_windows = enum_child_windows(hwnd)
    # print(f"找到 {len(child_windows)} 个子窗口")
    # for i, child_hwnd in enumerate(child_windows[:10]):  # 只显示前10个
    #     try:
    #         text = win32gui.GetWindowText(child_hwnd)
    #         class_name = win32gui.GetClassName(child_hwnd)
    #         print(f"  子窗口 {i}: 句柄={child_hwnd}, 标题='{text}', 类名='{class_name}'")
    #     except:
    #         print(f"  子窗口 {i}: 句柄={child_hwnd}")
    
    # if len(child_windows) > 10:
    #     print(f"  ... 还有 {len(child_windows) - 10} 个子窗口")
    
    # # 测试获取窗口大小
    # size = get_window_size(hwnd)
    # print(f"当前窗口大小: {size}")
    
    # # 测试设置窗口大小
    # if size:
    #     print("测试设置窗口大小...")
    #     original_width, original_height = size
    #     set_window_size(hwnd)
    #     time.sleep(1)
        
    #     new_size = get_window_size(hwnd)
    #     print(f"新窗口大小: {new_size}")
    
    # 测试后台焦点设置
    # print("测试设置后台焦点...")
    # set_background_focus(hwnd)
    # time.sleep(2)  # 等待2秒观察效果
    
    # # 测试前台焦点设置
    # # print("测试设置前台焦点...")
    # # set_foreground_focus(hwnd)
    # # time.sleep(2)  # 等待2秒观察效果
    
    # print("焦点设置测试完成")

    # whil@Te True:
    #     if is_mouse_in_window(hwnd):
    #         print("yes")
    #         move_mouse_to_top_right_corner(hwnd)
    #     else:
    #         print("no")
    #     time.sleep(0.5)