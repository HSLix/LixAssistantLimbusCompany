import cv2
import numpy as np
import matplotlib.pyplot as plt

try:
    from recognize.utils import pil_to_cv2, mask_screenshot
    from recognize.img_registry import get_image, register_images_from_directory, get_images_by_tag
except ImportError:
    from utils import pil_to_cv2, mask_screenshot
    from img_registry import get_image, register_images_from_directory, get_images_by_tag


def run_match(img, template, threshold):
    """对某一scale执行一次匹配，返回所有得分大于阈值的匹配"""
    h, w = img.shape[:2]
    th, tw = template.shape[:2]

    # 不可匹配
    if h < th or w < tw:
        return []

    res = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
    loc = np.where(res >= threshold)
    
    matches = []
    for pt in zip(*loc[::-1]):  # 逆序转换为 (x, y)
        score = res[pt[1], pt[0]]
        cx = pt[0] + tw // 2
        cy = pt[1] + th // 2
        matches.append((cx, cy, score))  # 返回 (cx, cy, score)

    return matches


def pyramid_template_match(
        screenshot,
        template,
        threshold=0.7,
        visualize=False,
        grayscale=True,
    ):
    """
    金字塔快速缩放 → 固定尺度匹配（1.3, 1.0, 0.7）
    """
    screenshot = pil_to_cv2(screenshot, grayscale)
    template = pil_to_cv2(template, grayscale)

    # template = cv2.resize(template, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
    # screenshot = cv2.resize(screenshot, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
    
    clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
    screenshot = clahe.apply(screenshot)
    template = clahe.apply(template)

    # template = cv2.medianBlur(template, 5)
    # screenshot = cv2.medianBlur(screenshot, 5)

    template = cv2.GaussianBlur(template, (5, 5), 0)
    screenshot = cv2.GaussianBlur(screenshot, (5, 5), 0)

    # if grayscale:
    #     screenshot = cv2.equalizeHist(screenshot)
    #     template = cv2.equalizeHist(template)

    th, tw = template.shape[:2]

    # --- 固定金字塔测试的scale ---  
    pyramid_scales = list(np.arange(1.5, 0.5, -0.025))

    all_matches = []  # 用于存储所有匹配

    # ===========================
    #  第一阶段：金字塔粗匹配
    # ===========================
    for sc in pyramid_scales:
        new_h = int(screenshot.shape[0] * sc)
        new_w = int(screenshot.shape[1] * sc)

        if new_h < th or new_w < tw:
            continue

        resized = cv2.resize(screenshot, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        # 使用阈值调整
        matches = run_match(resized, template, max(threshold - 0.0, 0))
        if matches:
            # 这里将匹配结果的坐标还原到原始截图的大小
            for cx, cy, score in matches:
                original_x = int(cx / sc)
                original_y = int(cy / sc)
                # 将匹配到的缩放倍率一起记录
                all_matches.append((original_x, original_y, score, sc))  # 添加缩放倍率

    if not all_matches:
        return []  # 没有找到任何匹配
    
    # 去重与排序
    refined_matches = _merge_close_matches(all_matches)


    # threshold_offset = 0.2
    # if refined_matches[0][3] < threshold + threshold_offset:
    #     # ===========================
    #     #  第二阶段：动态细分查找
    #     # ===========================
    #     # 初始步长
    #     step_size = 0.1

    #     while step_size > 0.01:  # 步长小于0.02时结束

    #         # 对所有匹配进行细化
    #         for i in range(len(refined_matches)):
    #             cx, cy, score, sc = refined_matches[i]

    #             best_match = (cx, cy, score, sc)  # 初始化当前匹配为最优匹配

    #             # 对每个匹配，尝试 `sc-0.1`, `sc`, `sc+0.1` 来细化
    #             for delta in [-step_size, 0, step_size]:
    #                 new_sc = sc + delta
    #                 resized = cv2.resize(screenshot, 
    #                                     (int(screenshot.shape[1] * new_sc), int(screenshot.shape[0] * new_sc)),
    #                                     interpolation=cv2.INTER_LINEAR)
    #                 matches = run_match(resized, template, threshold)

    #                 if matches:
    #                     # 比较当前匹配和新的匹配，取分数最好的
    #                     for new_cx, new_cy, new_score in matches:
    #                         if new_score > best_match[2]:
    #                             best_match = (new_cx / new_sc, new_cy / new_sc, new_score, new_sc)

    #             # 如果新的分数比阈值高偏差，则终止循环
    #             if best_match[2] > threshold + threshold_offset:
    #                 break  # 终止细化循环

    #             # 更新原始匹配的得分和缩放倍率
    #             refined_matches[i] = best_match

    #         # 如果已经终止循环，跳出外部的 while 循环
    #         if best_match[2] > threshold + threshold_offset:
    #             break

    #         # 步长减半，直到小于0.02
    #         step_size = max(step_size / 2, 0.01)


    #     # 按得分从高到低排序
    #     refined_matches.sort(key=lambda x: x[2], reverse=True)

    # ===========================
    # 可视化结果
    # ===========================
    if visualize and refined_matches:
        vis = screenshot.copy()  # 创建一个副本，防止直接修改原图

        for (cx, cy, score, sc) in refined_matches:
            # 计算矩形的左上角 (tl) 和右下角 (br)
            tl = (int(cx - tw / 2), int(cy - th / 2))
            br = (int(cx + tw / 2), int(cy + th / 2))

            # 绘制矩形框
            cv2.rectangle(vis, tl, br, (0, 255, 255), 2)

            # 在矩形框上方绘制分数和缩放倍数
            cv2.putText(vis, f"{score:.2f} (Scale: {sc:.2f})", (tl[0], tl[1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (128, 128, 128), 2)

        # 使用 Matplotlib 显示结果，包括源图像和模板图像
        fig, axes = plt.subplots(1, 2, figsize=(15, 6))
        
        # 显示源图像
        if grayscale:
            axes[0].imshow(vis, cmap="gray")
        else:
            axes[0].imshow(cv2.cvtColor(vis, cv2.COLOR_BGR2RGB))
        axes[0].set_title("Source Image with Matches")
        axes[0].axis("off")
        
        # 显示模板图像
        if grayscale:
            axes[1].imshow(template, cmap="gray")
        else:
            axes[1].imshow(cv2.cvtColor(template, cv2.COLOR_BGR2RGB))
        axes[1].set_title("Template Image")
        axes[1].axis("off")
        
        plt.tight_layout()
        plt.show()
    elif visualize and not refined_matches:
        # 即使没有匹配结果也显示图像以便调试
        fig, axes = plt.subplots(1, 2, figsize=(15, 6))
        
        # 显示源图像
        if grayscale:
            axes[0].imshow(screenshot, cmap="gray")
        else:
            axes[0].imshow(cv2.cvtColor(screenshot, cv2.COLOR_BGR2RGB))
        axes[0].set_title("Source Image (No Matches Found)")
        axes[0].axis("off")
        
        # 显示模板图像
        if grayscale:
            axes[1].imshow(template, cmap="gray")
        else:
            axes[1].imshow(cv2.cvtColor(template, cv2.COLOR_BGR2RGB))
        axes[1].set_title("Template Image")
        axes[1].axis("off")
        
        plt.tight_layout()
        plt.show()

    # 返回按得分排序的匹配结果
    return refined_matches


def _merge_close_matches(matches, distance_threshold=20):
    """
    合并中心坐标相近的匹配结果
    :param matches: 匹配结果列表
    :param distance_threshold: 距离阈值
    :return: 合并后的匹配结果列表
    """
    # 按匹配分数从高到低排序
    sorted_matches = sorted(matches, key=lambda x: x[2], reverse=True)
    
    # 合并中心坐标相近的匹配结果
    merged_matches = []
    for match in sorted_matches:
        center_x, center_y, score, sc = match
        merged = False
        
        # 检查是否与已合并的匹配结果相近
        for i, merged_match in enumerate(merged_matches):
            merged_x, merged_y, merged_score, _ = merged_match
            # 如果中心坐标相差不到distance_threshold，则认为是同一个目标
            if abs(center_x - merged_x) < distance_threshold and abs(center_y - merged_y) < distance_threshold:
                # 保留分数较高的匹配
                if score > merged_score:
                    merged_matches[i] = (center_x, center_y, score, sc)
                merged = True
                break
        
        # 如果没有相近的匹配结果，则添加为新的匹配
        if not merged:
            merged_matches.append(match)
    
    return merged_matches


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
    register_images_from_directory()
    # tmp_screenshot = mask_screenshot(input_handler.capture_screenshot(), 530, 200, 630, 350)
    # all_ego_gifts = get_images_by_tag("ego_gifts_Bleed")
    # for gift_name, gift_img in all_ego_gifts:
    #     # print(gift_name)
    #     res = pyramid_template_match(tmp_screenshot, gift_img, visualize=True, threshold=0.7)
    #     if len(res) > 0:
    #         print(f"find：{gift_name}")
    #         print(res)
            

    print(pyramid_template_match(get_image("TURAS"), get_image("Vain Pride"), threshold=0.7))

    # 加载测试图像
    try:
        templates = []
        screenshot = input_handler.capture_screenshot()
        screenshot = mask_screenshot(screenshot, 590, 180, 560, 350)
        # templates.append(get_image("Wound Clerid"))
        # templates.append(get_image("Millarca"))
        # templates.append(get_image("Respite"))
        # templates.append(get_image("Rusted Muzzle"))
        # templates.append(get_image("main_drive_with_text"))
        

        # templates.append(get_image("Bell of Truth"))
        templates.append(get_image("Rest"))
        # templates.append(get_image("Millarca"))
        # templates.append(get_image("WB Flask"))
        # templates.append(get_image("Little and To-be-Naughty Plushie"))
        # templates.append(get_image("Grimy Iron Stake"))
        # templates.append(get_image("Sanguine Fragrance Descends"))
        

        # templates.append(get_image("Lightning Axe"))
        # templates.append(get_image("Entanglement Override Sequencer"))
        # templates.append(get_image("Bloodflame Sword"))
        # templates.append(get_image("Rusted Clock Hands"))
        


        # templates.append(get_image("node_regular_encounter"))
        # templates.append(get_image("node_event"))
        # templates.append(get_image("node_elite_encounter"))
        # templates.append(get_image("node_focused_encounter"))
        # templates.append(get_image("node_shop"))
        # templates.append(get_image("node_boss_encounter"))
        # templates.append(get_image("train_head"))
        print("已加载测试图像和模板图像")
    except Exception as e:
        print(f"加载图像时出错: {e}")
        exit(1)
    
    # 测试模板匹配
    print("\n1. 测试模板匹配 (默认阈值):")
    import time
    try:
        for template in templates:
            # matches = template_match(screenshot, template, visualize=True, threshold=0.2, grayscale=False)
            # start = time.time()
            # screenshot = mask_screenshot(screenshot, 600, 40, 200, 580)
            # screenshot = mask_screenshot(screenshot, 380, 40, 420, 580)
            matches = pyramid_template_match(screenshot, template, visualize=True, threshold=0.7)
            # print(f"使用了 {time.time()-start} 秒")
            print(f"   找到 {len(matches)} 个匹配")
            input_handler.set_background_state()
            for i, match in enumerate(matches):
                print(f"   匹配 {i+1}: 中心坐标({match[0]}, {match[1]}), 匹配分数: {match[2]:.4f}")
                print(match)
                # con.click(match[0], match[1])
                # time.sleep(3)
                # if i == 6:
                #     break
            # print(f"used time:{time.time()-start}")
    except Exception as e:
        print(f"   模板匹配出错: {e}")
    
    
    print("\nTemplate Match模块测试完成")