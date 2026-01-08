import cv2
import numpy as np
from PIL import Image

from recognize.utils import pil_to_cv2, cv2_to_pil
from recognize.img_registry import get_image, register_images_from_directory, get_images_by_tag

def get_component(screenshot):
    # Step 1: 将 PIL 图像转换为 NumPy 数组
    img = pil_to_cv2(screenshot, True)
    
    # Step 2: 使用 Otsu's 二值化方法进行图像二值化
    _, binary_image = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Step 3: 使用 connectedComponentsWithStats 进行连通区域标记
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary_image)

    # Step 4: 创建一个可视化图像，将每个连通区域标注不同颜色
    output_img = cv2.cvtColor(binary_image, cv2.COLOR_GRAY2RGB)  # 将灰度图转为RGB图
    for label in range(1, num_labels):  # 从 1 开始，0 是背景
        x, y, w, h, area = stats[label]
        color = np.random.randint(0, 255, size=3).tolist()  # 随机颜色
        cv2.rectangle(output_img, (x, y), (x + w, y + h), color, 2)  # 标记每个连通区域

    # Step 5: 转换回 PIL 图像并展示
    output_pil_img = cv2_to_pil(output_img)
    output_pil_img.show()

# 示例使用
if __name__ == '__main__':
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
      
        # templates.append(get_image("event_pass_very_low"))
        # templates.append(get_image("event_pass_low"))
        # templates.append(get_image("event_pass_normal"))
        # templates.append(get_image("event_pass_high"))
        # templates.append(get_image("event_pass_very_high"))

        # templates.append(get_image("event_scroll_strip"))
        # templates.append(get_image("Thunderbranch"))
        # templates.append(get_image("Lightning Rod"))
        # templates.append(get_image("Rest"))
        # templates.append(get_image("Entanglement Override Sequencer"))
        # templates.append(get_image("Bloodflame Sword"))

        # templates.append(get_image("Dark Vestige"))
        # templates.append(get_image("Faint Vestige"))
        
        # templates.append(get_image("right_top_setting"))

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
    
    
    get_component(screenshot)