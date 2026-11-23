"""User GUI 数据盘点、运行使用摘要和人工清理事务。"""

import ast
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
import shutil
import stat
from threading import Lock
import uuid

from .assets import asset_name
from .manifest import ROLES, SECTIONS
from .manifest_reference import ManifestReference
from .page_packages import real_directory
from .run_logs import retained_runs, run_summary, snapshot, trace_records
from .run_log_sharing import list_logs
from .runtime import atomic_write_json
from .work_files import create_work_directory, work_file


DATA_ERRORS = (OSError, ValueError, TypeError, KeyError, OverflowError)
CLEANUP_ACTIVITY = "Data cleanup"


def _datetime(value):
    if isinstance(value, str):
        result = datetime.fromisoformat(value)
        if result.tzinfo is not None:
            return result.astimezone(UTC)
    raise ValueError("Invalid usage timestamp.")


def _file_stat(path):
    real_directory(path.parent)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or _junction(info):
        raise ValueError(f"Expected a regular file: {path.name}")
    return info


def _junction(info):
    return os.name == "nt" and info.st_reparse_tag == stat.IO_REPARSE_TAG_MOUNT_POINT


def _tree(path, *, fingerprint=True):
    """校验入口的父链，每个子项用一次不跟随链接的文件状态检查。"""
    real_directory(path.parent)

    def walk(current, info):
        directory = stat.S_ISDIR(info.st_mode)
        if _junction(info) or not (directory or stat.S_ISREG(info.st_mode)):
            raise ValueError(f"Cleanup does not accept links or special files: {current.name}")
        yield current, info.st_dev, info.st_ino, info.st_mtime_ns, 0 if directory else info.st_size
        if directory:
            with os.scandir(current) as children:
                for child in sorted(children, key=lambda child: child.name):
                    path = current / child.name
                    # Windows 的 DirEntry.stat 不提供文件标识，预览快照需要真实 stat。
                    info = path.lstat() if os.name == "nt" and fingerprint else child.stat(follow_symlinks=False)
                    yield from walk(path, info)

    return walk(path, path.lstat())


def _summary(root, identity):
    """从固定的完整 Trace 读取实际开始的调用，损坏时保留证据。"""
    _file_stat(root / "traces" / f"{identity}.jsonl")
    before = snapshot(root, identity)
    if not before[2] or before[2] != before[4]:
        raise ValueError(f"Run {identity} has an incomplete Trace.")
    manifests = {}
    components = {}
    for record in trace_records(root, identity, boundary=before):
        if record is None:
            raise ValueError(f"Run {identity} has a damaged Trace.")
        event = record.get("event")
        if event in {"run_started", "working_manifest_selected", "component_started", "recovery_rule_started"}:
            stamp = _datetime(record["recorded_at"]).isoformat()
            manifest = record.get("base_manifest_id" if event == "run_started" else "manifest_id")
            if not isinstance(manifest, str) or not manifest:
                raise ValueError(f"Run {identity} has an invalid Manifest event.")
            manifests[manifest] = max(manifests.get(manifest, stamp), stamp)
        if event in {"component_started", "recovery_rule_started"}:
            name, digest = record["logical_name"], record["component_id"]
            if not isinstance(name, str) or not isinstance(digest, str):
                raise ValueError(f"Run {identity} has an invalid Component event.")
            key = (name, digest)
            count, last = components.get(key, (0, stamp))
            components[key] = count + 1, max(last, stamp)
    if snapshot(root, identity) != before:
        raise ValueError(f"Run {identity} changed while reading.")
    return {"run_id": identity, "manifests": manifests, "components": [
        [name, digest, count, stamp] for (name, digest), (count, stamp) in sorted(components.items())
    ]}


def _add_summary(usage, value, identity):
    """验证摘要字段后再整体累加，避免损坏摘要只累加一部分。"""
    if (not isinstance(value, dict) or type(value.get("run_id")) is not int or value["run_id"] != identity
            or not isinstance(value.get("manifests"), dict) or not isinstance(value.get("components"), list)):
        raise ValueError("Invalid Run usage summary.")
    versions = [(key, 1, _datetime(stamp)) for key, stamp in value["manifests"].items()
                if isinstance(key, str)]
    sources = {}
    for name, digest, count, stamp in value["components"]:
        if (not isinstance(name, str) or not isinstance(digest, str)
                or type(count) is not int or count < 1 or (name, digest) in sources):
            raise ValueError("Invalid Component usage summary.")
        sources[name, digest] = count, _datetime(stamp)
    for group, rows in ((usage[0], versions), (usage[1], [(key, *counts) for key, counts in sources.items()])):
        for key, count, stamp in rows:
            old, last = group.get(key, (0, stamp))
            group[key] = old + count, max(last, stamp)


@dataclass(frozen=True)
class CleanupPlan:
    """仅包含人工预览的条目和文件快照，提交前必须重新生成。"""

    category: str
    keys: tuple
    rows: tuple
    sources: tuple
    targets: tuple
    fingerprints: tuple

    @property
    def size(self):
        return sum(item[-1] for item in self.fingerprints)


class DataMaintenance:
    """仅供人工页面调用的只读盘点和排他清理，始终复核保护规则。"""

    def __init__(self, service):
        self.service = service
        self.manager = service.manifest_manager
        self.root = service.data_root.absolute()
        self._usage_lock = Lock()
        self._trace_usage = {}

    def _versions(self):
        """拿到完整的静态引用表，同时保留无法解析的条目用于阻止清理。"""
        folder = real_directory(self.manager.manifests_dir)
        reference = ManifestReference(self.manager)
        rows, invalid = [], 0
        for path in folder.glob("*.json"):
            if path.name == "default.json":
                continue
            try:
                info = _file_stat(path)
                data = reference.read(path.stem)
                date = (_datetime(data["published_at"]) if "published_at" in data
                        else datetime.fromtimestamp(info.st_mtime, UTC))
                members = tuple((name, entry["component_id"]) for section in SECTIONS
                                for name, entry in data[section].items())
            except DATA_ERRORS:
                invalid += 1
                continue
            rows.append(dict(key=path.stem, date=date, file_date="published_at" not in data,
                             notes=data.get("AdditionalMessage", ""), members=members, rules=tuple(entry["component_id"] for entry in data["recovery_rules"].values())))
        default = self.manager.default_manifest_id()
        pointer = folder / "default.json"
        if pointer.exists() or pointer.is_symlink():
            try:
                _file_stat(pointer)
                if default is None:
                    raise ValueError("Invalid Default Manifest.")
            except DATA_ERRORS:
                invalid += 1
        rows.sort(key=lambda entry: (entry["date"], entry["key"]), reverse=True)
        for index, row in enumerate(rows):
            row.update(default=row["key"] == default, latest=index == 0)
        return rows, invalid

    def _usage(self):
        """版本与组件页共享内存摘要，按 Trace 状态重新计算变化的 Run。"""
        with self._usage_lock:
            traces = real_directory(self.root / "traces")
            directory = real_directory(self.root / "run-usage")
            runs = set(retained_runs(self.root))
            saved = {int(path.stem) for path in directory.glob("*.json")
                     if re.fullmatch(r"[1-9][0-9]*", path.stem)}
            usage, invalid = ({}, {}), 0
            cache = {}
            for identity in runs | saved:
                try:
                    if identity in runs:
                        try:
                            info = (traces / f"{identity}.jsonl").lstat()
                            if not stat.S_ISREG(info.st_mode) or _junction(info):
                                raise ValueError("Invalid Trace file.")
                            key = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
                            cached = self._trace_usage.get(identity)
                            value = cached[1] if cached is not None and cached[0] == key else _summary(self.root, identity)
                            _add_summary(usage, value, identity)
                            cache[identity] = (key, value)
                            continue
                        except DATA_ERRORS:
                            # 清理可能在枚举后提交，优先尝试刚落盘的摘要。
                            pass
                    path = directory / f"{identity}.json"
                    _file_stat(path)
                    _add_summary(usage, json.loads(path.read_text(encoding="utf-8")), identity)
                except DATA_ERRORS:
                    invalid += 1
            self._trace_usage = cache
            return usage, invalid

    def _log_targets(self, entry):
        if entry["imported"]:
            return (entry["root"],)
        identity = entry["run_id"]
        trace = self.root / "traces" / f"{identity}.jsonl"
        _file_stat(trace)
        paths = [trace]
        for folder, name, directory in (("runs", f"{identity}.json", False),
                                        ("evidence", str(identity), True)):
            path = real_directory(self.root / folder) / name
            if path.exists() or path.is_symlink() or path.is_junction():
                real_directory(path) if directory else _file_stat(path)
                paths.append(path)
        return tuple(paths)

    def _logs(self, keys=None):
        """仅用日志首尾填表，截图目录的占用另行扫描。"""
        real_directory(self.root / "traces")
        rows, invalid = [], 0
        for entry in list_logs(self.root, keys=keys, read_start=False):
            try:
                info = run_summary(entry["root"], entry["run_id"])
                date = _datetime(info["started_at"]) if info["started_at"] else None
            except DATA_ERRORS:
                invalid += 1
                continue
            cancelled = (info["result"] or {}).get("failure_code") == "user_cancelled"
            status = info["status"] if isinstance(info["status"], str) else "unknown"
            rows.append({**entry, "started_at": info["started_at"], "date": date,
                         "status": "cancelled" if cancelled else status, "size": None})
        rows.sort(key=lambda row: (row["date"] or datetime.min.replace(tzinfo=UTC), str(row["key"])), reverse=True)
        return rows, invalid

    def log_sizes(self, rows, *, cancelled=None):
        """后台补齐日志占用，无法安全遍历的条目仍可查看日志。"""
        sizes = {}
        for row in rows:
            if cancelled is not None and cancelled.is_set():
                break
            try:
                sizes[row["key"]] = sum(item[-1] for path in self._log_targets(row)
                                        for item in _tree(path, fingerprint=False))
            except DATA_ERRORS:
                continue
        return sizes

    def _assets(self):
        folder = real_directory(self.root / "assets")
        usage = self.root / "asset-usage.json"
        invalid, index = 0, {}
        if usage.exists() or usage.is_symlink():
            try:
                _file_stat(usage)
                index = json.loads(usage.read_text(encoding="utf-8"))
                if not isinstance(index, dict):
                    raise ValueError("Invalid Asset usage index.")
            except DATA_ERRORS:
                invalid, index = 1, {}
        rows = []
        for name, children, files in os.walk(folder):
            current = Path(name)
            children[:] = [child for child in children
                           if not (current / child).is_symlink() and not (current / child).is_junction()]
            images = [current / file for file in files if re.fullmatch(r"[0-9a-f]{64}\.png", file)]
            if not images:
                continue
            try:
                logical_name = asset_name(current.relative_to(folder).as_posix())
                size = sum(_file_stat(path).st_size for path in images)
            except DATA_ERRORS:
                invalid += 1
                continue
            hit = index.get(logical_name)
            try:
                last = _datetime(hit["last_used_at"]) if hit is not None else None
            except DATA_ERRORS:
                last = None
                invalid += 1
            rows.append(dict(key=logical_name, count=len(images), size=size, last=last))
        rows.sort(key=lambda row: (row["last"] or datetime.min.replace(tzinfo=UTC), row["key"]), reverse=True)
        return rows, invalid

    def inventory(self, category, *, with_usage=True):
        """读取一类盘点。跨 Run 使用统计仅在查看相关页时计算。"""
        if category == "logs":
            return self._logs()
        if category == "assets":
            return self._assets()
        versions, invalid = self._versions()
        (version_usage, component_usage), gaps = self._usage() if with_usage else (({}, {}), 0)
        if category == "manifests":
            for row in versions:
                row["count"], row["last"] = version_usage.get(row["key"], (None, None))
            return versions, invalid + gaps
        if category != "components":
            raise ValueError("Unknown inventory category.")
        references_unknown = bool(invalid)
        references = defaultdict(set)
        names = set()
        for row in versions:
            for name, digest in row["members"]:
                names.add((name, digest))
                references[digest].add(row["key"])
        folder = real_directory(self.manager.components_dir)
        rows, roles = [], {}
        rules = {digest for row in versions for digest in row["rules"]}
        for name, digest in names | component_usage.keys():
            path = folder / f"{digest.removeprefix('sha256:')}.py"
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest) or not path.is_file():
                continue
            if digest not in roles:
                try:
                    _file_stat(path)
                    tree = ast.parse(path.read_bytes())
                    functions = self.manager._top_functions(tree)
                    roles[digest] = next((role for fn in functions.get("execute", ())
                                          for decorator in fn.decorator_list
                                          if (role := self.manager._decorator_name(decorator)) in ROLES),
                                         "recovery_rule" if digest in rules else "")
                except DATA_ERRORS + (SyntaxError,):
                    roles[digest] = ""
                    invalid += 1
            count, last = component_usage.get((name, digest), (None, None))
            rows.append(dict(key=digest, name=name, references=None if references_unknown else len(references[digest]),
                             count=count, last=last, role=roles[digest]))
        for path in folder.glob("*.py"):
            if re.fullmatch(r"[0-9a-f]{64}", path.stem) and f"sha256:{path.stem}" not in roles:
                try:
                    _file_stat(path)
                except DATA_ERRORS:
                    invalid += 1
                    continue
                rows.append(dict(key=f"sha256:{path.stem}", name=None,
                                 references=None if references_unknown else 0, count=None, last=None, role=""))
        rows.sort(key=lambda row: (-(row["count"] or 0), row["name"] or "", row["key"]))
        return rows, invalid + gaps

    def preview(self, category, keys):
        """根据当前存储生成可确认的删除计划，预览本身不写数据。"""
        pending = next(real_directory(self.root).glob(".data-cleanup-pending-*"), None)
        if pending is not None:
            # 暂存的 Manifest 仍可能需要恢复，不能按活跃目录计算下一次引用差集。
            raise OSError(f"An interrupted cleanup retained data at {pending}")
        keys = tuple(keys)
        if not keys or len(set(keys)) != len(keys):
            raise ValueError("Select at least one item.")
        selected, sources, fingerprints = [], [], []
        if category == "logs":
            rows, _ = self._logs(set(keys))
            by_key = {row["key"]: row for row in rows}
            targets = []
            for key in keys:
                row = by_key.get(key)
                if row is None or row["date"] is None:
                    raise ValueError("A selected run log is unavailable or has no start date.")
                paths = self._log_targets(row)
                files = [item for path in paths for item in _tree(path)]
                targets.extend(paths)
                fingerprints.extend(files)
                selected.append({**row, "size": sum(item[-1] for item in files)})
        elif category in {"manifests", "components"}:
            versions, invalid = self._versions()
            if invalid:
                raise ValueError("An unreadable Manifest or Default pointer prevents safe cleanup.")
            selected_keys = set(keys)
            retained = {digest for row in versions if category == "components" or row["key"] not in selected_keys
                        for _, digest in row["members"]}
            if category == "components":
                targets = []
                for digest in keys:
                    if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest) or digest in retained:
                        raise ValueError("A selected Component source is invalid or still referenced.")
                    path = self.manager.components_dir / f"{digest[7:]}.py"
                    info = _file_stat(path)
                    targets.append(path)
                    selected.append(dict(key=digest, size=info.st_size))
            else:
                by_key = {row["key"]: row for row in versions}
                for key in keys:
                    row = by_key.get(key)
                    if row is None or row["default"] or row["latest"]:
                        raise ValueError("A selected Manifest is unavailable or protected.")
                    selected.append(row)
                removed = {digest for row in selected for _, digest in row["members"]}
                for digest in sorted(removed - retained):
                    path = self.manager.components_dir / f"{digest.removeprefix('sha256:')}.py"
                    if path.exists() or path.is_symlink() or path.is_junction():
                        _file_stat(path)
                        names = sorted({name for row in selected for name, member in row["members"] if member == digest})
                        sources.append((path, tuple(names)))
                targets = [self.manager.manifests_dir / f"{row['key']}.json" for row in selected]
                targets.extend(path for path, _ in sources)
            fingerprints = [item for path in targets for item in _tree(path.absolute())]
        else:
            raise ValueError("This data category cannot be cleaned.")
        targets = tuple(path.absolute() for path in targets)
        return CleanupPlan(category, keys, tuple(selected), tuple(sources), targets, tuple(fingerprints))

    def execute(self, plan):
        """排他复核、保留统计并提交永久清理。后续残留路径交给界面报告。"""
        with self.service.activity(CLEANUP_ACTIVITY), self.manager.store_lock():
            current = self.preview(plan.category, plan.keys)
            if current != plan:
                raise ValueError("Selected data changed. Preview cleanup again.")
            if plan.category == "logs":
                summaries = [(row["run_id"], _summary(self.root, row["run_id"]))
                             for row in plan.rows if not row["imported"]]
                directory = real_directory(self.root / "run-usage")
                for identity, value in summaries:
                    path = directory / f"{identity}.json"
                    if path.exists() or path.is_symlink() or path.is_junction():
                        _file_stat(path)
                    directory.mkdir(exist_ok=True)
                    with work_file(dir=directory, prefix=".summary-") as stream:
                        stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8"))
                        stream.flush()
                        os.fsync(stream.fileno())
                        staged = Path(stream.name)
                        stream.close()
                        staged.replace(path)
            return self._commit(plan.targets)

    def _commit(self, targets):
        """同盘隔离整批目标，移动失败按相反顺序恢复。"""
        stage = Path(create_work_directory(dir=real_directory(self.root), prefix=".data-cleanup-pending-"))
        committed = stage.with_name(stage.name.replace("pending", "committed", 1))
        moved = []
        try:
            atomic_write_json(stage / "targets.json", {"paths": [str(path.relative_to(self.root)) for path in targets]})
            for index, path in enumerate(targets):
                isolated = stage / str(index)
                path.rename(isolated)
                moved.append((path, isolated))
            stage.rename(committed)
        except BaseException:
            try:
                for path, isolated in reversed(moved):
                    if path.exists() or path.is_symlink() or path.is_junction():
                        raise FileExistsError(path)
                    isolated.rename(path)
            except OSError as error:
                raise OSError(f"Cleanup rollback failed. Retained data: {stage}") from error
            shutil.rmtree(stage)
            raise
        try:
            shutil.rmtree(committed)
        except OSError:
            return committed
        return None
