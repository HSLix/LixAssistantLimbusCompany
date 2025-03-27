from executor.eye import get_eye

eye = get_eye()

eye.captureScreenShot()

# c = eye.templateMatch("purchase_ego_gift.png", recognize_area=[500, 230, 400, 60], threshold=0, is_show_result=False)

# print(c)

eye.screenshotOcr(recognize_area=[660, 185, 170, 75])
rest_cost = eye.ocrGetFirstNum()
print(rest_cost)