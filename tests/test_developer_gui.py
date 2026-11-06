"""覆盖 Developer GUI、OCR 框选、共享活动互斥、截图保存和凭据边界。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_developer_gui.py
"""

import json
import time
from pathlib import Path

import pytest

from lalc.agent_log import read_json

from lalc.application import StartError
from test_agent_repair import host_for


def test_activity_blocks_runner_capture_rebuild_publish_and_clears_on_failure(tmp_path):
    host, loaded = host_for(tmp_path)
    with host.service.activity("Agent"):
        for operation in (lambda: host.service.start("steps.total", {}), host.capture,
                          lambda: host.recognize_preview((bytes(16), (2, 2), 1)),
                          lambda: host.initialize(loaded.manifest_id, replace=True), host.publish):
            with pytest.raises(StartError):
                operation()
    assert host.service.state["activity"] is None
    with pytest.raises(ValueError):
        with host.service.activity("Capture"):
            raise ValueError("failed")
    assert host.service.state["activity"] is None


def test_trial_modal_blocks_main_window_without_topmost_and_closes_on_result(gui, monkeypatch):
    from PySide6.QtCore import Qt
    from lalc.gui import ErrorDialog
    app, window = gui
    calls = []
    for name in ("pause", "resume", "stop"):
        monkeypatch.setattr(window.service, name, lambda *_, name=name: calls.append(name))
    monkeypatch.setattr(ErrorDialog, "open", lambda self: pytest.fail("Trial must return errors to Agent"))
    window.show()
    state = {**window.service.state, "phase": "running", "run_id": 1, "activity": "Agent",
             "entry": {"developer_trial": True}, "trace": [{"sequence": 1, "event": "run_started"}]}
    window.render_state(state)
    app.processEvents()
    dialog = window.trial_dialog
    assert dialog.windowModality() == Qt.WindowModality.WindowModal
    assert dialog.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    assert not dialog.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert app.activeModalWidget() is dialog
    assert "run_started" in dialog.logs.toPlainText()
    dialog.pause.click()
    state["paused"] = True
    window.render_state(state)
    # 按钮读取真实服务状态，而不是界面文字。
    monkeypatch.setattr(window.service, "_state", {**window.service._state, "paused": True})
    dialog.pause.click()
    dialog.stop.click()
    assert calls == ["pause", "resume", "stop"]
    dialog.reject()
    assert not dialog.close() and dialog.isVisible()
    window.render_state({**state, "phase": "finished", "paused": False,
                         "result": {"status": "failure", "failure_code": "execution_failed"}})
    assert window.trial_dialog is None and not dialog.isVisible()


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


def test_removed_runner_preferences_are_ignored(gui):
    app, window = gui
    preferences = window.service.data_root / 'developer-settings.json'
    preferences.write_text('old invalid settings')
    window.repair_page.new()
    assert not hasattr(window, 'runner_manifest')
    assert not hasattr(window, 'trial_button')
    assert preferences.read_text() == 'old invalid settings'


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
    from PySide6.QtWidgets import QApplication, QDialog
    from lalc.gui import MainWindow
    host, _ = host_for(tmp_path)
    monkeypatch.chdir(tmp_path)
    app = QApplication.instance() or QApplication([])
    window = MainWindow(host.service)
    from lalc.developer_session import DeveloperSession
    session = DeveloperSession.create(host.service, host.manager.default_manifest_id(), entry='gui')
    session.host.secrets = window.host.secrets
    session.conversation()
    window.repair_page.activate_session(session)
    yield app, window
    # 隐藏主窗口不会关闭独立错误弹窗，避免模态状态污染后续反馈测试。
    for dialog in window.findChildren(QDialog):
        dialog.close()
    window.close()
    app.processEvents()


def wait_jobs(app, window):
    until = time.monotonic() + 10
    while window.jobs and time.monotonic() < until:
        app.processEvents()
        time.sleep(.005)
    assert not window.jobs
    app.processEvents()


def test_ocr_capture_selection_replacement_and_failure(gui, monkeypatch):
    """真实后台任务使用替身 OCR；验证原始像素、框选、空结果及错误清理。"""
    from types import SimpleNamespace
    from PySide6.QtCore import QPointF, Qt
    from lalc.gui import ErrorDialog
    from lalc.ocr import OcrService
    from lalc.developer_gui import OcrView
    app, window = gui
    page = window.ocr_page
    pixels = bytes([1, 2, 3, 255]) * 200 * 100
    captures = []
    class Session:
        def __init__(self, *_):
            self.image, self.size, self.observation = pixels, (200, 100), 1
        def capture(self):
            captures.append(True)
    monkeypatch.setattr('lalc.developer.FocusedAutomationSession', Session)
    window.host.preview = original = (bytes(16), (2, 2), 7)
    calls = []
    item = {"text": "<文字>&", "box": {"x": 50, "y": 20, "width": 30, "height": 10}}
    def recognize(self, image, *, region, checkpoint):
        checkpoint()
        assert image.shape == (100, 200, 3)
        assert image[0, 0].tolist() == [1, 2, 3]
        calls.append(region)
        return {"items": [item] if region is None else []}
    monkeypatch.setattr(OcrService, 'recognize', recognize)
    page.capture()
    assert not page.capture_button.isEnabled() and not page.view.isEnabled()
    wait_jobs(app, window)
    assert window.host.preview is original
    assert page.results.toPlainText() == '1. <文字>&'
    assert page.view.items == [item]
    assert page.full_button.isEnabled()
    # 通过鼠标处理路径验证等比缩放、释放时识别和区域偏移传递。
    view = page.view
    view.resize(400, 200)
    def event(x, y):
        return SimpleNamespace(button=lambda: Qt.MouseButton.LeftButton, position=lambda: QPointF(x, y))
    view.mousePressEvent(event(100, 40))
    assert calls == [None]
    view.mouseMoveEvent(event(200, 100))
    assert calls == [None]
    view.mouseReleaseEvent(event(200, 100))
    wait_jobs(app, window)
    assert calls[-1] == {"x": 50, "y": 20, "width": 50, "height": 30}
    assert not view.items and page.results.toPlainText()
    page.full_button.click()
    wait_jobs(app, window)
    assert calls[-1] is None and view.region is None and view.items == [item]
    assert len(captures) == 1
    # 标注只改变绘制结果，不修改原图像素。
    plain = OcrView()
    plain.resize(view.size())
    plain.set_image(pixels, (200, 100))
    assert view.grab().toImage() != plain.grab().toImage()
    assert view.image == plain.image
    errors = []
    monkeypatch.setattr(ErrorDialog, 'open', lambda dialog: errors.append(dialog.details.toPlainText()))
    def fail(*_, **__):
        raise RuntimeError('OCR test failure')
    monkeypatch.setattr(OcrService, 'recognize', fail)
    page.recognize()
    wait_jobs(app, window)
    assert not view.items and not page.results.toPlainText()
    assert errors and 'OCR test failure' in errors[-1]
    assert page.capture_button.isEnabled() and view.isEnabled()
    plain.close()


def test_required_pages_ocr_after_capture_scaled_crop_and_no_implicit_selection(gui):
    from PySide6.QtCore import QPointF
    app, window = gui
    pages = [window.pages.widget(i).objectName() for i in range(window.pages.count())]
    assert {"developer-capture", "developer-ocr", "developer-settings", "developer-workbench"} <= set(pages)
    assert pages.index("developer-ocr") == pages.index("developer-capture") + 1
    assert not hasattr(window.repair_page, "files")
    assert not hasattr(window.repair_page, "diff")
    view = window.capture_page.view
    view.resize(400, 200)
    view.set_image(bytes(200 * 100 * 4), (200, 100))
    assert view.pixel(QPointF(100, 50)) == (50, 25)
    session = window.repair_page.session
    (session.host.candidate / "manifest.json").write_text("invalid")
    window.repair_page.new()
    assert window.repair_page.session is None
    assert (session.host.candidate / "manifest.json").read_text() == "invalid"


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
    assert not window.repair_page.new_button.isEnabled()
    assert not window.capture_page.capture_button.isEnabled()
    assert not window.repair_page.baseline.isEnabled()
    release.set()
    wait_jobs(app, window)
    assert results == ["done"]
    assert window.repair_page.new_button.isEnabled()


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


def test_no_manual_run_entry_but_agent_trial_modal_is_retained(gui):
    app, window = gui
    assert not hasattr(window, 'start_selected_plan')
    assert not hasattr(window, 'runner_manifest')
    window.render_state({**window.service.state, 'phase': 'running', 'run_id': 1,
                         'entry': {'developer_trial': True}, 'trace': []})
    assert window.trial_dialog is not None
    window.render_state({**window.service.state, 'phase': 'finished'})
    assert window.trial_dialog is None


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
        image = view.grab().toImage()
        ratio = image.devicePixelRatio()
        assert image.pixelColor(round(80 * ratio), round(40 * ratio)) != QColor(80, 50, 30)

        QTest.mousePress(view, Qt.MouseButton.LeftButton, pos=QPoint(360, 160))
        assert view.region is None and selections[-1] == {}
        assert view.grab().toImage().pixelColor(round(80 * ratio), round(40 * ratio)) == QColor(80, 50, 30)
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
    assert page.provider.currentData() == "llama.cpp" and page.provider.count() == 2
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
    page.set_api_key()
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
    page.url.setText("http://host/another/api")
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
    page.set_api_key()
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
    window.switchTo(window.settings_view)
    window.settings_page.set_api_key()
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


@pytest.mark.parametrize("phase", ["before_send", "after_send", "restored"])
@pytest.mark.parametrize("valid", [True, False])
def test_manual_validate_displays_once_and_persists_context(gui, monkeypatch, phase, valid):
    app, window = gui
    page = window.repair_page
    chat = page.host.conversation
    if phase in {"after_send", "restored"}:
        chat.log.on_event = window.operation_event.emit
    if phase == "restored":
        page.session.conversation()
        page.activate_session(page.session)
        chat = page.host.conversation
    if not valid:
        (page.host.candidate / "manifest.json").write_text("broken json")
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
    assert read_json(chat.log.path / "context.json") == chat.history
    assert len(chat.history) == 1
    if not valid:
        assert page.diagnostics.errors.currentData()["errors"] == result["errors"]


def test_manual_validate_without_conversation_does_not_create_one(gui):
    app, window = gui
    window.repair_page.new()
    assert window.host.conversation is None
    window.repair_page.validate()
    wait_jobs(app, window)
    assert window.host.conversation is None
    assert not window.repair_page.chat.entries


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


def test_settings_provider_options_and_memory_keys_are_independent(gui, monkeypatch):
    monkeypatch.setattr('lalc.developer_gui.sys.platform', 'darwin')
    app, window = gui
    page = window.settings_page
    assert page.deepseek_options.isHidden()
    page.url.setText('http://local/custom/api')
    page.model.setText('local-model')
    page.save(secret='local-temporary-key')
    wait_jobs(app, window)
    assert window.host.secret == 'local-temporary-key'
    page.provider.setCurrentIndex(page.provider.findData('deepseek'))
    assert not page.deepseek_options.isHidden()
    assert page.model.text() == 'deepseek-flash' and page.model.isReadOnly()
    assert page.url.text() == 'https://api.deepseek.com'
    assert page.thinking.isChecked() and page.effort.currentData() == 'high'
    assert page.key is None and page.secret_state.text() == 'API Key：未设置'
    page.thinking.setChecked(False)
    assert not page.effort.isEnabled()
    page.save(secret='cloud-temporary-key')
    wait_jobs(app, window)
    assert window.host.secret == 'cloud-temporary-key'
    saved = json.loads((window.service.data_root / 'agent-settings.json').read_text())
    assert saved['thinking'] is False and saved['reasoning_effort'] == 'high'
    assert 'cloud-temporary-key' not in json.dumps(saved)
    assert 'local-temporary-key' not in json.dumps(saved)
    page.provider.setCurrentIndex(page.provider.findData('llama.cpp'))
    assert page.deepseek_options.isHidden() and not page.model.isReadOnly()
    assert page.url.text() == 'http://local/custom/api' and page.model.text() == 'local-model'
    assert page.secret_state.text() == 'API Key：已设置'
    page.save(clear=True)
    wait_jobs(app, window)
    assert 'llama.cpp' not in window.host.secrets
    assert window.host.secrets['deepseek'] == 'cloud-temporary-key'
    page.provider.setCurrentIndex(page.provider.findData('deepseek'))
    page.thinking.setChecked(True)
    page.effort.setCurrentIndex(page.effort.findData('max'))
    page.save()
    wait_jobs(app, window)
    page.reload()
    assert page.thinking.isChecked() and page.effort.currentData() == 'max'


@pytest.mark.parametrize("can_open", [True, False])
def test_more_menu_opens_external_pages_folder(gui, monkeypatch, can_open):
    from PySide6.QtGui import QDesktopServices
    from lalc.gui import ErrorDialog
    _, window = gui
    page = window.repair_page
    directory = window.service.data_root / "pages"
    assert not directory.exists()
    assert page.workspace_action.isEnabled()
    assert page.pages_action.isEnabled()
    opened, errors = [], []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toLocalFile()) or can_open)
    monkeypatch.setattr(ErrorDialog, "open", lambda dialog: errors.append(dialog.details.toPlainText()))
    page.pages_action.trigger()
    assert directory.is_dir()
    assert opened == [str(directory.absolute())]
    assert bool(errors) != can_open


@pytest.mark.parametrize("case", ["missing", "existing", "system_refused", "path_is_file"])
def test_capture_creates_asset_directory_before_opening(gui, monkeypatch, case):
    """缺失目录自动创建，已有内容保留，创建与系统打开失败仍显示错误。"""
    from PySide6.QtGui import QDesktopServices
    from lalc.gui import ErrorDialog
    _, window = gui
    directory = window.service.asset_library.root
    assert not directory.exists()
    if case == "existing":
        directory.mkdir(parents=True)
        (directory / "keep.txt").write_text("keep")
    elif case == "path_is_file":
        directory.parent.mkdir(parents=True, exist_ok=True)
        directory.write_text("keep")
    opened, errors = [], []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toLocalFile()) or case != "system_refused")
    monkeypatch.setattr(ErrorDialog, "open", lambda dialog: errors.append(dialog.details.toPlainText()))
    window.capture_page.open_assets()
    assert bool(errors) == (case in {"system_refused", "path_is_file"})
    if case == "path_is_file":
        assert directory.read_text() == "keep" and not opened
    else:
        assert directory.is_dir() and opened == [str(directory.absolute())]
        if case == "existing":
            assert (directory / "keep.txt").read_text() == "keep"
