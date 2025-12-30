import cv2
import numpy as np
import time
import matplotlib.pyplot as plt
from PIL import Image
import os

try:
    from recognize.utils import pil_to_cv2, mask_screenshot
    from recognize.img_registry import get_image, register_images_from_directory, get_images_by_tag
except ImportError:
    # 添加项目根目录到Python路径
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from recognize.utils import pil_to_cv2, mask_screenshot
    from recognize.img_registry import get_image, register_images_from_directory, get_images_by_tag


def template_match(screenshot, template, threshold=0.8, visualize=False, grayscale=True, screenshot_scale=1):
    """
    模板匹配
    :param screenshot: PIL图像对象，来自game_input.screenshot
    :param template: PIL图像对象，要查找的模板图像
    :param threshold: 匹配阈值
    :param visualize: 是否可视化匹配结果
    :param grayscale: 是否将图像转换为灰度图并直方图均衡化进行匹配
    :param screenshot_scale: 对目标图片进行放缩的倍率
    :return: 匹配结果列表，每个元素包含(中心x坐标, 中心y坐标, 匹配分数)
    """
    # 转换图像格式
    screenshot = pil_to_cv2(screenshot, grayscale)
    template = pil_to_cv2(template, grayscale)

    # template = cv2.GaussianBlur(template, (3, 3), 0)
    # screenshot = cv2.GaussianBlur(screenshot, (3, 3), 0)

    # if grayscale:
    #     screenshot = cv2.equalizeHist(screenshot)
    #     template = cv2.equalizeHist(template)

    clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
    screenshot = clahe.apply(screenshot)
    template = clahe.apply(template)

    # template = cv2.medianBlur(template, 5)
    # screenshot = cv2.medianBlur(screenshot, 5)

    template = cv2.GaussianBlur(template, (5, 5), 0)
    screenshot = cv2.GaussianBlur(screenshot, (5, 5), 0)

    if screenshot_scale != 1:
        h, w = screenshot.shape[:2]
        screenshot = cv2.resize(
            screenshot, 
            (int(w * screenshot_scale), int(h * screenshot_scale)),
            interpolation=cv2.INTER_AREA
        )


    # 检查模板尺寸是否合适
    if (template.shape[0] > screenshot.shape[0] or 
        template.shape[1] > screenshot.shape[1]):
        return []

    # 执行模板匹配
    result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
    
    # 查找匹配位置
    locations = np.where(result >= threshold)
    
    matches = []
    for pt in zip(*locations[::-1]):  # 转换为(x, y)坐标
        # 计算中心坐标
        cx = pt[0] + template.shape[1] // 2
        cy = pt[1] + template.shape[0] // 2
        score = result[pt[1], pt[0]]
        cx_orig = int(cx / screenshot_scale)
        cy_orig = int(cy / screenshot_scale)
        matches.append((cx_orig, cy_orig, score))
    
    # 按匹配分数从高到低排序
    matches.sort(key=lambda x: x[2], reverse=True)
    
    # 合并中心坐标相近的匹配结果（横纵坐标相差不到20的）
    merged_matches = []
    for match in matches:
        center_x, center_y, score = match
        merged = False
        
        # 检查是否与已合并的匹配结果相近
        for i, merged_match in enumerate(merged_matches):
            merged_x, merged_y, merged_score = merged_match
            # 如果中心坐标相差不到20，则认为是同一个目标
            if abs(center_x - merged_x) < 20 and abs(center_y - merged_y) < 20:
                # 保留分数较高的匹配
                if score > merged_score:
                    merged_matches[i] = (center_x, center_y, score)
                merged = True
                break
        
        # 如果没有相近的匹配结果，则添加为新的匹配
        if not merged:
            merged_matches.append(match)
    
    matches = merged_matches
    
    # 如果需要可视化，则显示结果
    if visualize:
        vis = screenshot.copy()
        th, tw = template.shape[:2]
        for (cx_orig, cy_orig, score) in matches:

            # 可视化需要 scale 后的坐标
            cx = int(cx_orig * screenshot_scale)
            cy = int(cy_orig * screenshot_scale)

            tl = (int(cx - tw/2), int(cy - th/2))
            br = (int(cx + tw/2), int(cy + th/2))

            cv2.rectangle(vis, tl, br, (128, 128, 128), 2)
            cv2.putText(vis, f"{score:.2f}", (tl[0], tl[1]-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (128,128,128), 2)

        plt.figure(figsize=(12, 6))
        if grayscale:
            plt.imshow(vis, cmap="gray")
        else:
            plt.imshow(cv2.cvtColor(vis, cv2.COLOR_BGR2RGB))
        plt.axis("off")
        plt.show()
    
    # print(f"Template matching processed in {processing_time:.4f} seconds")
    # print("Template:" + str(matches))
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
    # 加载测试图像
    try:
        templates = []
        screenshot = input_handler.capture_screenshot()
        # screenshot = mask_screenshot(screenshot, 250, 290, 60, 60)
        register_images_from_directory()
        # templates.append(get_image("Little and To-be-Naughty Plushie"))
      
        # templates.append(get_image("event_pass_high"))
        templates.append(get_image("Thunderbranch"))
        templates.append(get_image("Lightning Rod"))
        # templates.append(get_image("Rest"))
        # templates.append(get_image("Entanglement Override Sequencer"))
        # templates.append(get_image("Bloodflame Sword"))

        # templates.append(get_image("Faint Vestige"))

        # templates.append(get_image("node_regular_encounter"))
        # templates.append(get_image("node_event"))
        # templates.append(get_image("node_elite_encounter"))
        # templates.append(get_image("node_focused_encounter"))
        # templates.append(get_image("node_shop"))
        # templates.append(get_image("node_boss_encounter"))
        
        # print(template_match(get_image("ANL"), get_image("Emotional Repression"), threshold=0.3))
        print("已加载测试图像和模板图像")
    except Exception as e:
        print(f"加载图像时出错: {e}")
        exit(1)
    
    # 测试模板匹配
    print("\n1. 测试模板匹配 (默认阈值):")
    try:
        for template in templates:
            # matches = template_match(screenshot, template, visualize=True, threshold=0.2, grayscale=False)
            start = time.time()
            matches = template_match(screenshot, template, visualize=True, threshold=0.8, screenshot_scale=1)
            print(f"used time:{time.time()-start}")
            print(f"   找到 {len(matches)} 个匹配")
            input_handler.set_background_state()
            for i, match in enumerate(matches):
                print(f"   匹配 {i+1}: 中心坐标({match[0]}, {match[1]}), 匹配分数: {match[2]:.4f}")
                # con.click(match[0], match[1])
                # time.sleep(3)
                # if i == 6:
                #     break
    except Exception as e:
        print(f"   模板匹配出错: {e}")
    
    print("\nTemplate Match模块测试完成")