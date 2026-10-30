"""通过独立 pi 二进制验证图片和受限源码读取，不持久化会话或交互日志。"""

from __future__ import annotations

import asyncio
import base64
from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from collections import deque
import getpass
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from .agent_diagnostics import AgentDiagnosticError, redact, error_details


PI_VERSION = "1.4.0"
_spawn_lock = threading.Lock()


@contextmanager
def pi_process_environment(env):
    """冻结宿主启动独立 pi 时隔离其库查找路径，随后恢复 Qt 的 DLL 路径。"""
    if not getattr(sys, "frozen", False):
        yield env
        return
    root = Path(sys._MEIPASS).resolve()
    prepared = dict(env)
    for name in ("PATH", "DYLD_LIBRARY_PATH", "LD_LIBRARY_PATH"):
        if name in prepared:
            prepared[name] = os.pathsep.join(value for value in prepared[name].split(os.pathsep)
                                            if value and not Path(value).resolve().is_relative_to(root))
    if sys.platform != "win32":
        yield prepared
        return
    import ctypes
    with _spawn_lock:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetDllDirectoryW.argtypes = [ctypes.c_uint32, ctypes.c_wchar_p]
        kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
        original = ctypes.create_unicode_buffer(kernel.GetDllDirectoryW(0, None) + 1)
        kernel.GetDllDirectoryW(len(original), original)
        if not kernel.SetDllDirectoryW(None):
            raise AgentDiagnosticError("无法隔离 pi 的 DLL 查找环境。", "pi_environment") from ctypes.WinError(ctypes.get_last_error())
        try:
            yield prepared
        finally:
            if not kernel.SetDllDirectoryW(original.value or None):
                raise AgentDiagnosticError("无法恢复应用 DLL 查找环境。", "pi_cleanup") from ctypes.WinError(ctypes.get_last_error())


class PiStartError(AgentDiagnosticError):
    """仅表示操作系统未能建立 pi 进程，区别于清理或模型错误。"""


class PiExited(RuntimeError):
    """pi 输出流结束；是否可回退由本轮是否已发送请求决定。"""


class PiVersionError(RuntimeError):
    """版本探测未给出有效输出，允许在请求前尝试环境 pi。"""


class PiStartup:
    """同一轮共享 pi 选择及请求边界；模型预检之后也不重新开放回退。"""

    def __init__(self):
        self.fallback = None
        self.request_started = False
        self.env = None
        self.on_warning = None

    def select(self, requested, env, cwd, on_warning):
        self.env, self.on_warning = env, on_warning
        bundled = Path(sys.executable).resolve().parent / "pi" / "pi.exe"
        environmental = shutil.which(requested)
        if getattr(sys, "frozen", False) and requested == "pi" and bundled.is_file():
            if environmental and Path(environmental).resolve() != bundled:
                self.fallback = environmental
            executable = str(bundled)
        else:
            executable = environmental
            if getattr(sys, "frozen", False) and requested == "pi" and executable:
                self.record_fallback(str(bundled), executable, "bundled pi not found")
        if not executable:
            raise AgentDiagnosticError(f"pi executable not found: {requested}", "pi_start")
        command = [executable]
        try:
            self.version(command, env, cwd)
        except (OSError, subprocess.SubprocessError, PiVersionError, UnicodeError) as error:
            if not self.retry(command, env, cwd, error):
                raise
        return command

    def version(self, command, env, cwd):
        with pi_process_environment(env) as prepared:
            version = subprocess.run([command[0], "--version"], env=prepared, cwd=cwd,
                                     check=True, capture_output=True, text=True, encoding="utf-8", timeout=10,
                                     **({"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {})).stdout.strip()
        if not version:
            raise PiVersionError("pi --version returned no version")
        if version != PI_VERSION:
            message = f"pi 版本不匹配：已验证 {PI_VERSION}，实际 {version}；继续启动，但兼容性尚未验证。"
            logging.getLogger(__name__).warning(message)
            if sys.stderr is not None:
                print("WARNING: " + message, file=sys.stderr, flush=True)
            if self.on_warning:
                self.on_warning({"type": "pi_version_warning", "expected_version": PI_VERSION,
                                 "actual_version": version, "message": message})
        for target in (self.env, env):
            target["LALC_PI_VERSION"] = version
            target["LALC_PI_EXECUTABLE"] = command[0]
        if self.on_warning:
            self.on_warning({"type": "pi_selected", "path": command[0], "version": version})

    def retry(self, command, env, cwd, error):
        """先消费唯一回退机会，再探测另一程序；探测失败直接保留异常。"""
        if self.request_started or self.fallback is None:
            return False
        previous, command[0], self.fallback = command[0], self.fallback, None
        self.record_fallback(previous, command[0], str(error))
        self.version(command, env, cwd)
        return True

    def record_fallback(self, previous, selected, reason):
        event = {"type": "pi_fallback", "previous_path": previous, "path": selected,
                 "reason": redact(reason, [self.env.get("LALC_PI_API_KEY", "")])}
        logging.getLogger(__name__).warning("pi fallback: %s", event)
        if self.on_warning:
            self.on_warning(event)


def _models(base_url: str, key: str) -> list[dict]:
    """读取指定服务的模型声明，不触发加载或自动改选供应商。"""
    request = Request(base_url + "/models", headers={} if key == "lalc-no-key" else {"Authorization": f"Bearer {key}"})
    try:
        with urlopen(request, timeout=10) as response:
            value = json.load(response)
            models = value.get("data") if isinstance(value, dict) else None
            if not isinstance(models, list) or any(not isinstance(m, dict) or not isinstance(m.get("id"), str) for m in models):
                raise ValueError("响应必须包含 data 模型列表，每项必须有字符串 id")
            return models
    except HTTPError as error:
        reason = "authentication failed" if error.code in {401, 403} else "service check failed"
        with error:
            body = error.read(65536).decode("utf-8", errors="replace")
        raise AgentDiagnosticError(f"Model {reason} (HTTP {error.code})，请查看错误详情。", "service_check",
                                   url=request.full_url, http_status=error.code,
                                   response_body=redact(body, [key]),
                                   hint="检查 API Key 和服务权限。" if error.code in {401, 403} else
                                   "检查模型服务或代理日志；HTTP 状态码不能单独确定故障来源。") from error
    except (URLError, TimeoutError, ConnectionError) as error:
        raise AgentDiagnosticError("模型服务无法连接或连接超时，请查看错误详情。", "service_check",
                                   url=request.full_url, cause=redact(str(error) or type(error).__name__, [key]),
                                   hint="检查服务是否启动、客户端网络/Tailscale、地址和代理设置。") from error
    except (ValueError, UnicodeError) as error:
        raise AgentDiagnosticError("模型列表响应格式不正确，请检查 Base URL 和服务响应。", "service_check",
                                   url=request.full_url, cause=redact(str(error), [key])) from error


@asynccontextmanager
async def _rpc_session(command: list[str], env: dict[str, str], cwd: str, show):
    """共享 pi RPC 传输；调用者负责事件含义，取消时回收子进程。"""
    process = None
    try:
        with pi_process_environment(env) as prepared:
            process = await asyncio.create_subprocess_exec(
                *command, env=prepared, cwd=cwd,
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                limit=16 * 1024 * 1024,
                **({"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}),
            )
    except BaseException as error:
        if process is not None:
            if process.returncode is None:
                process.kill()
            await process.wait()
        elif isinstance(error, OSError):
            raise PiStartError("pi 进程启动失败，请查看错误详情。", "pi_start") from error
        raise
    async def send(value) -> None:
        process.stdin.write((json.dumps(value) + "\n").encode())
        await process.stdin.drain()

    async def stderr() -> None:
        while line := await process.stderr.readline():
            show("pi stderr: " + line.decode(errors="replace").rstrip())

    async def event() -> dict:
        line = await process.stdout.readline()
        if not line:
            raise PiExited(f"pi exited before completion (exit={await process.wait()})")
        return json.loads(line)

    errors = asyncio.create_task(stderr())
    cancelling = False
    try:
        yield send, event
    except asyncio.CancelledError:
        cancelling = True
        if process.returncode is None:
            try:
                await send({"type": "abort"})
            except Exception as error:
                raise AgentDiagnosticError("取消 pi 请求失败，请查看清理详情。", "cancel_cleanup") from error
        raise
    finally:
        try:
            if process.returncode is None:
                process.stdin.close()
                try:
                    await asyncio.wait_for(process.wait(), timeout=3)
                except asyncio.TimeoutError:
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=3)
                    except asyncio.TimeoutError:
                        process.kill()
                        await process.wait()
            await errors
        except Exception as error:
            raise AgentDiagnosticError("pi 进程清理失败，请查看错误详情。",
                                       "cancel_cleanup" if cancelling else "pi_cleanup") from error


async def rpc_event(event, waiting_for: str) -> dict:
    """为就绪和配置响应等待保留明确的超时阶段及原始异常。"""
    try:
        return await asyncio.wait_for(event(), timeout=30)
    except TimeoutError as error:
        raise TimeoutError(f"等待 pi {waiting_for} 超时（30 秒）；请查看 pi stderr 诊断。") from error


@asynccontextmanager
async def rpc_session(command: list[str], env: dict[str, str], cwd: str, show, *, startup=None):
    """就绪前允许一次程序回退；清理、取消及调用者主体异常永不重试。"""
    while True:
        failure = None
        buffered = deque()
        async with AsyncExitStack() as stack:
            try:
                send, event = await stack.enter_async_context(_rpc_session(command, env, cwd, show))
                if startup is not None and not startup.request_started:
                    while True:
                        item = await rpc_event(event, "就绪事件 lalc_ready")
                        buffered.append(item)
                        if item.get("type") in {"lalc_ready", "extension_error"}:
                            break
            except (PiStartError, PiExited) as error:
                failure = error
            if failure is None:
                async def tracked_send(value):
                    if startup is not None and value.get("type") == "prompt":
                        startup.request_started = True
                    await send(value)

                async def buffered_event():
                    return buffered.popleft() if buffered else await event()

                yield tracked_send, buffered_event
                return
        # 离开进程作用域后再切换，避免遗留两个活动 pi；清理失败不会走到这里。
        if startup is None or not startup.retry(command, env, cwd, failure):
            raise failure


async def _interact(command: list[str], env: dict[str, str], cwd: str, prompt: dict, key: str, *, startup=None) -> int:
    """验证受限读取并展示事件；完整修复复用 RPC 传输而非此成功判据。"""
    requests = 0
    read_ok = False
    last_message = {}
    def show(value) -> None:
        def clean(item):
            if isinstance(item, dict):
                return {name: ("[image base64 omitted]" if name == "data" and item.get("type") == "image"
                               else clean(content)) for name, content in item.items()}
            if isinstance(item, list):
                return [clean(content) for content in item]
            if isinstance(item, str) and key != "lalc-no-key":
                return item.replace(key, "[REDACTED]")
            return item

        shown = redact(clean(value), [key])
        print(shown if isinstance(shown, str) else json.dumps(shown, ensure_ascii=False), flush=True)

    async with rpc_session(command, env, cwd, show, startup=startup) as (send, event):
        async def configure(kind: str) -> None:
            await send({"id": kind, "type": kind, "enabled": False})
            while True:
                item = await rpc_event(event, f"配置响应 {kind}")
                show(item)
                if item.get("id") == kind:
                    if not item.get("success"):
                        raise RuntimeError(f"pi rejected {kind}")
                    return

        try:
            while True:
                item = await rpc_event(event, "就绪事件 lalc_ready")
                show(item)
                if item.get("type") == "lalc_ready":
                    if item.get("tools") != ["read"]:
                        raise RuntimeError("Unexpected active tools")
                    break
                if item.get("type") == "extension_error":
                    raise RuntimeError("pi extension failed")
            await configure("set_auto_retry")
            await configure("set_auto_compaction")
            await send(prompt)
            while True:
                item = await event()
                kind = item.get("type")
                # 图片以文件、哈希和请求中的图片标记展示，不在终端倾倒 base64。
                if kind == "message_update":
                    # 完整响应由 message_end 展示，避免逐 token 重复和刷屏。
                    continue
                elif kind in {"message_start", "message_end"} and item.get("message", {}).get("role") == "user":
                    show({"type": kind, "role": "user", "image": "supplied PNG"})
                else:
                    show(item)
                if kind == "response" and not item.get("success"):
                    raise RuntimeError("pi rejected RPC command")
                if kind == "lalc_request":
                    requests = item["requests"]
                if kind == "tool_execution_end" and item.get("toolName") == "read" and not item.get("isError"):
                    read_ok = True
                if kind == "message_end" and item.get("message", {}).get("role") == "assistant":
                    last_message = item["message"]
                if kind == "extension_error":
                    raise RuntimeError("pi extension failed")
                if kind == "agent_settled":
                    success = (requests > 0 and read_ok and last_message.get("stopReason") == "stop"
                               and any(part.get("type") == "text" and part.get("text", "").strip()
                                       for part in last_message.get("content", [])))
                    show({"result": "completed" if success else "incomplete", "requests": requests,
                          "source_read": read_ok, "stop_reason": last_message.get("stopReason"),
                          "error": last_message.get("errorMessage")})
                    return 0 if success else 1
        except asyncio.CancelledError:
            show({"result": "cancelled", "requests": requests})
            raise


@contextmanager
def configured_pi(args, root: Path, key: str, system_prompt: str, *, require_image: bool = True, on_warning=None, startup=None):
    """隔离连接配置；版本差异仅警告，保留实际版本供终端、GUI 和日志检查。"""
    if not shutil.which(args.pi) and not (getattr(sys, "frozen", False) and args.pi == "pi" and
            (Path(sys.executable).resolve().parent / "pi" / "pi.exe").is_file()):
        raise AgentDiagnosticError(f"pi executable not found: {args.pi}", "pi_start")
    base = args.base_url.rstrip("/")
    if not args.model:
        raise AgentDiagnosticError("Agent model is required; supply --model 或在 Agent Settings 中填写模型。", "settings")
    models = _models(base, key)
    matching = [m for m in models if m["id"] == args.model]
    if len(matching) != 1:
        raise AgentDiagnosticError("Select exactly one model with --model：模型不存在或 ID 不唯一。", "model_status")
    model = matching[0]
    status = model.get("status", {}).get("value")
    if status is not None and status != "loaded":
        logging.getLogger(__name__).info("模型状态 %s，继续请求，由服务端决定加载策略。", status)
    provider = getattr(args, "provider", None) or "llama.cpp"
    if provider == "deepseek" and args.model != "deepseek-flash":
        raise AgentDiagnosticError("DeepSeek 当前仅支持 deepseek-flash", "settings")
    if require_image and provider != "deepseek" and "image" not in model.get("architecture", {}).get("input_modalities", []):
        raise AgentDiagnosticError("Selected service model does not declare image input support", "model_preflight")
    with tempfile.TemporaryDirectory(prefix="lalc-pi-") as temporary:
        agent_dir = Path(temporary) / "agent"
        agent_dir.mkdir()
        (agent_dir / "settings.json").write_text(json.dumps({
            "retry": {"enabled": False, "maxRetries": 0},
            "compaction": {"enabled": False}, "cacheWarming": "off",
            "enableInstallTelemetry": False, "enableAnalytics": False,
        }), encoding="utf-8")
        env = {**os.environ, "PI_CODING_AGENT_DIR": str(agent_dir), "PI_OFFLINE": "1",
               "PI_TELEMETRY": "0", "LALC_PI_API_KEY": key, "LALC_PI_BASE_URL": base,
               "LALC_PI_MODEL": model["id"], "LALC_PI_SOURCE_ROOT": str(root),
               "LALC_PI_MAX_REQUESTS": str(args.max_requests), "LALC_PI_PROVIDER": provider,
               "LALC_PI_THINKING": "1" if provider == "deepseek" and getattr(args, "thinking", None) is not False else "0"}
        # 使用系统已信任的 CA，保留显式覆盖；不关闭 TLS 证书校验。
        env.setdefault("NODE_USE_SYSTEM_CA", "1")
        env.pop("LALC_PI_REPAIR_TARGET", None)
        env.pop("LALC_PI_PAYLOAD_DIR", None)
        env.pop("LALC_PI_PREFLIGHT", None)
        env.pop("LALC_PI_REQUESTS_USED", None)
        env.pop("LALC_PI_REPAIR_FILES", None)
        env.pop("LALC_PI_HISTORY", None)
        startup = startup or PiStartup()
        command = startup.select(args.pi, env, temporary, on_warning)
        command += ["--mode", "rpc", "--no-session", "--no-extensions",
                   "--no-skills", "--no-prompt-templates", "--no-context-files", "--no-themes",
                   "--no-approve", "--offline", "--no-builtin-tools", "--tools", "read",
                   "--extension", str(Path(__file__).with_suffix(".ts")),
                   "--provider", "lalc-probe", "--model", model["id"], "--thinking",
                   (getattr(args, "reasoning_effort", None) or "high") if env["LALC_PI_THINKING"] == "1" else "off",
                   "--system-prompt", system_prompt]
        yield command, env, temporary, model


def run_probe(args) -> int:
    """使用临时配置及受限读取；不同于已验证版本时提示但不阻止启动。"""
    key = "lalc-no-key"
    try:
        if args.ask_api_key:
            key = getpass.getpass("API key（无需认证时留空）: ") or key
        if args.max_requests < 2:
            raise ValueError("max-requests must be at least 2; reset the request limit")
        root = args.source_root.resolve(strict=True)
        source = (root / args.source).resolve(strict=True)
        if not root.is_dir() or not source.is_file() or not source.is_relative_to(root):
            raise ValueError("source must be a file inside source-root")
        image = args.image.resolve(strict=True)
        data = image.read_bytes()
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("image must be a PNG")
        prompt = {
            "type": "prompt", "id": "probe",
            "message": (f"先调用 read 工具读取 {source.relative_to(root).as_posix()}，简述该源码的职责；"
                        f"然后根据随附图片回答：{args.prompt}\n必须实际读取源码，不能只提出读取计划。"),
            "images": [{"type": "image", "mimeType": "image/png", "data": base64.b64encode(data).decode()}],
        }
        startup = PiStartup()
        with configured_pi(args, root, key, "你是只读图片与源码分析助手。使用提供的 read 工具，不执行命令或游戏操作。", startup=startup,
                           on_warning=lambda event: print(json.dumps(redact(event, [key]), ensure_ascii=False), flush=True)) as (command, env, temporary, model):
            print(json.dumps({"pi": env["LALC_PI_VERSION"], "tested_pi_version": PI_VERSION,
                              "base_url": env["LALC_PI_BASE_URL"], "model": model["id"],
                              "model_status": model.get("status", {}).get("value"),
                              "image": str(image), "sha256": hashlib.sha256(data).hexdigest(),
                              "prompt": prompt["message"], "max_requests": args.max_requests}, ensure_ascii=False), flush=True)
            return asyncio.run(_interact(command, env, temporary, prompt, key, startup=startup))
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        details = error_details(error, "pi_probe", keys=[key])
        logging.getLogger(__name__).error("pi probe failed: %s", details)
        print(json.dumps({"error": details["message"], "diagnostics": details}, ensure_ascii=False), flush=True)
        return 1
