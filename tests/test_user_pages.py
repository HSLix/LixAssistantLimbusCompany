"""覆盖外置页发现、双向告警、保存快照和共享设置/重载交接。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_user_pages.py
"""

from pathlib import Path
import shutil
import threading

import pytest

from lalc.agent_settings import load_settings, save_settings, save_selection, settings_document, settings_snapshot
from lalc.application import ApplicationService
from lalc.gui import GuiCoordinator, StateBridge
from lalc.lifecycle import ApplicationLifecycle
from lalc.manifest import ManifestManager, plan_task_ids
from lalc.user_pages import UserSettings, discover_pages, task_inputs

EXAMPLE = Path(__file__).resolve().parent / "fixtures/user-pages"
PAGES = EXAMPLE / "pages"


@pytest.fixture
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def owner(tmp_path, app, monkeypatch):
    from lalc.developer import DeveloperHost
    root = tmp_path / "data"
    shutil.copytree(PAGES, root / "pages")
    manager = ManifestManager(root)
    published = manager.publish(EXAMPLE / "manifest.json")
    assert published.ok, published.errors
    assert manager.set_default(published.loaded.manifest_id).ok
    service = ApplicationService(root, manifest_manager=manager)
    coordinator = GuiCoordinator(service, ApplicationLifecycle())
    coordinator.host = DeveloperHost(service, tmp_path / "candidate")
    bridge = StateBridge()
    service.on_change = bridge.changed.emit
    bridge.changed.connect(coordinator.render_state)
    coordinator.open_window()
    yield coordinator
    coordinator.reloading = False
    for window in (coordinator.user, coordinator.developer):
        if window:
            window.setEnabled(True)
            window.settings_page.dirty = False
            window.shutdown()
            window.close()
    app.processEvents()


def test_pages_run_real_plan_with_pure_settings_and_independent_snapshot(owner, app, monkeypatch):
    user = owner.user
    assert user.pages.count() == 4
    assert len(user.business_pages) == 2 and not user.warning_history
    assert list(user.task_rows) == ["sample.loop"]
    enabled, count = user.task_rows["sample.loop"]
    count.setValue(2)
    enabled.setChecked(True)
    pages = {page.page_id: page.widget for page in user.business_pages}
    pages["sample.message"].message.setText("before")
    pages["sample.general"].prefix.setText("prefix:")
    entered, release = threading.Event(), threading.Event()
    def hold():
        entered.set()
        assert release.wait(3)
    monkeypatch.setattr(owner.service, "_start_session", hold)
    try:
        user.start_plan()
        assert entered.wait(1)
        pages["sample.message"].message.setText("after")
        user.page_store.save_task("sample.loop", False, 9)
        user.page_store.save("pages", "sample.message", {"message": "after"})
    finally:
        release.set()
    owner.service.wait_for(lambda state: state["phase"] == "finished")
    owner.service._thread.join()
    result = owner.service.state["result"]
    assert result["status"] == "completed" and result["all_tasks_succeeded"]
    assert len(result["items"]) == 2
    assert all(item["output"] == "prefix:before" for item in result["items"])
    assert UserSettings(owner.service.data_root).value["tasks"]["sample.loop"]["count"] == 9


def test_discovery_isolates_import_create_and_all_conflicting_registrations(tmp_path, app):
    pages = tmp_path / "pages"
    shutil.copytree(PAGES, pages)
    (pages / "bad_import.py").write_text('raise ValueError("import broke")')
    (pages / "bad_create.py").write_text('PAGE_ID="broken"\nPAGE_NAME="broken"\ndef create_page(ctx):\n    raise ValueError("create broke")\n')
    (pages / "duplicate.py").write_text((pages / "loop.py").read_text())
    found, errors = discover_pages(pages, UserSettings(tmp_path))
    assert [page.page_id for page in found] == ["sample.general"]
    assert len(errors) == 4
    assert any("import broke" in error for error in errors)
    assert any("create broke" in error for error in errors)
    assert sum("冲突" in error for error in errors) == 2


@pytest.mark.parametrize("declaration, expected, warning", [
    ("", "APPLICATION", False),
    ("PAGE_ICON = None", "APPLICATION", False),
    ("from qfluentwidgets import FluentIcon\nPAGE_ICON = FluentIcon.EDUCATION", "EDUCATION", False),
    ('PAGE_ICON = "invalid"', "APPLICATION", True),
])
def test_page_icon_metadata_defaults_and_invalid_values_keep_page_usable(tmp_path, app, caplog, declaration, expected, warning):
    """导航图标可选，错误值只记警告，不改变页面加载与配置提交。"""
    from qfluentwidgets import FluentIcon
    directory = tmp_path / "pages"
    directory.mkdir()
    (directory / "loop.py").write_text((PAGES / "loop.py").read_text() + "\n" + declaration + "\n")
    store = UserSettings(tmp_path)
    pages, errors = discover_pages(directory, store)
    assert not errors and len(pages) == 1
    page = pages[0]
    assert page.icon == getattr(FluentIcon, expected)
    assert ("PAGE_ICON 无效" in caplog.text) == warning
    if warning:
        assert "loop.py" in caplog.text and page.page_id in caplog.text
    page.context.save(page.widget.submit())
    assert store.value["pages"][page.page_id] == {"message": "Hello"}
    page.widget.close()


def test_business_navigation_keeps_all_pages_and_uses_registered_icon(owner, app):
    """纯设置页也归入业务分组，页面图标不改变路由、页面数和任务注册。"""
    from qfluentwidgets import FluentIcon, NavigationItemHeader, NavigationSeparator
    from PySide6.QtTest import QTest
    owner.user.business_pages[0].icon = FluentIcon.EDUCATION
    assert owner.user.close()
    user = owner.open_window()
    panel = user.navigationInterface.panel
    widgets = [panel.topLayout.itemAt(i).widget() for i in range(panel.topLayout.count())][2:]
    assert isinstance(widgets[0], NavigationItemHeader) and widgets[0].text() == "GENERAL"
    assert [widget.property("routeKey") for widget in widgets[1:3]] == ["dashboard", "general-settings"]
    assert isinstance(widgets[3], NavigationSeparator)
    assert isinstance(widgets[4], NavigationItemHeader) and widgets[4].text() == "WORKFLOW SETTINGS"
    assert [widget.property("routeKey") for widget in widgets[5:]] == [page.page_id for page in user.business_pages]
    assert panel.widget(user.business_pages[0].page_id)._icon == FluentIcon.EDUCATION
    assert panel.widget(user.business_pages[1].page_id)._icon == FluentIcon.APPLICATION
    assert user.pages.count() == 4 and list(user.task_rows) == ["sample.loop"]
    for page in user.business_pages:
        user.switchTo(page.widget)
        QTest.qWait(700)
        assert user.pages.currentWidget() is page.widget
        assert panel.widget(page.page_id).itemWidget.isSelected


def test_support_is_bidirectional_and_empty_list_warns_without_deleting_values(tmp_path, app):
    store = UserSettings(tmp_path)
    pages, errors = discover_pages(PAGES, store)
    assert not errors
    store.save_task("sample.loop", True, 5)
    for page in pages:
        page.context.save(page.widget.submit())
    repetitions, settings, warnings = task_inputs(pages, ("missing.task",), store)
    assert repetitions == {"sample.loop": 0, "missing.task": 0}
    assert len(warnings) == 2
    assert "sample.general" in settings
    repetitions, _, warnings = task_inputs(pages, ("sample.loop",), store)
    assert repetitions["sample.loop"] == 5 and not warnings
    settings["sample.general"]["prefix"] = "changed"
    assert store.value["pages"]["sample.general"]["prefix"] != "changed"
    assert task_inputs([], (), store)[2] == ["当前 Plan 未声明支持任何循环任务。"]


@pytest.mark.parametrize("declaration", ['["a", "a"]', '[""]', '[1]', '{"a": 1}', 'make_tasks()'])
def test_invalid_plan_support_declaration_rejected(declaration, tmp_path):
    assert plan_task_ids('"""empty"""') == ()
    with pytest.raises(ValueError):
        plan_task_ids("SUPPORTED_TASK_IDS = " + declaration)
    candidate = tmp_path / "candidate"
    shutil.copytree(EXAMPLE, candidate)
    path = candidate / "plan.py"
    path.write_text(path.read_text().replace('["sample.loop"]', declaration))
    result = ManifestManager(tmp_path / "data").publish(candidate / "manifest.json")
    assert not result.ok and any(error.code == "plan_tasks_invalid" for error in result.errors)


def test_single_editor_handoff_autosaves_and_restores_independent_selection(owner, app):
    user = owner.user
    user.settings_page.url.setText("http://local-before/v1")
    developer = owner.open_window(True)
    assert load_settings(owner.service.data_root)["base_url"] == "http://local-before/v1"
    assert not user.agent_controls.isEnabled()
    assert developer.settings_page.isEnabled()
    page = developer.settings_page
    page.provider.setCurrentIndex(page.provider.findData("deepseek"))
    page.limit.setValue(7)
    page.limit.editingFinished.emit()
    assert load_settings(owner.service.data_root)["max_requests"] == 7
    assert load_settings(owner.service.data_root, side="user")["provider"] == "llama.cpp"
    assert not settings_document(owner.service.data_root)["user_enabled"]
    page.provider.setCurrentIndex(page.provider.findData("llama.cpp"))
    page.url.setText("http://local-after/v1")
    page.url.editingFinished.emit()
    assert developer.close()
    assert user.agent_controls.isEnabled()
    assert user.settings_page.url.text() == "http://local-after/v1"
    user.settings_page.provider.setCurrentIndex(user.settings_page.provider.findData("deepseek"))
    assert user.settings_page.limit.value() == 7
    assert load_settings(owner.service.data_root)["provider"] == "llama.cpp"
    assert load_settings(owner.service.data_root, side="user")["provider"] == "deepseek"


def test_invalid_text_is_saved_and_handed_off_for_later_correction(owner):
    user = owner.user
    user.settings_page.url.setText("invalid")
    developer = owner.open_window(True)
    assert developer.settings_page.url.text() == "invalid"
    assert not user.agent_controls.isEnabled()
    with pytest.raises(ValueError):
        load_settings(owner.service.data_root)
    assert developer.close()
    assert user.agent_controls.isEnabled()
    assert user.settings_page.url.text() == "invalid"


def test_settings_can_save_during_agent_activity(owner):
    page = owner.open_window(True).settings_page
    with owner.service.activity("Agent"):
        page.url.setText("http://next-round/v1")
        page.submit()
        assert load_settings(owner.service.data_root)["base_url"] == "http://next-round/v1"


def test_profile_migration_and_auth_snapshot_survive_clear(tmp_path):
    from types import SimpleNamespace
    path = tmp_path / "agent-settings.json"
    path.write_text('{"model":"legacy","base_url":"http://old/v1","max_requests":9}')
    before = path.read_bytes()
    assert load_settings(tmp_path)["model"] == "legacy"
    assert path.read_bytes() == before
    keys = {}
    save_settings(tmp_path, {"model": "legacy"}, secret="example-old-secret", temporary_keys=keys)
    value, key = settings_snapshot(SimpleNamespace(ask_api_key=False), tmp_path, temporary_keys=keys)
    save_settings(tmp_path, {"provider": "deepseek", "max_requests":5})
    save_selection(tmp_path, "user", "deepseek", enabled=True)
    save_settings(tmp_path, {"provider": "llama.cpp"}, clear=True, temporary_keys=keys)
    assert value["model"] == "legacy" and value["max_requests"] == 9 and key == "example-old-secret"
    assert not keys
    assert load_settings(tmp_path)["base_url"] == "http://old/v1"
    assert load_settings(tmp_path, side="user")["max_requests"] == 5
    assert "example-old-secret" not in path.read_text()


def test_validation_failure_does_not_start_or_schedule_restart(owner):
    page = next(page.widget for page in owner.user.business_pages if page.task_id)
    page.message.clear()
    with pytest.raises(ValueError, match="消息不能为空"):
        owner.user.start_plan()
    assert owner.service.state["run_id"] is None
    with pytest.raises(ValueError, match="消息不能为空"):
        owner.request_reload()
    assert not owner.reloading and owner.lifecycle.restart is None


def test_reload_blocks_all_activity_then_saves_both_windows_and_restores_ids(owner, app, monkeypatch):
    developer = owner.open_window(True)
    with owner.service.activity("Agent Settings 检查"):
        with pytest.raises(ValueError, match="不能重载"):
            owner.request_reload()
    developer.jobs.append(object())
    with pytest.raises(ValueError, match="不能重载"):
        owner.request_reload()
    developer.jobs.clear()
    calls = []
    monkeypatch.setattr(owner, "restart_process", calls.append)
    owner.request_reload()
    assert owner.reloading and calls == []
    with pytest.raises(ValueError, match="重新加载"):
        owner.open_window(True)
    owner.shutdown()
    owner.lifecycle.restart()
    assert calls == [("user", "developer")]
    assert owner.user is None and owner.developer is None
    assert UserSettings(owner.service.data_root).value["pages"]["sample.general"]["prefix"] == "LALC: "


def test_warning_latches_across_window_close_until_new_application(owner):
    user = owner.user
    pages = user.business_pages
    user.add_warning("previous mismatch")
    user.close()
    (owner.service.data_root / "pages/added.py").write_text((PAGES / "loop.py").read_text())
    reopened = owner.open_window()
    assert reopened.business_pages is pages and len(pages) == 2
    assert "previous mismatch" in reopened.warning_history
    assert not reopened.warning_button.isHidden()


def test_save_failure_preserves_input_and_blocks_handoff_and_reload(owner, monkeypatch):
    import lalc.agent_settings as settings
    page = owner.user.settings_page
    page.url.setText("http://unsaved/v1")
    def fail(*_):
        raise OSError("save failed")
    monkeypatch.setattr(settings, "atomic_write_json", fail)
    with pytest.raises(OSError, match="save failed"):
        owner.open_window(True)
    assert owner.developer is None and page.dirty
    assert page.url.text() == "http://unsaved/v1"
    with pytest.raises(OSError, match="save failed"):
        owner.request_reload()
    assert owner.lifecycle.restart is None


@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_lifecycle_only_restarts_after_successful_cleanup(tmp_path, monkeypatch, cleanup_fails):
    from lalc.lifecycle import run_application
    events = []
    def start(lifecycle):
        def cleanup():
            events.append("cleanup")
            if cleanup_fails:
                raise OSError("cleanup failed")
        lifecycle.shutdown = cleanup
        lifecycle.restart = lambda: events.append("restart")
        return 0
    def fatal(self, details):
        self.pending_details = ""
        events.append("error")
    monkeypatch.setattr(ApplicationLifecycle, "present_fatal", fatal)
    result = run_application(start, data_root=tmp_path)
    assert result == (1 if cleanup_fails else 0)
    assert events == (["cleanup", "error"] if cleanup_fails else ["cleanup", "restart"])


def test_restart_spawn_failure_reports_error(tmp_path, monkeypatch):
    from lalc.lifecycle import run_application
    errors = []
    def start(lifecycle):
        def fail():
            raise OSError("could not start")
        lifecycle.restart = fail
        return 0
    monkeypatch.setattr(ApplicationLifecycle, "present_fatal", lambda self, details: errors.append(details))
    assert run_application(start, data_root=tmp_path) == 1
    assert "could not start" in errors[0]


@pytest.mark.parametrize("frozen", [False, True])
def test_gui_reload_replaces_launcher_instead_of_leaving_detached_child(monkeypatch, frozen):
    """源码与打包入口均替换当前程序，终端不会提前结束其启动命令。"""
    import sys
    calls = []
    monkeypatch.setattr(sys, "frozen", frozen, raising=False)
    monkeypatch.setattr("lalc.gui.os.execv", lambda executable, arguments: calls.append((executable, arguments)))
    GuiCoordinator.restart_process(("user", "developer"))
    command = [sys.executable] + ([] if frozen else ["-m", "lalc"]) + ["--restore-gui=user,developer"]
    assert calls == [(sys.executable, command)]


def test_reload_through_real_process_restores_both_windows_and_rescans(tmp_path):
    import os
    import socket
    import subprocess
    import sys
    import time
    if hasattr(socket, "AF_UNIX"):
        import tempfile
        probe = socket.socket(socket.AF_UNIX)
        probe_path = Path(tempfile.gettempdir()) / f"lalc-reload-probe-{os.getpid()}"
        try:
            probe.bind(str(probe_path))
        except PermissionError:
            pytest.skip("当前环境禁止本地 IPC，需在允许 IPC 的环境运行真实重载检查")
        finally:
            probe.close()
            probe_path.unlink(missing_ok=True)
    root = tmp_path / ("LALC" if sys.platform == "win32" else ".local/share/LALC")
    (root / "pages").mkdir(parents=True)
    page = """from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import FluentWindow
import atexit
PAGE_ID = "probe"
PAGE_NAME = "probe"
class Page(QWidget):
    def submit(self):
        return {}
def create_page(context):
    root = context.store.path.parent
    marker = root / "first"
    def verify():
        users = [w for w in QApplication.topLevelWidgets() if w.__class__.__name__ == "UserWindow"]
        if not users:
            return QTimer.singleShot(30, verify)
        owner = users[0].coordinator
        if owner.developer is None or any(w.jobs for w in (owner.user, owner.developer)):
            return QTimer.singleShot(30, verify)
        if second:
            assert isinstance(owner.user, FluentWindow) and isinstance(owner.developer, FluentWindow)
            assert owner.user.pages.count() == 4
            assert not owner.user.agent_controls.isEnabled()
            atexit.register(lambda: (root / "clean-exit").write_text("normal"))
            (root / "ready").write_text("restored-and-rescanned")
            def close_when_requested():
                if not (root / "close-now").exists():
                    return QTimer.singleShot(20, close_when_requested)
                assert owner.user.close()
                assert owner.user is None and owner.developer is not None
                assert owner.developer.close()
                assert owner.developer is None
            QTimer.singleShot(20, close_when_requested)
        else:
            (root / "pages/new.py").write_text('from PySide6.QtWidgets import QWidget\\nPAGE_ID="new"\\nPAGE_NAME="new"\\nclass P(QWidget):\\n    def submit(self): return {}\\ndef create_page(ctx): return P()\\n')
            owner.request_reload()
    second = marker.exists()
    marker.touch()
    QTimer.singleShot(50, verify)
    return Page()
"""
    (root / "pages/probe.py").write_text(page)
    env = {**os.environ, "HOME": str(tmp_path), "USERPROFILE": str(tmp_path),
           "LOCALAPPDATA": str(tmp_path), "QT_QPA_PLATFORM": "cocoa" if sys.platform == "darwin" else "offscreen",
           "PYTHONFAULTHANDLER": "1"}
    process = subprocess.Popen([sys.executable, "-c",
        'from lalc.gui import run_gui; from lalc.lifecycle import run_application; '
        'raise SystemExit(run_application(lambda owner: run_gui(owner, restore=("user","developer"))))'],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        until = time.monotonic() + 10
        while not (root / "ready").exists() and process.poll() is None and time.monotonic() < until:
            time.sleep(.03)
        assert (root / "ready").exists() and process.poll() is None
        (root / "close-now").touch()
        output, error = process.communicate(timeout=10)
        assert process.returncode == 0, error.decode()
        assert (root / "ready").read_text() == "restored-and-rescanned", error.decode()
        assert "Fatal Python error" not in error.decode()
        assert (root / "clean-exit").exists()
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=2)
