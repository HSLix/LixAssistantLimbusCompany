"""执行日志的快照、双向分块读取和完整正文搜索；不修改原始 Trace。"""

from __future__ import annotations

import json
from pathlib import Path
from threading import Event

from .file_content import FileContent, open_image, require_memory


ACTION_ENDS = {"trusted_action_returned", "trusted_action_failed", "trusted_action_interrupted"}
LIVE_LOG_LIMIT = 300
LIVE_STATE_EVENTS = {
    "run_started", "run_paused", "paused_by_user", "run_resumed", "input_resumed",
    "input_resume_requested", "input_resume_rejected", "run_cancel_requested",
    "component_failed", "execution_anomaly", "safe_task_termination",
    "step_reinvocation_failed", "run_finished",
}


def is_live_log(record: dict) -> bool:
    """仅筛选运行弹窗可见事件，完整 Trace 的存储不受此过滤影响。"""
    event = record.get("event")
    if event == "component_log":
        return record.get("level", "info").lower() in {"info", "warning", "error"}
    return event in LIVE_STATE_EVENTS


def trace_path(root: Path, run_id: int) -> Path:
    """只访问数据目录内的正式数字 Run 文件，拒绝链接越界。"""
    if type(run_id) is not int or run_id < 1:
        raise ValueError("Invalid Run ID")
    path = root / "traces" / f"{run_id}.jsonl"
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("Run log unavailable")
    return path


def snapshot(root: Path, run_id: int) -> tuple:
    """固定完整换行记录的末尾，不将正在追加的半行纳入本次阅读。"""
    path = trace_path(root, run_id)
    with path.open("rb") as stream:
        import os
        stat = os.fstat(stream.fileno())
        end = stat.st_size
        while end:
            start = max(0, end - 65536)
            stream.seek(start)
            chunk = stream.read(end - start)
            newline = chunk.rfind(b"\n")
            if newline >= 0:
                end = start + newline + 1
                break
            end = start
    return stat.st_dev, stat.st_ino, end, stat.st_mtime_ns, stat.st_size


def image_path(root: Path, run_id: int, record: dict) -> Path | None:
    """仅解析当前 Run 的证据 ID，不信任历史绝对路径。"""
    metadata = record.get("debug_image", record)
    identity = metadata.get("evidence_id", "") if isinstance(metadata, dict) else ""
    prefix, _, number = str(identity).partition("/")
    if prefix != str(run_id) or not number.isdecimal():
        return None
    for extension in ("avif", "png"):
        path = root / "evidence" / str(run_id) / f"{number}.{extension}"
        if (path.is_symlink() or path.parent.is_symlink() or (root / "evidence").is_symlink()
                or not path.resolve().is_relative_to(root.resolve())):
            return None
        if path.is_file() or extension == "png":
            return path


def display_json(value, depth=0):
    """保留 JSON 层次；短标量数组单行显示，字符串内容不做文本替换。"""
    compact = json.dumps(value, ensure_ascii=False)
    if not isinstance(value, (dict, list)) or not value:
        return compact
    if isinstance(value, list) and all(not isinstance(item, (list, dict)) for item in value) and len(compact) + depth * 2 <= 80:
        return compact
    pad, child = "  " * depth, "  " * (depth + 1)
    if isinstance(value, dict):
        parts = [child + json.dumps(key, ensure_ascii=False) + ": " + display_json(item, depth + 1)
                 for key, item in value.items()]
        return "{\n" + ",\n".join(parts) + "\n" + pad + "}"
    return "[\n" + ",\n".join(child + display_json(item, depth + 1) for item in value) + "\n" + pad + "]"


def log_text(record: dict) -> str:
    """构造完整可搜索正文；显示折叠不改变此文本。"""
    if record.get("event") not in ACTION_ENDS:
        text = str(record.get("message", ""))
        if text.lstrip().startswith(("{", "[")):
            try:
                return display_json(json.loads(text))
            except ValueError:
                pass
        return text
    status = record["event"].removeprefix("trusted_action_")
    if status in {"failed", "interrupted"}:
        status += " (attempted)"
    text = f"{record['logical_name']} · {status}\n" + json.dumps(record.get("inputs", {}), ensure_ascii=False)
    result = record.get("return_value")
    if record["logical_name"] == "observe.match_asset" and isinstance(result, list):
        text += "\n" + "\n".join(f"#{i}: score={item['score']}" for i, item in enumerate(result, 1))
    if result is not None:
        text += "\n" + display_json(result)
    for key in ("failure_message", "message", "traceback", "reason"):
        if record.get(key):
            text += "\n" + str(record[key])
    if record.get("debug_image", {}).get("image_unavailable"):
        text += "\n[No screenshot available]"
    return text


def lines(path: Path, start: int, end: int, reverse: bool, cancelled: Event):
    """在固定字节区间内分块扫描；暂不解析仍未换行的尾记录。"""
    with path.open("rb") as stream:
        stream.seek(max(start, end - 1))
        complete = end <= start or stream.read(1) == b"\n"
        if reverse:
            position, pending, skip = end, b"", not complete
            while position > start:
                if cancelled.is_set():
                    return
                size = min(65536, position - start)
                position -= size
                stream.seek(position)
                pending = stream.read(size) + pending
                require_memory(len(pending) * 12)
                parts = pending.split(b"\n")
                pending = parts[0]
                offset = position + len(pending) + 1
                indexed = []
                for part in parts[1:]:
                    indexed.append((offset, offset + len(part) + 1, part))
                    offset += len(part) + 1
                for a, b, part in reversed(indexed):
                    if b > end:  # split 后最后一个元素是尾片段。
                        if skip:
                            skip = False
                        continue
                    if part.strip():
                        yield a, b, part
            if pending.strip() and not skip:
                yield start, start + len(pending) + 1, pending
        else:
            stream.seek(start)
            pending, offset = b"", start
            while stream.tell() < end:
                if cancelled.is_set():
                    return
                pending += stream.read(min(65536, end - stream.tell()))
                require_memory(len(pending) * 12)
                parts = pending.split(b"\n")
                pending = parts.pop()
                for part in parts:
                    finish = offset + len(part) + 1
                    if part.strip():
                        yield offset, finish, part
                    offset = finish


def retained_runs(root):
    """列出可保留读取的本机 Run，实际访问仍经路径校验。"""
    return sorted((int(path.stem) for path in (root / "traces").glob("*.jsonl")
                   if path.stem.isdecimal() and int(path.stem) > 0 and not path.is_symlink()), reverse=True)


def trace_records(root, run_id, *, reverse=False, check=lambda: None):
    """按快照流式读取完整事件；损坏行交给调用者计数，不读取追加中的半行。"""
    boundary = snapshot(root, run_id)
    for _, _, raw in lines(trace_path(root, run_id), 0, boundary[2], reverse, Event()):
        check()
        try:
            record = json.loads(raw)
            if not isinstance(record, dict):
                raise ValueError("Invalid trace record")
            yield record
        except (ValueError, UnicodeError):
            yield None


def run_log_counts(root, run_id, *, check=lambda: None):
    """统计整份 Run 快照的显式警告与错误等级，不受分页和筛选影响。"""
    counts = {"scope": "full_run", "warning": 0, "error": 0, "damaged_records": 0}
    for record in trace_records(root, run_id, check=check):
        if record is None:
            counts["damaged_records"] += 1
            continue
        level = record.get("level")
        if isinstance(level, str) and level.lower() in {"warning", "error"}:
            counts[level.lower()] += 1
    return counts


def run_summary(root, run_id, *, check=lambda: None):
    """只读首尾事件，缺失终态时不把历史 Run 冒充正在运行。"""
    first = next((r for r in trace_records(root, run_id, check=check) if r), {})
    last = next((r for r in trace_records(root, run_id, reverse=True, check=check) if r), {})
    start = first if first.get("event") == "run_started" else {}
    end = last if last.get("event") == "run_finished" else {}
    result = end.get("result")
    result = result if isinstance(result, dict) else {}
    trial = start.get("developer_trial")
    duration = None
    try:
        from datetime import datetime
        duration = (datetime.fromisoformat(end["recorded_at"]) - datetime.fromisoformat(start["recorded_at"])).total_seconds()
    except (KeyError, TypeError, ValueError):
        pass
    return {"run_id": run_id, "started_at": start.get("recorded_at"), "finished_at": end.get("recorded_at"),
            "duration_seconds": duration, "status": result.get("status", "unknown"),
            "logical_name": start.get("logical_name"), "manifest_id": start.get("base_manifest_id"),
            "source": "agent_trial" if trial is True else "user" if trial is False else "unknown",
            "result": result or None, "failure_reason": result.get("failure_message") or result.get("reason")}


def query_trace(root, run_ids, *, start_sequence=1, limit=100, levels=None, logical_name=None,
                keyword="", check=lambda: None):
    """组合条件按事件原文筛选，返回下一条匹配的位置，扫描内存不随文件增长。"""
    if type(start_sequence) is not int or start_sequence < 1 or type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("start_sequence 必须为正整数，limit 必须为 1–200。")
    if levels is not None and (not isinstance(levels, list) or not levels or
                              any(not isinstance(level, str) or level not in {"debug", "info", "warning", "error"} for level in levels)):
        raise ValueError("levels 必须为非空日志级别列表。")
    if logical_name is not None and (not isinstance(logical_name, str) or not logical_name):
        raise ValueError("logical_name 必须为非空字符串。")
    if not isinstance(keyword, str):
        raise ValueError("keyword 必须为字符串。")
    matches, damaged = [], 0
    for index, run_id in enumerate(run_ids):
        for record in trace_records(root, run_id, check=check):
            if record is None or type(record.get("sequence")) is not int:
                damaged += 1
                continue
            if record["sequence"] < (start_sequence if index == 0 else 1):
                continue
            level = record.get("level", "debug" if str(record.get("event", "")).startswith("trusted_action_") else "info")
            if levels is not None and level not in levels:
                continue
            if logical_name is not None and record.get("logical_name") != logical_name:
                continue
            if keyword.casefold() not in json.dumps(record, ensure_ascii=False).casefold():
                continue
            if len(matches) == limit:
                return {"matches": matches, "next": {"start_run_id": run_id, "start_sequence": record["sequence"]},
                        "damaged_records": damaged}
            matches.append({"run_id": run_id, "sequence": record["sequence"], "record": record})
    return {"matches": matches, "next": None, "damaged_records": damaged}


def read_page(root: Path, run_id: int, boundary: tuple, *, start=0, end=None,
              reverse=True, levels=("error", "warning", "info"), keyword="", images=False,
              limit=60, cancelled=None) -> dict:
    """读取一批匹配项；稀疏搜索可扫描全区间，但不全量保存或解码。"""
    cancelled = cancelled or Event()
    path = trace_path(root, run_id)
    current = snapshot(root, run_id)
    if current[:2] != boundary[:2] or current[2] < boundary[2]:
        raise ValueError("Run log was replaced or truncated; select it again")
    end = boundary[2] if end is None else min(end, boundary[2])
    rows, damaged = [], 0
    if not levels:
        return {"rows": rows, "damaged": damaged}
    for a, b, raw in lines(path, start, end, reverse, cancelled):
        if cancelled.is_set():
            return {"rows": [], "damaged": damaged}
        try:
            record = json.loads(raw)
            if not isinstance(record, dict):
                raise ValueError("Invalid record")
            event = record.get("event")
            if event != "component_log" and event not in ACTION_ENDS:
                continue
            if event in ACTION_ENDS and (not isinstance(record.get("logical_name"), str)
                                        or not isinstance(record.get("inputs", {}), dict)
                                        or not isinstance(record.get("debug_image", {}), dict)):
                raise ValueError("Invalid action record")
            level = "debug" if event in ACTION_ENDS else record.get("level", "info")
            if level not in levels:
                continue
            text = log_text(record)
            if keyword.casefold() not in (str(record.get("logical_name", "")) + "\n" + text).casefold():
                continue
            image = image_path(root, run_id, record)
            if images and image is None:
                continue
            dimensions = (16, 9)
            if image is not None:
                try:
                    with open_image(FileContent.from_path(image)) as decoded:
                        dimensions = decoded.size
                except (OSError, ValueError):
                    pass
            rows.append({"offset": a, "end": b, "record": record, "text": text,
                         "image": image, "dimensions": dimensions, "level": level})
            if len(rows) == limit:
                break
        except (ValueError, KeyError, TypeError):
            damaged += 1
    if not reverse:
        rows.reverse()
    return {"rows": rows, "damaged": damaged}
