"""覆盖 pi 管道聚合负载省略、有界读取和通信失败，不启动真实 Agent。

项目根目录运行：.venv/bin/python -m pytest -q tests/test_pi_process.py
"""

import asyncio
import io
import json
import queue
from types import SimpleNamespace

import pytest

from lalc.pi_process import EVENT_LIMIT, READ_CHUNK, PiProcess
from lalc.pi_probe import PiExited


class BoundedStream(io.BytesIO):
    """确保读取端不会一次申请整条超大消息。"""

    def readline(self, size=-1):
        assert 0 < size <= READ_CHUNK
        return super().readline(size)


def read_events(data, *, stderr=False):
    process, events, shown = PiProcess(), queue.Queue(), []
    process.show = shown.append
    process._read(BoundedStream(data), events, stderr=stderr)
    return list(events.queue), shown


@pytest.mark.parametrize("size", [8, EVENT_LIMIT + 100])
def test_agent_end_payload_omitted_and_settled_preserved(size):
    data = b'{"type":"agent_end","messages":["' + b'x' * size + b'"],"willRetry":false}\n'
    rows, _ = read_events(data + b'{"type":"agent_settled","aborted":true}\n')
    assert rows == [
        {"type": "agent_end", "payload_omitted": True, "received_bytes": len(data)},
        {"type": "agent_settled", "aborted": True}, None,
    ]


@pytest.mark.parametrize("prefix,kind", [
    (b'{"type":"message_end","message":"', "message_end"),
    (b'{"messages":"', "unknown"),
    (b'{"type":"turn_end","toolResults":"', "turn_end"),
])
def test_oversized_required_or_unknown_event_fails_with_safe_diagnostics(prefix, kind):
    rows, _ = read_events(b'{"type":"turn_start"}\n' + prefix + b'SENSITIVE' * (EVENT_LIMIT // 9 + 1))
    assert rows[0] == {"type": "turn_start"}
    error = rows[1]
    assert isinstance(error, ValueError)
    for expected in ["channel=stdout", f"type={kind}", f"limit_bytes={EVENT_LIMIT}",
                     f"received_bytes_at_least={EVENT_LIMIT + 1}", "previous_event=turn_start"]:
        assert expected in str(error)
    assert "SENSITIVE" not in str(error)
    assert rows[-1] is None


def test_stderr_cannot_use_agent_end_exception():
    rows, shown = read_events(b'{"type":"agent_end","messages":"' + b'x' * EVENT_LIMIT, stderr=True)
    assert len(rows) == 1 and isinstance(rows[0], ValueError)
    assert "channel=stderr" in str(rows[0]) and "type=unknown" in str(rows[0])
    assert not shown


@pytest.mark.parametrize("size", [5, READ_CHUNK + 20])
def test_truncated_agent_end_is_communication_error(size):
    rows, _ = read_events(b'{"type":"agent_end","messages":"' + b'x' * size)
    assert isinstance(rows[0], ValueError) and "agent_end 未读完整" in str(rows[0])
    assert rows[-1] is None


def test_type_inside_content_is_not_event_type_and_reordered_small_json_still_works():
    items = [{"message": {"type": "agent_end"}, "type": "message_end"},
             {"messages": [], "type": "agent_end"}]
    rows, _ = read_events(b''.join(json.dumps(x).encode() + b'\n' for x in items))
    assert rows == [*items, None]


def test_event_limit_boundary():
    prefix, suffix = b'{"type":"message_end","text":"', b'"}\n'
    data = prefix + b'x' * (EVENT_LIMIT - len(prefix) - len(suffix)) + suffix
    rows, _ = read_events(data)
    assert isinstance(rows[0], dict) and rows[-1] is None
    rows, _ = read_events(data[:-3] + b'x' + data[-3:])
    assert isinstance(rows[0], ValueError)


def test_agent_end_chunk_boundary_and_next_event():
    data = b' { "type" : "agent_end", "messages":"'
    data += b'x' * (4096 - len(data))
    data += b'"}\n{"type":"agent_settled"}\n'
    rows, _ = read_events(data)
    assert rows[0]["payload_omitted"] is True
    assert rows[1] == {"type": "agent_settled"}


def test_exit_after_agent_end_without_settled_fails(tmp_path):
    async def exercise():
        process = PiProcess()
        command = ["pi", "--tools", "read", "--system-prompt", "test"]
        process.signature = (tuple(["pi", "--tools", "<round>", "--system-prompt", "<round>"]), None, None, None)
        process.directory = SimpleNamespace(name=str(tmp_path))
        process.process = SimpleNamespace(pid=123, poll=lambda: None, stdin=io.BytesIO(), wait=lambda: 0)
        process.close = lambda **kwargs: None
        process._read(io.BytesIO(b'{"type":"agent_end","messages":[]}\n'), process.events)
        async with process.session(command, {}, tmp_path, lambda _: None) as (_, event):
            assert (await event())["payload_omitted"]
            with pytest.raises(PiExited, match="agent_settled"):
                await event()

    asyncio.run(exercise())
