"""开发者连续修复；显式多文件授权、逐轮额度和实际交互留存。"""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
import uuid

from .pi_probe import PI_VERSION, configured_pi, rpc_event, rpc_session
from .runtime import _exception_fields
from .repair_tools import REPAIR_TOOLS, RepairTools
from .agent_settings import effective_settings, resolve_key
from .developer import candidate_files, selected_files, file_diff


SYSTEM_PROMPT = """你是 LALC Developer Candidate 修复助手。根据用户问题分析，需要修改时实际 read、edit，并 validate 完整候选。
只能读取 Candidate 内已有文件；仅可编辑本轮开发者明确选择的已有文件，包括被选中的 manifest.json 和 Recovery Rule。
plan.json 始终只读。不新建、删除或重命名文件，不自行扩大授权。没有选中文件时只分析，并提示需要开发者先选择编辑文件。
校验失败不影响继续读取和修改；先前校验结果可从上下文查阅。信息不足时说明缺少什么并结束本轮，等待用户主动补充。
asset_tree/asset_directory/asset_images 只读共享素材；action_contracts 只读应用实际动作契约。
game_screenshot 现场截图；crop_asset 每次从新截图裁剪新增素材，同名同哈希保留原图和原标签。非 Windows 现场工具不可用。
截图会恢复并置前唯一游戏窗口。不修改既有图片/标签、正式 Manifest/源码或 Trusted Actions。
不运行命令、候选 Workflow、点击或按键，不 Publish、不设置 Default。不要生成文件操作、网络、子进程、顶层副作用或绕过 ctx 的后台调用。
Validator 会导入 Python，不是安全沙箱，校验通过也不证明真实游戏行为修复。
遵守现有 Component、Recovery Rule 与 ctx.call/ctx.action 契约；Python 模块和关键函数用简洁中文 docstring。
最后回答 JSON：{"revise_success": true或false, "message": "分析、修改结果或缺少的信息"}。
revise_success 仅是本轮修订判断，不能代替校验或游戏验收；最终回答后结束本轮，不自动续跑。
"""


class RepairLog:
    """每对话一个交互目录；逐轮保留原始事件，认证值统一脱敏。"""

    def __init__(self, data_root: Path, key: str = "lalc-no-key", on_event=None):
        self.path = data_root / "agent-interactions" / datetime.now(timezone.utc).strftime("%Y-%m-%d") / str(uuid.uuid4())
        self.path.mkdir(parents=True)
        self.keys = set()
        self.key = key
        self.group = 0
        self.requests = 0
        self.on_event = on_event

    @property
    def key(self):
        return self._key

    @key.setter
    def key(self, value):
        self._key = value
        if value and value != "lalc-no-key":
            self.keys.add(value)

    def clean(self, value):
        if isinstance(value, str):
            for key in self.keys:
                value = value.replace(key, "[REDACTED]")
            return value
        if isinstance(value, list):
            return [self.clean(item) for item in value]
        if isinstance(value, dict):
            return {name: self.clean(item) for name, item in value.items()}
        return value

    def record(self, value):
        if isinstance(value, str):
            value = {"type": "stderr", "message": value}
        event = self.clean({"time": datetime.now(timezone.utc).isoformat(), "round": self.group, "event": value})
        with (self.path / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        if self.on_event:
            self.on_event(event)

    def save_json(self, name, value):
        (self.path / name).write_text(json.dumps(self.clean(value), ensure_ascii=False, indent=2), encoding="utf-8")

    def snapshot(self, name, files):
        directory = self.path / name
        directory.mkdir()
        for relative, content in files.items():
            path = directory / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)


def final_answer(message):
    text = "".join(part.get("text", "") for part in message.get("content", []) if part.get("type") == "text")
    value = json.loads(text)
    if (not isinstance(value, dict) or type(value.get("revise_success")) is not bool
            or not isinstance(value.get("message"), str) or not value["message"].strip()):
        raise ValueError("Final answer must be JSON with boolean revise_success and non-empty message")
    return value


async def configure_session(send, event, log, expected_tools):
    """确认实际工具集并关闭自动重试和压缩，供预检与修复共用。"""
    while True:
        item = await rpc_event(event, "就绪事件 lalc_ready")
        log.record(item)
        if item.get("type") == "extension_error":
            raise RuntimeError(str(item))
        if item.get("type") == "lalc_ready":
            if item.get("tools") != expected_tools:
                raise RuntimeError("Unexpected repair tools")
            break
    for setting in ("set_auto_retry", "set_auto_compaction"):
        await send({"id": setting, "type": setting, "enabled": False})
        while True:
            item = await rpc_event(event, f"配置响应 {setting}")
            log.record(item)
            if item.get("id") == setting:
                if not item.get("success"):
                    raise RuntimeError(f"pi rejected {setting}")
                break


async def check_model_image(command, env, temporary, image, log):
    """用真实图片执行一次无工具请求；成功前不修改候选，计数沿用到修复。"""
    checking = {**env, "LALC_PI_PREFLIGHT": "1", "LALC_PI_SOURCE_ROOT": temporary,
                "LALC_PI_MAX_REQUESTS": "1", "LALC_PI_PAYLOAD_DIR": str(log.path.resolve())}
    prompt = {"type": "prompt", "message": "连接检查：请简短回答已收到，不调用工具。"}
    if image is not None:
        prompt = {"type": "prompt", "message": "简短描述随附图片中的可见内容。这是连接和图片输入检查，不调用工具。",
                  "images": [{"type": "image", "mimeType": "image/png", "data": base64.b64encode(image).decode()}]}
    if image is None:
        prompt = {"type": "prompt", "message": "连接检查：请简短回答已收到，不调用工具。"}
    last = {}
    async with rpc_session(command, checking, temporary, log.record) as (send, event):
        await configure_session(send, event, log, [])
        log.record({"type": "model_check_started", "prompt": prompt})
        await send(prompt)
        while True:
            item = await event()
            kind = item.get("type")
            if kind == "message_update":
                continue
            log.record(item)
            if kind == "lalc_request":
                log.requests = item["requests"]
            elif kind == "message_end" and item.get("message", {}).get("role") == "assistant":
                last = item["message"]
            elif kind == "extension_error" or (kind == "response" and not item.get("success")):
                raise RuntimeError("Model image check failed: " + str(item))
            elif kind == "agent_settled":
                if (log.requests != 1 or last.get("stopReason") != "stop"
                        or not any(part.get("type") == "text" and part.get("text", "").strip()
                                   for part in last.get("content", []))):
                    raise RuntimeError("Model image check failed: " + str(last.get("errorMessage") or last))
                log.record({"type": "model_check_passed", "requests": log.requests})
                return


class RepairConversation:
    """消息主动触发一轮；实际消息/图片/工具结果留在上下文，候选不随对话清空。"""

    def __init__(self, host):
        self.host = host
        self.log = RepairLog(host.service.data_root)
        self.history = []
        self.tools = RepairTools(host.service.data_root, self.log, platform=host.service.window_platform)

    def add_validation(self, result):
        self.log.record({"type": "validation", **result})
        self.history.append({"role": "user", "content": [{"type": "text", "text":
            "开发者执行完整校验：" + json.dumps(result, ensure_ascii=False)}], "timestamp": int(datetime.now().timestamp() * 1000)})

    async def run(self, message, names, args, *, image=None, key=None, on_event=None):
        """GUI/CLI 共用一轮处理；错误、超限和取消均保留已有修改，不自动追加提示。"""
        with self.host.service.activity("Agent"):
            names = selected_files(self.host.candidate, names)
            if not message.strip():
                raise ValueError("消息不能为空。")
            self.log.on_event = on_event
            self.log.group += 1
            self.log.requests = 0
            prefix = f"round-{self.log.group}"
            round_path = self.log.path / prefix
            round_path.mkdir()
            before = candidate_files(self.host.candidate)
            baseline = self.host.baseline()
            if not (self.log.path / "baseline").exists():
                self.log.snapshot("baseline", baseline)
            self.log.snapshot(f"{prefix}/original", before)
            result = {"status": "incomplete", "reason": "setup_error"}
            tools = self.tools
            tools.cancelled.clear()
            prior_history = list(self.history)
            try:
                settings = effective_settings(args, self.host.service.data_root)
                options = SimpleNamespace(**vars(args))
                for field, value in settings.items():
                    setattr(options, field, value)
                self.log.key = key if key is not None else resolve_key(options, settings, self.host.service.data_root)
                if image is not None:
                    from .recognition import decode_image
                    if not image.startswith(b"\x89PNG\r\n\x1a\n"):
                        raise ValueError("image must be a PNG")
                    decode_image(image)
                    (round_path / "input.png").write_bytes(image)
                prompt = {"type": "prompt", "message": "本轮允许编辑的已有文件：" + json.dumps(names, ensure_ascii=False)
                          + "\n用户消息：" + message}
                if image is not None:
                    prompt["images"] = [{"type": "image", "mimeType": "image/png", "data": base64.b64encode(image).decode()}]
                self.history.append(self.log.clean({"role": "user", "timestamp": int(datetime.now().timestamp() * 1000),
                    "content": [{"type": "text", "text": prompt["message"]}, *prompt.get("images", [])]}))
                input_record = {"prompt": prompt, "settings": settings,
                                    "selected_files": names, "source_manifest_id": json.loads(self.host.metadata.read_text())["manifest_id"],
                                    "pi": None, "tested_pi_version": PI_VERSION, "system_prompt": SYSTEM_PROMPT}
                self.log.save_json(f"{prefix}/input.json", input_record)
                with configured_pi(options, self.host.candidate.resolve(), self.log.key, SYSTEM_PROMPT,
                                   require_image=image is not None, on_warning=self.log.record) as (command, env, temporary, model):
                    input_record["pi"] = env["LALC_PI_VERSION"]
                    self.log.save_json(f"{prefix}/input.json", input_record)
                    env["LALC_PI_PAYLOAD_DIR"] = str(round_path.resolve())
                    # 预检实际请求计入本轮，历史消息不进入连接检查。
                    old_path = self.log.path
                    self.log.path = round_path
                    try:
                        await check_model_image(command, env, temporary, image, self.log)
                    finally:
                        self.log.path = old_path
                    env["LALC_PI_REQUESTS_USED"] = str(self.log.requests)
                    env["LALC_PI_REPAIR_FILES"] = json.dumps([str((self.host.candidate / name).resolve()) for name in names])
                    history_path = Path(temporary) / "history.json"
                    history_path.write_text(json.dumps(self.log.clean(prior_history)), encoding="utf-8")
                    env["LALC_PI_HISTORY"] = str(history_path)
                    expected = [name for name in REPAIR_TOOLS if names or name != "edit"]
                    command[command.index("--tools") + 1] = ",".join(expected)
                    async with rpc_session(command, env, temporary, self.log.record) as (send, event):
                        await configure_session(send, event, self.log, expected)
                        self.log.record({"type": "round_started", "selected_files": names, "model": model["id"], "prompt": prompt})
                        await send(prompt)
                        last = {}
                        while True:
                            item = await event()
                            kind = item.get("type")
                            if kind == "message_update":
                                continue
                            self.log.record(item)
                            if kind == "lalc_request":
                                self.log.requests = item["requests"]
                            elif kind == "message_end":
                                received = item.get("message", {})
                                if received.get("role") != "user":
                                    self.history.append(self.log.clean(received))
                                if received.get("role") == "assistant":
                                    last = received
                            elif kind == "extension_error" or (kind == "response" and not item.get("success")):
                                raise RuntimeError(str(item))
                            elif kind == "extension_ui_request":
                                title = item.get("title", "")
                                if item.get("method") != "input":
                                    raise RuntimeError("Unexpected interactive request")
                                if title == "lalc.validate":
                                    errors = self.host.manager.validate(self.host.candidate / "manifest.json")
                                    validation = {"ok": not errors, "errors": [error.as_dict() for error in errors]}
                                    self.log.record({"type": "validation", **validation})
                                    value = json.dumps(self.log.clean(validation))
                                elif title.startswith("lalc.tool:"):
                                    request = json.loads(title.removeprefix("lalc.tool:"))
                                    value = await asyncio.to_thread(tools.call, request["name"], request["arguments"])
                                else:
                                    raise RuntimeError("Unexpected interactive request")
                                await send({"type": "extension_ui_response", "id": item["id"], "value": value})
                            elif kind == "agent_settled":
                                if last.get("stopReason") != "stop":
                                    reason = "request_limit" if "LALC request limit reached" in last.get("errorMessage", "") else "provider_error"
                                    result = {"status": "incomplete", "reason": reason, "answer": last}
                                else:
                                    answer = final_answer(last)
                                    result = {"status": "completed", "reason": "answered", "answer": answer}
                                break
            except asyncio.CancelledError:
                tools.cancelled.set()
                result = {"status": "cancelled", "reason": "user_cancelled"}
            except Exception as error:
                result = {"status": "incomplete", "reason": "error", "error": str(error)}
                self.log.record({"type": "repair_error", **_exception_fields(error)})
            finally:
                tools.cancelled.set()
                try:
                    after = candidate_files(self.host.candidate)
                    self.log.snapshot(f"{prefix}/final", after)
                    changed = [name for name in before.keys() | after.keys() if before.get(name) != after.get(name)]
                    unauthorized = [name for name in changed if name not in names or name not in before or name not in after]
                    if unauthorized:
                        result.update(status="incomplete", reason="unauthorized_changes", unauthorized_files=unauthorized)
                    diff = file_diff(baseline, after)
                    (round_path / "cumulative.diff").write_text(self.log.clean(diff), encoding="utf-8")
                except Exception as error:
                    result.update(status="incomplete", artifact_error=str(error))
                result.update(requests=self.log.requests, round=self.log.group, log_path=str(self.log.path))
                self.log.save_json(f"{prefix}/result.json", result)
                self.log.save_json("result.json", result)
                self.log.save_json("context.json", self.history)
                self.log.record({"type": "round_finished", **result})
            return self.log.clean(result)


def run_repair(args, manager, candidate):
    """CLI 同样使用当前 Candidate；可显式交互续聊，默认只处理一条消息。"""
    from .application import ApplicationService
    from .developer import DeveloperHost
    host = DeveloperHost(ApplicationService(manager.data_root, manifest_manager=manager), candidate)
    try:
        names = list(args.files)
        if args.all_files:
            names = [name for name in candidate_files(candidate) if "plan.json" not in Path(name).parts]
        selected_files(candidate, names)
        conversation = host.new_conversation()
        image = args.image.read_bytes() if args.image else None
        message = args.problem + ("\n异常信息：" + args.exception if args.exception else "")
        while True:
            result = asyncio.run(conversation.run(message, names, args, image=image))
            print(json.dumps(result, ensure_ascii=False), flush=True)
            if not args.chat:
                return 0 if result["status"] == "completed" else 130 if result["status"] == "cancelled" else 1
            message = input("消息（空行退出）：")
            if not message.strip():
                return 0
            image = None
    except (KeyboardInterrupt, EOFError):
        return 130
    except Exception as error:
        print(json.dumps({"status": "incomplete", "error": str(error)}, ensure_ascii=False))
        return 1
