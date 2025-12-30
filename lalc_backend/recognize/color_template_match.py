import cv2
import numpy as np
import time
import matplotlib.pyplot as plt
from PIL import Image
import os

try:
    from recognize.template_match  import template_match
    from recognize.utils import pil_to_cv2
    from recognize.img_registry import register_images_from_directory, get_images_by_tag, get_image
except ImportError:
    from img_registry import register_images_from_directory, get_images_by_tag, get_image
    from template_match import template_match
    from utils import pil_to_cv2


def color_template_match(screenshot, template, threshold=0.7, visualize=False, color_weight=0.5,
                        color_threshold=0.5, color_bins=(80, 80, 80), color_method=cv2.HISTCMP_BHATTACHARYYA, grayscale=False):
    """
    结合颜色相似度检查的模板匹配
    :param screenshot: PIL图像对象，来自game_input.screenshot
    :param template: PIL图像对象，要查找的模板图像
    :param threshold: 匹配阈值
    :param visualize: 是否可视化匹配结果
    :param color_weight: 颜色匹配的分数所占权重（0-1）
    :param color_threshold: 颜色阈值，当将分数以此为分界线放缩
    :param color_bins: 颜色直方图bins数量，三元组分别对应B、G、R通道
    :param color_method: 颜色直方图比较方法
    :param grayscale: 是否将图像转换为灰度图进行匹配
    :return: 匹配结果列表，每个元素包含(中心x坐标, 中心y坐标, 总和匹配分数, 模板匹配分数，颜色相似度分数)
    """    
    # 转换图像格式
    screenshot_cv2 = pil_to_cv2(screenshot, grayscale=grayscale)
    template_cv2 = pil_to_cv2(template, grayscale=grayscale)
    
    # 使用现有的模板匹配函数获取匹配结果
    # 降低此处阈值，是为了减少第一次就错筛的情况
    template_threshold = max(0, threshold-0.1)
    base_matches = template_match(screenshot, template, template_threshold, visualize=False, grayscale=grayscale) 
    
    # 为每个匹配结果添加颜色相似度分数
    matches = []
    h, w = template_cv2.shape[:2]
    
    for (center_x, center_y, template_score) in base_matches:
        # 计算匹配区域的左上角坐标
        top_left_x = int(center_x - w / 2)
        top_left_y = int(center_y - h / 2)
        
        # 提取匹配区域
        matched_region = screenshot_cv2[top_left_y:top_left_y+h, top_left_x:top_left_x+w]
        
        # 计算颜色相似度
        color_similarity = _calculate_color_similarity(template_cv2, matched_region, color_bins, color_method)
        color_similarity = 1 if color_similarity > color_threshold else color_similarity / color_threshold

        score = template_score * (1-color_weight) + color_similarity * color_weight
        if score >= threshold:
            matches.append((center_x, center_y, score, template_score, color_similarity))

    matches.sort(key=lambda x: x[2], reverse=True)
    
    # 如果需要可视化，则显示结果
    if visualize:
        # 创建彩色版本用于显示
        if len(screenshot_cv2.shape) == 2:  # 如果是灰度图
            vis_screenshot = cv2.cvtColor(screenshot_cv2, cv2.COLOR_GRAY2BGR)
        else:
            vis_screenshot = screenshot_cv2.copy()

        if matches:
            for (center_x, center_y, score, template_score, color_similarity) in matches:
                top_left = (int(center_x - w/2), int(center_y - h/2))
                bottom_right = (int(center_x + w/2), int(center_y + h/2))
                # 使用红色框 (B=0, G=0, R=255)
                cv2.rectangle(vis_screenshot, top_left, bottom_right, (0, 0, 255), 2)
                # 使用红色文字
                cv2.putText(vis_screenshot, f'S: {score:.2f}', 
            (top_left[0]+40, top_left[1]-20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                cv2.putText(vis_screenshot, f'T: {template_score:.2f}', 
                        (top_left[0]+40, top_left[1]+10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                cv2.putText(vis_screenshot, f'C: {color_similarity:.2f}', 
                        (top_left[0]+40, top_left[1]+40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
        plt.figure(figsize=(12, 6))
        plt.subplot(1, 2, 1)
        plt.imshow(cv2.cvtColor(vis_screenshot, cv2.COLOR_BGR2RGB))
        plt.title('Color Template Matching Results')
        plt.axis('off')
        
        plt.subplot(1, 2, 2)
        plt.imshow(cv2.cvtColor(template_cv2, cv2.COLOR_BGR2RGB))
        plt.title('Template')
        plt.axis('off')
        
        plt.tight_layout()
        plt.show()
    
    # print(f"Color template matching processed in {processing_time:.4f} seconds")
    return matches


def _calculate_color_similarity(image1, image2, bins, method):
    """
    计算两个图像的颜色相似度
    :param image1: 第一个OpenCV图像
    :param image2: 第二个OpenCV图像
    :param bins: 直方图bins数量，三元组分别对应B、G、R通道
    :param method: 直方图比较方法，默认使用相关性(cv2.HISTCMP_CORREL)
                   可选方法：
                   - cv2.HISTCMP_CORREL: 相关性 (结果范围[-1, 1]，1为完全匹配)
                   - cv2.HISTCMP_CHISQR: 卡方距离 (结果范围[0, +∞)，0为完全匹配)
                   - cv2.HISTCMP_INTERSECT: 直方图交集 (结果范围[0, 1]，1为完全匹配)
                   - cv2.HISTCMP_BHATTACHARYYA: 巴氏距离 (结果范围[0, 1]，0为完全匹配)
    :return: 颜色相似度分数(0-1)
    """
    # 如果是灰度图，将其转换为三通道的彩色图
    if len(image1.shape) == 2:  # 单通道图像 (灰度图)
        image1 = cv2.cvtColor(image1, cv2.COLOR_GRAY2BGR)
    if len(image2.shape) == 2:  # 单通道图像 (灰度图)
        image2 = cv2.cvtColor(image2, cv2.COLOR_GRAY2BGR)

    # 调整图像尺寸以匹配
    if image1.shape != image2.shape:
        image2 = cv2.resize(image2, (image1.shape[1], image1.shape[0]))
    
    # 计算两个图像的颜色直方图
    hist1 = cv2.calcHist([image1], [0, 1, 2], None, bins, [0, 256, 0, 256, 0, 256])
    hist2 = cv2.calcHist([image2], [0, 1, 2], None, bins, [0, 256, 0, 256, 0, 256])
    
    # 归一化直方图
    cv2.normalize(hist1, hist1, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
    cv2.normalize(hist2, hist2, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
    
    # 计算直方图相似度
    similarity = cv2.compareHist(hist1, hist2, method)
    
    # 对于某些方法需要转换结果范围到[0,1]
    if method == cv2.HISTCMP_CHISQR:
        # 卡方距离需要转换，值越大表示差异越大
        similarity = 1 / (1 + similarity)
    elif method == cv2.HISTCMP_BHATTACHARYYA:
        # 巴氏距离已经在[0,1]范围内，1-距离得到相似度
        similarity = 1 - similarity
    elif method == cv2.HISTCMP_CORREL:
        # 相关性在[-1,1]范围内，转换到[0,1]范围
        similarity = (similarity + 1) / 2
    
    return similarity



if __name__ == "__main__":
    # 独立测试color_template_match模块
    print("=== Color Template Match Module Test ===")
    
    # Fix the import issue by using absolute import instead of relative import
    import sys
    import os
    # Add the parent directory to sys.path to make imports work
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from input.input_handler import input_handler

    input_handler.refresh_window_state()
    # 加载测试图像
    try:
        screenshot = input_handler.capture_screenshot()
        templates = []
        register_images_from_directory()
        # for name, img in get_images_by_tag("theme_packs"):
        #     print(name)
        #     templates.append(img)
        templates.append(get_image("Wound Clerid"))
        templates.append(get_image("Millarca"))
        templates.append(get_image("Respite"))
        templates.append(get_image("Rusted Muzzle"))
        # templates.append(Image.open(r"./img/mirror/owned_ego_resources.png"))

        # templates.append(Image.open(r"./img/mirror/node_regular_encounter.png"))
        # templates.append(Image.open(r"./img/mirror/node_event.png"))
        print("已加载测试图像和模板图像")
    except Exception as e:
        print(f"加载图像时出错: {e}")
        exit(1)
    
    # 测试颜色模板匹配
    print("\n1. 测试颜色模板匹配 (默认参数):")
    try:
        for template in templates:
            matches = color_template_match(screenshot, template, visualize=True, threshold=0.5, grayscale=False)
            print(f"   找到 {len(matches)} 个匹配")
            input_handler.set_background_state()
            for i, match in enumerate(matches):
                print(f"   匹配 {i+1}: 中心坐标({match[0]}, {match[1]}), 匹配分数: {match[2]:.4f}, 模板匹配分数: {match[3]:.4f}, 颜色相似度: {match[4]:.4f}")
                # con.click(match[0], match[1])
                # time.sleep(3)
                # if i == 6:
                #     break
        
    except Exception as e:
        print(f"   颜色模板匹配出错: {e}")

    
    print("\nColor Template Match模块测试完成")