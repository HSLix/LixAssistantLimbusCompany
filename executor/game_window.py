# coding: utf-8
import pygetwindow as gw

from globals import ignoreScaleAndDpi


def initSet():
    """
    需要初始化的函数集合
    TODO 消除这样的函数，内部的东西应该在某个构造函数做合适的初始化
    """
    initMouseBasePoint()
    initWindowSize()
    activateWindow()


def initMouseBasePoint():
    """
    初始化鼠标开始点的地方
    """
    # 查找名为 "LimbusCompany" 的窗口
    window = getWindow()

    # 获取窗口的位置和大小
    left, top = window.left, window.top
    # MOUSE_BASEPOINT[0], MOUSE_BASEPOINT[1] = left, top
    
    # print("基点：")
    #print((left, top))
    return (left, top)





def initWindowSize(window_size):
    """
    初始化设置窗口大小
    """
    window = getWindow()
    if (window.width == window_size[0]+22 and window.height == window_size[1]+56):
        return
    window.resizeTo(window_size[0]+22, window_size[1]+56)




def getWindow():
    try:
        windows = gw.getWindowsWithTitle("LimbusCompany")  # 获取第一个匹配的窗口
        for window in windows:
            if (window.title == "LimbusCompany"):
                return window
    except(IndexError):
        print("没有窗口，强制退出")
        raise NotImplementedError("检测不到游戏窗口，任务结束\nCan not detect the window of Game, Quit")

    print("没有窗口，强制退出")
    raise NotImplementedError("检测不到游戏窗口，任务结束\nCan not detect the window of Game, Quit")


def activateWindow():
    """
    激活窗口
    对最小化的窗口也有用
    """
    # 查找名为 "LimbusCompany" 的窗口
    window = getWindow()

    if (window.isActive):
        return
    try:
        window.restore()
        window.activate()
    except(gw.PyGetWindowException):
        pass

if __name__ == "__main__":
    ignoreScaleAndDpi()
    initWindowSize([1600, 1200])