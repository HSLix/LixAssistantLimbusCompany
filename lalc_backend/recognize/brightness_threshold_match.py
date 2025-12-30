import cv2
import numpy as np
import time
import matplotlib.pyplot as plt
from PIL import Image
import os

try:
    from recognize.utils import pil_to_cv2, mask_screenshot
    from recognize.img_registry import get_image, register_images_from_directory
except ImportError:
    from utils import pil_to_cv2, mask_screenshot
    from img_registry import get_image, register_images_from_directory


def brightness_threshold_match(screenshot, threshold=180, visualize=False, grayscale=True, screenshot_scale=1,
                               box_width=50, box_height=50, step=10):
    """
    基于滑动窗口和亮度阈值分割的方框检测
    :param screenshot: PIL图像对象，来自game_input.screenshot
    :param threshold: 亮度阈值，高于此值的区域被认为是“亮”的方框
    :param visualize: 是否可视化匹配结果
    :param grayscale: 是否将图像转换为灰度图
    :param screenshot_scale: 对目标图片进行放缩的倍率
    :param box_width: 检测窗口的宽度（像素）
    :param box_height: 检测窗口的高度（像素）
    :param step: 窗口滑动的步长（像素），步长越小越精确，但速度越慢
    :return: 匹配结果列表，每个元素包含(中心x坐标, 中心y坐标, 平均亮度分数)
    """
    # 转换图像格式
    screenshot_cv = pil_to_cv2(screenshot, grayscale)

    # 如果需要，对图像进行缩放
    if screenshot_scale != 1:
        h, w = screenshot_cv.shape[:2]
        screenshot_cv = cv2.resize(
            screenshot_cv,
            (int(w * screenshot_scale), int(h * screenshot_scale)),
            interpolation=cv2.INTER_AREA
        )

    # 应用高斯模糊以减少噪声
    screenshot_cv = cv2.GaussianBlur(screenshot_cv, (5, 5), 0)

    # 获取图像尺寸
    h, w = screenshot_cv.shape[:2]

    # 存储所有检测到的方框信息
    matches = []

    # 滑动窗口遍历图像
    for y in range(0, h - box_height + 1, step):
        for x in range(0, w - box_width + 1, step):
            # 裁剪出当前窗口区域
            roi = screenshot_cv[y:y+box_height, x:x+box_width]
            
            # 计算该区域的平均亮度
            avg_brightness = np.mean(roi)
            
            # 如果平均亮度大于阈值，则认为这是一个“亮”方框
            if avg_brightness > threshold:
                # 计算窗口中心坐标
                cx = x + box_width // 2
                cy = y + box_height // 2
                
                # 将坐标还原到原始截图尺寸
                cx_orig = int(cx / screenshot_scale)
                cy_orig = int(cy / screenshot_scale)
                
                matches.append((cx_orig, cy_orig, avg_brightness))

    # 按平均亮度从高到低排序
    matches.sort(key=lambda x: x[2], reverse=True)

    # 合并中心坐标相近的匹配结果（横纵坐标相差不到20的）
    merged_matches = []
    for match in matches:
        center_x, center_y, score = match
        merged = False
        
        for i, merged_match in enumerate(merged_matches):
            merged_x, merged_y, merged_score = merged_match
            if abs(center_x - merged_x) < box_width and abs(center_y - merged_y) < box_height:
                if score > merged_score:
                    merged_matches[i] = ((center_x+merged_x)//2, (center_y+merged_y)//2, score)
                merged = True
                break
        
        if not merged:
            merged_matches.append(match)

    matches = merged_matches

    # 如果需要可视化，则显示结果
    if visualize:
        # 创建一个副本用于绘制
        vis = screenshot_cv.copy()
        
        # 如果是单通道，转换为BGR以便画彩色矩形
        if len(vis.shape) == 2:
            vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)

        for (cx_orig, cy_orig, score) in matches:
            cx = int(cx_orig * screenshot_scale)
            cy = int(cy_orig * screenshot_scale)
            # 绘制一个矩形来表示检测到的窗口
            tl = (cx - box_width // 2, cy - box_height // 2)
            br = (cx + box_width // 2, cy + box_height // 2)
            cv2.rectangle(vis, tl, br, (128, 128, 128), 2)
            cv2.putText(vis, f"{score:.2f}", (tl[0], tl[1]-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (128,128,128), 2)

        plt.figure(figsize=(12, 6))
        if grayscale:
            plt.imshow(vis, cmap="gray")
        else:
            plt.imshow(cv2.cvtColor(vis, cv2.COLOR_BGR2RGB))
        plt.title("Sliding Window Detection Result")
        plt.axis("off")
        plt.show()

    return matches


if __name__ == "__main__":
    
    # 独立测试template_match模块
    print("=== Template Match Module Test ===")
    # Fix the import issue by using absolute import instead of relative import
    import sys
    import os
    # Add the parent directory to sys.path to make imports work
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from input.input_handler import input_handler
    input_handler.refresh_window_state()
    input_handler.set_window_size()
    tmp_screenshot = input_handler.capture_screenshot()
    tmp_screenshot = mask_screenshot(tmp_screenshot, 590, 180, 560, 350)
    try:
        start = time.time()
        matches = brightness_threshold_match(tmp_screenshot, visualize=True, threshold=30, screenshot_scale=1, box_width=70, box_height=70)
        print(f"used time:{time.time()-start}")
        print(f"   找到 {len(matches)} 个匹配")
        print(matches)
    except Exception as e:
        print(f"   亮度匹配出错: {e}")
    
