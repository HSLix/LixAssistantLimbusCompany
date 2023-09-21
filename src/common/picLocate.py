'''
* Author: LuYaoQi
* Time  : 2023/9/16 9:25
* File  : picLocate.py    
* Project   :LixAssistantLimbusCompany
* Function  :定位模板位置               
'''

from cv2 import imread, IMREAD_GRAYSCALE, matchTemplate, TM_CCOEFF_NORMED
from numpy import where
from gc import collect
from src.log.nbLog import myLog
from src.error.myError import withOutPicError



#全局变量存经常用的图片
#img是screenshot，template是用于匹配的模板
img = ""
template = ""
match = ""




def getSinCenXY(img_model_path, correctNum = 0.8):
    """
    仅寻找一个目标
    用来判定游戏画面的点击坐标
    :param img_model_path:用来检测的图片
    :param correctNum:准确率
    :return:以元组形式返回检测到的区域中心的坐标
    """
    
    
    #初始化匹配模板图片
    try:
        template = imread(img_model_path, IMREAD_GRAYSCALE)
    except:
        myLog("error","file could not be read, check with os.path.exists()") 
        raise withOutPicError("无法读取图片文件，图片文件很可能被删除，或主程序被移动")
    
    #初始化目标截图
    try:
        img = imread('./pic/screenshot.png',  IMREAD_GRAYSCALE)
    except:
        myLog("error","file could not be read, check with os.path.exists()") 
        raise withOutPicError("无法读取图片文件，图片文件很可能被删除，或主程序被移动")
    
    #匹配并得到坐标
    match = matchTemplate(img, template, TM_CCOEFF_NORMED)
    locations = where(match >= correctNum)

    #取目标的宽高
    h, w = template.shape[0:2]
    #看是否存在模板的标志
    existFlag = False
    for p in zip(*locations[::-1]):
        x1, y1 = p[0], p[1]
        center = (x1 + w/2,y1 + h/2)
        existFlag = True
        break

    # 内存释放
    del img,template,match,locations
    collect()

    if existFlag:
        return center
    else:
        return None
    



def getMulCenXY(img_model_path, correctNum = 0.8):
    """
    会寻找多个目标
    用来判定游戏画面的点击坐标
    :param img_model_path:用来检测的图片
    :param correctNum:准确率
    :return:以元组形式返回检测到的区域中心的坐标列表
    """
    
    #初始化匹配模板图片
    try:
        template = imread(img_model_path, IMREAD_GRAYSCALE)
    except:
        myLog("error","file could not be read, check with os.path.exists()") 
        raise withOutPicError("无法读取图片文件，图片文件很可能被删除，或主程序被移动")
    
    #初始化目标截图
    try:
        img = imread('./pic/screenshot.png',  IMREAD_GRAYSCALE)
    except:
        myLog("error","file could not be read, check with os.path.exists()") 
        raise withOutPicError("无法读取图片文件，图片文件很可能被删除，或主程序被移动")

    #匹配并得到坐标
    match = matchTemplate(img, template, TM_CCOEFF_NORMED)
    locations = where(match >= correctNum)

    #取目标的宽高然后画图
    h, w = template.shape[0:2]
    #看是否存在模板的标志
    existFlag = False
    positionList = []

    firstFlag = 1
    for p in zip(*locations[::-1]):
        x1, y1 = p[0], p[1]
        cx = x1 + w/2
        cy = y1 + h/2

        #跳过过于接近的匹配结果
        if(firstFlag == 0):
            if(abs(positionList[-2] - cx) < 10 and abs(positionList[-1] - cy) < 10):
                continue

        positionList.append(cx)
        positionList.append(cy)
        firstFlag = 0
        existFlag = True

    # 内存释放
    del img,template,match,locations
    collect()

    if existFlag:
        return positionList
    else:
        return None
    
