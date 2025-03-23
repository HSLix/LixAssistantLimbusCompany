# coding: utf-8
from executor.mouse_keyboard import mk
from globals import ignoreScaleAndDpi
from time import sleep

if __name__ == "__main__":
    ignoreScaleAndDpi()  
    mk.updateMouseBasepoint()
    # sleep(3)
    # print("滚")
    # mk.scroll([0,-1], 5)
#     mk.moveClick([1400,
#             860])
    mk.listenMouse()  
    # gift_places = []
    # x = 860
    # y = 370
    # x_step = 115
    # y_step = 120
    # for i in range(3):
    #     for j in range(5):
    #         gift_places.append([x + j*x_step, y + i*y_step])
    #         mk.moveClick([x + j*x_step, y + i*y_step])