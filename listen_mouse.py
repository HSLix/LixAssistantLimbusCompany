# coding: utf-8
from executor.mouse_keyboard import mk
from globals import ignoreScaleAndDpi
from time import sleep

if __name__ == "__main__":
    ignoreScaleAndDpi()  
    # sleep(3)
    # print("滚")
    # mk.scroll([0,-1], 5)
    mk.listenMouse()  