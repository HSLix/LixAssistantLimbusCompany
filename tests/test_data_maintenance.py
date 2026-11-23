"""覆盖数据盘点、使用摘要、删除保护和同盘回滚。

从项目根目录运行：.venv/bin/python -m pytest -q tests/test_data_maintenance.py
"""

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import uuid

import pytest

from lalc.application import ApplicationService, StartError
from lalc.data_maintenance import DataMaintenance
from lalc.process_lock import ProcessLock
from lalc.run_log_sharing import export_log, import_log
from lalc.runtime import atomic_write_json


def source(root, name):
    content = f"# {name}\n@step\ndef execute(ctx): ...\n".encode()
    digest = hashlib.sha256(content).hexdigest()
    folder = root / "components"
    folder.mkdir(exist_ok=True)
    (folder / f"{digest}.py").write_bytes(content)
    return f"sha256:{digest}"


def version(root, day, **members):
    key = str(uuid.uuid4())
    atomic_write_json(root / "manifests" / f"{key}.json", {
        "schema_version": 2, "manifest_id": key, "published_at": f"2026-11-{day:02}T12:00:00+00:00",
        "components": {name: {"component_id": digest} for name, digest in members.items()},
        "recovery_rules": {},
    })
    return key


def trace(root, key, manifest, components):
    directory = root / "traces"
    directory.mkdir(exist_ok=True)
    stamp = "2026-11-11T12:00:00+00:00"
    records = [
        {"event": "run_started", "base_manifest_id": manifest},
        {"event": "working_manifest_selected", "manifest_id": manifest},
        *({"event": "component_started", "logical_name": name, "component_id": digest, "manifest_id": manifest}
          for name, digest in components),
        {"event": "run_finished", "result": {"status": "success"}},
    ]
    path = directory / f"{key}.jsonl"
    path.write_text("".join(json.dumps({"recorded_at": stamp, "sequence": i, **record}) + "\n"
                            for i, record in enumerate(records, 1)), encoding="utf-8")
    return path


def test_usage_and_imported_identity_survive_local_cleanup(tmp_path):
    data = DataMaintenance(ApplicationService(tmp_path))
    digest = source(tmp_path, "step")
    manifest = version(tmp_path, 10, one=digest)
    trace(tmp_path, 4, manifest, [("one", digest), ("one", digest)])
    evidence = tmp_path / "evidence/4"
    evidence.mkdir(parents=True)
    (evidence / "1.png").write_bytes(b"example")
    state = tmp_path / "runs/4.json"
    ledger = tmp_path / "ledger/4.json"
    session = tmp_path / "developer-sessions/saved/session.json"
    for path in (state, ledger, session):
        atomic_write_json(path, {})
    archive = tmp_path / "log.zip"
    export_log(tmp_path, 4, archive)
    imported = import_log(tmp_path, archive)
    before, _ = data.inventory("components")
    assert before[0]["count"] == 2 and before[0]["last"] == datetime(2026, 11, 11, 12, tzinfo=UTC)
    assert data.inventory("manifests")[0][0]["count"] == 1
    assert {row["key"] for row in data.inventory("logs")[0]} == {4, imported}
    plan = data.preview("logs", [4])
    assert not (tmp_path / "run-usage").exists() and plan.size > 7
    assert data.execute(plan) is None
    assert not state.exists() and not evidence.exists()
    assert ledger.is_file() and session.is_file()
    assert data.inventory("components")[0] == before
    assert data.inventory("manifests")[0][0]["count"] == 1
    assert [row["key"] for row in data.inventory("logs")[0]] == [imported]
    assert data.service._allocate_run_id() == 5
    data.execute(data.preview("logs", [imported]))
    assert data.inventory("logs")[0] == [] and data.inventory("components")[0] == before


def test_cleanup_recalculates_protection_and_only_removes_newly_unreferenced(tmp_path):
    data = DataMaintenance(ApplicationService(tmp_path))
    common, unused, previous, orphan = (source(tmp_path, name) for name in ("shared", "unused", "previous", "orphan"))
    old = version(tmp_path, 1, one=common, two=unused)
    base = version(tmp_path, 2, one=previous)
    latest = version(tmp_path, 3, one=common)
    pointer = tmp_path / "manifests/default.json"
    atomic_write_json(pointer, {"manifest_id": base})
    for key in (base, latest):
        with pytest.raises(ValueError, match="protected"):
            data.preview("manifests", [key])
    plan = data.preview("manifests", [old])
    assert [(path.stem, names) for path, names in plan.sources] == [(unused[7:], ("two",))]
    atomic_write_json(pointer, {"manifest_id": old})
    with pytest.raises(ValueError, match="protected"):
        data.execute(plan)
    atomic_write_json(pointer, {"manifest_id": base})
    new_reference = version(tmp_path, 4, one=unused)
    with pytest.raises(ValueError, match="changed"):
        data.execute(plan)
    (tmp_path / f"manifests/{new_reference}.json").unlink()
    data.execute(plan)
    assert not (tmp_path / f"manifests/{old}.json").exists()
    assert {path.stem for path in (tmp_path / "components").iterdir()} == {common[7:], previous[7:], orphan[7:]}
    assert {row["key"] for row in data.inventory("manifests")[0]} == {base, latest}


def test_invalid_retained_manifest_and_staged_rename_failure(tmp_path, monkeypatch):
    data = DataMaintenance(ApplicationService(tmp_path))
    previous, latest = source(tmp_path, "old"), source(tmp_path, "new")
    old = version(tmp_path, 1, one=previous)
    new = version(tmp_path, 2, one=latest)
    new_path = tmp_path / f"manifests/{new}.json"
    original = new_path.read_text(encoding="utf-8")
    new_path.write_text(original.replace('"components":', '"components": {}, "components":'), encoding="utf-8")
    with pytest.raises(ValueError, match="unreadable"):
        data.preview("manifests", [old])
    new_path.write_text(original, encoding="utf-8")
    plan = data.preview("manifests", [old])
    rename = Path.rename
    def blocked(path, target):
        if path == plan.sources[0][0]:
            raise OSError("simulated file in use")
        return rename(path, target)
    monkeypatch.setattr(Path, "rename", blocked)
    with pytest.raises(OSError, match="file in use"):
        data.execute(plan)
    assert all(path.exists() for path in plan.targets)
    assert not list(tmp_path.glob(".data-cleanup-*"))


def test_no_delete_when_busy_storage_locked_or_trace_corrupt(tmp_path):
    data = DataMaintenance(ApplicationService(tmp_path))
    digest = source(tmp_path, "step")
    manifest = version(tmp_path, 10, one=digest)
    path = trace(tmp_path, 4, manifest, [("one", digest)])
    plan = data.preview("logs", [4])
    with data.manager.store_lock(), pytest.raises(OSError):
        data.execute(plan)
    with ProcessLock("game"), pytest.raises(StartError, match="另一进程"):
        data.execute(plan)
    assert path.exists()
    with path.open("a", encoding="utf-8") as stream:
        stream.write('{"invalid"\n')
    with pytest.raises(ValueError, match="damaged Trace"):
        data.execute(data.preview("logs", [4]))
    assert path.exists() and not (tmp_path / "run-usage").exists()


def test_rollback_failure_keeps_the_only_manifest_copy(tmp_path, monkeypatch):
    data = DataMaintenance(ApplicationService(tmp_path))
    previous, current = source(tmp_path, "previous"), source(tmp_path, "current")
    old = version(tmp_path, 1, one=previous)
    version(tmp_path, 2, one=current)
    plan = data.preview("manifests", [old])
    rename = Path.rename

    def blocked(path, destination):
        if path == plan.sources[0][0] or destination == plan.targets[0]:
            raise OSError("simulated rename failure")
        return rename(path, destination)

    monkeypatch.setattr(Path, "rename", blocked)
    with pytest.raises(OSError, match="Retained data"):
        data.execute(plan)
    (stage,) = tmp_path.glob(".data-cleanup-pending-*")
    assert json.loads((stage / "0").read_text(encoding="utf-8"))["manifest_id"] == old
    assert json.loads((stage / "targets.json").read_text(encoding="utf-8"))["paths"][0].endswith(f"{old}.json")
    with pytest.raises(OSError, match="interrupted cleanup"):
        data.preview("manifests", [old])


def test_asset_inventory_reads_latest_match_without_touching_images(tmp_path):
    data = DataMaintenance(ApplicationService(tmp_path))
    folder = tmp_path / "assets/ui/menu"
    folder.mkdir(parents=True)
    (folder / ("a" * 64 + ".png")).write_bytes(b"inventory counts size only")
    atomic_write_json(tmp_path / "asset-usage.json", {"ui/menu": {"last_used_at": "2026-11-08T06:00:00+00:00"}})
    assert data.inventory("assets") == ([
        {"key": "ui/menu", "count": 1, "size": 26, "last": datetime(2026, 11, 8, 6, tzinfo=UTC)},
    ], 0)
