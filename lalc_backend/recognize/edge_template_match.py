import cv2
import numpy as np
import matplotlib.pyplot as plt
import time

try:
    from recognize.utils import pil_to_cv2, mask_screenshot
    from recognize.img_registry import get_image, register_images_from_directory
except ImportError:
    from utils import pil_to_cv2, mask_screenshot
    from img_registry import get_image, register_images_from_directory


import cv2
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image


# -------------------- 1. 权重图生成 --------------------
def make_weight_map(template_gray, mode='gradient', sigma=0.3):
    h, w = template_gray.shape
    if mode == 'gradient':
        gx = cv2.Sobel(template_gray, cv2.CV_32F, 1, 0)
        gy = cv2.Sobel(template_gray, cv2.CV_32F, 0, 1)
        mag = np.sqrt(gx * gx + gy * gy)
        weight = mag
    elif mode == 'rarity':
        hist = cv2.calcHist([template_gray], [0], None, [256], [0, 256])
        hist = hist.ravel() / hist.sum()
        rarity = 1.0 / (hist[template_gray] + 1e-6)
        weight = rarity.astype(np.float32)
    else:
        weight = np.ones((h, w), dtype=np.float32)
    if sigma > 0:
        weight = cv2.GaussianBlur(weight, (0, 0), sigma)
    weight /= weight.sum()  # Σ=1
    return weight


# -------------------- 2. 加权 NCC（积分图） --------------------
def weighted_ncc_match(scr_gray, tmp_gray, weight):
    h, w = scr_gray.shape
    ht, wt = tmp_gray.shape
    tmp_f = tmp_gray.astype(np.float32)
    w_tmp_mean = np.sum(weight * tmp_f)
    w_tmp_var = np.sum(weight * (tmp_f - w_tmp_mean) ** 2)

    int_I = cv2.integral(scr_gray.astype(np.float32))
    int_I2 = cv2.integral(scr_gray.astype(np.float32) ** 2)
    int_W = cv2.integral(weight)
    int_WI = cv2.integral(weight * scr_gray.astype(np.float32))

    res = np.zeros((h - ht + 1, w - wt + 1), dtype=np.float32)
    for y in range(res.shape[0]):
        for x in range(res.shape[1]):
            y1, x1, y2, x2 = y, x, y + ht, x + wt
            sum_w = int_W[y2, x2] - int_W[y1, x2] - int_W[y2, x1] + int_W[y1, x1]
            sum_wi = int_WI[y2, x2] - int_WI[y1, x2] - int_WI[y2, x1] + int_WI[y1, x1]
            if sum_w == 0:
                res[y, x] = 0.0
                continue
            mean_iw = sum_wi / sum_w
            sum_i2 = int_I2[y2, x2] - int_I2[y1, x2] - int_I2[y2, x1] + int_I2[y1, x1]
            sum_i = int_I[y2, x2] - int_I[y1, x2] - int_I[y2, x1] + int_I[y1, x1]
            var_i = (sum_w * sum_i2 - 2 * sum_i * sum_wi + sum_w * sum_i * mean_iw ** 2) / sum_w
            if var_i <= 0:
                res[y, x] = 0.0
                continue
            sum_cross = np.sum(weight * (scr_gray[y1:y2, x1:x2] - mean_iw) * (tmp_f - w_tmp_mean))
            res[y, x] = sum_cross / np.sqrt(var_i * w_tmp_var)
    return res


# -------------------- 3. 加权 SSD（可选） --------------------
def weighted_ssd_match(scr_gray, tmp_gray, weight):
    ht, wt = tmp_gray.shape
    tmp_f = tmp_gray.astype(np.float32)
    int_W = cv2.integral(weight)
    int_WI = cv2.integral(weight * scr_gray.astype(np.float32))
    int_WI2 = cv2.integral(weight * scr_gray.astype(np.float32) ** 2)
    int_tmp = cv2.integral(weight * tmp_f)
    int_cross = cv2.integral(weight * scr_gray.astype(np.float32) * tmp_f)

    res = np.zeros((scr_gray.shape[0] - ht + 1, scr_gray.shape[1] - wt + 1), dtype=np.float32)
    for y in range(res.shape[0]):
        for x in range(res.shape[1]):
            y1, x1, y2, x2 = y, x, y + ht, x + wt
            sum_w = int_W[y2, x2] - int_W[y1, x2] - int_W[y2, x1] + int_W[y1, x1]
            sum_wi2 = int_WI2[y2, x2] - int_WI2[y1, x2] - int_WI2[y2, x1] + int_WI2[y1, x1]
            sum_cross = int_cross[y2, x2] - int_cross[y1, x2] - int_cross[y2, x1] + int_cross[y1, x1]
            sum_tmp = int_tmp[y2, x2] - int_tmp[y1, x2] - int_tmp[y2, x1] + int_tmp[y1, x1]
            if sum_w == 0:
                res[y, x] = 0.
            else:
                ssd = (sum_wi2 - 2 * sum_cross + sum_tmp) / sum_w
                res[y, x] = ssd
    return res


# -------------------- 4. 主匹配函数 --------------------
def template_match(screenshot, template, threshold=0.7,
                   visualize=False, grayscale=False, screenshot_scale=1,
                   weighted_mode="ssd", weight_mode='gradient'):
    """
    模板匹配（原版 OR 加权 NCC/SSD）
    :param weighted_mode: None | 'ncc' | 'ssd'
    :param weight_mode: 'gradient' | 'rarity' | None
    :return: [(中心x, 中心y, 分数), ...]  分数∈[0,1] 越大越好
    """
    # ---- 1. 图像预处理 ----
    screenshot = np.array(screenshot) if isinstance(screenshot, Image.Image) else screenshot
    template = np.array(template) if isinstance(template, Image.Image) else template
    if screenshot_scale != 1:
        h, w = screenshot.shape[:2]
        screenshot = cv2.resize(screenshot, (int(w * screenshot_scale), int(h * screenshot_scale)),
                                interpolation=cv2.INTER_AREA)
    if template.shape[0] > screenshot.shape[0] or template.shape[1] > screenshot.shape[1]:
        return []

    # ---- 2. 选择基底 ----
    scr_base = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY) if len(screenshot.shape) == 3 else screenshot
    tmp_base = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY) if len(template.shape) == 3 else template

    # ---- 3. 计算响应图 ----
    if weighted_mode in ('ncc', 'ssd'):
        weight_map = make_weight_map(tmp_base, mode=weight_mode, sigma=0.3)
        if weighted_mode == 'ncc':
            result = weighted_ncc_match(scr_base, tmp_base, weight_map)
        else:
            result = weighted_ssd_match(scr_base, tmp_base, weight_map)
            # SSD 越小越好 → 转 [0,1] 大→好
            result = np.clip(1.0 - result / (result.max() + 1e-8), 0, 1)
    else:
        result = cv2.matchTemplate(scr_base, tmp_base, cv2.TM_CCOEFF_NORMED)

    # ---- 4. 提取候选 ----
    locations = np.where(result >= threshold)
    matches = []
    for pt in zip(*locations[::-1]):
        cx = pt[0] + tmp_base.shape[1] // 2
        cy = pt[1] + tmp_base.shape[0] // 2
        score = result[pt[1], pt[0]]
        cx_orig = int(cx / screenshot_scale)
        cy_orig = int(cy / screenshot_scale)
        matches.append((cx_orig, cy_orig, score))

    # ---- 5. 合并相近框 ----
    merged = []
    for (x, y, s) in matches:
        if any(abs(x - mx) < 20 and abs(y - my) < 20 for mx, my in merged):
            continue
        merged.append((x, y, s))
    matches = merged

    # ---- 6. 可视化 ----
    if visualize and matches:
        vis = screenshot.copy()
        th, tw = tmp_base.shape
        for (cx_orig, cy_orig, score) in matches:
            cx = int(cx_orig * screenshot_scale)
            cy = int(cy_orig * screenshot_scale)
            tl = (int(cx - tw // 2), int(cy - th // 2))
            br = (int(cx + tw // 2), int(cy + th // 2))
            cv2.rectangle(vis, tl, br, (0, 255, 0), 2)
            text = f"{score:.3f}" + (f" {weighted_mode.upper()}" if weighted_mode else "")
            cv2.putText(vis, text, (tl[0], tl[1] - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        plt.figure(figsize=(12, 6))
        if grayscale:
            plt.imshow(vis, cmap='gray')
        else:
            plt.imshow(cv2.cvtColor(vis, cv2.COLOR_BGR2RGB))
        plt.axis('off')
        plt.show()

    return matches



if __name__ == "__main__":
    
    # 独立测试template_match模块
    print("=== Template Match Module Test ===")
    # Fix the import issue by using absolute import instead of relative import
    import sys
    import os
    # Add the parent directory to sys.path to make imports work
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from input.input_handler import input_handler
    input_handler.refresh_window_state()
    input_handler.set_window_size()
    # 加载测试图像
    try:
        templates = []
        screenshot = input_handler.capture_screenshot()
        screenshot = mask_screenshot(screenshot, 590, 180, 560, 350)
        register_images_from_directory()
        # templates.append(get_image("Little and To-be-Naughty Plushie"))
        # templates.append(get_image(""))
      
        # templates.append(get_image("Bell of Truth"))
        # templates.append(get_image("Rest"))
        # templates.append(get_image("Millarca"))
        # templates.append(get_image("WB Flask"))
        # templates.append(get_image("Little and To-be-Naughty Plushie"))
        # templates.append(get_image("Grimy Iron Stake"))
        # templates.append(get_image("Sanguine Fragrance Descends"))
        

        templates.append(get_image("Lightning Axe"))
        templates.append(get_image("Entanglement Override Sequencer"))
        templates.append(get_image("Bloodflame Sword"))
        templates.append(get_image("Rusted Clock Hands"))
        
        # templates.append(get_image("node_regular_encounter"))
        # templates.append(get_image("node_event"))
        # templates.append(get_image("node_elite_encounter"))
        # templates.append(get_image("node_focused_encounter"))
        # templates.append(get_image("node_shop"))
        # templates.append(get_image("node_boss_encounter"))
        
        # print(template_match(get_image("Tearful Things"), get_image("Flat-broke Gamblers")))
        print("已加载测试图像和模板图像")
    except Exception as e:
        print(f"加载图像时出错: {e}")
        exit(1)
    
    # 测试模板匹配
    print("\n1. 测试模板匹配 (默认阈值):")
    try:
        for template in templates:
            # matches = template_match(screenshot, template, visualize=True, threshold=0.2, grayscale=False)
            start = time.time()
            matches = template_match(screenshot, template, visualize=True, threshold=0.5, screenshot_scale=0.93, grayscale=False)
            print(f"used time:{time.time()-start}")
            print(f"   找到 {len(matches)} 个匹配")
            input_handler.set_background_state()
            for i, match in enumerate(matches):
                print(f"   匹配 {i+1}: 中心坐标({match[0]}, {match[1]}), 匹配分数: {match[2]:.4f}")
                # con.click(match[0], match[1])
                # time.sleep(3)
                # if i == 6:
                #     break
    except Exception as e:
        print(f"   模板匹配出错: {e}")
    
    print("\nTemplate Match模块测试完成")