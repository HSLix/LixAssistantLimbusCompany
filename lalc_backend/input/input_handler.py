import win32api, win32con, win32gui
import copy
import ctypes
from ctypes import wintypes
import time
import webbrowser
import threading

from input.game_window import find_game_window, set_window_size, set_window_position, set_window_to_top, set_background_focus, set_foreground_focus, is_mouse_in_window, move_mouse_to_top_right_corner, get_cursor_pos, close_window, close_limbus_window
from input.game_screenshot import take_screenshot, _get_logical_client_rect
from input.game_click import background_click, foreground_click
from input.game_keyboard import background_key_press, foreground_key_press
from input.game_swipe import background_swipe, foreground_swipe
from input.idle_monitor import wait_input_idle
from utils.logger import init_logger


logger = init_logger()


# 状态接口定义各类操作的行为
class InputState:
    """输入状态抽象类"""
    
    def click(self, hwnd, x, y):
        raise NotImplementedError
    
    def key_press(self, hwnd, key):
        raise NotImplementedError
    
    def swipe(self, hwnd, start_x, start_y, end_x, end_y):
        raise NotImplementedError
    
    def set_focus(self, hwnd):
        raise NotImplementedError


class ForegroundInputState(InputState):
    """前台输入状态"""
    
    def click(self, hwnd, x, y):
        # 在执行点击前阻止用户输入
        ctypes.windll.user32.BlockInput(True)
        try:
            return foreground_click(hwnd, x, y)
        finally:
            # 确保无论如何都会解除阻止
            ctypes.windll.user32.BlockInput(False)
    
    def key_press(self, hwnd, key):
        return foreground_key_press(hwnd, key)
    
    def swipe(self, hwnd, start_x, start_y, end_x, end_y):
        # 在执行拖拽前阻止用户输入
        ctypes.windll.user32.BlockInput(True)
        try:
            return foreground_swipe(hwnd, start_x, start_y, end_x, end_y)
        finally:
            # 确保无论如何都会解除阻止
            ctypes.windll.user32.BlockInput(False)
    
    def set_focus(self, hwnd):
        return set_foreground_focus(hwnd)


class BackgroundInputState(InputState):
    """后台输入状态"""
    
    def click(self, hwnd, x, y):
        # 在执行点击前阻止用户输入
        ctypes.windll.user32.BlockInput(True)
        try:
            return background_click(hwnd, x, y)
        finally:
            # 确保无论如何都会解除阻止
            ctypes.windll.user32.BlockInput(False)
    
    def key_press(self, hwnd, key):
        return background_key_press(hwnd, key)
    
    def swipe(self, hwnd, start_x, start_y, end_x, end_y):
        # 在执行拖拽前阻止用户输入
        ctypes.windll.user32.BlockInput(True)
        try:
            return background_swipe(hwnd, start_x, start_y, end_x, end_y)
        finally:
            # 确保无论如何都会解除阻止
            ctypes.windll.user32.BlockInput(False)
    
    def set_focus(self, hwnd):
        return set_background_focus(hwnd)


class _Input:
    _singleton = None  # 保存唯一实例，供 wait_input_idle 访问

    def __init__(self):
        """
        初始化Input实例，默认为后台模式。
        使用状态模式管理前台/后台输入状态。
        注意，需要手动 refresh_handle 来获取初始句柄
        """
        if _Input._singleton is None:
            _Input._singleton = self

        self._hwnd = None
        
        # 初始化状态对象
        self._foreground_state = ForegroundInputState()
        self._background_state = BackgroundInputState()
        self._current_state = self._background_state  # 默认状态为后台
        
        self._screenshot = None
        self._width = 0
        self._height = 0
        # self.refresh_handle()

        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        
        screen_width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
        self._mouse_reset_position = (screen_width - 1, 0)

        # ======== 新增：暂停/停止标志 ========
        self._pause_flag = threading.Event()
        self._stop_flag  = threading.Event()
        self._pause_flag.set()  # 初始非暂停
        # ====================================

    def reset_mouse_position(self):
        ctypes.windll.user32.SetCursorPos(self._mouse_reset_position)

    def set_background_state(self):
        self._current_state = self._background_state
    
    def set_foreground_state(self):
        self._current_state = self._foreground_state

    # 供 ServerController 调用
    def pause(self):
        self._pause_flag.clear()
        logger.debug("InputHandler 已暂停")

    def resume(self):
        self._pause_flag.set()
        logger.debug("InputHandler 已恢复")

    def stop(self):
        self._stop_flag.set()
        self.resume()  # 若正在暂停，先解开
        logger.debug("InputHandler 已停止")
    
    def reset(self):
        """
        重置InputHandler到初始状态，包括恢复暂停标志、清除停止标志、重新查找窗口句柄
        """
        # 恢复到非暂停状态（即激活状态）
        self._pause_flag.set()
        # 清除停止标志
        self._stop_flag.clear()
        # 重置窗口句柄
        self.refresh_window_state()
        # 确保默认为后台模式
        self._current_state = self._background_state
        logger.debug("InputHandler 已重置到初始状态")
    
    def refresh_window_state(self):
        """
        刷新窗口句柄并更新相关属性。
        """
        self._hwnd = find_game_window()
        self._update_window_size()

    def _update_window_size(self):
        """
        根据当前窗口尺寸更新窗口大小属性。
        """
        if self._hwnd:
            self._width, self._height = _get_logical_client_rect(self._hwnd)
    
    @property
    def screenshot(self):
        return copy.copy(self._screenshot)  # 获取时返回副本
    
    @screenshot.setter
    def screenshot(self, value):
        self._screenshot = value  # 修改时直接设置
    
    @property
    def width(self):
        return self._width
    
    @property
    def height(self):
        return self._height
    
    def open_limbus(self):
        try:
            self.refresh_window_state()
        except Exception:
            logger.log("未找到游戏窗口，将尝试自动打开游戏，随后等待 30 秒")
            webbrowser.open("steam://rungameid/1973530")
            time.sleep(30)
        
    
    def capture_screenshot(self, reset=True, save_path=None):
        """
        截取游戏窗口屏幕并存储在screenshot属性中。
        """
        if self._hwnd:
            if self.set_focus():
                self.refresh_window_state()
                self.set_window_size()
            
            mouse_in_window, mouse_x, mouse_y = is_mouse_in_window(self._hwnd)
            if reset and mouse_in_window:
                logger.debug("检测到鼠标在游戏窗口内，尝试暂时移开鼠标")
                move_mouse_to_top_right_corner(self._hwnd)
            
            self.screenshot = take_screenshot(self._hwnd, width=self.width, height=self.height, save_path=save_path)
            # 复原
            if reset and mouse_in_window:
                logger.debug("之前检测到鼠标在游戏窗口内，暂时移开鼠标，现将鼠标归回原位")
                ctypes.windll.user32.SetCursorPos(mouse_x, mouse_y)
            return self.screenshot
        else:
            raise Exception("hwnd init Error")
    
    def set_window_size(self, width=1302, height=776):
        """
        设置窗口尺寸为指定大小。
        注意：这需要实际调用窗口大小调整函数的实现。
        """
        # 占位符用于实际窗口大小调整的实现
        # 通常会调用game_window模块中的函数
        self._width = width
        self._height = height
        if self._hwnd:
            set_window_size(self._hwnd, self._width, self._height)
            self.refresh_window_state()
        else:
            raise Exception("hwnd init Error")
    
    def set_window_position(self, x, y):
        """
        设置窗口位置为指定坐标。
        :param x: 窗口左上角x坐标
        :param y: 窗口左上角y坐标
        """
        if self._hwnd:
            set_window_position(self._hwnd, x, y)
        else:
            raise Exception("hwnd init Error")
            
    def set_window_to_top(self, client_width=1302, client_height=776):
        """
        将窗口客户区调整到屏幕顶部，并设置客户区大小
        :param client_width: 客户区宽度
        :param client_height: 客户区高度
        """
        if self._hwnd:
            set_window_to_top(self._hwnd, client_width, client_height)
            # 更新窗口尺寸信息
            self._update_window_size()
        else:
            raise Exception("hwnd init Error")
    
    def close_window(self):
        """
        关闭当前窗口并清空hwnd
        """
        if self._hwnd and win32gui.IsWindow(self._hwnd):
            logger.debug("正在关闭游戏窗口")
            close_window(self._hwnd)
            # 等待窗口关闭
            time.sleep(0.5)
            # 清空hwnd
            self._hwnd = None
            self._width = 0
            self._height = 0
            logger.debug("游戏窗口已关闭")
            return True
        else:
            logger.debug("没有有效的窗口句柄，无法关闭窗口")
            return False

    def close_limbus_window(self):
        """
        关闭LimbusCompany游戏窗口
        """
        logger.log("尝试关闭LimbusCompany窗口")
        result = close_limbus_window()
        if result:
            # 清空hwnd
            self._hwnd = None
            self._width = 0
            self._height = 0
        return result

    # 使用状态模式执行点击操作
    def click(self, x, y):
        """
        在指定位置执行点击操作，根据当前模式决定前台或后台点击。
        支持暂停/恢复/停止
        """
        if self._stop_flag.is_set(): 
            return
        self._pause_flag.wait()
        if self._hwnd:
            logger.debug(f"输入适配器执行:点击(click), 坐标: ({x}, {y})")
            wait_input_idle()
            if self._stop_flag.is_set(): 
                return
            self._pause_flag.wait()
            self.set_focus()
            return self._current_state.click(self._hwnd, x, y)
        else:
            raise Exception("hwnd init Error")
    
    # 使用状态模式执行键盘按键操作
    def key_press(self, key):
        """
        执行键盘按键操作，根据当前模式决定前台或后台按键。
        key 最常用："p", "enter", "esc"
        支持暂停/恢复/停止
        """
        if self._stop_flag.is_set(): 
            return
        self._pause_flag.wait()
        if self._hwnd:
            logger.debug(f"输入适配器执行:按键(key), 按键: {key}")
            self.set_focus()
            return self._current_state.key_press(self._hwnd, key)
        else:
            raise Exception("hwnd init Error")
    
    # 使用状态模式执行拖拽操作
    def swipe(self, start_x, start_y, end_x, end_y):
        """
        执行鼠标拖拽操作，根据当前模式决定前台或后台拖拽。
        支持暂停/恢复/停止
        """
        if self._stop_flag.is_set(): 
            return
        self._pause_flag.wait()
        if self._hwnd:
            wait_input_idle()
            if self._stop_flag.is_set(): 
                return
            self._pause_flag.wait()
            logger.debug(f"输入适配器执行:拖拽(swipe), 起点和终点: ({start_x}, {start_y}), ({end_x}, {end_y})")
            self.set_focus()
            return self._current_state.swipe(self._hwnd, start_x, start_y, end_x, end_y)
        else:
            raise Exception("hwnd init Error")
    
    # 使用状态模式设置焦点
    def set_focus(self)->bool:
        """
        设置窗口焦点，根据当前模式决定前台或后台焦点设置。
        :reutrn: 返回是否显示最小化窗口
        """
        if self._hwnd:
            return self._current_state.set_focus(self._hwnd)
        else:
            raise Exception("hwnd init Error")

input_handler = _Input()

if __name__ == "__main__":
    import time
    from game_window import find_game_window
    # 创建Input实例
    game_input = input_handler
    game_input.refresh_window_state()
    game_input.set_window_size()
    
    print(f"找到游戏窗口，句柄: {game_input._hwnd}")
    print(f"窗口尺寸: {game_input.width}x{game_input.height}")
    print(f"初始模式: {game_input.mode.value}")
    
    # 测试截图功能
    print("\n--- 测试截图功能 ---")
    try:
        screenshot = game_input.capture_screenshot(save_path="test.png")
        print(f"截图成功，尺寸: {screenshot.size}")
    except Exception as e:
        raise e
    
    # 测试前台模式切换
    print("\n--- 测试模式切换 ---")
    # game_input.mode = Mode.FOREGROUND
    # print(f"切换到前台模式: {game_input.mode.value}")
    
    # 测试后台模式切换
    print(f"切换到后台模式:")
    game_input.set_background_state()

    # 测试设置焦点功能
    print("\n--- 测试设置焦点功能 ---")
    try:
        result = game_input.set_focus()
        print(f"设置焦点操作完成")
    except Exception as e:
        raise e
        
    # 测试点击功能（在窗口左上角点击）
    print("\n--- 测试点击功能 ---")
    try:
        game_input.set_focus()
        for x, y in {"Yi Sang":[375,340], "Faust":[540,340], "Don Quixote":[700,340], "Ryoshu":[880,340], "Meursault":[1030,340], "Hong Lu":[1210,340],
    "Heathcliff":[375, 590], "Ishmael":[540, 590], "Rodion":[700, 590], "Sinclair":[880, 590], "Outis":[1030, 590], "Gregor":[1210, 590]}:
            result = game_input.click(x, y)
        print(f"点击操作完成")
    except Exception as e:
        raise e
    
    # # 测试键盘输入功能
    # print("\n--- 测试键盘输入功能 ---")
    # try:
    #     result = game_input.key_press('esc')
    #     print(f"键盘输入操作完成")
    # except Exception as e:
    #     print(f"键盘输入操作失败: {e}")
    
    # # 测试拖拽功能
    # print("\n--- 测试拖拽功能 ---")
    # try:
    #     result = game_input.swipe(10, 10, 500, 500)
    #     print(f"拖拽操作完成")
    # except Exception as e:
    #     print(f"拖拽操作失败: {e}")
        
    
        
    print("\n--- 所有测试完成 ---")

