"""覆盖 Skill 初始化、固定副本、链接拒绝、失败回滚及取消，不启动 pi。

项目根目录运行：.venv/bin/python -m pytest -q tests/test_agent_skills.py
"""

import asyncio
import threading
from pathlib import Path

import pytest

from lalc import agent_skills as skills


def test_defaults_initialized_once_and_empty_directory_stays_empty(tmp_path):
    root = skills.initialize_skills(tmp_path)
    assert {path.parent.name for path in root.glob("*/SKILL.md")} == set(skills.DEFAULT_SKILL_NAMES)
    for path in root.rglob("*"):
        if path.is_file():
            path.unlink()
    for path in root.iterdir():
        path.rmdir()
    assert skills.initialize_skills(tmp_path) == root
    assert list(root.iterdir()) == []


def test_snapshot_freezes_references_and_skips_links(tmp_path):
    root = tmp_path / "skills"
    root.mkdir()
    file = root / "reference.txt"
    file.write_text("old")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("must not be copied")
    (root / "escape").symlink_to(outside, target_is_directory=True)
    async def check():
        async with skills.skill_snapshot(tmp_path) as (fixed, diagnostics):
            assert diagnostics and not (fixed / "escape").exists()
            file.write_text("new")
            assert (fixed / "reference.txt").read_text() == "old"
        assert not fixed.exists()
        async with skills.skill_snapshot(tmp_path) as (next_root, _):
            assert (next_root / "reference.txt").read_text() == "new"
    asyncio.run(check())


def test_copy_failure_leaves_no_partial_initialization(tmp_path, monkeypatch):
    def fail(*args):
        raise OSError("disk full")
    monkeypatch.setattr(skills, "copy_content", fail)
    with pytest.raises(OSError, match="disk full"):
        skills.initialize_skills(tmp_path)
    assert not (tmp_path / "skills").exists()
    assert not list(tmp_path.glob(".skills-init-*"))


def test_directory_created_during_initialization_is_not_overwritten(tmp_path, monkeypatch):
    original = skills.copy_files
    def create_during_copy(files, destination):
        original(files, destination)
        (tmp_path / "skills").mkdir()
    monkeypatch.setattr(skills, "copy_files", create_during_copy)
    root = skills.initialize_skills(tmp_path)
    assert root.is_dir() and list(root.iterdir()) == []
    assert not list(tmp_path.glob(".skills-init-*"))


def test_initialization_exclusion_does_not_modify_existing_directory(tmp_path):
    from lalc.process_lock import ProcessLock
    root = tmp_path / "skills"
    root.mkdir()
    file = root / "custom.txt"
    file.write_text("custom")
    with ProcessLock(f"skills-init:{tmp_path}"):
        with pytest.raises(OSError):
            skills.initialize_skills(tmp_path)
    assert file.read_text() == "custom"
    assert list(root.iterdir()) == [file]


def test_cancel_waits_for_snapshot_worker_cleanup(tmp_path, monkeypatch):
    started = threading.Event()
    finished = threading.Event()
    roots = []
    def prepare(data_root, destination, cancelled):
        roots.append(destination)
        started.set()
        assert cancelled.wait(5)
        finished.set()
        raise InterruptedError("cancelled")
    monkeypatch.setattr(skills, "prepare_skills", prepare)
    async def work():
        async with skills.skill_snapshot(tmp_path):
            pytest.fail("Cancelled preparation must not yield")
    async def check():
        task = asyncio.create_task(work())
        assert await asyncio.to_thread(started.wait, 5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(check())
    assert finished.is_set() and not roots[0].exists()


def test_snapshot_rejects_changed_source(tmp_path, monkeypatch):
    root = tmp_path / "skills"
    root.mkdir()
    file = root / "reference.txt"
    file.write_text("old")
    original = skills.copy_files
    def changing(files, destination):
        original(files, destination)
        file.write_text("changed while copying")
    monkeypatch.setattr(skills, "copy_files", changing)
    async def check():
        async with skills.skill_snapshot(tmp_path):
            pytest.fail("Changed source must not be delivered")
    with pytest.raises(ValueError, match="内容发生变化"):
        asyncio.run(check())
