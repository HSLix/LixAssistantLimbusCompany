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
    c = eye.templateMatch("mirror_init_teams.png", is_show_result=True, threshold=0)
    print(c)