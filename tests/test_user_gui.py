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
    app, owner, user, developer = windows
    assert user.service is developer.service and user.host is developer.host
    assert owner.open_window(True) is developer
    assert user.navigation.item(0).text() == 'Dashboard'
    assert [developer.tabs.tabText(i) for i in range(developer.tabs.count())] == ['Capture', 'Agent Settings', 'Agent Repair']
    assert developer.close()
    assert owner.developer is None and owner.user is user
    assert owner.open_window(True) is not developer


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
        assert developer.settings_page.save_button.isEnabled()
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
        user.navigation.setCurrentRow(1)
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
    row.findChild(QPushButton).click()
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
    env = {**os.environ, 'QT_QPA_PLATFORM': 'offscreen'}
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
