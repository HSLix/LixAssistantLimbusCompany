import cv2
import numpy as np
from PIL import Image
import os
from datetime import datetime

from recognize.img_recognizer import recognize_handler
from recognize.utils import mask_screenshot
from input.input_handler import input_handler


def get_and_save_skill_icons():
    skill_types = ["skill_blunt", "skill_pierce", "skill_slash"]
    skills = []
    tmp_sc = input_handler.capture_screenshot()
    for type_name in skill_types:
        skills += recognize_handler.pyramid_template_match(tmp_sc, type_name, 0.8, mask=[0, 470, 1280, 155])
    skills.sort(key=lambda x:x[0])
    

    offset = [(15, -20), (20, -15)]  # 第一个是缩放小于1.2时的偏移，第二个是大于等于1.2时的偏移

    # 创建保存目录
    save_dir = os.path.join("img", "dataset", "battle_skill", "unclassified")
    os.makedirs(save_dir, exist_ok=True)

    # 获取胜利标志位置用于过滤右侧图标
    win_rate = recognize_handler.template_match(tmp_sc, "win_rate")
    if not win_rate:
        win_rate = [(1280, 0)]  # 默认最右边

    # 处理每个技能图标
    for skill in skills:
        center_x, center_y, _, scale_ratio = skill  # 解构元组 (x, y, score, scale)
        print(center_x, center_y, scale_ratio)
        # 跳过win rate后的无效区域
        if center_x > win_rate[0][0]:
            continue

        if center_y < 560 or (570 < center_y < 590) or center_y > 600:
            continue

        # 根据缩放比例选择偏移
        selected_offset = offset[1] if scale_ratio >= 1.2 else offset[0]
        final_x = center_x + selected_offset[0]
        final_y = center_y + selected_offset[1]

        # 计算裁剪区域 (80x80)
        left = final_x - 40
        top = final_y - 40
        right = final_x + 40
        bottom = final_y + 40

        # 截图并保存
        cropped_img = tmp_sc.crop((left, top, right, bottom))

        # 生成时间戳文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"skill_{timestamp}.png"
        filepath = os.path.join(save_dir, filename)
        cropped_img.save(filepath)
        print(f"技能图标已保存至: {filepath}")
    


def filter_color_by_rgb(image_pil, target_rgb, tolerance=(30, 30, 30)):
    """
    根据RGB值筛选颜色（支持各通道独立容差）
    
    参数:
        image_pil: PIL.Image对象
        target_rgb: 目标颜色元组 (R, G, B)，例如 (255, 200, 50)
        tolerance: RGB各通道容差元组 (R_tol, G_tol, B_tol)，例如 (20, 30, 20)
    
    返回:
        PIL.Image: 筛选后的图像（只保留目标颜色）
    """
    # 1. 展示原图
    # print("【步骤1】原图：")
    # image_pil.show()
    # input("按任意键继续...")
    
    # 转换为numpy数组
    img_array = np.array(image_pil)
    
    
    lower_bound = np.array([
        max(0, target_rgb[0] - tolerance[0]),
        max(0, target_rgb[1] - tolerance[1]),
        max(0, target_rgb[2] - tolerance[2])
    ])
    
    upper_bound = np.array([
        min(255, target_rgb[0] + tolerance[0]),
        min(255, target_rgb[1] + tolerance[1]),
        min(255, target_rgb[2] + tolerance[2])
    ])
    
    mask = cv2.inRange(img_array, lower_bound, upper_bound)

    result = cv2.bitwise_and(img_array, img_array, mask=mask)
    result_pil = Image.fromarray(result)

    return result_pil

def find_colored_clusters_center_coords(img):
    """
    检测图像中多团颜色的中心坐标
    :param img: 输入图像 (PIL Image 或 OpenCV Mat)
    :return: 包含各团颜色中心坐标的列表 [(x1, y1), (x2, y2), ...],按 x 升序排列
    """
    import cv2
    import numpy as np
    from PIL import Image
    
    # 转换为OpenCV格式，如果是PIL图像
    if isinstance(img, Image.Image):
        # 转为numpy数组 (PIL使用RGB，cv2使用BGR)
        img_array = np.array(img)
        # RGB转BGR
        sinner_hp_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    else:
        sinner_hp_cv = img
    
    # 将图像转换为HSV色彩空间，便于检测颜色
    hsv = cv2.cvtColor(sinner_hp_cv, cv2.COLOR_BGR2HSV)
    
    # 创建掩膜，找出非黑色的区域
    # 黑色通常定义为亮度较低的区域
    lower_black = np.array([0, 0, 0])
    upper_black = np.array([180, 255, 50])  # 饱和度和亮度较低的区域视为黑色
    
    mask = cv2.inRange(hsv, lower_black, upper_black)
    
    # 反转掩膜，得到非黑色区域（即彩色区域）
    colored_mask = cv2.bitwise_not(mask)
    
    # 查找轮廓
    contours, _ = cv2.findContours(colored_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    centers = []
    
    # 遍历所有轮廓，计算中心坐标
    for contour in contours:
        # 计算轮廓的矩
        moment = cv2.moments(contour)
        
        # 避免除零错误
        if moment["m00"] != 0:
            # 计算中心坐标
            center_x = int(moment["m10"] / moment["m00"])
            center_y = int(moment["m01"] / moment["m00"])
            centers.append((center_x, center_y))
    centers.sort(key=lambda x: x[0])
    return centers


skill_color = {
    "Wrath":[(150, 0, 0), (100, 20, 20)],
    "Lust":[],
    "Sloth":[],
    "Gluttony":[(100, 230, 20), (70, 25, 30)],
    "Gloom":[(40, 210, 210), (40, 45, 45)],
    "Pride":[(0, 50, 210), (10, 30, 40)],
    "Envy":[(80, 0, 150), (30, 30, 100)],
}

# 使用示例
if __name__ == "__main__":
    # 加载图片
    from input.input_handler import input_handler
    from recognize.utils import mask_screenshot, closing_operation, pil_to_cv2, cv2_to_pil
    input_handler.refresh_window_state()
    # pil = mask_screenshot(input_handler.capture_screenshot(), 330, 70, 750, 550)
    # tmp_sc = input_handler.capture_screenshot()
    # # tmp_sc = mask_screenshot(tmp_sc, 0, 470, 1280, 155)
    # tmp_sc = mask_screenshot(tmp_sc, 0, 675, 1280, 40)

    # icons = extract_skill_icons_center(tmp_sc)
    # for i, icon in enumerate(icons):
    #     icon.save(f"debug_icon_{i}.png")

    # img = filter_color_by_rgb(tmp_sc, (225, 80, 40), (30, 30, 30))
    # sinner_hp = cv2_to_pil(closing_operation(pil_to_cv2(img), (5, 5), 2))
    # c = find_colored_clusters_center_coords(sinner_hp)
    # print(c)

    get_and_save_skill_icons()