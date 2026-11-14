"""覆盖候选源码删除的确认、权限、路径及草稿变更保护。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_delete_component.py
"""

import pytest

from lalc.agent_policy import allowed_tools
from lalc.developer import candidate_files
from test_agent_repair import host_for
from test_repair_tools import invoke


@pytest.fixture
def deletion(tmp_path):
    host, _ = host_for(tmp_path)
    tools = host.conversation.tools
    tools.allowed = allowed_tools('Repair', 'gui')
    tools.on_feedback = lambda request: request.finish('confirmed', '确认删除 steps.total.py')
    return host, tools


def test_only_target_deleted_without_manifest_or_published_changes(deletion):
    host, tools = deletion
    before = candidate_files(host.candidate)
    published = candidate_files(host.manager.components_dir)
    result = invoke(tools, 'delete_component', filename='steps.total.py', impact='用户要求删除；移除后 Manifest 登记将失效。')
    assert result['details']['deleted']
    assert candidate_files(host.candidate) == {k: v for k, v in before.items() if k != 'steps.total.py'}
    assert tools.deleted_files == {'steps.total.py'}
    assert candidate_files(host.manager.components_dir) == published


@pytest.mark.parametrize('status,text', [('skipped', ''), ('confirmed', ''), ('confirmed', '不要删除'),
                                         ('confirmed', '确认删除 other.py')])
def test_refusal_or_wrong_confirmation_preserves_everything(deletion, status, text):
    host, tools = deletion
    before = candidate_files(host.candidate)
    tools.on_feedback = lambda request: request.finish(status, text)
    result = invoke(tools, 'delete_component', filename='steps.total.py', impact='删除影响')
    assert not result['details']['deleted']
    assert candidate_files(host.candidate) == before
    assert not tools.deleted_files


@pytest.mark.parametrize('filename', ['../outside.py', '/outside.py', 'manifest.json', 'missing.py',
                                      'a/../steps.total.py', './steps.total.py', 'a\\b.py', 'C:foo.py'])
def test_bad_paths_never_prompt(deletion, filename):
    host, tools = deletion
    before = candidate_files(host.candidate)
    tools.on_feedback = lambda request: pytest.fail('无效路径不得请求确认')
    assert invoke(tools, 'delete_component', filename=filename, impact='删除影响')['isError']
    assert candidate_files(host.candidate) == before


def test_symlink_rejected(deletion):
    host, tools = deletion
    (host.candidate / 'link.py').symlink_to(host.candidate / 'steps.total.py')
    tools.on_feedback = lambda request: pytest.fail('符号链接不得请求确认')
    assert invoke(tools, 'delete_component', filename='link.py', impact='删除影响')['isError']
    assert (host.candidate / 'steps.total.py').exists()


@pytest.mark.parametrize('change', ['target', 'manifest', 'cancel'])
def test_changes_or_cancellation_while_waiting_prevent_deletion(deletion, change):
    host, tools = deletion
    def feedback(request):
        if change == 'cancel':
            tools.cancelled.set()
        else:
            path = host.candidate / ('steps.total.py' if change == 'target' else 'manifest.json')
            path.write_text('changed', encoding='utf-8')
        request.finish('confirmed', '确认删除 steps.total.py')
    tools.on_feedback = feedback
    assert invoke(tools, 'delete_component', filename='steps.total.py', impact='删除影响')['isError']
    assert (host.candidate / 'steps.total.py').exists()
    assert not tools.deleted_files


def test_permissions_and_missing_feedback(deletion):
    host, tools = deletion
    for mode in ('Construct', 'Repair'):
        assert 'delete_component' in allowed_tools(mode, 'gui')
    assert 'delete_component' not in allowed_tools('Repair', 'cli')
    assert 'delete_component' not in allowed_tools('Repair', 'runtime')
    assert 'delete_component' not in allowed_tools('Repair', 'runtime', runtime_feedback_enabled=True)
    for enabled in (False, True):
        tools.allowed = allowed_tools('Repair', 'runtime', runtime_feedback_enabled=enabled)
        tools.on_feedback = lambda request: pytest.fail('Runtime 不得进入删除确认')
        assert invoke(tools, 'delete_component', filename='steps.total.py', impact='影响')['isError']
    tools.allowed = allowed_tools('Repair', 'cli')
    assert invoke(tools, 'delete_component', filename='steps.total.py', impact='影响')['isError']
    tools.allowed = allowed_tools('Repair', 'gui')
    tools.on_feedback = None
    assert invoke(tools, 'delete_component', filename='steps.total.py', impact='影响')['isError']
    assert (host.candidate / 'steps.total.py').exists()
