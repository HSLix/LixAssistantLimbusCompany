from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from lalc.application import DemoService
from lalc.runtime import RunGate, TaskCancelled, sha256_bytes


def test_supervised_candidate_and_permanent_approval(tmp_path: Path) -> None:
    service = DemoService(tmp_path)
    service.start({"supported": False, "amount": 3})
    review = service.wait_for(lambda state: state["phase"] == "runtime_review")
    assert "不是安全沙箱" in review["pending_review"]["warning"]
    service.decide_runtime("approve")
    capability = service.wait_for(lambda state: state["phase"] == "capability_review")
    assert capability["pending_capability"]["trial_succeeded"] is True
    assert capability["result"]["status"] == "success"
    service.decide_capability("approve")
    finished = service.wait_for(lambda state: state["phase"] == "finished")
    assert finished["active_manifest_id"].startswith("approved-")
    assert list((tmp_path / "traces").glob("*.jsonl"))
    assert list((tmp_path / "logs").glob("*.json"))

    service.start({"supported": False, "amount": 5})
    reused = service.wait_for(lambda state: state["phase"] == "finished")
    assert reused["result"]["value"]["amount"] == 5
    assert "agent_turn" not in [item["event"] for item in reused["trace"]]


def test_rejection_requires_feedback_and_reaches_next_turn(tmp_path: Path) -> None:
    service = DemoService(tmp_path)
    service.start({"supported": False})
    service.wait_for(lambda state: state["phase"] == "runtime_review")
    with pytest.raises(ValueError, match="feedback_required"):
        service.decide_runtime("reject")
    service.decide_runtime("reject", "请修正")
    second = service.wait_for(
        lambda state: state["phase"] == "runtime_review" and state["remaining_turns"] == 0
    )
    assert second["working_manifest_id"] == "base"
    service.decide_runtime("terminate")
    capability = service.wait_for(lambda state: state["phase"] == "capability_review")
    assert capability["pending_capability"]["trial_succeeded"] is False
    service.decide_capability("reject")
    service.wait_for(lambda state: state["phase"] == "finished")
    logs = sorted((tmp_path / "logs").glob("*.json"))
    assert json.loads(logs[-1].read_text())["feedback"] == "请修正"


def test_failed_trial_rolls_back_before_next_turn(tmp_path: Path) -> None:
    service = DemoService(tmp_path)
    service.start({"supported": False, "candidate_fail_turns": 1})
    service.wait_for(lambda state: state["phase"] == "runtime_review")
    service.decide_runtime("approve")
    second = service.wait_for(
        lambda state: state["phase"] == "runtime_review" and state["remaining_turns"] == 0
    )
    events = [item["event"] for item in second["trace"]]
    assert "working_manifest_rolled_back" in events
    assert second["working_manifest_id"] == "base"
    service.decide_runtime("approve")
    service.wait_for(lambda state: state["phase"] == "capability_review")
    service.decide_capability("reject")
    assert service.wait_for(lambda state: state["phase"] == "finished")["result"]["status"] == "success"


def test_cancellation_terminates_runner_without_manifest_rollback(tmp_path: Path) -> None:
    service = DemoService(tmp_path, runner_timeout=30)
    service.start({"supported": False, "candidate_should_hang": True})
    service.wait_for(lambda state: state["phase"] == "runtime_review")
    service.decide_runtime("approve")
    running = service.wait_for(lambda state: state["phase"] == "candidate_trial")
    selected_manifest = running["working_manifest_id"]
    service.stop()
    capability = service.wait_for(lambda state: state["phase"] == "capability_review")
    assert capability["working_manifest_id"] == selected_manifest != "base"
    assert capability["result"]["failure_code"] == "user_cancelled"
    service.decide_capability("reject")
    service.wait_for(lambda state: state["phase"] == "finished")


def test_terminal_failures_do_not_start_agent(tmp_path: Path) -> None:
    for scenario in ({"supported": True, "step_external_failure": True}, {"supported": True, "verification_fails": True}):
        service = DemoService(tmp_path / str(len(list(tmp_path.iterdir()))))
        service.start(scenario)
        state = service.wait_for(lambda current: current["phase"] == "finished")
        assert "agent_turn" not in [item["event"] for item in state["trace"]]


def test_run_gate_sleeps_until_resume_or_stop() -> None:
    gate = RunGate()
    gate.pause()
    outcomes: list[str] = []
    first = threading.Thread(target=lambda: (gate.wait(), outcomes.append("resumed")))
    first.start()
    assert outcomes == []
    gate.resume()
    first.join(1)
    assert outcomes == ["resumed"]

    gate.pause()
    second = threading.Thread(target=lambda: _capture_cancel(gate, outcomes))
    second.start()
    gate.stop()
    second.join(1)
    assert outcomes[-1] == "cancelled"


def _capture_cancel(gate: RunGate, outcomes: list[str]) -> None:
    try:
        gate.wait()
    except TaskCancelled:
        outcomes.append("cancelled")


def test_candidate_runner_and_packaging_probe(tmp_path: Path) -> None:
    candidate = tmp_path / "候选 step.py"
    candidate.write_text(
        "import sys\nfrom lalc import api_version\n"
        "def execute(ctx, *, value=1):\n"
        "    assert 'PySide6' not in sys.modules\n"
        "    ctx.control('done', value)\n"
        "    return {'completed': True, 'api': api_version()}\n"
    )
    result = tmp_path / "结果.json"
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "protocol_version": 1,
                "source_path": str(candidate),
                "expected_sha256": sha256_bytes(candidate.read_bytes()),
                "arguments": {"value": 2},
                "example_scenario": {},
                "result_path": str(result),
            }
        )
    )
    completed = subprocess.run(
        [sys.executable, "-m", "lalc", "--candidate-runner", str(request)], check=False
    )
    assert completed.returncode == 0
    output = json.loads(result.read_text())
    assert output["result"] == {"completed": True, "api": 1}
    assert output["action_events"][0]["action"] == "control"

    probe = tmp_path / "external.py"
    probe.write_text("from lalc import api_version\ndef probe(): return {'api': api_version()}\n")
    probe_result = tmp_path / "probe-result.json"
    completed = subprocess.run(
        [sys.executable, "-m", "lalc", "--packaging-probe", str(probe), str(probe_result)], check=False
    )
    assert completed.returncode == 0
    assert json.loads(probe_result.read_text())["result"] == {"api": 1}


def test_candidate_runner_rejects_hash_mismatch_and_context_field(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.py"
    candidate.write_text("def execute(ctx): return {}\n")
    for extra in ({"expected_sha256": "0" * 64}, {"context": {}}):
        result = tmp_path / f"result-{len(list(tmp_path.glob('result-*')))}.json"
        request = {
            "protocol_version": 1,
            "source_path": str(candidate),
            "expected_sha256": sha256_bytes(candidate.read_bytes()),
            "arguments": {},
            "example_scenario": {},
            "result_path": str(result),
            **extra,
        }
        request_path = result.with_suffix(".request.json")
        request_path.write_text(json.dumps(request))
        completed = subprocess.run(
            [sys.executable, "-m", "lalc", "--candidate-runner", str(request_path)], check=False
        )
        assert completed.returncode == 1
        assert json.loads(result.read_text())["status"] == "failure"


def test_qt_main_window_smoke(tmp_path: Path) -> None:
    from PySide6.QtWidgets import QApplication

    from lalc.gui import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow(DemoService(tmp_path))
    window.show()
    app.processEvents()
    assert window.windowTitle() == "LALC Architecture Demo"
    window.close()
