# coding: utf-8
from os import path
from ctypes import windll


 
# 定义资源文件夹路径
WORK_DIR = path.abspath(path.join("."))
RESOURCE_DIR = path.join(WORK_DIR, "resource")
TEMPLATE_DIR = path.join(RESOURCE_DIR, "template")
GUI_DIR = path.join(RESOURCE_DIR, "gui")
LOG_DIR = path.join(WORK_DIR, "log")
VIDEO_DIR = path.join(WORK_DIR, "video")
DLL_DIR = path.join(RESOURCE_DIR, "dll")
CONFIG_DIR = path.join(WORK_DIR, "config")

# 事件名称
EVENT_NAME = "LixAssistantLimbusCompanyRunning"

# 版本号
VERSION = "3.0.0"


# 支持网址
ZH_SUPPORT_URL = "https://github.com/HSLix/LixAssistantLimbusCompany/tree/V3.0.0?tab=readme-ov-file#%E6%89%93%E8%B5%8F"
EN_SUPPORT_URL = "https://github.com/HSLix/LixAssistantLimbusCompany/blob/V3.0.0/README_en.md#Sponsorship"


MOUSE_BASEPOINT = [0,0]

MOUSE_HOME = [0,0]

# 设定窗口的大小
window_size = [1600, 1200]

# 人物选择对应坐标
sinner_place = {
    "YiSang":[375,500], "Faust":[540,500], "DonQuixote":[700,500], "Ryoshu":[880,500], "Meursault":[1030,500], "HongLu":[1210,500],
    "Heathcliff":[375, 740], "Ishmael":[540, 740], "Rodion":[700, 740], "Sinclair":[880, 740], "Outis":[1030, 740], "Gregor":[1210, 740]
}

sinner_name = [  # 固定十二个人物列表
            "YiSang", "Faust", "DonQuixote", "Ryoshu", "Meursault", "HongLu",
            "Heathcliff", "Ishmael", "Rodion", "Sinclair", "Outis", "Gregor"
]

def ignoreScaleAndDpi():
    windll.shcore.SetProcessDpiAwareness(2)

def resetDpiAwareness():
    windll.shcore.SetProcessDpiAwareness(0)

def getScreenScale():
        gdi32 = windll.gdi32
        user32 = windll.user32
        dc = user32.GetDC(None)
        widthScale = gdi32.GetDeviceCaps(dc, 8)  # 分辨率缩放后的宽度
        # heightScale = gdi32.GetDeviceCaps(dc, 10)  # 分辨率缩放后的高度
        width = gdi32.GetDeviceCaps(dc, 118)  # 原始分辨率的宽度
        height = gdi32.GetDeviceCaps(dc, 117)  # 原始分辨率的高度
        scale = width / widthScale

        print("Screen(not scaled):{0}*{1}; Scale:{2}%".format(width, height, scale*100))
        
        if(not(scale > 1.49 and scale < 1.51)):
            print(scale)

if __name__ == "__main__":
    getScreenScale()
    # ignoreScaleAndDpi()
    resetDpiAwareness()
    getScreenScale()
    print(WORK_DIR)
    # ignoreScaleAndDpi()
    # activateWindow()
    # initMouseBasePoint()
    # initWindowSize()
