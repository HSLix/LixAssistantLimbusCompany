"""覆盖运行状态增量、有界日志、通知合并及跨 Run 的完整证据保留。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_run_ui_updates.py
"""

import json
import threading

from lalc.application import ApplicationService
from test_workflow import _publish, _finished


def test_snapshot_and_notifications_never_copy_historical_trace(tmp_path):
    service = ApplicationService(tmp_path)
    service._state["run_id"] = 1
    service._trace_path = tmp_path / "traces" / "1.jsonl"
    notifications = []
    service.on_change = lambda: notifications.append(True)
    for i in range(10350):
        service._emit("component_log" if i < 350 else "target_window_checked",
                      {"message": str(i)})
    assert len(notifications) == 10350
    assert len(service._live_logs) == 300
    saved = [json.loads(line) for line in service._trace_path.read_text(encoding="utf-8").splitlines()]
    assert saved == service.state["trace"]

    class NoCopyTrace(list):
        """禁止快照悄悄恢复为全历史复制，也禁止从头扫描历史。"""
        def __deepcopy__(self, memo):
            raise AssertionError("UI must not copy full Trace")

        def __iter__(self):
            raise AssertionError("UI must not scan full Trace")

    service._state["trace"] = NoCopyTrace(saved)
    with service._condition:
        service._changed_locked()
    state = service.ui_snapshot()
    assert "trace" not in service.status and "trace" not in state
    assert [r["sequence"] for r in state["log_records"]] == list(range(51, 351))
    assert state["logs_trimmed"] and state["last_sequence"] == 10350
    state["log_records"][0]["message"] = "caller-only"
    assert service.ui_snapshot()["log_records"][0]["message"] == "50"
    assert service.ui_snapshot(1, 10350)["log_records"] == []
    service._emit("component_log", {"message": "next"})
    assert [r["sequence"] for r in service.ui_snapshot(1, 10350)["log_records"]] == [10351]


def test_new_run_resets_live_window_and_full_state_remains_available(tmp_path):
    service = ApplicationService(tmp_path, manifest_manager=_publish(tmp_path))
    first = service.start("tasks.rotate_teams", {"teams": ["one"], "runs": 0})
    _finished(service, first)
    old = service.ui_snapshot()
    service._thread.join()
    second = service.start("tasks.rotate_teams", {"teams": ["two"], "runs": 0})
    completed = _finished(service, second)
    snapshot = service.ui_snapshot(first, old["last_sequence"])
    assert snapshot["run_id"] == second
    assert snapshot["log_records"][0]["event"] == "run_started"
    assert snapshot["log_records"][-1]["event"] == "run_finished"
    assert all(r["run_id"] == second for r in snapshot["log_records"])
    assert not snapshot["logs_trimmed"]
    assert snapshot["result"] == completed["result"]
    assert len(completed["trace"]) > len(snapshot["log_records"])
    service.shutdown()


def test_bridge_coalesces_worker_burst_and_keeps_changes_during_read(tmp_path):
    from PySide6.QtWidgets import QApplication
    from lalc.gui import StateBridge
    app = QApplication.instance() or QApplication([])
    service = ApplicationService(tmp_path)
    received = []
    bridge = StateBridge(service, received.append)
    bridge.timer.stop()
    try:
        worker = threading.Thread(target=lambda: [service.on_change() for _ in range(20000)])
        worker.start()
        worker.join()
        assert received == []
        bridge.flush()
        assert len(received) == 1 and "trace" not in received[0]
        bridge.flush()
        assert len(received) == 1
        original = service.ui_snapshot
        def changed_during_read(*args):
            service.on_change()
            return original(*args)
        service.ui_snapshot = changed_during_read
        service.on_change()
        bridge.flush()
        assert bridge.dirty.is_set()
        service.ui_snapshot = original
        bridge.flush()
        assert not bridge.dirty.is_set() and len(received) == 3
        from PySide6.QtTest import QTest
        service.on_change()
        bridge.timer.start()
        QTest.qWait(150)
        bridge.timer.stop()
        assert len(received) == 4
    finally:
        bridge.close()
        assert service.on_change is None and not bridge.timer.isActive()
        bridge.flush()
        bridge.close()
        app.processEvents()
