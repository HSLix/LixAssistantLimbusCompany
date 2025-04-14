# coding: utf-8
from executor.mouse_keyboard import mk
from globals import ignoreScaleAndDpi
from time import sleep

if __name__ == "__main__":
    ignoreScaleAndDpi()  
    mk.updateMouseBasepoint()
    sleep(1)
    # mk.moveClick([150, 630])
    # mk.scroll([0,1], 30, 0.01)
    # sleep(0.5)
    # mk.scroll([0,-1], 7)
    # mk.moveClick([150,555])
    # mk.moveClick([555, 885])
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