import cv2
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt

try:
    from recognize.utils import pil_to_cv2, mask_screenshot
    from recognize.img_registry import get_image, register_images_from_directory, get_images_by_tag
except ImportError:
    from utils import pil_to_cv2, mask_screenshot
    from img_registry import get_image, register_images_from_directory, get_images_by_tag

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
        center_x, center_y, score = match
        merged = False
        
        # 检查是否与已合并的匹配结果相近
        for i, merged_match in enumerate(merged_matches):
            merged_x, merged_y, merged_score = merged_match
            # 如果中心坐标相差不到distance_threshold，则认为是同一个目标
            if abs(center_x - merged_x) < distance_threshold and abs(center_y - merged_y) < distance_threshold:
                # 保留分数较高的匹配
                if score > merged_score:
                    merged_matches[i] = (center_x, center_y, score)
                merged = True
                break
        
        # 如果没有相近的匹配结果，则添加为新的匹配
        if not merged:
            merged_matches.append(match)
    
    return merged_matches


def feature_match(screenshot, template, threshold=0.75, visualize=False, min_matches=8):
    # 将 PIL 图像转换为 OpenCV 格式（灰度）
    screenshot_gray = pil_to_cv2(screenshot, grayscale=True)
    template_gray = pil_to_cv2(template, grayscale=True)

    template_gray = cv2.resize(template_gray, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
    screenshot_gray = cv2.resize(screenshot_gray, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
    

    # 创建 ORB 特征检测器
    orb = cv2.ORB_create(nfeatures=1000, scaleFactor=1.2, edgeThreshold=20)

    # 检测关键点和描述符
    kp1, des1 = orb.detectAndCompute(template_gray, None)
    kp2, des2 = orb.detectAndCompute(screenshot_gray, None)

    # 使用 FLANN 匹配器
    FLANN_INDEX_LSH = 6
    index_params = dict(algorithm=FLANN_INDEX_LSH, table_number=6, key_size=12, multi_probe_level=1)
    search_params = dict(checks=50)
    flann = cv2.FlannBasedMatcher(index_params, search_params)

    # KNN 匹配
    matches = flann.knnMatch(des1, des2, k=2)

    # 比率测试（Lowe's ratio test）
    good_matches = []
    for match in matches:
        if len(match) >= 2:
            m, n = match
            if m.distance < threshold * n.distance:
                good_matches.append(m)

    # 如果匹配点数量不足，返回空结果
    if len(good_matches) < min_matches:
        return []

    # 获取匹配点的坐标
    matched_points = []
    for match in good_matches:
        pt_template = kp1[match.queryIdx].pt
        pt_screenshot = kp2[match.trainIdx].pt
        matched_points.append(pt_screenshot)

    # 如果需要可视化结果
    if visualize:
        # 绘制匹配的关键点
        result_img = cv2.drawMatches(template_gray, kp1, screenshot_gray, kp2, good_matches, None, flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)

        # 在结果图像中绘制模板图像和目标图像的匹配点
        for match in good_matches:
            pt_template = tuple(map(int, kp1[match.queryIdx].pt))
            cv2.circle(result_img, pt_template, 5, (0, 0, 255), -1)  # 红色圆点

            pt_screenshot = tuple(map(int, kp2[match.trainIdx].pt))
            cv2.circle(result_img, pt_screenshot, 5, (0, 255, 0), -1)  # 绿色圆点

        # 使用 Matplotlib 显示结果图像
        plt.imshow(result_img)
        plt.axis('off')  # 关闭坐标轴
        plt.show()

    # 计算匹配点的中心和评分
    match_results = []
    for pt in matched_points:
        center_x, center_y = int(pt[0]), int(pt[1])
        # 评分可以基于匹配点的距离
        score = 1 - good_matches[0].distance / max(1.0, matches[0][0].distance)
        match_results.append((center_x, center_y, score))

    return match_results


# def feature_match(screenshot_pil, template_pil, visualize=False, grayscale=True, max_instances=5, threshold=0.7):
#     """
#     使用 ORB 进行多目标图标匹配
#     :param screenshot_pil: PIL 格式截图
#     :param template_pil: PIL 格式模板图
#     :param threshold 可信度阈值
#     :param visualize: 是否显示可视化结果（默认 False）
#     返回 [(center_x, center_y, score), ...]
#     """
#     # --- 转 OpenCV 格式 ---
#     screenshot = pil_to_cv2(screenshot_pil, grayscale)
#     template = pil_to_cv2(template_pil, grayscale)

#     # --- 增强 ---
#     # template = cv2.GaussianBlur(template, (3,3), 0)
#     # screenshot = cv2.GaussianBlur(screenshot, (3,3), 0)
#     # template = cv2.equalizeHist(template)
#     # screenshot = cv2.equalizeHist(screenshot)

#     # kernel = np.array([[0, -1, 0],
#     #                    [-1, 5,-1],
#     #                    [0, -1, 0]])

#     # template = cv2.filter2D(template, -1, kernel)
#     # screenshot = cv2.filter2D(screenshot, -1, kernel)

#     # --- ORB --- 
#     orb = cv2.ORB_create(
#         nfeatures=100,
#         scaleFactor=1.1,
#         edgeThreshold=2,
#         patchSize=15,
#         fastThreshold=20
#     )

#     kp_tmpl, des_tmpl = orb.detectAndCompute(template, None)
#     kp_scr, des_scr = orb.detectAndCompute(screenshot, None)

#     if des_tmpl is None or des_scr is None:
#         print("特征描述无效")
#         return []

#     bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

#     results = []
#     used_indices = set()
#     h, w = template.shape[:2]

#     for instance_id in range(max_instances):

#         matches = bf.match(des_tmpl, des_scr)

#         # 过滤掉已用特征点
#         matches = [m for m in matches if m.trainIdx not in used_indices]

#         if len(matches) < 6:
#             break

#         matches = sorted(matches, key=lambda x: x.distance)
#         matches_small = matches[:30]

#         if len(matches_small) < 6:
#             break

#         pts_t = np.float32([kp_tmpl[m.queryIdx].pt for m in matches_small])
#         pts_s = np.float32([kp_scr[m.trainIdx].pt for m in matches_small])

#         M, mask = cv2.estimateAffinePartial2D(
#             # pts_t, pts_s, method=cv2.RANSAC, ransacReprojThreshold=5
#             pts_t, pts_s, method=cv2.RANSAC, ransacReprojThreshold=5
#         )

#         if M is None:
#             break

#         mask = mask.reshape(-1)
#         inlier_matches = [matches_small[i] for i in range(len(matches_small)) if mask[i] == 1]

#         if len(inlier_matches) < 6:
#             break

#         corners = np.float32([[0,0], [w,0], [w,h], [0,h]]).reshape(-1,1,2)
#         pts_trans = cv2.transform(corners, M).reshape(-1,2)

#         cx = int(pts_trans[:,0].mean())
#         cy = int(pts_trans[:,1].mean())

#         # 置信度
#         distances = [m.distance for m in inlier_matches]
#         score_raw = float(np.mean(distances))
#         score = 1 - min(score_raw / 100, 1)

#         # ⭐ 加入 score 过滤（threshold）
#         if score >= threshold:
#             results.append((cx, cy, score))

#         # 非极大抑制：剔除用过的点
#         for m in inlier_matches:
#             used_indices.add(m.trainIdx)

#     # 合并中心坐标相近的匹配结果（横纵坐标相差不到20的）
#     results = _merge_close_matches(results, 20)

#     # --- 可视化 --- 
#     if visualize:
#         # 可视化截图图像
#         vis_scr = cv2.cvtColor(screenshot, cv2.COLOR_GRAY2BGR)
#         for cx, cy, sc in results:
#             cv2.circle(vis_scr, (cx, cy), 1, (0,255,255), 2)
#             cv2.putText(vis_scr, f"{sc:.2f}", (cx+10, cy-10),
#                         cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)

#         # 可视化模板图像
#         vis_tmpl = cv2.cvtColor(template, cv2.COLOR_GRAY2BGR)
#         for kp in kp_tmpl:
#             cv2.circle(vis_tmpl, tuple(np.int32(kp.pt)), 1, (0,255,255), 2)

#         # 展示截图与模板特征点
#         fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

#         # 展示截图图像和匹配的特征点
#         ax1.imshow(cv2.cvtColor(vis_scr, cv2.COLOR_BGR2RGB))
#         ax1.set_title("Screenshot with Feature Points")
#         ax1.axis("off")

#         # 展示模板图像和特征点
#         ax2.imshow(cv2.cvtColor(vis_tmpl, cv2.COLOR_BGR2RGB))
#         ax2.set_title("Template with Feature Points")
#         ax2.axis("off")

#         plt.show()

#     return results



if __name__ == "__main__":
    print("=== Feature Match Module Test ===")
    # Fix the import issue by using absolute import instead of relative import
    import sys
    import os
    # Add the parent directory to sys.path to make imports work
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from input.input_handler import input_handler
    input_handler.refresh_window_state()
    
    # 加载测试图像
    try:
        templates = []
        screenshot = input_handler.capture_screenshot()
        # screenshot = mask_screenshot(screenshot, 70, 150, 1100, 400)
        register_images_from_directory()
        # for name, img in get_images_by_tag("theme_packs"):
        #     print(name)
        #     templates.append(img)
        templates.append(get_image("Wound Clerid"))
        templates.append(get_image("Millarca"))
        templates.append(get_image("Respite"))
        templates.append(get_image("Rusted Muzzle"))
        # templates.append(get_image("node_regular_encounter"))
        # templates.append(get_image("node_event"))
        print("已加载测试图像和模板图像")
    except Exception as e:
        print(f"加载图像时出错: {e}")
        exit(1)
    
    # 测试特征匹配
    print("\n1. 测试特征匹配 (默认阈值):")
    try:
        for template in templates:
            # matches = feature_match(mask_screenshot(screenshot, 650, 40, 160, 580), template, visualize=True, grayscale=True, threshold=0.7)
            matches = feature_match(screenshot, template, visualize=True, threshold=0.0)
            print(f"   找到 {len(matches)} 个匹配")
            input_handler.set_background_state()
            for i, match in enumerate(matches):
                print(f"   匹配 {i+1}: 中心坐标({match[0]}, {match[1]}), 匹配分数: {match[2]:.4f}")
                # con.click(match[0], match[1])
                # time.sleep(3)
                # if i == 6:
                #     break
    except Exception as e:
        print(f"   特征匹配出错: {e}")