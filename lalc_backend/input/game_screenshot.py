import win32gui
import win32ui
import numpy as np
from PIL import Image
import cv2
import ctypes
from ctypes import wintypes
import time

# 加载user32.dll（截图依赖）
user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
user32.PrintWindow.restype = wintypes.BOOL


def _get_logical_client_rect(hwnd):
    """
    获取窗口客户区逻辑尺寸
    :param hwnd: 窗口句柄
    :return: 包含宽度和高度的字典
    """
    client_rect = win32gui.GetClientRect(hwnd)  # (left, top, right, bottom)
    logic_width = client_rect[2] - client_rect[0] 
    logic_height = client_rect[3] - client_rect[1] 
    return (logic_width, logic_height)


def take_screenshot(hwnd, width=None, height=None, save_path=None):
    """
    对游戏窗口进行后台截图
    :param hwnd: 游戏窗口句柄
    :param width: 窗口逻辑尺寸信息（None则自动获取）
    :param save_path: 保存路径（None则不保存）
    :return: PIL.Image对象（截图内容）
    """
    # 获取逻辑尺寸
    if width is None or height is None:
        width, height = _get_logical_client_rect(hwnd)

    # 获取设备上下文
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()

    # 创建匹配尺寸的位图
    save_bitmap = win32ui.CreateBitmap()
    save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
    save_dc.SelectObject(save_bitmap)

    # 捕获客户区内容
    success = user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 3)  # PW_PRINTCLIENT
    if not success:
        raise ctypes.WinError(ctypes.get_last_error())

    # 解析位图数据
    bmp_info = save_bitmap.GetInfo()
    bmp_str = save_bitmap.GetBitmapBits(True)
    img_height = abs(bmp_info["bmHeight"])
    img_width = bmp_info["bmWidth"]

    # 转换为数组并修正方向
    img = np.frombuffer(bmp_str, dtype=np.uint8).reshape((img_height, img_width, 4))
    if bmp_info["bmHeight"] < 0:
        img = np.flipud(img)

    # 转换为RGB格式
    img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
    pil_img = Image.fromarray(img)

    # 清理资源
    win32gui.DeleteObject(save_bitmap.GetHandle())
    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)

    # 保存截图（如果需要）
    if save_path:
        pil_img.save(save_path)

    return pil_img


def performance_test(hwnd, save_image=False, count=100):
    """
    对截图功能进行性能测试
    :param hwnd: 游戏窗口句柄
    :param save_image: 是否保存图片
    :param count: 测试次数
    :return: None
    """
    print(f"开始性能测试: 连续截图100次, 保存图片: {save_image}")
    
    start_time = time.time()
    
    for i in range(count):
        if save_image:
            save_path = f"screenshot_test.png"
            take_screenshot(hwnd, save_path)
        else:
            take_screenshot(hwnd)
    
    end_time = time.time()
    total_time = end_time - start_time
    avg_time = total_time / count
    
    print(f"测试完成:")
    print(f"  总耗时: {total_time:.2f} 秒")
    print(f"  平均每次截图耗时: {avg_time:.4f} 秒")
    print(f"  帧率 (FPS): {1/avg_time:.2f}")
    
    return total_time, avg_time


if __name__ == "__main__":
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # 2=PROCESS_PER_MONITOR_DPI_AWARE
    try:
        from game_window import find_game_window
        hwnd = find_game_window()
        if hwnd:
            take_screenshot(hwnd, save_path="test.png")
            # print("找到游戏窗口，开始性能测试...")
            
            # # 测试不保存图片的性能
            # print("\n=== 测试不保存图片 ===")
            # performance_test(hwnd, save_image=False, count=1)
            
            # # 测试保存图片的性能
            # print("\n=== 测试保存图片 ===")
            # performance_test(hwnd, save_image=True, count=1)
        else:
            print("未找到游戏窗口，请确保游戏正在运行")
    except Exception as e:
        print(f"性能测试失败: {e}")
