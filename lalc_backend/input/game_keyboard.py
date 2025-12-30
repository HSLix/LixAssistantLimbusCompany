import win32gui
import win32api
import win32con
import time
import random
import ctypes

# 虚拟键码映射表
VK_CODE = {
    'a': 0x41, 'b': 0x42, 'c': 0x43, 'd': 0x44, 'e': 0x45, 'f': 0x46, 'g': 0x47,
    'h': 0x48, 'i': 0x49, 'j': 0x4A, 'k': 0x4B, 'l': 0x4C, 'm': 0x4D, 'n': 0x4E,
    'o': 0x4F, 'p': 0x50, 'q': 0x51, 'r': 0x52, 's': 0x53, 't': 0x54, 'u': 0x55,
    'v': 0x56, 'w': 0x57, 'x': 0x58, 'y': 0x59, 'z': 0x5A,
    'enter': 0x0D, 'esc': 0x1B, 'space': 0x20
}

# 存储按键状态
_key_state = {}


def _map_key_to_vk(key):
    """
    将字符串键映射到虚拟键码
    :param key: 字符串键名或虚拟键码
    :return: 虚拟键码
    """
    if isinstance(key, int):
        return key  # 已经是虚拟键码
    
    vk_code = VK_CODE.get(key.lower())
    if vk_code is None:
        raise ValueError(f"无法找到键 '{key}' 对应的虚拟键码")
    return vk_code


def background_key_press(hwnd, key, duration=0.05):
    """
    后台按键按下和释放
    :param hwnd: 窗口句柄
    :param key: 字符串键名或虚拟键码
    :param duration: 按键持续时间（秒）
    :return: 操作是否成功
    """
    if not hwnd or not win32gui.IsWindow(hwnd):
        raise Exception(f"错误：窗口句柄无效（hwnd={hwnd}）")
    
    try:
        vk_code = _map_key_to_vk(key)
    except ValueError as e:
        raise Exception(f"键映射错误：{str(e)}")
        
    
    # set_focus(hwnd)

    try:
        # 获取扫描码
        scan_code = win32api.MapVirtualKey(vk_code, 0)
        
        # 发送按键按下消息
        win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, vk_code, (scan_code << 16) | 0x00000001)
        time.sleep(duration + random.random() * 0.05)
        
        # 发送按键释放消息
        win32gui.PostMessage(hwnd, win32con.WM_KEYUP, vk_code, (scan_code << 16) | 0xC0000001)

        # print(f"后台按键成功：键='{key}' 键码={vk_code}")
        return True

    except Exception as e:
        raise Exception(f"后台按键失败：{str(e)}")
        


def background_key_down(hwnd, key):
    """
    后台按键按下（不释放）
    :param hwnd: 窗口句柄
    :param key: 字符串键名或虚拟键码
    :return: 操作是否成功
    """
    if not hwnd or not win32gui.IsWindow(hwnd):
        raise Exception(f"错误：窗口句柄无效（hwnd={hwnd}）")
    
    try:
        vk_code = _map_key_to_vk(key)
    except ValueError as e:
        raise Exception(f"键映射错误：{str(e)}")
    
    # set_focus(hwnd)

    try:
        # 获取扫描码
        scan_code = win32api.MapVirtualKey(vk_code, 0)
        
        # 发送按键按下消息
        lparam = (scan_code << 16) | 0x00000001
        win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, vk_code, lparam)
        
        # 更新按键状态
        _key_state[vk_code] = True
        
        print(f"后台按键按下成功：键='{key}' 键码={vk_code}")
        return True

    except Exception as e:
        raise Exception(f"后台按键按下失败：{str(e)}")


def background_key_up(hwnd, key):
    """
    后台按键释放
    :param hwnd: 窗口句柄
    :param key: 字符串键名或虚拟键码
    :return: 操作是否成功
    """
    if not hwnd or not win32gui.IsWindow(hwnd):
        raise Exception(f"错误：窗口句柄无效（hwnd={hwnd}）")
    
    try:
        vk_code = _map_key_to_vk(key)
    except ValueError as e:
        raise Exception(f"键映射错误：{str(e)}")
    
    # set_focus(hwnd)

    try:
        # 获取扫描码
        scan_code = win32api.MapVirtualKey(vk_code, 0)
        
        # 发送按键释放消息
        lparam = (scan_code << 16) | 0xC0000001
        win32gui.PostMessage(hwnd, win32con.WM_KEYUP, vk_code, lparam)
        
        # 更新按键状态
        if vk_code in _key_state:
            del _key_state[vk_code]
            
        print(f"后台按键释放成功：键='{key}' 键码={vk_code}")
        return True

    except Exception as e:
        raise Exception(f"后台按键释放失败：{str(e)}")


def foreground_key_press(key, duration=0.05):
    """
    前台按键按下和释放
    :param key: 字符串键名或虚拟键码
    :param duration: 按键持续时间（秒）
    :return: 操作是否成功
    """
    try:
        vk_code = _map_key_to_vk(key)
    except ValueError as e:
        raise Exception(f"键映射错误：{str(e)}")

    try:
        # 获取扫描码
        scan_code = win32api.MapVirtualKey(vk_code, 0)
        
        # 使用win32api.keybd_event模拟按键按下和释放
        win32api.keybd_event(vk_code, scan_code, 0, 0)  # 按下
        time.sleep(duration + random.random() * 0.05)
        win32api.keybd_event(vk_code, scan_code, win32con.KEYEVENTF_KEYUP, 0)  # 释放

        print(f"前台按键成功：键='{key}' 键码={vk_code}")
        return True

    except Exception as e:
        raise Exception(f"前台按键失败：{str(e)}")


def foreground_key_down(key):
    """
    前台按键按下（不释放）
    :param key: 字符串键名或虚拟键码
    :return: 操作是否成功
    """
    try:
        vk_code = _map_key_to_vk(key)
    except ValueError as e:
        raise Exception(f"键映射错误：{str(e)}")

    try:
        # 获取扫描码
        scan_code = win32api.MapVirtualKey(vk_code, 0)
        
        # 使用win32api.keybd_event模拟按键按下
        win32api.keybd_event(vk_code, scan_code, 0, 0)  # 按下
        
        # 更新按键状态
        _key_state[vk_code] = True

        print(f"前台按键按下成功：键='{key}' 键码={vk_code}")
        return True

    except Exception as e:
        raise Exception(f"前台按键按下失败：{str(e)}")


def foreground_key_up(key):
    """
    前台按键释放
    :param key: 字符串键名或虚拟键码
    :return: 操作是否成功
    """
    try:
        vk_code = _map_key_to_vk(key)
    except ValueError as e:
        raise Exception(f"键映射错误：{str(e)}")

    try:
        # 获取扫描码
        scan_code = win32api.MapVirtualKey(vk_code, 0)
        
        # 使用win32api.keybd_event模拟按键释放
        win32api.keybd_event(vk_code, scan_code, win32con.KEYEVENTF_KEYUP, 0)  # 释放
        
        # 更新按键状态
        if vk_code in _key_state:
            del _key_state[vk_code]

        print(f"前台按键释放成功：键='{key}' 键码={vk_code}")
        return True

    except Exception as e:
        raise Exception(f"前台按键释放失败：{str(e)}")


if __name__ == "__main__":
    # 测试函数：需要先运行main.py获取hwnd
    ctypes.windll.shcore.SetProcessDpiAwareness(2)

    try:
        from game_window import find_game_window
        hwnd = find_game_window()
        print(f"成功连接游戏窗口，句柄: {hwnd}")
        
        # 测试后台按键
        print("测试后台按键 'p'...")
        background_key_press(hwnd, "p")
        time.sleep(1)
        
        # 测试前台按键
        print("测试前台按键 'p'...")
        foreground_key_press("p")
        time.sleep(1)
        
        # 测试后台长按
        print("测试后台长按 'space'...")
        background_key_down(hwnd, "space")
        time.sleep(0.5)
        background_key_up(hwnd, "space")
        time.sleep(1)
        
        print("键盘测试完成")
        
    except Exception as e:
        print(f"键盘测试失败: {str(e)}")