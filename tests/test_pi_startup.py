"""覆盖模拟 pi 的路径选择、一次回退、请求边界和清理顺序，不启动真实 Agent。

项目根目录运行：.venv/bin/python -m pytest -q tests/test_pi_startup.py
"""

import asyncio
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

import lalc.pi_probe as probe


@pytest.fixture
def packaged(tmp_path, monkeypatch):
    executable = tmp_path / "LALC.exe"
    bundled = tmp_path / "pi/pi.exe"
    bundled.parent.mkdir()
    bundled.write_bytes(b"test")
    monkeypatch.setattr(sys, "executable", str(executable))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "_internal"), raising=False)
    monkeypatch.setattr(probe.shutil, "which", lambda requested: "/environment/pi")
    monkeypatch.setattr(probe.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout=probe.PI_VERSION))
    return bundled


def test_bundled_first_explicit_path_preserved_and_missing_bundle_uses_environment(packaged, tmp_path):
    startup = probe.PiStartup()
    assert startup.select("pi", {}, str(tmp_path), None) == [str(packaged)]
    assert startup.fallback == "/environment/pi"
    assert probe.PiStartup().select("/custom/pi", {}, str(tmp_path), None) == ["/environment/pi"]
    packaged.unlink()
    assert probe.PiStartup().select("pi", {}, str(tmp_path), None) == ["/environment/pi"]


def test_failed_version_probe_falls_back_once_but_different_version_only_warns(packaged, tmp_path, monkeypatch):
    calls, events = [], []
    def version(command, **kwargs):
        calls.append(command[0])
        if command[0] == str(packaged):
            raise subprocess.CalledProcessError(1, command)
        return SimpleNamespace(stdout="different")
    monkeypatch.setattr(probe.subprocess, "run", version)
    startup, env = probe.PiStartup(), {}
    command = startup.select("pi", env, str(tmp_path), events.append)
    assert calls == [str(packaged), "/environment/pi"] and startup.fallback is None
    assert env["LALC_PI_VERSION"] == "different"
    assert any(event["type"] == "pi_fallback" for event in events)
    assert any(event["type"] == "pi_version_warning" for event in events)
    assert not startup.retry(command, env, str(tmp_path), RuntimeError("again"))
    calls.clear()
    monkeypatch.setattr(probe.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout="different"))
    assert probe.PiStartup().select("pi", {}, str(tmp_path), None) == [str(packaged)]


def test_same_environmental_path_is_not_retried(packaged, tmp_path, monkeypatch):
    monkeypatch.setattr(probe.shutil, "which", lambda _: str(packaged))
    startup = probe.PiStartup()
    startup.select("pi", {}, str(tmp_path), None)
    assert startup.fallback is None


@pytest.mark.parametrize("failure", ["spawn", "eof", "cancel", "cleanup", "protocol", "timeout"])
def test_ready_failure_only_retries_supported_failures_after_cleanup(monkeypatch, failure):
    events, command = [], ["bundled"]
    startup = probe.PiStartup()
    startup.env, startup.fallback = {}, "environment"
    monkeypatch.setattr(startup, "version", lambda *args: None)
    @asynccontextmanager
    async def raw(command, env, cwd, show):
        selected = command[0]
        events.append("open:" + selected)
        if selected == "bundled" and failure == "spawn":
            raise probe.PiStartError("failed", "pi_start")
        async def send(value):
            events.append(value["type"])
        async def event():
            if selected == "bundled":
                if failure in {"eof", "cleanup"}:
                    raise probe.PiExited("exited")
                if failure == "cancel":
                    raise asyncio.CancelledError()
                if failure == "protocol":
                    raise ValueError("bad JSON")
                raise TimeoutError("ready timeout")
            return {"type": "lalc_ready"}
        try:
            yield send, event
        finally:
            events.append("close:" + selected)
            if selected == "bundled" and failure == "cleanup":
                raise probe.AgentDiagnosticError("cleanup failed", "pi_cleanup")
    monkeypatch.setattr(probe, "_rpc_session", raw)
    async def run():
        async with probe.rpc_session(command, {}, ".", lambda _: None, startup=startup) as (send, event):
            assert await event() == {"type": "lalc_ready"}
            await send({"type": "prompt"})
    if failure in {"spawn", "eof"}:
        asyncio.run(run())
        assert command == ["environment"] and startup.request_started
        if failure == "eof":
            assert events.index("close:bundled") < events.index("open:environment")
    else:
        with pytest.raises(BaseException):
            asyncio.run(run())
        assert "open:environment" not in events


def test_request_send_and_later_process_failure_never_retry(monkeypatch):
    startup, command = probe.PiStartup(), ["bundled"]
    startup.env, startup.fallback = {}, "environment"
    sends = []
    @asynccontextmanager
    async def raw(*args):
        async def send(value):
            sends.append(value)
            raise BrokenPipeError("prompt partially written")
        async def event():
            return {"type": "lalc_ready"}
        yield send, event
    monkeypatch.setattr(probe, "_rpc_session", raw)
    async def run():
        async with probe.rpc_session(command, {}, ".", lambda _: None, startup=startup) as (send, event):
            await event()
            await send({"type": "prompt"})
    with pytest.raises(BrokenPipeError):
        asyncio.run(run())
    assert startup.request_started and len(sends) == 1
    @asynccontextmanager
    async def failed(*args):
        raise probe.PiStartError("second process failed", "pi_start")
        yield
    monkeypatch.setattr(probe, "_rpc_session", failed)
    with pytest.raises(probe.PiStartError):
        asyncio.run(run())
    assert command == ["bundled"]


def test_frozen_library_paths_are_removed_only_for_child(packaged, tmp_path):
    root = Path(sys._MEIPASS)
    import os
    env = {"PATH": os.pathsep.join([str(root), str(root / "Qt/bin"), "/system/bin"])}
    with probe.pi_process_environment(env) as prepared:
        assert prepared["PATH"] == "/system/bin"
    assert str(root) in env["PATH"]


def test_spawned_process_is_reaped_when_host_environment_restore_fails(monkeypatch):
    events = []
    class Process:
        returncode = None
        def kill(self):
            events.append("kill")
        async def wait(self):
            events.append("wait")
            self.returncode = 1
    async def spawn(*args, **kwargs):
        return Process()
    @contextmanager
    def environment(env):
        yield env
        raise probe.AgentDiagnosticError("restore failed", "pi_cleanup")
    monkeypatch.setattr(probe, "pi_process_environment", environment)
    monkeypatch.setattr(probe.asyncio, "create_subprocess_exec", spawn)
    startup = probe.PiStartup()
    startup.fallback = "environment"
    async def run():
        async with probe.rpc_session(["bundled"], {}, ".", lambda _: None, startup=startup):
            pytest.fail("cleanup failure accepted")
    with pytest.raises(probe.AgentDiagnosticError, match="restore failed"):
        asyncio.run(run())
    assert events == ["kill", "wait"] and startup.fallback == "environment"


def test_version_environment_failure_does_not_switch_pi(packaged, tmp_path, monkeypatch):
    @contextmanager
    def environment(env):
        yield env
        raise probe.AgentDiagnosticError("restore failed", "pi_cleanup")
    monkeypatch.setattr(probe, "pi_process_environment", environment)
    startup = probe.PiStartup()
    with pytest.raises(probe.AgentDiagnosticError, match="restore failed"):
        startup.select("pi", {}, str(tmp_path), None)
    assert startup.fallback == "/environment/pi"
