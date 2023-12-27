# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/11/26 15:53
* File  : pressKey.py       
* Project   :LixAssistantLimbusCompany
* Function  :模拟键盘按键    
'''

from win32api import keybd_event
from win32con import KEYEVENTF_KEYUP
from src.log.myLog import myLog
from src.common.myTime import mySleep


asciiCode = {'p': 0x50, 'space': 0x20, 'esc': 0x1b, 'enter': 0x0D}
scanCode = {'p': 0x19, 'space':0x39, 'esc': 0x01, 'enter':0x1c}

def pressKey(key):
    """
    输入一个字符，形成模拟键盘信号
    :param key: 想输入的字符
    :目前支持字符有：p, space(空格),esc,enter
    :return: 无
    """
    msg = "pressing thg key " + key
    myLog("debug",msg)
    asciiIndex = asciiCode[key]
    scanIndex = scanCode[key]

    keybd_event(asciiIndex,scanIndex,0,0) 
    mySleep(0.2) 
    keybd_event(asciiIndex,scanIndex,KEYEVENTF_KEYUP,0)  
    mySleep(0.2) 
    

