# coding: utf-8
from executor.mouse_keyboard import mk
from globals import ignoreScaleAndDpi
from time import sleep

if __name__ == "__main__":
    ignoreScaleAndDpi()  
    mk.updateMouseBasepoint()
    # sleep(1)
    # mk.moveClick([150, 555])
    # mk.scroll([0,-1], 7)
    # mk.listenMouse()  

    mk.moveClick([150, 430])
    mk.moveClick([150, 480])

    mk.moveClick([150, 530])

    mk.moveClick([150, 570])

    mk.moveClick([150, 620])

    mk.moveClick([150, 660])

    # x = 350
    # y = 400
    # x_step = 250
    # y_step = 250
    # l = []
    # for j in range(2):
    #     for i in range(5):
    #         mk.moveClick([x + i*x_step, y + j*y_step])
    #         l.append([x + i*x_step, y + j*y_step])
    #         print("%d, %d".format(x + i*x_step, y + j*y_step))

    # print(l)
    # style_refresh = {
    #                 "Burn":[420, 415],
    #                 "Bleed":[610, 415],
    #                 "Tremor":[800, 415],
    #                 "Rupture":[990, 415],
    #                 "Sinking":[1180, 415],
    #                 "Poise":[420, 590],
    #                 "Charge":[610, 590],
    #                  }
    # for place in style_refresh.values():
    #     mk.moveClick(place)