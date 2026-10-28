"""开发者连续修复；已有文件编辑、逐轮额度和实际交互留存。"""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
import uuid

from .pi_probe import PI_VERSION, configured_pi, rpc_event, rpc_session
from .repair_tools import REPAIR_TOOLS, RepairTools
from .agent_settings import settings_snapshot
from .developer import candidate_files, editable_files, file_diff
from .agent_diagnostics import AgentDiagnosticError, redact, error_details
from .agent_log import LogStore


SYSTEM_PROMPT = """你是 LALC Developer Policy 开发助手。根据开发者 prompt 和当前游戏状态持续开发、调试工作流，需要修改时实际 read、edit，并 validate 完整候选。
只能读取 Candidate 内已有文件；可按需修改多个已有文件，包括 manifest.json、Recovery Rule 和未被 Manifest 引用的文件。
可编辑已有 Candidate Python Plan；不得执行可变 Candidate 路径，Plan 必须先 Publish。不通用新建、删除或重命名文件，不访问目录外文件。
新增源码仅用 add_component / add_recovery_rule，提供 filename、logical_name、source 完整源码，工具同时创建并登记 Manifest。
新增成功后同轮可 read/edit/validate；不自动登记已有未引用文件，不把工具成功当作完整校验通过。
校验失败不影响继续读取和修改；先前校验结果可从上下文查阅。信息不足时说明缺少什么并结束本轮，等待用户主动补充。
asset_tree/asset_directory/asset_images 只读共享素材；action_contracts 只读应用实际动作契约。
game_screenshot 返回现场原图和每隔40px的网格辅助图；辅助覆盖层不能进入模板或原始截图证据。
先 preview_crop(logical_name, region, threshold, tags) 取得区域标线图、干净裁剪图及同图匹配结果，再 crop_asset(preview_id) 保存完全相同的像素和参数，不重新截图。
预览不进入活跃素材库；同图匹配不证明跨状态可靠性，也不自动决定是否保存。同名同哈希保留原图和原标签。
remove_asset(logical_name, sha, reason) 可归档任意既有图片及原Tags、理由和移除时新截的原始游戏画面，再同步移除活跃图片及该逻辑名的标签关系；截图失败不移除。移除影响所有后续使用该素材的匹配。
非 Windows 现场工具不可用。截图会恢复并置前唯一游戏窗口。除专用移除归档外，不修改既有图片/标签、正式 Manifest/源码或 Trusted Actions。
trial_run 不提供 logical_name 时运行已保存 Manifest 的唯一 Python Plan，inputs 为 task_repetitions/settings；可自主使用 publish 保存完整不可变版本，再用 trial_run 指定 Manifest ID 及入口/输入试运行；修改 Candidate 后必须重新 Publish 才能运行新代码。
试运行支持 Candidate 内已有 JSON Plan 或 Task Workflow/Subworkflow/Step。运行期间等待工具结果，不并行修改或操作游戏。
启动拒绝无 Run ID，修正原因后可再次调用；已启动的结果带 Run ID，使用 list_runs 查看可用 ID、read_run_log 分段查看日志及引用截图。
试运行结果返回后可继续修改、发布、试运行直到完成开发要求；用户停止本次运行后建议总结并等待下个指示。
不运行命令、不直接点击或按键、不执行可变 Candidate、不设置 Default。Publish 不表示运行时永久批准。不要生成文件操作、网络、子进程、顶层副作用或绕过 ctx 的后台调用。
Validator 会导入 Python，不是安全沙箱，校验通过也不证明真实游戏行为修复。
遵守现有 Component、Recovery Rule 与 ctx.call/ctx.action 契约；ctx.log(message, screenshot=False) 可记录语义日志并可选附上已有截图，不重新截图。Python 模块和关键函数用简洁中文 docstring。
最终回答必须只输出一个合法 JSON 对象，格式为 {"revise_success": false, "message": "分析、修改结果或缺少的信息"}。
revise_success 必须是 JSON 布尔值 true 或 false，message 必须是非空字符串；不要输出 Markdown 代码块、前后说明或 JSON 之外的文字。
所有给用户的说明均放入 message 字段，包括纯分析和信息不足的情况。
revise_success 仅是本轮修订判断，不能代替校验或游戏验收。宿主反馈格式错误时，只重新生成最终 JSON，不调用工具、不重复修改。
合法最终回答后结束本轮，等待开发者下一条消息。
"""

FORMAT_RETRY_PREFIX = "LALC_FINAL_FORMAT_CORRECTION\n"


class RepairLog:
    """每对话一个交互目录；逐轮保留原始事件，认证值统一脱敏。"""

    def __init__(self, data_root: Path, key: str = "lalc-no-key", on_event=None, *, category="agent-interactions"):
        self.path = data_root / category / datetime.now(timezone.utc).strftime("%Y-%m-%d") / str(uuid.uuid4())
        self.path.mkdir(parents=True)
        self.root = self.path
        self.store = LogStore(self.root)
        self.store.initialize()
        self.transport_dir = None
        self.keys = set()
        self.key = key
        self.group = 0
        self.requests = 0
        self.transport_error = None
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
        return redact(value, self.keys)

    def record(self, value):
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
            path.write_bytes(content)


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
            hint="最终回答只能是一个 JSON 对象，禁止代码块和前后说明；格式纠正计入本轮请求上限。") from error
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


async def check_model_image(command, env, temporary, images, log):
    """整组图片只预检一次；成功前不修改候选，计数沿用到修复。"""
    checking = {**env, "LALC_PI_PREFLIGHT": "1", "LALC_PI_SOURCE_ROOT": temporary,
                "LALC_PI_MAX_REQUESTS": "1"}
    prompt = {"type": "prompt", "message": "连接检查：请简短回答已收到，不调用工具。"}
    if images:
        prompt = {"type": "prompt", "message": "简短描述随附图片中的可见内容。这是连接和图片输入检查，不调用工具。",
                  "images": images}
    checking["LALC_PI_INPUT_MESSAGE"] = prompt["message"]
    last = {}
    async with rpc_session(command, checking, temporary, log.record) as (send, event):
        await configure_session(send, event, log, [])
        log.record({"type": "model_check_started", "prompt": prompt})
        await send({key: value for key, value in prompt.items() if key != "images"})
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
                if last.get("stopReason") != "stop":
                    raise model_error(last, "model_preflight", log.requests, 1, log.transport_error)
                if (log.requests != 1 or not any(part.get("type") == "text" and part.get("text", "").strip()
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
        self.tools = RepairTools(host.service.data_root, self.log, platform=host.service.window_platform, host=host)

    def add_validation(self, result):
        """手动校验立即落盘；来源标记避免 GUI 同时显示日志事件与完成回调。"""
        self.log.record({"type": "validation", "source": "manual", **result})
        self.history.append({"role": "user", "content": [{"type": "text", "text":
            "开发者执行完整校验：" + json.dumps(result, ensure_ascii=False)}], "timestamp": int(datetime.now().timestamp() * 1000)})
        self.log.save_json("context.json", self.history)

    async def run(self, message, args, *, images=(), key=None, on_event=None):
        """GUI/CLI 共用一轮处理；错误、超限和取消均保留已有修改，不自动追加提示。"""
        with self.host.service.activity("Agent"), self.host.candidate_lock():
            names = editable_files(self.host.candidate)
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
            tools.created_files.clear()
            prior_history = list(self.history)
            stage = "settings"
            context = {"conversation": self.log.path.name, "round": self.log.group,
                       "log_path": str(round_path), "tested_pi_version": PI_VERSION}
            if key is not None:
                self.log.key = key
            def failed(error, failure_stage):
                details = error_details(error, failure_stage, context, self.log.keys)
                self.log.record({"type": "repair_error", **details})
                self.host.service.logger.error("Agent Repair 错误：%s", details)
                return details
            try:
                settings, actual_key = settings_snapshot(args, self.host.service.data_root,
                                                         temporary_keys=self.host.secrets, key=key)
                context["settings"] = settings
                options = SimpleNamespace(**vars(args))
                for field, value in settings.items():
                    setattr(options, field, value)
                self.log.key = actual_key
                stage = "attachments"
                attachments, attachment_records = image_attachments(images, round_path)
                for attachment in attachment_records:
                    self.log.store.register_image(round_path / attachment["filename"])
                prompt = {"type": "prompt", "message": "本轮允许编辑的已有文件：" + json.dumps(names, ensure_ascii=False)
                          + "\n用户消息：" + message}
                if attachments:
                    prompt["images"] = attachments
                self.history.append(self.log.clean({"role": "user", "timestamp": int(datetime.now().timestamp() * 1000),
                    "content": [{"type": "text", "text": prompt["message"]}, *prompt.get("images", [])]}))
                input_record = {"policy": "developer", "prompt": prompt, "settings": settings,
                                    "attachments": attachment_records, "editable_files": names, "source_manifest_id": json.loads(self.host.metadata.read_text())["manifest_id"],
                                    "pi": None, "tested_pi_version": PI_VERSION, "system_prompt": SYSTEM_PROMPT}
                self.log.save_json(f"{prefix}/input.json", input_record)
                stage = "pi_start"
                with configured_pi(options, self.host.candidate.resolve(), self.log.key, SYSTEM_PROMPT,
                                   require_image=bool(attachments), on_warning=self.log.record) as (command, env, temporary, model):
                    self.log.transport_dir = Path(temporary)
                    payloads = Path(temporary) / "payloads"
                    payloads.mkdir()
                    input_record["pi"] = env["LALC_PI_VERSION"]
                    context["pi_version"] = env["LALC_PI_VERSION"]
                    self.log.save_json(f"{prefix}/input.json", input_record)
                    image_path = Path(temporary) / "input-images.json"
                    image_path.write_text(json.dumps(attachments), encoding="utf-8")
                    env["LALC_PI_INPUT_IMAGES"] = str(image_path)
                    env["LALC_PI_INPUT_MESSAGE"] = prompt["message"]
                    env["LALC_PI_PAYLOAD_DIR"] = str(payloads)
                    env["LALC_PI_CONVERSATION_ROUND"] = str(self.log.group)
                    env["LALC_PI_ROUND_REQUEST_LIMIT"] = str(settings["max_requests"])
                    # 预检实际请求计入本轮，历史消息不进入连接检查。
                    old_path = self.log.path
                    self.log.path = round_path
                    try:
                        stage = "model_preflight"
                        await check_model_image(command, env, temporary, attachments, self.log)
                    finally:
                        self.log.path = old_path
                    env["LALC_PI_REQUESTS_USED"] = str(self.log.requests)
                    env["LALC_PI_REPAIR_FILES"] = json.dumps([str((self.host.candidate / name).resolve()) for name in names])
                    history_path = Path(temporary) / "history.json"
                    history_path.write_text(json.dumps(self.log.clean(prior_history)), encoding="utf-8")
                    env["LALC_PI_HISTORY"] = str(history_path)
                    expected = list(REPAIR_TOOLS)
                    command[command.index("--tools") + 1] = ",".join(expected)
                    stage = "pi_start"
                    async with rpc_session(command, env, temporary, self.log.record) as (send, event):
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
                                        feedback = (FORMAT_RETRY_PREFIX + "你的最终回答未通过严格 JSON 校验：\n"
                                                    + details["message"] + "\n只纠正最终输出格式，不调用工具，不重新执行或修改。"
                                                    '\n仅输出一个 JSON 对象：{"revise_success": false, "message": "说明"}。'
                                                    "revise_success 必须为 true 或 false，message 为非空字符串。"
                                                    "所有说明放入 message；禁止代码块、前后说明和 JSON 之外的文字。")
                                        correction = {"type": "prompt", "message": feedback}
                                        self.log.record({"type": "final_answer_retry", "diagnostics": details,
                                                         "requests_remaining": remaining, "prompt": correction})
                                        self.history.append(self.log.clean({"role": "user", "content": [{"type": "text", "text": feedback}],
                                                                            "timestamp": int(datetime.now().timestamp() * 1000)}))
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


def run_repair(args, manager, candidate):
    """CLI 同样使用当前 Candidate；可显式交互续聊，默认只处理一条消息。"""
    from .application import ApplicationService
    from .developer import DeveloperHost
    host = DeveloperHost(ApplicationService(manager.data_root, manifest_manager=manager), candidate)
    try:
        conversation = host.new_conversation()
        images = args.image or []
        message = args.problem + ("\n异常信息：" + args.exception if args.exception else "")
        while True:
            result = asyncio.run(conversation.run(message, args, images=images))
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
        keys = host.conversation.log.keys if host.conversation else ()
        details = error_details(error, "repair_setup", keys=keys)
        host.service.logger.error("Agent Repair 错误：%s", details)
        print(json.dumps({"status": "incomplete", "error": details["message"], "diagnostics": details}, ensure_ascii=False))
        return 1
