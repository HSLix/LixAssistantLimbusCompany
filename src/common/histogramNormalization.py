# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/10/10 10:01
* File  : histogramNormalization.py   
* Project   :LixAssistantLimbusCompany
* Function  :取出图片，返回其均值化的图片
'''

from cv2 import imread, createCLAHE, IMREAD_GRAYSCALE, imshow, waitKey, destroyAllWindows


def getGreyNormalizedPic(picPath):
    # 读取图像
    img = imread(picPath, IMREAD_GRAYSCALE)

    # 自适应均衡化
    clahe = createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    cl1 = clahe.apply(img)
    
    # 显示原始图像和均衡化后的图像

    '''imshow('Original Image', img)
    imshow('Equalized Image', cl1)
    waitKey(0)
    destroyAllWindows()'''
    return cl1
    
