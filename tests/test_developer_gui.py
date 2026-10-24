"""覆盖四页 GUI、共享活动互斥、截图原图保存、Runner 持久选择和凭据边界。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_developer_gui.py
"""

import json
import time
from pathlib import Path

import pytest

from lalc.application import StartError
from test_agent_repair import host_for


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
    assert not hasattr(window.repair_page, "files")
    assert not hasattr(window.repair_page, "diff")
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
    assert not window.repair_page.baseline.isEnabled()
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
    monkeypatch.setattr("lalc.agent_repair.RepairConversation", fail)
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


def test_crop_reselection_clears_old_outline_and_keeps_new_region(gui):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QColor
    from PySide6.QtTest import QTest
    from lalc.developer_gui import CropView
    app, window = gui
    view = CropView()
    selections = []
    view.selected.connect(selections.append)
    view.resize(400, 200)
    view.set_image(bytes([30, 50, 80, 255]) * 100 * 50, (100, 50))
    view.show()
    app.processEvents()
    try:
        QTest.mousePress(view, Qt.MouseButton.LeftButton, pos=QPoint(80, 40))
        QTest.mouseMove(view, QPoint(200, 120))
        QTest.mouseRelease(view, Qt.MouseButton.LeftButton, pos=QPoint(200, 120))
        assert view.region == {"x": 20, "y": 10, "width": 30, "height": 20}
        assert view.grab().toImage().pixelColor(80, 40) != QColor(80, 50, 30)

        QTest.mousePress(view, Qt.MouseButton.LeftButton, pos=QPoint(360, 160))
        assert view.region is None and selections[-1] == {}
        assert view.grab().toImage().pixelColor(80, 40) == QColor(80, 50, 30)
        QTest.mouseMove(view, QPoint(240, 80))
        QTest.mouseRelease(view, Qt.MouseButton.LeftButton, pos=QPoint(240, 80))
        expected = {"x": 60, "y": 20, "width": 30, "height": 20}
        assert view.region == selections[-1] == expected
        QTest.mouseMove(view, QPoint(20, 20))
        assert view.region == expected

        QTest.mouseClick(view, Qt.MouseButton.LeftButton, pos=QPoint(20, 20))
        assert view.region is None and selections[-1] == {}
    finally:
        view.close()


@pytest.mark.parametrize(("text", "expected"), [
    ("", []), ("[]", []), ("en, default, en", ["en", "default", "en"]),
    ("[en, default]", ["en", "default"]),
    ('["带,逗号", "中文", "中文"]', ["带,逗号", "中文", "中文"]),
])
def test_capture_tags_input(text, expected):
    from lalc.developer_gui import capture_tags
    assert capture_tags(text) == expected


@pytest.mark.parametrize("text", ["en,,default", "en,", "[en", '["en", default]', "[en, ]"])
def test_capture_tags_invalid_input_has_readable_error(text):
    from lalc.developer_gui import capture_tags
    with pytest.raises(ValueError, match="标签"):
        capture_tags(text)


def test_capture_save_accepts_unquoted_tags_and_preserves_preview(gui, monkeypatch):
    from PySide6.QtWidgets import QDialog
    from lalc.assets import AssetLibrary
    app, window = gui
    page = window.capture_page
    pixels, size = bytes([0, 0, 255, 255]) * 4, (2, 2)
    window.host.preview = pixels, size, 7
    page.view.set_image(pixels, size)
    region = {"x": 0, "y": 0, "width": 1, "height": 2}
    page.view.region = region
    page.name.setText("ui/capture-test")
    page.tags.setText("[en, default, en]")
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    page.save()
    wait_jobs(app, window)
    directory = window.service.asset_library.root / "ui/capture-test"
    images = list(directory.glob("*.png"))
    assert len(images) == 1
    assert images[0].read_bytes() == AssetLibrary.crop_content(pixels, size, region)[0]
    assert json.loads((directory / "asset-tag.json").read_text()) == {
        images[0].stem: ["en", "default", "en"]}
    assert "已保存" in page.region_label.text()


def test_settings_checks_unsaved_form_and_invalidates_stale_result(gui, monkeypatch):
    import threading
    app, window = gui
    page = window.settings_page
    assert page.provider.currentData() == "llama.cpp" and page.provider.count() == 1
    assert page.output_limit.count() == 1
    assert page.output_limit.currentText() == "使用服务端默认值"
    assert page.values()["output_limit"] == "server_default"
    entered, release = threading.Event(), threading.Event()
    calls = []
    def models(base, key):
        calls.append((base, key))
        entered.set()
        assert release.wait(3)
        return [{"id": "Gemma4", "status": {"value": "unloaded"}}]
    monkeypatch.setattr("lalc.pi_probe._models", models)
    page.url.setText("http://host/custom/api")
    page.model.setText("Gemma4")
    page.key.setText("gui-secret")
    page.check(True)
    assert entered.wait(1)
    page.model.setText("changed")
    release.set()
    wait_jobs(app, window)
    assert calls == [("http://host/custom/api", "gui-secret")]
    assert "设置已变更" in page.check_status.text()
    assert not (window.service.data_root / "agent-settings.json").exists()
    page.model.setText("Gemma4")
    page.check(True)
    wait_jobs(app, window)
    assert "未加载" in page.check_status.text()
    assert page.diagnostics.path.is_dir()
    assert "gui-secret" not in (page.diagnostics.path / "result.json").read_text()
    page.key.setText("another-secret")
    assert "设置已变更" in page.check_status.text()


def test_settings_error_can_reopen_copy_and_open_logs(gui, monkeypatch):
    import io
    from urllib.error import HTTPError
    from PySide6.QtGui import QDesktopServices
    from lalc.gui import ErrorDialog
    app, window = gui
    page = window.settings_page
    def fail(request, **kwargs):
        raise HTTPError(request.full_url, 502, "bad gateway", {}, io.BytesIO(b"upstream gui-secret"))
    monkeypatch.setattr("lalc.pi_probe.urlopen", fail)
    page.key.setText("gui-secret")
    page.check(False)
    wait_jobs(app, window)
    assert "错误" in page.check_status.text() and "502" in page.check_status.text()
    dialogs = page.diagnostics.findChildren(ErrorDialog)
    assert dialogs and "upstream" in dialogs[-1].details.toPlainText()
    dialogs[-1].close()
    app.processEvents()
    page.diagnostics.show_error()
    page.diagnostics.copy_error()
    text = app.clipboard().text()
    assert "gui-secret" not in text and "HTTPError" in text and "502" in text
    assert "\nTraceback" in text
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toLocalFile()) or True)
    page.diagnostics.open_logs()
    assert opened == [str(page.diagnostics.path.absolute())]


def test_repair_error_is_not_agent_reply_and_normal_answer_stays_reply(gui, monkeypatch):
    app, window = gui
    page = window.repair_page
    monkeypatch.setattr(page, "show_diff", lambda: None)
    page.answered({"reason": "error", "requests": 0, "error": "failed",
                   "diagnostics": {"stage": "service_check", "message": "failed", "traceback": "cause"}})
    assert "Agent" not in page.chat.toPlainText() and "错误：failed" in page.status.text()
    page.diagnostics.copy_error()
    assert "cause" in app.clipboard().text()
    page.answered({"reason": "answered", "requests": 2, "answer": {"message": "信息不足"}})
    assert "Agent" in page.chat.toPlainText() and "信息不足" in page.chat.toPlainText()


def test_interaction_error_uses_redacted_details_and_keeps_log_entry(gui, caplog):
    app, window = gui
    window.tabs.setCurrentWidget(window.settings_page)
    window.settings_page.key.setText("gui-secret")
    def fail():
        raise ValueError("gui-secret failed")
    window._interact(fail)
    panel = window.settings_page.diagnostics
    assert panel.errors.count() == 1
    assert "gui-secret" not in caplog.text
    assert panel.path.is_dir() and (panel.path / "events.jsonl").exists()
    panel.copy_error()
    assert "gui-secret" not in app.clipboard().text()


@pytest.mark.parametrize("phase", ["before_send", "after_send", "new_conversation"])
@pytest.mark.parametrize("valid", [True, False])
def test_manual_validate_displays_once_and_persists_context(gui, monkeypatch, phase, valid):
    app, window = gui
    page = window.repair_page
    chat = window.host.new_conversation()
    if phase in {"after_send", "new_conversation"}:
        chat.log.on_event = window.operation_event.emit
    if phase == "new_conversation":
        page.new()
        chat = window.host.conversation
    if not valid:
        (window.host.candidate / "manifest.json").write_text("broken json")
    opened = []
    monkeypatch.setattr(page.diagnostics, "show_error", lambda: opened.append(True))
    page.validate()
    wait_jobs(app, window)
    entries = page.chat.entries
    assert len(entries) == 1 and entries[0]["name"] == "validate"
    result = entries[0]["events"]["validation"]
    assert len(page.chat.tools) == 1
    assert result["ok"] is valid
    assert page.diagnostics.errors.count() == (0 if valid else 1)
    assert len(opened) == (0 if valid else 1)
    assert json.loads((chat.log.path / "context.json").read_text()) == chat.history
    assert len(chat.history) == 1
    if not valid:
        assert page.diagnostics.errors.currentData()["errors"] == result["errors"]


def test_manual_validate_without_conversation_does_not_create_one(gui):
    app, window = gui
    assert window.host.conversation is None
    window.repair_page.validate()
    wait_jobs(app, window)
    assert window.host.conversation is None
    assert len(window.repair_page.chat.entries) == 1
    assert window.repair_page.chat.entries[0]["name"] == "validate"


def test_request_progress_keeps_round_and_limit_through_tool_events_and_resets(gui):
    app, window = gui
    page = window.repair_page
    window.host.new_conversation()
    page.show_event({"round": 2, "event": {"type": "lalc_request", "requests": 7, "request_limit": 20}})
    assert page.request_progress.text() == "对话轮次：2；本轮模型请求：7/20"
    page.show_event({"round": 2, "event": {"type": "tool_execution_start", "toolName": "read"}})
    assert page.request_progress.text().endswith("7/20")
    assert "read" in page.status.text()
    page.new()
    assert page.request_progress.text() == "对话轮次：尚未开始；本轮模型请求：0"
    page.show_event({"round": 1, "event": {"type": "lalc_request", "requests": 1, "request_limit": 3}})
    assert page.request_progress.text() == "对话轮次：1；本轮模型请求：1/3"
