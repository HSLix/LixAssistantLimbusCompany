import cv2
import numpy as np
from PIL import Image, ImageDraw
import os
from datetime import datetime
from utils.logger import init_logger


class_names = {
    "node_abnormality_encounter",
    "node_boss_encounter",
    "node_elite_encounter",
    "node_empty",
    "node_event",
    "node_focused_encounter",
    "node_regular_encounter",
    "node_shop",
    "unclassified",
}

logger = init_logger()


def save_to_dataset_mirror_legend(img: Image, class_name: str = "unclassified"):
    if not class_name in class_names:
        raise Exception(f"未知分类名字：{class_name}；所有类：{class_names}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    save_dir = os.path.join("img", "dataset", "mirror_legend", class_name)
    os.makedirs(save_dir, exist_ok=True)
    filename = f"{timestamp}.png"
    filepath = os.path.join(save_dir, filename)
    img.save(filepath)
    logger.debug(f"图片已保存至: {filepath}")


def get_and_save_mirror_path_node(save=False):
    """
    获取镜像地牢节点

    Args:
        save: 是否保存到 img/dataset/mirror_legend/ 目录

    Returns:
        List[PIL.Image]: 镜像地牢节点 PIL Image 列表
    """
    from input.input_handler import input_handler
    from recognize.utils import mask_screenshot

    input_handler.refresh_window_state()
    tmp_sc = input_handler.capture_screenshot()
    first_up = mask_screenshot(tmp_sc, 660, 80, 130, 110)
    first_mid = mask_screenshot(tmp_sc, 660, 290, 130, 110)
    first_low = mask_screenshot(tmp_sc, 660, 500, 130, 110)
    second_up = mask_screenshot(tmp_sc, 920, 80, 130, 110)
    second_mid = mask_screenshot(tmp_sc, 920, 300, 130, 110)
    second_low = mask_screenshot(tmp_sc, 920, 500, 130, 110)

    to_save = [first_up, first_mid, first_low, second_up, second_mid, second_low]

    if save:
        for img in to_save:
            save_to_dataset_mirror_legend(img, "unclassified")

    return to_save