"""宿主持有的 pi 管道；读线程只搬运事件，不承载轮次或权限状态。"""

import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import tempfile
import threading


class PiProcess:
    """跨事件循环复用一个 pi；轮次异常即丢弃，下一轮重新启动。"""

    def __init__(self):
        self.process = None
        self.directory = None
        self.signature = None
        self.events = queue.Queue()
        self.show = lambda _value: None
        self.readers = []

    def close(self, *, abort=False):
        """仅回收自己启动的进程，等待管道线程结束后释放临时配置。"""
        process, self.process = self.process, None
        if process is not None:
            if process.poll() is None:
                if abort:
                    process.terminate()
                if process.stdin is not None:
                    process.stdin.close()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
            for reader in self.readers:
                reader.join(timeout=5)
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
        self.readers = []
        if self.directory is not None:
            self.directory.cleanup()
            self.directory = None
        self.signature = None

    def _read(self, stream, events, *, stderr=False):
        try:
            for line in iter(lambda: stream.readline(16 * 1024 * 1024 + 1), b""):
                if len(line) > 16 * 1024 * 1024:
                    raise ValueError("pi 协议事件超过上限。")
                if stderr:
                    self.show("pi stderr: " + line.decode(errors="replace").rstrip())
                else:
                    events.put(json.loads(line))
        except Exception as error:
            events.put(error)
        finally:
            if not stderr:
                events.put(None)

    @asynccontextmanager
    async def session(self, command, env, cwd, show):
        from .pi_probe import PiExited, PiStartError, pi_process_environment
        signature_command = list(command)
        for flag in ("--tools", "--system-prompt"):
            signature_command[signature_command.index(flag) + 1] = "<round>"
        signature = (tuple(signature_command), *(env.get(key) for key in
                     ("LALC_PI_BASE_URL", "LALC_PI_API_KEY", "LALC_PI_PROVIDER")))
        reuse = self.process is not None and self.process.poll() is None and self.signature == signature
        if not reuse:
            self.close()
            self.directory = tempfile.TemporaryDirectory(prefix="lalc-pi-process-")
            home = Path(self.directory.name)
        else:
            assert self.directory is not None
            home = Path(self.directory.name)
        # 密钥留在启动环境；轮次文件只传已单独持久化的提示、路径及权限。
        keys = ("SOURCE_ROOT", "REPAIR_FILES", "HISTORY", "INPUT_IMAGES", "INPUT_MESSAGE", "PAYLOAD_DIR",
                "CONVERSATION_ROUND", "ROUND_REQUEST_LIMIT", "ALLOWED_TOOLS", "MAX_REQUESTS")
        state = {"LALC_PI_" + key: env.get("LALC_PI_" + key) for key in keys}
        state["LALC_PI_SYSTEM_PROMPT"] = command[command.index("--system-prompt") + 1]
        config = home / "round.json"
        config.write_text(json.dumps(state), encoding="utf-8")
        self.show = show
        try:
            if not reuse:
                prepared_env = dict(env, LALC_PI_ROUND_CONFIG=str(config), PI_CODING_AGENT_DIR=str(home / "agent"))
                shutil.copytree(Path(cwd) / "agent", home / "agent")
                try:
                    with pi_process_environment(prepared_env) as prepared:
                        self.process = subprocess.Popen(command, env=prepared, cwd=home,
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}))
                except OSError as error:
                    raise PiStartError("pi 进程启动失败。", "pi_start") from error
                self.signature = signature
                self.events = queue.Queue()
                self.readers = [threading.Thread(target=self._read, args=(self.process.stdout, self.events), daemon=True),
                                threading.Thread(target=self._read, args=(self.process.stderr, self.events),
                                                 kwargs={"stderr": True}, daemon=True)]
                for reader in self.readers:
                    reader.start()
            process = self.process
            assert process is not None and process.stdin is not None
            input_stream = process.stdin

            async def send(value):
                payload = (json.dumps(value) + "\n").encode()
                def write():
                    input_stream.write(payload)
                    input_stream.flush()
                await asyncio.to_thread(write)

            async def event():
                while True:
                    try:
                        item = self.events.get_nowait()
                    except queue.Empty:
                        await asyncio.sleep(.01)
                        continue
                    if item is None:
                        raise PiExited(f"pi exited before completion (exit={process.wait()})")
                    if isinstance(item, Exception):
                        raise item
                    return item

            if reuse:
                try:
                    await send({"id": "lalc_new_round", "type": "new_session"})
                except (BrokenPipeError, ConnectionResetError) as error:
                    raise PiExited("复用 pi 时旧进程已退出。") from error
            show({"type": "pi_process", "pid": process.pid, "reused": reuse})
            yield send, event
        except BaseException:
            self.close(abort=True)
            raise
