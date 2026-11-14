"""覆盖上下文设置、内存图片编号查询、历史引用及损坏状态保护。

项目根目录运行：.venv/bin/python -m pytest -q tests/test_agent_context.py
"""

import base64
import json

import pytest

from lalc.agent_context import checked_session_file, context_bootstrap
from lalc.agent_repair import RepairLog
from lalc.agent_settings import checked_options, load_settings, save_options


def test_context_defaults_and_provider_profiles(tmp_path):
    assert load_settings(tmp_path, for_use=False)['provider'] == 'deepseek'
    local = load_settings(tmp_path, {'provider': 'llama.cpp'}, for_use=False)
    assert local['base_url'] == 'http://localhost:12138/v1' and local['model'] is None
    options = save_options(tmp_path, context_compaction_mode='fixed', context_compaction_tokens=1,
                           context_compaction_ratio=90, context_image_limit=12)
    assert options['context_compaction_tokens'] == 1
    assert options['context_compaction_ratio'] == 90


@pytest.mark.parametrize('changes', [
    {'context_compaction_ratio': 19}, {'context_compaction_ratio': 91},
    {'context_compaction_ratio': True}, {'context_image_limit': 0},
    {'context_compaction_tokens': -1}, {'context_compaction_mode': 'other'},
])
def test_context_settings_reject_invalid_values(changes):
    with pytest.raises(ValueError):
        checked_options(changes)


def test_bootstrap_keeps_image_ids_and_original_evidence(tmp_path):
    log = RepairLog(tmp_path)
    image = {'type': 'image', 'mimeType': 'image/png', 'data': base64.b64encode(b'original').decode()}
    message = {'role': 'user', 'content': [{'type': 'text', 'text': 'old request'}, image]}
    log.record({'type': 'session_message', 'message': message})
    result = context_bootstrap(log, [message], checked_options({}))
    assert result['history'][0]['content'][1]['type'] == 'text'
    assert 'image_id=1:0' in result['history'][0]['content'][1]['text']
    assert 'original' not in json.dumps(result)
    from lalc.agent_log import read_events
    assert list(read_events(log.root / 'events.jsonl'))[0]['event']['message'] == message


def test_missing_or_partial_pi_state_is_not_reimported(tmp_path):
    directory = tmp_path / 'pi'
    path = checked_session_file(directory)
    (directory / 'initialized').write_text('1\n')
    with pytest.raises(ValueError, match='丢失'):
        checked_session_file(directory)
    path.write_text('{"type":"session"}')
    original = path.read_bytes()
    with pytest.raises(ValueError, match='不完整'):
        checked_session_file(directory)
    assert path.read_bytes() == original


def test_image_references_are_recorded_and_rebuilt_without_shared_file(tmp_path):
    import hashlib
    from lalc.agent_log import read_events
    log = RepairLog(tmp_path)
    image = {'type': 'image', 'mimeType': 'image/png', 'data': base64.b64encode(b'new').decode()}
    event = {'type': 'tool_execution_end', 'result': {'content': [image, image]}}
    log.record(event)
    digest = hashlib.sha256(b'new').hexdigest()
    assert log.image_references([digest]) == {digest: '1:0'}
    assert list(read_events(log.root / 'events.jsonl'))[0]['event'] == event
    log.record(event)
    assert log.image_references([digest]) == {digest: '1:0'}
    rebuilt = context_bootstrap(log, [], checked_options({}))
    assert rebuilt['image_ids'] == log.image_references([digest])
    assert not list(log.root.rglob('*image-index*'))


@pytest.mark.parametrize('digests', [None, {}, 'a' * 64, [1], ['bad'], ['G' * 64]])
def test_image_references_reject_invalid_query(tmp_path, digests):
    with pytest.raises(ValueError, match='SHA-256'):
        RepairLog(tmp_path).image_references(digests)


def test_image_references_reject_unrecorded_image(tmp_path):
    log = RepairLog(tmp_path)
    with pytest.raises(ValueError, match='尚无已记录'):
        log.image_references(['a' * 64])
    assert log.image_references([]) == {}
