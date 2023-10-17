from win32api import mouse_event
from win32con import MOUSEEVENTF_WHEEL
from random import uniform

def littleUpScroll():
    upNum = int(uniform(10, 30))
    mouse_event(MOUSEEVENTF_WHEEL,0,0,upNum)

