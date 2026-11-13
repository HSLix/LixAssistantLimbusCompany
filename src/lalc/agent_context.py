"""准备一次性历史迁入和图片引用；有效上下文及压缩边界由 pi 保存。"""

import base64
import hashlib
import json
from pathlib import Path

from .agent_log import LogStore


def context_bootstrap(log, history, options):
    """为 pi 提供旧消息、人工消息游标和可验证图片 ID，不传旧图原文。"""
    store = LogStore(log.root)
    image_ids, inputs = {}, []
    sequence = 0
    events = log.root / "events.jsonl"
    if events.exists():
        for sequence, line in enumerate(events.read_text(encoding="utf-8").splitlines(), 1):
            images = []

            def reference(ref):
                image_id = f"{sequence}:{len(images)}"
                images.append(ref)
                image_ids.setdefault(ref["sha256"], image_id)
                return {"image_id": image_id}

            row = store.unpack(json.loads(line), image_handler=reference)
            event = row.get("event", {})
            if event.get("type") == "session_message":
                message = event["message"]
                text = message.get("content", "")
                if isinstance(text, list):
                    text = "\n".join(part.get("text", "") for part in text if part.get("type") == "text")
                inputs.append({"sequence": sequence, "message": message, "text": text})

    def strip(value):
        if isinstance(value, list):
            return [strip(item) for item in value]
        if not isinstance(value, dict):
            return value
        if value.get("type") == "image":
            data = value.get("data")
            image_id = data.get("image_id") if isinstance(data, dict) else image_ids.get(
                hashlib.sha256(base64.b64decode(data, validate=True)).hexdigest())
            if not image_id:
                raise ValueError("历史图片缺少可恢复的本地引用。")
            return {"type": "text", "text": image_reference(log.identity, image_id)}
        return {key: strip(item) for key, item in value.items()}

    return {"history": strip(history), "inputs": strip(inputs), "source_sequence": sequence,
            "session_id": log.identity, "image_ids": image_ids,
            "policy": {name: options[name] for name in (
                "context_image_limit", "context_compaction_mode", "context_compaction_ratio", "context_compaction_tokens")}}


def image_reference(session_id, image_id):
    """引用不授予权限；旧图仅由已授权历史工具显式读取。"""
    return (f"[历史图片，非当前画面：session_id={session_id}, image_id={image_id}；"
            "需要查看时调用 read_agent_session，须具有当前历史读取权限。]")


def checked_session_file(directory):
    """拒绝缺失、截断或结构损坏的已迁入状态，保留唯一旧副本。"""
    directory = Path(directory)
    directory.mkdir(exist_ok=True)
    path = directory / "session.jsonl"
    if directory.is_symlink() or path.is_symlink():
        raise ValueError("pi Session 不允许符号链接。")
    if (directory / "initialized").exists() and not path.exists():
        raise ValueError("pi Session 文件丢失；不能以完整旧日志覆盖压缩状态。")
    if path.exists():
        content = path.read_text(encoding="utf-8")
        if not content or not content.endswith("\n"):
            raise ValueError("pi Session 不完整；原文件保留，未重新导入。")
        rows = [json.loads(line) for line in content.splitlines()]
        if rows[0].get("type") != "session" or rows[0].get("version") != 3:
            raise ValueError("未知 pi Session 格式。")
        ids = set()
        for row in rows[1:]:
            identity = row.get("id")
            if not identity or identity in ids or row.get("parentId") is not None and row["parentId"] not in ids:
                raise ValueError("pi Session 消息关联损坏。")
            ids.add(identity)
    return path
