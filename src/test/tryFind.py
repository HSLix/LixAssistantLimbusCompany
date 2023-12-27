# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/12/27 21:52
* File  : tryFind.py
* Project   :LixAssistantLimbusCompany
* Function  :实验性识图测试
'''
from src.common import getPic, autoFindOrClick as afc

def tryFind(img_model_path, name, correctRate = 0.8):
    getPic.winCap()
    afc.autoFind(img_model_path, name, correctRate)

