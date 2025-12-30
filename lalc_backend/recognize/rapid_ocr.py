import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from PIL import Image
import cv2
import numpy as np


from rapidocr import RapidOCR
from recognize.utils import pil_to_cv2, cv2_to_pil, mask_screenshot, fill_mask_screenshot
from input.input_handler import input_handler

import os
base_dir = os.path.dirname(__file__)
yaml_path = os.path.join(base_dir, "rapidocr.yaml")
# print(yaml_path)
img_ocr = RapidOCR(config_path=yaml_path)


# def detect_text_in_image(image: Image.Image, visualize=False, threshold=0.3):
#     """
#     detect_text_in_image:
#     使用 CLAHE
#     特别适合粗体英文、间距小、笔画粘连的 OCR 场景
#     :return: 匹配(包含目标字符串)的列表，每个元素为 (文字, center_x, center_y, 置信度)
#     """
#     # ----------- 统一转灰度 -----------
#     image_cv = pil_to_cv2(image, grayscale=True)

#     # image_cv = cv2.resize(image_cv, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)

#     # image_cv = cv2.convertScaleAbs(image_cv, alpha=1.3, beta=15)

#     # ----------- CLAHE（增强局部对比）-----------
#     clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
#     image_cv = clahe.apply(image_cv)

#     # ----------- RapidOCR -----------
#     result = img_ocr(image_cv)

#     dt_boxes = result.boxes
#     texts = result.txts
#     scores = result.scores

#     detected_texts = []
#     if dt_boxes is None or len(dt_boxes) == 0:
#         if visualize:
#             cv2_to_pil(image_cv, True).show()
#         return detected_texts

#     for box, text, conf in zip(dt_boxes, texts, scores):
#         box = np.array(box)
#         center_x = int(box[:, 0].mean())
#         center_y = int(box[:, 1].mean())
#         detected_texts.append((text, center_x, center_y, float(conf)))

#     detected_texts.sort(key=lambda x: x[3], reverse=True)

#     # ----------- 可视化（此时才转回彩色）-----------
#     if visualize:
#         vis_img = cv2.cvtColor(image_cv, cv2.COLOR_GRAY2BGR)
#         for box, text, conf in zip(dt_boxes, texts, scores):
#             if conf >= threshold:
#                 box = np.array(box, dtype=np.int32)
#                 cv2.polylines(vis_img, [box], True, (255, 0, 0), 2)
#         cv2_to_pil(vis_img).show()

#     return detected_texts


# def detect_text_in_image(image: Image.Image, visualize=False, threshold=0.3, y_merge_threshold=30, dx_threshold=80):
#     """
#     detect_text_in_image with non-consecutive line merging.
#     Handles cases like:
#         [('A', x, y1), ('B', x2, y2), ('C', x, y3)] → merge A & C if y3-y1 <= threshold and |x-x| small.
#     """
#     # ----------- 预处理 -----------
#     image_cv = pil_to_cv2(image, grayscale=True)
#     clahe = cv2.createCLAHE(clipLimit=2, tileGridSize=(16, 16))
#     image_cv = clahe.apply(image_cv)

#     result = img_ocr(image_cv)
#     dt_boxes = result.boxes
#     texts = result.txts
#     scores = result.scores

#     if dt_boxes is None or len(dt_boxes) == 0:
#         if visualize:
#             cv2_to_pil(image_cv, True).show()
#         return []

#     # 构建原始项
#     raw_items = []
#     for box, text, conf in zip(dt_boxes, texts, scores):
#         box = np.array(box, dtype=np.float32)
#         cx = int(box[:, 0].mean())
#         cy = int(box[:, 1].mean())
#         raw_items.append({
#             'text': text,
#             'cx': cx,
#             'cy': cy,
#             'conf': float(conf),
#             'box': box.copy()
#         })

#     # 按 y 排序（从上到下）
#     raw_items.sort(key=lambda x: x['cy'])

#     n = len(raw_items)
#     visited = [False] * n
#     merged_items = []

#     for i in range(n):
#         if visited[i]:
#             continue

#         # 当前起始项
#         base = raw_items[i]
#         group = [i]  # 存储索引
#         visited[i] = True

#         # 向后查找所有可合并项（不要求连续！）
#         for j in range(i + 1, n):
#             if visited[j]:
#                 continue
#             other = raw_items[j]
#             dy = other['cy'] - base['cy']
#             dx = abs(other['cx'] - base['cx'])

#             # 必须在下方，且垂直距离合理，且水平对齐
#             if 0 < dy <= y_merge_threshold and dx <= dx_threshold:
#                 group.append(j)
#                 visited[j] = True

#         # 合并 group 中所有项
#         merged_text = ' '.join(raw_items[idx]['text'] for idx in sorted(group, key=lambda idx: raw_items[idx]['cy']))
#         merged_boxes = [raw_items[idx]['box'] for idx in group]
#         merged_conf = min(raw_items[idx]['conf'] for idx in group)

#         # 计算合并后的 bounding box
#         all_points = np.concatenate(merged_boxes, axis=0)
#         min_x, min_y = all_points.min(axis=0)
#         max_x, max_y = all_points.max(axis=0)
#         merged_box = np.array([
#             [min_x, min_y],
#             [max_x, min_y],
#             [max_x, max_y],
#             [min_x, max_y]
#         ], dtype=np.int32)

#         cx = int((min_x + max_x) // 2)
#         cy = int((min_y + max_y) // 2)
#         merged_items.append((merged_text, cx, cy, merged_conf, merged_box))

#     # 按置信度排序
#     merged_items.sort(key=lambda x: x[3], reverse=True)

#     detected_texts = [(text, cx, cy, conf) for text, cx, cy, conf, _ in merged_items]

#     # ----------- 可视化 -----------
#     if visualize:
#         vis_img = cv2.cvtColor(image_cv, cv2.COLOR_GRAY2BGR)
#         for text, cx, cy, conf, box in merged_items:
#             if conf >= threshold:
#                 cv2.polylines(vis_img, [box], True, (255, 0, 0), 2)
#         cv2_to_pil(vis_img).show()

#     return detected_texts


import numpy as np
from PIL import Image
import cv2

def detect_text_in_image(image: Image.Image, visualize=False, threshold=0.3, merge_x=True, merge_y=True):
    """
    detect_text_in_image with horizontal and vertical merging.
    - Horizontal merge: x distance <= x_merge_threshold
    - Vertical merge: y distance <= y_merge_threshold
    :param image: 输入图像
    :param visualize: 是否可视化结果
    :param threshold: 可视化时的置信度阈值
    :param merge_x: 是否在x方向合并文本（默认True）
    :param merge_y: 是否在y方向合并文本（默认True）
    """
    # ----------- 预处理 ----------- 
    image_cv = pil_to_cv2(image, grayscale=True)

    clahe = cv2.createCLAHE(clipLimit=2, tileGridSize=(16, 16))
    image_cv = clahe.apply(image_cv)

    result = img_ocr(image_cv)
    dt_boxes = result.boxes
    texts = result.txts
    scores = result.scores

    if dt_boxes is None or len(dt_boxes) == 0:
        if visualize:
            cv2_to_pil(image_cv, True).show()
        return []

    # 构建原始项
    raw_items = []
    for box, text, conf in zip(dt_boxes, texts, scores):
        box = np.array(box, dtype=np.float32)
        cx = int(box[:, 0].mean())  # 中心x坐标
        cy = int(box[:, 1].mean())  # 中心y坐标
        raw_items.append({
            'text': text,
            'cx': cx,
            'cy': cy,
            'conf': float(conf),
            'box': box.copy()
        })

    # 创建初始合并项列表
    merged_items = []
    
    # 第一步：处理x方向合并
    if merge_x:
        # 按 x 坐标排序（从左到右）
        raw_items.sort(key=lambda x: x['cx'])

        n = len(raw_items)
        visited = [False] * n

        # 合并横向的文本（同一行文本），x 合并
        for i in range(n):
            if visited[i]:
                continue

            # 当前起始项
            base = raw_items[i]
            group = [i]  # 存储索引
            visited[i] = True

            # 向后查找所有可合并项（即合并在同一行的文本）
            for j in range(i + 1, n):
                if visited[j]:
                    continue
                other = raw_items[j]
                dx = abs(other['cx'] - base['cx'])  # x坐标的差
                dy = abs(other['cy'] - base['cy'])

                # 如果水平距离小于设定阈值，认为是同一行的一部分
                if dx <= 100 and dy <= 10:
                    group.append(j)
                    visited[j] = True

            # 合并 group 中所有项
            merged_text = ' '.join(raw_items[idx]['text'] for idx in sorted(group, key=lambda idx: raw_items[idx]['cx']))  # 按 x 排序
            merged_boxes = [raw_items[idx]['box'] for idx in group]
            merged_conf = min(raw_items[idx]['conf'] for idx in group)

            # 计算合并后的 bounding box
            all_points = np.concatenate(merged_boxes, axis=0)
            min_x, min_y = all_points.min(axis=0)
            max_x, max_y = all_points.max(axis=0)
            merged_box = np.array([
                [min_x, min_y],
                [max_x, min_y],
                [max_x, max_y],
                [min_x, max_y]
            ], dtype=np.int32)

            cx = int((min_x + max_x) // 2)
            cy = int((min_y + max_y) // 2)
            merged_items.append((merged_text, cx, cy, merged_conf, merged_box))
    else:
        # 如果不合并x方向，直接使用原始项
        for item in raw_items:
            merged_items.append((item['text'], item['cx'], item['cy'], item['conf'], item['box']))

    # 创建最终合并项列表
    final_merged_items = []
    
    # 第二步：处理y方向合并
    if merge_y:
        # 按 y 坐标合并（处理换行），y 合并
        merged_items.sort(key=lambda x: x[2])  # 按 y 坐标排序

        # 遍历合并后的文本项，进一步合并相邻的行
        visited_y = [False] * len(merged_items)

        for i in range(len(merged_items)):
            if visited_y[i]:
                continue

            # 当前起始项
            base = merged_items[i]
            group_y = [i]  # 存储索引
            visited_y[i] = True

            # 向后查找所有可合并项（即合并在同一行的文本）
            for j in range(i + 1, len(merged_items)):
                if visited_y[j]:
                    continue
                other = merged_items[j]
                dy = abs(other[2] - base[2])  # y坐标的差
                dx = abs(other[1] - base[1])  # x坐标的差

                # 如果垂直距离小于设定阈值，且水平距离合理
                if dy <= 30 and dx <= 80:
                    group_y.append(j)
                    visited_y[j] = True

            # 合并 group 中所有项
            merged_text_y = ' '.join(merged_items[idx][0] for idx in sorted(group_y, key=lambda idx: merged_items[idx][2]))  # 按 y 排序
            merged_boxes_y = [merged_items[idx][4] for idx in group_y]
            merged_conf_y = min(merged_items[idx][3] for idx in group_y)

            # 计算合并后的 bounding box
            all_points_y = np.concatenate(merged_boxes_y, axis=0)
            min_x, min_y = all_points_y.min(axis=0)
            max_x, max_y = all_points_y.max(axis=0)
            merged_box_y = np.array([
                [min_x, min_y],
                [max_x, min_y],
                [max_x, max_y],
                [min_x, max_y]
            ], dtype=np.int32)

            cx = int((min_x + max_x) // 2)
            cy = int((min_y + max_y) // 2)
            final_merged_items.append((merged_text_y, cx, cy, merged_conf_y, merged_box_y))
    else:
        # 如果不合并y方向，直接使用merged_items
        final_merged_items = merged_items

    detected_texts = [(text, cx, cy, conf) for text, cx, cy, conf, _ in final_merged_items]

    # ----------- 可视化 ----------- 
    if visualize:
        vis_img = cv2.cvtColor(image_cv, cv2.COLOR_GRAY2BGR)
        for text, cx, cy, conf, box in final_merged_items:
            if conf >= threshold:
                # 确保box是正确的整数类型
                box = np.array(box, dtype=np.int32)
                cv2.polylines(vis_img, [box], True, (255, 0, 0), 2)
        cv2_to_pil(vis_img).show()

    return detected_texts


def find_text_in_image(pil_image, target_text, visualize=False, threshold=0.5):
    """
    在图像中查找指定的文字
    :return: 匹配(包含目标字符串)的列表，每个元素为 (文字, center_x, center_y, 置信度)
    """
    detected_texts = detect_text_in_image(pil_image, visualize=visualize, threshold=threshold)

    found_texts = []
    for text in detected_texts:
        if target_text in text[0]:
            found_texts.append(text)

    return found_texts


if __name__ == "__main__":
    import sys
    import os
    # sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    input_handler.refresh_window_state()
    input_handler.set_window_size()

    from PIL import Image

    import time
    start = time.time()
    res = detect_text_in_image(
        # fill_mask_screenshot(input_handler.capture_screenshot(), 100, 435, 1100, 50), # 主题包名字
        # fill_mask_screenshot(input_handler.capture_screenshot(), 1120, 500, 110, 55), # 战斗人员数
        # fill_mask_screenshot(input_handler.capture_screenshot(), 535, 320, 165, 50), # 技能替换
        # fill_mask_screenshot(input_handler.capture_screenshot(), 535, 325, 650, 50), # 商店第一行饰品名字
        # fill_mask_screenshot(input_handler.capture_screenshot(), 535, 200, 650, 40), # 商店第一行饰品顶部购买标识
        # fill_mask_screenshot(input_handler.capture_screenshot(), 535, 355, 650, 40), # 商店第二行饰品顶部购买标识
        # fill_mask_screenshot(input_handler.capture_screenshot(), 535, 480, 650, 50), # 商店第二行饰品名字
        # fill_mask_screenshot(input_handler.capture_screenshot(), 568, 100, 100, 80), # 商店金额
        # fill_mask_screenshot(input_handler.capture_screenshot(), 110, 120, 1090, 60), # 换层 ego 的顶
        fill_mask_screenshot(input_handler.capture_screenshot(), 90, 175, 1090, 40), # 换层 ego 的名字
        # fill_mask_screenshot(input_handler.capture_screenshot(), 280, 150, 300, 130), # enhance ego 的名字
        # input_handler.capture_screenshot(),
        visualize=True,
        # merge_x=False,
        # merge_y=False,
    )
    print("used time:%f" % (time.time()-start))
    print(res)

    # pos = find_text_in_image(mask_screenshot(input_handler.capture_screenshot(), 670, 140, 620, 500), r"Select to gain*E.G.O Gift")
    # print(pos)

    # index = str.find(res[0][0], "/")
    # selected_count = int(res[0][0][:index])
    # all_count = int(res[0][0][index+1:])
    # print(selected_count, all_count)
