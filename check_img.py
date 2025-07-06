from executor.eye import get_eye
from time import sleep
from globals import ignoreScaleAndDpi

eye = get_eye()
ignoreScaleAndDpi()

# while True:

eye.captureScreenShot()
c = eye.templateMatch("mirror_victory.png", recognize_area=[0, 0, 0, 0], threshold=0, is_show_result=True)

# c = [[100, 110]]
# c += eye.templateMultiMatch("acquire_ego_gift.png", threshold=0.7, recognize_area=[0, 0, 0, 0], is_show_result=False)
# c.clear()

# c = eye.rgbDetection([1330, 840])

print(c)
sleep(0.1)

# eye.screenshotOcr(recognize_area=[660, 185, 170, 75])
# rest_cost = eye.ocrGetFirstNum()
# print(rest_cost)