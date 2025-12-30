import cv2
import numpy as np
from PIL import Image


def pil_to_cv2(pil_image, grayscale=False):
    """
    将PIL图像转换为OpenCV格式
    :param pil_image: PIL图像对象
    :param grayscale: 是否转换为灰度图
    :return: OpenCV图像（numpy数组）
    """
    # 转换PIL图像为numpy数组
    img_np = np.array(pil_image)
    
    if grayscale:
        # 转换为灰度图
        if len(img_np.shape) == 3:
            img_cv2 = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        else:
            img_cv2 = img_np
    else:
        # RGB转BGR（OpenCV使用BGR）
        if len(img_np.shape) == 3:
            img_cv2 = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        else:
            img_cv2 = img_np
            
    return img_cv2


def cv2_to_pil(cv2_image, grayscale=False):
    """
    将OpenCV图像转换为PIL格式
    :param cv2_image: OpenCV图像（numpy数组）
    :param grayscale: 是否将图像转换为灰度图像，默认为False
    :return: PIL图像对象
    """
    # 如果是灰度图像，直接将图像转换为灰度
    if grayscale:
        pil_image = Image.fromarray(cv2_image, mode='L')  # 'L' 表示灰度模式
    else:
        # OpenCV 使用 BGR 色彩空间，PIL 使用 RGB，所以需要转换颜色通道
        pil_image = Image.fromarray(cv2_image[:, :, ::-1])  # BGR 转为 RGB
    
    return pil_image


def equalize_histogram(gray_image):
    """
    对灰度图进行直方图均衡化
    :param gray_image: 灰度图像（单通道OpenCV图像）
    :return: 直方图均衡化后的图像
    """
    # 检查图像是否为灰度图
    if len(gray_image.shape) != 2:
        raise ValueError("输入图像必须是灰度图（单通道图像）")
        
    # 应用直方图均衡化
    equalized_image = cv2.equalizeHist(gray_image)
    
    return equalized_image


def mask_screenshot(image: Image.Image, start_x, start_y, width, height):
    """
    对PIL图像进行裁剪，只返回指定区域的小图像。
    :param image: 输入的PIL图像
    :param start_x: 起始X坐标
    :param start_y: 起始Y坐标
    :param width: 截取宽度
    :param height: 截取高度
    :return: 裁剪后的PIL图像
    """
    image = image.copy()
    # 修正 start 坐标
    start_x = max(0, start_x)
    start_y = max(0, start_y)

    # 计算 end 坐标
    end_x = min(start_x + width, image.width)
    end_y = min(start_y + height, image.height)

    # 区域无效
    if end_x <= start_x or end_y <= start_y:
        raise Exception(
            "裁剪无效，获得数据：start:(%d, %d), end:(%d, %d), width:%d, height:%d" 
            % (start_x, start_y, end_x, end_y, width, height)
        )

    return image.crop((start_x, start_y, end_x, end_y))



def fill_mask_screenshot(image: Image.Image, start_x, start_y, width, height):
    """
    对PIL图像进行掩码截图，保留指定区域，其余区域变为黑色
    :param image: 输入的PIL图像
    :param start_x: 起始X坐标
    :param start_y: 起始Y坐标
    :param width: 截取宽度
    :param height: 截取高度
    :return: 掩码处理后的PIL图像
    """
    # 修正 start 坐标
    start_x = max(0, start_x)
    start_y = max(0, start_y)

    # 计算 end 坐标（基于修正后的 start）
    end_x = min(start_x + width, image.width)
    end_y = min(start_y + height, image.height)

    # 如果区域无效，返回全黑图像
    if end_x <= start_x or end_y <= start_y:
        raise Exception("裁剪无效，获得数据：start:(%d, %d), end:(%d, %d), width:%d, height:%d" % (start_x, start_y, end_x, end_y, width, height))

    image = image.copy()
    
    # 创建黑图
    black = Image.new(image.mode, image.size, 0)

    # 裁剪
    crop_region = image.crop((start_x, start_y, end_x, end_y))

    # 贴回黑图
    black.paste(crop_region, (start_x, start_y))

    return black


def erode_image(image, kernel_size=(3, 3), iterations=1):
    """
    对图像进行腐蚀操作
    :param image: 输入的OpenCV图像
    :param kernel_size: 卷积核大小，默认为(3, 3)
    :param iterations: 迭代次数，默认为1
    :return: 腐蚀后的图像
    """
    # 创建卷积核
    kernel = np.ones(kernel_size, np.uint8)
    
    # 应用腐蚀操作
    eroded_image = cv2.erode(image, kernel, iterations=iterations)
    
    return eroded_image


def dilate_image(image, kernel_size=(3, 3), iterations=1):
    """
    对图像进行膨胀操作
    :param image: 输入的OpenCV图像
    :param kernel_size: 卷积核大小，默认为(3, 3)
    :param iterations: 迭代次数，默认为1
    :return: 膨胀后的图像
    """
    # 创建卷积核
    kernel = np.ones(kernel_size, np.uint8)
    
    # 应用膨胀操作
    dilated_image = cv2.dilate(image, kernel, iterations=iterations)
    
    return dilated_image


def opening_operation(image, kernel_size=(3, 3), iterations=1):
    """
    对图像进行开运算（先腐蚀后膨胀）
    :param image: 输入的OpenCV图像
    :param kernel_size: 卷积核大小，默认为(3, 3)
    :param iterations: 迭代次数，默认为1
    :return: 开运算后的图像
    """
    # 创建卷积核
    kernel = np.ones(kernel_size, np.uint8)
    
    # 应用开运算
    opened_image = cv2.morphologyEx(image, cv2.MORPH_OPEN, kernel, iterations=iterations)
    
    return opened_image


def closing_operation(image, kernel_size=(3, 3), iterations=1):
    """
    对图像进行闭运算（先膨胀后腐蚀）
    :param image: 输入的OpenCV图像
    :param kernel_size: 卷积核大小，默认为(3, 3)
    :param iterations: 迭代次数，默认为1
    :return: 闭运算后的图像
    """
    # 创建卷积核
    kernel = np.ones(kernel_size, np.uint8)
    
    # 应用闭运算
    closed_image = cv2.morphologyEx(image, cv2.MORPH_CLOSE, kernel, iterations=iterations)
    
    return closed_image