"""覆盖多任务注册、停用保留、专用确认及 Session 来源显示。

项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_page_availability.py
"""


import pytest

from lalc.agent_policy import allowed_tools
from lalc.page_packages import snapshot_page
from lalc.page_preview import PageAvailabilityDialog, PreviewRequest
from lalc.user_pages import PageAvailability, UserSettings, discover_pages, task_inputs
from test_page_drafts import SOURCE, drafts
from test_user_pages import app, owner


TASKS = [
    {"id": "first", "name": "First", "show_task_count": True},
    {"id": "second", "name": "Second", "show_task_count": False},
]


def source(tasks=TASKS):
    return SOURCE + f'\nTASKS = {tasks!r}\n'


def install_source(drafts, code=None):
    drafts.installed.mkdir(parents=True, exist_ok=True)
    (drafts.installed / 'sample.py').write_text(code or source())
    package = snapshot_page(drafts.package_path('sample.py', 'installed'))
    return {'filename': 'sample.py', 'sha256': package.sha256, 'package': package}


def test_multiple_tasks_disable_restore_and_reserve_ids(drafts, app):
    snapshot = install_source(drafts)
    root = drafts.installed.parent
    store = UserSettings(root)
    store.save('pages', 'sample.page', {'field': 'saved'})
    for task in TASKS:
        store.save_task(task['id'], True, 7)
    pages, errors = discover_pages(drafts.installed, store)
    assert not errors and len(pages[0].tasks) == 2
    repetitions, _, _ = task_inputs(pages, ('first', 'second'), store)
    assert repetitions == {'first': 7, 'second': 1}
    for page in pages:
        page.widget.close()
    assert drafts.set_enabled(snapshot, False)['reload_required']
    assert drafts.list()['items'][0]['enabled'] is False
    pages, errors = discover_pages(drafts.installed, store)
    assert not pages and not errors
    repetitions, settings, _ = task_inputs(pages, ('first', 'second'), store)
    assert repetitions == {'first': 0, 'second': 0}
    assert settings['sample.page'] == {'field': 'saved'}
    (drafts.installed / 'other.py').write_text(source().replace('sample.page', 'other.page'))
    pages, errors = discover_pages(drafts.installed, store)
    assert not pages and len(errors) == 2
    (drafts.installed / 'other.py').unlink()
    # 覆盖安装同一页不能改变停用名单，业务配置保存也不能覆盖状态。
    drafts.create('sample.py', copy_from='sample.py')
    drafts.install(drafts.snapshot('sample.py'), 'sample.page', TASKS)
    store.save('pages', 'sample.page', {'field': 'updated'})
    assert not PageAvailability(root).enabled('sample.py')
    drafts.set_enabled(snapshot, True)
    pages, errors = discover_pages(drafts.installed, UserSettings(root))
    assert not errors and len(pages) == 1
    assert task_inputs(pages, ('first', 'second'), store)[0] == {'first': 7, 'second': 1}
    for page in pages:
        page.widget.close()


@pytest.mark.parametrize('declaration', [
    'TASK_ID = "old"', 'SHOW_TASK_COUNT = False',
    'TASKS = [{"id": "x", "name": "X", "show_task_count": "false"}]',
    f'TASKS = {[TASKS[0], TASKS[0]]!r}',
])
def test_invalid_and_legacy_declarations_rejected(drafts, app, declaration):
    install_source(drafts, SOURCE + '\n' + declaration)
    pages, errors = discover_pages(drafts.installed, UserSettings(drafts.installed.parent))
    assert not pages and len(errors) == 1


@pytest.mark.parametrize('decision', ['confirm', 'close', 'cancel', 'stale'])
def test_dedicated_availability_confirmation(drafts, app, decision):
    snapshot = install_source(drafts)
    request = PreviewRequest(drafts, snapshot, '停用测试', ('session', 1, 1))
    request.enabled = False
    # Qt parent 必须为 QWidget；测试窗口保留真实生命周期属性。
    from PySide6.QtWidgets import QWidget
    window = QWidget()
    window.jobs, window.closing = [], False
    dialog = PageAvailabilityDialog(request, window)
    if decision == 'confirm':
        dialog.apply_change()
        assert request.result['status'] == 'availability_changed'
    elif decision == 'close':
        dialog.reject()
        assert request.result['status'] == 'skipped'
    elif decision == 'cancel':
        request.close()
        dialog.apply_change()
        assert request.result is None
    else:
        (drafts.installed / 'sample.py').write_text(source() + '\n# new version\n')
        dialog.apply_change()
        assert request.result['status'] == 'failed'
    assert PageAvailability(drafts.installed.parent).enabled('sample.py') is (decision != 'confirm')
    dialog.close()
    window.close()
    app.processEvents()


def test_availability_permission_scope():
    assert 'page_set_enabled' in allowed_tools('Construct', 'gui')
    for mode, entry in [('Repair', 'gui'), ('Repair', 'cli')]:
        assert 'page_set_enabled' not in allowed_tools(mode, entry)


def test_source_label_fixed_session_and_new_selection(owner, app):
    from lalc.developer_session import DeveloperSession
    owner.open_window(True)
    page = owner.developer.repair_page
    assert page.source_label.text().endswith('None') or page.source_label.text().endswith('无')
    identity = owner.host.manager.default_manifest_id()
    page.baseline.setCurrentIndex(page.baseline.findData(identity))
    assert identity in page.source_label.text()
    session = DeveloperSession.create(owner.service, identity, mode='Construct', entry='gui')
    session.conversation()
    page.activate_session(session)
    page.baseline.setCurrentIndex(0)
    assert identity in page.source_label.text()
    blank = DeveloperSession.create(owner.service, None, mode='Construct', entry='gui')
    blank.conversation()
    page.activate_session(blank)
    assert identity not in page.source_label.text()


def test_availability_tool_waits_and_cancel_invalidates_approval(drafts):
    """工具等待人工选择，取消轮次后旧请求不能写入状态。"""
    from concurrent.futures import ThreadPoolExecutor
    import threading
    from lalc.agent_log import read_json
    install_source(drafts)
    tools = drafts.session.host.conversation.tools
    ready = threading.Event()
    requests = []
    def show(request):
        requests.append(request)
        ready.set()
    tools.on_page_preview = show
    with ThreadPoolExecutor() as pool:
        pending = pool.submit(tools.call, 'page_set_enabled',
                              {'filename': 'sample.py', 'enabled': False, 'summary': '停用'})
        assert ready.wait(3) and not pending.done()
        tools.cancelled.set()
        assert read_json(pending.result(timeout=3))['isError']
    request = requests[0]
    assert not request.finish(action=lambda: drafts.set_enabled(request.snapshot, False))
    assert PageAvailability(drafts.installed.parent).enabled('sample.py')


def test_gui_routes_availability_and_prompts_restart_after_cleanup(owner, app):
    """真实 GUI 接收专用请求，批准后只在轮次清理完成时提示重启。"""
    from types import SimpleNamespace
    from lalc.developer_session import DeveloperSession
    from lalc.page_drafts import PageDrafts
    owner.open_window(True)
    window = owner.developer
    page = window.repair_page
    session = DeveloperSession.create(owner.service, None, mode='Construct', entry='gui')
    chat = session.conversation()
    page.activate_session(session)
    draft_store = PageDrafts(session)
    snapshot = install_source(draft_store)
    request = PreviewRequest(draft_store, snapshot, '停用页面', (chat.log.identity, chat.log.group, 1))
    request.enabled = False
    window.jobs = [SimpleNamespace(cancel_requested=False)]
    try:
        page.show_page_preview(request)
        dialog = page.page_preview_dialog
        assert isinstance(dialog, PageAvailabilityDialog)
        dialog.confirm.click()
        assert request.result['status'] == 'availability_changed'
        assert not hasattr(window, 'page_installed_dialog')
    finally:
        window.jobs = []
    page.finish_page_installations()
    assert window.page_installed_dialog.isVisible()
    window.page_installed_dialog.reject()
    app.processEvents()
