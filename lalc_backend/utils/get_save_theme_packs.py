import cv2
import numpy as np
from PIL import Image, ImageDraw
import os
from datetime import datetime
import difflib

from recognize.img_recognizer import recognize_handler
from recognize.img_registry import get_images_by_tag, get_max_radio_of_theme_packs, register_images_from_directory
from recognize.utils import pil_to_cv2, cv2_to_pil, mask_screenshot
from input.input_handler import input_handler
from utils.logger import init_logger

logger = init_logger()



def get_rect_from_center(x, y,
                         left_offset=135, up_offset=35,
                         right_offset=35, down_offset=295):
    """
    根据中心点坐标返回左上角和右下角
    """
    x1 = x - left_offset
    y1 = y - up_offset
    x2 = x + right_offset
    y2 = y + down_offset
    return (x1, y1), (x2, y2)


def detect_and_save_theme_pack(pil_img):
    """
    输入：PIL Image
    功能增强版：
      1. 先模板匹配并按 x 排序
      2. 对每个匹配点进行点击
      3. OCR 识别对应主题包文本，作为文件名
      4. 自动创建 theme_packs 文件夹
      5. 裁剪并按 OCR 命名保存
      6. 画框+最终展示
    :return [(主题包名, 主题包中心横坐标, 主题包中心纵坐标)]
    """
    get_new_theme_pack = False
    logger.info("识别并保存未存储的主题包（非 new，new 的卡包不会显示真正包", pil_img)

    # ---- 1. 模板匹配检测 ----
    matches = recognize_handler.template_match(pil_img, "theme_pack_detail")
    matches.sort(key=lambda x: x[0])  # 按横坐标排序

    if not matches:
        logger.debug("未检测到 theme pack")
        return

    # ---- 2. 保存目录 ----
    save_dir = "img/theme_packs"
    os.makedirs(save_dir, exist_ok=True)

    draw = ImageDraw.Draw(pil_img)
    
    ocr_results = recognize_handler.detect_text_in_image(
            pil_img,
            mask=[100, 440, 1100, 60]
    )
    ocr_results.sort(key=lambda x:x[1])

    # ---- 3. 关联 OCR 结果和匹配项 ----
    # 存储处理过的主题包信息
    processed_theme_packs = []
    
    # 创建一个列表来跟踪哪些 OCR 结果已经被使用
    used_ocr_indices = set()

    existed_theme_packs = get_images_by_tag("theme_packs")

    # max_theme_pack_radio = get_max_radio_of_theme_packs()
    
    # 没有进入过的主题包，不能留档，等探索后再留
    theme_pack_new = recognize_handler.template_match(pil_img, "mirror_theme_pack_new")

    # 过滤matches，移除与theme_pack_new位置相近的项
    filtered_matches = []
    for match in matches:
        mx, my = match[0], match[1]
        
        # 检查是否有theme_pack_new在其x坐标-180范围内（同时考虑y坐标的接近性）
        skip_match = False
        for new_x, new_y, _ in theme_pack_new:
            if mx - new_x <= 180 and abs(my - new_y) <= 50:  # 添加y坐标检查，避免垂直方向差异过大
                logger.debug(f"检测到 new 标记，剔除主题包位置 ({mx}, {my}) 不做图片保存记录")
                skip_match = True
                break
        
        if not skip_match:
            filtered_matches.append(match)
    
    matches = filtered_matches

    # 遍历所有匹配项
    for idx, match in enumerate(matches):
        cx, cy = match[0], match[1]

        # 根据中心计算矩形
        (x1, y1), (x2, y2) = get_rect_from_center(cx, cy)
        x1 = max(0, x1); y1 = max(0, y1)
        x2 = min(pil_img.width, x2)
        y2 = min(pil_img.height, y2)

        # 裁剪
        cropped = pil_img.crop((x1, y1, x2, y2))

        # 查找最接近的 OCR 结果（x 坐标差不超过 50）
        best_ocr_idx = None
        best_distance = float('inf')
        
        for ocr_idx, (_, ocr_cx, _, _) in enumerate(ocr_results):
            # 跳过已经使用的 OCR 结果
            if ocr_idx in used_ocr_indices:
                continue
                
            # 计算匹配项中心和 OCR 文本中心的 x 坐标差
            distance = abs(cx - ocr_cx)
            
            # 如果距离小于等于 100 并且是目前最小的距离，则记录
            if distance <= 100 and distance < best_distance:
                best_distance = distance
                best_ocr_idx = ocr_idx
        
        # 根据匹配结果确定文件名
        if best_ocr_idx is not None:
            # 找到了匹配的 OCR 结果
            raw_name = ocr_results[best_ocr_idx][0]
            processed_name = raw_name.strip()
            used_ocr_indices.add(best_ocr_idx)
        else:
            # 没有找到匹配的 OCR 结果，使用时间戳作为文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            processed_name = f"theme_pack_{timestamp}_{idx}"
        
        processed_theme_packs.append((processed_name, (x1+x2)//2, (y1+y2)//2))

        # 获取已存在的theme_packs图像名称列表
        existing_theme_packs = get_images_by_tag("theme_packs") + get_images_by_tag("theme_packs")
        existing_names = [name for name, _ in existing_theme_packs]
        
        # 如果processed_name已经存在于现有图像名称中，则跳过保存
        # tmp = difflib.get_close_matches(processed_name, existing_names, cutoff=0.9)
        # if len(tmp) > 0:
        #     logger.debug(f"图片名字 {processed_name}.png 已存在({tmp[0]})，跳过保存")
        #     continue

        # 从图片上检查是否有重合的
        existed_flag = False
        
        for theme_pack in existed_theme_packs:
            res = recognize_handler.template_match(cropped, theme_pack[0], 0.85, mask_template=[20, 20, 130, 290])
            if len(res) > 0:
                existed_flag = True
                logger.debug(f"新检测的卡包 {processed_name} 与已有卡包 {theme_pack[0]} 图片相似({res[0][2]})，跳过保存")
                break
        
        if existed_flag:
            continue
            
        filename = os.path.join(save_dir, f"{processed_name}.png")
        cropped.save(filename)

        get_new_theme_pack = True
        logger.info(f"已保存新主题包: {filename}")
        
        # ⑥ 在原图画框
        # draw.rectangle((x1, y1, x2, y2), outline="red", width=3)
        # input_handler.key_press("esc")
        # time.sleep(1)

    # ---- 5. 显示最终图像 ----
    # pil_img.show()

    if get_new_theme_pack:
        register_images_from_directory()

    return processed_theme_packs

if __name__ == "__main__":
    input_handler.refresh_window_state()
    input_handler.set_window_size()
    # 使用你的图片路径
    print(detect_and_save_theme_pack(input_handler.capture_screenshot()))