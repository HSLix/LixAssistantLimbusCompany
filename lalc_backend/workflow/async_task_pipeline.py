import asyncio
import threading
import traceback
from typing import Dict, Any, Callable, Optional
import sys
import os

# 添加上级目录到路径中，以便导入模块
# sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from workflow.task_registry import get_task, init_tasks
from workflow.task_execution import TaskExecution
from utils.config_manager import initialize_configs
from utils.logger import init_logger


class AsyncTaskPipeline:
    """
    异步任务流水线，负责从任务的开始节点流水线执行到next为空
    实现基于函数栈的新任务处理机制，支持异步操作
    """
    # 定义任务流水线状态常量
    STATE_STOPPED = "stopped"
    STATE_RUNNING = "running"
    STATE_PAUSED = "paused"
    
    def __init__(self):
        # 初始化任务注册表
        init_tasks()
        self.task_stack = []
        self.task_execution = None
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # 初始非暂停
        self._stop_event = asyncio.Event()
        self._worker_task: asyncio.Task | None = None
        self.shared_params = None
        self.logger = init_logger()
        self._error_callback: Optional[Callable[[str, str], None]] = None
        self._completion_callback: Optional[Callable[[], None]] = None
        # 添加状态属性
        self._state = self.STATE_STOPPED

    def set_error_callback(self, callback: Callable[[str, str], None]):
        """
        设置错误回调函数，用于将错误信息传递给服务器
        :param callback: 回调函数，参数为(error_message, traceback_string)
        """
        self._error_callback = callback

    def set_completion_callback(self, callback: Callable[[], None]):
        """
        设置完成回调函数，用于通知任务正常结束
        :param callback: 回调函数，无参数
        """
        self._completion_callback = callback

    @property
    def state(self):
        """
        获取当前任务流水线状态
        :return: 当前状态 (STATE_STOPPED, STATE_RUNNING, STATE_PAUSED)
        """
        return self._state

    def refresh_target_count(self):
        """
        根据 shared params 的内容，把几个 target count 的值给覆盖一下
        """
        for check_name, cfg_name in [("exp_check", "exp_cfg"), ("thread_check", "thread_cfg"), ("mirror_check", "mirror_cfg")]:
            check_task = get_task(check_name)
            check_task.set_param("target_count", self.shared_params[cfg_name]["check_node_target_count"])
            if check_task.get_param("target_count") == 0:
                check_task.get_param("disable_node").enable = False

    def add_start_task(self, task_name: str):
        """
        清空任务栈，并添加起始任务
        """
        self.get_shared_params()
        # 初始化执行类
        self.task_execution = TaskExecution(self.shared_params)

        # 清空任务栈
        self.task_stack.clear()
        
        # 使用 task registry 的 get_task 获取 TaskNode
        task_node = get_task(task_name)
        
        # 获取该节点的 do_action 和 get_next 函数
        pre_task_name, do_action_func, get_next_func = task_node.name, task_node.do_action, task_node.get_next
        
        # 按压栈规则压入（先 get_next，再 do_action）
        if get_next_func is not None:
            self.task_stack.append((pre_task_name, get_next_func))
        if do_action_func is not None:
            self.task_stack.append((pre_task_name, do_action_func))

        # 刷新任务节点执行次数
        self.refresh_target_count()
        self.logger.debug(f"添加起始任务: {task_name}")

    async def start(self, entry: str):
        """
        启动异步任务流水线
        """
        # 允许在STOPPED状态下重新启动，即使_worker_task不为None也要重置
        if self._state == self.STATE_RUNNING:
            self.logger.debug("任务流水线已在运行中")
            return
            
        self._stop_event.clear()
        self._state = self.STATE_RUNNING
        
        # 重置任务栈并添加起始任务
        self.add_start_task(entry)
        
        # 创建并启动工作协程（无论之前是否存在）
        self._worker_task = asyncio.create_task(self._worker())
        self.logger.debug(f"启动异步任务流水线，入口任务: {entry}")

    async def _worker(self):
        """
        异步工作协程，不断处理任务栈中的函数
        """
        self.logger.debug("异步任务工作协程开始运行")
        try:
            while self.task_stack and not self._stop_event.is_set():
                # 检查是否处于暂停状态
                await self._pause_event.wait()

                # print(self.task_stack)
                
                # 弹出栈顶的函数
                pre_task_name, func = self.task_stack.pop()
                
                # 执行函数
                cur_task_name, do_action_func, *get_next_funcs = await asyncio.get_event_loop().run_in_executor(
                    None, self.task_execution.execute, pre_task_name, func
                )
                
                # 压栈规则：先压 get_next_func，再压 do_action_func
                for next_func in reversed(get_next_funcs):
                    if next_func is not None:
                        self.task_stack.append((cur_task_name, next_func))
                if do_action_func is not None:
                    self.task_stack.append((cur_task_name, do_action_func))
                    
                # 短暂让出控制权，避免阻塞事件循环
                await asyncio.sleep(0.01)
            
            # 检查是否是正常完成还是被停止
            if not self._stop_event.is_set():
                # 正常完成
                self._state = self.STATE_STOPPED
                # 通知任务正常完成
                if self._completion_callback:
                    try:
                        self._completion_callback()
                    except Exception as callback_error:
                        self.logger.log(f"完成回调执行失败: {str(callback_error)}", level="ERROR")
            else:
                self._state = self.STATE_STOPPED
        except Exception as e:
            error_msg = f"任务执行过程中发生错误: {str(e)}"
            traceback_str = traceback.format_exc()
            self.logger.log(error_msg, level="ERROR")
            self.logger.log(traceback_str, level="ERROR")
            # 清空任务栈并停止运行
            self.task_stack.clear()
            self._stop_event.set()
            self._pause_event.set()
            self._state = self.STATE_STOPPED
            
            # 调用错误回调函数通知服务器
            if self._error_callback:
                try:
                    self._error_callback(error_msg, traceback_str)
                except Exception as callback_error:
                    self.logger.log(f"错误回调执行失败: {str(callback_error)}", level="ERROR")
            
            raise  # 重新抛出异常，让调用者处理
        finally:
            # 确保在任何情况下都将_worker_task重置为None
            self._worker_task = None
            self.logger.debug("异步任务工作协程结束运行")

    async def pause(self):
        """
        暂停任务执行
        """
        self._pause_event.clear()
        self._state = self.STATE_PAUSED
        self.logger.debug("异步任务流水线已暂停")

    async def resume(self):
        """
        恢复任务执行
        """
        self._pause_event.set()
        self._state = self.STATE_RUNNING
        self.logger.debug("异步任务流水线已恢复")

    async def stop(self):
        """
        停止任务执行
        """
        if self._state == self.STATE_STOPPED:
            self.logger.debug("任务流水线未在运行")
            return
            
        self._stop_event.set()
        self._pause_event.set()
        self._state = self.STATE_STOPPED
        
        if self._worker_task:
            # 等待工作协程结束，但要处理可能的异常
            try:
                await self._worker_task
            except Exception as e:
                self.logger.log(f"工作协程结束时发生异常: {str(e)}", level="ERROR")
            finally:
                self._worker_task = None
            
        # 清空任务栈
        self.task_stack.clear()
        self.logger.debug("异步任务流水线已停止")

    def get_shared_params(self)->None:
        """
        获取共享参数
        """
        # 初始化配置管理器
        config_manager = initialize_configs()
        
        # 从配置管理器加载配置
        exp_cfg = config_manager.get_exp_config()
        thread_cfg = config_manager.get_thread_config()
        mirror_cfg = config_manager.get_mirror_config()
        other_task_cfg = config_manager.get_other_task_config()
        theme_pack_cfg = config_manager.get_theme_pack_config()
        
        self.shared_params = {
            "exp_cfg": exp_cfg,
            "thread_cfg": thread_cfg,
            "mirror_cfg": mirror_cfg,
            "other_task_cfg": other_task_cfg,
            "theme_pack_cfg": theme_pack_cfg,
        }
        self.logger.debug("获取共享参数完成")


# 用于调试的主函数
async def main():
    # 创建异步任务流水线实例
    pipeline = AsyncTaskPipeline()
    
    # 启动流水线
    await pipeline.start("main")
    
    # 运行几秒钟用于测试
    # await asyncio.sleep(5)
    
    # 暂停
    # await pipeline.pause()
    # await asyncio.sleep(2)
    
    # 恢复
    # await pipeline.resume()
    # await asyncio.sleep(20)
    
    # 停止
    # await pipeline.stop()

if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main())