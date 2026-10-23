"""人工启动单 Component 修复，保留逐组交互与候选产物，不发布或运行候选。"""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import uuid

from .manifest import ManifestManager
from .pi_probe import PI_VERSION, configured_pi, rpc_session
from .repair_tools import REPAIR_TOOLS, RepairTools
from .agent_settings import effective_settings, resolve_key


SYSTEM_PROMPT = """你是 LALC 单 Component 修复助手。必须实际 read 源码、edit 指定文件、validate 完整候选，按反馈迭代。
源码只能读取候选目录中的文件，只能编辑指定目标；禁止修改 manifest.json、其他源码或正式发布物。
使用 asset_tree 发现素材名称，asset_directory 查看全部文件名和原始标签，asset_images 按完整逻辑名和完整哈希查看一张或多张图片。
action_contracts 返回应用实际动作契约，不执行动作。game_screenshot 可查看当前游戏，crop_asset 从新截图裁剪新增素材。
每次截图/裁剪都会恢复并置前唯一游戏窗口；工具失败可再次调用，不使用旧截图替代。非 Windows 平台实时工具不可用。
裁剪只能新增素材；同名同哈希复用原图和旧标签。不得改已有图片/标签；新增素材失败或取消后也保留。
不运行命令、候选代码或点击/按键，不发布或设置 Default。材料不足或单文件无法解决时说明原因并结束。
LALC 约束：Python 模块有中文职责 docstring；execute 使用一个原有的 plain @task_workflow/@sub_workflow/@step，保留角色与签名。
Task 可通过 ctx.call 调用 Subworkflow/Step；Subworkflow 只能调用 Step；Step 不调用正式 Component。
使用字面量 ctx.call/ctx.action 名称，不创建 Trusted Action 或 Recovery Rule。业务数据用参数、返回值和局部变量传递。
只有 Step 可以有可选的只读 condition，签名与 execute 一致。Task 返回 JSON 兼容结果。未知状态应抛出 ExecutionFailure。
Validator 会导入 Python，不是安全沙箱；禁止生成顶层副作用、文件操作、网络、子进程或绕过 ctx 的后台调用。
每轮交互只有最后回答是 JSON 对象：{"revise_success": true或false, "message": "说明修改或改不了的原因"}。
revise_success 是你对本轮修订的判断，不代表真实游戏行为已修复。中间的工具调用不要加此字段。不要 Markdown 围栏。
"""


class RepairLog:
    """一次调用的独立留存；分组只在模型最终回答后结束，认证密钥不落盘。"""

    def __init__(self, data_root: Path, key: str):
        now = datetime.now(timezone.utc)
        self.path = data_root / "agent-interactions" / now.strftime("%Y-%m-%d") / str(uuid.uuid4())
        self.path.mkdir(parents=True)
        self.key = key
        self.group = 1
        self.requests = 0

    def clean(self, value):
        if isinstance(value, str):
            return value.replace(self.key, "[REDACTED]") if self.key != "lalc-no-key" else value
        if isinstance(value, list):
            return [self.clean(item) for item in value]
        if isinstance(value, dict):
            return {name: self.clean(item) for name, item in value.items()}
        return value

    def record(self, value) -> None:
        """逐事件追加，保留完整图片载荷；终端仅展示摘要。"""
        if isinstance(value, str):
            value = {"type": "stderr", "message": value}
        event = self.clean({"time": datetime.now(timezone.utc).isoformat(), "group": self.group, "event": value})
        with (self.path / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        if isinstance(value, dict) and value.get("type") in {"lalc_request", "group_finished", "validation"}:
            print(json.dumps(self.clean({name: item for name, item in value.items() if name != "payload"}),
                             ensure_ascii=False), flush=True)

    def save_json(self, name: str, value) -> None:
        (self.path / name).write_text(json.dumps(self.clean(value), ensure_ascii=False, indent=2), encoding="utf-8")

    def snapshot(self, name: str, source: Path, original: bytes) -> str:
        """从真实文件保存源码和实际 Diff，不使用模型生成的差异描述。"""
        content = source.read_bytes()
        (self.path / f"{name}.py").write_bytes(content)
        diff = "".join(difflib.unified_diff(original.decode("utf-8").splitlines(keepends=True),
                                           content.decode("utf-8").splitlines(keepends=True),
                                           fromfile="original/" + source.name, tofile="candidate/" + source.name))
        (self.path / f"{name}.diff").write_text(self.clean(diff), encoding="utf-8")
        return diff


def repair_baseline(manager: ManifestManager, candidate: Path, logical_name: str):
    """在模型接入及草稿替换前检查 Default、目标和工作目录。"""
    loaded = manager.load_default()
    if not loaded.ok:
        raise ValueError(json.dumps([error.as_dict() for error in loaded.errors], ensure_ascii=False))
    baseline = loaded.loaded
    if logical_name not in baseline.components:
        raise ValueError(f"Target is not an existing Task Workflow, Subworkflow or Step: {logical_name}")
    if candidate.is_symlink() or (candidate.exists() and not candidate.is_dir()):
        raise ValueError("candidate must be a real directory, not a link or file")
    return baseline


def prepare_candidate(manager: ManifestManager, candidate: Path, logical_name: str, baseline):
    """完整物化已固定的基线后替换草稿；不改变普通 init 语义。"""
    # 先物化完整基线，避免来源文件读取失败时已清空用户草稿。
    with tempfile.TemporaryDirectory(prefix=".lalc-repair-", dir=candidate.parent) as temporary:
        prepared = Path(temporary) / "candidate"
        errors = manager.initialize_candidate(prepared, manifest_id=baseline.manifest_id)
        if errors:
            raise ValueError(json.dumps([error.as_dict() for error in errors], ensure_ascii=False))
        source_name = f"{logical_name}.py"
        original = (prepared / source_name).read_bytes()
        if candidate.exists():
            shutil.rmtree(candidate)
        prepared.replace(candidate)
    return baseline.manifest_id, candidate / source_name, original


def validate_candidate(manager: ManifestManager, candidate: Path, log: RepairLog) -> dict:
    """沿用完整候选 Validator，向日志及模型返回实际诊断。"""
    errors = manager.validate(candidate / "manifest.json")
    result = {"ok": not errors, "errors": [error.as_dict() for error in errors]}
    log.record({"type": "validation", **result})
    return result


def final_answer(message: dict) -> dict:
    """只接受最终回答中的 JSON 和真正的布尔值，不猜测自然语言。"""
    text = "".join(part.get("text", "") for part in message.get("content", []) if part.get("type") == "text")
    value = json.loads(text)
    if (not isinstance(value, dict) or type(value.get("revise_success")) is not bool
            or not isinstance(value.get("message"), str) or not value["message"].strip()):
        raise ValueError("Final answer must be JSON with boolean revise_success and non-empty message")
    return value


async def configure_session(send, event, log, expected_tools):
    """确认实际工具集并关闭自动重试和压缩，供预检与修复共用。"""
    while True:
        item = await asyncio.wait_for(event(), timeout=30)
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
            item = await asyncio.wait_for(event(), timeout=30)
            log.record(item)
            if item.get("id") == setting:
                if not item.get("success"):
                    raise RuntimeError(f"pi rejected {setting}")
                break


async def check_model_image(command, env, temporary, image, log):
    """用真实图片执行一次无工具请求；成功前不修改候选，计数沿用到修复。"""
    checking = {**env, "LALC_PI_PREFLIGHT": "1", "LALC_PI_SOURCE_ROOT": temporary,
                "LALC_PI_MAX_REQUESTS": "1", "LALC_PI_PAYLOAD_DIR": str(log.path.resolve())}
    prompt = {"type": "prompt", "message": "简短描述随附图片中的可见内容。这是连接和图片输入检查，不调用工具。",
              "images": [{"type": "image", "mimeType": "image/png", "data": base64.b64encode(image).decode()}]}
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


async def repair_loop(command, env, temporary, prompt, manager, candidate, source, original, log):
    """复用 pi 工具循环；格式或最终校验反馈触发下一组，不改写上一组评价。"""
    last = {}
    tools = RepairTools(manager.data_root, log)
    async with rpc_session(command, env, temporary, log.record) as (send, event):
        await configure_session(send, event, log, REPAIR_TOOLS)
        log.record({"type": "initial_prompt", "prompt": prompt})
        await send(prompt)
        while True:
            item = await event()
            kind = item.get("type")
            # 完整 message_end 含最终文本、工具参数及图片；无需重复存储逐 token 增量。
            if kind == "message_update":
                continue
            log.record(item)
            if kind == "lalc_request":
                log.requests = item["requests"]
            elif kind == "extension_error" or (kind == "response" and not item.get("success")):
                raise RuntimeError(str(item))
            elif kind == "extension_ui_request":
                if item.get("method") != "input":
                    raise RuntimeError("Unexpected interactive request")
                title = item.get("title", "")
                if title == "lalc.validate":
                    result = json.dumps(log.clean(validate_candidate(manager, candidate, log)), ensure_ascii=False)
                elif title.startswith("lalc.tool:"):
                    request = json.loads(title.removeprefix("lalc.tool:"))
                    try:
                        result = await asyncio.to_thread(tools.call, request["name"], request["arguments"])
                    except asyncio.CancelledError:
                        tools.cancelled.set()
                        raise
                else:
                    raise RuntimeError("Unexpected interactive request")
                await send({"type": "extension_ui_response", "id": item["id"],
                            "value": result})
            elif kind == "message_end" and item.get("message", {}).get("role") == "assistant":
                last = item["message"]
            elif kind == "agent_settled":
                log.snapshot(f"group-{log.group}", source, original)
                if last.get("stopReason") != "stop":
                    reason = "request_limit" if "LALC request limit reached" in last.get("errorMessage", "") else "provider_error"
                    log.record({"type": "group_finished", "reason": reason, "answer": last})
                    return {"status": "incomplete", "reason": reason}
                validation = {"performed": False}
                try:
                    answer = final_answer(last)
                except (ValueError, TypeError) as error:
                    log.record({"type": "group_finished", "reason": "invalid_final", "error": str(error), "answer": last})
                    feedback = str(error) + '\n请纠正最终回答，仅输出 {"revise_success": true或false, "message": "说明"}。'
                else:
                    log.record({"type": "group_finished", "answer": answer})
                    if not answer["revise_success"]:
                        return {"status": "incomplete", "reason": "unable", "answer": answer,
                                "validation": validate_candidate(manager, candidate, log)}
                    validation = validate_candidate(manager, candidate, log)
                    if validation["ok"]:
                        return {"status": "completed", "reason": "validated_candidate", "answer": answer,
                                "validation": validation}
                    feedback = "最终候选校验失败，请按实际反馈继续修订：" + json.dumps(validation, ensure_ascii=False)
                if log.requests >= int(env["LALC_PI_MAX_REQUESTS"]):
                    return {"status": "incomplete", "reason": "request_limit", "validation": validation}
                log.group += 1
                last = {}
                log.record({"type": "feedback", "message": feedback})
                await send({"type": "prompt", "message": log.clean(feedback)})


def run_repair(args, manager: ManifestManager, candidate: Path) -> int:
    """独立修复入口；错误和中断保留产物，不改变 Default 或发布代码。"""
    key = "lalc-no-key"
    log = None
    source = None
    result = {"status": "incomplete", "reason": "setup_error"}
    original = b""
    try:
        baseline = repair_baseline(manager, candidate, args.logical_name)
        settings = effective_settings(args, manager.data_root)
        if settings["model"] is None:
            raise ValueError("Agent model is required; save it with agent-config --model or supply --model")
        for field, value in settings.items():
            setattr(args, field, value)
        key = resolve_key(args, settings, manager.data_root)
        image = args.image.read_bytes()
        if not image.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("image must be a PNG")
        # 模型连接、版本和输入预检先于草稿替换；这些失败无需牺牲旧草稿。
        log = RepairLog(manager.data_root, key)
        log.group = 0
        print(f"Agent Interaction Log: {log.path}", flush=True)
        log.save_json("input.json", {"source_manifest_id": baseline.manifest_id, "target": args.logical_name,
                                    "pi": PI_VERSION, "settings": settings, "system_prompt": SYSTEM_PROMPT})
        (log.path / "input.png").write_bytes(image)
        with configured_pi(args, candidate.resolve(), key, SYSTEM_PROMPT) as (command, env, temporary, model):
            asyncio.run(check_model_image(command, env, temporary, image, log))
            env["LALC_PI_REQUESTS_USED"] = str(log.requests)
            log.group = 1
            manifest_id, source, original = prepare_candidate(manager, candidate, args.logical_name, baseline)
            env["LALC_PI_REPAIR_TARGET"] = str(source.resolve())
            env["LALC_PI_PAYLOAD_DIR"] = str(log.path.resolve())
            command[command.index("--tools") + 1] = ",".join(REPAIR_TOOLS)
            (log.path / "original.py").write_bytes(original)
            (log.path / "input.png").write_bytes(image)
            prompt = {"type": "prompt", "message": f"目标文件：{source.name}\n问题与预期：{args.problem}\n异常/复现信息：{args.exception or '未提供'}",
                      "images": [{"type": "image", "mimeType": "image/png", "data": base64.b64encode(image).decode()}]}
            log.save_json("input.json", {"source_manifest_id": manifest_id, "target": args.logical_name,
                                        "pi": PI_VERSION, "base_url": env["LALC_PI_BASE_URL"], "model": model,
                                        "max_requests": args.max_requests, "settings": settings, "system_prompt": SYSTEM_PROMPT,
                                        "prompt": prompt, "image_sha256": hashlib.sha256(image).hexdigest()})
            result = asyncio.run(repair_loop(command, env, temporary, prompt, manager, candidate, source, original, log))
    except KeyboardInterrupt:
        result = {"status": "cancelled", "reason": "user_cancelled"}
    except Exception as error:
        result = {"status": "incomplete", "reason": "error", "error": str(error)}
    finally:
        if log is not None:
            result.setdefault("validation", {"performed": False})
            if source is not None:
                try:
                    log.snapshot("final", source, original)
                    result.update({"source_path": str(log.path / "final.py"),
                                   "diff_path": str(log.path / "final.diff")})
                except Exception as error:
                    result.update({"status": "incomplete", "artifact_error": str(error)})
            result.update({"requests": log.requests, "groups": log.group, "log_path": str(log.path)})
            log.save_json("result.json", result)
            log.record({"type": "repair_finished", **result})
            print(json.dumps(log.clean(result), ensure_ascii=False), flush=True)
        else:
            print(json.dumps(result, ensure_ascii=False).replace(key, "[REDACTED]"), flush=True)
    return 0 if result["status"] == "completed" else 130 if result["status"] == "cancelled" else 1
