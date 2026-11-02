"""覆盖工作台准备状态、Session 路由、入口授权及 Manifest 纯只读边界；不启动 Agent。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_workbench.py
"""

import asyncio
import hashlib
import json
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt

from lalc.agent_log import read_json
from lalc.agent_policy import allowed_tools
from lalc.developer_session import DeveloperSession
from lalc.manifest_reference import ManifestReference
from test_agent_repair import host_for
from test_developer_gui import gui, wait_jobs


def test_construct_empty_ignores_default_and_cli_cannot_resume(tmp_path):
    host, loaded = host_for(tmp_path)
    original = {str(path): path.read_bytes() for path in host.candidate.rglob('*') if path.is_file()}
    session = DeveloperSession.create(host.service, None, mode='Construct', entry='gui')
    chat = session.conversation()
    manifest = json.loads((session.host.candidate / 'manifest.json').read_text())
    assert list(manifest['components']) == ['plans.default'] and not manifest['recovery_rules']
    assert session.host.baseline() == {'manifest.json': (session.host.candidate / 'manifest.json').read_bytes(),
                                       'plan.py': (session.host.candidate / 'plan.py').read_bytes()}
    assert host.manager.default_manifest_id() == loaded.manifest_id
    assert all(Path(path).read_bytes() == content for path, content in original.items())
    assert 'Construct' in chat.system_prompt
    with pytest.raises(ValueError, match='CLI'):
        DeveloperSession(host.service, session.identity).conversation()
    assert session.host.validate()['ok']
    assert session.host.publish()


def test_mode_entry_policy_and_host_reject_before_dispatch(tmp_path, monkeypatch):
    from lalc.agent_policy import MODE_TOOLS
    host, loaded = host_for(tmp_path)
    session = DeveloperSession.create(host.service, loaded.manifest_id)
    chat = session.conversation()
    chat.tools.allowed = frozenset({'read_manifest'})
    monkeypatch.setattr(chat.tools, 'publish', lambda: pytest.fail('forbidden dispatch'))
    result = read_json(chat.tools.call('publish', {}))
    assert result['isError'] and '不允许' in result['details']['message']
    monkeypatch.setitem(MODE_TOOLS, 'Construct', frozenset({'read'}))
    assert allowed_tools('Construct', 'gui') == ('read',)
    with pytest.raises(ValueError):
        allowed_tools('Construct', 'cli')


@pytest.mark.parametrize('mode', ['Construct', 'Repair'])
def test_knowledge_directory_creates_without_session_and_preserves_content(gui, monkeypatch, mode):
    from PySide6.QtGui import QDesktopServices
    app, window = gui
    page = window.repair_page
    page.new()
    page.mode.setCurrentItem(mode)
    assert page.session is None
    opened = []
    monkeypatch.setattr(QDesktopServices, 'openUrl', lambda url: opened.append(url.toLocalFile()) or True)
    root = window.service.data_root / 'knowledge'
    assert not root.exists()
    page.knowledge_action.trigger()
    assert root.is_dir() and opened == [str(root)]
    (root / 'keep.md').write_text('keep')
    page.knowledge_action.trigger()
    assert (root / 'keep.md').read_text() == 'keep' and len(opened) == 2
    assert page.session is None


def test_knowledge_directory_file_collision_preserves_original(gui, caplog):
    app, window = gui
    root = window.service.data_root / 'knowledge'
    root.write_text('original')
    window.repair_page.open_knowledge()
    assert root.read_text() == 'original' and '普通文件' in caplog.text


def test_manifest_reference_is_versioned_paged_and_never_imports(tmp_path, monkeypatch):
    host, first = host_for(tmp_path)
    reader = ManifestReference(host.manager)
    first_source = reader.source(first.manifest_id, 'components', 'steps.total')
    path = host.candidate / 'steps.total.py'
    path.write_text(path.read_text().replace('if value > 0', 'if value >= 0'))
    second_id = host.publish()
    second_source = reader.source(second_id, 'components', 'steps.total')
    assert first_source['component_id'] != second_source['component_id']
    monkeypatch.setattr(host.manager, '_load_module', lambda *a, **k: pytest.fail('read imported Python'))
    assert reader.source(first.manifest_id, 'components', 'steps.total') == first_source
    assert reader.structure(second_id, limit=1)['truncated']
    page = reader.source(second_id, 'components', 'steps.total', limit=1)
    assert page['start_line'] == 1 and page['next_offset'] == 1 and page['truncated']
    rest = reader.source(second_id, 'components', 'steps.total', offset=1)
    assert page['source'] + rest['source'] == second_source['source']
    assert reader.list(limit=1)['next_offset'] == 1
    before = host.manager.default_manifest_id()
    with pytest.raises(ValueError, match='成员'):
        reader.source(first.manifest_id, 'recovery_rules', 'steps.total')
    with pytest.raises(ValueError):
        reader.read('../default')
    with pytest.raises(ValueError):
        reader.read(str(uuid.uuid4()))
    assert host.manager.default_manifest_id() == before


@pytest.mark.parametrize('failure', ['hash', 'source_symlink', 'manifest_symlink', 'identity'])
def test_manifest_reference_rejects_corrupt_identity_and_paths(tmp_path, failure):
    host, loaded = host_for(tmp_path)
    reader = ManifestReference(host.manager)
    value = reader.read(loaded.manifest_id)
    manifest_path = host.manager.manifests_dir / f'{loaded.manifest_id}.json'
    digest = value['components']['steps.total']['component_id'].removeprefix('sha256:')
    source_path = host.manager.components_dir / f'{digest}.py'
    if failure == 'hash':
        source_path.write_text('corrupted')
    elif failure == 'source_symlink':
        content = source_path.read_bytes()
        source_path.unlink()
        outside = tmp_path / 'outside.py'
        outside.write_bytes(content)
        source_path.symlink_to(outside)
    elif failure == 'manifest_symlink':
        content = manifest_path.read_bytes()
        manifest_path.unlink()
        outside = tmp_path / 'outside.json'
        outside.write_bytes(content)
        manifest_path.symlink_to(outside)
    else:
        value['manifest_id'] = str(uuid.uuid4())
        manifest_path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        reader.source(loaded.manifest_id, 'components', 'steps.total')


def test_reference_read_does_not_execute_even_registered_side_effect_source(tmp_path):
    host, loaded = host_for(tmp_path)
    reader = ManifestReference(host.manager)
    value = reader.read(loaded.manifest_id)
    content = b'raise RuntimeError("reference must never execute")\n'
    digest = hashlib.sha256(content).hexdigest()
    (host.manager.components_dir / f'{digest}.py').write_bytes(content)
    value['components']['steps.total']['component_id'] = 'sha256:' + digest
    (host.manager.manifests_dir / f'{loaded.manifest_id}.json').write_text(json.dumps(value))
    assert reader.source(loaded.manifest_id, 'components', 'steps.total')['source'] == content.decode()


def test_first_send_uses_final_choices_and_preserves_manual_candidate(gui, monkeypatch):
    from lalc.agent_repair import RepairConversation
    app, window = gui
    page = window.repair_page
    manual = {path: path.read_bytes() for path in window.host.candidate.rglob('*') if path.is_file()}
    page.new()
    root = window.service.data_root / 'developer-sessions'
    existing = set(root.iterdir())
    page.mode.setCurrentItem('Repair')
    page.mode.setCurrentItem('Construct')
    page.baseline.setCurrentIndex(0)
    assert set(root.iterdir()) == existing and page.session is None
    calls = []
    async def run(self, message, args, **kwargs):
        calls.append((self.mode, message, kwargs['manifest_references']))
        self.append_user({'role': 'user', 'content': [{'type': 'text', 'text': message}]})
        return {'reason': 'answered', 'requests': 0, 'answer': {'message': 'saved'}}
    monkeypatch.setattr(RepairConversation, 'run', run)
    page.message.setPlainText('build from blank')
    page.send()
    wait_jobs(app, window)
    assert calls == [('Construct', 'build from blank', [])]
    assert page.session is not None and not page.mode.isEnabled() and not page.baseline.isEnabled()
    assert page.host.secrets is window.host.secrets
    assert all(path.read_bytes() == value for path, value in manual.items())
    assert json.loads((page.host.candidate / 'manifest.json').read_text())['components'].keys() == {'plans.default'}
    identity = page.session.identity
    page.new()
    item = next(page.history.item(i) for i in range(page.history.count())
                if identity == page.history.item(i).data(Qt.ItemDataRole.UserRole))
    page.open_session(item)
    wait_jobs(app, window)
    assert page.session.identity == identity and 'build from blank' in page.chat.toPlainText()


def test_new_session_initialization_failure_keeps_preparation(gui, monkeypatch):
    app, window = gui
    page = window.repair_page
    page.new()
    page.mode.setCurrentItem('Construct')
    page.baseline.setCurrentIndex(0)
    page.message.setPlainText('keep input')
    monkeypatch.setattr(DeveloperSession, 'create', lambda *a, **k: (_ for _ in ()).throw(ValueError('failed create')))
    errors = []
    monkeypatch.setattr(window, '_interact', lambda operation: catch(operation, errors))
    page.send()
    wait_jobs(app, window)
    assert errors and page.session is None and page.message.toPlainText() == 'keep input'
    assert page.mode.isEnabled() and page.baseline.isEnabled()


def catch(operation, errors):
    try:
        operation()
    except ValueError as error:
        errors.append(str(error))


def test_gui_opens_cli_history_and_manual_validation_uses_session(gui):
    app, window = gui
    identity = window.host.manager.default_manifest_id()
    session = DeveloperSession.create(window.service, identity)
    chat = session.conversation()
    chat.append_user({'role': 'user', 'content': [{'type': 'text', 'text': 'CLI message'}]})
    page = window.repair_page
    page.refresh_sessions()
    item = next(page.history.item(i) for i in range(page.history.count())
                if session.identity == page.history.item(i).data(Qt.ItemDataRole.UserRole))
    page.open_session(item)
    wait_jobs(app, window)
    assert 'CLI message' in page.chat.toPlainText() and page.mode.currentRouteKey() == 'Repair'
    page.validate()
    wait_jobs(app, window)
    restored = DeveloperSession(window.service, session.identity).conversation()
    assert any('完整校验' in str(message) for message in restored.history)
    assert window.host.conversation is None


def test_history_read_obeys_session_lock_and_restored_error_is_not_duplicated(gui, monkeypatch):
    from lalc.process_lock import ProcessLock
    app, window = gui
    page = window.repair_page
    chat = page.host.conversation
    details = {'message': 'provider failed', 'stage': 'provider_request', 'round': 1}
    chat.log.record({'type': 'repair_error', **details})
    monkeypatch.setattr(page.diagnostics, 'show_error', lambda: None)
    page.answered({'reason': 'error', 'requests': 1, 'diagnostics': details})
    assert page.diagnostics.errors.count() == 1
    previous = page.chat.toPlainText()
    with ProcessLock('candidate:' + str(page.host.candidate.resolve())):
        with pytest.raises(OSError):
            page.reload_history()
    assert page.chat.toPlainText() == previous


def test_manual_publish_and_latest_cli_messages_restore_in_gui(gui):
    app, window = gui
    page = window.repair_page
    cli = DeveloperSession(window.service, page.session.identity).conversation()
    cli.append_user({'role': 'user', 'content': [{'type': 'text', 'text': 'new CLI input'}]})
    page.publish()
    wait_jobs(app, window)
    assert 'new CLI input' in page.chat.toPlainText()
    assert page.host.manager.list_manifests()[0]['manifest_id'] in page.chat.toPlainText()
    restored = DeveloperSession(window.service, page.session.identity).conversation()
    assert 'Manifest ID' in str(restored.history[-1])


def test_failed_initial_settings_still_preserve_user_message_and_references(tmp_path, monkeypatch):
    host, loaded = host_for(tmp_path)
    session = DeveloperSession.create(host.service, loaded.manifest_id, entry='gui')
    chat = session.conversation()
    def fail(*args, **kwargs):
        raise ValueError('missing settings')
    monkeypatch.setattr('lalc.agent_repair.settings_snapshot', fail)
    result = asyncio.run(chat.run('do not lose first input', SimpleNamespace(),
                                 manifest_references=[loaded.manifest_id]))
    assert result['status'] == 'incomplete'
    restored = session.conversation()
    assert 'do not lose first input' in str(restored.history)
    assert loaded.manifest_id in str(restored.history)


def test_session_list_does_not_stat_disappearing_pending_directories(gui, monkeypatch):
    app, window = gui
    root = window.service.data_root / 'developer-sessions'
    (root / '.pending-creating').mkdir()
    original = Path.lstat
    def lstat(path, *args, **kwargs):
        if path.name.startswith('.pending-'):
            raise FileNotFoundError('another CLI finished creating its Session')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'lstat', lstat)
    window.repair_page.refresh_sessions()
    assert window.repair_page.history.count() == 1
