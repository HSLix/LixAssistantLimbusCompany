"""经真实 pi 检查编辑、校验反馈、分组、错误与取消，并提供可重用真模型修复验收。

在项目根目录运行：
UV_CACHE_DIR=.generated/uv-cache uv run --frozen pytest --run-agent-tests -q tests/test_component_repair_agent.py
默认使用 HTTP 替身；设置 LALC_REPAIR_TEST_BASE_URL 后才额外运行真模型案例。
"""

import json
import os
from pathlib import Path
import runpy
import signal
import subprocess
import sys

import pytest

from lalc.manifest import ManifestManager
from test_component_repair import FIXTURE, baseline
from test_pi_probe import probe


pytestmark = pytest.mark.agent


def repair_command(data_root, image, base_url, model=None):
    """仅替换 CLI 的数据目录定位，仍走实际公开命令及真实 pi。"""
    case = json.loads((FIXTURE / "case.json").read_text())
    command = [sys.executable, "-c", "import sys; from pathlib import Path; import lalc.__main__ as cli; "
               "root=Path(sys.argv.pop(1)); cli.default_data_root=lambda: root; raise SystemExit(cli.main())",
               str(data_root), "repair", case["target"], "--image", str(image),
               "--problem", case["problem"], "--base-url", base_url]
    if model:
        command += ["--model", model]
    return command


def tool(name, arguments):
    return {"role": "assistant", "tool_calls": [{"index": 0, "id": "call-" + name, "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments)}}]}, "tool_calls"


def answer(success=True):
    return {"role": "assistant", "content": json.dumps({"revise_success": success, "message": "fixed" if success else "need more evidence"})}, "stop"


@pytest.fixture
def repair(probe, tmp_path):
    command, state, _ = probe
    manager, _ = baseline(tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    candidate = project / "candidate"
    candidate.mkdir()
    (candidate / "old.py").write_text("discard this draft")
    image = tmp_path / "image.png"
    base_url = command[command.index("--base-url") + 1]
    command = repair_command(manager.data_root, image, base_url)
    retained = {p: p.read_bytes() for p in manager.data_root.rglob("*") if p.is_file()}
    state["steps"] = [
        tool("read", {"path": "steps.total.py"}),
        tool("edit", {"path": "steps.total.py", "oldText": "if value > 0", "newText": "if"}),
        tool("validate", {}),
        tool("edit", {"path": "steps.total.py", "oldText": " in values if)", "newText": " in values)"}),
        tool("validate", {}), answer(),
    ]
    state["respond"] = lambda body: state["steps"][min(len(state["calls"]) - 1, len(state["steps"]) - 1)]
    return command, state, project, manager, retained


def outputs(manager):
    path = sorted(manager.data_root.glob("agent-interactions/*/*"), key=lambda p: p.stat().st_mtime_ns)[-1]
    result = json.loads((path / "result.json").read_text())
    events = [json.loads(line) for line in (path / "events.jsonl").read_text().splitlines()]
    return path, result, events


def assert_pure_case(source):
    """只对测试自有的纯计算案例做输入输出断言，不提供 Agent 执行工具。"""
    execute = runpy.run_path(str(source))["execute"]
    for check in json.loads((FIXTURE / "case.json").read_text())["checks"]:
        assert execute(None, values=check["values"]) == check["expected"]


def test_real_edit_validator_feedback_and_retained_outputs(repair):
    command, state, project, manager, retained = repair
    # 使用实际大小的截图，覆盖 RPC 大消息与独立请求日志，不能只测试一像素图片。
    command[command.index("--image") + 1] = str(Path(__file__).resolve().parents[1] / "test_pi_img.png")
    result = subprocess.run(command + ["--ask-api-key"], input="memory-only-key\n", cwd=project,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    path, summary, events = outputs(manager)
    assert summary["requests"] == 6 and summary["groups"] == 1
    assert_pure_case(project / "candidate" / "steps.total.py")
    assert (path / "final.py").read_bytes() == (project / "candidate" / "steps.total.py").read_bytes()
    assert (path / "original.py").read_bytes() == (FIXTURE / "steps.total.py").read_bytes()
    assert "-    return sum(value for value in values if value > 0)" in (path / "final.diff").read_text()
    assert all(p.read_bytes() == content for p, content in retained.items())
    assert (project / "candidate" / "steps.unchanged.py").read_bytes() == (FIXTURE / "steps.unchanged.py").read_bytes()
    validations = [event["event"] for event in events if event["event"].get("type") == "validation"]
    assert any(not v["ok"] and v["errors"] for v in validations) and validations[-1]["ok"]
    assert "syntax" in json.dumps(state["calls"][3]).lower()
    assert "data:image/png;base64," in (path / "request-1.json").read_text()
    assert json.loads((path / "request-1.json").read_text()) == state["calls"][0]
    assert [t["function"]["name"] for t in state["calls"][0]["tools"]] == ["read", "edit", "validate"]
    for artifact in path.iterdir():
        assert b"memory-only-key" not in artifact.read_bytes()
    assert "memory-only-key" not in result.stdout + result.stderr
    # 同一次测试重建候选，再次修复，旧交互产物必须保留。
    previous = (path / "events.jsonl").read_bytes()
    state["calls"].clear()
    again = subprocess.run(command, cwd=project, capture_output=True, text=True, timeout=60)
    assert again.returncode == 0, again.stdout
    assert (path / "events.jsonl").read_bytes() == previous
    assert outputs(manager)[0] != path


@pytest.mark.parametrize("target", ["manifest.json", "steps.unchanged.py", "../outside.py", "outside-link.py"])
def test_edit_rejects_other_files(repair, target):
    command, state, project, manager, retained = repair
    outside = project / "outside.py"
    outside.write_text("PRIVATE_EXTERNAL_CONTENT")
    state["steps"] = [tool("edit", {"path": target, "oldText": "unchanged", "newText": "damaged"}), answer(False)]
    if target == "outside-link.py":
        # 链接在候选物化后创建，模拟模型访问一个现有的候选外部链接。
        def respond(body):
            if len(state["calls"]) == 1:
                (project / "candidate" / target).symlink_to(outside)
            return state["steps"][min(len(state["calls"]) - 1, 1)]
        state["respond"] = respond
    result = subprocess.run(command, cwd=project, capture_output=True, text=True, timeout=60)
    assert result.returncode == 1
    assert outside.read_text() == "PRIVATE_EXTERNAL_CONTENT"
    assert all(p.read_bytes() == content for p, content in retained.items())
    assert (project / "candidate" / "steps.unchanged.py").read_bytes() == (FIXTURE / "steps.unchanged.py").read_bytes()
    assert "Only the selected Component" in json.dumps(state["calls"]) or "outside allowed directory" in json.dumps(state["calls"])
    assert outputs(manager)[1]["reason"] == "unable"


def test_format_and_final_validation_start_new_groups(repair):
    command, state, project, manager, _ = repair
    state["steps"] = [
        ({"role": "assistant", "content": "not JSON"}, "stop"),
        tool("edit", {"path": "steps.total.py", "oldText": "if value > 0", "newText": "if"}),
        answer(),
        tool("edit", {"path": "steps.total.py", "oldText": " in values if)", "newText": " in values)"}),
        tool("validate", {}), answer(),
    ]
    result = subprocess.run(command, cwd=project, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    path, summary, events = outputs(manager)
    assert summary["groups"] == 3
    groups = [e for e in events if e["event"].get("type") == "group_finished"]
    assert groups[0]["event"]["reason"] == "invalid_final"
    assert groups[1]["event"]["answer"]["revise_success"] is True
    assert groups[2]["event"]["answer"]["revise_success"] is True
    assert " in values if)" in (path / "group-2.py").read_text()
    assert_pure_case(path / "group-3.py")


@pytest.mark.parametrize("mode", ["limit", "provider_error", "unable"])
def test_incomplete_paths_keep_source_and_reason(repair, mode):
    command, state, project, manager, _ = repair
    if mode == "limit":
        command += ["--max-requests", "1"]
    elif mode == "provider_error":
        state["status"] = 503
    else:
        state["steps"] = [answer(False)]
    result = subprocess.run(command, cwd=project, capture_output=True, text=True, timeout=60)
    assert result.returncode == 1, result.stdout
    path, summary, _ = outputs(manager)
    assert summary["reason"] == {"limit": "request_limit", "provider_error": "provider_error", "unable": "unable"}[mode]
    assert summary["requests"] == len(state["calls"]) == 1
    assert (path / "final.py").exists() and (path / "original.py").exists()


@pytest.mark.parametrize("last_failure", ["invalid_final", "invalid_candidate"])
def test_limit_after_final_feedback_preserves_group_judgment(repair, last_failure):
    command, state, project, manager, _ = repair
    if last_failure == "invalid_final":
        state["steps"] = [({"role": "assistant", "content": "not JSON"}, "stop")]
        command += ["--max-requests", "1"]
    else:
        state["steps"] = [tool("edit", {"path": "steps.total.py", "oldText": "if value > 0", "newText": "if"}), answer()]
        command += ["--max-requests", "2"]
    result = subprocess.run(command, cwd=project, capture_output=True, text=True, timeout=60)
    assert result.returncode == 1, result.stdout
    _, summary, events = outputs(manager)
    assert summary["reason"] == "request_limit"
    assert summary["requests"] == len(state["calls"])
    group = next(e["event"] for e in events if e["event"].get("type") == "group_finished")
    if last_failure == "invalid_final":
        assert group["reason"] == "invalid_final" and summary["validation"] == {"performed": False}
    else:
        assert group["answer"]["revise_success"] is True
        assert summary["validation"]["ok"] is False and summary["validation"]["errors"]


@pytest.mark.skipif(sys.platform == "win32", reason="Windows actual exe cancellation acceptance is separate")
def test_cancel_preserves_outputs(repair):
    command, state, project, manager, _ = repair
    state["block"] = True
    process = subprocess.Popen(command, cwd=project, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert state["started"].wait(15)
        process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate(timeout=15)
        assert process.returncode == 130, stdout + stderr
        path, summary, _ = outputs(manager)
        assert summary["reason"] == "user_cancelled"
        assert (path / "final.py").exists()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


@pytest.mark.skipif(not os.environ.get("LALC_REPAIR_TEST_BASE_URL"), reason="Explicit real model endpoint required")
def test_real_model_repairs_fixed_pure_case(tmp_path):
    manager, _ = baseline(tmp_path)
    retained = {p: p.read_bytes() for p in manager.data_root.rglob("*") if p.is_file()}
    project = tmp_path / "project"
    project.mkdir()
    image = Path(__file__).resolve().parents[1] / "test_pi_img.png"
    command = repair_command(manager.data_root, image, os.environ["LALC_REPAIR_TEST_BASE_URL"],
                             os.environ.get("LALC_REPAIR_TEST_MODEL"))
    result = subprocess.run(command, cwd=project, capture_output=True, text=True, timeout=300)
    path, summary, events = outputs(manager)
    print(f"Real model repair evidence: {path}")
    assert result.returncode == 0, result.stdout + result.stderr
    assert summary["answer"]["revise_success"] is True
    assert (path / "final.py").read_bytes() != (path / "original.py").read_bytes()
    assert manager.validate(project / "candidate" / "manifest.json") == ()
    assert_pure_case(path / "final.py")
    assert all(p.read_bytes() == content for p, content in retained.items())
    assert (project / "candidate" / "steps.unchanged.py").read_bytes() == (FIXTURE / "steps.unchanged.py").read_bytes()
    successful_tools = {e["event"].get("toolName") for e in events
                        if e["event"].get("type") == "tool_execution_end" and not e["event"].get("isError")}
    assert {"read", "edit", "validate"} <= successful_tools
