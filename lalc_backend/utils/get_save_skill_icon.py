import cv2
import numpy as np
from PIL import Image
import os
from datetime import datetime

from recognize.img_recognizer import recognize_handler
from recognize.utils import mask_screenshot
from input.input_handler import input_handler


def get_and_save_skill_icons(save=False):
    """
    获取技能图标

    Args:
        save: 是否保存到 img/dataset/skill_icon/unclassified/ 目录

    Returns:
        Tuple[List[PIL.Image], List[Tuple[int, int]]]: (技能图标 PIL Image 列表, 对应的中心坐标列表)
    """
    skill_types = ["skill_blunt", "skill_pierce", "skill_slash"]
    skills = []
    tmp_sc = input_handler.capture_screenshot()
    for type_name in skill_types:
        skills += recognize_handler.pyramid_template_match(
            tmp_sc, type_name, 0.8, mask=[0, 470, 1280, 155]
        )
    skills.sort(key=lambda x: x[0])

    offset = [(15, -20), (20, -15)]
    save_dir = os.path.join("img", "dataset", "skill_icon", "unclassified")

    win_rate = recognize_handler.template_match(tmp_sc, "win_rate")
    if not win_rate:
        win_rate = [(1280, 0)]

    pil_images = []
    centers = []

    for skill in skills:
        center_x, center_y, _, scale_ratio = skill

        if center_x > win_rate[0][0]:
            continue

        if center_y < 560 or (570 < center_y < 590) or center_y > 600:
            continue

        selected_offset = offset[1] if scale_ratio >= 1.2 else offset[0]
        final_x = center_x + selected_offset[0]
        final_y = center_y + selected_offset[1]

        left = final_x - 40
        top = final_y - 40
        right = final_x + 40
        bottom = final_y + 40

        cropped_img = tmp_sc.crop((left, top, right, bottom))
        pil_images.append(cropped_img)
        centers.append((final_x, final_y))

        if save:
            os.makedirs(save_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"skill_{timestamp}.png"
            filepath = os.path.join(save_dir, filename)
            cropped_img.save(filepath)
            print(f"技能图标已保存至: {filepath}")

    return pil_images, centers


# 使用示例
if __name__ == "__main__":
    # 加载图片
    from input.input_handler import input_handler
    from recognize.utils import (
        mask_screenshot,
        closing_operation,
        pil_to_cv2,
        cv2_to_pil,
    )

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

    get_and_save_skill_icons(save=True)
