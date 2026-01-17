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
    
    # 获取当前时间戳
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    
    # 创建保存路径
    save_dir = os.path.join("img", "dataset", "mirror_legend", class_name)
    os.makedirs(save_dir, exist_ok=True)
    
    # 生成文件名
    filename = f"{timestamp}.png"
    filepath = os.path.join(save_dir, filename)
    
    # 保存图片
    img.save(filepath)
    logger.debug(f"图片已保存至: {filepath}")


def guess_class_name(img: Image) -> str:
    return "unclassified"


def get_mirror_path_node():
    from input.input_handler import input_handler
    from recognize.utils import mask_screenshot
    input_handler.refresh_window_state()
    # pil = mask_screenshot(input_handler.capture_screenshot(), 330, 70, 750, 550) # 镜牢识别下两列节点的区域
    tmp_sc = input_handler.capture_screenshot()
    first_up = mask_screenshot(tmp_sc, 660, 80, 130, 110)
    first_mid = mask_screenshot(tmp_sc, 660, 290, 130, 110)
    first_low = mask_screenshot(tmp_sc, 660, 500, 130, 110)

    second_up = mask_screenshot(tmp_sc, 920, 80, 130, 110)
    second_mid = mask_screenshot(tmp_sc, 920, 300, 130, 110)
    second_low = mask_screenshot(tmp_sc, 920, 500, 130, 110)

    to_save = [first_up, first_mid, first_low, second_up, second_mid, second_low]

    for img in to_save:
        save_to_dataset_mirror_legend(img, guess_class_name(img))


if __name__ == "__main__":
    get_mirror_path_node()
    