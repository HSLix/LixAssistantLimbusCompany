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
from lalc.repair_tools import REPAIR_TOOLS
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
    command = repair_command(manager.data_root, image, base_url, "gemma4-test")
    state["repair_check"] = True
    retained = {p: p.read_bytes() for p in manager.data_root.rglob("*") if p.is_file()}
    state["steps"] = [
        tool("read", {"path": "steps.total.py"}),
        tool("edit", {"path": "steps.total.py", "oldText": "if value > 0", "newText": "if"}),
        tool("validate", {}),
        tool("edit", {"path": "steps.total.py", "oldText": " in values if)", "newText": " in values)"}),
        tool("validate", {}), answer(),
    ]
    state["respond"] = lambda body: state["steps"][min(len(state["calls"]) - 2, len(state["steps"]) - 1)]
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
    assert summary["requests"] == 7 and summary["groups"] == 1
    assert_pure_case(project / "candidate" / "steps.total.py")
    assert (path / "final.py").read_bytes() == (project / "candidate" / "steps.total.py").read_bytes()
    assert (path / "original.py").read_bytes() == (FIXTURE / "steps.total.py").read_bytes()
    assert "-    return sum(value for value in values if value > 0)" in (path / "final.diff").read_text()
    assert all(p.read_bytes() == content for p, content in retained.items())
    assert (project / "candidate" / "steps.unchanged.py").read_bytes() == (FIXTURE / "steps.unchanged.py").read_bytes()
    validations = [event["event"] for event in events if event["event"].get("type") == "validation"]
    assert any(not v["ok"] and v["errors"] for v in validations) and validations[-1]["ok"]
    assert "syntax" in json.dumps(state["calls"][4]).lower()
    assert "data:image/png;base64," in (path / "request-1.json").read_text()
    assert json.loads((path / "request-1.json").read_text()) == state["calls"][0]
    assert not state["calls"][0].get("tools")
    assert [t["function"]["name"] for t in state["calls"][1]["tools"]] == REPAIR_TOOLS

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


def test_saved_connection_and_full_path_are_used_without_cli_model(repair, monkeypatch):
    import lalc.__main__ as cli
    command, state, project, manager, _ = repair
    base = command[command.index("--base-url") + 1].removesuffix("/v1") + "/custom/api"
    monkeypatch.setattr(cli, "default_data_root", lambda: manager.data_root)
    assert cli.main(["agent-config", "--base-url", base, "--model", "gemma4-test", "--max-requests", "9"]) == 0
    saved = (manager.data_root / "agent-settings.json").read_bytes()
    for flag in ("--model", "--base-url"):
        position = command.index(flag)
        del command[position:position + 2]
    result = subprocess.run(command + ["--max-requests", "8"], cwd=project, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert state["get_paths"] == ["/custom/api/models"]
    assert set(state["post_paths"]) == {"/custom/api/chat/completions"}
    path, summary, events = outputs(manager)
    assert summary["requests"] == len(state["calls"]) == 7
    assert json.loads((path / "input.json").read_text())["settings"]["max_requests"] == 8
    assert (manager.data_root / "agent-settings.json").read_bytes() == saved
    assert not state["calls"][0].get("tools")
    assert any(e["event"].get("type") == "model_check_passed" for e in events)


@pytest.mark.parametrize("mode", ["missing_model", "invalid_limit", "unloaded", "loading", "unsupported_image", "authentication"])
def test_startup_rejection_keeps_draft_and_sends_no_model_request(repair, mode):
    command, state, project, manager, _ = repair
    if mode == "missing_model":
        position = command.index("--model")
        del command[position:position + 2]
    elif mode == "invalid_limit":
        command += ["--max-requests", "1"]
    elif mode == "authentication":
        state["get_status"] = 401
    else:
        state["models"] = [{"id": "gemma4-test", "status": {"value": mode if mode in {"unloaded", "loading"} else "loaded"},
                            "architecture": {"input_modalities": ["text"]}}]
    result = subprocess.run(command, cwd=project, capture_output=True, text=True, timeout=60)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (project / "candidate" / "old.py").read_text() == "discard this draft"
    assert not state["calls"]
    if mode in {"unloaded", "loading"}:
        assert "not loaded" in result.stdout and "image input support" not in result.stdout
    if mode == "authentication":
        assert "authentication failed" in result.stdout


def test_image_request_failure_is_counted_redacted_and_preserves_draft(repair):
    command, state, project, manager, _ = repair
    state["status"] = 501
    state["error_message"] = "image unsupported; echoed memory-only-key"
    result = subprocess.run(command + ["--ask-api-key"], input="memory-only-key\n", cwd=project,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 1
    path, summary, _ = outputs(manager)
    assert summary["requests"] == len(state["calls"]) == 1
    assert "image unsupported" in result.stdout
    assert (project / "candidate" / "old.py").exists()
    assert not (path / "final.py").exists()
    assert all(b"memory-only-key" not in p.read_bytes() for p in path.rglob("*") if p.is_file())
    assert "memory-only-key" not in result.stdout + result.stderr


@pytest.mark.skipif(sys.platform == "win32", reason="Tests unsupported live tools on Mac; Windows uses explicit game acceptance")
def test_asset_tools_return_actual_multiple_images_through_pi(repair):
    import base64
    from test_assets import entry
    command, state, project, manager, retained = repair
    first = entry(manager.data_root, "ui/claim")
    second = entry(manager.data_root, "other/button")
    images = [{"logical_name": name, "sha256": item["sha256"]}
              for name, item in [("ui/claim", first), ("other/button", second)]]
    retained.update({p: p.read_bytes() for p in (manager.data_root / "assets").rglob("*") if p.is_file()})
    state["steps"] = [tool("asset_tree", {}), tool("asset_directory", {"logical_name": "ui/claim"}),
                      tool("asset_images", {"images": images}), tool("action_contracts", {}),
                      tool("asset_images", {"images": [images[0], {"logical_name": "ui/claim", "sha256": "0" * 64}]}),
                      tool("game_screenshot", {}), answer(False)]
    result = subprocess.run(command, cwd=project, capture_output=True, text=True, timeout=60)
    assert result.returncode == 1, result.stdout + result.stderr
    path, summary, events = outputs(manager)
    assert summary["reason"] == "unable"
    results = [event["event"] for event in events if event["event"].get("type") == "repair_tool"]
    assert [event["name"] for event in results] == [step[0]["tool_calls"][0]["function"]["name"] for step in state["steps"][:-1]]
    assert results[1]["result"]["details"]["tags_missing"]
    assert len(results[2]["result"]["details"]["images"]) == 2
    body = json.dumps(state["calls"][4])
    for item in [first, second]:
        content = (manager.data_root / "assets" / item["path"]).read_bytes()
        assert "data:image/png;base64," + base64.b64encode(content).decode() in body
    assert all(image["sha256"] in body for image in images)
    assert results[4]["result"]["isError"] and not any(part["type"] == "image" for part in results[4]["result"]["content"])
    if sys.platform != "win32":
        assert results[5]["result"]["isError"] and "only on Windows" in json.dumps(results[5])
    assert len(list(path.glob("tool-3-image-*.png"))) == 2
    assert all(p.read_bytes() == content for p, content in retained.items())


def test_real_model_inspects_assets_and_actions(tmp_path):
    """真模型经公开修复入口读素材与动作；不修改测试基线或调用真实游戏。"""
    endpoint = os.environ.get("LALC_REPAIR_TEST_BASE_URL")
    if not endpoint:
        pytest.skip("Set LALC_REPAIR_TEST_BASE_URL for actual model acceptance")
    import base64
    import numpy as np
    from test_assets import entry
    manager, _ = baseline(tmp_path)
    first = entry(manager.data_root, "demo/one", np.full((64, 64, 3), (0, 0, 255), dtype=np.uint8))
    second = entry(manager.data_root, "demo/two", np.full((64, 64, 3), (255, 0, 0), dtype=np.uint8))
    project = tmp_path / "project"
    project.mkdir()
    image = Path(__file__).resolve().parents[1] / "test_pi_img.png"
    command = repair_command(manager.data_root, image, endpoint, os.environ.get("LALC_REPAIR_TEST_MODEL"))
    command[command.index("--problem") + 1] = (
        "本次只做工具验收，不需要修改代码。必须实际调用 asset_tree；asset_directory 查看 demo/one 和 demo/two；"
        "asset_images 在同一次调用查看这两个逻辑名的图片（使用目录中的完整哈希），指出每张图片的颜色；"
        "action_contracts 查看动作契约；再调用 asset_directory，logical_name 为 ../outside，确认工具拒绝越界。"
        "不调用实时游戏工具，不编辑源码。最后以 revise_success=false 的合法 JSON 汇报两张图片颜色和边界检查。")
    before = {p: p.read_bytes() for p in manager.data_root.rglob("*") if p.is_file()}
    result = subprocess.run(command, cwd=project, capture_output=True, text=True, timeout=240)
    assert result.returncode == 1, result.stdout + result.stderr
    path, summary, events = outputs(manager)
    assert summary["reason"] == "unable", summary
    results = [event["event"] for event in events if event["event"].get("type") == "repair_tool"]
    successful = {event["name"] for event in results if not event["result"].get("isError")}
    assert {"asset_tree", "asset_directory", "asset_images", "action_contracts"} <= successful
    assert any(event["name"] == "asset_images" and len(event["result"]["details"].get("images", [])) == 2 for event in results)
    assert any(event["name"] == "asset_directory" and event["result"].get("isError") for event in results)
    requests = "\n".join(p.read_text() for p in path.glob("request-*.json"))
    for item in [first, second]:
        assert "data:image/png;base64," + base64.b64encode((manager.data_root / "assets" / item["path"]).read_bytes()).decode() in requests
    assert all(p.read_bytes() == content for p, content in before.items())
    assert (project / "candidate/steps.total.py").read_bytes() == (FIXTURE / "steps.total.py").read_bytes()
    print(f"Real-model Asset/action evidence: {path}")


def test_windows_real_model_captures_and_reuses_crop(tmp_path):
    """Windows 实机验收：用户准备静止画面及固定像素区域，真实模型调用现场工具。"""
    endpoint = os.environ.get("LALC_REPAIR_TEST_BASE_URL")
    region_text = os.environ.get("LALC_REPAIR_TEST_CROP_REGION")
    if sys.platform != "win32" or not endpoint or not region_text:
        pytest.skip("Requires Windows game, LALC_REPAIR_TEST_BASE_URL and LALC_REPAIR_TEST_CROP_REGION")
    region = json.loads(region_text)
    manager, _ = baseline(tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    command = repair_command(manager.data_root, Path(__file__).resolve().parents[1] / "test_pi_img.png",
                             endpoint, os.environ.get("LALC_REPAIR_TEST_MODEL"))
    command[command.index("--problem") + 1] = (
        "本次只验收游戏观察工具，不改代码。先调用 game_screenshot 查看游戏，"
        f"再调用 crop_asset，logical_name=acceptance/live，region={json.dumps(region)}，tags=[\"keep\"]。"
        "随后以相同逻辑名和区域再次调用 crop_asset，但 tags=[\"replace\"]；核对复用图片且标签仍为 keep。"
        "不要点击、按键或编辑源码，最后以 revise_success=false 的合法 JSON 汇报。")
    before = {p: p.read_bytes() for p in manager.data_root.rglob("*") if p.is_file()}
    result = subprocess.run(command, cwd=project, capture_output=True, text=True, timeout=240)
    assert result.returncode == 1, result.stdout + result.stderr
    path, summary, events = outputs(manager)
    assert summary["reason"] == "unable", summary
    results = [event["event"] for event in events if event["event"].get("type") == "repair_tool"]
    assert any(item["name"] == "game_screenshot" and not item["result"].get("isError") for item in results)
    crops = [item for item in results if item["name"] == "crop_asset" and not item["result"].get("isError")]
    assert len(crops) >= 2
    first, second = (item["result"]["details"] for item in crops[:2])
    assert not first["existed"] and second["existed"] and first["sha256"] == second["sha256"]
    assert crops[0]["arguments"]["tags"] == ["keep"] and crops[1]["arguments"]["tags"] == ["replace"]
    assert second["tags"] == ["keep"]
    assert json.loads((manager.data_root / "assets/acceptance/live/asset-tag.json").read_text()) == {first["sha256"]: ["keep"]}
    assert Path(first["source_screenshot"]).is_file() and Path(second["source_screenshot"]).is_file()
    assert all(p.read_bytes() == content for p, content in before.items())
    print(f"Windows real-model screenshot/crop evidence: {path}")


def test_live_tools_through_pi_keep_old_tags_with_platform_substitute(repair):
    command, state, project, manager, retained = repair
    setup = (f"sys.path.insert(0, {str(Path(__file__).parent)!r}); "
             "from test_focused_observation import FakeWindowPlatform; "
             "import lalc.repair_tools as rt; window=FakeWindowPlatform(); "
             "window.capture=lambda hwnd,width,height: bytes([10,20,30,255])*width*height; "
             "rt.WindowsWindowPlatform=lambda **kwargs: window; ")
    command[2] = command[2].replace("raise SystemExit(cli.main())", setup + "raise SystemExit(cli.main())")
    crop = {"logical_name": "ui/new", "region": {"x": 0, "y": 0, "width": 1, "height": 1}}
    state["steps"] = [tool("game_screenshot", {}), tool("crop_asset", {**crop, "tags": ["keep"]}),
                      tool("crop_asset", {**crop, "tags": ["replace"]}), answer(False)]
    result = subprocess.run(command, cwd=project, capture_output=True, text=True, timeout=60)
    assert result.returncode == 1, result.stdout + result.stderr
    path, summary, events = outputs(manager)
    results = [event["event"]["result"] for event in events if event["event"].get("type") == "repair_tool"]
    assert len(results) == 3 and all(not item.get("isError") for item in results)
    first, reused = [item["details"] for item in results[1:]]
    assert not first["existed"] and reused["existed"] and reused["tags"] == ["keep"]
    assert json.loads((manager.data_root / "assets/ui/new/asset-tag.json").read_text()) == {first["sha256"]: ["keep"]}
    assert len([event for event in events if event["event"].get("type") == "target_window_connected"]) == 3
    assert Path(reused["source_screenshot"]).is_relative_to(path)
    assert "data:image/png;base64," in json.dumps(state["calls"][3])
    assert all(p.read_bytes() == content for p, content in retained.items())


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX SIGINT; Windows needs actual acceptance")
def test_cancel_while_tool_waits_for_focus(repair):
    import time
    command, state, project, manager, retained = repair
    marker = project / "waiting-for-focus"
    setup = f'''
import time
sys.path.insert(0, {str(Path(__file__).parent)!r})
from test_focused_observation import FakeWindowPlatform
import lalc.repair_tools as rt
def platform(**kwargs):
    window = FakeWindowPlatform()
    def focus(hwnd):
        Path({str(marker)!r}).write_text("waiting")
        while True:
            kwargs["checkpoint"]()
            time.sleep(0.02)
    window.focus = focus
    return window
rt.WindowsWindowPlatform = platform
raise SystemExit(cli.main())
'''
    command[2] = command[2].replace("raise SystemExit(cli.main())", setup)
    state["steps"] = [tool("game_screenshot", {}), answer(False)]
    process = subprocess.Popen(command, cwd=project, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 15
        while not marker.exists() and time.monotonic() < deadline and process.poll() is None:
            time.sleep(0.02)
        assert marker.exists(), "tool did not reach focus wait"
        process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate(timeout=15)
        assert process.returncode == 130, stdout + stderr
        assert len(state["calls"]) == 2
        assert outputs(manager)[1]["reason"] == "user_cancelled"
        assert all(p.read_bytes() == content for p, content in retained.items())
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()



@pytest.mark.parametrize("target", ["manifest.json", "steps.unchanged.py", "../outside.py", "outside-link.py"])
def test_edit_rejects_other_files(repair, target):
    command, state, project, manager, retained = repair
    outside = project / "outside.py"
    outside.write_text("PRIVATE_EXTERNAL_CONTENT")
    state["steps"] = [tool("edit", {"path": target, "oldText": "unchanged", "newText": "damaged"}), answer(False)]
    if target == "outside-link.py":
        # 链接在候选物化后创建，模拟模型访问一个现有的候选外部链接。
        def respond(body):
            if len(state["calls"]) == 2:
                (project / "candidate" / target).symlink_to(outside)
            return state["steps"][min(len(state["calls"]) - 2, 1)]
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
        command += ["--max-requests", "2"]
    elif mode == "provider_error":
        state["status"] = 503
    else:
        state["steps"] = [answer(False)]
    result = subprocess.run(command, cwd=project, capture_output=True, text=True, timeout=60)
    assert result.returncode == 1, result.stdout
    path, summary, _ = outputs(manager)
    assert summary["reason"] == {"limit": "request_limit", "provider_error": "error", "unable": "unable"}[mode]
    assert summary["requests"] == len(state["calls"]) == (1 if mode == "provider_error" else 2)
    if mode == "provider_error":
        assert (project / "candidate" / "old.py").exists()
        assert not (path / "final.py").exists()
    else:
        assert (path / "final.py").exists() and (path / "original.py").exists()


@pytest.mark.parametrize("last_failure", ["invalid_final", "invalid_candidate"])
def test_limit_after_final_feedback_preserves_group_judgment(repair, last_failure):
    command, state, project, manager, _ = repair
    if last_failure == "invalid_final":
        state["steps"] = [({"role": "assistant", "content": "not JSON"}, "stop")]
        command += ["--max-requests", "2"]
    else:
        state["steps"] = [tool("edit", {"path": "steps.total.py", "oldText": "if value > 0", "newText": "if"}), answer()]
        command += ["--max-requests", "3"]
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
        assert not (path / "final.py").exists()
        assert (project / "candidate" / "old.py").exists()
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


@pytest.mark.skipif(sys.platform != "win32", reason="Requires real Windows DPAPI and authenticated model service")
def test_windows_saved_dpapi_secret_authenticates_real_model(tmp_path, monkeypatch):
    """使用开发者已保存的命名密钥；同时确认服务拒绝匿名访问，不能以无认证服务冒充。"""
    import lalc.__main__ as cli
    from lalc.agent_settings import resolve_key, secret_path
    from lalc.application import default_data_root
    from lalc.pi_probe import _models
    import argparse
    endpoint = os.environ.get("LALC_REPAIR_TEST_BASE_URL")
    model = os.environ.get("LALC_REPAIR_TEST_MODEL")
    name = os.environ.get("LALC_REPAIR_TEST_SECRET_NAME")
    if not all((endpoint, model, name)):
        pytest.skip("Set test BASE_URL, MODEL and SECRET_NAME for Windows authenticated acceptance")
    with pytest.raises(ValueError, match="authentication failed"):
        _models(endpoint.rstrip("/"), "lalc-no-key")
    manager, _ = baseline(tmp_path)
    target = secret_path(manager.data_root, name)
    target.parent.mkdir(parents=True)
    target.write_bytes(secret_path(default_data_root(), name).read_bytes())
    monkeypatch.setattr(cli, "default_data_root", lambda: manager.data_root)
    assert cli.main(["agent-config", "--base-url", endpoint, "--model", model, "--secret-name", name]) == 0
    key = resolve_key(argparse.Namespace(ask_api_key=False), {"secret_name": name}, manager.data_root)
    project = tmp_path / "project"
    project.mkdir()
    image = Path(__file__).resolve().parents[1] / "test_pi_img.png"
    command = repair_command(manager.data_root, image, endpoint)
    position = command.index("--base-url")
    del command[position:position + 2]
    result = subprocess.run(command, cwd=project, capture_output=True, text=True, timeout=300)
    path, summary, _ = outputs(manager)
    print(f"Windows DPAPI authenticated model evidence: {path}")
    assert result.returncode == 0, result.stdout + result.stderr
    assert summary["requests"] >= 2
    assert_pure_case(path / "final.py")
    assert all(key.encode() not in p.read_bytes() for p in manager.data_root.rglob("*") if p.is_file())
    assert key not in result.stdout + result.stderr
