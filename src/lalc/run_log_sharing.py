"""单次运行日志的只读快照、ZIP 传输及隔离导入，不修改本机运行编号。"""

from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import stat
import uuid
import zipfile

from .work_files import WorkDirectory
from .file_content import (FileContent, checkpoint, copy_content, require_disk, require_memory,
                           content_hash, file_transfers, transfer_file)
from .page_packages import real_directory
from .run_logs import image_path, lines, snapshot, trace_path
from .sharing import strict_json, json_bytes
from threading import Event


AI_REPAIR_SUMMARY = 'ai-repair-summary.json'


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


def list_logs(root):
    """枚举本机与隔离导入日志，按原始开始时间排序。"""
    result = []
    for path in (root / 'traces').glob('*.jsonl'):
        if path.stem.isdecimal() and int(path.stem) > 0 and not path.is_symlink():
            identity = int(path.stem)
            result.append(dict(key=identity, root=root, run_id=identity, imported=False,
                               started_at=start_time(root, identity)))
    imported = root / 'imported-run-logs'
    real_directory(imported)
    for folder in imported.glob('*'):
        if not folder.is_dir() or folder.name.startswith('.'):
            continue
        try:
            real_directory(folder)
            metadata = strict_json(FileContent.from_path(folder / 'run.json'))
            identity = metadata['run_id']
            if type(identity) is not int or identity < 1:
                continue
            trace_path(folder, identity)
            result.append(dict(key=folder.name, root=folder, run_id=identity, imported=True,
                               started_at=start_time(folder, identity)))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    def order(item):
        value = item['started_at']
        return (datetime.fromisoformat(value).timestamp() if value else float('-inf'), str(item['key']))
    return sorted(result, key=order, reverse=True)


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
                (stage / 'run.json').write_bytes(json_bytes(metadata))
                if snapshot(stage, identity)[2] != (stage / trace_name).stat().st_size:
                    raise ValueError('Incomplete log record.')
                checkpoint(len(files), len(files), 'Import')
                key = str(uuid.uuid4())
                progress.update(phase="Finishing…")
                stage.rename(folder / key)
    progress.update(finished=True)
    return key
