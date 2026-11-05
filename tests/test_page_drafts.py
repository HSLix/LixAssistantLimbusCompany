"""覆盖页面草稿持久化、权限、只读不执行、预览内存配置、版本安装与取消。

项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_page_drafts.py
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import threading
import time

import pytest

from lalc.agent_log import read_json
from lalc.agent_policy import PAGE_TOOLS, allowed_tools
from lalc.developer_session import DeveloperSession
from lalc.page_drafts import PageDrafts, page_filename
from lalc.user_pages import UserSettings, discover_pages, task_inputs
from test_agent_repair import host_for
from test_developer_gui import gui, wait_jobs
from test_user_pages import app, owner


SOURCE = '''from PySide6.QtWidgets import QWidget, QVBoxLayout, QLineEdit
PAGE_ID = "sample.page"
PAGE_NAME = "Sample"
TASK_ID = "sample.task"
class Page(QWidget):
    def __init__(self, context):
        super().__init__()
        self.context = context
        self.field = QLineEdit(context.load({"field": "default"})["field"])
        QVBoxLayout(self).addWidget(self.field)
        self.field.textChanged.connect(lambda text: context.save({"field": text}))
    def submit(self):
        raise AssertionError("preview must not submit")
def create_page(context):
    return Page(context)
'''


@pytest.fixture
def drafts(tmp_path):
    host, _ = host_for(tmp_path / "page-drafts-service")
    session = DeveloperSession.create(host.service, None, mode="Construct", entry="gui")
    session.conversation()
    return PageDrafts(session)


def test_persistent_drafts_readonly_source_settings_and_permissions(drafts):
    root = drafts.session.host.service.data_root
    installed = root / "pages"
    installed.mkdir()
    marker = root / "must-not-execute"
    code = f'from pathlib import Path\nPath({str(marker)!r}).touch()\n' + SOURCE
    (installed / "sample.py").write_text(code)
    UserSettings(root).save("pages", "sample.page", {"field": "old"})
    assert drafts.list()["items"][0]["filename"] == "sample.py"
    first = drafts.read(filename="sample.py", limit=10)
    assert first["source"] + drafts.read(filename="sample.py", offset=10)["source"] == code
    assert json.loads(drafts.read("settings")["source"])["pages"]["sample.page"] == {"field": "old"}
    drafts.create("sample.py", copy_from="sample.py")
    drafts.update("sample.py", SOURCE)
    restored = PageDrafts(DeveloperSession(drafts.session.host.service, drafts.session.identity, entry="gui"))
    assert restored.snapshot("sample.py")["source"] == SOURCE.encode()
    assert restored.metadata("sample.py")["replace"] is True
    assert not marker.exists()
    raw = SOURCE.replace("\n", "\r\n").encode()
    (installed / "windows.py").write_bytes(raw)
    assert drafts.read(filename="windows.py")["sha256"] == hashlib.sha256(raw).hexdigest()
    other = PageDrafts(DeveloperSession.create(drafts.session.host.service, None, mode="Construct", entry="gui"))
    assert not other.list("drafts")["items"]
    repair = DeveloperSession.create(drafts.session.host.service, drafts.session.host.manager.default_manifest_id(), entry="gui")
    with pytest.raises(ValueError, match="Construct"):
        PageDrafts(repair)
    for mode, entry in (("Repair", "gui"), ("Repair", "cli")):
        assert not set(PAGE_TOOLS) & set(allowed_tools(mode, entry))
        tools = repair.conversation().tools
        for name in PAGE_TOOLS:
            assert read_json(tools.call(name, {}))["isError"]
    assert set(PAGE_TOOLS) <= set(allowed_tools("Construct", "gui"))


@pytest.mark.parametrize("name", ["../page.py", "/page.py", "p/x.py", "p\\x.py", "con.py", "con.extra.py", "LPT1.py", "_hidden.py", "p.py:stream", "p.txt", "", None])
def test_invalid_filenames(name):
    with pytest.raises(ValueError):
        page_filename(name)


def test_existing_unicode_filename_and_settings_symlink(drafts, tmp_path):
    drafts.create("镜牢设置.py", SOURCE)
    assert drafts.list("drafts")["items"][0]["filename"] == "镜牢设置.py"
    outside = tmp_path / "settings.json"
    outside.write_text('{"secret": "must not read"}')
    (drafts.session.host.service.data_root / "user-settings.json").symlink_to(outside)
    with pytest.raises(ValueError, match="符号链接"):
        drafts.read("settings")


def test_creation_update_failure_and_symlinks_preserve_files(drafts, tmp_path, monkeypatch):
    import lalc.page_drafts as storage
    drafts.create("new.py", SOURCE)
    original = drafts.snapshot("new.py")
    with pytest.raises(ValueError):
        drafts.create("new.py", SOURCE)
    with pytest.raises(SyntaxError):
        drafts.update("new.py", "def broken(")
    monkeypatch.setattr(storage.os, "link", lambda *args: (_ for _ in ()).throw(OSError("disk failure")))
    with pytest.raises(OSError):
        drafts.create("failed.py", SOURCE)
    assert not (drafts.root / "failed.py").exists()
    assert not (drafts.root / "failed.json").exists()
    assert drafts.snapshot("new.py") == original
    outside = tmp_path / "outside.py"
    outside.write_text(SOURCE)
    (drafts.root / "link.py").symlink_to(outside)
    with pytest.raises(ValueError, match="符号链接"):
        drafts.read("drafts", "link.py")
    (drafts.root / "link.py").unlink()
    (drafts.root / "new.json").unlink()
    (drafts.root / "new.json").symlink_to(outside)
    with pytest.raises(ValueError):
        drafts.snapshot("new.py")
    assert outside.read_text() == SOURCE


def test_install_snapshot_no_clobber_conflict_and_failed_replace(drafts, monkeypatch):
    drafts.create("sample.py", SOURCE)
    snapshot = drafts.snapshot("sample.py")
    drafts.update("sample.py", SOURCE.replace('"Sample"', '"Changed"'))
    installed = drafts.install(snapshot, "sample.page", "sample.task")
    assert installed["sha256"] == snapshot["sha256"]
    target = drafts.path("sample.py", "installed")
    assert target.read_bytes() == SOURCE.encode()
    with pytest.raises(ValueError, match="已存在"):
        drafts.install(snapshot, "sample.page", "sample.task")
    drafts.create("other.py", SOURCE)
    with pytest.raises(ValueError, match="冲突"):
        drafts.install(drafts.snapshot("other.py"), "sample.page", "other.task")
    with pytest.raises(ValueError, match="冲突"):
        drafts.install(drafts.snapshot("other.py"), "other.page", "sample.task")
    # 将新增草稿与已正式安装页面分开，用另一 Session 创建替换草稿。
    session = DeveloperSession.create(drafts.session.host.service, None, mode="Construct", entry="gui")
    replacement = PageDrafts(session)
    replacement.create("sample.py", copy_from="sample.py")
    replacement.update("sample.py", SOURCE.replace('"Sample"', '"Changed"'))
    original_rename = Path.rename
    def failed_replace(path, dest):
        if path.name == "new" and dest == target.parent:
            raise OSError("replace failed")
        return original_rename(path, dest)
    monkeypatch.setattr(Path, "rename", failed_replace)
    with pytest.raises(OSError):
        replacement.install(replacement.snapshot("sample.py"), "sample.page", "sample.task")
    assert target.read_bytes() == SOURCE.encode()
    assert replacement.snapshot("sample.py")["source"] != SOURCE.encode()
    assert not list(drafts.installed.glob(".page-*"))


def preview(gui, drafts, source=SOURCE, old=None):
    from lalc.page_preview import PagePreviewDialog, PreviewRequest
    app, window = gui
    if old is not None:
        drafts.installed.mkdir(exist_ok=True)
        (drafts.installed / "sample.py").write_text(old)
        drafts.create("sample.py", copy_from="sample.py")
        drafts.update("sample.py", source)
    else:
        drafts.create("sample.py", source)
    request = PreviewRequest(drafts, drafts.snapshot("sample.py"), "字段影响说明", (drafts.session.identity, 1, 1))
    dialog = PagePreviewDialog(request, window)
    if dialog.ready:
        dialog.show()
    app.processEvents()
    return request, dialog


def test_preview_independent_memory_no_submit_and_install_exact_version(gui, drafts):
    from PySide6.QtCore import QEvent, Qt
    app, window = gui
    root = drafts.session.host.service.data_root
    store = UserSettings(root)
    store.save("pages", "sample.page", {"field": "old"})
    config = store.path.read_bytes()
    request, dialog = preview(gui, drafts, old=SOURCE)
    try:
        assert app.activeModalWidget() is dialog
        assert dialog.windowModality() == Qt.WindowModality.ApplicationModal
        assert dialog.tabs.currentRouteKey() == 'proposed' and dialog.stack.currentIndex() == 1
        assert 'sample.page' in dialog.review_details.toPlainText()
        assert request.snapshot['sha256'] in dialog.review_details.toPlainText()
        assert dialog.review_summary.toPlainText() == request.summary
        other = window.coordinator.open_window() if window.coordinator is not None else window
        app.sendEvent(other, QEvent(QEvent.Type.WindowBlocked))
        assert dialog.notice.text()
        assert dialog.install_button.isEnabled()
        assert dialog.current.widget.field.text() == dialog.proposed.widget.field.text() == "old"
        dialog.current.widget.field.setText("left")
        dialog.proposed.widget.field.setText("right")
        for key, index in (('current', 0), ('review', 2), ('proposed', 1)):
            dialog.tabs.setCurrentItem(key)
            assert dialog.stack.currentIndex() == index
            assert dialog.install_button.isEnabled() and dialog.close_button.isEnabled() and dialog.cancel.isEnabled()
        assert dialog.current.widget.field.text() == 'left'
        assert dialog.proposed.widget.field.text() == 'right'
        assert dialog.current.context.load() == {"field": "left"}
        assert dialog.proposed.context.load() == {"field": "right"}
        assert store.path.read_bytes() == config
        drafts.update("sample.py", SOURCE.replace('"Sample"', '"Future"'))
        dialog.install_button.click()
        assert request.result["status"] == "installed"
        assert drafts.path("sample.py", "installed").read_text() == SOURCE
        assert store.path.read_bytes() == config
    finally:
        dialog.close()
    assert app.activeModalWidget() is None
    # 新应用发现正式文件，配置仍按稳定 ID 进入 Dashboard / Plan。
    pages, errors = discover_pages(drafts.installed, UserSettings(root))
    assert not errors
    settings = UserSettings(root)
    settings.save_task("sample.task", True, 3)
    repetitions, values, warnings = task_inputs(pages, ("sample.task",), settings)
    assert repetitions == {"sample.task": 3} and values["sample.page"] == {"field": "old"} and not warnings
    for page in pages:
        page.widget.close()


def test_broken_current_page_still_allows_repair(gui, drafts):
    app, _ = gui
    request, dialog = preview(gui, drafts, old='raise ValueError("old broken")')
    assert dialog.ready and dialog.isVisible() and 'current' in dialog.errors
    assert dialog.tabs.currentRouteKey() == 'proposed'
    dialog.install_button.click()
    assert request.result['status'] == 'installed'
    app.processEvents()
    assert app.activeModalWidget() is None


@pytest.mark.parametrize('source,expected', [
    (SOURCE.replace('PAGE_ID = "sample.page"', ''), 'PAGE_ID'),
    (SOURCE.replace('PAGE_ID = "sample.page"', 'PAGE_ID = "dashboard"'), '页面声明'),
    ('raise ValueError("new broken")', 'new broken'),
    (SOURCE.replace('return Page(context)', 'raise ValueError("create failed")'), 'create failed'),
    (SOURCE.replace('return Page(context)', 'return None'), 'QWidget'),
    (SOURCE.replace('def submit(self):', 'def unrelated(self):'), 'submit'),
])
def test_invalid_proposed_never_shows_approval(gui, drafts, source, expected):
    app, _ = gui
    request, dialog = preview(gui, drafts, source, old=SOURCE)
    assert not dialog.ready and request.done.is_set()
    assert request.result['status'] == 'preview_failed'
    assert expected in request.result['error']
    assert (drafts.installed / 'sample.py').read_text() == SOURCE
    assert dialog.current is None  # 拟安装页失败时，不再执行旧页。
    assert app.activeModalWidget() is None



@pytest.mark.parametrize('conflict', ['page', 'task'])
def test_registration_failure_returns_before_approval(gui, drafts, conflict):
    app, _ = gui
    drafts.installed.mkdir()
    other = SOURCE.replace('"sample.task"', '"other.task"') if conflict == 'page' else SOURCE.replace('"sample.page"', '"other.page"')
    (drafts.installed / 'other.py').write_text(other)
    request, dialog = preview(gui, drafts)
    assert not dialog.ready and request.result['status'] == 'preview_failed'
    assert '冲突' in request.result['error']
    assert app.activeModalWidget() is None
    assert not (drafts.installed / 'sample.py').exists()


def test_preparation_and_tab_switches_execute_proposed_once(gui, drafts, monkeypatch):
    import builtins
    from lalc.page_preview import PagePreviewDialog, PreviewRequest
    app, window = gui
    counts = {'module': 0, 'create': 0}
    monkeypatch.setattr(builtins, '_lalc_preview_counts', counts, raising=False)
    source = ('import builtins\nbuiltins._lalc_preview_counts["module"] += 1\n' + SOURCE).replace(
        'return Page(context)', 'builtins._lalc_preview_counts["create"] += 1\n    return Page(context)')
    request, dialog = preview(gui, drafts, source)
    assert counts == {'module': 1, 'create': 1}
    for key in ('review', 'current', 'proposed', 'review', 'proposed'):
        dialog.tabs.setCurrentItem(key)
    assert counts == {'module': 1, 'create': 1}
    dialog.close_button.click()
    # 取消若在加载中到达，不能在准备完成后展示或授权。
    next_request = PreviewRequest(drafts, drafts.snapshot('sample.py'), 'cancel while loading', request.identity)
    import lalc.page_preview as ui
    create = ui.create_business_page
    def cancel_during_load(*args):
        page = create(*args)
        next_request.close()
        return page
    monkeypatch.setattr(ui, 'create_business_page', cancel_during_load)
    cancelled = PagePreviewDialog(next_request, window)
    assert not cancelled.ready and next_request.done.is_set() and next_request.result is None
    assert not cancelled.isVisible()
    app.processEvents()
    assert app.activeModalWidget() is None


def test_preview_cancel_wakes_tool_and_stale_approval_invalid(drafts):
    tools = drafts.session.host.conversation.tools
    drafts.create("sample.py", SOURCE)
    ready = threading.Event()
    requests = []
    def show(request):
        requests.append(request)
        ready.set()
    tools.on_page_preview = show
    with ThreadPoolExecutor() as pool:
        pending = pool.submit(tools.call, "page_preview", {"filename": "sample.py", "summary": "无字段变更"})
        try:
            assert ready.wait(3)
            assert not pending.done()
        finally:
            tools.cancelled.set()
        assert read_json(pending.result(timeout=3))["isError"]
    assert not requests[0].finish({"status": "installed"})
    assert not drafts.installed.exists()


def test_preview_install_failure_redacted_then_reopen_current_bytes(gui, drafts, monkeypatch):
    from lalc.page_preview import PagePreviewDialog, PreviewRequest
    app, window = gui
    request, dialog = preview(gui, drafts, old=SOURCE)
    drafts.session.host.secrets['test'] = 'sensitive-value'
    def fail(*args):
        raise OSError('disk failure sensitive-value')
    with monkeypatch.context() as patch:
        patch.setattr(drafts, 'install', fail)
        dialog.install_button.click()
    assert not request.done.is_set()
    assert dialog.isVisible() and 'sensitive-value' not in dialog.status.text()
    assert (drafts.installed / 'sample.py').read_text() == SOURCE
    dialog.close_button.click()
    assert request.result['status'] == 'not_installed'
    assert 'install' in request.result['errors'] and 'sensitive-value' not in str(request.result)
    new_source = SOURCE.replace('"Sample"', '"Fresh page"')
    drafts.update('sample.py', new_source)
    next_request = PreviewRequest(drafts, drafts.snapshot('sample.py'), '显示名变更', (drafts.session.identity, 1, 2))
    next_dialog = PagePreviewDialog(next_request, window)
    next_dialog.show()
    app.processEvents()
    assert next_dialog.proposed.name == 'Fresh page'
    assert next_request.snapshot['sha256'] != request.snapshot['sha256']
    assert not request.finish(action=lambda: pytest.fail('旧批准不能安装新版本'))
    next_dialog.close_button.click()
    app.processEvents()
    assert app.activeModalWidget() is None


@pytest.mark.parametrize("action", ["close", "cancel", "install"])
def test_gui_request_identity_modal_wait_and_round_result(gui, action):
    app, window = gui
    session = DeveloperSession.create(window.service, None, mode="Construct", entry="gui")
    session.conversation()
    window.repair_page.activate_session(session)
    drafts = PageDrafts(session)
    drafts.create("sample.py", SOURCE)
    tools = session.host.conversation.tools
    tools.on_page_preview = window.page_preview_requested.emit
    async def operation():
        with window.service.activity("Agent"):
            try:
                return await asyncio.to_thread(tools.call, "page_preview", {"filename": "sample.py", "summary": "无字段变更"})
            except asyncio.CancelledError:
                tools.cancelled.set()
                raise
    window.launch(operation)
    until = time.monotonic() + 3
    while not hasattr(window.repair_page, "page_preview_dialog") and time.monotonic() < until:
        app.processEvents()
        time.sleep(.005)
    dialog = window.repair_page.page_preview_dialog
    app.processEvents()
    assert not window.repair_page.new_button.isEnabled()
    from lalc.page_preview import PreviewRequest
    stale = PreviewRequest(drafts, drafts.snapshot("sample.py"), "stale", ("old", 0, 1))
    window.repair_page.show_page_preview(stale)
    assert stale.done.is_set() and window.repair_page.page_preview_dialog is dialog
    if action == "close":
        dialog.close_button.click()
    elif action == "cancel":
        dialog.cancel.click()
    else:
        dialog.install_button.click()
    wait_jobs(app, window)
    assert dialog.request.done.is_set()
    assert not dialog.request.finish({"status": "installed"})
    assert dialog.request.result is None if action == "cancel" else dialog.request.result["status"] == ("installed" if action == "install" else "not_installed")
    assert window.service.state["activity"] is None


def test_installed_page_reload_and_real_plan_keep_formal_configuration(owner, app, monkeypatch):
    """人工安装后走既有重载保存链，新宿主重扫并实际执行无游戏操作的 Plan。"""
    from lalc.application import ApplicationService
    from lalc.gui import GuiCoordinator
    from lalc.lifecycle import ApplicationLifecycle
    from lalc.page_preview import PagePreviewDialog, PreviewRequest
    user = owner.user
    developer = owner.open_window(True)
    session = DeveloperSession.create(owner.service, None, mode="Construct", entry="gui")
    session.conversation()
    developer.repair_page.activate_session(session)
    drafts = PageDrafts(session)
    drafts.create("loop.py", copy_from="loop.py")
    drafts.update("loop.py", (drafts.installed / "loop.py").read_text() + '\nPAGE_NAME = "Installed settings"\n')
    request = PreviewRequest(drafts, drafts.snapshot("loop.py"), "仅修改页面显示名，字段与 Plan 不变。", (session.identity, 0, 1))
    dialog = PagePreviewDialog(request, developer)
    dialog.show()
    app.processEvents()
    dialog.proposed.widget.message.setText("preview-only")
    dialog.install_button.click()
    assert request.result["status"] == "installed"
    pages = {page.page_id: page.widget for page in user.business_pages}
    pages["sample.message"].message.setText("formal")
    pages["sample.general"].prefix.setText("kept:")
    enabled, count = user.task_rows["sample.loop"]
    count.setValue(2)
    enabled.setChecked(True)
    monkeypatch.setattr(owner, "restart_process", lambda windows: None)
    owner.request_reload()
    owner.shutdown()
    owner.lifecycle.restart()
    assert UserSettings(owner.service.data_root).value["pages"]["sample.message"] == {"message": "formal"}
    service = ApplicationService(owner.service.data_root)
    fresh = GuiCoordinator(service, ApplicationLifecycle())
    try:
        new_user = fresh.open_window()
        installed = next(page for page in new_user.business_pages if page.page_id == "sample.message")
        assert installed.name == "Installed settings" and installed.widget.message.text() == "formal"
        monkeypatch.setattr(service, "_start_session", lambda: None)
        new_user.start_plan()
        service.wait_for(lambda state: state["phase"] == "finished")
        service._thread.join()
        result = service.state["result"]
        assert result["status"] == "completed" and result["all_tasks_succeeded"]
        assert len(result["items"]) == 2
        assert all(item["output"] == "kept:formal" for item in result["items"])
    finally:
        fresh.shutdown()
        if fresh.user is not None:
            fresh.user.close()
        app.processEvents()
