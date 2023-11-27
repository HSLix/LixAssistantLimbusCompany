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

keyDictionary = {'p': 112, 'space': 32, 'esc': 27, 'enter': 13}

def pressKey(key):
    '''
    :param
    key:字符，转为对应ASCII
    '''
    msg = "pressing thg key " + key
    myLog(msg)
    index = keyDictionary[key]

    keybd_event(index,0,0,0)  
    keybd_event(index,0,KEYEVENTF_KEYUP,0)  
    
    

