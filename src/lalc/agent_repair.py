"""开发者连续修复；已有文件编辑、逐轮额度和实际交互留存。"""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
import uuid

from .pi_probe import PI_VERSION, PiStartup, configured_pi, rpc_event, rpc_session
from .repair_tools import RepairTools
from .agent_policy import allowed_tools
from .manifest_reference import ManifestReference
from .agent_settings import settings_snapshot
from .developer import candidate_files, editable_files, file_diff
from .agent_diagnostics import AgentDiagnosticError, redact, error_details
from .agent_log import LogStore
from .agent_prompts import load_sop, system_prompt, FORMAT_RETRY_PREFIX, FORMAT_RETRY


class RepairLog:
    """每对话一个交互目录；逐轮保留原始事件，认证值统一脱敏。"""

    def __init__(self, data_root: Path, key: str = "lalc-no-key", on_event=None, *, category="agent-interactions", path=None, identity=None):
        self.path = Path(path) if path is not None else data_root / category / datetime.now(timezone.utc).strftime("%Y-%m-%d") / str(uuid.uuid4())
        existing = self.path.exists()
        self.path.mkdir(parents=True, exist_ok=path is not None)
        self.root = self.path
        self.identity = identity or self.root.name
        self.store = LogStore(self.root)
        if not existing:
            self.store.initialize()
        self.transport_dir = None
        self.keys = set()
        self.key = key
        self.group = 0
        self.requests = 0
        self.transport_error = None
        self.on_event = on_event
        self.raw_content = {}

    @property
    def key(self):
        return self._key

    @key.setter
    def key(self, value):
        self._key = value
        if value and value != "lalc-no-key":
            self.keys.add(value)

    def clean(self, value):
        return redact(value, self.keys)

    def record(self, value):
        if isinstance(value, dict) and value.get("type") in {"message_start", "message_end", "repair_error", "round_finished"}:
            self.raw_content.clear()
        if isinstance(value, str):
            value = {"type": "stderr", "message": value}
        if value.get("type") == "lalc_request":
            self.transport_error = None
            if value.get("payload_path"):
                source = Path(value["payload_path"])
                if (self.transport_dir is None or source.resolve().parent != (self.transport_dir / "payloads").resolve()
                        or type(value.get("requests")) is not int or value["requests"] < 1
                        or source.name != f"request-{value['requests']}.json"):
                    raise ValueError("模型请求快照必须来自本轮临时传输目录。")
                target = self.root / f"round-{self.group}" / source.name
                self.store.write_json(target, self.clean(json.loads(source.read_text(encoding="utf-8"))))
                source.unlink()
                value = {**value, "payload_path": str(target)}
        elif value.get("type") == "lalc_transport_error":
            self.transport_error = self.clean(value)
        event = self.clean({"time": datetime.now(timezone.utc).isoformat(), "round": self.group, "event": value})
        with (self.path / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(self.store.pack(event), ensure_ascii=False) + "\n")
        if (value.get("type") == "tool_execution_end" and value.get("isError")
                or value.get("type") == "validation" and not value.get("ok")):
            import logging
            logging.getLogger(__name__).error("Agent 操作错误：%s", event)
        if self.on_event:
            self.on_event(event)

    def stream(self, value):
        """累计 pi 的内容块增量后脱敏，仅通知界面，不逐片写入历史。"""
        if not self.on_event:
            return
        event = value.get("assistantMessageEvent", {})
        kind, index = event.get("type", ""), event.get("contentIndex")
        if index is None:
            return
        block, _, phase = kind.partition("_")
        if block in {"text", "thinking"}:
            part = self.raw_content.setdefault(index, {"type": block, block: ""})
            if phase == "delta":
                part[block] += event.get("delta", "")
            elif phase == "end":
                part[block] = event.get("content", part[block])
        elif block == "toolcall":
            part = self.raw_content.setdefault(index, {"type": "toolCall", "name": "", "partialArgs": ""})
            if phase == "start":
                part["name"] = event.get("toolName", "")
            elif phase == "delta":
                part["partialArgs"] += event.get("delta", "")
            elif phase == "end":
                tool = event.get("toolCall", {})
                part.update(name=tool.get("name", part["name"]),
                            partialArgs=json.dumps(tool.get("arguments", {}), ensure_ascii=False))
        else:
            return
        self.on_event(self.clean({"round": self.group, "event": {
            "type": "raw_output", "content": [self.raw_content[key] for key in sorted(self.raw_content)]}}))

    def save_json(self, name, value):
        self.store.write_json(self.path / name, self.clean(value))

    def tool_result(self, name, value):
        """持久化用引用，给 pi 的临时传输文件仍是完整结果。"""
        self.save_json(name, value)
        if self.transport_dir is None:
            return str(self.path / name)
        path = self.transport_dir / name
        path.write_text(json.dumps(self.clean(value), ensure_ascii=False), encoding="utf-8")
        return str(path)

    def snapshot(self, name, files):
        directory = self.path / name
        directory.mkdir()
        for relative, content in files.items():
            path = directory / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            from .file_content import write_content
            write_content(path, content)


def final_answer(message):
    """严格解析完整回复为 JSON；不剥离说明或代码块，错误保留原文和解析位置。"""
    text = "".join(part.get("text", "") for part in message.get("content", []) if part.get("type") == "text")
    candidate = text
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as error:
        raise AgentDiagnosticError(
            f"模型最终回答不是可解析的 JSON：{error.msg}（第 {error.lineno} 行，第 {error.colno} 列）；请查看实际回复。",
            "final_answer", raw_text=text, json_text=candidate, parse_line=error.lineno,
            parse_column=error.colno, parse_offset=error.pos,
            hint="回复外层禁止三个反引号 ``` 或 ```json；正文直接以 { 开始、以 } 结束，message 字符串内部可以有 Markdown；格式纠正计入本轮请求上限。") from error
    if (not isinstance(value, dict) or type(value.get("revise_success")) is not bool
            or not isinstance(value.get("message"), str) or not value["message"].strip()):
        raise AgentDiagnosticError("Final answer must be JSON with boolean revise_success and non-empty message："
                                   "revise_success 必须是布尔值，message 必须是非空字符串。",
                                   "final_answer", raw_text=text, json_text=candidate, parsed_value=value)
    return value


def model_error(message, stage, requests, request_limit, transport=None):
    """区分请求额度、单次输出截断与服务错误，保留实际用量及结束原因。"""
    stop = message.get("stopReason")
    original = message.get("errorMessage") or ""
    usage = message.get("usage", {})
    if "LALC request limit reached" in original:
        code, summary = "request_limit", f"本轮请求次数已达到上限（{requests}/{request_limit}）。"
    elif stop == "length":
        code = "output_limit"
        summary = f"模型单次输出被长度上限截断（stopReason=length，输出 {usage.get('output', '未知')} token）；不是本轮请求次数超限。"
    else:
        code, summary = "provider_error", original or f"模型请求未正常结束（stopReason={stop or '未提供'}），服务未返回具体错误说明。"
    parts = message.get("content", [])
    if transport:
        summary += " 底层连接信息：" + json.dumps(transport.get("error", {}), ensure_ascii=False)
    return AgentDiagnosticError(summary, stage, failure_code=code, stop_reason=stop,
                                transport=transport,
                                provider_error=original or None, usage=usage,
                                requests_used=requests, request_limit=request_limit,
                                content_types=[part.get("type") for part in parts],
                                text_chars=sum(len(part.get("text", "")) for part in parts if part.get("type") == "text"),
                                thinking_chars=sum(len(part.get("thinking", "")) for part in parts if part.get("type") == "thinking"))


async def configure_session(send, event, log, expected_tools):
    """正式请求前确认实际工具集，并关闭自动重试和压缩。"""
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


def image_attachments(paths, directory):
    """按实际内容识别图片并原样留存整组附件；不按扩展名过滤或转码。"""
    if not paths:
        return [], []
    from io import BytesIO
    from PIL import Image
    result, records = [], []
    for index, path in enumerate(paths, 1):
        path = Path(path)
        content = path.read_bytes()
        try:
            with Image.open(BytesIO(content)) as image:
                kind = image.format.lower()
                mime = Image.MIME.get(image.format, "image/" + kind)
                image.verify()
        except (OSError, ValueError) as error:
            raise ValueError(f"附件不是有效图片：{path.name}：{error}") from error
        filename = f"input-{index}.{kind}"
        (directory / filename).write_bytes(content)
        result.append({"type": "image", "mimeType": mime, "data": base64.b64encode(content).decode()})
        records.append({"filename": filename, "original_name": path.name, "mime_type": mime})
    return result, records



class RepairConversation:
    """消息主动触发一轮；实际消息/图片/工具结果留在上下文，候选不随对话清空。"""

    def __init__(self, host, *, session=None, entry="cli"):
        self.host = host
        self.session = session
        self.entry = entry
        self.mode = session.mode if session else "Repair"
        self.allowed = allowed_tools(self.mode, entry)
        self.system_prompt = system_prompt(self.mode, {})
        self.log = RepairLog(host.service.data_root, path=session.path / "log" if session else None,
                             identity=session.identity if session else None)
        self.history = []
        self.tools = RepairTools(host.service.data_root, self.log, platform=host.service.window_platform, host=host, allowed=self.allowed)

    def append_user(self, message):
        """Session 的主动输入先记入持久事件，恢复不依赖轮末快照。"""
        message = self.log.clean(message)
        if self.session:
            self.log.record({"type": "session_message", "message": message})
        self.history.append(message)

    def add_validation(self, result):
        """手动校验立即落盘；来源标记避免 GUI 同时显示日志事件与完成回调。"""
        self.log.record({"type": "validation", "source": "manual", "toolCallId": "manual-" + str(uuid.uuid4()), **result})
        self.append_user({"role": "user", "content": [{"type": "text", "text":
            "开发者执行完整校验：" + json.dumps(result, ensure_ascii=False)}], "timestamp": int(datetime.now().timestamp() * 1000)})
        self.log.save_json("context.json", self.history)

    async def run(self, message, args, *, images=(), key=None, on_event=None, manifest_references=(), on_feedback=None, on_page_preview=None):
        """GUI/CLI 共用一轮处理；错误、超限和取消均保留已有修改，不自动追加提示。"""
        with self.host.candidate_lock(), self.host.service.activity("Agent"):
            if self.session:
                self.session.restore(self)
            if self.session and self.mode != self.session.mode:
                raise ValueError("Session 模式不能改变。")
            self.allowed = allowed_tools(self.mode, self.entry)
            self.tools.allowed = frozenset(self.allowed)
            references = list(dict.fromkeys(manifest_references))
            for identity in references:
                ManifestReference(self.host.manager).read(identity)
            names = editable_files(self.host.candidate)
            if not message.strip():
                raise ValueError("消息不能为空。")
            self.log.on_event = on_event
            self.log.group += 1
            self.log.requests = 0
            prefix = f"round-{self.log.group}"
            round_path = self.log.path / prefix
            round_path.mkdir()
            from .agent_history import record_observation
            from .agent_prompts import chat_title
            title = ''
            for prior in self.history:
                if prior.get('role') == 'user':
                    title = chat_title('\n'.join(part.get('text', '') for part in prior.get('content', []) if part.get('type') == 'text'))[0]
                    if title:
                        break
            observation = record_observation(self.log, self.host.service.data_root,
                                             f'{self.entry}:{self.mode}', title or chat_title(message)[0])
            if self.session:
                self.log.record({"type": "round_opened"})
            before = candidate_files(self.host.candidate)
            baseline = self.host.baseline()
            if not (self.log.path / "baseline").exists():
                self.log.snapshot("baseline", baseline)
            self.log.snapshot(f"{prefix}/original", before)
            result = {"status": "incomplete", "reason": "setup_error"}
            tools = self.tools
            tools.on_feedback = on_feedback
            tools.on_page_preview = on_page_preview
            tools.cancelled.clear()
            tools.created_files.clear()
            tools.knowledge.begin_round()
            prior_history = list(self.history)
            stage = "attachments"
            submitted = False
            runtime_context = {"mode": self.mode, "entry": self.entry,
                               "game_version_observation": observation,
                               "candidate": ".", "source_manifest_id": json.loads(self.host.metadata.read_text())["manifest_id"],
                               "editable_files": names, "manifest_references": references}
            prompt = {"type": "prompt", "message": "<runtime_context>\n"
                      + json.dumps(runtime_context, ensure_ascii=False)
                      + "\n</runtime_context>\n<user_request>\n" + message + "\n</user_request>"}
            self.log.keys.update(value for value in self.host.secrets.values() if value)
            context = {"conversation": self.log.identity, "round": self.log.group,
                       "log_path": str(round_path), "tested_pi_version": PI_VERSION}
            if key is not None:
                self.log.key = key
            def failed(error, failure_stage):
                details = error_details(error, failure_stage, context, self.log.keys)
                self.log.record({"type": "repair_error", **details})
                self.host.service.logger.error("Agent Repair 错误：%s", details)
                return details
            try:
                stage = "prompt"
                sop = load_sop(self.mode)
                self.system_prompt = system_prompt(self.mode, sop)
                stage = "attachments"
                attachments, attachment_records = image_attachments(images, round_path)
                for attachment in attachment_records:
                    self.log.store.register_image(round_path / attachment["filename"])
                if attachments:
                    prompt["images"] = attachments
                stage = "settings"
                settings, actual_key = settings_snapshot(args, self.host.service.data_root,
                                                         temporary_keys=self.host.secrets, key=key)
                context["settings"] = settings
                options = SimpleNamespace(**vars(args))
                for field, value in settings.items():
                    setattr(options, field, value)
                self.log.key = actual_key
                self.append_user({"role": "user", "timestamp": int(datetime.now().timestamp() * 1000),
                    "content": [{"type": "text", "text": prompt["message"]}, *prompt.get("images", [])]})
                submitted = True
                input_record = {"policy": "developer", "prompt": prompt, "settings": settings,
                                    "game_version_observation": observation,
                                    "attachments": attachment_records, "editable_files": names, "source_manifest_id": runtime_context["source_manifest_id"],
                                    "pi": None, "tested_pi_version": PI_VERSION, "system_prompt": self.system_prompt, "sop": sop, "mode": self.mode, "entry": self.entry,
                                    "manifest_references": references}
                self.log.save_json(f"{prefix}/input.json", input_record)
                stage = "pi_start"
                startup = PiStartup()
                with configured_pi(options, self.host.candidate.resolve(), self.log.key, self.system_prompt,
                                   require_image=bool(attachments), on_warning=self.log.record,
                                   startup=startup) as (command, env, temporary, model):
                    self.log.transport_dir = Path(temporary)
                    payloads = Path(temporary) / "payloads"
                    payloads.mkdir()
                    input_record.update(pi=env["LALC_PI_VERSION"], pi_path=command[0])
                    context.update(pi_version=env["LALC_PI_VERSION"], pi_path=command[0])
                    self.log.save_json(f"{prefix}/input.json", input_record)
                    image_path = Path(temporary) / "input-images.json"
                    image_path.write_text(json.dumps(attachments), encoding="utf-8")
                    env["LALC_PI_INPUT_IMAGES"] = str(image_path)
                    env["LALC_PI_INPUT_MESSAGE"] = prompt["message"]
                    env["LALC_PI_PAYLOAD_DIR"] = str(payloads)
                    env["LALC_PI_CONVERSATION_ROUND"] = str(self.log.group)
                    env["LALC_PI_ROUND_REQUEST_LIMIT"] = str(settings["max_requests"])
                    env["LALC_PI_REPAIR_FILES"] = json.dumps([str((self.host.candidate / name).resolve()) for name in names])
                    history_path = Path(temporary) / "history.json"
                    history_path.write_text(json.dumps(self.log.clean(prior_history)), encoding="utf-8")
                    env["LALC_PI_HISTORY"] = str(history_path)
                    expected = list(self.allowed)
                    env["LALC_PI_ALLOWED_TOOLS"] = json.dumps(expected)
                    command[command.index("--tools") + 1] = ",".join(expected)
                    stage = "pi_start"
                    async with rpc_session(command, env, temporary, self.log.record, startup=startup,
                                           pool=self.host.service.pi_process) as (send, event):
                        input_record.update(pi=env["LALC_PI_VERSION"], pi_path=command[0])
                        context.update(pi_version=env["LALC_PI_VERSION"], pi_path=command[0])
                        self.log.save_json(f"{prefix}/input.json", input_record)
                        await configure_session(send, event, self.log, expected)
                        stage = "agent"
                        self.log.record({"type": "round_started", "editable_files": names, "model": model["id"], "prompt": prompt})
                        # 原图经 context hook 注入，不进入 pi 的 RPC 图片转码流程。
                        await send({key: value for key, value in prompt.items() if key != "images"})
                        last = {}
                        while True:
                            item = await event()
                            kind = item.get("type")
                            if kind == "message_update":
                                self.log.stream(item)
                                continue
                            self.log.record(item)
                            if kind == "lalc_request":
                                self.log.requests = item["requests"]
                                if item.get("budget_message"):
                                    self.history.append(self.log.clean(item["budget_message"]))
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
                                if title.startswith("lalc.validate:"):
                                    if "validate" not in self.allowed:
                                        raise ValueError("当前模式和入口不允许 validate。")
                                    stage = "validation"
                                    errors = self.host.manager.validate(self.host.candidate / "manifest.json")
                                    validation = {"ok": not errors, "errors": [error.as_dict() for error in errors]}
                                    self.log.record({"type": "validation", "toolCallId": title.removeprefix("lalc.validate:"), **validation})
                                    value = json.dumps(self.log.clean(validation))
                                elif title.startswith("lalc.tool:"):
                                    request = json.loads(title.removeprefix("lalc.tool:"))
                                    stage = "tool:" + request["name"]
                                    pending = asyncio.create_task(asyncio.to_thread(
                                        tools.call, request["name"], request["arguments"],
                                        tool_call_id=request.get("tool_call_id")))
                                    try:
                                        value = await asyncio.shield(pending)
                                    except asyncio.CancelledError:
                                        tools.cancelled.set()
                                        await asyncio.gather(pending, return_exceptions=True)
                                        raise
                                else:
                                    raise RuntimeError("Unexpected interactive request")
                                await send({"type": "extension_ui_response", "id": item["id"], "value": value})
                                stage = "agent"
                            elif kind == "agent_settled":
                                if last.get("stopReason") != "stop":
                                    error = model_error(last, "provider_request", self.log.requests, settings["max_requests"], self.log.transport_error)
                                    reason = error.evidence["failure_code"]
                                    result = {"status": "incomplete", "reason": reason, "answer": last}
                                    result["error"] = str(error)
                                    result["diagnostics"] = failed(error, "provider_request")
                                else:
                                    stage = "final_answer"
                                    try:
                                        answer = final_answer(last)
                                    except AgentDiagnosticError as error:
                                        details = failed(error, stage)
                                        remaining = settings["max_requests"] - self.log.requests
                                        if remaining <= 0:
                                            result = {"status": "incomplete", "reason": "request_limit",
                                                      "error": details["message"] + " 本轮请求额度已耗尽。",
                                                      "diagnostics": {**details, "budget_exhausted": True}}
                                            break
                                        feedback = FORMAT_RETRY_PREFIX + details["message"] + "\n" + FORMAT_RETRY
                                        correction = {"type": "prompt", "message": feedback}
                                        self.log.record({"type": "final_answer_retry", "diagnostics": details,
                                                         "requests_remaining": remaining, "prompt": correction})
                                        self.append_user({"role": "user", "content": [{"type": "text", "text": feedback}],
                                                          "timestamp": int(datetime.now().timestamp() * 1000)})
                                        await send(correction)
                                        last = {}
                                        stage = "agent"
                                        continue
                                    result = {"status": "completed", "reason": "answered", "answer": answer}
                                break
            except asyncio.CancelledError:
                tools.cancelled.set()
                result = {"status": "cancelled", "reason": "user_cancelled"}
            except Exception as error:
                details = failed(error, stage)
                result = {"status": "incomplete", "reason": details.get("failure_code", "error"),
                          "error": details["message"], "diagnostics": details}
            finally:
                tools.on_feedback = None
                tools.on_page_preview = None
                if not submitted:
                    self.append_user({"role": "user", "timestamp": int(datetime.now().timestamp() * 1000),
                        "content": [{"type": "text", "text": prompt["message"]}, *prompt.get("images", [])]})
                self.log.transport_dir = None
                tools.cancelled.set()
                try:
                    after = candidate_files(self.host.candidate)
                    self.log.snapshot(f"{prefix}/final", after)
                    changed = [name for name in before.keys() | after.keys() if before.get(name) != after.get(name)]
                    unauthorized = [name for name in changed if name not in set(names) | tools.created_files
                                    or name not in after or name not in before and name not in tools.created_files]
                    if unauthorized:
                        result.update(status="incomplete", reason="unauthorized_changes", unauthorized_files=unauthorized)
                        result["error"] = "发现未授权文件变更：" + ", ".join(unauthorized)
                        result["diagnostics"] = failed(RuntimeError(result["error"]), "authorization")
                    diff = file_diff(baseline, after)
                    (round_path / "cumulative.diff").write_text(self.log.clean(diff), encoding="utf-8")
                except Exception as error:
                    details = failed(error, "artifacts")
                    result.update(status="incomplete", artifact_error=details["message"],
                                  error=details["message"], diagnostics=details)
                result.update(requests=self.log.requests, round=self.log.group, log_path=str(self.log.path))
                self.log.save_json(f"{prefix}/result.json", result)
                self.log.save_json("result.json", result)
                self.log.save_json("context.json", self.history)
                self.log.record({"type": "round_finished", **result})
            return self.log.clean(result)


def run_repair(args, manager):
    """CLI 创建或恢复独立 Repair Session；输入等待不持锁，不接管手工草稿。"""
    from .application import ApplicationService
    from .developer_session import DeveloperSession
    service = ApplicationService(manager.data_root, manifest_manager=manager)
    conversation = None
    try:
        session = (DeveloperSession.create(service, args.manifest_id) if args.manifest_id
                   else DeveloperSession(service, args.session))
        print(json.dumps({"session_id": session.identity}, ensure_ascii=False), flush=True)
        conversation = session.conversation()
        images = args.image or []
        message = args.problem + ("\n异常信息：" + args.exception if args.exception else "")
        while True:
            result = asyncio.run(conversation.run(message, args, images=images))
            result["session_id"] = session.identity
            print(json.dumps(result, ensure_ascii=False), flush=True)
            if not args.chat:
                return 0 if result["status"] == "completed" else 130 if result["status"] == "cancelled" else 1
            message = input("消息（空行退出）：")
            if not message.strip():
                return 0
            images = []
    except (KeyboardInterrupt, EOFError):
        return 130
    except Exception as error:
        keys = conversation.log.keys if conversation else ()
        details = error_details(error, "repair_setup", keys=keys)
        service.logger.error("Agent Repair 错误：%s", details)
        print(json.dumps({"status": "incomplete", "error": details["message"], "diagnostics": details}, ensure_ascii=False))
        return 1
    finally:
        service.shutdown()
