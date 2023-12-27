# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/9/16 9:25
* File  : tryClick.py
* Project   :LixAssistantLimbusCompany
* Function  :实验性点击测试
'''
from src.common import getPic, autoFindOrClick as afc

def tryClick(img_model_path, name, addX=0, addY=0,waitTime = 0.7, clickCount = 1, correctRate = 0.8):
    getPic.winCap()
    afc.autoSinClick(img_model_path, name, addX, addY,waitTime, clickCount , correctRate)


