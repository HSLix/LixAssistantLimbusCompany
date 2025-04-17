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
    
    # x = 420
    # y = 415
    # x_step = 190
    # y_step = 175
    # for i in range(5):
    #     for j in range(2):
    #         mk.moveClick([x + i*x_step, y + j*y_step])
    #         print("%d, %d".format(x + i*x_step, y + j*y_step))

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