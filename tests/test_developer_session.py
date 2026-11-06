"""覆盖 Session 隔离、失败保护、锁内恢复、中断协议与日志保留；不启动 Agent。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_developer_session.py
"""

import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import uuid

import pytest

from lalc.agent_log import read_json
from lalc.developer_session import DeveloperSession, restored_history
from lalc.runtime import atomic_write_json
from test_agent_repair import host_for


@pytest.fixture
def session(tmp_path):
    host, loaded = host_for(tmp_path)
    return DeveloperSession.create(host.service, loaded.manifest_id)


def message(text):
    return {"role": "user", "content": [{"type": "text", "text": text}], "timestamp": 1}


def interrupted(chat, calls=("publish",)):
    chat.log.group += 1
    (chat.log.root / f"round-{chat.log.group}").mkdir()
    chat.log.record({"type": "round_opened"})
    chat.append_user(message("before crash"))
    chat.log.record({"type": "message_end", "message": {"role": "assistant", "content": [
        {"type": "toolCall", "id": f"call-{name}", "name": name, "arguments": {}} for name in calls]}})


def test_sessions_isolate_candidate_and_preserve_manual_source(tmp_path):
    host, loaded = host_for(tmp_path)
    (host.candidate / "manual.txt").write_text("manual draft")
    before = {path: path.read_bytes() for path in host.candidate.rglob("*") if path.is_file()}
    first = DeveloperSession.create(host.service, loaded.manifest_id)
    second = DeveloperSession.create(host.service, loaded.manifest_id)
    (first.host.candidate / "steps.total.py").write_text("unpublished first")
    assert (second.host.candidate / "steps.total.py").read_text() != "unpublished first"
    assert first.host.diff() and not second.host.diff()
    assert {path: path.read_bytes() for path in host.candidate.rglob("*") if path.is_file()} == before
    assert first.host.manager.default_manifest_id() == loaded.manifest_id


@pytest.mark.parametrize("entry", ["session", "manual"])
def test_workspace_staging_inherits_directory_permissions(tmp_path, monkeypatch, entry):
    host, loaded = host_for(tmp_path)
    mkdir = os.mkdir
    created = []

    def record(path, mode=0o777, *, dir_fd=None):
        created.append((Path(path), mode))
        return mkdir(path, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "mkdir", record)
    if entry == "session":
        session = DeveloperSession.create(host.service, loaded.manifest_id)
        assert session.host.validate()["ok"]
    else:
        host.initialize(loaded.manifest_id, replace=True)
        assert host.validate()["ok"]
    staging = [(path, mode) for path, mode in created
               if path.name.startswith((".pending-", ".candidate.", ".prepared.", ".lalc-candidate-"))]
    assert staging
    # Windows 对 0700 设置独立 DACL，重命名后普通 Explorer 仍可能无法访问。
    assert all(mode != 0o700 for _, mode in staging)


def test_failed_creation_has_no_visible_session_or_changes(session, monkeypatch):
    before = sorted(session.path.parent.iterdir())
    with pytest.raises(ValueError):
        DeveloperSession.create(session.host.service, None)
    with pytest.raises(ValueError):
        DeveloperSession.create(session.host.service, "missing")
    def fail(*_):
        raise OSError("disk full")
    monkeypatch.setattr("lalc.developer_session.atomic_write_json", fail)
    with pytest.raises(OSError):
        DeveloperSession.create(session.host.service, json.loads((session.path / "session.json").read_text())["source_manifest_id"])
    assert sorted(session.path.parent.iterdir()) == before


@pytest.mark.parametrize("identity", ["../escape", "", "not-a-uuid", str(uuid.uuid4()).upper()])
def test_reject_invalid_identity(session, identity):
    with pytest.raises(ValueError):
        DeveloperSession(session.host.service, identity)


def test_reject_construct_symlink_and_corrupt_reference(session, tmp_path):
    metadata = session.path / "session.json"
    original = metadata.read_bytes()
    value = json.loads(original)
    value["mode"] = "Construct"
    atomic_write_json(metadata, value)
    with pytest.raises(ValueError, match="Repair"):
        session.conversation()
    metadata.write_bytes(original)
    outside = tmp_path / "outside"
    outside.mkdir()
    (session.path / "log" / "round-1").symlink_to(outside)
    with pytest.raises(ValueError, match="符号链接"):
        session.conversation()
    (session.path / "log" / "round-1").unlink()
    chat = session.conversation()
    chat.append_user(message("large" * 1000))
    for path in (chat.log.root / "objects").iterdir():
        path.unlink()
    with pytest.raises((ValueError, OSError)):
        session.conversation()


def test_restart_restores_associations_marks_unknown_and_keeps_evidence(session):
    chat = session.conversation()
    interrupted(chat, ("publish", "edit", "read"))
    actual = {"content": [{"type": "text", "text": "saved-manifest-id"}], "details": {"manifest_id": "saved-manifest-id"}}
    chat.log.record({"type": "repair_tool", "toolCallId": "call-publish", "result": actual})
    chat.log.record({"type": "tool_execution_end", "toolCallId": "call-edit", "result": {"content": [{"type": "text", "text": "edited"}]}, "isError": False})
    chat.log.record({"type": "tool_reserved", "sequence": 12})
    original = (chat.log.root / "events.jsonl").read_bytes()
    restored = DeveloperSession(session.host.service, session.identity).conversation()
    results = [item for item in restored.history if item["role"] == "toolResult"]
    assert [item["toolName"] for item in results] == ["publish", "edit", "read"]
    assert results[0]["details"] == actual["details"]
    assert not results[1]["isError"]
    assert results[2]["isError"] and results[2]["details"]["outcome"] == "unknown"
    assert read_json(restored.log.root / "round-1/result.json")["status"] == "interrupted"
    assert restored.log.group == 1 and restored.tools.sequence == 12
    assert (chat.log.root / "events.jsonl").read_bytes().startswith(original)
    again = session.conversation()
    assert again.history == restored.history
    assert read_json(again.log.root / "context.json") == again.history


def test_repeated_tool_ids_in_later_rounds_keep_distinct_results():
    events = []
    for number in (1, 2):
        events.extend([
            {"event": {"type": "session_message", "message": message(str(number))}},
            {"event": {"type": "message_end", "message": {"role": "assistant", "content": [
                {"type": "toolCall", "id": "repeated", "name": "read", "arguments": {}}]}}},
            {"event": {"type": "tool_execution_end", "toolCallId": "repeated", "result": {
                "content": [{"type": "text", "text": str(number)}]}}}])
    history = restored_history(events)
    assert [item["content"][0]["text"] for item in history if item["role"] == "toolResult"] == ["1", "2"]
    events[1]["event"]["message"]["content"] *= 2
    with pytest.raises(ValueError, match="ID 重复"):
        restored_history(events)


def test_incomplete_tail_retained_but_complete_corruption_fails(session):
    chat = session.conversation()
    chat.append_user(message("saved"))
    path = chat.log.root / "events.jsonl"
    with path.open("ab") as stream:
        stream.write(b'{"unfinished":')
    restored = session.conversation()
    assert restored.history == [message("saved")]
    assert next(chat.log.root.glob("interrupted-tail-*.bin")).read_bytes() == b'{"unfinished":'
    with path.open("ab") as stream:
        stream.write(b'broken\n')
    with pytest.raises(ValueError):
        session.conversation()


def test_idle_object_reloads_latest_state_before_new_round(session, monkeypatch):
    stale = session.conversation()
    other = session.conversation()
    other.append_user(message("from another entry"))
    def no_pi(*args, **kwargs):
        raise RuntimeError("stop before pi")
    monkeypatch.setattr("lalc.agent_repair.configured_pi", no_pi)
    result = asyncio.run(stale.run("new user input", SimpleNamespace(base_url="http://localhost:1/v1", model="test", max_requests=2, ask_api_key=False)))
    assert result["status"] == "incomplete"
    assert stale.history[0] == message("from another entry")
    assert "new user input" in stale.history[1]["content"][0]["text"]
    with session.host.candidate_lock():
        pass


def test_real_process_lock_and_exit_release(session):
    chat = session.conversation()
    script = ('import sys; from pathlib import Path; from lalc.process_lock import ProcessLock; '
              'lock=ProcessLock("candidate:"+str(Path(sys.argv[1]).resolve())); '
              'lock.acquire(); print("ready",flush=True); input()')
    process = subprocess.Popen([sys.executable, "-c", script, str(session.host.candidate)],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert process.stdout.readline().strip() == "ready"
        with pytest.raises(OSError):
            session.conversation()
        with pytest.raises(OSError):
            asyncio.run(chat.run("blocked", SimpleNamespace()))
        assert not list((session.path / "log").glob("round-*"))
    finally:
        process.kill()
        process.communicate(timeout=5)
    assert session.conversation().history == []


def test_process_exit_retains_unfinished_call_without_replaying(session):
    script = '''
import os, sys
from pathlib import Path
from lalc.application import ApplicationService
from lalc.developer_session import DeveloperSession
session = DeveloperSession(ApplicationService(Path(sys.argv[1])), sys.argv[2])
chat = session.conversation()
chat.log.group = 1
(chat.log.root / "round-1").mkdir()
chat.append_user({"role": "user", "content": [{"type": "text", "text": "before exit"}], "timestamp": 1})
chat.log.record({"type": "message_end", "message": {"role": "assistant", "content": [
    {"type": "toolCall", "id": "unfinished", "name": "publish", "arguments": {}}]}})
os._exit(0)
'''
    result = subprocess.run([sys.executable, "-c", script, str(session.host.service.data_root), session.identity], timeout=5)
    assert result.returncode == 0
    restored = session.conversation()
    assert restored.history[0]["content"][0]["text"] == "before exit"
    assert restored.history[2]["details"]["outcome"] == "unknown"
    assert read_json(restored.log.root / "round-1/result.json")["status"] == "interrupted"


def test_tool_artifacts_and_invalid_preview_survive_restart(session):
    chat = session.conversation()
    chat.tools.call("action_contracts", {})
    old = {path: path.read_bytes() for path in chat.log.root.glob("tool-*")}
    chat.tools.previews["old-preview"] = {"not": "persisted"}
    restored = session.conversation()
    result = read_json(restored.tools.call("crop_asset", {"preview_id": "old-preview"}))
    assert result["isError"] and "失效" in result["details"]["error"]
    assert all(path.read_bytes() == content for path, content in old.items())
    assert restored.tools.sequence == 2


@pytest.mark.parametrize("source", [[], ["--from", "x", "--session", "y"]])
def test_cli_requires_exactly_one_source(source):
    from lalc.__main__ import _parser
    with pytest.raises(SystemExit) as raised:
        _parser().parse_args(["repair", *source, "--problem", "test"])
    assert raised.value.code == 1


def test_cli_chat_releases_lock_while_waiting_and_reloads_other_entry(session, monkeypatch, capsys):
    import lalc.__main__ as cli
    monkeypatch.setattr(cli, "default_data_root", lambda: session.host.service.data_root)
    def no_pi(*args, **kwargs):
        raise RuntimeError("stop before pi")
    monkeypatch.setattr("lalc.agent_repair.configured_pi", no_pi)
    identities = []
    def next_message(_prompt):
        rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
        identity = rows[-1]["session_id"]
        other = DeveloperSession(session.host.service, identity)
        chat = other.conversation()
        with other.host.candidate_lock():
            pass
        if identities:
            assert "other entry while idle" in json.dumps(chat.history)
            assert "second CLI message" in json.dumps(chat.history)
            assert chat.log.group == 2
            return ""
        identities.append(identity)
        with other.host.candidate_lock():
            chat.append_user(message("other entry while idle"))
        return "second CLI message"
    monkeypatch.setattr("builtins.input", next_message)
    source = json.loads((session.path / "session.json").read_text())["source_manifest_id"]
    assert cli.main(["repair", "--from", source, "--chat", "--problem", "first CLI message",
                     "--base-url", "http://localhost:1/v1", "--model", "test"]) == 0


def test_history_browsing_defers_model_context_and_preserves_interruption(session, monkeypatch):
    chat = session.conversation()
    interrupted(chat, ('read',))
    chat.log.record({'type': 'lalc_request', 'requests': 7})
    chat.log.record({'type': 'tool_reserved', 'sequence': 12})
    chat.log.save_json('context.json', chat.history)
    context = (chat.log.root / 'context.json').read_bytes()
    from lalc.agent_log import LogStore
    unpack, register_image = LogStore.unpack, LogStore.register_image
    (chat.log.root / 'tool-1.png').write_bytes(b'original image')
    monkeypatch.setattr(LogStore, 'register_image', lambda *_: pytest.fail('浏览不得读取旧截图'))
    monkeypatch.setattr(LogStore, 'unpack', lambda *_args, **_kwargs: pytest.fail('浏览不得展开完整历史'))
    browsing = session.conversation(load_history=False)
    assert browsing.log.group == 1 and browsing.log.requests == 7
    assert browsing.tools.sequence == 12
    assert (chat.log.root / 'context.json').read_bytes() == context
    monkeypatch.setattr(LogStore, 'unpack', unpack)
    monkeypatch.setattr(LogStore, 'register_image', register_image)
    assert read_json(chat.log.root / 'round-1/result.json')['status'] == 'interrupted'
    with session.host.candidate_lock():
        session.restore(browsing)
    assert browsing.history[0] == message('before crash')
    tool_result = next(item for item in browsing.history if item['role'] == 'toolResult')
    assert tool_result['isError'] and tool_result['details']['outcome'] == 'unknown'
    assert read_json(chat.log.root / 'context.json') == browsing.history
