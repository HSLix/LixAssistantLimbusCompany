import time
from pynput import mouse, keyboard
from threading import Thread
from utils.logger import init_logger

logger = init_logger()

class IdleMonitor:
    def __init__(self, idle_time=0.4, test_mode=False):
        self.idle_time = idle_time  # 设置空闲时间
        self.test_mode = test_mode  # 是否启用测试模式
        self.last_input_time = time.time()  # 记录上次活动时间
        self.stop_monitoring = False  # 用于停止监听
        self.mouse_listener = None
        self.keyboard_listener = None
        self.mouse_pressed = False  # 跟踪鼠标按键状态

    # 记录鼠标活动
    def on_move(self, x, y):
        if not self.stop_monitoring:
            self.record_activity("Mouse move")
        return not self.stop_monitoring
    
    def on_click(self, x, y, button, pressed):
        if not self.stop_monitoring:
            # 更新鼠标按键状态
            if pressed:
                self.mouse_pressed = True
            else:
                self.mouse_pressed = False
            self.record_activity(f"Mouse click: {button} {'pressed' if pressed else 'released'}")
        return not self.stop_monitoring
    
    def on_scroll(self, x, y, dx, dy):
        if not self.stop_monitoring:
            self.record_activity("Mouse scroll")
        return not self.stop_monitoring

    # 记录键盘活动
    def on_press(self, key):
        if not self.stop_monitoring:
            self.record_activity(f"Key pressed: {key}")
        return not self.stop_monitoring

    def on_release(self, key):
        # if key == keyboard.Key.esc:  # 按下Esc时退出
        #     self.stop_monitoring = True
        #     return False
        if not self.stop_monitoring:
            self.record_activity(f"Key released: {key}")
        return not self.stop_monitoring

    # 记录活动
    def record_activity(self, activity:str):
        if self.test_mode:
            print(activity)
        logger.debug(activity)
        self.last_input_time = time.time()

    # 检查空闲时间
    def monitor_idle(self):
        while not self.stop_monitoring:
            # 如果鼠标按键处于按下状态，则不算空闲
            if self.mouse_pressed:
                self.last_input_time = time.time()
            
            if time.time() - self.last_input_time > self.idle_time:
                self.stop_monitoring = True
                break
            time.sleep(0.1)
        
        # 打印空闲时间超过后退出的信息
        if self.stop_monitoring:
            logger.debug("Monitoring stopped.")
        else:
            logger.debug(f"Idle time exceeded {self.idle_time} seconds, exiting.")

    # 启动鼠标和键盘监听器
    def start_listening(self):
        # 创建监听器
        self.mouse_listener = mouse.Listener(
            on_move=self.on_move,
            on_click=self.on_click,
            on_scroll=self.on_scroll)
        
        self.keyboard_listener = keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release)
        
        # 启动监听器
        self.mouse_listener.start()
        self.keyboard_listener.start()

        # 监测空闲时间
        self.monitor_idle()

        # 停止监听器
        self.mouse_listener.stop()
        self.keyboard_listener.stop()

        # 等待监听线程结束
        self.mouse_listener.join()
        self.keyboard_listener.join()

# 用法
def wait_input_idle(idle_time=0.4, test_mode=False):
    monitor = IdleMonitor(idle_time, test_mode)
    monitor.start_listening()

if __name__ == "__main__":
    
    # 测试，0.4秒空闲后退出
    wait_input_idle(idle_time=0.4, test_mode=True)