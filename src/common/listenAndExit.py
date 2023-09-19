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



def listenAndExit():
    '''
    启动键盘监听线程，一旦按下ESC键便退出程序
    '''
    # 创建并启动键盘监听线程
    keyboard_thread = Thread(target=listen_keyboard)
    keyboard_thread.setDaemon(True)
    keyboard_thread.start()

# 执行需要在按下ESC键后运行的代码
def exit_program():
    _exit(0)

def on_press(key):
    if key == keyboard.Key.esc:
        exit_program()

def listen_keyboard():
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()