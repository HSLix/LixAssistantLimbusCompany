"""单次运行日志的只读快照、ZIP 传输及隔离导入，不修改本机运行编号。"""

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import stat
import uuid
import zipfile

from .work_files import WorkDirectory
from .file_content import (FileContent, checkpoint, copy_content, require_disk, require_memory)
from .page_packages import real_directory
from .run_logs import lines, snapshot, trace_path
from .sharing import strict_json, json_bytes
from threading import Event


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


def export_log(root, run_id, destination, boundary=None):
    """先固定完整记录边界，再流式压缩正文和本次运行引用的原图。"""
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
        for _, _, raw in lines(trace, 0, boundary[2], False, Event()):
            checkpoint()
            try:
                record = json.loads(raw)
            except (ValueError, UnicodeError):
                continue
            for identity in _evidence(record):
                if re.fullmatch(fr'{run_id}/[0-9]+', identity):
                    image = root / 'evidence' / (identity + '.png')
                    real_directory(image.parent)
                    if image.is_file():
                        files['evidence/' + identity + '.png'] = FileContent.from_path(image)
        metadata = dict(format='lalc-run-log', version=1, run_id=run_id,
                        files={name: dict(size=len(content), sha256=content.sha256) for name, content in files.items()})
        require_disk([(destination.parent, sum(len(content) + 1024 for content in files.values()))])
        pending = stage / 'log.zip'
        with zipfile.ZipFile(pending, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('run.json', json_bytes(metadata))
            for number, (name, content) in enumerate(files.items()):
                checkpoint(number, len(files), name)
                with archive.open(name, 'w', force_zip64=True) as stream:
                    copy_content(content, stream)
        checkpoint(len(files), len(files), 'ZIP')
        if destination.is_symlink():
            raise ValueError('ZIP destination must not be a link.')
        pending.replace(destination)


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
                    or metadata['format'] != 'lalc-run-log' or type(metadata['version']) is not int or metadata['version'] != 1
                    or type(metadata['run_id']) is not int or metadata['run_id'] < 1 or type(metadata['files']) is not dict):
                raise ValueError('Invalid run log package.')
            identity, files = metadata['run_id'], metadata['files']
            trace_name = f'traces/{identity}.jsonl'
            if trace_name not in files or set(names) != {'run.json', *files}:
                raise ValueError('ZIP contents do not match index.')
            for name, record in files.items():
                if (name != trace_name and not re.fullmatch(fr'evidence/{identity}/[0-9]+\.png', name)):
                    raise ValueError('Unexpected ZIP path.')
                if (type(record) is not dict or set(record) != {'size', 'sha256'}
                        or type(record['size']) is not int or record['size'] < 0
                        or record['size'] != archive.getinfo(name).file_size
                        or not isinstance(record['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', record['sha256'])):
                    raise ValueError('Invalid ZIP size or hash.')
            require_disk([(folder, sum(info.file_size + 4096 for info in members))])
            for number, (name, record) in enumerate(files.items()):
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
                if size != record['size'] or digest.hexdigest() != record['sha256']:
                    raise ValueError('ZIP hash mismatch.')
            (stage / 'run.json').write_bytes(json_bytes(metadata))
            if snapshot(stage, identity)[2] != (stage / trace_name).stat().st_size:
                raise ValueError('Incomplete log record.')
            checkpoint(len(files), len(files), 'Import')
            key = str(uuid.uuid4())
            stage.rename(folder / key)
    return key
