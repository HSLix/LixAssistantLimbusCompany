"""覆盖新恢复样例的生产动作、唯一目标点击、Step 重试及安全停止分支。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_recovery_example.py
"""

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from lalc.actions import application_actions
from lalc.application import ApplicationService
from lalc.manifest import ManifestManager
from test_assets import Window, template, entry
from test_input_control import FakeInput


@pytest.mark.parametrize("case", ["recovered", "no_popup", "click_ineffective", "multiple_targets", "multiple_rules"])
def test_recovery_example_uses_existing_executor_and_actions(tmp_path, case):
    candidate = tmp_path / "candidate"
    shutil.copytree(Path(__file__).resolve().parents[1] / "example/workflow", candidate)
    path = candidate / "manifest.json"
    if case == "multiple_rules":
        manifest = json.loads(path.read_text())
        manifest["recovery_rules"]["recovery.also_matches"] = {"source_path": "recovery.close_popup.py"}
        path.write_text(json.dumps(manifest))
    manager = ManifestManager(tmp_path / "data", actions=application_actions())
    assert not manager.validate(path)
    saved = manager.publish(path)
    assert saved.ok, saved.errors
    entry(manager.data_root, "tutorial/recovery-popup")
    platform, backend = Window(), FakeInput()
    platform.create_input_backend = lambda: backend
    platform.image = np.zeros((8, 12, 3), dtype=np.uint8)
    if case != "no_popup":
        platform.image[1:3, 2:4] = template()
    if case == "multiple_targets":
        platform.image[5:7, 8:10] = template()
    if case == "recovered":
        backend.on_down = lambda: platform.image.fill(0)
    service = ApplicationService(manager.data_root, manifest_manager=manager, window_platform=platform, game_language="zh")
    identity = service.start("steps.check_popup", {}, manifest_id=saved.loaded.manifest_id)
    state = service.wait_for(lambda value: value["phase"] == "finished")
    successful = case in {"recovered", "no_popup"}
    assert (state["result"]["status"] == "success") == successful, state["result"]
    trace = state["trace"]
    phases = [event["phase"] for event in trace if event["event"] == "recovery_rule_started"]
    if case == "no_popup":
        assert not phases
    elif case == "multiple_rules":
        assert phases == ["detect", "detect"]
        assert not any(event["event"] == "step_reinvocation_started" for event in trace)
    else:
        assert phases == ["detect", "recover"]
    clicks = [event for event in backend.events if isinstance(event, tuple) and event[0] == "down"]
    assert len(clicks) == (1 if case in {"recovered", "click_ineffective"} else 0)
    assert sum(event["event"] == "step_reinvocation_started" for event in trace) == (1 if case in {"recovered", "click_ineffective"} else 0)
    persisted = [json.loads(line) for line in (manager.data_root / f"traces/{identity}.jsonl").read_text().splitlines()]
    assert persisted == trace
