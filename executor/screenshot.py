# coding: utf-8
import ctypes
import pygetwindow as gw
import mss
import mss.tools
import numpy as np
from globals import RESOURCE_DIR
from os.path import join
import cv2
import time

from .game_window import getWindow
    

def captureLimbusCompanyWindow(is_save_pic: bool = False, is_pic_gray: bool = True):
    """
    查找名为 "LimbusCompany" 的窗口，根据缩放比例调整窗口数据，并截屏。
    """
    window = getWindow()
    
    left, top, width, height = window.left, window.top, window.width, window.height

    monitor = {"left": left, "top": top, "width": width, "height": height}

    with mss.mss() as sct:
        screenshot = sct.grab(monitor)
        if is_save_pic:
            output_path = join(RESOURCE_DIR, "limbus_company_screenshot.png")
            mss.tools.to_png(screenshot.rgb, screenshot.size, output=output_path)

    screenshot = np.array(screenshot)

    if is_pic_gray:
        screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2GRAY)


    return screenshot





if __name__ == "__main__":
    ctypes.windll.shcore.SetProcessDpiAwareness(2)

    # 记录开始时间
    start_time = time.time()


    # 调用函数 100 次
    for _ in range(100):
        captureLimbusCompanyWindow()

    # 记录结束时间
    end_time = time.time()

    # 计算总耗时
    total_time = end_time - start_time
    print(f"100 次调用函数所花时间: {total_time:.4f} 秒")

    # 计算平均每次调用时间
    average_time = total_time / 100
    print(f"平均每次调用时间: {average_time:.4f} 秒")
    # screenshot = captureLimbusCompanyWindow()
    # if screenshot is not None:
    #     # 这里可以直接使用 OpenCV 对截图进行处理
    #     cv2.imshow('Screenshot', screenshot)
    #     cv2.waitKey(0)
    #     cv2.destroyAllWindows()
