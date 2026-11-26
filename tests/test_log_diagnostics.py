"""覆盖日志组合查询、AVIF 传输、知识库开关与紧凑 JSON；不启动 Agent。

项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_log_diagnostics.py
"""

import base64
import json
from io import BytesIO

import pytest
from PIL import Image

from lalc.agent_policy import KNOWLEDGE_TOOLS, allowed_tools
from lalc.agent_settings import save_options, settings_document
from lalc.run_logs import display_json, image_path, query_trace, run_log_counts, run_summary
from lalc.run_log_sharing import export_log, import_log
from test_agent_repair import host_for


@pytest.fixture
def gui_run_tools(tmp_path):
    """以允许读取本机日志的工作台入口验证合成证据。"""
    from lalc.developer_session import DeveloperSession
    host, saved = host_for(tmp_path)
    return DeveloperSession.create(host.service, saved.manifest_id, entry="gui").conversation().tools
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


def test_tools_search_continuation_and_evidence_avif_roundtrip(tmp_path, gui_run_tools):
    tools = gui_run_tools
    root = tools.library.data_root
    write_trace(root, 2, [dict(sequence=sequence, event='component_log', level='info', message='hit')
                          for sequence in (1, 2)])
    write_trace(root, 1, [dict(sequence=1, event='component_log', level='info', message='hit', evidence_id='1/2')])
    path = root / 'evidence/1/2.avif'
    path.parent.mkdir(parents=True)
    Image.new('RGB', (20, 10), 'red').save(path, quality=65, speed=8)
    page = tools.search_run_logs('HIT', run_id=2, limit=1)['details']
    next_page = tools.search_run_logs('HIT', run_id=2, limit=1, **page['next'])['details']
    assert [(p['matches'][0]['run_id'], p['matches'][0]['sequence']) for p in (page, next_page)] == [(2, 1), (2, 2)]
    assert next_page['next'] is None
    assert tools.read_run_log(1, evidence_id='1/2')['content'][-1]['mimeType'] == 'image/jpeg'
    export_log(root, 1, tmp_path / 'log.zip')
    identity = import_log(root, tmp_path / 'log.zip')
    imported = root / 'imported-run-logs' / identity
    assert image_path(imported, 1, {'evidence_id': '1/2'}).read_bytes() == path.read_bytes()
    listing = tools.list_runs()['details']
    assert listing['run_ids'] == [3, 2, 1]
    imported_run, local_run = listing['runs'][:2]
    assert imported_run['origin'] == 'imported' and imported_run['original_run_id'] == 1
    assert local_run['origin'] == 'local' and 'original_run_id' not in local_run
    result = tools.read_run_log(3, evidence_id='1/2')
    assert result['details']['run_id'] == 3 and result['details']['original_run_id'] == 1
    assert result['content'][-1]['mimeType'] == 'image/jpeg'
    hit = tools.search_run_logs('hit', run_id=3)['details']['matches'][0]
    assert hit['run_id'] == 3 and hit['record']['evidence_id'] == '1/2'
    assert tools.search_run_logs('hit', run_id=3, limit=1)['details']['next'] is None
    with pytest.raises(ValueError, match='游标'):
        tools.search_run_logs('hit', run_id=3, **page['next'])
    tools.read_other_runs = False
    assert 3 not in tools.list_runs()['details']['run_ids']
    with pytest.raises(ValueError, match='日志不可用'):
        tools.read_run_log(3)
    with pytest.raises(ValueError, match='日志不可用'):
        tools.search_run_logs('hit', run_id=3)
    with pytest.raises(TypeError):
        tools.search_run_logs('hit')
    with pytest.raises(TypeError):
        tools.search_run_logs('hit', run_id=1, all_runs=True)


def test_list_runs_summarizes_large_terminal_result(gui_run_tools):
    tools = gui_run_tools
    result = {"status": "interrupted", "items": [{"result": "failure"}] * 10_000,
              "all_tasks_succeeded": False, "failure_code": "branch_limit", "failure_message": "故障" * 2_000,
              "output": {"raw": "omitted"}}
    write_trace(tools.library.data_root, 1, [
        {"sequence": 1, "event": "run_started"},
        {"sequence": 2, "event": "run_finished", "result": result},
    ])
    listing = tools.list_runs(limit=1)
    row = listing["details"]["runs"][0]
    assert row["status"] == "interrupted"
    assert row["result"] == {"task_count": 10_000, "all_tasks_succeeded": False, "failure_code": "branch_limit"}
    assert len(row["failure_reason"]) == 512 and row["failure_reason"].endswith("…")
    assert len(listing["content"][0]["text"].encode("utf-8")) < 2_000
    assert tools.read_run_log(1, start_sequence=2, limit=1)["details"]["events"][0]["result"] == result


@pytest.mark.parametrize('extension', ['avif', 'png'])
def test_tool_renders_exact_action_on_shared_evidence(gui_run_tools, extension):
    tools = gui_run_tools
    root = tools.library.data_root
    common = {'event': 'trusted_action_returned', 'debug_image': {'evidence_id': '1/2'}}
    write_trace(root, 1, [
        dict(common, sequence=1, logical_name='observe.match_asset',
             return_value=[{'x': 200, 'y': 220, 'width': 200, 'height': 180}]),
        dict(common, sequence=2, logical_name='observe.ocr', return_value={'items': [
            {'text': '確認', 'box': {'x': 600, 'y': 420, 'width': 200, 'height': 150}}]}),
        dict(common, sequence=3, logical_name='control.click', inputs={'centerxy': [900, 300]}),
        dict(common, sequence=4, logical_name='observe.match_asset', return_value=[]),
        dict(common, sequence=5, logical_name='observe.match_asset_group_in_regions',
             return_value=[[], [{'x': 300, 'y': 220, 'width': 200, 'height': 180}]]),
        dict(common, sequence=6, logical_name='observe.ocr', debug_image={'image_unavailable': True}),
        dict(common, sequence=7, logical_name='control.click', debug_image={'evidence_id': '2/2'}),
        dict(common, sequence=8, logical_name='control.scroll'),
        dict(common, sequence=9, logical_name='observe.match_asset', event='trusted_action_started'),
    ])
    path = root / f'evidence/1/2.{extension}'
    path.parent.mkdir(parents=True)
    Image.new('RGB', (2560, 1280), 'white').save(path)
    original = path.read_bytes()

    def preview(result):
        part = result['content'][-1]
        assert part['mimeType'] == 'image/jpeg'
        with Image.open(BytesIO(base64.b64decode(part['data']))) as image:
            assert image.size == (1280, 640)
            return image.copy()

    def red_near(image, x, y):
        return any(r > g + 70 for r, g, _ in image.crop((x - 2, y - 2, x + 3, y + 3)).get_flattened_data())

    raw = preview(tools.read_run_log(1, evidence_id='1/2'))
    for sequence, point in [(1, (200, 160)), (2, (400, 260)), (3, (450, 330)), (5, (250, 160))]:
        result = tools.read_run_log(1, render_sequence=sequence)
        assert [e['sequence'] for e in result['details']['events']] == [sequence]
        assert result['details']['render_sequence'] == sequence
        assert result['details']['next_sequence'] is None
        rendered = preview(result)
        assert not red_near(raw, *point) and red_near(rendered, *point)
        if sequence == 2:
            assert not red_near(rendered, 200, 160)
            assert any(r > g + 70 for r, g, _ in rendered.crop((305, 213, 324, 226)).get_flattened_data())
    assert preview(tools.read_run_log(1, render_sequence=4)).tobytes() == raw.tobytes()
    assert path.read_bytes() == original
    for sequence, message in [(True, '正整数'), (10, '事件序号不存在'), (6, '截图证据不可用'),
                              (7, '截图证据不可用'), (8, '动作结束事件'), (9, '动作结束事件')]:
        with pytest.raises(ValueError, match=message):
            tools.read_run_log(1, render_sequence=sequence)
    with pytest.raises(ValueError, match='仅与 run_id'):
        tools.read_run_log(1, evidence_id='1/2', render_sequence=1)


@pytest.mark.parametrize('outcome', ['success', 'failed'])
@pytest.mark.parametrize('save', [True, False])
def test_match_only_references_existing_evidence(tmp_path, monkeypatch, outcome, save):
    service, window, manifest = make_service(tmp_path,
        f'    ctx.action("observe.capture_screen", save={save})\n'
        '    ctx.action("observe.match_asset", asset="ui/test")\n')
    def match(*args, **kwargs):
        if outcome == 'failed':
            raise ValueError('文字错误')
        return []
    monkeypatch.setattr(service, '_match_asset', match)
    state = finish(service, service.start('steps.drive', {}, manifest_id=manifest))
    assert sum(r['event'] == 'screenshot_saved' for r in state['trace']) == int(save)
    action = next(r for r in state['trace'] if r['event'] == 'trusted_action_' + ('returned' if outcome == 'success' else 'failed')
                  and r['logical_name'] == 'observe.match_asset')
    assert action['inputs']['asset'] == 'ui/test'
    assert bool(action['debug_image'].get('evidence_id')) is save
    assert window.captures == 1


def test_ocr_does_not_backfill_after_an_unsaved_capture(tmp_path, monkeypatch):
    service, _, manifest = make_service(tmp_path,
        '    ctx.action("observe.capture_screen")\n'
        '    ctx.action("observe.ocr")\n'
        '    ctx.action("observe.capture_screen", save=False)\n'
        '    ctx.action("observe.ocr")\n')
    monkeypatch.setattr(service, '_ocr', lambda **_: {'observation': service._focused_session.observation,
                                                     'region': {'x': 0, 'y': 0, 'width': 1, 'height': 1}, 'items': []})
    state = finish(service, service.start('steps.drive', {}, manifest_id=manifest))
    assert sum(r['event'] == 'screenshot_saved' for r in state['trace']) == 1
    records = [r for r in state['trace'] if r['event'] == 'trusted_action_returned'
               and r['logical_name'] == 'observe.ocr']
    assert records[0]['debug_image']['observation'] == records[0]['return_value']['observation']
    assert records[1]['debug_image'] == {'image_unavailable': True}


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



def test_read_run_log_counts_whole_run_independent_of_filters_and_paging(gui_run_tools):
    """分页、筛选及正文中的等级字样均不改变整份快照的显式等级统计。"""
    tools = gui_run_tools
    root = tools.library.data_root
    records = [
        dict(sequence=1, event="component_log", level="warning", message="first"),
        dict(sequence=2, event="component_log", level="info", message="warning error"),
        dict(sequence=3, event="trusted_action_failed", logical_name="observe.test", message="failed"),
        dict(sequence=4, event="component_log", level="error", message="last"),
        dict(sequence=5, event="component_log", level="WARNING", message="upper"),
    ]
    path = write_trace(root, 1, records)
    with path.open("a", encoding="utf-8") as stream:
        stream.write('broken\n[]\n{"sequence":6,"level":"error"')
    expected = dict(scope="full_run", warning=2, error=1, damaged_records=2)
    first = tools.read_run_log(1, limit=1)["details"]
    filtered = tools.read_run_log(1, start_sequence=2, levels=["info"], logical_name="missing")["details"]
    assert first["log_counts"] == filtered["log_counts"] == expected
    assert len(first["events"]) == 1 and filtered["events"] == []
    assert json.loads(tools.read_run_log(1)["content"][0]["text"])["log_counts"] == expected
    with path.open("a", encoding="utf-8") as stream:
        stream.write('}\n')
    assert run_log_counts(root, 1) == dict(expected, error=2)


def test_log_count_zeroes_and_cancellation(tmp_path):
    """空日志明确返回零；扫描仍响应取消，损坏等级不导致计数崩溃。"""
    write_trace(tmp_path, 1, [])
    assert run_log_counts(tmp_path, 1) == dict(scope="full_run", warning=0, error=0, damaged_records=0)
    write_trace(tmp_path, 1, [dict(level=["warning"], message="bad level")])
    assert run_log_counts(tmp_path, 1)["warning"] == 0
    def cancelled():
        raise RuntimeError("cancelled")
    with pytest.raises(RuntimeError, match="cancelled"):
        run_log_counts(tmp_path, 1, check=cancelled)
