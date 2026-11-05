"""覆盖 codesearch 模型路径发现、缺失资源不下载及进程清理，使用进程替身。

项目根目录运行：.venv/bin/python -m pytest -q tests/test_codesearch.py
"""

from contextlib import contextmanager
import hashlib
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from lalc import codesearch


@pytest.mark.parametrize('location', ['adjacent', 'override', 'bundled', 'cache', 'invalid-adjacent'])
def test_model_discovery_for_path_executable(tmp_path, monkeypatch, location):
    binary = tmp_path / 'tools' / ('codesearch.exe' if codesearch.os.name == 'nt' else 'codesearch')
    binary.parent.mkdir()
    binary.write_bytes(b'fake')
    bundled = tmp_path / 'repo' / 'codesearch_resources' / 'models'
    search = codesearch.CodeSearch(tmp_path / 'data')
    sources = {'adjacent': binary.parent / 'models', 'override': tmp_path / 'custom-models',
               'bundled': bundled, 'cache': search.root / 'models'}
    content = b'model'
    monkeypatch.delenv('LALC_CODESEARCH', raising=False)
    monkeypatch.delenv('LALC_CODESEARCH_MODELS', raising=False)
    monkeypatch.setattr(codesearch.sys, 'frozen', False, raising=False)
    monkeypatch.setattr(codesearch, '__file__', str(tmp_path / 'repo' / 'src' / 'lalc' / 'codesearch.py'))
    monkeypatch.setattr(codesearch, 'MODEL_FILES', {'config.json': hashlib.sha256(content).hexdigest()})
    monkeypatch.setattr(codesearch.shutil, 'which', lambda name, **kw: str(binary) if name == 'codesearch' else
                        (str(Path(codesearch.sys.executable)) if name == 'git' else None))
    monkeypatch.setattr(codesearch.subprocess, 'run', lambda *a, **k: SimpleNamespace(returncode=0, stdout='codesearch 1.7.9'))
    monkeypatch.setattr(codesearch.subprocess, 'Popen', lambda *a, **k: pytest.fail('prepare 不应启动服务'))
    for name, root in sources.items():
        snapshot = root / codesearch.MODEL_REPO / 'snapshots' / codesearch.MODEL_REVISION
        snapshot.mkdir(parents=True)
        valid = name == location or (location == 'invalid-adjacent' and name == 'bundled')
        (snapshot / 'config.json').write_bytes(content if valid else b'invalid')
    if location == 'override':
        monkeypatch.setenv('LALC_CODESEARCH_MODELS', str(sources['override']))
    elif location in {'bundled', 'cache'}:
        # 默认搜索只跳过不存在的目录，不能用其他模型掩盖损坏资源。
        shutil.rmtree(sources['adjacent'])
        if location == 'cache':
            shutil.rmtree(bundled)
    if location == 'invalid-adjacent':
        with pytest.raises(FileNotFoundError, match='哈希不符'):
            search.prepare()
        return
    search.prepare()
    cached = search.root / 'models' / codesearch.MODEL_REPO / 'snapshots' / codesearch.MODEL_REVISION / 'config.json'
    assert cached.read_bytes() == content
    assert Path(search.binary).read_bytes() == binary.read_bytes()


def test_missing_model_fails_before_index_or_service_spawn(tmp_path, monkeypatch):
    binary = tmp_path / 'codesearch'
    binary.write_bytes(b'fake')
    monkeypatch.setenv('LALC_CODESEARCH', str(binary))
    monkeypatch.setenv('LALC_CODESEARCH_MODELS', str(tmp_path / 'absent-models'))
    monkeypatch.setattr(codesearch.subprocess, 'run', lambda *a, **k: SimpleNamespace(returncode=0, stdout='codesearch 1.7.9'))
    monkeypatch.setattr(codesearch.subprocess, 'Popen', lambda *a, **k: pytest.fail('资源缺失不能启动下载或查询'))
    with pytest.raises(FileNotFoundError, match='不会自动下载'):
        codesearch.CodeSearch(tmp_path / 'data').prepare()


def test_environment_restore_error_reaps_spawned_child(monkeypatch):
    process = object()
    stopped = []
    @contextmanager
    def environment(env):
        yield env
        raise RuntimeError('restore failed')
    monkeypatch.setattr(codesearch, 'pi_process_environment', environment)
    monkeypatch.setattr(codesearch.subprocess, 'Popen', lambda *a, **k: process)
    monkeypatch.setattr(codesearch, 'stop', stopped.append)
    with pytest.raises(RuntimeError, match='restore failed'):
        codesearch.spawn(['fake'], {})
    assert stopped == [process]


def test_host_attempts_both_process_cleanups_even_if_pi_cleanup_fails(tmp_path):
    from lalc.application import ApplicationService
    service = ApplicationService(tmp_path)
    closed = []
    def fail():
        closed.append('pi')
        raise OSError('cleanup failed')
    service._pi_process = SimpleNamespace(close=fail)
    service._codesearch = SimpleNamespace(close=lambda: closed.append('codesearch'))
    with pytest.raises(OSError, match='cleanup failed'):
        service.shutdown()
    assert closed == ['pi', 'codesearch']


def test_index_refuses_parent_git_root_before_spawning_indexer(tmp_path, monkeypatch):
    search = codesearch.CodeSearch(tmp_path)
    search.binary, search.env = 'fake-codesearch', {}
    monkeypatch.setattr(search, 'prepare', lambda: None)
    monkeypatch.setattr(codesearch.subprocess, 'run', lambda *a, **k: SimpleNamespace(returncode=0, stdout=str(tmp_path)))
    monkeypatch.setattr(codesearch, 'spawn', lambda *a, **k: pytest.fail('不能索引父目录'))
    child = tmp_path / 'child'
    child.mkdir()
    with pytest.raises(ValueError, match='独立 Git 根'):
        search.build(child, lambda: None)
