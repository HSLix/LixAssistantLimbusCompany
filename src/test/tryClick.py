# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/9/16 9:25
* File  : tryClick.py
* Project   :LixAssistantLimbusCompany
* Function  :实验性点击测试
'''
from src.common import getPic, autoFindOrClick as afc
from src.common import picLocate
from ctypes import windll
import globalVar

def tryClick(img_model_path, name, addX=0, addY=0,waitTime = 0.7, clickCount = 1, correctRate = 0.8):
    getPic.winCap()

    address = "./pic/mirror/mirror4/ego/" + globalVar.mirror_start_ego + "EGOGift.png"
    afc.autoSinClick(address, "SelectMirrorStartTendency", 0, 0, 0.7, 1, 0.9)
    print(address)
    #afc.autoMulClick("./pic/mirror/mirror4/ego/StartSelectedGift.png",  "TestEGOSign", -200, 0, 0.5, 1, 0.7)
    #afc.autoSinClick(img_model_path, name, addX, addY,waitTime, clickCount , correctRate)
    # afc.autoSinClick("./pic/mirror/mirror3/way/Self.png", "Self")
    '''center = picLocate.getSinCenXY("./pic/mirror/mirror4/way/TestHighLoc.png", 0.6)                
    print(center)        
    center = picLocate.getSinCenXY("./pic/mirror/mirror4/way/TestMiddleLoc.png", 0.6)                
    print(center)  
    center = picLocate.getSinCenXY("./pic/mirror/mirror4/way/TestLowLoc.png", 0.6)                
    print(center)'''   
    #afc.autoSinClick("./pic/Wait.png", "Wait Sign")

    # afc.clickAndDragTo("./pic/mirror/mirror3/way/Self.png", "DragSelf", center[0] + 20, center[1] + 40, 0, 0, 0.9, 0.6)



