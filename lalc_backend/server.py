import asyncio
import websockets
import json
import uuid
import logging
import traceback
from typing import Set, Dict, Any, Optional
from datetime import datetime


from workflow.async_task_pipeline import AsyncTaskPipeline

from utils.logger import init_logger
from utils.encrypt_decrypt import decrypt_cdk
from input.input_handler import input_handler


# -------------------- WebSocket 服务器 --------------------
class ServerController:
    """
    接收的消息type 为 request 和 heartbeat
    回复的消息 type 为 response，error 和 heartbeat_ack
    """

    def __init__(self):
        from workflow.task_execution import set_server_ref   # 刚才写的注入函数
        set_server_ref(self)
        
        # 初始化配置管理器，使用相对于server.py的config目录
        from utils.config_manager import init_config_manager
        self.config_manager = init_config_manager("config")
        
        self.pipeline = AsyncTaskPipeline()
        self.pipeline.set_error_callback(self._on_pipeline_error)
        self.pipeline.set_completion_callback(self._on_pipeline_completion)
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self._req_futures: Dict[str, asyncio.Future] = {}   # 用于 request/response 匹配
        self.lalc_logger = init_logger()
        self.loop = None  # 添加事件循环引用
        self.received_configs = {}  # 存储接收到的配置
        self._timeout_task = None  # 超时检查任务
        self._last_client_disconnect_time = None  # 最后一个客户端断开连接的时间
        self._should_exit = False  # 退出标志
        self._download_task: Optional[asyncio.Task] = None   # 当前下载任务
        self._download_future: Optional[asyncio.Future] = None  # 下载结果 future

    def _on_pipeline_error(self, error_msg: str, traceback_str: str):
        """
        当任务流水线发生错误时的回调函数
        """
        # 在事件循环中执行广播错误信息
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(self._broadcast_error(error_msg, traceback_str))
        else:
            loop.run_until_complete(self._broadcast_error(error_msg, traceback_str))

    def _on_pipeline_completion(self):
        """
        当任务流水线正常完成时的回调函数
        """
        # 在事件循环中执行广播完成信息
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(self._broadcast_completion())
        else:
            loop.run_until_complete(self._broadcast_completion())

    async def _broadcast_error(self, error_msg: str, traceback_str: str):
        """
        广播错误信息给所有连接的客户端
        """
        error_data = {
            "type": "error",
            "payload": {
                "status": "error",
                "message": error_msg,
                "traceback": traceback_str
            }
        }
        await self.broadcast(error_data)

    async def _broadcast_completion(self):
        """
        广播任务完成信息给所有连接的客户端
        """
        completion_data = {
            "type": "task_log",
            "payload": {
                "status": "completed",
                "message": "任务已正常完成"
            }
        }
        await self.broadcast(completion_data)

    # 新增广播函数
    async def broadcast_task_log(self, msg: str):
        await self.broadcast({
            "type": "task_log",
            "payload": {
                "level": "INFO",
                "message": msg
            }
        })

    # ---------- 工具 ----------
    async def send_json(self, ws: websockets.WebSocketServerProtocol, data: dict):
        await ws.send(json.dumps(data))

    async def broadcast(self, data: dict):
        if self.clients:
            await asyncio.gather(*(self.send_json(c, data) for c in self.clients), return_exceptions=True)

    def convert_frontend_config_to_backend_format(self, frontend_config: dict) -> dict:
        """
        将前端传来的配置转换为后端ConfigManager使用的格式
        :param frontend_config: 前端传来的配置
        :return: 转换后的配置字典
        """
        backend_config = {
            "exp_cfg": {},
            "thread_cfg": {},
            "mirror_cfg": {},
            "other_task_cfg": {},
            "theme_pack_cfg": {}
        }
        
        # 处理taskConfigs
        task_configs = frontend_config.get("taskConfigs", {})
        
        # EXP配置转换
        exp_config = task_configs.get("EXP", {})
        if exp_config:
            # enabled为false时，check_node_target_count设为0，否则使用count值
            backend_config["exp_cfg"]["check_node_target_count"] = \
                exp_config.get("count", 0) if exp_config.get("enabled", False) else 0
            
            # 处理params中的参数
            exp_params = exp_config.get("params", {})
            # luxcavationMode映射到luxcavation_mode
            if "luxcavationMode" in exp_params:
                backend_config["exp_cfg"]["luxcavation_mode"] = exp_params["luxcavationMode"].lower()
            # expStage映射到exp_stage
            if "expStage" in exp_params:
                backend_config["exp_cfg"]["exp_stage"] = exp_params["expStage"]
        
        # Thread配置转换
        thread_config = task_configs.get("Thread", {})
        if thread_config:
            # enabled为false时，check_node_target_count设为0，否则使用count值
            backend_config["thread_cfg"]["check_node_target_count"] = \
                thread_config.get("count", 0) if thread_config.get("enabled", False) else 0
            
            # 处理params中的参数
            thread_params = thread_config.get("params", {})
            # luxcavationMode映射到luxcavation_mode
            if "luxcavationMode" in thread_params:
                backend_config["thread_cfg"]["luxcavation_mode"] = thread_params["luxcavationMode"].lower()
            # threadStage映射到thread_stage
            if "threadStage" in thread_params:
                backend_config["thread_cfg"]["thread_stage"] = thread_params["threadStage"]
                
        # Mirror配置转换
        mirror_config = task_configs.get("Mirror", {})
        if mirror_config:
            # enabled为false时，check_node_target_count设为0，否则使用count值
            backend_config["mirror_cfg"]["check_node_target_count"] = \
                mirror_config.get("count", 0) if mirror_config.get("enabled", False) else 0
            
            # 处理params中的参数
            mirror_params = mirror_config.get("params", {})
            # stopPurchaseGiftMoney映射到mirror_stop_purchase_gift_money
            if "stopPurchaseGiftMoney" in mirror_params:
                backend_config["mirror_cfg"]["mirror_stop_purchase_gift_money"] = mirror_params["stopPurchaseGiftMoney"]
        
        # 处理teamConfigs
        team_configs = frontend_config.get("teamConfigs", {})
        
        # 为EXP、Thread、Mirror配置队伍信息
        for task_type, config in [("EXP", exp_config), ("Thread", thread_config), ("Mirror", mirror_config)]:
            if config and "teams" in config:
                teams = config["teams"]
                team_orders = []
                team_indexes = []
                
                for team_index in teams:
                    team_key = str(team_index - 1)  # 前端队伍索引从1开始，后端从0开始
                    if team_key in team_configs:
                        team_config = team_configs[team_key]
                        # 获取选中的成员
                        selected_members = team_config.get("selectedMembers", [])
                        team_orders.append(selected_members)
                        team_indexes.append(team_index)
                        
                        # 特殊处理Mirror相关的队伍配置
                        if task_type == "Mirror":
                            # 队伍风格
                            if "selectedStyleType" in team_config:
                                if "mirror_team_styles" not in backend_config["mirror_cfg"]:
                                    backend_config["mirror_cfg"]["mirror_team_styles"] = []
                                backend_config["mirror_cfg"]["mirror_team_styles"].append(team_config["selectedStyleType"])
                            
                            # 偏好EGO饰品类型
                            if "selectedPreferEgoGiftTypes" in team_config:
                                if "mirror_team_ego_gift_styles" not in backend_config["mirror_cfg"]:
                                    backend_config["mirror_cfg"]["mirror_team_ego_gift_styles"] = []
                                backend_config["mirror_cfg"]["mirror_team_ego_gift_styles"].append(team_config["selectedPreferEgoGiftTypes"])
                                
                            # EGO饰品白名单和黑名单
                            if "giftName2Status" in team_config:
                                allow_list = []
                                block_list = []
                                for gift_name, status in team_config["giftName2Status"].items():
                                    if status == "Allow List":
                                        allow_list.append(gift_name)
                                    elif status == "Block List":
                                        block_list.append(gift_name)
                                        
                                if "mirror_team_ego_allow_list" not in backend_config["mirror_cfg"]:
                                    backend_config["mirror_cfg"]["mirror_team_ego_allow_list"] = []
                                backend_config["mirror_cfg"]["mirror_team_ego_allow_list"].append(allow_list)
                                
                                if "mirror_team_ego_block_list" not in backend_config["mirror_cfg"]:
                                    backend_config["mirror_cfg"]["mirror_team_ego_block_list"] = []
                                backend_config["mirror_cfg"]["mirror_team_ego_block_list"].append(block_list)
                                
                            # 技能替换配置
                            if "skillReplacementEnabled" in team_config and "skillReplacementOrders" in team_config:
                                replace_skill = {}
                                sinners = ["Yi Sang", "Faust", "Don Quixote", "Ryoshu", "Meursault", 
                                          "Hong Lu", "Heathcliff", "Ishmael", "Rodion", "Sinclair", "Outis", "Gregor"]
                                for sinner in sinners:
                                    # 只处理启用的罪人
                                    if team_config["skillReplacementEnabled"].get(sinner, False):
                                        orders = team_config["skillReplacementOrders"].get(sinner, [])
                                        if orders:
                                            # 根据技能替换顺序映射到数字
                                            # [1, 2] -> 1, [2, 3] -> 2, [1, 3] -> 3
                                            skill_order = []
                                            for order in orders:
                                                if order == [1, 2]:
                                                    skill_order.append(1)
                                                elif order == [2, 3]:
                                                    skill_order.append(2)
                                                elif order == [1, 3]:
                                                    skill_order.append(3)
                                            
                                            if skill_order:
                                                replace_skill[sinner] = skill_order
                                                
                                if "mirror_replace_skill" not in backend_config["mirror_cfg"]:
                                    backend_config["mirror_cfg"]["mirror_replace_skill"] = []
                                backend_config["mirror_cfg"]["mirror_replace_skill"].append(replace_skill)
                                
                            # 商店治疗配置
                            if "shopHealAll" in team_config:
                                if "mirror_shop_heal" not in backend_config["mirror_cfg"]:
                                    backend_config["mirror_cfg"]["mirror_shop_heal"] = []
                                backend_config["mirror_cfg"]["mirror_shop_heal"].append(team_config["shopHealAll"])
                                
                            # 初始EGO饰品选择顺序
                            if "initialEgoGifts" in team_config:
                                if "mirror_team_initial_ego_orders" not in backend_config["mirror_cfg"]:
                                    backend_config["mirror_cfg"]["mirror_team_initial_ego_orders"] = []
                                backend_config["mirror_cfg"]["mirror_team_initial_ego_orders"].append(team_config["initialEgoGifts"])
                                
                            # 星光配置
                            if "mirrorStarEnabled" in team_config and "mirrorStarValues" in team_config:
                                stars = []
                                for star_index, enabled in team_config["mirrorStarEnabled"].items():
                                    if enabled and star_index in team_config["mirrorStarValues"]:
                                        stars.append(team_config["mirrorStarValues"][star_index])
                                if "mirror_team_stars" not in backend_config["mirror_cfg"]:
                                    backend_config["mirror_cfg"]["mirror_team_stars"] = []
                                backend_config["mirror_cfg"]["mirror_team_stars"].append(stars)
                
                # 将队伍信息添加到对应的任务配置中
                cfg_key = task_type.lower() + "_cfg"
                backend_config[cfg_key]["team_orders"] = team_orders
                backend_config[cfg_key]["team_indexes"] = team_indexes
                
        # 处理主题包权重配置
        theme_pack_weights = frontend_config.get("themePackWeights", {})
        for theme_pack_name, weight in theme_pack_weights.items():
            backend_config["theme_pack_cfg"][theme_pack_name] = {"weight": weight}
            
        # 处理其他配置
        daily_lunacy_purchase = task_configs.get("Daily Lunacy Purchase", {})
        if daily_lunacy_purchase:
            backend_config["other_task_cfg"]["lunary_purchase_target"] = \
                daily_lunacy_purchase.get("count", 0) if daily_lunacy_purchase.get("enabled", False) else 0
        backend_config["other_task_cfg"]["test_mode"] = False
        
        return backend_config

    async def _check_timeout(self):
        """
        检查是否超时，如果超过一定的时间没有客户端连接则关闭服务器
        """
        outdate_time = 10
        while True:
            await asyncio.sleep(1)
            
            # 如果还有客户端连接，则重置断开时间
            if self.clients:
                self._last_client_disconnect_time = None
                continue
                
            # 如果没有客户端连接
            if not self._last_client_disconnect_time:
                self._last_client_disconnect_time = datetime.now()
                continue
                
            # 检查是否超时
            elapsed = datetime.now() - self._last_client_disconnect_time
            if elapsed.total_seconds() >= outdate_time:
                self.lalc_logger.log(f"服务器超时自动关闭：超过{outdate_time}秒无客户端连接")
                # 停止任务流水线
                await self.pipeline.stop()
                # 关闭服务器
                if self.server:
                    self.server.close()
                    await self.server.wait_closed()
                # 设置退出标志
                self._should_exit = True
                break

    # ---------- 业务路由 ----------
    async def handle_command(self, ws: websockets.WebSocketServerProtocol, cmd: str, msg_id: str, args_list=None):
        base_cmd = cmd
        # 如果客户端已经拆好，就直接用
        if args_list is not None:
            args = args_list
        
        try:
            if base_cmd == "start":
                # 打印接收到的配置
                self.lalc_logger.debug(f"接收到的配置: {json.dumps(self.received_configs, ensure_ascii=False)}")
                
                # 转换配置格式并更新到ConfigManager
                if self.received_configs:
                    converted_config = self.convert_frontend_config_to_backend_format(self.received_configs)
                    self.lalc_logger.debug(f"转换后的配置: {json.dumps(converted_config, ensure_ascii=False)}")
                    
                    # 使用实例化的config_manager更新配置
                    if "exp_cfg" in converted_config and converted_config["exp_cfg"]:
                        self.config_manager.update_exp_config(converted_config["exp_cfg"])
                    if "thread_cfg" in converted_config and converted_config["thread_cfg"]:
                        self.config_manager.update_thread_config(converted_config["thread_cfg"])
                    if "mirror_cfg" in converted_config and converted_config["mirror_cfg"]:
                        self.config_manager.update_mirror_config(converted_config["mirror_cfg"])
                    if "other_task_cfg" in converted_config and converted_config["other_task_cfg"]:
                        self.config_manager.update_other_task_config(converted_config["other_task_cfg"])
                    if "theme_pack_cfg" in converted_config and converted_config["theme_pack_cfg"]:
                        self.config_manager.update_theme_pack_config(converted_config["theme_pack_cfg"])
                    
                    # 保存配置到文件
                    self.config_manager.save_configs()
                
                input_handler.reset() 
                await self.pipeline.start("main")
                await self.send_json(ws, {"type": "response", "id": msg_id, "payload": {"status": "success", "message": "started"}})
                self.lalc_logger.debug(f"收到 start 命令，已启动任务流水线")
            elif base_cmd == "get_latest_version":
                from utils.update_manager import get_latest_version
                version = get_latest_version()
                await self.send_json(ws, {
                    "type": "response", 
                    "id": msg_id, 
                    "payload": {
                        "status": "success", 
                        "type": "version_info",
                        "version": version
                    }
                })
                self.lalc_logger.debug(f"获取最新版本号: {version}")
            elif base_cmd == "download_from_github":
                # 默认下载路径为当前目录
                download_path = args[0] if args else "."
                
                # 如果前一条下载还没完，直接拒绝
                if self._download_task and not self._download_task.done():
                    await self.send_json(ws, {
                        "type": "response", 
                        "id": msg_id, 
                        "payload": {"status": "error", "message": "已有下载任务进行中，请先 cancel_download"}
                    })
                    return
                
                from utils.update_manager import download_lalc_release_asset
                
                def _progress(p):
                    asyncio.run_coroutine_threadsafe(
                        self.send_json(ws, {
                            "type": "response", 
                            "id": msg_id, 
                            "payload": {
                                "status": "progress", 
                                "type": "download_progress",
                                "progress": p
                            }
                        }),
                        self.loop
                    )
                
                # 启动可取消任务
                task, file_path = download_lalc_release_asset(
                    download_path,
                    _progress
                )
                self._download_task = task

                # 用 asyncio.create_task 把「下载+完成广播」包在一起，
                # 防止 handle_command 本身被挂起
                async def _wrap():
                    try:
                        result = await task
                        await self.send_json(ws, {
                            "type": "response", 
                            "id": msg_id, 
                            "payload": {
                                "status": "success", 
                                "type": "download_complete",
                                "file_path": result
                            }
                        })
                        self.lalc_logger.debug(f"从GitHub下载完成: {result}")
                    except asyncio.CancelledError:
                        # 用户主动取消
                        self.lalc_logger.debug("下载已被取消")
                        await self.send_json(ws, {
                            "type": "response", 
                            "id": msg_id, 
                            "payload": {
                                "status": "cancelled", 
                                "type": "download_cancelled"
                            }
                        })
                    except Exception as e:
                        self.lalc_logger.debug(f"下载失败: {e}", level="ERROR")
                        await self.send_json(ws, {
                            "type": "response", 
                            "id": msg_id, 
                            "payload": {
                                "status": "error", 
                                "message": str(e)
                            }
                        })
                    finally:
                        self._download_task = None
                
                asyncio.create_task(_wrap())
            elif base_cmd == "download_from_mirrorchan":
                # 默认下载路径为当前目录，第二个参数是CDK
                download_path = args[0] if args else "."
                cdk = args[1] if len(args) > 1 else None
                print(f"cdk:{cdk}")
                cdk = decrypt_cdk(cdk)
                print(f"decrypt_cdk:{cdk}")
                
                # 检查CDK是否为空
                self.lalc_logger.debug(f"目标下载地址：{download_path}; cdk:{cdk}")
                if not cdk:
                    self.lalc_logger.debug("CDK为空，无法下载")
                    await self.send_json(ws, {
                        "type": "response", 
                        "id": msg_id, 
                        "payload": {
                            "status": "error", 
                            "message": "CDK为空，无法下载"
                        }
                    })
                    return
                
                # 如果前一条下载还没完，直接拒绝
                if self._download_task and not self._download_task.done():
                    await self.send_json(ws, {
                        "type": "response", 
                        "id": msg_id, 
                        "payload": {"status": "error", "message": "已有下载任务进行中，请先 cancel_download"}
                    })
                    return
                
                from utils.update_manager import download_lalc_from_mirrorchan
                
                def _progress(p):
                    asyncio.run_coroutine_threadsafe(
                        self.send_json(ws, {
                            "type": "response", 
                            "id": msg_id, 
                            "payload": {
                                "status": "progress", 
                                "type": "download_progress",
                                "progress": p
                            }
                        }),
                        self.loop
                    )
                
                # 启动可取消任务
                task, file_path = download_lalc_from_mirrorchan(
                    download_path,
                    cdk,
                    None,  # current_version
                    _progress
                )
                self._download_task = task

                # 用 asyncio.create_task 把「下载+完成广播」包在一起，
                # 防止 handle_command 本身被挂起
                async def _wrap():
                    try:
                        result = await task
                        await self.send_json(ws, {
                            "type": "response", 
                            "id": msg_id, 
                            "payload": {
                                "status": "success", 
                                "type": "download_complete",
                                "file_path": result
                            }
                        })
                        self.lalc_logger.debug(f"从mirrorchan下载完成: {result}")
                    except asyncio.CancelledError:
                        # 用户主动取消
                        self.lalc_logger.debug("下载已被取消")
                        await self.send_json(ws, {
                            "type": "response", 
                            "id": msg_id, 
                            "payload": {
                                "status": "cancelled", 
                                "type": "download_cancelled"
                            }
                        })
                    except Exception as e:
                        self.lalc_logger.debug(f"下载失败: {e}", level="ERROR")
                        await self.send_json(ws, {
                            "type": "response", 
                            "id": msg_id, 
                            "payload": {
                                "status": "error", 
                                "message": str(e)
                            }
                        })
                    finally:
                        self._download_task = None
                
                asyncio.create_task(_wrap())
            elif base_cmd == "cancel_download":
                if self._download_task and not self._download_task.done():
                    self._download_task.cancel()
                    await self.send_json(ws, {
                        "type": "response", 
                        "id": msg_id, 
                        "payload": {"status": "success", "message": "已请求取消下载"}
                    })
                else:
                    await self.send_json(ws, {
                        "type": "response", 
                        "id": msg_id, 
                        "payload": {"status": "error", "message": "当前没有进行中的下载任务"}
                    })
            elif base_cmd == "pause":
                await self.pipeline.pause()
                input_handler.pause()
                await self.send_json(ws, {"type": "response", "id": msg_id, "payload": {"status": "success", "message": "paused"}})
                self.lalc_logger.debug(f"收到 pause 命令，已暂停任务流水线")
            elif base_cmd == "resume":
                await self.pipeline.resume()
                input_handler.resume()
                await self.send_json(ws, {"type": "response", "id": msg_id, "payload": {"status": "success", "message": "resumed"}})
                self.lalc_logger.debug(f"收到 resume 命令，已恢复任务流水线")
            elif base_cmd == "stop":
                await self.pipeline.stop()
                input_handler.stop()
                await self.send_json(ws, {"type": "response", "id": msg_id, "payload": {"status": "success", "message": "stopped"}})
                self.lalc_logger.debug(f"收到 stop 命令，已停止任务流水线")
            elif base_cmd == "shutdown_pc":
                import subprocess
                import sys
                # 在Windows上使用shutdown命令设置1分钟后关机
                if sys.platform == "win32":
                    result = subprocess.run(["shutdown", "/s", "/t", "60"], capture_output=True, text=True)
                    if result.returncode == 0:
                        await self.send_json(ws, {"type": "response", "id": msg_id, "payload": {"status": "success", "message": "PC will shutdown in 1 minute"}})
                        self.lalc_logger.debug("收到 shutdown_pc 命令，计算机将在1分钟后关闭")
                    else:
                        await self.send_json(ws, {"type": "response", "id": msg_id, "payload": {"status": "error", "message": f"Failed to schedule shutdown: {result.stderr}"}})
                        self.lalc_logger.debug(f"计划关机失败: {result.stderr}", level="ERROR")
                else:
                    # 对于非Windows系统，暂时返回不支持
                    await self.send_json(ws, {"type": "response", "id": msg_id, "payload": {"status": "error", "message": "Shutdown command only supported on Windows"}})
                    self.lalc_logger.debug("收到 shutdown_pc 命令，但当前系统不支持", level="ERROR")
            elif base_cmd == "close_window":
                result = input_handler.close_window()
                if result:
                    await self.send_json(ws, {"type": "response", "id": msg_id, "payload": {"status": "success", "message": "window closed"}})
                    self.lalc_logger.debug("收到 close_window 命令，已关闭游戏窗口")
                else:
                    await self.send_json(ws, {"type": "response", "id": msg_id, "payload": {"status": "error", "message": "no valid window handle"}})
                    self.lalc_logger.debug("收到 close_window 命令，但没有有效的窗口句柄")
            elif base_cmd == "cancel_shutdown_pc":
                import subprocess
                import sys
                # 在Windows上使用shutdown命令取消计划关机
                if sys.platform == "win32":
                    result = subprocess.run(["shutdown", "/a"], capture_output=True, text=True)
                    if result.returncode == 0:
                        await self.send_json(ws, {"type": "response", "id": msg_id, "payload": {"status": "success", "message": "PC shutdown canceled"}})
                        self.lalc_logger.debug("收到 cancel_shutdown_pc 命令，已取消计划关机")
                    else:
                        await self.send_json(ws, {"type": "response", "id": msg_id, "payload": {"status": "error", "message": f"Failed to cancel shutdown: {result.stderr}"}})
                        self.lalc_logger.debug(f"取消关机失败: {result.stderr}", level="ERROR")
                else:
                    # 对于非Windows系统，暂时返回不支持
                    await self.send_json(ws, {"type": "response", "id": msg_id, "payload": {"status": "error", "message": "Cancel shutdown command only supported on Windows"}})
                    self.lalc_logger.debug("收到 cancel_shutdown_pc 命令，但当前系统不支持", level="ERROR")
            elif base_cmd == "get_status":
                # 返回当前任务流水线状态
                status = self.pipeline.state
                await self.send_json(ws, {"type": "response", "id": msg_id, "payload": {"status": "success", "pipeline_state": status}})
                self.lalc_logger.debug(f"收到 get_status 命令，当前任务流水线状态: {status}")
            elif base_cmd == "get_log_folders":
                import os
                from pathlib import Path
                import re
                from datetime import datetime
                
                # 获取日志根目录
                logs_root = Path("./logs")
                if not logs_root.exists():
                    logs_root.mkdir(exist_ok=True)
                
                # 获取所有日志文件夹并解析时间戳
                folders_with_time = []
                for item in logs_root.iterdir():
                    if item.is_dir():
                        # 尝试解析文件夹名称中的时间戳
                        try:
                            # 假设文件夹名就是时间戳格式 YYYY-MM-DD-HH-MM-SS
                            dt = datetime.strptime(item.name, "%Y-%m-%d-%H-%M-%S")
                            folders_with_time.append((dt, item.name))
                        except ValueError:
                            # 如果不是标准时间戳格式，跳过或者使用文件夹修改时间
                            try:
                                mtime = datetime.fromtimestamp(item.stat().st_mtime)
                                folders_with_time.append((mtime, item.name))
                            except:
                                # 最后备选方案：使用当前时间
                                folders_with_time.append((datetime.now(), item.name))
                
                # 按时间倒序排列（最新的在前面）
                folders_with_time.sort(key=lambda x: x[0], reverse=True)
                folders = [name for dt, name in folders_with_time]
                
                await self.send_json(ws, {
                    "type": "response", 
                    "id": msg_id, 
                    "payload": {
                        "status": "success", 
                        "type": "log_folders",
                        "folders": folders
                    }
                })
                self.lalc_logger.debug(f"已发送日志文件夹列表，共 {len(folders)} 个")
            elif base_cmd == "get_log_address":
                if not args:
                    raise ValueError("缺少文件夹名称参数")
                
                folder_name = args[0]
                import os
                from pathlib import Path
                
                # 构造日志文件夹的绝对路径
                log_dir = Path("./logs") / folder_name
                if not log_dir.exists():
                    raise ValueError(f"日志文件夹不存在: {folder_name}")
                
                # 获取绝对路径
                absolute_path = str(log_dir.resolve())
                
                # 发送日志文件夹的绝对路径
                await self.send_json(ws, {
                    "type": "response", 
                    "id": msg_id, 
                    "payload": {
                        "status": "success", 
                        "type": "log_address",
                        "folder": folder_name,
                        "address": absolute_path
                    }
                })
                
                self.lalc_logger.debug(f"已发送日志文件夹地址：{folder_name} -> {absolute_path}")
            elif base_cmd == "get_img_address":
                import os
                from pathlib import Path
                
                # 构造项目根目录下img文件夹的绝对路径
                img_dir = Path("./img")
                if not img_dir.exists():
                    raise ValueError(f"项目根目录下img文件夹不存在: {img_dir}")
                
                # 获取绝对路径
                absolute_path = str(img_dir.resolve())
                
                # 发送图片文件夹的绝对路径
                await self.send_json(ws, {
                    "type": "response", 
                    "id": msg_id, 
                    "payload": {
                        "status": "success", 
                        "type": "img_address",
                        "address": absolute_path
                    }
                })
                
                self.lalc_logger.debug(f"已发送img文件夹地址: {absolute_path}")
            elif base_cmd == "get_log_content":
                if not args:
                    raise ValueError("缺少文件夹名称参数")
                
                folder_name = args[0]
                import os
                from pathlib import Path
                import re
                from datetime import datetime
                
                # 构造日志文件路径
                log_dir = Path("./logs") / folder_name
                if not log_dir.exists():
                    raise ValueError(f"日志文件夹不存在: {folder_name}")
                
                # 查找主日志文件（run.log）
                log_file = log_dir / "run.log"
                if not log_file.exists():
                    raise ValueError(f"在文件夹 {folder_name} 中未找到 run.log 文件")
                
                # 计算日志总行数
                total_lines = 0
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        total_lines += 1
                
                # 先发送日志总行数
                await self.send_json(ws, {
                    "type": "response", 
                    "id": msg_id, 
                    "payload": {
                        "status": "success", 
                        "type": "log_content_info",
                        "folder": folder_name,
                        "total_lines": total_lines
                    }
                })
                
                self.lalc_logger.debug(f"已发送日志信息：文件夹 {folder_name} 共 {total_lines} 行")
            elif base_cmd == "get_log_line":
                if len(args) < 2:
                    raise ValueError("缺少参数：文件夹名称、行号")
                
                folder_name = args[0]
                line_number = int(args[1])
                
                import os
                from pathlib import Path
                import re
                from datetime import datetime
                
                # 构造日志文件路径
                log_dir = Path("./logs") / folder_name
                if not log_dir.exists():
                    raise ValueError(f"日志文件夹不存在: {folder_name}")
                
                # 查找主日志文件（run.log）
                log_file = log_dir / "run.log"
                if not log_file.exists():
                    raise ValueError(f"在文件夹 {folder_name} 中未找到 run.log 文件")
                
                # 读取指定行的日志
                target_line = None
                with open(log_file, "r", encoding="utf-8") as f:
                    for current_line_num, line in enumerate(f, 1):
                        if current_line_num == line_number:
                            target_line = line
                            break
                
                if target_line is None:
                    raise ValueError(f"日志文件中没有第 {line_number} 行")
                
                # 解析日志行，格式示例：
                # 2023-06-15 14:30:25,123 | INFO | [task_name] 日志消息 | IMAGE:images/xxx.png
                match = re.match(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) \| (\w+) \| (.*?)(?:\s*\|\s*IMAGE:(.*?))?$', target_line)
                log_entry = None
                if match:
                    timestamp, level, message, image_path = match.groups()
                    # 如果有图片路径，读取图片数据
                    image_data = None
                    if image_path:
                        try:
                            from PIL import Image
                            import io
                            import base64
                            
                            # 构造完整图片路径
                            full_image_path = log_dir / "images" / image_path
                            if full_image_path.exists():
                                # 读取图片并转换为base64编码
                                with Image.open(full_image_path) as img:
                                    # 转换为RGB模式（如果是RGBA或其他模式）
                                    if img.mode != 'RGB':
                                        img = img.convert('RGB')
                                    
                                    # 将图片保存到内存缓冲区
                                    buffer = io.BytesIO()
                                    img.save(buffer, format='JPEG')
                                    image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
                        except Exception as e:
                            self.lalc_logger.log(f"读取图片失败: {str(e)}", level="ERROR")
                    
                    log_entry = {
                        "timestamp": timestamp,
                        "level": level,
                        "message": message,
                        "image_data": image_data
                    }
                else:
                    # 对于不匹配标准格式的行
                    log_entry = {
                        "timestamp": "",
                        "level": "INFO",
                        "message": target_line.rstrip('\n'),
                        "image_data": None
                    }
                
                await self.send_json(ws, {
                    "type": "response", 
                    "id": msg_id, 
                    "payload": {
                        "status": "success", 
                        "type": "log_line",
                        "folder": folder_name,
                        "line_number": line_number,
                        "entry": log_entry
                    }
                })
            else:
                await self.send_json(ws, {"type": "response", "id": msg_id, "payload": {"status": "error", "message": f"unknown command: {base_cmd}"}})
                self.lalc_logger.debug(f"收到未知命令: {base_cmd}", level="ERROR")
        except Exception as e:
            error_msg = f"执行命令时发生错误: {str(e)}"
            traceback_str = traceback.format_exc()
            self.lalc_logger.debug(error_msg, level="ERROR")
            self.lalc_logger.debug(traceback_str, level="ERROR")
            await self.send_json(ws, {
                "type": "response", 
                "id": msg_id, 
                "payload": {
                    "status": "error", 
                    "message": error_msg
                }
            })

    # ---------- 连接生命周期 ----------
    async def client_handler(self, ws: websockets.WebSocketServerProtocol):
        self.clients.add(ws)
        self.lalc_logger.debug(f"客户端接入 {ws.remote_address} 当前连接数 {len(self.clients)}")
        await self.send_json(ws, {"type": "response", "id": "12138", "payload": {"status": "success", "message": "connection confirm"}})
        # await self.send_json(ws, {"type": "error", "id": "12139", "payload": {"status": "fail", "message": "test error type"}})

        try:
            async for raw in ws:
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    await self.send_json(ws, {"type": "error", "payload": "invalid json"})
                    self.lalc_logger.debug("收到无效JSON数据", level="WARNING")
                    continue

                # 心跳
                if data.get("type") == "heartbeat":
                    await self.send_json(ws, {"type": "heartbeat_ack"})
                    continue

                # 处理配置数据
                if data.get("type") == "configurations":
                    # 保存配置数据
                    self.received_configs = data.get("payload", {})
                    continue

                # 业务命令
                if data.get("type") == "request":
                    cmd = data.get("payload", {}).get("command")
                    msg_id = data.get("id", "")
                    args_list = data.get("payload", {}).get("args", None)
                    await self.handle_command(ws, cmd, msg_id, args_list)
                else:
                    await self.send_json(ws, {"type": "error", "payload": "unknown message type"})
                    self.lalc_logger.debug("收到未知消息类型")
        except websockets.exceptions.ConnectionClosed:
            self.lalc_logger.debug(f"客户端断开 {ws.remote_address}")
        except Exception as e:
            self.lalc_logger.debug(f"client_handler 异常: {str(e)}", level="ERROR")
            await self.send_json(ws, {"type": "error", "payload": str(e)})
        finally:
            self.clients.discard(ws)
            self.lalc_logger.debug(f"客户端移除 {ws.remote_address} 剩余 {len(self.clients)}")
            
            # 如果没有客户端连接了，记录断开时间
            if not self.clients:
                self._last_client_disconnect_time = datetime.now()

    # ---------- 启动入口 ----------
    async def run_server(self, host: str = "localhost", port_range=range(8765, 8767)):
        self.loop = asyncio.get_running_loop()  # 保存事件循环引用
        for port in port_range:
            try:
                self.server = await websockets.serve(
                    self.client_handler, host, port,            # 减少大图流量
                    ping_interval=None,             # 自己心跳
                    ping_timeout=None
                )
                self.lalc_logger.log(f"WebSocket 服务器启动，监听 ws://{host}:{port}")
                return port
            except OSError:
                continue
        raise RuntimeError("无可用端口")

    async def run_forever(self):
        await self.run_server()
        self.lalc_logger.debug("WebSocket 服务器开始运行")
        
        # 启动超时检查任务
        self._timeout_task = asyncio.create_task(self._check_timeout())
        
        try:
            while not self._should_exit:
                await asyncio.sleep(0.1)  # 短暂休眠以避免忙等待
        finally:
            # 取消超时检查任务
            if self._timeout_task and not self._timeout_task.done():
                self._timeout_task.cancel()
                try:
                    await self._timeout_task
                except asyncio.CancelledError:
                    pass

# -------------------- 入口 --------------------
async def amain():
    srv = ServerController()
    await srv.run_forever()

if __name__ == "__main__":
    asyncio.run(amain())