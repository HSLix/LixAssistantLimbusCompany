from executor.eye import get_eye

eye = get_eye()

eye.captureScreenShot()

c = eye.templateMatch("shop_purchase_keywordless.png", recognize_area=[575, 405, 60, 60], threshold=0, is_show_result=False)

print(c)

# eye.screenshotOcr(recognize_area=[660, 185, 170, 75])
# rest_cost = eye.ocrGetFirstNum()
# print(rest_cost)