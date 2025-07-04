from executor.eye import get_eye
from time import sleep

eye = get_eye()


# while True:
eye.captureScreenShot()
# c = eye.templateMatch("shop_sell_ego_resource.png", recognize_area=[0, 0, 0, 0], threshold=0, is_show_result=True)

# c = [[100, 110]]
# c += eye.templateMultiMatch("acquire_ego_gift.png", threshold=0.7, recognize_area=[0, 0, 0, 0], is_show_result=False)
# c.clear()

c = eye.rgbDetection([1330, 840])

print(c)
sleep(0.1)

# eye.screenshotOcr(recognize_area=[660, 185, 170, 75])
# rest_cost = eye.ocrGetFirstNum()
# print(rest_cost)