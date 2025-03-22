from globals import ignoreScaleAndDpi
from executor.eye import get_eye
from executor.game_window import activateWindow
from time import sleep


if __name__ == "__main__":
    ignoreScaleAndDpi()
    activateWindow()
    sleep(1)
    eye = get_eye()
    eye.captureScreenShot()
    # c = eye.templateMatch("shop_scroll_block.png", is_show_result=True, threshold=0, recognize_area=[1375, 455, 55, 370])
    c = eye.templateMatch("shop_scroll_block.png", recognize_area=[1375, 310, 55, 370], threshold=0, is_show_result=False)
    print(c)