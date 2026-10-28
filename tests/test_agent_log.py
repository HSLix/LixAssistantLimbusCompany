"""覆盖对话内无损引用、完整展开、复制独立性、脱敏及日志失败边界，不启动 Agent。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_agent_log.py
"""

import base64
import json
from pathlib import Path
import shutil

import pytest

from lalc.agent_log import MARKER, read_json, read_events
from lalc.agent_repair import RepairLog


def test_complete_round_trip_reuses_images_and_structured_history(tmp_path):
    log = RepairLog(tmp_path)
    image = bytes(range(256)) * 100
    path = log.path / "original.png"
    path.write_bytes(image)
    log.store.register_image(path)
    encoded = base64.b64encode(image).decode()
    message = {"role": "assistant", "content": [{"type": "text", "text": "回答" * 1000},
               {"type": "image", "data": encoded, "mimeType": "image/png"}]}
    request = {"messages": [message, message], "image": "data:image/png;base64," + encoded}
    log.save_json("first.json", request)
    before = set(log.path.rglob("*"))
    log.save_json("second.json", request)
    assert set(log.path.rglob("*")) - before == {log.path / "second.json"}
    assert read_json(log.path / "first.json") == request
    assert read_json(log.path / "second.json") == request
    assert not list(log.path.glob("objects/*.bin"))
    assert (log.path / "first.json").stat().st_size < len(json.dumps(request)) // 10
    moved = tmp_path / "copied"
    shutil.copytree(log.path, moved)
    shutil.rmtree(log.path)
    assert read_json(moved / "first.json") == request


def test_events_keep_identity_live_callback_and_cross_round_storage(tmp_path):
    live = []
    log = RepairLog(tmp_path, "test-private-key", on_event=live.append)
    body = {"type": "tool_execution_end", "toolCallId": "id-1", "result": {"text": "结果" * 2000}}
    log.record(body)
    root = log.path
    log.path = root / "round-1"
    log.path.mkdir()
    log.group = 1
    log.record(body)
    log.record({"type": "error", "message": "Bearer test-private-key"})
    assert live[0]["event"] == live[1]["event"] == body
    assert list(read_events(root / "events.jsonl"))[0]["event"] == body
    assert list(read_events(log.path / "events.jsonl"))[0]["event"] == body
    assert not (log.path / "objects").exists()
    assert len(list(root.glob("objects/*.txt"))) == 1
    assert "test-private-key" not in "".join(p.read_text() for p in root.rglob("*") if p.is_file())


def test_literal_marker_is_not_interpreted_as_a_reference(tmp_path):
    log = RepairLog(tmp_path)
    value = {MARKER: {"path": "../../private", "literal": [["x", "y"]]},
             "nested": [{MARKER: {"kind": "txt", "sha256": "bad"}}]}
    log.save_json("literal.json", value)
    assert read_json(log.path / "literal.json") == value


@pytest.mark.parametrize("pairs", [None, [["key"]], [[1, "value"]], [["key", 1], ["key", 2]]])
def test_corrupt_literal_escape_fails_explicitly(tmp_path, pairs):
    log = RepairLog(tmp_path)
    path = log.path / "corrupted.json"
    path.write_text(json.dumps({MARKER: {"literal": pairs}}))
    with pytest.raises(ValueError, match="转义格式"):
        read_json(path)


@pytest.mark.parametrize("fault", ["missing", "hash", "outside", "symlink"])
def test_invalid_reference_fails_explicitly(tmp_path, fault):
    log = RepairLog(tmp_path)
    log.save_json("value.json", {"message": "x" * 2048})
    raw = json.loads((log.path / "value.json").read_text())
    ref = raw["message"][MARKER]
    blob = log.path / ref["path"]
    if fault == "missing":
        blob.unlink()
    elif fault == "hash":
        blob.write_bytes(b"corrupted")
    elif fault == "outside":
        ref["path"] = "../outside.txt"
    else:
        outside = tmp_path / "outside.txt"
        outside.write_bytes(blob.read_bytes())
        blob.unlink()
        blob.symlink_to(outside)
    (log.path / "value.json").write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        read_json(log.path / "value.json")


def test_failed_blob_write_does_not_publish_or_replace_document(tmp_path, monkeypatch):
    import lalc.agent_log as storage
    log = RepairLog(tmp_path)
    log.save_json("context.json", {"value": "original"})
    original = (log.path / "context.json").read_bytes()
    def fail(*args):
        raise OSError("storage unavailable")
    monkeypatch.setattr(storage.os, "link", fail)
    with pytest.raises(OSError):
        log.save_json("context.json", {"value": "large" * 1000})
    assert (log.path / "context.json").read_bytes() == original
    assert not list(log.path.rglob(".pending-*"))


def test_conversations_do_not_share_objects_and_old_logs_stay_untouched(tmp_path):
    first, second = RepairLog(tmp_path), RepairLog(tmp_path)
    value = {"text": "独立" * 1000}
    first.save_json("value.json", value)
    second.save_json("value.json", value)
    assert list(first.path.glob("objects/*")) and list(second.path.glob("objects/*"))
    shutil.rmtree(first.path)
    assert read_json(second.path / "value.json") == value
    old = tmp_path / "old.json"
    old.write_text('{"old":"unchanged"}')
    original = old.read_bytes()
    with pytest.raises(ValueError, match="旧日志"):
        read_json(old)
    assert old.read_bytes() == original


def test_payload_ingestion_and_tool_transport_are_separate(tmp_path):
    log = RepairLog(tmp_path)
    log.group = 1
    (log.path / "round-1").mkdir()
    transport = tmp_path / "temporary"
    (transport / "payloads").mkdir(parents=True)
    log.transport_dir = transport
    source = transport / "payloads/request-1.json"
    payload = {"messages": [{"content": "长消息" * 1000}]}
    source.write_text(json.dumps(payload))
    log.record({"type": "lalc_request", "requests": 1, "payload_path": str(source)})
    assert read_json(log.path / "round-1/request-1.json") == payload
    assert not source.exists()
    result = {"content": [{"type": "text", "text": "完整结果" * 1000}]}
    path = Path(log.tool_result("tool-1.json", result))
    assert path.parent == transport and json.loads(path.read_text()) == result
    assert read_json(log.path / "tool-1.json") == result


def test_expand_command_keeps_existing_output(tmp_path, monkeypatch):
    from lalc.agent_log import main
    log = RepairLog(tmp_path)
    value = {"message": "输出" * 1000}
    log.save_json("request.json", value)
    output = tmp_path / "expanded.json"
    monkeypatch.setattr("sys.argv", ["agent_log", str(log.path / "request.json"), "--output", str(output)])
    main()
    assert json.loads(output.read_text()) == value
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 1 and json.loads(output.read_text()) == value
