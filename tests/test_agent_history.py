"""覆盖版本索引增量写入、重建、跨版本有界读取、图片及故障降级，不启动 Agent。

项目根目录运行：QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_agent_history.py
"""

import asyncio
import base64
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from lalc.agent_history import AgentHistory, DATABASE, record_observation
from lalc.agent_log import read_events, read_json
from lalc.agent_repair import RepairLog
from lalc.agent_policy import allowed_tools
from lalc import agent_history as history


def observe(monkeypatch, game="1.118.0", build="26156805", day=1):
    value = {"game_version": game, "steam_build_id": build,
             "observed_at": f"2026-11-{day:02}T00:00:00Z", "errors": []}
    monkeypatch.setattr(history, "observe_game_version", lambda _: value)
    return value


def add(log, tmp_path, number, monkeypatch, game="1.118.0", build="26156805", day=1):
    log.group = number
    observe(monkeypatch, game, build, day)
    record_observation(log, tmp_path, "gui:Repair", "修复标题")


def test_incremental_groups_update_only_current_pair_and_deduplicate(tmp_path, monkeypatch):
    log = RepairLog(tmp_path)
    index = AgentHistory(tmp_path)
    add(log, tmp_path, 1, monkeypatch)
    add(log, tmp_path, 2, monkeypatch, game="1.119.0", day=2)
    add(log, tmp_path, 3, monkeypatch, game="1.119.0", day=3)
    record = read_json(log.root / "version-observations/3.json")
    index.add(record, log.root)
    groups = index.versions()["versions"]
    assert len(groups) == 2 and all(g["session_count"] == 1 for g in groups)
    assert groups[0]["last_observed_at"].startswith("2026-11-03")
    assert groups[1]["last_observed_at"].startswith("2026-11-01")
    record["observation"]["observed_at"] = "2026-11-04T00:00:00Z"
    with pytest.raises(ValueError, match="Conflicting"):
        index.add(record, log.root)


def test_unknown_partial_pairs_and_no_automatic_history_scan(tmp_path, monkeypatch):
    old = RepairLog(tmp_path)
    old.record({"type": "old"})
    log = RepairLog(tmp_path)
    add(log, tmp_path, 1, monkeypatch, game=None, build=None)
    add(log, tmp_path, 2, monkeypatch, build=None)
    add(log, tmp_path, 3, monkeypatch, game=None)
    with monkeypatch.context() as scoped:
        scoped.setattr(Path, "glob", lambda *_: pytest.fail("Unexpected history scan"))
        assert len(AgentHistory(tmp_path).versions()["versions"]) == 3
        assert AgentHistory(tmp_path).search(unknown=True)["sessions"][0]["matches"][0]["round"] == 1
    assert AgentHistory(tmp_path).rebuild()["observations"] == 3
    assert all(row["session_id"] != old.identity for row in AgentHistory(tmp_path).search()["sessions"])


def test_exact_partial_group_does_not_merge_with_complete_group(tmp_path, monkeypatch):
    log = RepairLog(tmp_path)
    add(log, tmp_path, 1, monkeypatch, build=None)
    add(log, tmp_path, 2, monkeypatch)
    index = AgentHistory(tmp_path)
    broad = index.search(game_version='1.118.0')['sessions'][0]
    assert [row['round'] for row in broad['matches']] == [1, 2]
    group = next(row['version_group'] for row in index.versions()['versions'] if row['steam_build_id'] is None)
    exact = index.search(version_group=group)['sessions'][0]
    assert [row['round'] for row in exact['matches']] == [1]
    page, _ = index.read(**exact['read_arguments'])
    assert {row['round'] for row in page['events']} == {1}


def test_read_filters_round_versions_old_unknown_and_long_event_continuation(tmp_path, monkeypatch):
    log = RepairLog(tmp_path)
    log.record({"type": "old", "text": "old"})
    add(log, tmp_path, 1, monkeypatch)
    log.record({"type": "answer", "text": "A" * 30000})
    add(log, tmp_path, 2, monkeypatch, game="1.119.0", day=2)
    log.record({"type": "answer", "text": "B"})
    index = AgentHistory(tmp_path)
    result = index.search(game_version="1.118.0")["sessions"][0]
    page, _ = index.read(**result["read_arguments"])
    assert all(event["round"] == 1 for event in page["events"])
    assert page["next"]["text_offset"] > 0
    next_page, _ = index.read(**result["read_arguments"], **page["next"])
    assert next_page["events"][0]["text_offset"] > 0
    all_events, _ = index.read(log.identity, round_numbers=[0, 2])
    assert all_events["events"][0]["version_group"]["label"] == "Unknown"
    assert all_events["events"][-1]["version_group"]["game_version"] == "1.119.0"
    assert {path.name for path in (log.root / "version-observations").glob("*.json")} == {"1.json", "2.json"}


def test_text_does_not_load_images_and_explicit_image_checks_hash_and_round(tmp_path, monkeypatch):
    log = RepairLog(tmp_path)
    add(log, tmp_path, 1, monkeypatch)
    image = log.root / "image.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    log.store.register_image(image)
    log.record({"type": "message", "content": [{"type": "image", "mimeType": "image/png",
                                               "data": base64.b64encode(image.read_bytes()).decode()}]})
    index = AgentHistory(tmp_path)
    original = Path.read_bytes
    with monkeypatch.context() as scoped:
        scoped.setattr(Path, "read_bytes", lambda path: pytest.fail("Image unexpectedly loaded") if path == image else original(path))
        page, _ = index.read(log.identity)
    image_id = page["events"][-1]["images"][0]
    metadata, content = index.read(log.identity, image_id=image_id)
    assert content == image.read_bytes() and metadata["version_group"]["game_version"] == "1.118.0"
    with pytest.raises(ValueError, match="selected rounds"):
        index.read(log.identity, round_numbers=[2], image_id=image_id)
    image.write_bytes(b"bad")
    with pytest.raises(ValueError, match="hash"):
        index.read(log.identity, image_id=image_id)


def test_index_failure_keeps_fact_and_missing_index_requires_explicit_rebuild(tmp_path, monkeypatch):
    log = RepairLog(tmp_path)
    value = observe(monkeypatch)
    with monkeypatch.context() as scoped:
        scoped.setattr(AgentHistory, "add", lambda *_: (_ for _ in ()).throw(OSError("index failed")))
        assert record_observation(log, tmp_path, "cli:Repair", "Title") == value
    assert read_json(log.root / "version-observations/0.json")["observation"] == value
    index = AgentHistory(tmp_path)
    assert index.rebuild()["observations"] == 1
    index.database.unlink()
    with pytest.raises(ValueError, match="history-rebuild"):
        index.versions()
    with pytest.raises(ValueError, match="history-rebuild"):
        index.add(read_json(log.root / "version-observations/0.json"), log.root)
    assert index.rebuild()["observations"] == 1


def test_failed_rebuild_preserves_original_database_and_symlinks_rejected(tmp_path, monkeypatch):
    log = RepairLog(tmp_path)
    add(log, tmp_path, 1, monkeypatch)
    index = AgentHistory(tmp_path)
    previous = index.database.read_bytes()
    path = log.root / "version-observations/1.json"
    path.write_text("bad")
    with pytest.raises(ValueError):
        index.rebuild()
    assert index.database.read_bytes() == previous
    path.unlink()
    path.symlink_to(tmp_path / "outside")
    with pytest.raises(ValueError, match="symlink"):
        index.rebuild()


def test_corrupt_database_recovers_from_facts_and_cannot_redirect_reading(tmp_path, monkeypatch):
    log = RepairLog(tmp_path)
    add(log, tmp_path, 1, monkeypatch)
    index = AgentHistory(tmp_path)
    index.database.write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='history-rebuild'):
        index.versions()
    add(log, tmp_path, 2, monkeypatch, day=2)
    assert read_json(log.root / 'version-observations/2.json')['round'] == 2
    assert index.rebuild()['observations'] == 2
    with index.connection(write=True) as connection:
        connection.execute('UPDATE rounds SET path=?', ('../outside',))
    with pytest.raises(ValueError, match='path'):
        index.read(log.identity)


def test_concurrent_transactions_never_lose_successful_writes(tmp_path, monkeypatch):
    logs = [RepairLog(tmp_path) for _ in range(8)]
    observe(monkeypatch)
    for log in logs:
        record_observation(log, tmp_path, "diagnostic:connection", "Connection")
    index = AgentHistory(tmp_path)
    records = []
    for log in logs:
        record = read_json(log.root / "version-observations/0.json")
        record["round"] = 1
        records.append((record, log.root))
    def write(value):
        try:
            index.add(*value)
            return True
        except OSError:
            return False
    with ThreadPoolExecutor(max_workers=4) as pool:
        succeeded = list(pool.map(write, records))
    assert any(succeeded)
    assert index.versions()["versions"][0]["session_count"] == 8
    with index.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM rounds").fetchone()[0] == 8 + sum(succeeded)


def test_round_observation_is_persistent_and_not_rewritten_on_resume(tmp_path, monkeypatch):
    from test_agent_repair import host_for
    from lalc.agent_prompts import user_message_text
    host, _ = host_for(tmp_path)
    conversation = host.conversation
    value = observe(monkeypatch)
    monkeypatch.setattr("lalc.agent_repair.settings_snapshot", lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("stop after observation")))
    asyncio.run(conversation.run("hello", SimpleNamespace(pi="pi", ask_api_key=False)))
    assert read_json(conversation.log.root / "version-observations/1.json")["observation"] == value
    assert "game_version_observation" in conversation.history[0]["content"][0]["text"]
    assert user_message_text(conversation.history[0]["content"][0]["text"]) == "hello"
    previous = conversation.history[0].copy()
    observe(monkeypatch, game="1.119.0", day=2)
    asyncio.run(conversation.run("next", SimpleNamespace(pi="pi", ask_api_key=False)))
    assert conversation.history[0] == previous


def test_tools_all_entry_permissions_and_removed_probe(tmp_path, monkeypatch):
    for mode, entry in (("Construct", "gui"), ("Repair", "gui"), ("Repair", "cli")):
        assert {"list_game_versions", "search_agent_sessions", "read_agent_session"} <= set(allowed_tools(mode, entry))
    import lalc.__main__ as cli
    monkeypatch.setattr(cli, "default_data_root", lambda: tmp_path)
    with pytest.raises(SystemExit):
        cli._parser().parse_args(["pi-probe"])
    assert cli.main(["history-rebuild"]) == 0
