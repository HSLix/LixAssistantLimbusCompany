"""覆盖单次 Run 共享配置、输入隔离及框架恢复计数只读边界。

从项目根目录运行：.venv/bin/python -m pytest tests/test_run_state.py -q
"""

import pytest

from lalc import RunState
from lalc.runtime import InputValidationError


def test_run_state_copies_initial_data_and_exposes_readonly_counter():
    source = {"page": {"teams": ["A"]}}
    state = RunState({"task": 2}, source)
    state.settings["page"]["teams"].append("B")
    state.task_repetitions["task"] -= 1
    assert source == {"page": {"teams": ["A"]}}
    snapshot = state.snapshot()
    snapshot["settings"]["page"]["teams"].clear()
    assert state.settings["page"]["teams"] == ["A", "B"]
    assert state.task_repetitions == {"task": 1}
    assert RunState().snapshot() == {"task_repetitions": {}, "settings": {}, "recovery_count": 0}
    with pytest.raises(AttributeError):
        state.recovery_count = 1


@pytest.mark.parametrize("repetitions,settings", [({"task": True}, {}), ({"task": -1}, {}),
                                                ({}, {"page": {"x": float("nan")}})])
def test_invalid_run_state_is_rejected(repetitions, settings):
    with pytest.raises(InputValidationError):
        RunState(repetitions, settings)
