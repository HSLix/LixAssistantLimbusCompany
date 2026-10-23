"""覆盖四页 GUI、共享活动互斥、截图原图保存、Runner 持久选择和凭据边界。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_developer_gui.py
"""

import json
import time
from pathlib import Path

import pytest

from lalc.application import StartError
from test_component_repair import host_for


def test_activity_blocks_runner_capture_rebuild_publish_and_clears_on_failure(tmp_path):
    host, loaded = host_for(tmp_path)
    with host.service.activity("Agent"):
        for operation in (lambda: host.service.start("steps.total", {}), host.capture,
                          lambda: host.initialize(loaded.manifest_id, replace=True), host.publish):
            with pytest.raises(StartError):
                operation()
    assert host.service.state["activity"] is None
    with pytest.raises(ValueError):
        with host.service.activity("Capture"):
            raise ValueError("failed")
    assert host.service.state["activity"] is None


def test_capture_preview_saves_exact_original_without_recapture(tmp_path):
    from lalc.assets import AssetLibrary
    host, _ = host_for(tmp_path)
    pixels = bytes([0, 0, 255, 255, 0, 255, 0, 255, 255, 0, 0, 255, 20, 30, 40, 255])
    size = (2, 2)
    region = {"x": 1, "y": 0, "width": 1, "height": 2}
    content, _ = AssetLibrary.crop_content(pixels, size, region)
    host.preview = pixels, size, 8
    snapshot = host.preview
    host.preview = bytes(len(pixels)), size, 9
    assert not host.service.asset_library.root.exists()
    saved = host.save_crop("ui/preview", region, ["zh", "zh"], preview=snapshot)
    assert Path(saved["image_path"]).read_bytes() == content
    assert saved["tags"] == ["zh", "zh"]
    assert saved["observation"] == 8


def test_runner_selection_independent_and_invalid_not_fallback(tmp_path):
    host, loaded = host_for(tmp_path)
    host.select_runner(loaded.manifest_id)
    assert host.runner_selection() == loaded.manifest_id
    original = host.metadata.read_bytes()
    (host.manager.manifests_dir / "default.json").unlink()
    assert host.runner_selection() == loaded.manifest_id
    with pytest.raises(ValueError):
        host.select_runner("missing")
    assert host.runner_selection() == loaded.manifest_id
    assert host.metadata.read_bytes() == original
    (host.manager.manifests_dir / f"{loaded.manifest_id}.json").unlink()
    with pytest.raises(StartError):
        host.service.start("steps.total", {"values": []}, manifest_id=host.runner_selection())
    assert host.service.state["phase"] == "idle"


def test_gui_blank_secret_preserves_and_explicit_clear_removes_reference(tmp_path, monkeypatch):
    import lalc.agent_settings as settings
    from lalc.runtime import atomic_write_json
    monkeypatch.setattr(settings.sys, "platform", "darwin")
    atomic_write_json(tmp_path / "agent-settings.json", {"secret_name": "existing"})
    saved = settings.save_settings(tmp_path, {"model": "test"})
    assert saved["secret_name"] == "existing"
    saved = settings.save_settings(tmp_path, {}, clear=True)
    assert saved["secret_name"] is None
    assert "test-secret" not in (tmp_path / "agent-settings.json").read_text()


@pytest.fixture
def gui(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from lalc.gui import MainWindow
    host, _ = host_for(tmp_path)
    monkeypatch.chdir(tmp_path)
    app = QApplication.instance() or QApplication([])
    window = MainWindow(host.service)
    yield app, window
    window.close()
    app.processEvents()


def wait_jobs(app, window):
    until = time.monotonic() + 10
    while window.jobs and time.monotonic() < until:
        app.processEvents()
        time.sleep(.005)
    assert not window.jobs
    app.processEvents()


def test_four_pages_scaled_crop_and_no_implicit_selection(gui):
    from PySide6.QtCore import QPointF
    app, window = gui
    assert [window.tabs.tabText(i) for i in range(4)] == ["Capture", "Runner", "Agent Settings", "Agent Repair"]
    assert window.repair_page.files.selectedItems() == []
    view = window.capture_page.view
    view.resize(400, 200)
    view.set_image(bytes(200 * 100 * 4), (200, 100))
    assert view.pixel(QPointF(100, 50)) == (50, 25)
    window.host.new_conversation()
    conversation = window.host.conversation
    (window.host.candidate / "manifest.json").write_text("invalid")
    window.repair_page.new()
    assert window.host.conversation is not conversation
    assert (window.host.candidate / "manifest.json").read_text() == "invalid"


def test_async_operation_and_host_busy_state(gui):
    import threading
    app, window = gui
    entered, release = threading.Event(), threading.Event()
    def operation():
        with window.service.activity("Agent"):
            entered.set()
            release.wait(3)
        return "done"
    results = []
    window.launch(operation, results.append)
    assert entered.wait(1)
    assert not window.start_button.isEnabled()
    assert not window.capture_page.capture_button.isEnabled()
    assert not window.repair_page.files.isEnabled()
    release.set()
    wait_jobs(app, window)
    assert results == ["done"]
    assert window.start_button.isEnabled()


def test_coordinate_monitor_does_not_focus_and_stops_until_refresh(tmp_path):
    host, _ = host_for(tmp_path)
    class Platform:
        def __init__(self):
            self.minimized = False
        def find_windows(self):
            return [4]
        def window_info(self, hwnd):
            return {"valid": True, "visible": True, "minimized": self.minimized,
                    "width": 100, "height": 50, "foreground": False, "process_id": 7}
        def cursor_position(self, hwnd):
            return {"x": -1, "y": 20, "inside": False}
        def focus(self, hwnd):
            pytest.fail("Passive monitor stole focus")
    platform = Platform()
    host.service.window_platform = platform
    assert not host.refresh_coordinates()["inside"]
    platform.minimized = True
    with pytest.raises(Exception):
        host.coordinates()
    platform.minimized = False
    with pytest.raises(Exception, match="手动刷新"):
        host.coordinates()
    assert host.refresh_coordinates()["x"] == -1


def test_runner_four_entry_modes_use_shared_service_and_freeze_inputs(gui, monkeypatch):
    app, window = gui
    calls = []
    monkeypatch.setattr(window.service, "start", lambda name, inputs, **kwargs: calls.append((name, inputs, kwargs)))
    monkeypatch.setattr(window.service, "start_plan", lambda path, **kwargs: calls.append((path, kwargs)))
    for role in ("task_workflow", "subworkflow", "step"):
        window.runner_role.setCurrentIndex(window.runner_role.findData(role))
        window.entry.setText("example." + role)
        window.inputs.setPlainText("")
        operation = window._start_request()
        window.entry.setText("changed after request")
        operation()
        assert calls[-1] == ("example." + role, {}, {"manifest_id": None})
    window.inputs.setPlainText("[]")
    with pytest.raises(ValueError):
        window._start_request()
    window.runner_role.setCurrentIndex(window.runner_role.findData("automation_plan"))
    window.plan_path.setText("existing-plan.json")
    window._start_request()()
    assert calls[-1] == (Path("existing-plan.json"), {"manifest_id": None})


def test_closing_cancels_then_waits_for_actual_cleanup(gui, monkeypatch):
    import asyncio
    import threading
    from PySide6.QtWidgets import QMessageBox
    app, window = gui
    entered, cleaned = threading.Event(), threading.Event()
    async def operation():
        with window.service.activity("Agent"):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                await asyncio.sleep(.05)
                cleaned.set()
    window.launch(operation)
    assert entered.wait(1)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.No)
    assert not window.close()
    assert not window.closing and not cleaned.is_set()
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    assert not window.close()
    assert window.closing
    wait_jobs(app, window)
    assert cleaned.is_set()
    assert window.service.state["activity"] is None
    window._finish_close()


def test_rebuild_log_creation_failure_preserves_draft_and_conversation(tmp_path, monkeypatch):
    host, loaded = host_for(tmp_path)
    previous = host.conversation
    source = host.candidate / "steps.total.py"
    source.write_text("keep me")
    metadata = host.metadata.read_bytes()
    def fail(*args):
        raise OSError("cannot save new conversation")
    monkeypatch.setattr("lalc.component_repair.RepairConversation", fail)
    with pytest.raises(OSError):
        host.initialize(loaded.manifest_id, replace=True)
    assert host.conversation is previous
    assert source.read_text() == "keep me"
    assert host.metadata.read_bytes() == metadata


def test_gui_pi_version_warning_stays_visible_after_progress_events(gui):
    app, window = gui
    page = window.repair_page
    message = "pi 版本不匹配：已验证 0.86.1，实际 1.4.0；继续启动，但兼容性尚未验证。"
    page.show_event({"event": {"type": "pi_version_warning", "message": message}})
    page.show_event({"event": {"type": "lalc_request", "requests": 1}})
    assert "WARNING: " + message in page.chat.toPlainText()
