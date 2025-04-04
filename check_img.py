from executor.eye import get_eye

eye = get_eye()

eye.captureScreenShot()

# c = eye.templateMatch("acquire_ego_owned.png", recognize_area=[160, 190, 1350, 100], threshold=0, is_show_result=True)
c = eye.templateMatch("acquire_ego_new.png", recognize_area=[160, 190, 1350, 100], threshold=0, is_show_result=True)

print(c)

# eye.screenshotOcr(recognize_area=[660, 185, 170, 75])
# rest_cost = eye.ocrGetFirstNum()
# print(rest_cost)