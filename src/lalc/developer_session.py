"""持久开发会话；CLI Repair 与后续 GUI 共用存储，不接管手工 Candidate。"""

from __future__ import annotations

import base64
import json
from pathlib import Path
import re
import tempfile
import uuid

from .agent_log import FORMAT, read_events
from .agent_policy import allowed_tools
from .developer import DeveloperHost, candidate_files
from .runtime import atomic_write_json


def restored_history(events):
    """从已保存事件重建消息；缺失的工具结果明确标为未知，不执行任何工具。"""
    history, pending, results = [], {}, {}

    def finish_calls():
        for identity, call in pending.items():
            result = results.get(identity, {
                "content": [{"type": "text", "text": "宿主中断，执行结果未知；不代表未执行或成功。请检查实际状态后自行判断如何继续，不自动重放。"}],
                "isError": True, "details": {"interrupted": True, "outcome": "unknown"}})
            history.append({"role": "toolResult", "toolCallId": identity, "toolName": call["name"],
                            "content": result["content"], "details": result.get("details", {}),
                            "isError": result.get("isError", False), "timestamp": call.get("timestamp", 0)})
        pending.clear()
        results.clear()

    for row in events:
        event = row["event"]
        kind = event.get("type")
        message = None
        if kind == "session_message":
            message = event["message"]
        elif kind == "lalc_request":
            message = event.get("budget_message")
        elif kind == "message_end" and event.get("message", {}).get("role") != "user":
            message = event["message"]
        elif kind in {"repair_tool", "tool_execution_end"} and event.get("toolCallId") in pending:
            result = event.get("result")
            if result is not None:
                results[event["toolCallId"]] = {**result, "isError": event.get("isError", result.get("isError", False))}
        elif kind == "validation" and event.get("toolCallId") in pending:
            result = {"ok": event["ok"], "errors": event["errors"]}
            results[event["toolCallId"]] = {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                                             "details": result}
        if message is None:
            continue
        if message["role"] == "toolResult":
            identity = message["toolCallId"]
            if identity not in pending:
                raise ValueError("Session 工具结果缺少关联调用。")
            pending.pop(identity)
            results.pop(identity, None)
        else:
            finish_calls()
        history.append(message)
        if message["role"] == "assistant":
            for part in message.get("content", []):
                if part.get("type") == "toolCall":
                    if part["id"] in pending:
                        raise ValueError("Session 同一消息的工具调用 ID 重复。")
                    pending[part["id"]] = part
    finish_calls()
    return history


class DeveloperSession:
    """固定身份与来源；所有可变状态须在 Candidate 跨进程锁内恢复。"""

    def __init__(self, service, identity, *, entry="cli"):
        if not isinstance(identity, str) or str(uuid.UUID(identity)) != identity:
            raise ValueError("Session ID 必须是标准 UUID。")
        self.entry = entry
        self.identity = identity
        self.path = service.data_root / "developer-sessions" / identity
        self.host = DeveloperHost(service, self.path / "candidate")
        self.host.session = self

    @classmethod
    def create(cls, service, manifest_id, *, mode="Repair", entry="cli"):
        """从明确版本或 Construct 空白准备完整目录后提交，失败不暴露半成品。"""
        allowed_tools(mode, entry)
        if (mode == "Repair" or manifest_id is not None) and (not isinstance(manifest_id, str) or not manifest_id.strip()):
            raise ValueError("Repair Session 必须明确指定已发布 Manifest。")
        session = cls(service, str(uuid.uuid4()), entry=entry)
        root = session.path.parent
        if root.is_symlink():
            raise ValueError("Session 根目录不能是符号链接。")
        root.mkdir(parents=True, exist_ok=True)
        with session.host.candidate_lock(), tempfile.TemporaryDirectory(dir=root, prefix=".pending-") as temporary:
            prepared = Path(temporary) / "session"
            prepared.mkdir()
            candidate = prepared / "candidate"
            errors = service.manifest_manager.initialize_candidate(candidate, manifest_id=manifest_id, empty=manifest_id is None)
            if errors:
                raise ValueError(json.dumps([error.as_dict() for error in errors], ensure_ascii=False))
            atomic_write_json(prepared / ".candidate-baseline.json", {"manifest_id": manifest_id, "files": {
                name: base64.b64encode(value).decode() for name, value in candidate_files(candidate).items()}})
            atomic_write_json(prepared / "session.json", {
                "version": 1, "session_id": session.identity, "mode": mode, "source_manifest_id": manifest_id})
            log = prepared / "log"
            log.mkdir()
            atomic_write_json(log / "log-format.json", FORMAT)
            prepared.replace(session.path)
        return session

    def check(self):
        """按当前入口检查模式与存储；历史记录和路径不能扩张权限。"""
        if self.path.parent.is_symlink() or self.path.is_symlink() or not self.path.is_dir():
            raise ValueError("Session 不存在或路径无效。")
        for relative in ("session.json", ".candidate-baseline.json", "log", "log/log-format.json", "log/events.jsonl"):
            if (self.path / relative).is_symlink():
                raise ValueError("Session 元数据和日志不能是符号链接。")
        metadata = json.loads((self.path / "session.json").read_text(encoding="utf-8"))
        if (metadata.get("version") != 1 or metadata.get("session_id") != self.identity
                or metadata.get("mode") not in {"Repair", "Construct"}
                or metadata.get("source_manifest_id") is not None and not isinstance(metadata["source_manifest_id"], str)
                or metadata.get("mode") == "Repair" and not metadata.get("source_manifest_id")):
            raise ValueError("Session 元数据无效；CLI 仅能恢复 Repair Session。")
        source = metadata["source_manifest_id"]
        if source is not None and str(uuid.UUID(source)) != source:
            raise ValueError("Session 来源必须是标准 Manifest UUID。")
        allowed_tools(metadata["mode"], self.entry)
        self.mode = metadata["mode"]
        if json.loads((self.path / "log/log-format.json").read_text(encoding="utf-8")) != FORMAT:
            raise ValueError("不支持该 Session 日志格式。")
        if any(path.is_symlink() for path in (self.path / "log").rglob("*")):
            raise ValueError("Session 日志不能包含符号链接。")
        baseline = json.loads(self.host.metadata.read_text(encoding="utf-8"))
        if baseline["manifest_id"] != metadata["source_manifest_id"]:
            raise ValueError("Session 来源与固定基线不一致。")
        for name, content in baseline["files"].items():
            path = Path(name)
            if not name or "\\" in name or ":" in name or path.is_absolute() or ".." in path.parts or path.as_posix() != name:
                raise ValueError("Session 固定基线路径无效。")
            base64.b64decode(content, validate=True)
        candidate_files(self.host.candidate)
        return metadata

    def conversation(self):
        """打开只恢复已保存状态，不发模型请求或重做工具；执行前仍须再次读取。"""
        from .agent_repair import RepairConversation
        with self.host.candidate_lock():
            self.check()
            conversation = RepairConversation(self.host, session=self, entry=self.entry)
            self.restore(conversation)
            self.host.conversation = conversation
            return conversation

    def restore(self, conversation):
        """调用方持有锁；保留不完整日志尾部，标记中断并恢复编号和协议有效历史。"""
        self.check()
        log = conversation.log
        events_path = log.root / "events.jsonl"
        if events_path.exists():
            content = events_path.read_bytes()
            if content and not content.endswith(b"\n"):
                boundary = content.rfind(b"\n") + 1
                tail = content[boundary:]
                try:
                    json.loads(tail)
                except (ValueError, UnicodeError):
                    # 只隔离未写完的末条字节，完整历史解析 / 引用错误仍明确失败。
                    archive = log.root / f"interrupted-tail-{uuid.uuid4()}.bin"
                    archive.write_bytes(tail)
                    with events_path.open("r+b") as stream:
                        stream.truncate(boundary)
                else:
                    with events_path.open("ab") as stream:
                        stream.write(b"\n")
        events = list(read_events(events_path)) if events_path.exists() else []
        conversation.history = restored_history(events)
        rounds = sorted(int(path.name.removeprefix("round-")) for path in log.root.glob("round-*")
                        if re.fullmatch(r"round-[1-9][0-9]*", path.name) and path.is_dir())
        previous_group = log.group
        log.group = max(rounds, default=0)
        log.requests = max((row["event"]["requests"] for row in events
                            if row.get("round") == log.group and row["event"].get("type") == "lalc_request"), default=0)
        conversation.tools.sequence = max((int(match[1]) for path in log.root.glob("tool-*")
            if (match := re.match(r"tool-([0-9]+)(?:\.|-)", path.name))), default=0)
        conversation.tools.sequence = max(conversation.tools.sequence,
            max((row["event"]["sequence"] for row in events if row["event"].get("type") == "tool_reserved"), default=0))
        if previous_group != log.group:
            conversation.tools.previews.clear()
        for pattern in ("round-*/input-*", "tool-*.png"):
            for path in log.root.glob(pattern):
                if path.is_file():
                    log.store.register_image(path)
        for number in rounds:
            result_path = log.root / f"round-{number}/result.json"
            if result_path.exists():
                continue
            result = {"status": "interrupted", "reason": "host_interrupted", "round": number,
                      "outcome": "unknown", "log_path": str(log.root)}
            log.save_json(f"round-{number}/result.json", result)
            log.save_json("result.json", result)
            log.record({"type": "round_interrupted", **result})
            conversation.append_user({"role": "user", "content": [{"type": "text", "text":
                f"宿主中断了第 {number} 轮；已保存的改动保留，未取得的结果未知。请检查文件和实际状态，自行判断如何继续；不要假定未执行或成功，不自动重放。重启前的现场裁剪预览 ID 已失效。"}],
                "timestamp": 0})
        log.save_json("context.json", conversation.history)
