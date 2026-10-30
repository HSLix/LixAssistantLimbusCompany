"""覆盖双窗口共享、运行归属、配置可编辑、通知及跨进程唤起。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_user_gui.py
"""

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from lalc.application import StartError
from lalc.lifecycle import ApplicationLifecycle
from test_agent_repair import host_for


@pytest.fixture
def windows(tmp_path, monkeypatch):
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication, QMessageBox
    from lalc.gui import GuiCoordinator, StateBridge
    monkeypatch.chdir(tmp_path)
    app = QApplication.instance() or QApplication([])
    host, _ = host_for(tmp_path)
    coordinator = GuiCoordinator(host.service, ApplicationLifecycle())
    coordinator.host = host
    bridge = StateBridge()
    host.service.on_change = bridge.changed.emit
    bridge.changed.connect(coordinator.render_state)
    user = coordinator.open_window()
    developer = coordinator.open_window(True)
    monkeypatch.setattr(QMessageBox, 'question', lambda *_: QMessageBox.StandardButton.Yes)
    yield app, coordinator, user, developer
    host.service.shutdown()
    for window in (coordinator.user, coordinator.developer):
        if window:
            window.shutdown()
            window.close()
    app.processEvents()


def test_shared_windows_and_independent_idle_close(windows):
    from qfluentwidgets import FluentWindow
    app, owner, user, developer = windows
    assert isinstance(user, FluentWindow) and isinstance(developer, FluentWindow)
    assert user.service is developer.service and user.host is developer.host
    assert owner.open_window(True) is developer
    assert user.pages.widget(0).objectName() == 'dashboard'
    assert [developer.pages.widget(i).objectName() for i in range(developer.pages.count())] == ['developer-capture', 'developer-settings', 'developer-repair']
    assert developer.close()
    assert owner.developer is None and owner.user is user
    assert owner.open_window(True) is not developer


def test_fluent_navigation_keeps_fixed_routes_and_always_visible_task_scrollbar(windows):
    from PySide6.QtCore import Qt
    _, _, user, developer = windows
    assert [user.pages.widget(i).objectName() for i in range(2)] == ["dashboard", "general-settings"]
    user.switchTo(user.general_settings)
    assert user.pages.currentWidget() is user.general_settings
    assert not user.pages.isAnimationEnabled()
    assert user.task_scroll.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOn
    developer.switchTo(developer.settings_view)
    assert developer.pages.currentWidget() is developer.settings_view
    assert not developer.pages.isAnimationEnabled()


def test_empty_navigation_groups_expand_and_compact_without_extra_pages(windows):
    """空业务分组也保留；展开有标题，收起只保留原生分隔线及页面图标。"""
    from PySide6.QtTest import QTest
    from qfluentwidgets import FluentIcon, NavigationItemHeader, NavigationSeparator, NavigationDisplayMode
    app, _, user, developer = windows
    panel = user.navigationInterface.panel
    widgets = [panel.topLayout.itemAt(i).widget() for i in range(panel.topLayout.count())][2:]
    assert len(widgets) == 5
    general, dashboard, settings, separator, workflow = widgets
    assert isinstance(general, NavigationItemHeader) and general.text() == "通用"
    assert isinstance(workflow, NavigationItemHeader) and workflow.text() == "业务设置"
    assert isinstance(separator, NavigationSeparator)
    assert dashboard._icon == FluentIcon.HOME and settings._icon == FluentIcon.SETTING
    assert user.pages.count() == 2 and not user.business_pages
    assert not developer.navigationInterface.findChildren(NavigationItemHeader)
    assert panel.expandWidth == 220
    user.navigationInterface.expand(useAni=False)
    QTest.qWait(200)
    assert all(header.height() > 0 for header in (general, workflow))
    assert separator.isVisible()
    panel.collapse()
    QTest.qWait(400)
    assert all(header.height() == 0 for header in (general, workflow))
    assert separator.isVisible() and separator.width() == 48
    assert dashboard.isCompacted and settings.isCompacted
    user.resize(700, 800)
    app.processEvents()
    user.navigationInterface.expand(useAni=False)
    QTest.qWait(200)
    assert panel.displayMode == NavigationDisplayMode.MENU
    assert all(header.height() > 0 for header in (general, workflow))
    assert separator.isVisible() and panel.expandWidth == 220


def test_native_owned_modal_keeps_other_fluent_window_editable(windows):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from qfluentwidgets import MessageBox
    app, _, user, developer = windows
    if app.platformName() == "offscreen":
        pytest.skip("原生焦点验收需要真实图形会话，不用 offscreen 代替")
    dialog = MessageBox("窗口范围", "仅阻塞所属 User 窗口", user)
    dialog.setWindowModality(Qt.WindowModality.WindowModal)
    dialog.show()
    try:
        developer.switchTo(developer.settings_view)
        developer.activateWindow()
        developer.settings_page.url.setFocus()
        QTest.qWait(150)
        assert app.focusWidget() is developer.settings_page.url
    finally:
        dialog.accept()
        QTest.qWait(150)


def test_user_run_blocks_developer_activity_but_allows_settings_and_idle_close(windows, monkeypatch):
    app, owner, user, developer = windows
    entered, release = threading.Event(), threading.Event()
    def session():
        entered.set()
        assert release.wait(4)
    monkeypatch.setattr(user.service, '_start_session', session)
    try:
        user.start_plan()
        assert entered.wait(2)
        app.processEvents()
        assert user.trial_dialog is not None
        assert not developer.capture_page.capture_button.isEnabled()
        assert developer.settings_page.url.isEnabled()
        developer.settings_page.url.setText('http://saved-for-next-round/v1')
        with pytest.raises(StartError):
            developer.host.capture()
        assert developer.close()
        assert not user.service._gate.stopped
        user.service.pause()
        with pytest.raises(StartError):
            developer.host.initialize(None, replace=True)
        user.service.resume()
    finally:
        release.set()
    user.service.wait_for(lambda state: state['phase'] == 'finished')
    app.processEvents()
    user.render_state(user.service.state)
    assert user.trial_dialog is None
    assert user.notifications.messages.count() == 1


def test_agent_activity_blocks_user_start_but_not_navigation_or_settings(windows):
    app, owner, user, developer = windows
    with user.service.activity('Agent'):
        app.processEvents()
        owner.render_state(user.service.state)
        assert not user.start_button.isEnabled()
        with pytest.raises(StartError):
            user.start_plan()
        user.switchTo(user.general_settings)
        assert user.pages.currentIndex() == 1 and user.pages.isEnabled()
        assert user.close()
        assert owner.user is None and owner.developer is developer
        assert developer.service.state['activity'] == 'Agent'


def test_owner_close_cancels_waits_and_cancelled_confirmation_keeps_window(windows, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    app, owner, user, developer = windows
    entered, release = threading.Event(), threading.Event()
    def session():
        entered.set()
        assert release.wait(4)
    monkeypatch.setattr(user.service, '_start_session', session)
    try:
        user.start_plan()
        assert entered.wait(2)
        monkeypatch.setattr(QMessageBox, 'question', lambda *_: QMessageBox.StandardButton.No)
        assert not user.close() and not user.closing
        assert not user.service._gate.stopped
        monkeypatch.setattr(QMessageBox, 'question', lambda *_: QMessageBox.StandardButton.Yes)
        assert not user.close() and user.closing
        assert user.service._gate.stopped and owner.user is user
    finally:
        release.set()
    user.service.wait_for(lambda state: state['phase'] == 'finished')
    app.processEvents()
    user._finish_close()
    assert owner.user is None and owner.developer is developer


def test_notifications_coexist_and_require_manual_dismissal(windows):
    from PySide6.QtWidgets import QPushButton
    app, _, user, _ = windows
    user.notifications.notify('第一条')
    user.notifications.notify('第二条')
    app.processEvents()
    assert user.notifications.messages.count() == 2
    row = user.notifications.messages.itemAt(0).widget()
    assert row.duration == -1
    row.closeButton.click()
    from PySide6.QtCore import QCoreApplication, QEvent
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert user.notifications.messages.count() == 1


def test_gui_request_is_forwarded_across_real_processes(tmp_path):
    import socket
    probe = socket.socket(socket.AF_UNIX) if hasattr(socket, "AF_UNIX") else None
    if probe is not None:
        try:
            import tempfile
            probe_path = Path(tempfile.gettempdir()) / f"lalc-ipc-probe-{os.getpid()}"
            probe.bind(str(probe_path))
        except PermissionError:
            pytest.skip('当前执行环境禁止本地 IPC；单独在允许 IPC 的环境运行此真实进程测试')
        finally:
            probe.close()
            probe_path.unlink(missing_ok=True)
    ready, received = tmp_path / 'ready', tmp_path / 'received' 
    script = '''
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from lalc.gui_instance import GuiInstance
app = QApplication([])
instance = GuiInstance()
assert instance.forward(False) is False
instance.listen(lambda developer: Path(sys.argv[2]).write_text(str(developer)))
Path(sys.argv[1]).touch()
QTimer.singleShot(10000, app.quit)
try:
    app.exec()
finally:
    instance.close()
'''
    env = {**os.environ, 'QT_QPA_PLATFORM': 'cocoa' if sys.platform == 'darwin' else 'offscreen'}
    process = subprocess.Popen([sys.executable, '-c', script, str(ready), str(received)], env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        until = time.monotonic() + 5
        while not ready.exists() and process.poll() is None and time.monotonic() < until:
            time.sleep(.02)
        assert ready.exists(), process.communicate(timeout=2)
        client = subprocess.run([sys.executable, '-c', 'from PySide6.QtWidgets import QApplication; from lalc.gui_instance import GuiInstance; app=QApplication([]); assert GuiInstance().forward(True)'],
                                env=env, capture_output=True, timeout=5)
        assert client.returncode == 0, client.stderr.decode()
        assert received.read_text() == 'True'
    finally:
        process.terminate()
        process.communicate(timeout=3)


def test_cli_developer_entry_selects_developer_window(tmp_path, monkeypatch):
    import lalc.__main__ as cli
    import lalc.gui as gui
    import lalc.lifecycle as lifecycle
    selected = []
    monkeypatch.setattr(lifecycle, "run_application", lambda start: start(lifecycle.ApplicationLifecycle()))
    monkeypatch.setattr(gui, "run_gui", lambda owner, *, developer=False: selected.append(developer) or 0)
    assert cli.main(["--developer"]) == 0
    assert selected == [True]
