# coding: utf-8
from os import path
from ctypes import windll
from re import fullmatch


 
# 定义资源文件夹路径
WORK_DIR = path.abspath(path.join("."))
RESOURCE_DIR = path.join(WORK_DIR, "resource")
TEMPLATE_DIR = path.join(RESOURCE_DIR, "template")
GUI_DIR = path.join(RESOURCE_DIR, "gui")
LOG_DIR = path.join(WORK_DIR, "log")
VIDEO_DIR = path.join(WORK_DIR, "video")
CONFIG_DIR = path.join(WORK_DIR, "config")
FFMPEG_FILE = path.join(RESOURCE_DIR, "ffmpeg/ffmpeg.exe")

# 仓库
GITHUB_REPOSITORY = "HSLix/LixAssistantLimbusCompany"

# 事件名称
EVENT_NAME = "LixAssistantLimbusCompanyRunning"

# 版本号
VERSION = "V3.1.6"


# 支持网址
ZH_SUPPORT_URL = "https://github.com/HSLix/LixAssistantLimbusCompany/tree/V3.0.0?tab=readme-ov-file#%E6%89%93%E8%B5%8F"
EN_SUPPORT_URL = "https://github.com/HSLix/LixAssistantLimbusCompany/blob/V3.0.0/README_en.md#Sponsorship"

# Discord
DISCORD_LINK = "https://discord.gg/bVzCuBU4bC"

MOUSE_BASEPOINT = [0,0]

MOUSE_HOME = [0,0]

# 设定窗口的大小
window_size = [1600, 900]

# 人物选择对应坐标
sinner_place = {
    "YiSang":[375,340], "Faust":[540,340], "DonQuixote":[700,340], "Ryoshu":[880,340], "Meursault":[1030,340], "HongLu":[1210,340],
    "Heathcliff":[375, 590], "Ishmael":[540, 590], "Rodion":[700, 590], "Sinclair":[880, 590], "Outis":[1030, 590], "Gregor":[1210, 590]
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


def isPathAllEnglish(path):
    """
    检查给定路径是否全部由英文字符组成。
    
    参数:
        path (str): 要检查的路径字符串。
        
    返回:
        bool: 如果路径中全是英文字符（包括字母、数字、标点符号和路径分隔符），返回 True；否则返回 False。
    """
    # 定义正则表达式模式：允许英文字符、数字、常见标点符号和路径分隔符
    pattern = r'^[a-zA-Z0-9\/\\.\\-_~!@#$%^&*()+=\[\]{}|;:",<>? ]+$'
    
    # 使用 re.fullmatch 检查整个字符串是否匹配模式
    return bool(fullmatch(pattern, path))

def checkWorkDirAllEnglish():
    print(WORK_DIR)
    if (not isPathAllEnglish(WORK_DIR)):
        raise ValueError("请把 LALC 放在路径全英文的目录下！ | Make sure that the path of LALC is all English!\n" + WORK_DIR)

if __name__ == "__main__":
    getScreenScale()
    # ignoreScaleAndDpi()
    # resetDpiAwareness()
    getScreenScale()
    print(WORK_DIR)
    # print(isPathAllEnglish(WORK_DIR))
    # ignoreScaleAndDpi()
    # activateWindow()
    # initMouseBasePoint()
    # initWindowSize()
