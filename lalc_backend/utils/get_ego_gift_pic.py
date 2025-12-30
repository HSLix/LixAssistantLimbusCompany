import cv2
import numpy as np
import sys
import os
import re
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from input.input_handler import input_handler
from recognize.utils import pil_to_cv2, cv2_to_pil
from recognize.img_recognizer import recognize_handler
from recognize.img_registry import get_image


def contour_detection(img):
    """
    使用轮廓检测来自动定位和切割图标。
    """
    img = pil_to_cv2(img)
    img_for_drawing = img.copy()

    # ---- 图像预处理 ----
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 130, 290) # burns-blunt
    # edges = cv2.Canny(gray, 120, 290) # burns-blunt
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
    # 查看边缘是否齐整
    # edges_pil = cv2_to_pil(edges, True)
    # edges_pil.show()

    # ---- 查找轮廓 ----
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # ---- 创建输出目录 ----
    output_dir = "ego_gift_icons"
    os.makedirs(output_dir, exist_ok=True)
    print("正在使用轮廓检测法切割图标...")

    # ---- 自动递增编号 ----
    existing_numbers = []
    for fname in os.listdir(output_dir):
        if fname.startswith("icon_") and fname.endswith(".png"):
            num = fname[5:-4]
            if num.isdigit():
                existing_numbers.append(int(num))
    start_index = max(existing_numbers) + 1 if existing_numbers else 0
    icon_index = start_index

    # ---- 筛选满足条件的轮廓 ----
    valid_boxes = []  # (x, y, w, h, center_y)

    for contour in contours:
        area = cv2.contourArea(contour)
        if 3000 < area < 7000:
            x, y, w, h = cv2.boundingRect(contour)
            if w > 100 or h > 100:
                continue
            aspect_ratio = w / h
            if 0.9 < aspect_ratio < 1.1:
                center_y = y + h / 2
                valid_boxes.append([x, y, w, h, center_y])

    # --------------------------------------------------------
    #  ⭐ 对近似同一行的 y 归一化
    # --------------------------------------------------------

    if not valid_boxes:
        print("未检测到图标！")
        return

    # 先按 center_y 排序
    valid_boxes.sort(key=lambda b: b[4])

    merged_rows = []   # 每个 row = [box1, box2, ...]
    row_threshold = 12  # y 差多少算同一行（可调）

    for box in valid_boxes:
        x, y, w, h, cy = box

        if not merged_rows:
            merged_rows.append([box])
        else:
            # 比较当前盒与上一行最后一个盒的 y 距离
            last_cy = merged_rows[-1][-1][4]
            if abs(cy - last_cy) <= row_threshold:
                merged_rows[-1].append(box)
            else:
                merged_rows.append([box])

    # 每行的 y 均值对齐（使排序稳定）
    normalized_boxes = []
    for row in merged_rows:
        avg_y = int(np.mean([b[1] for b in row]))  # 使用原始 y 的均值
        for b in row:
            x, y, w, h, cy = b
            normalized_boxes.append((x, avg_y, w, h))

    # --------------------------------------------------------
    # ⭐ 最终排序：先 y（行），再 x（列）
    # --------------------------------------------------------
    normalized_boxes.sort(key=lambda b: (b[1], b[0]))

    # ---- 切割并保存 ----
    for (x, y, w, h) in normalized_boxes:
        icon_roi = img[y+15:y + h-15, x+15:x + w-15]

        icon_filename = os.path.join(output_dir, f"icon_{icon_index}.png")
        # cv2.imwrite(icon_filename, icon_roi)
        icon_index += 1

        cv2.rectangle(img_for_drawing, (x, y), (x + w, y + h), (0, 255, 0), 2)

    print(f"切割完成！输出编号范围: {start_index} ~ {icon_index-1}，共 {icon_index - start_index} 个图标。")

    # ---- 显示结果 ----
    resized_img = cv2.resize(img_for_drawing, (img_for_drawing.shape[1], img_for_drawing.shape[0]))
    cv2_to_pil(resized_img).show()
    print(normalized_boxes)


def gift_search_named_contour_detection(img):
    """
    使用轮廓检测来自动定位图标，然后通过点击和OCR获取图标名称并以此命名保存。
    """
    img = pil_to_cv2(img)
    img_for_drawing = img.copy()

    # ---- 图像预处理 ----
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 120, 290)  # burns-blunt
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

    # ---- 查找轮廓 ----
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # ---- 创建输出目录 ----
    output_dir = "ego_gift_icons"
    os.makedirs(output_dir, exist_ok=True)
    print("正在使用带命名的轮廓检测法切割图标...")

    # ---- 筛选满足条件的轮廓 ----
    valid_boxes = []  # (x, y, w, h, center_y)

    for contour in contours:
        area = cv2.contourArea(contour)
        if 3000 < area < 6000:
            x, y, w, h = cv2.boundingRect(contour)
            if w > 100 or h > 100:
                continue
            aspect_ratio = w / h
            if 0.9 < aspect_ratio < 1.1:
                center_y = y + h / 2
                valid_boxes.append([x, y, w, h, center_y])

    # --------------------------------------------------------
    #  ⭐ 对近似同一行的 y 归一化
    # --------------------------------------------------------

    if not valid_boxes:
        print("未检测到图标！")
        return

    # 先按 center_y 排序
    valid_boxes.sort(key=lambda b: b[4])

    merged_rows = []   # 每个 row = [box1, box2, ...]
    row_threshold = 12  # y 差多少算同一行（可调）

    for box in valid_boxes:
        x, y, w, h, cy = box

        if not merged_rows:
            merged_rows.append([box])
        else:
            # 比较当前盒与上一行最后一个盒的 y 距离
            last_cy = merged_rows[-1][-1][4]
            if abs(cy - last_cy) <= row_threshold:
                merged_rows[-1].append(box)
            else:
                merged_rows.append([box])

    # 每行的 y 均值对齐（使排序稳定）
    normalized_boxes = []
    for row in merged_rows:
        avg_y = int(np.mean([b[1] for b in row]))  # 使用原始 y 的均值
        for b in row:
            x, y, w, h, cy = b
            normalized_boxes.append((x, avg_y, w, h))

    # --------------------------------------------------------
    # ⭐ 最终排序：先 y（行），再 x（列）
    # --------------------------------------------------------
    normalized_boxes.sort(key=lambda b: (b[1], b[0]))

    # ---- 点击、识别和保存 ----
    saved_count = 0
    skipped_count = 0
    for i, (x, y, w, h) in enumerate(normalized_boxes):
        try:
            # 计算中心点
            center_x = x + w // 2
            center_y = y + h // 2
            
            # 点击图标中心
            input_handler.click(center_x, center_y)
            
            # 等待界面响应
            import time
            time.sleep(0.2)
            
            # 截图并识别图标名称
            screenshot = input_handler.capture_screenshot(reset=False)
            
            # 使用OCR识别图标名称 (假设名称在图标附近的一个区域内)
            # 这里我们假设名称出现在图标上方一定区域
            name_region = [900, 200, 300, 45]
            ocr_results = recognize_handler.detect_text_in_image(screenshot, mask=name_region)
            
            if ocr_results and len(ocr_results) > 0:
                # 取置信度最高的结果作为名称
                icon_name = ocr_results[0][0]
                
                # 清理文件名，移除非法字符
                # icon_name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', icon_name)
                
                # 如果名称为空或者太短，使用默认名称
                # if not icon_name or len(icon_name.strip()) < 1:
                #     icon_name = f"unnamed_icon_{i}"
                
                icon_name = icon_name.strip()
                
                # 切割图标
                icon_roi = img[y+5:y + h-5, x+5:x + w-5]
                
                # 保存图标，使用识别出的名称
                icon_filename = os.path.join(output_dir, f"{icon_name}.png")
                
                # 如果文件已存在，就跳过
                if os.path.exists(icon_filename):
                    print(f"文件 {icon_name}.png 已存在，跳过...")
                    skipped_count += 1
                    input_handler.click(center_x, center_y)
                    time.sleep(0.5)
                    continue
                
                cv2.imwrite(icon_filename, icon_roi)
                saved_count += 1
                print(f"保存图标: {icon_name}")
            else:
                # 如果没有识别到名称，使用默认名称
                icon_roi = img[y+5:y + h-5, x+5:x + w-5]
                icon_filename = os.path.join(output_dir, f"unnamed_icon_{i}.png")
                
                # 如果文件已存在，就跳过
                if os.path.exists(icon_filename):
                    print(f"文件 unnamed_icon_{i}.png 已存在，跳过...")
                    skipped_count += 1
                    continue
                    
                cv2.imwrite(icon_filename, icon_roi)
                saved_count += 1
                print(f"保存未命名图标: unnamed_icon_{i}")
            
            # 在原图上绘制矩形框
            cv2.rectangle(img_for_drawing, (x, y), (x + w, y + h), (0, 255, 0), 2)
            # 恢复每点击的情形
            input_handler.click(center_x, center_y)
            time.sleep(0.2)
        except Exception as e:
            print(f"处理第 {i} 个图标时出错: {str(e)}")
            continue

    print(f"命名切割完成！共保存 {saved_count} 个图标，跳过 {skipped_count} 个已存在的图标。")

    # ---- 显示结果 ----
    resized_img = cv2.resize(img_for_drawing, (img_for_drawing.shape[1], img_for_drawing.shape[0]))
    cv2_to_pil(resized_img).show()

style_types = [
    "Bleed",
    "Blunt",
    "Burn",
    "Charge",
    "Keywordless",
    "Pierce",
    "Poise",
    "Rupture",
    "Sinking",
    "Slash",
    "Tremor"
]

def gift_compendium_named_contour_detection(img):
    """
    使用轮廓检测来自动定位图标，然后通过点击和OCR获取图标名称并以此命名保存。
    """
    img = pil_to_cv2(img)
    img_for_drawing = img.copy()

    # ---- 图像预处理 ----
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 120, 290)  # burns-blunt
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

    # ---- 查找轮廓 ----
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # ---- 创建输出目录 ----
    output_dir = "ego_gifts"
    os.makedirs(output_dir, exist_ok=True)
    print("正在使用带命名的轮廓检测法切割图标...")

    # ---- 筛选满足条件的轮廓 ----
    valid_boxes = []  # (x, y, w, h, center_y)

    for contour in contours:
        area = cv2.contourArea(contour)
        if 3000 < area < 6000:
            x, y, w, h = cv2.boundingRect(contour)
            if w > 100 or h > 100:
                continue
            aspect_ratio = w / h
            if 0.9 < aspect_ratio < 1.1:
                center_y = y + h / 2
                valid_boxes.append([x, y, w, h, center_y])

    # --------------------------------------------------------
    #  ⭐ 对近似同一行的 y 归一化
    # --------------------------------------------------------

    if not valid_boxes:
        print("未检测到图标！")
        return

    # 先按 center_y 排序
    valid_boxes.sort(key=lambda b: b[4])

    merged_rows = []   # 每个 row = [box1, box2, ...]
    row_threshold = 12  # y 差多少算同一行（可调）

    for box in valid_boxes:
        x, y, w, h, cy = box

        if not merged_rows:
            merged_rows.append([box])
        else:
            # 比较当前盒与上一行最后一个盒的 y 距离
            last_cy = merged_rows[-1][-1][4]
            if abs(cy - last_cy) <= row_threshold:
                merged_rows[-1].append(box)
            else:
                merged_rows.append([box])

    # 每行的 y 均值对齐（使排序稳定）
    normalized_boxes = []
    for row in merged_rows:
        avg_y = int(np.mean([b[1] for b in row]))  # 使用原始 y 的均值
        for b in row:
            x, y, w, h, cy = b
            normalized_boxes.append((x, avg_y, w, h))

    # --------------------------------------------------------
    # ⭐ 最终排序：先 y（行），再 x（列）
    # --------------------------------------------------------
    normalized_boxes.sort(key=lambda b: (b[1], b[0]))

    # ---- 点击、识别和保存 ----
    saved_count = 0
    skipped_count = 0
    print(f"find {len(normalized_boxes)} box")
    for i, (x, y, w, h) in enumerate(normalized_boxes):
        try:
            # 计算中心点
            center_x = x + w // 2
            center_y = y + h // 2
            
            # 点击图标中心
            input_handler.click(center_x, center_y)
            
            # 等待界面响应
            import time
            time.sleep(0.2)
            
            # 截图并识别图标名称
            screenshot = input_handler.capture_screenshot(reset=False)
            
            # 使用OCR识别图标名称 (假设名称在图标附近的一个区域内)
            name_region = [280, 150, 300, 130]
            ocr_results = recognize_handler.detect_text_in_image(screenshot, mask=name_region)
            
            if ocr_results and len(ocr_results) > 0:
                # 取置信度最高的结果作为名称
                icon_name = ocr_results[0][0]
                
                # 清理文件名，移除非法字符
                # icon_name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', icon_name)
                
                # 如果名称为空或者太短，使用默认名称
                # if not icon_name or len(icon_name.strip()) < 1:
                #     icon_name = f"unnamed_icon_{i}"
                
                icon_name = icon_name.strip()
                icon_name = icon_name.replace(":", " ")

                if icon_name == "???":
                    print("未解锁， 跳过")
                    continue
                
                # 切割图标
                icon_roi = img[y+5:y + h-5, x+5:x + w-5]
                
                # 确定保存路径 - 根据图标样式类型分类保存
                final_output_dir = output_dir
                recognized_style = None
                for style in style_types:
                    # 尝试通过图像识别确认图标类型
                    try:
                        if len(recognize_handler.template_match(screenshot, f"enhance_icon_{style}", mask=[250, 290, 60, 60])) > 0:
                            final_output_dir = os.path.join(output_dir, style)
                            recognized_style = style
                            break
                    except Exception:
                        # 如果找不到对应的图标模板，继续检查下一个
                        pass
                
                # 创建对应样式的子目录
                os.makedirs(final_output_dir, exist_ok=True)
                
                # 保存图标，使用识别出的名称
                icon_filename = os.path.join(final_output_dir, f"{icon_name}.png")
                
                # 如果文件已存在，就跳过
                if os.path.exists(icon_filename):
                    print(f"文件 {icon_name}.png 已存在，跳过...")
                    skipped_count += 1
                    # input_handler.click(center_x, center_y)
                    # time.sleep(0.5)
                    continue
                
                cv2.imwrite(icon_filename, icon_roi)
                saved_count += 1
                if recognized_style:
                    print(f"保存图标: {icon_name} 到 {recognized_style} 类别")
                else:
                    print(f"保存图标: {icon_name}")
            else:
                # 如果没有识别到名称，使用默认名称
                icon_roi = img[y+5:y + h-5, x+5:x + w-5]
                icon_filename = os.path.join(output_dir, f"unnamed_icon_{i}.png")
                
                # 如果文件已存在，就跳过
                if os.path.exists(icon_filename):
                    print(f"文件 unnamed_icon_{i}.png 已存在，跳过...")
                    skipped_count += 1
                    continue
                    
                cv2.imwrite(icon_filename, icon_roi)
                saved_count += 1
                print(f"保存未命名图标: unnamed_icon_{i}")
            
            # 在原图上绘制矩形框
            cv2.rectangle(img_for_drawing, (x, y), (x + w, y + h), (0, 255, 0), 2)
            # 恢复每点击的情形
            # input_handler.click(center_x, center_y)
            # time.sleep(0.2)
        except Exception as e:
            print(f"处理第 {i} 个图标时出错: {str(e)}")
            continue

    print(f"命名切割完成！共保存 {saved_count} 个图标，跳过 {skipped_count} 个已存在的图标。")

    # ---- 显示结果 ----
    resized_img = cv2.resize(img_for_drawing, (img_for_drawing.shape[1], img_for_drawing.shape[0]))
    cv2_to_pil(resized_img).show()



if __name__ == "__main__":
    input_handler.refresh_window_state()
    input_handler.set_window_size()
    # 使用你的图片路径
    from time import sleep
    # sleep(2)
    # contour_detection(input_handler.capture_screenshot(reset=False))

    # 对于点击后，可以获取文件名
    # gift_name = recognize_handler.detect_text_in_image(input_handler.capture_screenshot(), mask=[900, 200, 300, 45])[0][0]
    gift_compendium_named_contour_detection(input_handler.capture_screenshot())