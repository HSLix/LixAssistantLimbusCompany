import cv2
import numpy as np
from PIL import Image
import os
from datetime import datetime

from recognize.img_recognizer import recognize_handler
from recognize.utils import mask_screenshot, pil_to_cv2, cv2_to_pil, closing_operation, dilate_image
from input.input_handler import input_handler
from PIL import Image, ImageDraw

import numpy as np
import cv2
from PIL import Image, ImageDraw

# ---------- 你已有的 5 块“要变黑”的多边形 ----------
BLACK_POLYS = [
    [(0, 0), (0, 25), (20, 0)],                      # left_top_corner
    [(80, 0), (80, 28), (60, 0)],                     # right_top_corner
    [(0, 45), (0, 55), (4, 55)],                      # left_bottom_corner
    [(80, 40), (80, 55), (75, 55)],                   # right_bottom_corner
    [(11, 54), (4, 30), (24, 5), (56, 5), (75, 30), (70, 55)],  # avatar_center
    [(33, 0), (33, 3), (46, 3), (46, 0)]           # top
]
# ----------------------------------------------------


def enhance_img(img_pil: Image):
    img = np.asarray(img_pil).copy()
    h, w = img.shape[:2]

    for pts in BLACK_POLYS:
        cv2.fillPoly(img, [np.array(pts, np.int32)], color=(0, 0, 0))
    
    thickness = 3
    color     = (0, 0, 0)

    cv2.line(img, (0, 30), (w, 30), color, thickness)

    cv2.line(img, (22, 0), (22, h), color, thickness)

    cv2.line(img, (58, 0), (58, h), color, thickness)

    return cv2_to_pil(img)


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

    lower_bound = np.array(
        [
            max(0, target_rgb[0] - tolerance[0]),
            max(0, target_rgb[1] - tolerance[1]),
            max(0, target_rgb[2] - tolerance[2]),
        ]
    )

    upper_bound = np.array(
        [
            min(255, target_rgb[0] + tolerance[0]),
            min(255, target_rgb[1] + tolerance[1]),
            min(255, target_rgb[2] + tolerance[2]),
        ]
    )

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
    contours, _ = cv2.findContours(
        colored_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

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


def calculate_brightness_for_clusters(enhanced_img:Image):
    """
    对 enhance_img 处理后的图像进行“非黑色”聚类，并返回每一团的平均亮度。
    返回：list[int]  每个 int 代表一团的平均亮度（0–255）
    """
    # 1. PIL -> OpenCV (RGB)
    img_rgb = np.asarray(enhanced_img)
    # 2. 转灰度
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)

    gray = dilate_image(gray)

    # 3. 非黑色掩膜（亮度 > 20 视为前景）
    _, mask = cv2.threshold(gray, 5, 255, cv2.THRESH_BINARY)

    # 4. 连通域分析
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)

    brightness_list = []
    # 标签 0 是背景，跳过
    for lb in range(1, num_labels):
        # 取出当前团的所有像素
        cluster_pixels = gray[labels == lb]
        if cluster_pixels.size == 0:
            continue
        avg_brt = float(cluster_pixels.mean())
        brightness_list.append(int(avg_brt))

    # ---------- 可视化连通域 ----------
    # 给每个标签随机上色（0 背景保持黑色）
    # color_map = np.zeros((*labels.shape, 3), dtype=np.uint8)
    # for lb in range(1, num_labels):
    #     color_map[labels == lb] = [255 for _ in range(3)]
    # Image.fromarray(color_map).show(title="Connected Components")

    # 如果没有前景，返回空列表
    return brightness_list


def get_and_save_sinner_avatar(save=False):
    """
    获取罪人头像

    Args:
        save: 是否保存到 img/dataset/sinner_avatar/unclassified/ 目录

    Returns:
        Tuple[List[PIL.Image], List[Tuple[int, int]]]: (罪人头像 PIL Image 列表, 对应的中心坐标列表，这里的中心坐标是识别点的中心坐标，不是头像的中心坐标)
    """
    ori_sc = input_handler.capture_screenshot()
    tmp_sc = mask_screenshot(ori_sc, 0, 685, 1280, 10)
    img = filter_color_by_rgb(tmp_sc, (225, 80, 40), (20, 20, 20))
    sinner_hp = cv2_to_pil(closing_operation(pil_to_cv2(img), (5, 5), 2))
    # sinner_hp.show()
    # return
    c = find_colored_clusters_center_coords(sinner_hp)
    c.sort(key=lambda x: x[0])

    save_dir = os.path.join("img", "dataset", "sinner_avatar", "unclassified")

    pil_images = []
    centers = []
    brightness = []

    for center in c:
        center_x, center_y = center
        center_y += 685

        left = center_x - 21
        bottom = center_y - 10
        right = left + 80
        top = bottom - 55

        cropped_img = ori_sc.crop((left, top, right, bottom))

        cropped_img = enhance_img(cropped_img)

        brightness.append(calculate_brightness_for_clusters(cropped_img))

        pil_images.append(cropped_img)
        centers.append((center_x, center_y))

        if save:
            os.makedirs(save_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"sinner_avatar_{timestamp}.png"
            filepath = os.path.join(save_dir, filename)
            cropped_img.save(filepath)
            print(f"罪人头像已保存至: {filepath}")

    # print(brightness)
    return pil_images, centers, brightness


if __name__ == "__main__":
    input_handler.refresh_window_state()
    get_and_save_sinner_avatar(save=True)
