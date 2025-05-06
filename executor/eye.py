# coding: utf-8
from cv2 import (imread, createCLAHE, IMREAD_GRAYSCALE, imshow, waitKey, destroyAllWindows,
                 matchTemplate, TM_CCOEFF_NORMED, minMaxLoc, rectangle, cvtColor, COLOR_GRAY2BGR,
                 absdiff, resize, COLOR_BGR2GRAY, COLOR_BGRA2BGR, polylines, circle, COLOR_RGBA2BGR,
                 COLOR_GRAY2BGRA)
# import numpy as np
from numpy import average, where, array, int32
from globals import TEMPLATE_DIR, ignoreScaleAndDpi
import os
from time import sleep
from copy import deepcopy
from re import sub

from globals import RESOURCE_DIR
from .logger import lalc_logger
from .screenshot import captureLimbusCompanyWindow
from rapidocr_onnxruntime import RapidOCR

eye = None

def get_eye():
    global eye
    if (eye is None):
        eye = EYE()
    return eye



class EYE:
    def __init__(self):
        # self.captureScreenShot()
        self.screenshot = imread(os.path.join(RESOURCE_DIR, "limbus_company_screenshot.png"))
        self.ocr = RapidOCR()
        self.ocr_dict = {}

    def captureScreenShot(self):
        self.screenshot = captureLimbusCompanyWindow(is_pic_gray = True)

    def getScreenShot(self, is_pic_grey = True):
        screenshot = deepcopy(self.screenshot)
        if not is_pic_grey and len(screenshot.shape) == 2:
            screenshot = cvtColor(screenshot, COLOR_GRAY2BGR)
        return screenshot


    @staticmethod
    def getGreyNormalizedPic(image=None, is_show_pic: bool = False):
        """图片预处理"""
        if image is None:
            print(f"文件 {image} 不存在。")
            raise FileNotFoundError(image)
        else:
            img = image
        
        clahe = createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        cl1 = clahe.apply(img)
        
        if is_show_pic:
            imshow('Equalized Image', cl1)
            waitKey(0)
            destroyAllWindows()
        
        return cl1

    @staticmethod
    def cropImg(screenshot_img, recognize_area):
        """按区域裁剪图片"""
        if (len(recognize_area) < 4):
            lalc_logger.log_task("ERROR", "cropImg", "FAILED", 
                                f"裁剪区域设置不足四个值: {recognize_area}")
            raise ValueError("限定区域的设置不足四个")
        if (recognize_area == [0, 0, 0, 0]):
            return screenshot_img
        left = recognize_area[0]
        top = recognize_area[1]
        width = recognize_area[2]
        height = recognize_area[3]
        
        img_height, img_width = screenshot_img.shape[:2]
        right = left + width
        bottom = top + height
        left = max(0, left)
        top = max(0, top)
        right = min(img_width, right)
        bottom = min(img_height, bottom)
        width = right - left
        height = bottom - top
        
        if width <= 0 or height <= 0:
            lalc_logger.log_task("ERROR", "cropImg", "FAILED", 
                                f"无效的裁剪区域: 原图尺寸 {img_width}x{img_height}, 裁剪区域 {left}, {top}, {width}, {height}")
            raise ValueError("无效的裁剪区域。")
        
        # 记录裁剪区域信息
        lalc_logger.log_task("DEBUG", "cropImg", "SUCCESS", 
                            f"裁剪区域: 原图尺寸 {img_width}x{img_height}, 裁剪区域 {left}, {top}, {width}, {height}")
        
        
        screenshot_img = screenshot_img[top:bottom, left:right]
        return screenshot_img





    def templateMatch(self, pic_path, threshold:int=0.7, recognize_area=[0, 0, 0, 0], is_show_result:bool=False):
        # 默认导向设置
        pic_path = os.path.join(TEMPLATE_DIR, pic_path)
        target = imread(pic_path, IMREAD_GRAYSCALE)
        target = EYE.getGreyNormalizedPic(target)
        if target is None:
            raise FileNotFoundError(pic_path)
        
        
        template = self.getScreenShot()

        if recognize_area != [0, 0, 0, 0]:
            template = EYE.cropImg(template, recognize_area)

        
        template = EYE.getGreyNormalizedPic(image=template)
        if template is None:
            return (None, None)
        
        h_target, w_target = target.shape[:2]
        h_template, w_template = template.shape[:2]
        
        if h_template < h_target or w_template < w_target:
            lalc_logger.log_task("ERROR", "templateMatch", "FAILED", 
                            f"模板匹配失败: 裁剪后的区域尺寸小于目标图像，无法匹配。目标图片：{pic_path}; 截图模板尺寸: {w_template}x{h_template}, 目标图片尺寸: {w_target}x{h_target}, 裁剪区域: {recognize_area}")
            raise ValueError("裁剪后的区域尺寸小于目标图像，无法匹配。")


        
        match = matchTemplate(template, target, TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = minMaxLoc(match)
        
        result = (None, None)
        if max_val >= threshold:
            x_center = max_loc[0] + w_target // 2 + recognize_area[0]
            y_center = max_loc[1] + h_target // 2 + recognize_area[1]
            center = [x_center, y_center]
            result = (center, max_val)
            lalc_logger.log_task("DEBUG", "templateMatch", "SUCCESS", 
                            f"模板匹配成功: 目标图片: {pic_path}, 匹配中心坐标: {center}, 匹配值: {max_val:.4f}, 目标匹配值: {threshold}, 裁剪区域: {recognize_area}")
            # 在模板图像绘制红框
            if is_show_result:
                # 将灰度图转为BGR用于显示颜色
                template_color = cvtColor(template, COLOR_GRAY2BGR)
                target_color = cvtColor(target, COLOR_GRAY2BGR)
                top_left = max_loc
                bottom_right = (top_left[0] + w_target, top_left[1] + h_target)
                rectangle(template_color, top_left, bottom_right, (0, 0, 255), 2)
                
        else:
            lalc_logger.log_task("DEBUG", "templateMatch", "FAILED", 
                            f"模板匹配失败: 目标图片 {pic_path}, 当前匹配值: {max_val:.4f}, 目标匹配值: {threshold}, 裁剪区域: {recognize_area}")

        if is_show_result:
            # 显示图像
            imshow("Target Image", target_color)
            imshow("Matched Area (Red Box)", template_color)
            waitKey(0)
            destroyAllWindows()
        
        return result


        
    @staticmethod
    def isPicDif(pic1, pic2, threshold=35):
        """
        比较两张图片的差异。
        确保两张图片的尺寸和通道数相等。
        """
        # 检查图片是否为 None
        if pic1 is None or pic2 is None:
            raise ValueError("isPicDif:pic1 or pic2 is None")

        # 确保两张图片的尺寸和通道数相等
        if pic1.shape != pic2.shape:
            # 调整 pic2 的尺寸和通道数以匹配 pic1
            if len(pic1.shape) == 2:  # 灰度图像
                pic2 = resize(pic2, (pic1.shape[1], pic1.shape[0]))
                if len(pic2.shape) != 2:
                    pic2 = cvtColor(pic2, COLOR_BGR2GRAY)
            else:  # 彩色图像
                pic2 = resize(pic2, (pic1.shape[1], pic1.shape[0]))
                if pic2.shape[2] != pic1.shape[2]:
                    if pic1.shape[2] == 3:  # pic1 是 3 通道
                        pic2 = cvtColor(pic2, COLOR_BGRA2BGR) if pic2.shape[2] == 4 else cvtColor(pic2, COLOR_GRAY2BGR)
                    elif pic1.shape[2] == 1:  # pic1 是单通道
                        pic2 = cvtColor(pic2, COLOR_BGR2GRAY)

        # 计算差异
        grey_diff = absdiff(pic1, pic2)
        diff = average(grey_diff)
        print(f"pic diff: {diff}")
        lalc_logger.log_task("DEBUG", "idPicDif", "DOING", "pic diff: %f" % (diff))
        
        # 判断差异是否小于阈值
        if diff <= threshold:
            return False
        return True


    def waitFreeze(self, freeze_time:int = 2):
        self.captureScreenShot()
        old_screenshot_img = self.getScreenShot()
        old_screenshot_img = EYE.getGreyNormalizedPic(old_screenshot_img)
        while True:
            sleep(freeze_time)
            self.captureScreenShot()
            new_screenshot_img = self.getScreenShot()
            new_screenshot_img = EYE.getGreyNormalizedPic(new_screenshot_img)
            if (not EYE.isPicDif(old_screenshot_img, new_screenshot_img)):
                break
            old_screenshot_img = new_screenshot_img



    def templateMultiMatch(self, pic_path, threshold=0.8, recognize_area=[0, 0, 0, 0], merge_distance=10, is_show_result=False):
        # 加载目标图像
        pic_path = os.path.join(TEMPLATE_DIR, pic_path)
        target = imread(pic_path, IMREAD_GRAYSCALE)
        target = EYE.getGreyNormalizedPic(target)
        if target is None:
            raise FileNotFoundError(pic_path)

        
        template = self.getScreenShot()
        template = EYE.getGreyNormalizedPic(template)

        
        # 裁剪到指定区域
        if recognize_area != [0, 0, 0, 0]:
            template = EYE.cropImg(template, recognize_area)
            
        
        if template is None:
            raise ValueError("templateMultiMatch teamplate is None")
            
        
        h_target, w_target = target.shape[:2]
        h_template, w_template = template.shape[:2]
        
        if h_template < h_target or w_template < w_target:

            raise ValueError("裁剪后的区域尺寸小于目标图像，无法匹配。")

        
        # 执行模板匹配
        match = matchTemplate(template, target, TM_CCOEFF_NORMED)
        
        # 获取所有超过阈值的匹配点坐标
        ys, xs = where(match >= threshold)
        scores = match[ys, xs]
        
        if len(xs) == 0:
            if is_show_result:
                template_color = cvtColor(template, COLOR_GRAY2BGR)
                target_color = cvtColor(target, COLOR_GRAY2BGR)
                imshow("Target Image", target_color)
                imshow("Matched Areas (Red Boxes)", template_color)
                waitKey(0)
                destroyAllWindows()
            return []
        
        # 转换为截图区域内的中心坐标
        points = []
        for x, y, score in zip(xs, ys, scores):
            center_x = x + w_target // 2
            center_y = y + h_target // 2
            points.append((center_x, center_y, score))
        
        # 按分数降序排序
        points.sort(key=lambda p: -p[2])
        
        # 合并相近的点
        selected = []
        processed = [False] * len(points)
        
        for i in range(len(points)):
            if not processed[i]:
                current = points[i]
                selected.append(current)
                current_x, current_y, _ = current
                for j in range(i + 1, len(points)):
                    if not processed[j]:
                        j_x, j_y, _ = points[j]
                        # 计算平方距离以优化性能
                        distance_sq = (current_x - j_x)**2 + (current_y - j_y)**2
                        if distance_sq <= merge_distance**2:
                            processed[j] = True
        
        # 转换为全局坐标
        global_points = []
        
        
        # 显示匹配结果
        if is_show_result:
            
            for (x, y, score) in selected:
                global_x = x + recognize_area[0]
                global_y = y + recognize_area[1]
                global_points.append([int(global_x), int(global_y), float(score)])

            template_color = cvtColor(template, COLOR_GRAY2BGR)
            target_color = cvtColor(target, COLOR_GRAY2BGR)
            
            # 绘制所有匹配区域的红框
            for (x_center, y_center, _) in selected:
                top_left_x = x_center - w_target // 2
                top_left_y = y_center - h_target // 2
                bottom_right_x = top_left_x + w_target
                bottom_right_y = top_left_y + h_target
                rectangle(template_color, (top_left_x, top_left_y), (bottom_right_x, bottom_right_y), (0, 0, 255), 2)
            
            imshow("Target Image", target_color)
            imshow("Matched Areas (Red Boxes)", template_color)
            waitKey(0)
            destroyAllWindows()
        else:
            for (x, y, score) in selected:
                global_x = x + recognize_area[0]
                global_y = y + recognize_area[1]
                global_points.append([int(global_x), int(global_y)])
        
        return global_points


    def templateMactchExist(self, pic_path, threshold:int=0.7, recognize_area=[0, 0, 0, 0], is_show_result:bool=False):
        center, score = self.templateMatch(pic_path, threshold, recognize_area, is_show_result)
        if (score == None):
            return False
        else:
            return True


    def screenshotOcr(self, recognize_area=[0, 0, 0, 0], is_show_result=False):
        self.ocr_dict = {}

        screenshot = self.getScreenShot()

        if recognize_area != [0, 0, 0, 0]:
            screenshot = EYE.cropImg(screenshot, recognize_area)
        screenshot = EYE.getGreyNormalizedPic(screenshot)

        result, _ = self.ocr(screenshot)
        if not result:
            lalc_logger.log_task("WARNING", "screenshotocr", "FAILED", "未识别到文字。")
            self.ocr_dict = {}
            return

        center_coordinates = []
        recognized_texts = []

        if is_show_result:
            for line in result:
                box = array(line[0], dtype=int32).reshape((-1, 1, 2))
                polylines(screenshot, [box], True, (0, 0, 255), 2)
                x_coords = [point[0] for point in line[0]]
                y_coords = [point[1] for point in line[0]]
                center_x = int(sum(x_coords) / len(x_coords) + recognize_area[0])
                center_y = int(sum(y_coords) / len(y_coords) + recognize_area[1])
                center_coordinates.append((center_x, center_y))
                recognized_texts.append(line[1])
        else:
            for line in result:
                x_coords = [point[0] for point in line[0]]
                y_coords = [point[1] for point in line[0]]
                center_x = int(sum(x_coords) / len(x_coords) + recognize_area[0])
                center_y = int(sum(y_coords) / len(y_coords) + recognize_area[1])
                center_coordinates.append((center_x, center_y))
                recognized_texts.append(line[1])

        if is_show_result:
            imshow('Text Recognition', screenshot)
            waitKey(0)
            destroyAllWindows()
       
        for center, text in zip(center_coordinates, recognized_texts):
            processed_text = self.process_text(text)
            self.ocr_dict[processed_text] = center

        # for key, value in self.ocr_dict.items():
        #     print("{0}:{1};".format(key, value))

        lalc_logger.log_task("DEBUG", "screenshotocr", "SUCCESS", f"识别到 {len(self.ocr_dict)} 个文字区域。\n识别到:{self.ocr_dict}")


    @staticmethod
    def process_text(text):
        text = sub(r'[^a-zA-Z0-9]', '', text)
        text = text.lower()
        return text

    def queryOcrDict(self, query_text):
        processed_query = self.process_text(query_text)
        for key, value in self.ocr_dict.items():
            if processed_query in key:
                lalc_logger.log_task("DEBUG", "query_ocr_dict", "SUCCESS", f"找到匹配项: {key}, 坐标: {value}")
                return value
        lalc_logger.log_task("DEBUG", "query_ocr_dict", "FAILED", f"未找到匹配项: {processed_query}")
        return None

    def ocrGetFirstNum(self):
        for key in self.ocr_dict.keys():
            if key.isdigit():
                num = float(key)
                lalc_logger.log_task("DEBUG", "ocrGetFirstNum", "SUCCESS", f"找到第一个数字: {num}")
                return num
        lalc_logger.log_task("WARNING", "ocrGetFirstNum", "FAILED", "未找到全是数字的字符串。")
        return 0
    
    def rgbDetection(self, coordinate: list, recognize_area=[0, 0, 0, 0], is_show_result=False):
        """
        对截图中指定坐标区域进行RGB检测
        :param coordinate: 要检测的坐标 [x, y]（相对于recognize_area的坐标）
        :param recognize_area: 裁剪区域 [x1, y1, x2, y2]
        :param is_show_result: 是否显示结果
        :return: 裁剪区域的RGB值,由于已经灰度了，所以给的其实是亮度
        """
        screenshot = self.getScreenShot(is_pic_grey=False)
        # screenshot = cvtColor(screenshot, COLOR_RGBA2BGR)
        screenshot = self.cropImg(screenshot, recognize_area)
        
        # 检查坐标是否在图像范围内
        height, width = screenshot.shape[:2]
        if coordinate[0] < 0 or coordinate[0] >= width or coordinate[1] < 0 or coordinate[1] >= height:
            raise ValueError(f"rgbDetection 坐标 {coordinate} 超出图像范围 ({width}x{height})")
        
        # 获取裁剪区域的RGB值
        b, g, r = screenshot[recognize_area[1] + coordinate[1], recognize_area[0] + coordinate[0]]
        
        if is_show_result:
            # 创建图像副本用于可视化
            vis_img = screenshot.copy()
            # 在坐标处画一个白底黑边的小点
            point = (recognize_area[0] + coordinate[0], recognize_area[1] + coordinate[1])
            circle(vis_img, point, 5, (0, 0, 0), 2)  # 黑色边框
            circle(vis_img, point, 3, (255, 255, 255), -1)  # 白色填充
            
            imshow('RGB Detection', vis_img)
            waitKey(0)
            destroyAllWindows()
        
        return b


if __name__ == "__main__":
    ignoreScaleAndDpi()
    eye = EYE()
    c = eye.templateMatch("mirror_init_teams.png", is_show_result=True, threshold=0)
    c = eye.templateMatch("mirror_init_teams.png", is_show_result=True, threshold=0)
    print(c)
    # getGreyNormalizedPic(SCREENSHOT_PATH)
    # center, num = templateMatch("reward_card_coin_ego.png", is_show_result=False)
    # print(center)
    # print(num)
    # center, num = templateMatch("reward_card_coin.png", is_show_result=False)
    # print(center)
    # print(num)
    # center, num = templateMatch("reward_card_ego_resource.png", is_show_result=False)
    # print(center)
    # print(num)
    # waitFreeze(1,is_show_sign=False)
    # center, num = templateMatch("shop_purchase_bleed.png", is_show_result=True, threshold=0)
    # print((center, num))
    # pic = eye.templateMultiMatch("1.png", is_show_result=True, threshold=0.7)
    # for single_pic in pic:
    #     print((single_pic[0], single_pic[1], single_pic[2]))


    