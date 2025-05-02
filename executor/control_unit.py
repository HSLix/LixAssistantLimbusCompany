# coding: utf-8
from threading import Condition
from collections import deque
from time import sleep, time
from PyQt5.QtCore import QThread, pyqtSignal
from copy import deepcopy
from ctypes import windll

from .task import task_dict, custom_action_dict
from .game_window import activateWindow, initWindowSize
from .logger import lalc_logger
from i18n import _





class ControlUnit(QThread):
    _instance = None  # 单例实例

    # 定义信号，用于与主线程通信
    task_start = pyqtSignal(str) #任务名称，提示任务开始
    task_finished = pyqtSignal(str, int)          # 任务名称, 执行次数
    task_error = pyqtSignal(str)                  # 错误信息
    task_warning = pyqtSignal(str)
    task_paused = pyqtSignal()
    task_resumed = pyqtSignal()
    task_stopped = pyqtSignal()
    task_completed = pyqtSignal()
    team_info_updated = pyqtSignal(str, str)  # 当前队伍名字, 下一个队伍名字
    task_checkpoint = pyqtSignal(str) #检查点对应任务名称 和 任务完成数量
    pause_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    pause_completed = pyqtSignal()
    stop_completed = pyqtSignal()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ControlUnit, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, parent=None):
        if self._initialized:
            return
        super().__init__(parent)
        self.task_dict = task_dict  # 初始化任务字典
        self.condition = Condition()  # 线程条件变量
        self.is_paused = False  # 是否暂停
        self.is_stoped = False # 是否停止
        self.is_running = False  # 是否运行
        self.next_task = None  # 下一个任务
        self.pending_task_stack = deque()  # 待处理任务栈
        self.max_stack_size = 10  # 栈的最大容量
        self.task_executed_count = 0  # 任务已执行次数
        self.start_task_name = None  # 起始任务名称
        self._initialized = True  # 标记初始化完成
        self.task_params = {}
        self.mode = ""
        self.pause_requested.connect(self._handle_pause)
        self.stop_requested.connect(self._handle_stop)

    def set_task_params(self, params):
        self.task_params = params

    def get_task_param(self, key, default=None):
        return self.task_params.get(key, default)


    def get_task_from_dict(self, func_name: str):
        """从任务字典中获取任务"""
        get_task = self.task_dict.get(func_name)
        if get_task is None:
            self.task_error.emit(f"Error! 正在尝试读取不存在的函数[{func_name}]，程序已立即终止")
            self.stop()
        return get_task
    




    def set_max_stack_size(self, size: int):
        """设置栈的最大容量"""
        self.max_stack_size = size

    def set_start_task(self, task_name):
        """设置初始任务并唤醒线程"""
        with self.condition:
            self.start_task_name = task_name
            self.next_task = None  # 清空当前任务
            task = self.get_task_from_dict(task_name)
            if task:
                task.update_screenshot()
                task.execute_recognize()
                self.next_task = task
                self.condition.notify()  # 唤醒线程

    def set_next_task(self, task):
        """将任务设置为下一个待执行任务"""
        with self.condition:
            self.next_task = task
            self.condition.notify()  # 唤醒线程

    def _is_task_recognized(self, task):
        """判断任务是否识别成功"""
        if task.recognition == "TemplateMatch":
            return task.recognize_score is not None
        elif task.recognition == "ColorMatch":
            return task.recognize_score > 0
        elif task.recognition == "DirectHit":
            return True
        return False

    def _add_next(self, task):
        """处理next任务链"""
        activateWindow()
        sleep(0.1)
        task.update_screenshot()
        if task.next:
            with self.condition:
                for next_task_name in task.next:
                    next_task = self.get_task_from_dict(next_task_name)
                    if next_task and next_task.enabled:
                        next_task.execute_recognize()
                        if self._is_task_recognized(next_task):
                            self.next_task = next_task  # 直接设置下一个任务
                            break  # 找到第一个有效任务即终止循环
                self.condition.notify()

    def _add_interrupt(self, task):
        """处理中断任务"""
        with self.condition:
            for next_task_name in task.interrupt:
                next_task = self.get_task_from_dict(next_task_name)
                if next_task and next_task.enabled:
                    next_task.execute_recognize()
                    if self._is_task_recognized(next_task):
                        self.next_task = next_task  # 设置中断任务为下一个
                        self.push_to_stack(self.cur_task)  # 当前任务压栈
                        break  # 找到第一个有效中断即终止
            self.condition.notify()

    def pop_task(self):
        """获取并清空下一个任务"""
        with self.condition:
            task = self.next_task
            self.next_task = None
            return task

    def push_to_stack(self, task):
        """压栈操作"""
        with self.condition:
            if len(self.pending_task_stack) < self.max_stack_size:
                self.pending_task_stack.append(task)
            else:
                lalc_logger.log_task(
                    "WARNING",
                    self.cur_task.name,
                    "CAN NOT PROCESS ANY MORE. Restart."
                    )
                self.task_warning.emit(f"Stack is full, task[{task.name}] discarded.")

    def pop_from_stack(self):
        """弹栈操作"""
        with self.condition:
            return self.pending_task_stack.pop() if self.pending_task_stack else None

    def is_stack_empty(self):
        """栈空判断"""
        with self.condition:
            return not bool(self.pending_task_stack)
        

    def preprocess_tasks(self):
        """预处理函数，根据task_params修改task_dict里相关任务的enable设置"""
        for task_name, enable in self.task_params.items():
            if (type(enable) != bool):
                continue
            task = self.task_dict.get(task_name)
            if task:
                task.enabled = enable

    def init_target_task_count(self):
        """预处理函数，根据task_params修改task_dict里相关任务的count设置"""
        self.target_task_count = {}
        for task_name, target_count in self.task_params.items():
            if (type(target_count) != int):
                continue
            self.target_task_count[task_name] = target_count

        self.target_task_count["Pass"] = 0


    def run(self):
        """主执行循环（修改任务获取逻辑）"""
        
        self.is_running = True
        self.preprocess_tasks()
        self.task_executed_count = 0
        self.init_target_task_count()
        self.cur_task = None
        self.is_stoped = False
        self.is_paused = False
        lalc_logger.log_task(
            "INFO",
            "ContainUnitRun",
            'SUCCESS',
            "cu start working with task[{0}]".format(self.start_task_name)
        )
        if self.mode == "FullAuto":
            # 获取当前队伍和下一个队伍的信息
            current_team_name = custom_action_dict["get_team_name_by_index"](self.task_executed_count)
            next_team_name = custom_action_dict["get_team_name_by_index"](self.task_executed_count + 1)
            self.team_info_updated.emit(current_team_name, next_team_name)
        elif self.mode == "SemiAuto":
            self.team_info_updated.emit("-", "-")

        while self.is_running:
            try:  # 将整个循环体包裹在try块中
                activateWindow()
                initWindowSize([1600, 900])
                initWindowSize([1600, 900])
                with self.condition:
                    # 暂停
                    if self.is_paused:
                        self.pause_completed.emit()
                        lalc_logger.log_task(
                            "INFO",
                            "ContainUnitRun",
                            'SUCCESS',
                            "cu pause  with task[{0}]".format(self.cur_task.name)
                        )
                        lalc_logger.log_task(
                            "INFO",
                            "ContainUnitRun",
                            'SUCCESS',
                            "cu pause  with task[{0}]".format(self.cur_task.name)
                        )
                        while self.is_running and self.is_paused:
                            self.condition.wait()
                    
                    # 停止
                    if self.is_stoped:
                        break
                    
                    # 获取当前任务并清空指针
                    self.cur_task = self.next_task
                    self.next_task = None

                    if self.cur_task is None:
                        print("当前任务为空")
                        self.task_error.emit(_("当前任务为空，无法继续执行"))
                        lalc_logger.log_task(
                            "ERROR",
                            "?",
                            'Failed',
                            "cur_task is None"
                        )
                        self.stop()
                        break

                temp_target_task_count = deepcopy(self.target_task_count)

                # 记录任务开始
                lalc_logger.log_task(
                    self.cur_task.log_level,
                    self.cur_task.name,
                    'STARTED'
                )

                start_time = time()
                if self.cur_task.action == "Checkpoint":
                    self.task_executed_count += 1
                    self.task_finished.emit(self.cur_task.target_task_count_name, self.task_executed_count)
                    lalc_logger.log_task(
                        self.cur_task.log_level,
                        self.cur_task.name,
                        'FINISH',
                        f"For {self.task_executed_count} Times"
                    )

                    if self.mode == "FullAuto":
                        # 获取当前队伍和下一个队伍的信息
                        current_team_name = custom_action_dict["get_team_name_by_index"](self.task_executed_count)
                        next_team_name = custom_action_dict["get_team_name_by_index"](self.task_executed_count + 1)
                        self.team_info_updated.emit(current_team_name, next_team_name)
                    elif self.mode == "SemiAuto":
                        self.team_info_updated.emit("-", "-")

                if self.cur_task.name == "End":
                    self.complete()
                    break

                # 执行当前任务
                self.cur_task.execute_task(executed_time=self.task_executed_count, target_task_count=temp_target_task_count)

                # 满足结束检查点，重置任务已执行次数
                if (temp_target_task_count["Pass"] == 1): 
                    self.task_executed_count = 0

                # 处理正常任务链
                self._add_next(self.cur_task)

                # 处理中断任务（仅当没有后续任务时）
                if self.next_task is None:
                    self._add_interrupt(self.cur_task)

                # 尝试恢复栈中任务（当没有后续任务时）
                if self.next_task is None and not self.is_stack_empty():
                    self.set_next_task(self.pop_from_stack())

            except Exception as e:
                # 获取详细的错误信息
                from traceback import format_exc
                error_info = format_exc()
                # 记录任务异常
                if self.cur_task:
                    lalc_logger.log_task(
                        'ERROR',
                        self.cur_task.name if self.cur_task else 'Unknown',
                        'FAILED',
                        f"Error: {error_info}"
                    )
                self.task_error.emit(f"任务执行失败: {error_info}")
                break
            

        # 清理资源
        with self.condition:
            self.stop()


    def _handle_pause(self):
        """实际暂停操作"""
        with self.condition:
            self.is_paused = True
            self.condition.notify()


    def _handle_stop(self):
        """实际停止操作"""
        with self.condition:
            self.is_running = False
            self.is_stoped = True
            self.condition.notify()


    def pause(self):
        """暂停任务处理"""
        with self.condition:
            self.is_paused = True
            self.task_paused.emit()  # 发射任务暂停信号

    def resume(self):
        """恢复任务处理"""
        with self.condition:
            self.is_paused = False
            self.condition.notify()
            self.task_resumed.emit()  # 发射任务恢复信号

    def stop(self):
        """安全停止线程"""
        with self.condition:
            lalc_logger.log_task(
                "INFO",
                "ContainUnitStop",
                'SUCCESS',
                "cu stop with final task[{0}]".format(self.cur_task.name)
            )
            self.next_task = None
            self.pending_task_stack.clear()
            self.is_running = False
            self.condition.notify()
            self.stop_completed.emit()  # 发射任务停止信号

    def complete(self):
        """完成所有任务"""
        with self.condition:
            lalc_logger.log_task(
                "INFO",
                "ContainUnitComplete",
                'SUCCESS',
                "cu complete with final task[{0}]".format(self.cur_task.name)
            )
            self.stop()
            self.task_completed.emit()
            





lalc_cu = ControlUnit()







# 测试代码
if __name__ == "__main__":
    # 创建cu实例
    # cu = DebugControlUnit()
    # cu.set_max_stack_size(1)
    # cu.set_task_params({
    #     "EXP": 2,

    #     "Thread": 1,

    #     "Mirror": 1,
    #     'SkipEXPLuxcavationStart': False,
    #         "SkipThreadLuxcavationStart": False,
    #         "FullAutoMirrorCircleCenter":False
    #     })
    # cu.set_start_task("FullAutoEntrance")
    # cu.set_start_task("test")
    # 设置起始任务
    # cu.set_start_task("SemiAutoStart")
    # cu.set_start_task("SkipEXPLuxcavationStart")
    # cu.set_start_task("SkipThreadLuxcavationStart")
    # cu.set_start_task("GetPassMissionCoinStart")
    # cu.set_start_task("TouchToStart")
    # 启动线程
    # cu.start()
    # cu.run()
    # t = custom_action_dict["enhance_needed_ego_gift"]
    # t = custom_action_dict["purchase_needed_ego_gift"]
    # t(executed_time=0)
    pass

