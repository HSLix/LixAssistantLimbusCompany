"""单次运行日志的只读快照、ZIP 传输及隔离导入。"""

from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import uuid
import zipfile

from .work_files import WorkDirectory, work_file
from .file_content import (FileContent, checkpoint, copy_content, require_disk, require_memory,
                           content_hash, file_transfers, transfer_file)
from .page_packages import real_directory
from .process_lock import ProcessLock
from .run_logs import image_path, lines, snapshot, trace_path
from .runtime import atomic_write_json
from .sharing import strict_json, json_bytes
from threading import Event


AI_REPAIR_SUMMARY = 'ai-repair-summary.json'


def run_id_lock(root):
    """本机执行、导入提交及旧副本补号共用短时编号锁。"""
    return ProcessLock('run-id:' + os.path.normcase(str(root.resolve())), blocking=True)


def reserve_run_ids(root, count=1):
    """持有编号锁时持久预留一段编号；写入失败后的空号允许保留。"""
    path = root / 'run-sequence.json'
    if path.exists():
        value = json.loads(path.read_text(encoding='utf-8'))
        if (type(value) is not dict or set(value) != {'last_run_id'}
                or type(value['last_run_id']) is not int or value['last_run_id'] < 0):
            raise ValueError('run-sequence.json is invalid')
        last = value['last_run_id']
    else:
        last = max((data.get('local_run_id', 0) for _, data in _import_metadata(root)), default=0)
    existing = (int(item.stem) for folder, pattern in (('traces', '*.jsonl'), ('run-usage', '*.json'))
                for item in (root / folder).glob(pattern) if item.stem.isdecimal())
    last = max(last, max(existing, default=0))
    atomic_write_json(path, {'last_run_id': last + count})
    return range(last + 1, last + count + 1)


def _import_metadata(root, *, keys=None, check=lambda: None):
    """只枚举可定位到真实 Trace 的已提交副本。"""
    imported = real_directory(root / 'imported-run-logs')
    for folder in imported.iterdir() if imported.is_dir() else ():
        if folder.name.startswith('.') or (keys is not None and folder.name not in keys):
            continue
        check()
        try:
            real_directory(folder)
            data = strict_json(FileContent.from_path(folder / 'run.json'))
            original, local = data['run_id'], data.get('local_run_id', 0)
            if type(original) is not int or original < 1:
                continue
            if 'local_run_id' in data and (type(local) is not int or local < 1):
                continue
            trace_path(folder, original)
        except (OSError, ValueError, KeyError, TypeError):
            continue
        yield folder, data


def imported_logs(root, *, keys=None, assign_missing=True, check=lambda: None):
    """为旧导入副本补号，原始 Trace、截图和副本路径保留。"""
    entries = dict(_import_metadata(root, keys=keys, check=check))
    missing = {folder for folder, data in entries.items() if 'local_run_id' not in data}
    if assign_missing and missing:
        with run_id_lock(root):
            current = dict(_import_metadata(root, keys={folder.name for folder in missing}, check=check))
            pending = sorted(folder for folder, data in current.items() if 'local_run_id' not in data)
            if pending:
                for folder, identity in zip(pending, reserve_run_ids(root, len(pending))):
                    check()
                    data = {**current[folder], 'local_run_id': identity}
                    try:
                        with work_file(dir=folder, prefix='.run-id-') as stream:
                            stream.write(json_bytes(data))
                            stream.close()
                            Path(stream.name).replace(folder / 'run.json')
                    except FileNotFoundError:
                        # 数据清理可能已移走副本，不能重新创建目录。
                        current.pop(folder)
                    else:
                        current[folder] = data
            for folder in missing:
                entries.pop(folder)
            entries.update(current)
    return [dict(key=folder.name, root=folder, run_id=data.get('local_run_id'),
                 original_run_id=data['run_id'], imported=True) for folder, data in entries.items()]


def start_time(root, run_id):
    """使用首条有效事件时间；缺失时不伪造运行时间。"""
    with trace_path(root, run_id).open('rb') as stream:
        for raw in stream:
            checkpoint()
            require_memory(len(raw) * 12)
            try:
                value = json.loads(raw).get('recorded_at')
                stamp = datetime.fromisoformat(value)
                if stamp.tzinfo is not None:
                    return value
            except (ValueError, TypeError, AttributeError):
                continue
    return None


def list_logs(root, *, keys=None, read_start=True, assign_missing=True):
    """枚举本机与隔离导入日志，按原始开始时间排序。"""
    result = []
    for path in (root / 'traces').glob('*.jsonl'):
        if re.fullmatch(r'[1-9][0-9]*', path.stem) and not path.is_symlink():
            identity = int(path.stem)
            if keys is not None and identity not in keys:
                continue
            try:
                started_at = start_time(root, identity) if read_start else None
            except (FileNotFoundError, ValueError):
                # 另一窗口可能刚提交清理，重新枚举时不保留已消失的行。
                continue
            result.append(dict(key=identity, root=root, run_id=identity, imported=False,
                               started_at=started_at))
    for entry in imported_logs(root, keys=keys, assign_missing=assign_missing):
        try:
            started_at = start_time(entry['root'], entry['original_run_id']) if read_start else None
            result.append({**entry, 'started_at': started_at})
        except (OSError, ValueError):
            continue
    def order(item):
        value = item['started_at']
        return (datetime.fromisoformat(value).timestamp() if value else float('-inf'), str(item['key']))
    return sorted(result, key=order, reverse=True) if read_start else result


def _evidence(value):
    if isinstance(value, dict):
        if isinstance(value.get('evidence_id'), str):
            yield value['evidence_id']
        for item in value.values():
            yield from _evidence(item)
    elif isinstance(value, list):
        for item in value:
            yield from _evidence(item)


def _repair_round(record):
    """提取可分享的统计字段，旧日志缺失值保留为 null。"""
    result = record.get('result')
    if not isinstance(result, dict):
        result = {}
    row = {}
    for field in ('requests', 'compaction_requests', 'reported_tokens', 'requests_with_token_usage'):
        value = result.get(field)
        row[field] = value if type(value) is int and value >= 0 else None
    if row['requests'] is None or row['compaction_requests'] is None:
        row['total_requests'] = None
    else:
        row['total_requests'] = row['requests'] + row['compaction_requests']
    for field in ('provider', 'model', 'status'):
        value = result.get(field)
        row[field] = value if isinstance(value, str) and value else None
    duration = result.get('duration_seconds')
    try:
        duration = float(duration) if type(duration) in (int, float) else None
    except OverflowError:
        duration = None
    row['duration_seconds'] = duration if duration is not None and 0 <= duration < math.inf else None
    return {**row, 'session_id': record.get('session_id') if isinstance(record.get('session_id'), str) else None,
            'round': record.get('round') if type(record.get('round')) is int else None}


def _repair_summary(run_id, rounds, invoked, run_finished):
    """按同一 Trace 快照汇总已返回的轮次，明确缺失的用量和结果。"""
    unreported = max(0, invoked - len(rounds))
    totals = {}
    for field in ('duration_seconds', 'total_requests', 'requests', 'compaction_requests',
                  'reported_tokens', 'requests_with_token_usage'):
        values = [row[field] for row in rounds if row[field] is not None]
        totals[field] = sum(values) if values else None
    if totals['duration_seconds'] is not None and not math.isfinite(totals['duration_seconds']):
        totals['duration_seconds'] = None
    usage_complete = not unreported and all(
        row['total_requests'] is not None
        and row['reported_tokens'] is not None
        and row['requests_with_token_usage'] == row['total_requests']
        for row in rounds
    )
    return dict(run_id=run_id, run_finished=run_finished, unreported_rounds=unreported,
                totals=totals, token_usage_complete=usage_complete, rounds=rounds)


def export_log(root, run_id, destination, boundary=None):
    """在同一完整记录边界内压缩正文、原图和 AI 修复汇总。"""
    root, destination = Path(root), Path(destination)
    boundary = boundary or snapshot(root, run_id)
    require_disk([(destination.parent, boundary[2])])
    with WorkDirectory(dir=destination.parent) as directory:
        stage = Path(directory)
        trace = stage / 'trace.jsonl'
        with trace_path(root, run_id).open('rb') as source, trace.open('wb') as target:
            remaining = boundary[2]
            while remaining:
                checkpoint(boundary[2] - remaining, boundary[2], 'Trace')
                chunk = source.read(min(65536, remaining))
                if not chunk:
                    raise ValueError('Run log was truncated during export.')
                target.write(chunk)
                remaining -= len(chunk)
        current = snapshot(root, run_id)
        if current[:2] != boundary[:2] or current[2] < boundary[2]:
            raise ValueError('Run log was replaced during export.')
        files = {f'traces/{run_id}.jsonl': FileContent.from_path(trace)}
        rounds, invoked, run_finished = [], 0, False
        for _, _, raw in lines(trace, 0, boundary[2], False, Event()):
            checkpoint()
            try:
                record = json.loads(raw)
            except (ValueError, UnicodeError):
                continue
            if isinstance(record, dict):
                event = record.get('event')
                if event == 'agent_invoked':
                    invoked += 1
                elif event == 'runtime_agent_result':
                    rounds.append(_repair_round(record))
                elif event == 'run_finished':
                    run_finished = True
            for identity in _evidence(record):
                if re.fullmatch(fr'{run_id}/[0-9]+', identity):
                    image = image_path(root, run_id, {"evidence_id": identity})
                    if image is None:
                        raise ValueError('Invalid evidence path.')
                    real_directory(image.parent)
                    if image.is_file():
                        files['evidence/' + identity + image.suffix] = FileContent.from_path(image)
        if invoked or rounds:
            summary = _repair_summary(run_id, rounds, invoked, run_finished)
            files[AI_REPAIR_SUMMARY] = json.dumps(summary, indent=2, allow_nan=False).encode('ascii') + b'\n'
        metadata = dict(format='lalc-run-log', version=2 if AI_REPAIR_SUMMARY in files else 1, run_id=run_id,
                        files={name: dict(size=len(content), sha256=content_hash(content))
                               for name, content in files.items()})
        require_disk([(destination.parent, sum(len(content) + 1024 for content in files.values()))])
        pending = stage / 'log.zip'
        with file_transfers("Writing ZIP", len(files)) as progress:
            with zipfile.ZipFile(pending, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('run.json', json_bytes(metadata))
                for number, (name, content) in enumerate(files.items()):
                    checkpoint(number, len(files), name)
                    with archive.open(name, 'w', force_zip64=True) as stream:
                        copy_content(content, stream, name=name)
                    progress.complete()
            checkpoint(len(files), len(files), 'ZIP')
            if destination.is_symlink():
                raise ValueError('ZIP destination must not be a link.')
            progress.update(phase="Finishing…")
            pending.replace(destination)
    progress.update(finished=True)


def import_log(root, archive_path):
    """自动检查 ZIP 索引、路径和哈希，全部成功后一次提交隔离副本。"""
    root = real_directory(Path(root))
    folder = real_directory(root / 'imported-run-logs')
    folder.mkdir(parents=True, exist_ok=True)
    archive_path = Path(archive_path)
    if archive_path.is_symlink() or not archive_path.is_file():
        raise ValueError('ZIP must be a regular file.')
    with archive_path.open('rb') as stream:
        ending = zipfile._EndRecData(stream)
        if ending is None:
            raise ValueError('Invalid ZIP index.')
        require_memory(ending[zipfile._ECD_SIZE] * 12)
    with WorkDirectory(prefix='.pending-', dir=folder) as directory:
        stage = Path(directory)
        with zipfile.ZipFile(archive_path) as archive:
            members = archive.infolist()
            names = [info.filename for info in members]
            if len(set(names)) != len(names) or 'run.json' not in names:
                raise ValueError('Missing or duplicate ZIP members.')
            for info in members:
                checkpoint()
                if (info.flag_bits & 1 or info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
                        or stat.S_IFMT(info.external_attr >> 16) not in {0, stat.S_IFREG} or info.is_dir()):
                    raise ValueError('Unsupported ZIP member.')
            require_memory(archive.getinfo('run.json').file_size * 12)
            metadata = strict_json(archive.read('run.json'))
            if (type(metadata) is not dict or set(metadata) != {'format', 'version', 'run_id', 'files'}
                    or metadata['format'] != 'lalc-run-log' or type(metadata['version']) is not int or metadata['version'] not in (1, 2)
                    or type(metadata['run_id']) is not int or metadata['run_id'] < 1 or type(metadata['files']) is not dict):
                raise ValueError('Invalid run log package.')
            identity, files = metadata['run_id'], metadata['files']
            trace_name = f'traces/{identity}.jsonl'
            has_summary = metadata['version'] == 2
            if (trace_name not in files or set(names) != {'run.json', *files}
                    or has_summary != (AI_REPAIR_SUMMARY in files)):
                raise ValueError('ZIP contents do not match index.')
            for name, record in files.items():
                if (name not in {trace_name, AI_REPAIR_SUMMARY}
                        and not re.fullmatch(fr'evidence/{identity}/[0-9]+\.(png|avif)', name)):
                    raise ValueError('Unexpected ZIP path.')
                if (type(record) is not dict or set(record) != {'size', 'sha256'}
                        or type(record['size']) is not int or record['size'] < 0
                        or record['size'] != archive.getinfo(name).file_size
                        or not isinstance(record['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', record['sha256'])):
                    raise ValueError('Invalid ZIP size or hash.')
            require_disk([(folder, sum(info.file_size + 4096 for info in members))])
            with file_transfers("Extracting files", len(files)) as progress:
                for number, (name, record) in enumerate(files.items()):
                    transfer_file(0, record["size"], name)
                    target = stage / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    digest, size = hashlib.sha256(), 0
                    with archive.open(name) as source, target.open('wb') as output:
                        while chunk := source.read(65536):
                            checkpoint(number, len(files), name)
                            digest.update(chunk)
                            size += len(chunk)
                            if size > record['size']:
                                raise ValueError('ZIP size mismatch.')
                            output.write(chunk)
                            transfer_file(size, record["size"], name)
                    if size != record['size'] or digest.hexdigest() != record['sha256']:
                        raise ValueError('ZIP hash mismatch.')
                    transfer_file(size, record["size"], name, finished=True)
                    progress.complete()
                if snapshot(stage, identity)[2] != (stage / trace_name).stat().st_size:
                    raise ValueError('Incomplete log record.')
                checkpoint(len(files), len(files), 'Import')
                key = str(uuid.uuid4())
                progress.update(phase="Finishing…")
                with run_id_lock(root):
                    metadata['local_run_id'] = reserve_run_ids(root).start
                    (stage / 'run.json').write_bytes(json_bytes(metadata))
                    stage.rename(folder / key)
    progress.update(finished=True)
    return key
