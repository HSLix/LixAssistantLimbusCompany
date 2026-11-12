"""每轮版本留证、可重建 SQLite 索引及有界只读历史；不自动导入旧日志。"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import re
import sqlite3
import uuid

from .work_files import WorkDirectory
from .agent_log import FORMAT, LogStore, read_json
from .game_version import observe_game_version
from .process_lock import ProcessLock


DATABASE = "agent-history.sqlite3"
MARKER = ".agent-history-initialized"
SCHEMA = """
CREATE TABLE IF NOT EXISTS rounds (
 session_id TEXT NOT NULL, round INTEGER NOT NULL, path TEXT NOT NULL,
 source TEXT NOT NULL, title TEXT NOT NULL, game_version TEXT, steam_build_id TEXT,
 observed_at TEXT NOT NULL, PRIMARY KEY (session_id, round));
PRAGMA user_version=1;
"""


def _paging(offset, limit):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("offset must be nonnegative; limit must be 1–200")


def _uuid(value):
    if not isinstance(value, str) or str(uuid.UUID(value)) != value:
        raise ValueError("Session ID must be a canonical UUID")


def _group_details(observation=None):
    observation = dict(observation or {})
    game, build = observation.get("game_version"), observation.get("steam_build_id")
    return {"game_version": game, "steam_build_id": build,
            "label": (f"{game} / Steam {build or 'Unknown'}" if game else f"Steam {build}" if build else "Unknown")}


def _safe_path(data_root, relative):
    """索引只定位本数据目录的既有日志类别，拒绝任意路径与符号链接。"""
    root = Path(data_root).resolve()
    if (not isinstance(relative, str) or "\\" in relative or ":" in relative
            or Path(relative).is_absolute() or ".." in Path(relative).parts):
        raise ValueError("Invalid history path")
    parts = Path(relative).parts
    if not ((len(parts) == 3 and parts[0] == "developer-sessions" and parts[2] == "log")
            or (len(parts) == 3 and parts[0] in {"developer-operations", "agent-interactions", "agent-diagnostics"})):
        raise ValueError("Unknown history directory category")
    _uuid(parts[1] if parts[0] == "developer-sessions" else parts[2])
    path = root
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise ValueError("History symlinks are forbidden")
    if not path.resolve().is_relative_to(root):
        raise ValueError("History path escapes the data directory")
    return path


class AgentHistory:
    """事务化索引按日志 UUID / 轮次去重；读取不恢复或执行历史 Session。"""

    def __init__(self, data_root):
        self.root = Path(data_root).resolve()
        self.database = self.root / DATABASE

    def lock(self):
        return ProcessLock("agent-history:" + str(self.root))

    @contextmanager
    def connection(self, *, write=False, path=None):
        target = path or self.database
        if target.is_symlink():
            raise ValueError("History database symlinks are forbidden")
        if not write and not target.exists():
            if (self.root / MARKER).exists():
                raise ValueError("History index is missing; run lalc history-rebuild")
            yield None
            return
        if write and path is None and not target.exists() and (self.root / MARKER).exists():
            raise ValueError("History index is missing; run lalc history-rebuild")
        self.root.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(target) if write else target.as_uri() + "?mode=ro", uri=not write, timeout=.25)
        connection.row_factory = sqlite3.Row
        try:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version != 1:
                if version == 0 and write and (path is not None or not (self.root / MARKER).exists()):
                    connection.executescript(SCHEMA)
                else:
                    raise ValueError("Unsupported history index; run lalc history-rebuild")
            yield connection
            if write:
                connection.commit()
        except sqlite3.DatabaseError as error:
            raise ValueError("History index unavailable; run lalc history-rebuild: " + str(error)) from error
        finally:
            connection.close()

    def _row(self, record, log_root):
        if not isinstance(record, dict):
            raise ValueError("Invalid history observation document")
        identity, number = record["session_id"], record["round"]
        _uuid(identity)
        if record.get("version") != 1 or type(number) is not int or number < 0:
            raise ValueError("Invalid history observation identity")
        relative = Path(log_root).absolute().relative_to(self.root).as_posix()
        path = _safe_path(self.root, relative)
        if (path / "log-format.json").is_symlink():
            raise ValueError("History format marker symlinks are forbidden")
        if identity != (path.parent.name if path.name == "log" else path.name):
            raise ValueError("History UUID does not match its log directory")
        observation = record["observation"]
        game, build = observation.get("game_version"), observation.get("steam_build_id")
        if ((game is not None and (not isinstance(game, str) or not re.fullmatch(r"\d+\.\d+\.\d+[A-Za-z0-9.+-]*", game)))
                or (build is not None and (not isinstance(build, str) or not re.fullmatch(r"[1-9][0-9]{0,19}", build)))
                or not isinstance(observation.get("observed_at"), str)
                or not isinstance(record.get("source"), str) or not isinstance(record.get("title"), str)):
            raise ValueError("Invalid history observation fields")
        observed = datetime.fromisoformat(observation["observed_at"].replace("Z", "+00:00"))
        if observed.utcoffset() != timezone.utc.utcoffset(observed):
            raise ValueError("Observation time must be UTC")
        timestamp = observed.isoformat(timespec="microseconds").replace("+00:00", "Z")
        return (identity, number, relative, record["source"], record["title"], game, build, timestamp)

    def add(self, record, log_root):
        row = self._row(record, log_root)
        with self.lock(), self.connection(write=True) as connection:
            assert connection is not None
            # 同一轮的原始观测不可被重放或工具读取改写。
            existing = connection.execute("SELECT * FROM rounds WHERE session_id=? AND round=?", row[:2]).fetchone()
            if existing is not None and tuple(existing) != row:
                raise ValueError("Conflicting observation for the same Session round")
            connection.execute("INSERT OR IGNORE INTO rounds VALUES (?,?,?,?,?,?,?,?)", row)
        (self.root / MARKER).touch(exist_ok=True)

    @staticmethod
    def filters(game_version=None, steam_build_id=None, unknown=False, source=None, version_group=None):
        if type(unknown) is not bool or any(value is not None and (not isinstance(value, str) or not value)
                                            for value in (game_version, steam_build_id, source)):
            raise ValueError("Invalid history filter")
        if unknown and (game_version is not None or steam_build_id is not None):
            raise ValueError("Unknown cannot be combined with a version identifier")
        clauses, values = [], []
        if version_group is not None:
            if (not isinstance(version_group, dict)
                    or not {"game_version", "steam_build_id"} <= version_group.keys()
                    or version_group.keys() - {"game_version", "steam_build_id", "label"}
                    or any(version_group[key] is not None and (not isinstance(version_group[key], str) or not version_group[key])
                           for key in ("game_version", "steam_build_id"))
                    or unknown or game_version is not None or steam_build_id is not None):
                raise ValueError("Use an exact version_group OR individual version filters")
            clauses.append("game_version IS ? AND steam_build_id IS ?")
            values.extend([version_group["game_version"], version_group["steam_build_id"]])
        for name, value in (("game_version", game_version), ("steam_build_id", steam_build_id), ("source", source)):
            if value is not None:
                clauses.append(name + "=?")
                values.append(value)
        if unknown:
            clauses.append("game_version IS NULL AND steam_build_id IS NULL")
        return " AND ".join(clauses) or "1", values

    def versions(self, offset=0, limit=50, source=None):
        _paging(offset, limit)
        clause, values = self.filters(source=source)
        with self.connection() as connection:
            rows = [] if connection is None else connection.execute(
                "SELECT game_version, steam_build_id, COUNT(DISTINCT session_id) session_count, "
                "MAX(observed_at) last_observed_at FROM rounds WHERE " + clause
                + " GROUP BY game_version, steam_build_id ORDER BY last_observed_at DESC, game_version, steam_build_id LIMIT ? OFFSET ?",
                [*values, limit + 1, offset]).fetchall()
        return {"versions": [{**dict(row), "version_group": _group_details(row)} for row in rows[:limit]],
                "next_offset": offset + limit if len(rows) > limit else None}

    def search(self, game_version=None, steam_build_id=None, unknown=False, source=None, offset=0, limit=50, version_group=None):
        _paging(offset, limit)
        clause, values = self.filters(game_version, steam_build_id, unknown, source, version_group)
        with self.connection() as connection:
            rows = [] if connection is None else connection.execute(
                "SELECT session_id, MIN(title) title, MAX(observed_at) last_observed_at FROM rounds WHERE " + clause
                + " GROUP BY session_id ORDER BY last_observed_at DESC, session_id LIMIT ? OFFSET ?",
                [*values, limit + 1, offset]).fetchall()
            sessions = []
            for row in rows[:limit]:
                assert connection is not None
                matches = connection.execute("SELECT * FROM rounds WHERE session_id=? AND " + clause + " ORDER BY round LIMIT 21",
                                             [row["session_id"], *values]).fetchall()
                arguments = {"session_id": row["session_id"]}
                arguments.update({key: value for key, value in (("game_version", game_version), ("steam_build_id", steam_build_id),
                                                               ("unknown", unknown or None), ("source", source), ("version_group", version_group)) if value is not None})
                sessions.append({**dict(row), "matches": [{"round": item["round"], "source": item["source"],
                                 "version_group": _group_details(item), "observed_at": item["observed_at"]} for item in matches[:20]],
                                 "more_matching_rounds": len(matches) > 20, "read_arguments": arguments})
        return {"sessions": sessions, "next_offset": offset + limit if len(rows) > limit else None}

    def rebuild(self):
        """显式从新增观测重建；原子替换前失败保留原索引，不导入无观测旧日志。"""
        self.root.mkdir(parents=True, exist_ok=True)
        with self.lock(), WorkDirectory(dir=self.root, prefix=".history-rebuild-") as temporary:
            target = Path(temporary) / DATABASE
            count = 0
            with self.connection(write=True, path=target) as connection:
                assert connection is not None
                for pattern in ("developer-sessions/*/log/version-observations/*.json",
                                "developer-operations/*/*/version-observations/*.json",
                                "agent-interactions/*/*/version-observations/*.json",
                                "agent-diagnostics/*/*/version-observations/*.json"):
                    for path in sorted(self.root.glob(pattern)):
                        log_root = path.parent.parent
                        _safe_path(self.root, log_root.relative_to(self.root).as_posix())
                        if path.is_symlink() or path.parent.is_symlink():
                            raise ValueError("History observation symlinks are forbidden")
                        record = read_json(path)
                        connection.execute("INSERT INTO rounds VALUES (?,?,?,?,?,?,?,?)", self._row(record, log_root))
                        count += 1
            if self.database.is_symlink():
                raise ValueError("History database symlinks are forbidden")
            target.replace(self.database)
            (self.root / MARKER).touch(exist_ok=True)
        return {"observations": count}

    def read(self, session_id, round_numbers=None, start_sequence=1, limit=20, text_offset=0, image_id=None,
             game_version=None, steam_build_id=None, unknown=False, source=None, version_group=None):
        """按完整事件分页；超长事件可续读片段，图片只按本事件引用显式取回。"""
        _uuid(session_id)
        _paging(start_sequence - 1 if type(start_sequence) is int else -1, limit)
        if (type(text_offset) is not int or text_offset < 0
                or round_numbers is not None and (not isinstance(round_numbers, list) or not round_numbers
                    or any(type(n) is not int or n < 0 for n in round_numbers))):
            raise ValueError("Invalid history round selection or text offset")
        clause, values = self.filters(game_version, steam_build_id, unknown, source, version_group)
        with self.connection() as connection:
            indexed = [] if connection is None else connection.execute(
                "SELECT * FROM rounds WHERE session_id=? ORDER BY round", (session_id,)).fetchall()
            if clause != "1":
                if round_numbers is not None:
                    raise ValueError("Choose either explicit rounds or version/source filters")
                round_numbers = [] if connection is None else [row[0] for row in connection.execute(
                    "SELECT round FROM rounds WHERE session_id=? AND " + clause, [session_id, *values]).fetchall()]
        if not indexed:
            raise ValueError("Session is not indexed or its history is unavailable")
        paths = {item["path"] for item in indexed}
        if len(paths) != 1:
            raise ValueError("Conflicting Session log locations")
        root = _safe_path(self.root, paths.pop())
        store = LogStore(root)
        marker = root / "log-format.json"
        events_path = root / "events.jsonl"
        if marker.is_symlink() or events_path.is_symlink() or json.loads(marker.read_text(encoding="utf-8")) != FORMAT:
            raise ValueError("Invalid Session log format or path")
        versions = {}
        def round_version(number):
            if number not in versions:
                directory = root / "version-observations"
                path = directory / f"{number}.json"
                if directory.is_symlink() or path.is_symlink():
                    raise ValueError("History observation symlinks are forbidden")
                if path.exists():
                    record = read_json(path)
                    if not isinstance(record, dict):
                        raise ValueError("Invalid history observation document")
                    self._row(record, root)
                    if record["round"] != number:
                        raise ValueError("Observation round mismatch")
                    versions[number] = _group_details(record["observation"])
                else:
                    versions[number] = _group_details()
            return versions[number]
        image_sequence, image_number = None, None
        if image_id is not None:
            if not isinstance(image_id, str) or not re.fullmatch(r"[1-9][0-9]*:[0-9]+", image_id):
                raise ValueError("Invalid history image ID")
            image_sequence, image_number = map(int, image_id.split(":"))
        events, continuation, incomplete = [], None, False
        budget = 24000
        with events_path.open(encoding="utf-8") as stream:
            for sequence, line in enumerate(stream, 1):
                if not line.endswith("\n"):
                    incomplete = True
                    break
                if sequence < (image_sequence or start_sequence):
                    continue
                raw = json.loads(line)
                number = raw.get("round", 0)
                if type(number) is not int or number < 0:
                    raise ValueError("Invalid history event round")
                if round_numbers is not None and number not in round_numbers:
                    if sequence == image_sequence:
                        raise ValueError("Image does not belong to the selected rounds")
                    continue
                images = []
                def image_reference(reference):
                    images.append(reference)
                    return {"image_id": f"{sequence}:{len(images) - 1}"}
                event = store.unpack(raw, image_handler=image_reference)
                group = round_version(number)
                if image_sequence is not None:
                    assert image_number is not None
                    if sequence != image_sequence or image_number >= len(images):
                        raise ValueError("Image is not referenced by this Session event")
                    reference = images[image_number]
                    image_path = store._path(reference["path"])
                    if image_path.is_symlink() or image_path.stat().st_size > 32 * 1024 * 1024:
                        raise ValueError("History image is a symlink or exceeds 32 MiB")
                    content = image_path.read_bytes()
                    if hashlib.sha256(content).hexdigest() != reference["sha256"]:
                        raise ValueError("History image hash mismatch")
                    mime = ("image/png" if content.startswith(b"\x89PNG\r\n\x1a\n") else
                            "image/jpeg" if content.startswith(b"\xff\xd8\xff") else
                            "image/gif" if content.startswith((b"GIF87a", b"GIF89a")) else
                            "image/webp" if content[:4] == b"RIFF" and content[8:12] == b"WEBP" else None)
                    if mime is None:
                        raise ValueError("Unsupported history image format")
                    return {"session_id": session_id, "round": number, "version_group": group,
                            "image_id": image_id, "mime_type": mime}, content
                text = json.dumps(event, ensure_ascii=False)
                if text_offset > len(text):
                    raise ValueError("History text offset exceeds the selected event")
                fragment = text[text_offset:text_offset + budget]
                events.append({"sequence": sequence, "round": number, "version_group": group,
                               "text_offset": text_offset, "text": fragment,
                               "images": [f"{sequence}:{i}" for i in range(min(100, len(images)))],
                               "image_count": len(images)})
                if text_offset + len(fragment) < len(text):
                    continuation = {"start_sequence": sequence, "text_offset": text_offset + len(fragment)}
                    break
                budget -= len(fragment)
                text_offset = 0
                if len(events) == limit or budget < 1024:
                    continuation = {"start_sequence": sequence + 1, "text_offset": 0}
                    break
        if image_id is not None:
            raise ValueError("History image is unavailable")
        return {"session_id": session_id, "events": events, "next": continuation, "incomplete_tail": incomplete}, None


def record_observation(log, data_root, source, title):
    """先持久留证再更新索引；故障只记诊断，不阻断对话或覆盖旧观测。"""
    observation = log.clean(observe_game_version(data_root))
    record = log.clean({"version": 1, "session_id": log.identity, "round": log.group,
                        "source": source, "title": title, "observation": observation})
    try:
        directory = log.root / "version-observations"
        directory.mkdir(exist_ok=True)
        path = directory / f"{log.group}.json"
        if directory.is_symlink() or path.exists() or path.is_symlink():
            raise ValueError("Version observation already exists or its path is invalid")
        log.save_json(f"version-observations/{log.group}.json", record)
        log.record({"type": "game_version_observed", **record})
        AgentHistory(data_root).add(record, log.root)
    except Exception as error:
        message = log.clean(str(error))
        logging.getLogger(__name__).error("Agent history index: %s", message)
        try:
            log.record({"type": "history_index_error", "message": message})
        except Exception:
            logging.getLogger(__name__).exception("Cannot persist history index error")
    for error in observation["errors"]:
        logging.getLogger(__name__).error("Game version observation: %s", error)
    return observation
