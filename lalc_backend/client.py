import asyncio
import websockets
import json
import uuid
import sys
import logging
from typing import Optional

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger("WS-Client")


class ClientController:
    def __init__(self, port: int = 8765):
        self.url = f"ws://localhost:{port}"
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.send_queue: asyncio.Queue = asyncio.Queue()
        self._running = True
        # 新增：当前正在拉取的日志信息
        self._pulling_log: Optional[dict] = None   # {"folder": "xxx", "total": 123, "got": 0}

    # ---------- 网络层 ----------
    async def connect(self) -> bool:
        try:
            self.ws = await websockets.connect(self.url, ping_interval=None)
            logger.info(f"connected to {self.url}")
            return True
        except Exception as e:
            logger.error(f"connect failed: {e}")
            return False

    async def disconnect(self):
        if self.ws:
            await self.ws.close()
            self.ws = None
            logger.info("disconnected")

    # ---------- 发送协 ----------
    async def send_task(self):
        """不断从队列取消息发给服务器"""
        while self._running:
            try:
                msg = await asyncio.wait_for(self.send_queue.get(), 5)
            except asyncio.TimeoutError:
                continue
            if not self.ws:
                logger.warning("send_task: no ws, drop message")
                continue
            try:
                await self.ws.send(json.dumps(msg))
            except Exception as e:
                logger.error(f"send error: {e}")
                break

    # ---------- 接收协 ----------
    async def recv_task(self):
        """持续接收服务器消息（含主动推送）"""
        while self._running:
            if not self.ws:
                logger.info("recv_task: ws closed, will retry in 2s")
                await asyncio.sleep(2)
                if await self.connect():
                    continue
                else:
                    continue
            try:
                raw = await asyncio.wait_for(self.ws.recv(), timeout=10)
            except asyncio.TimeoutError:
                continue
            except websockets.exceptions.ConnectionClosed:
                logger.info("recv_task: connection closed")
                await self.disconnect()
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("recv_task: invalid json")
                continue
            
            # 处理日志文件夹地址信息
            if data.get("type") == "response" and data.get("payload", {}).get("type") == "log_address":
                payload = data.get("payload", {})
                folder = payload.get("folder")
                address = payload.get("address")
                
                logger.info(f"[LOG_ADDRESS] 日志文件夹 {folder} 的绝对路径: {address}")
                
            # 处理图片文件夹地址信息
            elif data.get("type") == "response" and data.get("payload", {}).get("type") == "img_address":
                payload = data.get("payload", {})
                address = payload.get("address")
                
                logger.info(f"[IMG_ADDRESS] img文件夹的绝对路径: {address}")
                
            # 处理日志内容信息
            elif data.get("type") == "response" and data.get("payload", {}).get("type") == "log_content_info":
                payload = data.get("payload", {})
                folder = payload.get("folder")
                total_lines = payload.get("total_lines")

                logger.info(f"[LOG_CONTENT_INFO] 日志文件夹 {folder} 共有 {total_lines} 行记录")

                # 初始化拉取状态
                self._pulling_log = {"folder": folder, "total": total_lines, "got": 0}

                # 自动逐行请求
                if total_lines > 0:
                    logger.info(f"[AUTO_FETCH] 正在逐条获取全部 {total_lines} 行日志…")
                    for line_no in range(1, total_lines + 1):
                        self.send_log_request("get_log_line", [folder, str(line_no)])
                else:
                    logger.info("[LOG_END] 日志为空")
                    self._pulling_log = None
                    
            # 处理单行日志数据
            elif data.get("type") == "response" and data.get("payload", {}).get("type") == "log_line":
                payload = data.get("payload", {})
                folder = payload.get("folder")
                line_number = payload.get("line_number")
                entry = payload.get("entry", {})

                timestamp = entry.get("timestamp", "")
                level = entry.get("level", "")
                message = entry.get("message", "")
                image_data = entry.get("image_data")

                log_line = f"[{timestamp}][{level}] {message}"
                if image_data:
                    log_line += f" | IMAGE: <Base64数据，长度 {len(image_data)}>"
                else:
                    image_path = entry.get("image_path")  # 兼容旧版本
                    if image_path:
                        log_line += f" | IMAGE: {image_path}"

                logger.info(f"[LOG_LINE] {folder} 第 {line_number} 行: {log_line}")

                # 更新拉取计数
                if self._pulling_log and self._pulling_log["folder"] == folder:
                    self._pulling_log["got"] += 1
                    if self._pulling_log["got"] >= self._pulling_log["total"]:
                        logger.info(f"[LOG_END] 日志 {folder} 全部打印完毕")
                        self._pulling_log = None
            
            # 处理版本信息
            elif data.get("type") == "response" and data.get("payload", {}).get("type") == "version_info":
                payload = data.get("payload", {})
                version = payload.get("version", "")
                
                logger.info(f"[VERSION_INFO] 最新版本号: {version}")
                
            # 处理下载进度
            elif data.get("type") == "response" and data.get("payload", {}).get("status") == "progress" and data.get("payload", {}).get("type") == "download_progress":
                payload = data.get("payload", {})
                progress = payload.get("progress", 0)
                
                logger.info(f"[DOWNLOAD_PROGRESS] 下载进度: {progress:.1f}%")
                
            # 处理下载完成
            elif data.get("type") == "response" and data.get("payload", {}).get("type") == "download_complete":
                payload = data.get("payload", {})
                file_path = payload.get("file_path", "")
                
                logger.info(f"[DOWNLOAD_COMPLETE] 下载完成，文件路径: {file_path}")
            
            # ↓↓↓ 新增：处理下载被取消
            elif data.get("type") == "response" and data.get("payload", {}).get("type") == "download_cancelled":
                logger.info("[DOWNLOAD_CANCELLED] 下载已被用户取消")
                
            # 如果是推送，直接展示
            elif data.get("type") == "response":
                payload = data.get("payload", {})
                logger.info(f"[RESPONSE] {payload}")
                
            elif data.get("type") == "task_log":
                payload = data.get("payload", {})
                level = payload.get("level", "INFO")
                message = payload.get("message", "")
                logger.info(f"[TASK_LOG][{level}] {message}")
                
            elif data.get("type") == "error":
                payload = data.get("payload", {})
                logger.error(f"[ERROR] {payload}")

    # ---------- 业务命令 ----------
    def send_command(self, command: str):
        """用户界面调用：把命令塞进队列即可"""
        msg = {
            "type": "request",
            "id": str(uuid.uuid4()),
            "payload": {"command": command}
        }
        self.send_queue.put_nowait(msg)

    def send_log_request(self, command: str, args: list = None):
        """发送带参数的日志相关命令"""
        msg = {
            "type": "request",
            "id": str(uuid.uuid4()),
            "payload": {"command": command}
        }
        
        if args:
            msg["payload"]["args"] = args
            
        self.send_queue.put_nowait(msg)

    # ---------- 交互 UI ----------
    async def interactive(self):
        """后台任务已启动，这里只负责读键盘"""
        logger.info("输入命令：start | pause | resume | stop | get_log_folders | ... | download_from_github[:<path>] | download_from_mirrorchan[:<path>[:<cdk>]] | cancel_download | quit")
        while self._running:
            # 修改此处以解决输入问题
            cmd = await asyncio.get_event_loop().run_in_executor(None, input, ">>> ")
            cmd = cmd.strip()
            
            if cmd == "quit":
                self._running = False
                break
            elif cmd in {"start", "pause", "resume", "stop", "get_img_address", "get_latest_version"}:
                self.send_command(cmd)
            elif cmd == "get_log_folders":
                self.send_command(cmd)
            elif cmd.startswith("get_log_count:"):
                # 解析文件夹名称
                parts = cmd.split(":", 1)
                if len(parts) > 1 and parts[1]:
                    folder_name = parts[1]
                    self.send_log_request("get_log_content", [folder_name])
                else:
                    logger.warning("请提供有效的日志文件夹名称")
            elif cmd.startswith("get_log_address:"):
                # 解析文件夹名称
                parts = cmd.split(":", 1)
                if len(parts) > 1 and parts[1]:
                    folder_name = parts[1]
                    self.send_log_request("get_log_address", [folder_name])
                else:
                    logger.warning("请提供有效的日志文件夹名称")
            elif cmd.startswith("get_log_line:"):
                # 解析文件夹名称和行号
                parts = cmd.split(":", 2)
                if len(parts) > 2 and parts[1] and parts[2]:
                    folder_name = parts[1]
                    line_number = parts[2]
                    try:
                        int(line_number)  # 验证行号是数字
                        self.send_log_request("get_log_line", [folder_name, line_number])
                    except ValueError:
                        logger.warning("行号必须是数字")
                else:
                    logger.warning("请提供有效的日志文件夹名称和行号，格式：get_log_line:<folder_name>:<line_number>")
            elif cmd.startswith("download_from_github"):
                # 解析下载路径
                parts = cmd.split(":", 1)
                if len(parts) > 1 and parts[1]:
                    download_path = parts[1]
                    self.send_log_request("download_from_github", [download_path])
                else:
                    # 默认下载到当前目录
                    self.send_log_request("download_from_github", ["."])
            elif cmd.startswith("download_from_mirrorchan"):
                # 解析下载路径和CDK
                print(f"cmd:{cmd}")
                parts = cmd.split(":", 2)  # 限制分割为最多3部分
                print(f"parts:{parts}")
                if len(parts) >= 2:
                    download_path = parts[1]
                    if len(parts) >= 3 and parts[2]:  # 检查是否有CDK部分且不为空
                        cdk = parts[2]
                        self.send_log_request("download_from_mirrorchan", [download_path, cdk])
                    else:
                        # 没有提供CDK，只传递下载路径
                        self.send_log_request("download_from_mirrorchan", [download_path])
                else:
                    # 默认下载到当前目录
                    self.send_log_request("download_from_mirrorchan", ["."])
            elif cmd == "cancel_download":
                self.send_command("cancel_download")
            else:
                logger.warning("未知命令")

    # ---------- 主入口 ----------
    async def run(self):
        if not await self.connect():
            return
        # 启动双工协程
        send_t = asyncio.create_task(self.send_task())
        recv_t = asyncio.create_task(self.recv_task())
        try:
            await self.interactive()
        finally:
            self._running = False
            await self.disconnect()
            await asyncio.gather(send_t, recv_t, return_exceptions=True)


# -------------------- 入口 --------------------
async def amain():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    cli = ClientController(port)
    await cli.run()

if __name__ == "__main__":
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        logger.info("Client shutdown by Ctrl-C")