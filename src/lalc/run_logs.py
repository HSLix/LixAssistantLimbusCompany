"""执行日志的快照、双向分块读取和完整正文搜索；不修改原始 Trace。"""

from __future__ import annotations

import json
from pathlib import Path
from threading import Event

from .file_content import FileContent, open_image, require_memory


ACTION_ENDS = {"trusted_action_returned", "trusted_action_failed", "trusted_action_interrupted"}


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
    path = root / "evidence" / str(run_id) / f"{number}.png"
    if (path.is_symlink() or path.parent.is_symlink() or (root / "evidence").is_symlink()
            or not path.resolve().is_relative_to(root.resolve())):
        return None
    return path


def log_text(record: dict) -> str:
    """构造完整可搜索正文；显示折叠不改变此文本。"""
    if record.get("event") not in ACTION_ENDS:
        return str(record.get("message", ""))
    status = record["event"].removeprefix("trusted_action_")
    if status in {"failed", "interrupted"}:
        status += " (attempted)"
    text = f"{record['logical_name']} · {status}\n" + json.dumps(record.get("inputs", {}), ensure_ascii=False)
    result = record.get("return_value")
    if record["logical_name"] == "observe.match_asset" and isinstance(result, list):
        text += "\n" + "\n".join(f"#{i}: score={item['score']}" for i, item in enumerate(result, 1))
    if result is not None:
        text += "\n" + json.dumps(result, ensure_ascii=False, indent=2)
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
