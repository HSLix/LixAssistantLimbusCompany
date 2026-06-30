import asyncio
import logging
from typing import Dict, Any, Callable, Awaitable, Optional
import traceback
import random
import time
import hashlib
import numpy as np
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


# ── 屏幕变化检测 ──────────────────────────────────────
class ScreenChangeDetector:
    """轻量屏变化检测：用中心区域像素 hash 判断画面是否推进。
    
    debug 级模板匹配 (≈50ms) 比实际游戏资源加载 (≈3-5s) 快得多。
    屏幕未变时跳过全部模板匹配，避免浪费。
    """
    # 检测区域：取画面中央 300×200 区域（避开边缘装饰、固定UI）
    CROP_X = 490
    CROP_Y = 260
    CROP_W = 300
    CROP_H = 200

    def __init__(self):
        self._last_hash: str | None = None
        self._unchanged_ticks = 0

    def check(self, screenshot: Image.Image) -> bool:
        """检查画面是否变化。返回 True = 变了 / 首次检测。"""
        w, h = screenshot.size
        cx, cy = w // 2, h // 2
        left = max(0, cx - self.CROP_W // 2)
        top = max(0, cy - self.CROP_H // 2)
        crop = screenshot.crop((left, top, left + self.CROP_W, top + self.CROP_H))

        # 转灰度后感知 hash（尺寸固定到 32×32 消除缩放噪声）
        gray = crop.convert("L").resize((32, 32), Image.LANCZOS)
        h = hashlib.md5(gray.tobytes()).hexdigest()

        if self._last_hash is None:
            self._last_hash = h
            self._unchanged_ticks = 0
            return True  # 首次检测视为变化

        if h == self._last_hash:
            self._unchanged_ticks += 1
            return False
        else:
            self._last_hash = h
            self._unchanged_ticks = 0
            return True

    @property
    def stale_ticks(self) -> int:
        """连续未变化的 tick 数。"""
        return self._unchanged_ticks


# ── 真人节奏模拟 ──────────────────────────────────────
class HumanTiming:
    """模拟真人操作节奏。
    
    核心原则：
    - debug 模板匹配的耗时 (≈50ms) ≠ 游戏实际加载资源的耗时 (≈3-5s)
    - 脚本不应比真人反应更快——快过人类的频率不能提升效率，只会浪费 CPU
    - 真人操作间隔呈正态分布，不是均匀随机
    """

    # 不同操作类型的基准延迟（秒），行动前等待
    ACTION_DELAYS = {
        "click":        (0.25, 0.8),    # 点击后等待画面响应
        "key":          (0.20, 0.6),    # 按键后等待
        "swipe":        (0.40, 1.0),    # 滑动后等待
        "wait_check":   (1.50, 3.0),    # 等待资源加载后的确认检查
        "idle_poll":    (2.50, 5.0),    # 纯轮询（error_handler 等无事可做时）
    }

    @staticmethod
    def delay(action_type: str = "click") -> float:
        """生成真人节奏延迟。
        
        使用截断正态分布（clamp 在 [min*0.5, max*2]）。
        """
        if action_type not in HumanTiming.ACTION_DELAYS:
            action_type = "click"
        mu, sigma = HumanTiming.ACTION_DELAYS[action_type]
        # 用 Box-Muller 近似正态，截断到合理范围
        d = random.gauss(mu, sigma * 0.35)
        lower = mu * 0.5
        upper = mu + sigma * 3.0
        return max(lower, min(upper, d))

    @staticmethod
    def action_jitter(base: int = 5) -> int:
        """坐标/偏移抖动：模拟人手点击的物理不精确性。
        
        返回 ±base 范围内的随机偏移（正态分布集中在中心附近）。
        """
        return int(round(random.gauss(0, base * 0.5)))


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
        
        # ── 状态机模式 ──
        self._use_state_machine = False  # 由 config 控制开关
        
        # ── 轮询优化组件 ──
        self._screen_detector = ScreenChangeDetector()
        self._last_action_time = time.time()

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
                self.logger.warning("暂时仅支持 Windows 平台的通知")
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
            self.logger.warning(f"发送通知失败: {e}")

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
            self.logger.warning(f"远程服务器连接异常，广播任务完成次数失败")
            return
        
        await self._server_ref.broadcast({
            "type": "task_completion",
            "payload": counts,
        })
        self.logger.info(f"已发送本轮任务完成次数：{counts}")

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
        self.logger.info(f"任务流水线已启动，入口节点：{entry}")

    async def _worker(self):
        """
        异步工作协程，不断处理任务栈中的函数
        
        支持两种模式：
        - 旧模式（默认）：基于任务栈的轮询循环
        - 状态机模式：基于转换表的确定性驱动
        """
        # ── 状态机模式 ──
        if self._use_state_machine:
            await self._run_state_machine()
            return
        
        self.logger.debug("异步任务工作协程开始运行")
        try:
            while self.task_stack and not self._stop_event.is_set():
                # 检查是否处于暂停状态
                await self._pause_event.wait()
                
                # ── 轮询节流：屏幕未变时放慢速度 ──
                # debug 模板匹配 ≈50ms, 游戏资源加载 ≈3-5s
                # 屏幕没变说明游戏尚未响应，不应高速轮询
                elapsed = time.time() - self._last_action_time
                try:
                    shot = input_handler.capture_screenshot()
                    screen_changed = self._screen_detector.check(shot)
                except Exception:
                    screen_changed = True  # 截图失败时保守假定有变化
                
                if not screen_changed and elapsed < 2.0:
                    # 屏幕没变且刚操作过 → 极可能游戏在加载中
                    # 用人类观察间隔等待，不做模板匹配
                    idle_wait = HumanTiming.delay("idle_poll")
                    self.logger.debug(
                        f"画面未变化 ({self._screen_detector.stale_ticks} ticks), "
                        f"等待 {idle_wait:.1f}s"
                    )
                    await asyncio.sleep(idle_wait)
                    continue  # 跳过本轮 execute，不进模板匹配
                
                # print(self.task_stack)
                
                # 弹出栈顶的函数
                pre_task_name, func = self.task_stack.pop()
                
                # 执行函数
                cur_task_name, do_action_func, *get_next_funcs = await asyncio.get_event_loop().run_in_executor(
                    None, self.task_execution.execute, pre_task_name, func
                )
                
                # 记录本次操作时间（供屏幕变化检测节流用）
                self._last_action_time = time.time()
                
                # 压栈规则：先压 get_next_func，再压 do_action_func
                for next_func in reversed(get_next_funcs):
                    if next_func is not None:
                        self.task_stack.append((cur_task_name, next_func))
                if do_action_func is not None:
                    self.task_stack.append((cur_task_name, do_action_func))
                
                # ── 真人节奏延迟 ──
                # 执行完一次操作后，按人类反应速度等待再继续
                # 缩短 sleep 时间（检测到动作推进画面后很快就 Check）
                await asyncio.sleep(0.05)
            
            # 检查是否是正常完成还是被停止
            if not self._stop_event.is_set():
                # 正常完成
                await self.stop()
                # 通知任务正常完成
                if self._completion_callback:
                    try:
                        self._completion_callback()
                    except Exception as callback_error:
                        self.logger.error(f"完成回调执行失败: {str(callback_error)}")
                
            else:
                self._state = self.STATE_STOPPED
        except Exception as e:
            error_msg = f"任务执行过程中发生错误: {str(e)}"
            traceback_str = traceback.format_exc()
            self.logger.error(error_msg)
            self.logger.error(traceback_str)
            
            # 调用错误回调函数通知服务器
            if self._error_callback:
                try:
                    self._error_callback(error_msg, traceback_str)
                except Exception as callback_error:
                    self.logger.error(f"错误回调执行失败: {str(callback_error)}")
            
            await self.stop()
            
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
                        self.logger.error(f"性能统计表格生成过程发生错误: {str(e)}")
                        
                    try:
                        self.logger.debug("TaskExecution 性能统计 | " + " | ".join(parts), chart_image)
                    except UnboundLocalError:
                        self.logger.debug("TaskExecution 性能统计 | " + " | ".join(parts))

    async def _run_state_machine(self):
        """状态机模式：构建转换表，用 GameStateMachine 驱动。
        
        只跑一次流水线，完成后 stop。
        """
        try:
            self.logger.info("状态机模式启动")
            
            # 1. 从现有 shared_params 提取配置
            from state_machine.transitions import build_daily_flow
            from state_machine.engine import GameStateMachine, MachineContext
            
            # 根据执行次数构建转换表
            check_config = {
                "exp_count": get_task("exp_check").get_param("execute_count"),
                "thread_count": get_task("thread_check").get_param("execute_count"),
                "mirror_count": get_task("mirror_check").get_param("execute_count"),
            }
            transitions = build_daily_flow(check_config)
            
            if not transitions:
                self.logger.info("无任务需要执行（所有 count 为 0）")
                return
            
            self.logger.info(f"构建转换表：{len(transitions)} 个状态转换")
            
            # 2. 创建上下文和引擎
            context = MachineContext(self.task_execution, self.shared_params)
            machine = GameStateMachine(context)
            
            # 3. 运行
            error = machine.run(transitions)
            
            if error:
                self.logger.error(f"状态机运行错误: {error}")
            else:
                self.logger.info("状态机运行完成")
                
        except Exception as e:
            self.logger.error(f"状态机运行异常: {e}")
            self.logger.error(traceback.format_exc())
        finally:
            await self.stop()
            if self._completion_callback:
                try:
                    self._completion_callback()
                except Exception as cb_err:
                    self.logger.error(f"完成回调失败: {cb_err}")

    def _generate_performance_chart(self, perf_data: dict) -> Image.Image:
        """
        生成性能统计图表，返回PIL Image对象
        :param perf_data: 性能统计数据，格式为 {handler_name: {"count": int, "total": float, "avg": float}}
        :return: PIL Image对象，包含三个图表
        """
        # 创建图表，设置合适的大小，包含三个子图
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 15))
        
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

        # 按平均耗时排序，取前10，从高到低
        sorted_by_avg = sorted(perf_data.items(), key=lambda x: x[1]['avg'], reverse=True)[:10]
        if sorted_by_avg:
            names_avg = [item[0] for item in sorted_by_avg]
            avgs = [item[1]['avg'] for item in sorted_by_avg]
            
            ax3.bar(names_avg, avgs)
            ax3.set_title('Top 10 Tasks by Average Execution Time (High to Low)')
            ax3.set_xlabel('Task Name')
            ax3.set_ylabel('Average Time (s)')
            plt.setp(ax3.get_xticklabels(), rotation=45, ha="right")
        # 如果没有数据，显示提示信息
        else:
            ax3.text(0.5, 0.5, 'No data available', horizontalalignment='center', verticalalignment='center',
                     transform=ax3.transAxes, fontsize=14)
            ax3.set_title('Top 10 Tasks by Average Execution Time')

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

        self._send_finish_notification()
            
        self._state = STATE_STOPPED
        if self._worker_task:
            if not self._worker_task.done():
                self.logger.info("正在取消 worker 任务...")
                self._worker_task.cancel()
                try:
                    await self._worker_task
                except asyncio.CancelledError:
                    self.logger.info("Worker 任务已取消")
            self._worker_task = None
        self.logger.info("任务流水线已停止")

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