"""覆盖普通创建权限、快照生命周期、提交后清理与禁止临时目录的边界。

项目根目录运行：.venv/bin/python -m pytest -q tests/test_work_files.py
"""

import ast
import gc
import os
from pathlib import Path
import stat

import pytest

from lalc.work_files import WorkDirectory, create_work_file, work_file


def test_directory_cleanup_and_committed_directory_survives(tmp_path):
    with WorkDirectory(dir=tmp_path) as name:
        path = Path(name)
        (path / 'data').write_text('complete')
        path.rename(tmp_path / 'committed')
    assert (tmp_path / 'committed/data').read_text() == 'complete'
    with pytest.raises(RuntimeError), WorkDirectory(dir=tmp_path) as name:
        raise RuntimeError('cancelled')
    assert not Path(name).exists()
    owner = WorkDirectory(dir=tmp_path)
    path = Path(owner.name)
    del owner
    gc.collect()
    assert not path.exists()


def test_files_cleanup_and_exclusive_creation(tmp_path):
    with work_file(dir=tmp_path) as stream:
        path = Path(stream.name)
        stream.write(b'content')
        stream.seek(0)
        assert stream.read() == b'content'
    assert not path.exists()
    descriptor, name = create_work_file(dir=tmp_path)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(b'published')
    Path(name).replace(tmp_path / 'saved')
    assert (tmp_path / 'saved').read_bytes() == b'published'


@pytest.mark.skipif(os.name == 'nt', reason='POSIX mode check; Windows inherited ACL requires native acceptance')
def test_permissions_match_ordinary_siblings(tmp_path):
    sibling = tmp_path / 'ordinary'
    sibling.mkdir()
    (sibling / 'file').write_bytes(b'normal')
    with WorkDirectory(dir=tmp_path) as name, work_file(dir=tmp_path) as stream:
        assert stat.S_IMODE(Path(name).stat().st_mode) == stat.S_IMODE(sibling.stat().st_mode)
        assert stat.S_IMODE(Path(stream.name).stat().st_mode) == stat.S_IMODE((sibling / 'file').stat().st_mode)
    descriptor, name = create_work_file(dir=tmp_path)
    os.close(descriptor)
    assert stat.S_IMODE(Path(name).stat().st_mode) == stat.S_IMODE((sibling / 'file').stat().st_mode)


def test_products_and_scripts_do_not_create_tempfile_directories():
    root = Path(__file__).resolve().parents[1]
    forbidden = {'TemporaryDirectory', 'mkdtemp', 'NamedTemporaryFile', 'mkstemp', 'TemporaryFile'}
    for path in [*root.joinpath('src').rglob('*.py'), *root.joinpath('scripts').rglob('*.py')]:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == 'tempfile':
                assert not forbidden.intersection(alias.name for alias in node.names), path
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert not (isinstance(node.func.value, ast.Name) and node.func.value.id == 'tempfile'
                            and node.func.attr in forbidden), (path, node.lineno)
