from executor.eye import get_eye
from time import sleep
from globals import ignoreScaleAndDpi
from executor.mouse_keyboard import mk

eye = get_eye()
ignoreScaleAndDpi()

# while True:

eye.captureScreenShot()
# c = eye.templateMatch("mirror_victory.png", recognize_area=[0, 0, 0, 0], threshold=0, is_show_result=True)

c = []
c += eye.templateMultiMatch("shop_purchase_left_bottom_corner.png", threshold=0.7, recognize_area=[0, 0, 0, 0], is_show_result=False)

# c = eye.rgbDetection([1330, 840])

print(c)
sleep(0.1)

for i in c:
    mk.moveClick(i)
    sleep(0.5)

# eye.screenshotOcr(recognize_area=[660, 185, 170, 75])
# rest_cost = eye.ocrGetFirstNum()
# print(rest_cost)