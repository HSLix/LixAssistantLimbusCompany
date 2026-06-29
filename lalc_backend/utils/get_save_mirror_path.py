import os
from datetime import datetime

from input.input_handler import input_handler
from recognize.utils import mask_screenshot
from PIL import Image


def get_mirror_path() -> Image.Image:
    tmp_sc = input_handler.capture_screenshot()
    tmp_sc = mask_screenshot(tmp_sc, 670, 70, 360, 540)
    return tmp_sc


def get_and_save_mirror_path(save=False):
    """
    获取镜像路径截图

    Args:
        save: 是否保存到 img/dataset/mirror_path/all/ 目录

    Returns:
        List[PIL.Image]: 镜像路径 PIL Image 列表
    """
    image = get_mirror_path()

    if save:
        save_dir = "img/dataset/mirror_path/all/"
        os.makedirs(save_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f_")
        filename = f"{timestamp}.png"
        filepath = os.path.join(save_dir, filename)
        image.save(filepath)
        print(f"镜像路径已保存至: {filepath}")
        return [image]

    return [image]


if __name__ == "__main__":
    input_handler.refresh_window_state()
    get_and_save_mirror_path(save=True)
