import os
import random
from datetime import datetime

from input.input_handler import input_handler
from recognize.utils import mask_screenshot
from PIL import Image, ImageDraw


def get_mirror_path() -> Image.Image:
    tmp_sc = input_handler.capture_screenshot()

    # 定义六个区域的坐标 (x, y, width, height)
    regions = [
        (670, 90, 110, 90),  # first_up
        (670, 300, 110, 90),  # first_mid
        (670, 510, 110, 90),  # first_low
        (930, 90, 110, 90),  # second_up
        (930, 310, 110, 90),  # second_mid
        (930, 510, 110, 90),  # second_low
    ]

    # 在每个区域随机生成涂鸦
    draw = ImageDraw.Draw(tmp_sc)
    for region in regions:
        x, y, width, height = region
        generate_random_graffiti(draw, x, y, width, height)

    # 截取指定区域
    # tmp_sc = mask_screenshot(tmp_sc, 610, 70, 490, 540)
    # tmp_sc = mask_screenshot(tmp_sc, 720, 70, 250, 540)
    tmp_sc = mask_screenshot(tmp_sc, 670, 70, 360, 540)
    return tmp_sc


def generate_random_graffiti(draw: ImageDraw, x: int, y: int, width: int, height: int):
    """
    在指定区域随机生成涂鸦，包括线条和斑点

    Args:
        draw: PIL ImageDraw 对象
        x, y: 区域左上角坐标
        width, height: 区域宽度和高度
    """
    # 随机选择涂鸦类型和数量
    num_elements = random.randint(7, 12)

    for _ in range(num_elements):
        element_type = random.choice(["line", "dot", "circle"])

        if element_type == "line":
            # 生成随机线条
            start_x = x + random.randint(0, width)
            start_y = y + random.randint(0, height)
            end_x = x + random.randint(0, width)
            end_y = y + random.randint(0, height)

            # 随机颜色 (偏向亮色，与游戏界面匹配)
            color = (
                random.randint(200, 255),  # R
                random.randint(200, 255),  # G
                random.randint(200, 255),  # B
            )

            # 随机线宽
            width_line = random.randint(3, 5)

            draw.line([start_x, start_y, end_x, end_y], fill=color, width=width_line)

        elif element_type == "dot":
            # 生成随机斑点
            dot_x = x + random.randint(0, width)
            dot_y = y + random.randint(0, height)

            # 随机颜色
            color = (
                random.randint(150, 255),
                random.randint(150, 255),
                random.randint(150, 255),
            )

            # 随机大小的斑点
            dot_size = random.randint(6, 12)

            # 绘制多个像素模拟斑点
            for dx in range(-dot_size // 2, dot_size // 2 + 1):
                for dy in range(-dot_size // 2, dot_size // 2 + 1):
                    if random.random() > 0.2:  # 20%概率跳过，创造不规则形状
                        px = min(max(dot_x + dx, x), x + width - 1)
                        py = min(max(dot_y + dy, y), y + height - 1)
                        if px >= x and px < x + width and py >= y and py < y + height:
                            draw.point([px, py], fill=color)

        elif element_type == "circle":
            # 生成随机圆形
            center_x = x + random.randint(10, width - 10)
            center_y = y + random.randint(10, height - 10)
            radius = random.randint(7, 12)

            # 随机颜色
            color = (
                random.randint(180, 255),
                random.randint(180, 255),
                random.randint(180, 255),
            )

            # 计算圆形边界
            bbox = [
                center_x - radius,
                center_y - radius,
                center_x + radius,
                center_y + radius,
            ]

            # 绘制圆形
            draw.ellipse(bbox, fill=color)


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
