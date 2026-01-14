import asyncio
import logging
from typing import Dict, Any, Callable, Awaitable, Optional
import traceback
from .task_node import TaskNode
from PIL import Image
import matplotlib.pyplot as plt
import io
from .task_execution import TaskExecution, get_server_ref
from utils.logger import init_logger
from utils.config_manager import initialize_configs
from .task_registry import init_tasks, get_task
from input.input_handler import input_handler

# 全局单例槽位
_pipeline_instance: "AsyncTaskPipeline | None" = None
_pipeline_lock = asyncio.Lock()

# 状态常量移到类外
STATE_STOPPED = "stopped"
STATE_RUNNING = "running"
STATE_PAUSED = "paused"

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
        # 添加server引用
        self._server_ref = None

    def set_server_ref(self, server):
        """
        设置服务器引用，用于广播消息
        """
        self._server_ref = server

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

    def _send_finish_notification(self):
        """
        统一发送任务结束通知（plyer 跨平台版）
        经验采光|EXP：xx
        纺锤采光|Thread: xx
        镜像迷宫|Mirror: xx
        """
        # ---------- 广播本轮各任务完成次数 ----------
        from workflow.task_registry import get_task   # 已在文件头部

        counts = {
            "exp":   get_task("exp_check").get_param("execute_count"),
            "thread":get_task("thread_check").get_param("execute_count"),
            "mirror":get_task("mirror_check").get_param("execute_count"),
        }
        # 只要有一个 >0 就发，前端自己决定要不要轮换
        if any(v > 0 for v in counts.values()):
            asyncio.create_task(self._broadcast_task_completion(counts))

        try:
            from workflow.task_registry import get_task  # 延迟导入
            from plyer import notification
            import platform
            import os
            ico_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "MagicAndWonder.ico")
            self.logger.debug(ico_path)

            # 仅 Windows 弹窗；如以后想支持 mac/Linux，直接删掉下面判断即可
            if platform.system() != "Windows":
                self.logger.log("暂时仅支持 Windows 平台的通知", level="WARNING")
                return

            exp_cnt = counts["exp"]
            thd_cnt = counts["thread"]
            mir_cnt = counts["mirror"]

            text = (f"经验采光|EXP：{exp_cnt}\n"
                    f"纺锤采光|Thread: {thd_cnt}\n"
                    f"镜像迷宫|Mirror: {mir_cnt}")

            notification.notify(
                title="LALC 任务结束",
                message=text,
                timeout=10,            # 显示秒数
                app_icon=ico_path,         # 如要换图标，给 .ico 绝对路径即可
                app_name="LALC"
            )
        except Exception as e:
            self.logger.log(f"发送通知失败: {e}", level="WARNING")

    async def _broadcast_task_completion(self, counts: dict[str, int]):
        """
        向所有前端客户端广播本轮任务完成次数。
        消息格式：
        {
          "type": "task_completion",
          "payload": {
            "exp": 1,
            "thread": 0,
            "mirror": 2
          }
        }
        """
        
        if self._server_ref is None:
            self._server_ref = get_server_ref()
        
        if self._server_ref is None:
            self.logger.log(f"远程服务器连接异常，广播任务完成次数失败", level="WARNING")
            return
        
        await self._server_ref.broadcast({
            "type": "task_completion",
            "payload": counts,
        })
        self.logger.log(f"已发送本轮任务完成次数：{counts}")

    @property
    def state(self):
        """
        获取当前任务流水线状态
        :return: 当前状态 (STATE_STOPPED, STATE_RUNNING, STATE_PAUSED)
        """
        return self._state

    def refresh_execute_target_count(self):
        """
        根据 shared params 的内容，把几个 target count 的值给覆盖一下
        """
        for check_name, cfg_name in [("exp_check", "exp_cfg"), ("thread_check", "thread_cfg"), ("mirror_check", "mirror_cfg")]:
            check_task = get_task(check_name)
            check_task.set_param("target_count", self.shared_params[cfg_name]["check_node_target_count"])
            if check_task.get_param("target_count") == 0:
                check_task.get_param("disable_node").enable = False
            
            check_task.set_param('execute_count', 0)

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
        self.refresh_execute_target_count()
        self.logger.debug(f"添加起始任务: {task_name}")

    @classmethod
    async def get(cls) -> "AsyncTaskPipeline":
        """线程安全的全局单例获取"""
        global _pipeline_instance
        async with _pipeline_lock:
            if _pipeline_instance is None:
                _pipeline_instance = AsyncTaskPipeline()
            return _pipeline_instance
    
    async def reset(self):
        """彻底重置到初始状态（用于客户端重连后想重开）"""
        await self.stop()  # 先停
        async with _pipeline_lock:
            global _pipeline_instance
            _pipeline_instance = None
        

    async def start(self, entry: str):
        """启动任务流水线"""
        input_handler.reset()
        if self._state != STATE_STOPPED:
            self.logger.debug("任务线未处于 STOPPED，忽略本次 start")
            return
            
        self._state = STATE_RUNNING
        self.add_start_task(entry)
        
        if self._worker_task and not self._worker_task.done():
            self.logger.warning("Worker task still running, cancelling...")
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError as e:
                raise e
        
        self._worker_task = asyncio.create_task(self._worker())
        self.logger.log(f"任务流水线已启动，入口节点：{entry}")

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
            # ---------- TaskExecution handler 性能统计（一条 log） ----------
            if self.task_execution:          # 确保已实例化
                perf = self.task_execution.get_perf_summary()
                if perf:
                    parts = []
                    for name, data in perf.items():
                        cnt   = data["count"]
                        total = data["total"]
                        avg   = total / cnt if cnt else 0
                        parts.append(f"{name}:{cnt}次 {total:.3f}s {avg:.3f}s/次")

                    # 生成性能统计图表
                    try:
                        # 使用新函数生成图表
                        chart_image = self._generate_performance_chart(perf)
                    except Exception as e:
                        self.logger.log(f"性能统计表格生成过程发生错误: {str(e)}", level="ERROR")

                    self.logger.debug("TaskExecution 性能统计 | " + " | ".join(parts), chart_image)
                    
                    

    def _generate_performance_chart(self, perf_data: dict) -> Image.Image:
        """
        生成性能统计图表，返回PIL Image对象
        :param perf_data: 性能统计数据，格式为 {handler_name: {"count": int, "total": float}}
        :return: PIL Image对象，包含上下两个图表
        """
        # 创建图表，设置合适的大小
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        
        # 按总耗时排序，取前10
        sorted_by_time = sorted(perf_data.items(), key=lambda x: x[1]['total'], reverse=True)[:10]
        if sorted_by_time:
            names_time = [item[0] for item in sorted_by_time]
            times = [item[1]['total'] for item in sorted_by_time]
            
            ax1.bar(names_time, times)
            ax1.set_title('Top 10 Tasks by Total Execution Time')
            ax1.set_xlabel('Task Name')
            ax1.set_ylabel('Total Time (s)')
            plt.setp(ax1.get_xticklabels(), rotation=45, ha="right")

        # 如果没有数据，显示提示信息
        else:
            ax1.text(0.5, 0.5, 'No data available', horizontalalignment='center', verticalalignment='center',
                     transform=ax1.transAxes, fontsize=14)
            ax1.set_title('Top 10 Tasks by Total Execution Time')

        # 按调用次数排序，取前10
        sorted_by_count = sorted(perf_data.items(), key=lambda x: x[1]['count'], reverse=True)[:10]
        if sorted_by_count:
            names_count = [item[0] for item in sorted_by_count]
            counts = [item[1]['count'] for item in sorted_by_count]
            
            ax2.bar(names_count, counts)
            ax2.set_title('Top 10 Tasks by Call Count')
            ax2.set_xlabel('Task Name')
            ax2.set_ylabel('Call Count')
            plt.setp(ax2.get_xticklabels(), rotation=45, ha="right")
        # 如果没有数据，显示提示信息
        else:
            ax2.text(0.5, 0.5, 'No data available', horizontalalignment='center', verticalalignment='center',
                     transform=ax2.transAxes, fontsize=14)
            ax2.set_title('Top 10 Tasks by Call Count')

        # 调整布局，防止标签被截断
        plt.tight_layout()
        
        # 将图表转换为PIL Image对象
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        img = Image.open(buf)
        
        # 关闭图表以释放内存
        plt.close(fig)
        
        return img

    async def pause(self):
        """
        暂停任务执行
        """
        input_handler.pause()
        self._pause_event.clear()
        self._state = self.STATE_PAUSED
        self.logger.debug("异步任务流水线已暂停")

    async def resume(self):
        """
        恢复任务执行
        """
        input_handler.resume()
        self._pause_event.set()
        self._state = self.STATE_RUNNING
        self.logger.debug("异步任务流水线已恢复")

    async def stop(self):
        """停止任务流水线"""
        if self._state == STATE_STOPPED:
            self.logger.debug("任务线已停止，无需重复 stop")
            return

        input_handler.stop()
        await self.resume()
            
        self._state = STATE_STOPPED
        if self._worker_task:
            if not self._worker_task.done():
                self.logger.log("正在取消 worker 任务...")
                self._worker_task.cancel()
                try:
                    await self._worker_task
                except asyncio.CancelledError:
                    self.logger.log("Worker 任务已取消")
            self._worker_task = None
        self.logger.log("任务流水线已停止")

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