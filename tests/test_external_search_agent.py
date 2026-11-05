"""真实 pi／codesearch 验证跨轮复用与哈希绑定检索，仅使用本机替身和本地资源。

项目根目录运行：QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --run-agent-tests -q tests/test_external_search_agent.py
默认跳过；不连接远端模型或参考仓库，不代替 Windows 验收。
"""

import asyncio
from pathlib import Path

import pytest

from test_agent_repair_agent import conversation
from agent_test_server import agent_server
from test_knowledge import repository, git
from lalc.agent_log import read_events
from lalc.knowledge import KnowledgeLibrary, knowledge_root

pytestmark = pytest.mark.agent


@pytest.fixture
def library(tmp_path):
    knowledge_root(tmp_path, create=True)
    instance = KnowledgeLibrary(tmp_path, lambda: None)
    try:
        yield instance
    finally:
        instance.codesearch.close()


def test_real_codesearch_version_update_and_process_reuse(library, repository, monkeypatch):
    resources = Path(__file__).resolve().parents[1] / 'codesearch_resources'
    binary = resources / 'codesearch'
    if not binary.exists():
        pytest.skip('需要显式准备本机 codesearch 基础版和固定模型')
    monkeypatch.setenv('LALC_CODESEARCH', str(binary))
    monkeypatch.setenv('LALC_CODESEARCH_MODELS', str(resources / 'models'))
    repo, ids = repository
    original = library._run
    def run(path, args, **kwargs):
        if args[0] == 'fetch':
            git(path, 'update-ref', 'refs/remotes/origin/main', ids[2])
            return {'ok': True, 'stdout': '', 'error': ''}
        return original(path, args, **kwargs)
    monkeypatch.setattr(library, '_run', run)
    result = library.search_hybrid('version documentation')
    assert result['items'], result
    assert result['sync'][0]['update']['ok'], result
    hit = result['items'][0]
    assert library.read(**hit['read_arguments'])[0]['sha256'] == hit['sha256']
    pid = library.codesearch.process.pid
    library.begin_round()
    next_result = library.search_hybrid('version documentation')
    assert next_result['sync'][0]['update']['unchanged']
    assert library.codesearch.process.pid == pid
    assert next_result['items'][0]['commit'] == ids[2]
    library.codesearch.process.kill()
    library.codesearch.process.wait(timeout=5)
    restarted = library.search_hybrid('version documentation')
    assert restarted['items'] and library.codesearch.process.pid != pid


def test_pi_is_reused_across_distinct_host_event_loops(conversation):
    chat, options, state = conversation
    assert asyncio.run(chat.run('ROUND_ONE', options))['status'] == 'completed'
    process = chat.host.service.pi_process.process
    first_pid = process.pid
    assert asyncio.run(chat.run('ROUND_TWO', options))['status'] == 'completed'
    assert chat.host.service.pi_process.process.pid == first_pid
    events = [row['event'] for row in read_events(chat.log.root / 'events.jsonl')]
    records = [row for row in events if row.get('type') == 'pi_process']
    assert records[-1]['reused'] and records[-1]['pid'] == first_pid
    assert state['calls'][-1]['messages']
    chat.host.service.shutdown()
    assert process.poll() is not None


def test_pi_changed_connection_settings_recreate_process(conversation):
    chat, options, state = conversation
    assert asyncio.run(chat.run('FIRST', options))['status'] == 'completed'
    first = chat.host.service.pi_process.process
    # 同一替身支持任意模型 ID；改变已声明模型要求新的 provider 配置。
    state['models'] = [{'id': 'second-model'}]
    options.model = 'second-model'
    assert asyncio.run(chat.run('SECOND', options))['status'] == 'completed'
    assert chat.host.service.pi_process.process.pid != first.pid
    assert first.poll() is not None


def test_pi_mid_round_exit_is_not_replayed_and_next_round_restarts(conversation):
    chat, options, state = conversation
    state['block'] = True
    old = []
    async def interrupted():
        task = asyncio.create_task(chat.run('INTERRUPTED_ROUND', options))
        try:
            async with asyncio.timeout(10):
                while not state['started'].is_set():
                    if task.done():
                        pytest.fail(str(task.result()))
                    await asyncio.sleep(.01)
            process = chat.host.service.pi_process.process
            old.append(process.pid)
            process.kill()
            return await task
        finally:
            state['release'].set()
            await asyncio.gather(task, return_exceptions=True)
    result = asyncio.run(interrupted())
    assert result['status'] == 'incomplete' and len(state['calls']) == 1
    state['block'] = False
    continued = asyncio.run(chat.run('NEW_ROUND', options))
    assert continued['status'] == 'completed' and len(state['calls']) == 2
    assert chat.host.service.pi_process.process.pid != old[0]
