"""只读 SIFT 多实例检测；所有预处理均从原像素生成，返回原图坐标。"""

import math

import cv2
import numpy as np

from .recognition import checked_region


def prepare_image(image, *, grayscale=True, scale=3, clahe=True):
    """生成独立处理图；彩色增强只作用于亮度，SIFT 最终仍提取灰度特征。"""
    working = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if grayscale else image.copy()
    if scale != 1:
        working = cv2.resize(working, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
    if clahe:
        enhancer = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
        if grayscale:
            working = enhancer.apply(working)
        else:
            lab = cv2.cvtColor(working, cv2.COLOR_BGR2LAB)
            lab[:, :, 0] = enhancer.apply(lab[:, :, 0])
            working = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    return working if grayscale else cv2.cvtColor(working, cv2.COLOR_BGR2GRAY)


def unique_pairs(matches, source, target):
    """同一位置的多方向关键点不重复贡献内点证据。"""
    kept, used_source, used_target = [], set(), set()
    for match in sorted(matches, key=lambda m: (m.distance, m.queryIdx, m.trainIdx)):
        a = tuple(round(v, 2) for v in source[match.trainIdx].pt)
        b = tuple(round(v, 2) for v in target[match.queryIdx].pt)
        if a not in used_source and b not in used_target:
            kept.append(match)
            used_source.add(a)
            used_target.add(b)
    return kept


def candidate_group(matches, source, target, shape):
    """用特征尺度和方向预测目标中心，避免全屏噪声淹没小目标的几何模型。"""
    cells = {}
    cell_size = max(shape) / 2
    center = np.array([shape[1], shape[0]]) / 2
    for match in matches:
        a, b = source[match.trainIdx], target[match.queryIdx]
        angle = math.radians(b.angle - a.angle)
        rotation = np.array([[math.cos(angle), -math.sin(angle)],
                             [math.sin(angle), math.cos(angle)]])
        prediction = np.array(b.pt) + rotation @ (center - a.pt) * (b.size / a.size)
        key = tuple(np.floor(prediction / cell_size).astype(int))
        cells.setdefault(key, []).append(match)
    best = []
    for cx, cy in sorted(cells):
        group = [m for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                 for m in cells.get((cx + dx, cy + dy), [])]
        if len(group) > len(best):
            best = group
    return best


def projection_metrics(polygon, source_points, target_points, shape):
    """衡量证据覆盖及投影角点处的缩放／拉伸，不依赖业务布局。"""
    height, width = shape[:2]
    source_coverage = cv2.contourArea(cv2.convexHull(source_points)) / (width * height)
    target_coverage = cv2.contourArea(cv2.convexHull(target_points)) / cv2.contourArea(polygon)
    edges = np.roll(polygon, -1, axis=0) - polygon
    lengths = [width, height, width, height]
    scales, deformations = [], []
    for index in range(4):
        basis = np.column_stack((edges[index] / lengths[index],
                                 -edges[index - 1] / lengths[index - 1]))
        singular = np.linalg.svd(basis, compute_uv=False)
        scales.extend(singular)
        deformations.append(singular[0] / singular[1] if singular[1] > 0 else math.inf)
    return dict(template_coverage=float(source_coverage), target_coverage=float(target_coverage),
                min_scale=float(min(scales)), max_scale=float(max(scales)),
                deformation=float(max(deformations)))


def detect_features(image, template, *, region=None, grayscale=True, scale=3, clahe=True,
                    nfeatures=0, n_octave_layers=3, contrast_threshold=0.04,
                    edge_threshold=10.0, sigma=1.6, precise_upscale=False,
                    pair_ratio=0.75, ransac_threshold=4 / 3, min_inliers=6,
                    min_inlier_ratio=0.4, min_scale=0.5, max_scale=2.0,
                    max_deformation=2.0, min_coverage=0.1):
    """反向配对后迭代提取多个几何模型；内点比例只统计当前候选范围。"""
    for value in (image, template):
        if value.dtype != np.uint8 or value.ndim != 3 or value.shape[2] != 3 or not value.size:
            raise ValueError("Feature detection requires non-empty uint8 BGR images.")
    for name, value in (("grayscale", grayscale), ("clahe", clahe), ("precise_upscale", precise_upscale)):
        if type(value) is not bool:
            raise ValueError(f"{name} must be bool.")
    for name, value, low, high in (("scale", scale, 1, 5), ("nfeatures", nfeatures, 0, 100000),
                                  ("n_octave_layers", n_octave_layers, 1, 10),
                                  ("min_inliers", min_inliers, 4, 100000)):
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"{name} must be an integer between {low} and {high}.")
    for name, value, high in (("contrast_threshold", contrast_threshold, 1),
                              ("edge_threshold", edge_threshold, 100), ("sigma", sigma, 10),
                              ("pair_ratio", pair_ratio, 1), ("ransac_threshold", ransac_threshold, 100),
                              ("min_inlier_ratio", min_inlier_ratio, 1)):
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= high:
            raise ValueError(f"{name} must be finite, positive and no greater than {high}.")
    if pair_ratio == 1:
        raise ValueError("pair_ratio must be less than 1.")
    for name, value, low, high in (("min_scale", min_scale, .001, 100),
                                   ("max_scale", max_scale, .001, 100),
                                   ("max_deformation", max_deformation, 1, 100),
                                   ("min_coverage", min_coverage, 0, 1)):
        if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f"{name} must be finite and between {low} and {high}.")
    if min_scale > max_scale:
        raise ValueError("min_scale must not exceed max_scale.")
    area = checked_region(region, image.shape[1], image.shape[0])
    x, y, width, height = (area[k] for k in ("x", "y", "width", "height"))
    options = dict(grayscale=grayscale, scale=scale, clahe=clahe)
    scene = prepare_image(image[y:y + height, x:x + width], **options)
    pattern = prepare_image(template, **options)
    sift = cv2.SIFT_create(nfeatures=nfeatures, nOctaveLayers=n_octave_layers,
                           contrastThreshold=contrast_threshold, edgeThreshold=edge_threshold,
                           sigma=sigma, enable_precise_upscale=precise_upscale)
    source_kp, source_des = sift.detectAndCompute(pattern, None)
    target_kp, target_des = sift.detectAndCompute(scene, None)
    if source_des is None or target_des is None or len(source_des) < 2:
        return []
    # 截图向模板配对，允许多个实例各自匹配同一个模板特征。
    pairs = cv2.BFMatcher(cv2.NORM_L2).knnMatch(target_des, source_des, k=2)
    remaining = [p[0] for p in pairs if len(p) == 2 and p[0].distance < pair_ratio * p[1].distance]
    all_pairs = remaining.copy()
    corners = np.float32([[0, 0], [pattern.shape[1], 0],
                          [pattern.shape[1], pattern.shape[0]], [0, pattern.shape[0]]])
    output = []
    while len(remaining) >= 4:
        group = candidate_group(remaining, source_kp, target_kp, pattern.shape)
        if len(group) < 4:
            break
        source = np.float32([source_kp[m.trainIdx].pt for m in group])
        target = np.float32([target_kp[m.queryIdx].pt for m in group])
        homography, mask = cv2.findHomography(source, target, cv2.RANSAC,
                                             ransac_threshold * scale, maxIters=5000)
        if homography is None or mask is None or not mask.any():
            discarded = {m.queryIdx for m in group}
            remaining = [m for m in remaining if m.queryIdx not in discarded]
            continue
        inlier_mask = mask.ravel().astype(bool)
        # 无论候选是否通过都移除本模型内点，确保退化模型不会阻塞后续实例。
        model_pairs = [m for m, keep in zip(group, inlier_mask) if keep]
        discarded = {m.queryIdx for m in model_pairs}
        remaining = [m for m in remaining if m.queryIdx not in discarded]
        denominators = np.column_stack((corners, np.ones(4))) @ homography[2]
        if not (np.all(denominators > 0) or np.all(denominators < 0)):
            continue
        polygon = cv2.perspectiveTransform(corners.reshape(-1, 1, 2), homography).reshape(-1, 2)
        if not np.isfinite(polygon).all() or not cv2.isContourConvex(polygon):
            continue
        if cv2.contourArea(polygon, oriented=True) <= scale * scale:
            continue
        tolerance = ransac_threshold * scale
        if (polygon.min(axis=0) < -tolerance).any() or (
                polygon.max(axis=0) > np.array([scene.shape[1], scene.shape[0]]) + tolerance).any():
            continue
        local = [m for m in all_pairs
                 if cv2.pointPolygonTest(polygon, target_kp[m.queryIdx].pt, False) >= 0]
        # 分母保留冲突的模板配对，但同一截图位置只计一次。
        local_positions = {tuple(round(v, 2) for v in target_kp[m.queryIdx].pt) for m in local}
        inliers = unique_pairs(model_pairs, source_kp, target_kp)
        inliers = [m for m in inliers if cv2.pointPolygonTest(polygon, target_kp[m.queryIdx].pt, False) >= 0]
        count = len(inliers)
        ratio = count / len(local_positions) if local_positions else 0.0
        if count < min_inliers or ratio < min_inlier_ratio:
            continue
        metrics = projection_metrics(polygon,
            np.float32([source_kp[m.trainIdx].pt for m in inliers]),
            np.float32([target_kp[m.queryIdx].pt for m in inliers]), pattern.shape)
        if (metrics["min_scale"] < min_scale or metrics["max_scale"] > max_scale
                or metrics["deformation"] > max_deformation
                or min(metrics["template_coverage"], metrics["target_coverage"]) < min_coverage):
            continue
        # 只在接受后消除目标范围内残余配对，拒绝的投影不能吞掉其他真实目标。
        remaining = [m for m in remaining if cv2.pointPolygonTest(polygon, target_kp[m.queryIdx].pt, False) < 0]
        low = np.maximum(0, np.floor(polygon.min(axis=0) / scale + 1e-3)).astype(int)
        high = np.minimum([width, height], np.ceil(polygon.max(axis=0) / scale - 1e-3)).astype(int)
        if (high <= low).any():
            continue
        left, top = int(low[0]) + x, int(low[1]) + y
        w, h = (int(v) for v in high - low)
        output.append(dict(x=left, y=top, width=w, height=h, score=count,
                           inliers=count, inlier_ratio=ratio, good_matches=len(local_positions),
                           centerxy=(left + w // 2, top + h // 2), **metrics))
    output.sort(key=lambda m: (-m["score"], m["y"], m["x"]))
    return output
