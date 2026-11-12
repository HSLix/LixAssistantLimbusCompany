"""覆盖日志组合查询、AVIF 传输、知识库开关与紧凑 JSON；不启动 Agent。

项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_log_diagnostics.py
"""

import json

import pytest
from PIL import Image

from lalc.agent_policy import KNOWLEDGE_TOOLS, allowed_tools
from lalc.agent_settings import save_options, settings_document
from lalc.run_logs import display_json, image_path, query_trace, run_summary
from lalc.run_log_sharing import export_log, import_log
from test_agent_repair import host_for
from test_workflow_observability import make_service, finish


def write_trace(root, run_id, records):
    path = root / 'traces' / f'{run_id}.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(record, ensure_ascii=False) + '\n' for record in records), encoding="utf-8")
    return path


def test_filtered_paging_cross_run_search_and_incomplete_records(tmp_path):
    records = [dict(sequence=i, event='component_log', logical_name='steps.test',
                    level='error' if i % 2 else 'info', message='MiXeD 关键字') for i in range(1, 8)]
    path = write_trace(tmp_path, 2, records)
    with path.open('a', encoding="utf-8") as stream:
        stream.write('broken\n{"sequence":8')
    write_trace(tmp_path, 1, [dict(records[0], message='mixed older')])
    first = query_trace(tmp_path, [2, 1], keyword='mixed', levels=['error'], logical_name='steps.test', limit=2)
    assert [m['sequence'] for m in first['matches']] == [1, 3]
    assert first['next'] == dict(start_run_id=2, start_sequence=5)
    second = query_trace(tmp_path, [2, 1], keyword='mixed', levels=['error'],
                         logical_name='steps.test', start_sequence=5, limit=2)
    assert [m['sequence'] for m in second['matches']] == [5, 7]
    assert second['next'] == dict(start_run_id=1, start_sequence=1)
    assert second['damaged_records'] == 1
    assert not query_trace(tmp_path, [2], keyword='absent')['matches']
    assert not query_trace(tmp_path, [2], logical_name='other')['matches']
    assert run_summary(tmp_path, 2)['status'] == 'unknown'


def test_tools_search_continuation_and_evidence_avif_roundtrip(tmp_path):
    host, _ = host_for(tmp_path)
    tools, root = host.conversation.tools, host.service.data_root
    write_trace(root, 2, [dict(sequence=1, event='component_log', level='info', message='hit')])
    write_trace(root, 1, [dict(sequence=1, event='component_log', level='info', message='hit', evidence_id='1/2')])
    path = root / 'evidence/1/2.avif'
    path.parent.mkdir(parents=True)
    Image.new('RGB', (20, 10), 'red').save(path, quality=65, speed=8)
    page = tools.search_run_logs('HIT', all_runs=True, limit=1)['details']
    next_page = tools.search_run_logs('HIT', all_runs=True, limit=1, **page['next'])['details']
    assert [p['matches'][0]['run_id'] for p in (page, next_page)] == [2, 1]
    assert next_page['next'] is None
    assert tools.read_run_log(1, evidence_id='1/2')['content'][-1]['mimeType'] == 'image/jpeg'
    target = tmp_path / 'imported'
    target.mkdir()
    export_log(root, 1, tmp_path / 'log.zip')
    identity = import_log(target, tmp_path / 'log.zip')
    imported = target / 'imported-run-logs' / identity
    assert image_path(imported, 1, {'evidence_id': '1/2'}).read_bytes() == path.read_bytes()
    with pytest.raises(ValueError):
        tools.search_run_logs('hit')
    with pytest.raises(ValueError):
        tools.search_run_logs('hit', run_id=1, all_runs=True)


@pytest.mark.parametrize('outcome', ['success', 'failed'])
def test_match_never_auto_saves_even_on_error(tmp_path, monkeypatch, outcome):
    service, window, manifest = make_service(tmp_path,
        '    ctx.action("observe.capture_screen")\n'
        '    ctx.action("observe.match_asset", asset="ui/test")\n')
    def match(*args, **kwargs):
        if outcome == 'failed':
            raise ValueError('文字错误')
        return []
    monkeypatch.setattr(service, '_match_asset', match)
    state = finish(service, service.start('steps.drive', {}, manifest_id=manifest))
    assert not any(r['event'] == 'screenshot_saved' for r in state['trace'])
    action = next(r for r in state['trace'] if r['event'] == 'trusted_action_' + ('returned' if outcome == 'success' else 'failed')
                  and r['logical_name'] == 'observe.match_asset')
    assert action['inputs']['asset'] == 'ui/test' and 'debug_image' not in action
    assert window.captures == 1


@pytest.mark.parametrize('name,arguments', [('observe.ocr', {}), ('control.drag', {'x': 1, 'y': 1, 'end_x': 2, 'end_y': 2, 'seconds': 0.01})])
def test_ocr_and_drag_still_auto_save(tmp_path, monkeypatch, name, arguments):
    service, _, manifest = make_service(tmp_path,
        '    ctx.action("observe.capture_screen")\n'
        f'    ctx.action({name!r}, **{arguments!r})\n')
    monkeypatch.setattr(service, '_ocr', lambda **_: {'observation': 1, 'region': {'x': 0, 'y': 0, 'width': 1, 'height': 1}, 'items': []})
    state = finish(service, service.start('steps.drive', {}, manifest_id=manifest))
    assert any(r['event'] == 'screenshot_saved' for r in state['trace']), state['result']


def test_knowledge_switch_applies_to_both_policies_and_is_persisted(tmp_path):
    assert settings_document(tmp_path)['knowledge_enabled'] is True
    save_options(tmp_path, knowledge_enabled=False)
    assert settings_document(tmp_path)['knowledge_enabled'] is False
    for entry in ('gui', 'runtime'):
        allowed = allowed_tools('Repair', entry, knowledge_enabled=False)
        assert not set(allowed) & set(KNOWLEDGE_TOOLS)
        assert 'read_agent_session' in allowed


def test_compact_arrays_keep_json_values_and_nested_structure():
    value = {'centerxy': [80, 90], 'items': [{'box': [1, 2, 3, 4], 'text': '[\n80,\n90\n]'}], 'long': list(range(100))}
    formatted = display_json(value)
    assert '"centerxy": [80, 90]' in formatted
    assert '"items": [\n' in formatted and '"long": [\n' in formatted
    assert json.loads(formatted) == value


def test_local_time_is_a_snapshot_and_never_changes_system_prompt(monkeypatch):
    from datetime import datetime, timezone, timedelta
    from lalc import agent_prompts
    prompt = agent_prompts.system_prompt('Repair')
    class Clock:
        value = datetime(2026, 11, 12, 10, tzinfo=timezone(timedelta(hours=8)))

        @classmethod
        def now(cls):
            return cls.value

    monkeypatch.setattr(agent_prompts, 'datetime', Clock)
    first = agent_prompts.local_time_snapshot()
    Clock.value += timedelta(hours=1)
    second = agent_prompts.local_time_snapshot()
    assert first != second and first['now'] != second['now']
    assert agent_prompts.system_prompt('Repair') == prompt
