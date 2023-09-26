# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/9/16 9:25
* File  : getAdmin.py
* Project   :LixAssistantLimbusCompany
* Function  :获取管理员权限
'''

from __future__ import print_function
from ctypes import windll
from sys import executable, version_info
from src.error.myError import withOutAdminError
from src.log.nbLog import myLog

def isAdmin():
    '''仅仅返回是否是管理员'''
    try:
        return windll.shell32.IsUserAnAdmin()
    except:
        return False
    


def getAdmin():
    '''
    判断是否有管理员权限，是则继续，否则获取，获取失败则返回错误
    :param result:接收管理员权限申请结果，小于32即没有通过

    '''
    if isAdmin():
        pass
    else:
        if version_info[0] == 3:
            result = windll.shell32.ShellExecuteW(None, "runas", executable, __file__, None, 0)
            if(result <= 32):
                myLog("error","Can't get Admin")
                raise withOutAdminError("无管理员权限，软件很可能不能正常运作")

