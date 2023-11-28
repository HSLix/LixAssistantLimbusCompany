# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/9/16 9:25
* File  : listenAndExit.py
* Project   :LixAssistantLimbusCompany
* Function  :监听键盘ESC键，一旦按下立即退出程序
'''
from pynput import keyboard
from os import _exit
from threading import Thread
from src.log.myLog import myLog
from src.common.myTime import mySleep


def listenAndExit():
    '''
    启动键盘监听线程，一旦按下键便退出程序
    '''
    # 创建并启动键盘监听线程
    keyboard_thread = Thread(target=listen_keyboard)
    keyboard_thread.setDaemon(True)
    keyboard_thread.start()

# 执行需要在按下键后运行的代码
def exit_program(key):
    myLog("info", "Keyboard input \'"+ str(key) + "\'Quit!")
    mySleep(0.2)    
    _exit(0)

def on_press(key):
    # 默认ctrl q
    if str(key) == r"'\x11'":
        exit_program(key)

def listen_keyboard():
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()