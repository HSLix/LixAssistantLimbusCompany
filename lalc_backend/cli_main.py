"""
CLI 模式入口 — 无需 GUI，直接读取 JSON 配置启动 LALC 任务流水线。

用法:
    python cli_main.py [--task main|semi_auto_main] [--config-dir config]

原理:
    原有的 main.py 依赖 WebSocket 服务器等待 GUI 发送配置。
    cli_main.py 跳过 WebSocket，直接从 JSON 配置文件加载配置，
    然后启动 AsyncTaskPipeline。

配置文件位置（默认 config/ 目录下）:
    - exp_cfg.json        经验本配置
    - thread_cfg.json     纺锤本配置
    - mirror_cfg.json     镜牢配置
    - other_task_cfg.json 其他任务配置
    - theme_pack_cfg.json 主题包配置

无 GUI 时的注意事项:
    - 配置修改需直接编辑 JSON 文件
    - 任务日志输出到终端和 log 文件
    - 如需运行时干预（停止/暂停），CLI 通过 stdin 命令控制
"""
import asyncio
import os
import signal
import sys
import argparse
import threading
from datetime import datetime

# 确保 lalc_backend/ 在 sys.path 中
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

from utils.config_manager import ConfigManager
from utils.logger import init_logger
from workflow.async_task_pipeline import AsyncTaskPipeline
from input.input_handler import input_handler

logger = init_logger()


class CliController:
    """
    命令行控制器 — 替代 ServerController，无 WebSocket。
    
    职责:
    1. 初始化 ConfigManager 并加载 JSON 配置
    2. 创建 AsyncTaskPipeline
    3. 提供 CLI 命令控制（start, stop, pause, resume, status, exit）
    """
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = config_dir
        self.config_manager = ConfigManager(config_dir)
        self.pipeline = AsyncTaskPipeline()
        self._running = False
        self._loop = None
        
        # 将窗口移至屏幕外（防止鼠标干扰）
        logger.info("尝试将游戏窗口移至屏幕外...")
        try:
            input_handler.move_window_offscreen()
            logger.info("游戏窗口已移出屏幕")
        except Exception as e:
            logger.warning(f"移动窗口失败（游戏可能未启动）: {e}")
        
        logger.info("CLI 控制器初始化完成")
    
    def load_config(self):
        """从 JSON 文件加载所有配置。"""
        logger.info(f"从 {self.config_dir}/ 加载配置...")
        self.config_manager.load_configs()
        logger.info("配置加载完成")
    
    async def run(self, entry: str = "main"):
        """启动任务流水线。"""
        if self._running:
            logger.warning("任务流水线已在运行")
            return
        
        self.load_config()
        
        # 设置回调（无 GUI 时仅写日志）
        self.pipeline.set_error_callback(self._on_error)
        self.pipeline.set_completion_callback(self._on_completion)
        
        logger.info(f"启动任务流水线 (entry={entry})")
        self._running = True
        try:
            await self.pipeline.start(entry)
        except asyncio.CancelledError:
            logger.info("任务流水线被取消")
        except Exception as e:
            logger.error(f"任务流水线异常: {e}")
        finally:
            self._running = False
            logger.info("任务流水线已停止")
    
    def stop(self):
        """停止任务流水线。"""
        if self._loop and self._running:
            logger.info("正在停止任务流水线...")
            asyncio.run_coroutine_threadsafe(
                self.pipeline.stop(),
                self._loop
            )
    
    def _on_error(self, error_msg: str, traceback_str: str):
        """错误回调。"""
        logger.error(f"流水线错误: {error_msg}")
        if traceback_str:
            logger.debug(f"错误详情:\n{traceback_str}")
    
    def _on_completion(self):
        """完成回调。"""
        logger.info("任务流水线已完成")
    
    def print_status(self):
        """打印当前状态。"""
        state = self.pipeline.state if hasattr(self.pipeline, 'state') else "unknown"
        print(f"\n=== LALC CLI 状态 ===")
        print(f"  流水线状态: {state}")
        print(f"  运行中: {self._running}")
        print(f"  配置文件: {self.config_dir}/")
        print(f"==================\n")
    
    async def cli_loop(self):
        """
        命令行交互循环 — 读取 stdin 命令。
        
        支持的命令:
            start [task]    启动任务（默认 main）
            stop            停止任务
            status          查看状态
            help            帮助
            exit            退出
        """
        self._loop = asyncio.get_event_loop()
        
        print("\n===== LALC CLI Mode =====")
        print("输入命令 (help 查看帮助)")
        
        while True:
            try:
                cmd_line = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: sys.stdin.readline().strip()
                )
            except (EOFError, KeyboardInterrupt):
                print("\n退出 CLI")
                break
            
            if not cmd_line:
                continue
            
            parts = cmd_line.split()
            cmd = parts[0].lower()
            args = parts[1:]
            
            if cmd == "start":
                entry = args[0] if args else "main"
                asyncio.create_task(self.run(entry))
            elif cmd == "stop":
                self.stop()
            elif cmd == "status":
                self.print_status()
            elif cmd == "help":
                print("""
可用命令:
  start [task]    启动任务 (默认: main, 可选: semi_auto_main)
  stop            停止当前任务
  status          查看流水线状态
  exit / quit     退出 CLI
  help            显示此帮助
                """.strip())
            elif cmd in ("exit", "quit"):
                if self._running:
                    self.stop()
                break
            else:
                print(f"未知命令: {cmd}  (输入 help 查看帮助)")


def main():
    parser = argparse.ArgumentParser(description="LALC CLI Mode — 无需 GUI")
    parser.add_argument("--task", default="main", choices=["main", "semi_auto_main"],
                        help="启动的任务类型 (默认: main)")
    parser.add_argument("--config-dir", default="config",
                        help="配置文件目录 (默认: config)")
    parser.add_argument("--auto-start", action="store_true",
                        help="启动后自动开始任务，不等待命令")
    parser.add_argument("--headless", action="store_true",
                        help="无交互模式 — 启动后自动开始，完成后退出")
    args = parser.parse_args()
    
    controller = CliController(config_dir=args.config_dir)
    
    async def amain():
        if args.auto_start or args.headless:
            await controller.run(args.task)
            if args.headless:
                return  # 完成后直接退出
            # auto_start 模式：任务完成后进入交互模式
            print("\n任务已结束，进入交互模式")
        
        await controller.cli_loop()
    
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        print("\n收到中断信号，退出")
        if controller._running:
            controller.stop()


if __name__ == "__main__":
    main()
