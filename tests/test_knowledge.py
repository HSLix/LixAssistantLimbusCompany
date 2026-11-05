"""覆盖知识库只读边界、资料版本、受控 Git 同步与进程取消，不连接远端或模型。

项目根目录运行：.venv/bin/python -m pytest -q tests/test_knowledge.py
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

import pytest

from lalc.knowledge import KnowledgeLibrary, git_diagnostic, knowledge_root
from lalc.agent_policy import KNOWLEDGE_TOOLS, allowed_tools
from lalc.process_lock import ProcessLock


@pytest.fixture
def library(tmp_path):
    root = knowledge_root(tmp_path, create=True)
    (root / "guide.md").write_text("第一行\nneedle is here\n" + "z" * 700 + "needle\n", encoding="utf-8")
    class Search:
        def prepare(self):
            pass
        def build(self, repo, checkpoint):
            (repo / ".codesearch.db").mkdir(exist_ok=True)
        def search(self, repositories, query, limit, checkpoint):
            return {"results": []}
        def close(self):
            pass
    return KnowledgeLibrary(tmp_path, lambda: None, Search())


def git(repo, *args):
    return subprocess.check_output([shutil.which("git"), "-C", str(repo), *args],
                                   stderr=subprocess.PIPE).decode().strip()


@pytest.fixture
def repository(library):
    if not shutil.which("git"):
        pytest.skip("本地 Git 不可用")
    repo = library.root / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "test@example.invalid")
    git(repo, "config", "user.name", "Test")
    ids = []
    for n in range(3):
        (repo / "guide.md").write_text(f"version {n}\nneedle\n")
        git(repo, "add", ".")
        git(repo, "commit", "-m", f"version {n}")
        ids.append(git(repo, "rev-parse", "HEAD"))
    git(repo, "remote", "add", "origin", "https://example.invalid/reference.git")
    git(repo, "update-ref", "refs/remotes/origin/main", ids[0])
    git(repo, "config", "branch.main.remote", "origin")
    git(repo, "config", "branch.main.merge", "refs/heads/main")
    return repo, ids


def test_list_read_search_and_continuation(library):
    (library.root / "manual.pdf").write_bytes(b"%PDF fake")
    page = library.list(limit=1)
    assert page["truncated"] and page["next_offset"] == 1
    assert not library.attempted
    first, image = library.read("guide.md", limit=3)
    assert image is None and first["text"] == "第一行" and first["source"] == "file"
    second, _ = library.read("guide.md", offset=3, limit=3, version=first["version"])
    assert second["text"].startswith("\n")
    found = library.search("needle", limit=1)
    assert found["total"] == 2 and found["items"][0]["line"] == 2
    last = library.search("needle", offset=1, version=found["version"])
    assert "needle" in last["items"][0]["excerpt"]
    assert library.read("manual.pdf")[0]["unsupported"]
    (library.root / "guide.md").write_text("changed")
    with pytest.raises(ValueError, match="变化"):
        library.read("guide.md", offset=3, version=first["version"])
    with pytest.raises(ValueError, match="变化"):
        library.search("needle", offset=1, version=found["version"])


@pytest.mark.parametrize("path", ["../secret", "/etc/passwd", ".git/config", "a/../../secret", "C:/secret", "a\\b"])
def test_rejects_paths(library, path):
    with pytest.raises(ValueError):
        library.path(path)


def test_links_metadata_and_root_are_rejected(library, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (library.root / "link").symlink_to(outside, target_is_directory=True)
    assert library.list()["items"][1]["kind"] == "symlink_unavailable"
    with pytest.raises(ValueError):
        library.read("link/secret.md")
    assert library.search("secret")["total"] == 0
    shutil.rmtree(library.root)
    library.root.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        knowledge_root(tmp_path, create=True)


def test_image_preserves_jpeg_and_no_ocr(library, monkeypatch):
    from PIL import Image
    from lalc.ocr import ocr_service
    monkeypatch.setattr(type(ocr_service), "recognize", lambda *a, **k: pytest.fail("资料图片不得 OCR"))
    image = library.root / "sample.jpg"
    Image.new("RGB", (2, 3), "red").save(image)
    details, content = library.read("sample.jpg")
    assert content == image.read_bytes() and details["mime_type"] == "image/jpeg"


def test_git_full_interval_head_worktree_and_once_per_round(library, repository, monkeypatch):
    repo, ids = repository
    original = library._run
    fetches = []
    def run(repo, args, **kwargs):
        if args[0] == "fetch":
            fetches.append(args)
            git(repo, "update-ref", "refs/remotes/origin/main", ids[2])
            return {"ok": True, "stdout": "", "error": ""}
        return original(repo, args, **kwargs)
    monkeypatch.setattr(library, "_run", run)
    library.list("repo")
    assert not fetches
    (repo / "guide.md").write_text("local uncommitted\n")
    read, _ = library.read("repo/guide.md")
    sync = read["sync"]
    assert sync["before"] == ids[0] and sync["after"] == ids[2] and sync["status"]["ok"]
    assert read["text"] == "version 2\nneedle\n"
    assert sync["update"]["ok"]
    committed = library.git_operation("repo", "show", ref=ids[0], path="guide.md")
    assert "version 0" in committed["text"] and committed["ref_commit"] == ids[0]
    delta = library.git_operation("repo", "diff", before=ids[0], after=ids[2])
    assert "-version 0" in delta["text"] and "+version 2" in delta["text"]
    assert library.git_operation("repo", "diff")["text"] == ""
    library.search("needle")
    assert len(fetches) == 1
    library.git_operation("repo", "fetch")
    assert len(fetches) == 2
    library.begin_round()
    library.read("repo/guide.md")
    assert len(fetches) == 3
    assert (repo / "guide.md").read_text() == "local uncommitted\n"


def test_failed_fetch_still_status_local_and_no_retry(library, repository, monkeypatch):
    repo, _ = repository
    original = library._run
    fetches = []
    def run(repo, args, **kwargs):
        if args[0] == "fetch":
            fetches.append(1)
            raise TimeoutError("timed out")
        return original(repo, args, **kwargs)
    monkeypatch.setattr(library, "_run", run)
    first = library.read("repo/guide.md")[0]
    second = library.read("repo/guide.md")[0]
    assert first["sync"]["status"]["ok"] and not first["sync"]["checked_remote"]
    assert "timed out" in second["sync"]["fetch"]["error"] and len(fetches) == 1


@pytest.mark.parametrize("state", ["no_upstream", "detached", "no_git"])
def test_uncertain_or_unavailable_still_reads(library, repository, state, monkeypatch):
    repo, ids = repository
    if state == "no_upstream":
        git(repo, "config", "--unset", "branch.main.remote")
    elif state == "detached":
        git(repo, "checkout", "--detach", ids[2])
    else:
        library.git = None
    details, _ = library.read("repo/guide.md")
    assert details["text"] and not details["sync"]["checked_remote"]
    assert details["sync"]["fetch"]["skipped"]


def test_git_paths_refs_operations_and_lock_are_bounded(library, repository):
    repo, _ = repository
    library.git = None
    for operation in ("push", "checkout", "-c", "clone"):
        with pytest.raises(ValueError):
            library.git_operation("repo", operation)
    with pytest.raises(ValueError):
        library.commit(repo, "--output=/tmp/no")
    with pytest.raises(ValueError):
        library.commit(repo, "HEAD:../secret")
    library.git = shutil.which("git")
    with ProcessLock("knowledge:" + str(repo.resolve())):
        sync = library.synchronize(repo)
    assert "error" in sync and not sync["checked_remote"]


def test_git_view_never_runs_textconv_or_clean_filters(library, repository, monkeypatch, tmp_path):
    repo, _ = repository
    marker = tmp_path / "executed"
    command = f'"{sys.executable}" -c "from pathlib import Path; Path(\'{marker}\').touch()"'
    git(repo, "config", "diff.danger.textconv", command)
    git(repo, "config", "filter.danger.clean", command)
    git(repo, "config", "filter.danger.process", command)
    (repo / ".gitattributes").write_text("*.md diff=danger filter=danger\n")
    (repo / "guide.md").write_text("dirty\n")
    # 不调用远端；保留真实 status / diff / show / log 的执行路径。
    library.attempted["repo"] = {"checked_remote": False}
    for operation in ("show", "diff", "log"):
        assert "text" in library.git_operation("repo", operation)
    assert library._run(repo, ["status", "--porcelain"])["ok"]
    assert not marker.exists()


def test_timeout_and_cancel_reap_process(library, tmp_path):
    if os.name == "nt":
        pytest.skip("POSIX 假 Git 脚本；Windows 进程树另验收")
    command = tmp_path / "fake-git"
    command.write_text(f"#!{sys.executable}\nimport time\ntime.sleep(60)\n")
    command.chmod(0o755)
    library.git = str(command)
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        library._run(library.root, ["log"], timeout=.1)
    assert time.monotonic() - started < 3
    event = threading.Event()
    def check():
        if event.is_set():
            raise RuntimeError("cancelled")
    library.checkpoint = check
    timer = threading.Timer(.1, event.set)
    timer.start()
    try:
        with pytest.raises(RuntimeError, match="cancelled"):
            library._run(library.root, ["log"])
    finally:
        timer.join()


def test_git_credentials_redacted_and_gui_only_policy():
    secret = "https://user:password@example.invalid/repo?token=hidden"
    assert "password" not in git_diagnostic(secret) and "hidden" not in git_diagnostic(secret)
    assert not set(KNOWLEDGE_TOOLS) & set(allowed_tools("Repair", "cli"))
    for mode in ("Construct", "Repair"):
        assert set(KNOWLEDGE_TOOLS) <= set(allowed_tools(mode, "gui"))


def test_commit_image_and_rewind_interval(library, repository, monkeypatch):
    from PIL import Image
    repo, ids = repository
    Image.new('RGB', (2, 2), 'blue').save(repo / 'ref.jpg')
    git(repo, 'add', 'ref.jpg')
    git(repo, 'commit', '-m', 'image')
    image_commit = git(repo, 'rev-parse', 'HEAD')
    original = library._run
    def run(repo, args, **kwargs):
        if args[0] == 'fetch':
            git(repo, 'update-ref', 'refs/remotes/origin/main', ids[0])
            return {'ok': True, 'stdout': '', 'error': ''}
        return original(repo, args, **kwargs)
    git(repo, 'update-ref', 'refs/remotes/origin/main', ids[2])
    monkeypatch.setattr(library, '_run', run)
    details = library.git_operation('repo', 'show', ref=image_commit, path='ref.jpg')
    assert details['_image'] == (repo / 'ref.jpg').read_bytes()
    sync = details['sync']
    assert sync['changed'] and sync['before'] == ids[2] and sync['after'] == ids[0]
    assert '-version 2' in library.git_operation('repo', 'diff', before=ids[2], after=ids[0])['text']


def test_search_each_involved_repo_once_and_git_cannot_escape(library, repository, monkeypatch, tmp_path):
    repo, ids = repository
    second = library.root / 'second'
    shutil.copytree(repo, second)
    fetches = []
    original = library._run
    def run(repo, args, **kwargs):
        if args[0] == 'fetch':
            fetches.append(library.relative(repo))
            return {'ok': True, 'stdout': '', 'error': ''}
        return original(repo, args, **kwargs)
    monkeypatch.setattr(library, '_run', run)
    assert library.search('needle')['total'] >= 2
    library.search('version')
    assert sorted(fetches) == ['repo', 'second']
    for path in ('../guide.md', '/etc/passwd', '.git/config'):
        with pytest.raises(ValueError):
            library.git_operation('repo', 'show', path=path)
    (repo / '.git/commondir').write_text(str(tmp_path))
    with pytest.raises(ValueError):
        library.read('repo/guide.md')


def test_limits_and_invalid_text_are_explicit(library, monkeypatch):
    import lalc.knowledge as knowledge
    monkeypatch.setattr(knowledge, 'MAX_BYTES', 30)
    assert library.search('needle')['skipped'] == ['guide.md']
    with pytest.raises(ValueError, match='2 MiB'):
        library.read('guide.md')
    (library.root / 'bad.md').write_bytes(b'\xff\x00')
    with pytest.raises(ValueError, match='UTF-8'):
        library.read('bad.md')
    for offset, limit in ((True, 10), (-1, 10), (0, 10000000)):
        with pytest.raises(ValueError):
            library.list(offset=offset, limit=limit)


def test_git_log_continues_and_output_has_version(library, repository):
    repo, ids = repository
    library.attempted['repo'] = {'checked_remote': False}
    first = library.git_operation('repo', 'log', limit=15)
    rest = library.git_operation('repo', 'log', offset=15, limit=16000, version=first['version'])
    assert len(first['text']) == 15 and 'version 0' in rest['text']
    history = library.git_operation('repo', 'log', ref=ids[2], history_offset=1)
    assert ids[2] not in history['text'] and ids[1] in history['text']
    assert history['next_history_offset'] is None
    before = library.git_operation('repo', 'diff')
    (repo / 'guide.md').write_text('different worktree\n')
    with pytest.raises(ValueError, match='变化'):
        library.git_operation('repo', 'diff', offset=10, version=before['version'])


def test_git_output_limit_and_diagnostic_redaction(library, tmp_path, monkeypatch):
    import lalc.knowledge as knowledge
    if os.name == 'nt':
        pytest.skip('POSIX 假 Git 脚本')
    command = tmp_path / 'fake-git'
    command.write_text(f'#!{sys.executable}\nimport sys\nsys.stderr.write("https://user:password@example.invalid/?token=hidden")\nsys.exit(1)\n')
    command.chmod(0o755)
    library.git = str(command)
    result = library._run(library.root, ['show'])
    assert not result['ok'] and 'password' not in result['error'] and 'hidden' not in result['error']
    monkeypatch.setattr(knowledge, 'MAX_OUTPUT', 128)
    command.write_text(f'#!{sys.executable}\nprint("x" * 8192)\n')
    with pytest.raises(ValueError, match='输出超过'):
        library._run(library.root, ['show'])


def prepare_version(library, repository, monkeypatch):
    """替身 fetch 使用仓库已有对象，构建与查询由普通测试替身完成。"""
    repo, ids = repository
    original = library._run
    def run(path, args, **kwargs):
        if args[0] == 'fetch':
            git(path, 'update-ref', 'refs/remotes/origin/main', ids[2])
            return {'ok': True, 'stdout': '', 'error': ''}
        return original(path, args, **kwargs)
    monkeypatch.setattr(library, '_run', run)
    assert library.synchronize(repo)['update']['ok']
    return repo


def test_disk_failure_keeps_a_and_reports_error(library, repository, monkeypatch):
    repo = prepare_version(library, repository, monkeypatch)
    active, record = library.active(repo)
    before = (library.version_home(repo) / 'active.json').read_bytes()
    def insufficient(*args):
        raise OSError('磁盘空间不足：预计需要 999 bytes，可用 1 bytes。')
    monkeypatch.setattr('lalc.knowledge.require_disk', insufficient)
    result = library.synchronize(repo, explicit=True)
    assert not result['update']['ok'] and '磁盘空间不足' in result['error']
    assert result['available_commit'] == record['commit']
    assert (library.version_home(repo) / 'active.json').read_bytes() == before
    assert library.read('repo/guide.md')[0]['text'] == (active / 'guide.md').read_text()
    assert len([p for p in library.version_home(repo).iterdir() if p.is_dir()]) == 1


def test_build_failure_keeps_a_and_first_failure_still_reads(library, repository, monkeypatch):
    repo, ids = repository
    original = library._run
    target = [ids[0]]
    def run(path, args, **kwargs):
        if args[0] == 'fetch':
            git(path, 'update-ref', 'refs/remotes/origin/main', target[0])
            return {'ok': True, 'stdout': '', 'error': ''}
        return original(path, args, **kwargs)
    monkeypatch.setattr(library, '_run', run)
    assert library.synchronize(repo)['update']['ok']
    pointer = (library.version_home(repo) / 'active.json').read_bytes()
    target[0] = ids[2]
    def fail(*args):
        raise OSError('index ENOSPC')
    monkeypatch.setattr(library.codesearch, 'build', fail)
    result = library.synchronize(repo, explicit=True)
    assert 'ENOSPC' in result['error'] and not result['update']['ok']
    assert (library.version_home(repo) / 'active.json').read_bytes() == pointer
    assert 'version 0' in library.read('repo/guide.md')[0]['text']
    second = library.root / 'fresh'
    shutil.copytree(repo, second)
    result = library.synchronize(second)
    assert not result['update']['ok'] and library.active(second) is None
    assert library.read('fresh/guide.md')[0]['text']


def test_hybrid_returns_hash_bound_reads_and_rejects_changed_content(library, repository, monkeypatch):
    repo = prepare_version(library, repository, monkeypatch)
    def search(repositories, query, limit, checkpoint):
        alias = next(iter(repositories))
        return {'results': [{'source': alias, 'path': alias + '/guide.md', 'start_line': 1,
                             'end_line': 2, 'score': .1}]}
    monkeypatch.setattr(library.codesearch, 'search', search)
    result = library.search_hybrid('documentation')
    hit = result['items'][0]
    assert library.read(**hit['read_arguments'])[0]['sha256'] == hit['sha256']
    library.path('repo/guide.md').write_text('changed')
    with pytest.raises(ValueError, match='过期'):
        library.search_hybrid('documentation')
    with pytest.raises(ValueError, match='变化'):
        library.read(**hit['read_arguments'])


def test_unchanged_version_reuses_index(library, repository, monkeypatch):
    repo = prepare_version(library, repository, monkeypatch)
    active = library.active(repo)[0]
    monkeypatch.setattr(library.codesearch, 'build', lambda *args: pytest.fail('不应重建相同版本'))
    result = library.synchronize(repo, explicit=True)
    assert result['update']['unchanged'] and library.active(repo)[0] == active


def test_reserved_and_nested_repositories_are_rejected(library, repository):
    repo, _ = repository
    nested = repo / 'nested'
    nested.mkdir()
    git(nested, 'init')
    with pytest.raises(ValueError, match='嵌套'):
        library.read('repo/nested/guide.md')
    git(library.root, 'init')
    with pytest.raises(ValueError, match='根'):
        library.repository(library.root)


def test_missing_remote_branch_does_not_publish_stale_upstream(library, repository, monkeypatch):
    repo = prepare_version(library, repository, monkeypatch)
    original = library._run
    before = (library.version_home(repo) / 'active.json').read_bytes()
    def run(path, args, **kwargs):
        if args[0] == 'fetch':
            assert args[-1] == '+refs/heads/main:refs/remotes/origin/main'
            return {'ok': False, 'stdout': '', 'error': "couldn't find remote ref refs/heads/main"}
        return original(path, args, **kwargs)
    monkeypatch.setattr(library, '_run', run)
    result = library.synchronize(repo, explicit=True)
    assert not result['update']['ok'] and not result['checked_remote']
    assert 'remote ref' in result['error']
    assert (library.version_home(repo) / 'active.json').read_bytes() == before
