"""覆盖远程 MCP 独立导航页、双窗口门控和真实本地人工审批，不运行模型。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_remote_mcp_gui.py
"""

import time
import uuid

from test_developer_gui import gui
from test_user_gui import windows
from test_page_drafts import SOURCE
from test_remote_mcp import wait_operation, perform


def setup_remote(window):
    remote = window.service.remote_mcp
    remote.initialize()
    remote.reset_token()
    remote.enabled = True
    remote.allow()
    token = remote.acquire()["control_token"]
    return remote, token


def pump(app, predicate):
    deadline = time.monotonic() + 5
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.01)
    assert predicate()


def test_separate_page_and_readonly_lab_exception(gui):
    app, window = gui
    remote, token = setup_remote(window)
    try:
        page = window.remote_mcp_page
        assert page.objectName() == "developer-remote-mcp" and window.stackedWidget.indexOf(page) >= 0
        window.render_state(window.service.status)
        assert page.revoke.isEnabled() and page.toggle.isEnabled()
        assert not page.initialize.isEnabled() and not window.repair_page.send_button.isEnabled()
        assert window.capture_page.capture_button.isEnabled() and not window.capture_page.resize_button.isEnabled()
        assert window.recognition_page.capture_button.isEnabled()
        state = {**window.service.status, "phase": "running", "run_id": 1,
                 "entry": {"developer_trial": True, "remote_operation_id": str(uuid.uuid4())}}
        window.render_state(state)
        assert not window.recognition_page.capture_button.isEnabled()
        assert window.recognition_page.methods.isEnabled() and window.trial_dialog is None
        assert page.stop.isEnabled() and page.pause.isEnabled()
    finally:
        remote.close()


def test_user_settings_are_locked_and_restore_after_release(windows):
    app, coordinator, user, developer = windows
    remote, token = setup_remote(developer)
    try:
        coordinator.render_state(user.service.status)
        assert not user.start_button.isEnabled() and not user.latest_button.isEnabled()
        assert not user.user_enabled.isEnabled()
        assert all(not p.widget.isEnabled() for p in user.business_pages)
        remote.release(token)
        coordinator.render_state(user.service.status)
        assert user.user_enabled.isEnabled()
    finally:
        remote.close()


def test_remote_feedback_uses_local_dialog_and_returns_actual_answer(gui):
    app, window = gui
    remote, token = setup_remote(window)
    try:
        identity = str(uuid.uuid4())
        remote.invoke("request_feedback", {"message": "Local confirmation"}, token, identity)
        pump(app, lambda: bool(window.remote_mcp_page.dialogs))
        dialog = window.remote_mcp_page.dialogs[0]
        dialog.reply.setPlainText("confirmed locally")
        dialog.respond("confirmed")
        op = wait_operation(remote, identity)
        assert op["result"]["details"] == {"status": "confirmed", "text": "confirmed locally"}
    finally:
        remote.close()


def test_remote_page_preview_installs_only_the_locally_approved_snapshot(gui):
    app, window = gui
    remote, token = setup_remote(window)
    try:
        created = perform(remote, token, "page_create", {"filename": "sample.py", "source": SOURCE})
        assert not created["result"].get("isError")
        identity = str(uuid.uuid4())
        remote.invoke("page_preview", {"filename": "sample.py", "summary": "Review the new page"}, token, identity)
        pump(app, lambda: bool(window.remote_mcp_page.dialogs))
        dialog = window.remote_mcp_page.dialogs[0]
        assert dialog.ready and not (remote.service.data_root / "pages/sample/page.py").exists()
        dialog.install()
        op = wait_operation(remote, identity)
        assert op["result"]["details"]["status"] == "installed"
        assert (remote.service.data_root / "pages/sample/page.py").read_text() == SOURCE
    finally:
        remote.close()
