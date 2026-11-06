"""覆盖三层样例发布、动作调用、完整匹配、Plan 成败日志及失败后继续调度。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_example_workflow.py
"""

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from lalc.actions import application_actions
from lalc.application import ApplicationService
from lalc.manifest import ManifestManager
from test_assets import Window


def test_three_level_example_and_all_production_actions(tmp_path):
    """使用生产注册动作，替换 Windows 平台和 OCR 模型，证明样例走统一应用入口。"""
    candidate = tmp_path / "candidate"
    shutil.copytree(Path(__file__).resolve().parents[1] / "example" / "workflow", candidate)
    manager = ManifestManager(tmp_path / "data", actions=application_actions())
    assert not manager.validate(candidate / "manifest.json")
    published = manager.publish(candidate / "manifest.json")
    assert published.ok, published.errors
    original = published.loaded
    traces = []
    def run(entry, inputs, manifest=original.manifest_id):
        service = ApplicationService(manager.data_root, manifest_manager=manager, window_platform=Window(), game_language="zh")
        service.ocr_service = SimpleNamespace(recognize=lambda image, **kwargs: {
            "region": {"x": 0, "y": 0, "width": image.shape[1], "height": image.shape[0]},
            "items": [{"text": "战斗开始", "score": 0.97, "box": {"x": 2, "y": 1, "width": 2, "height": 2},
                       "polygon": [[2, 1], [3, 1], [3, 2], [2, 2]], "centerxy": [2, 1]}]})
        run_id = service.start(entry, inputs, manifest_id=manifest)
        state = service.wait_for(lambda current: current["phase"] == "finished")
        assert state["result"]["status"] == "success", state["result"]
        assert state["run_id"] == run_id
        persisted = [json.loads(line) for line in (manager.data_root / "traces" / f"{run_id}.jsonl").read_text(encoding="utf-8").splitlines()]
        assert persisted == state["trace"]
        traces.extend(state["trace"])
        return state
    state = run("tasks.exp", {})
    entered = [e["role"] for e in state["trace"] if e["event"] == "component_started"]
    assert entered == ["task_workflow", "sub_workflow", "step", "step"]
    assert Path(state["result"]["output"]["evidence_path"]).is_file()
    assert not any(e["event"] == "input_pressed" for e in state["trace"])
    ledger = json.loads((manager.data_root / "ledger" / f"{state['run_id']}.json").read_text(encoding="utf-8"))
    assert {record["workflow_kind"] for record in ledger["records"]} == {"task", "sub"}
    assert all(record["result"] == "success" and record["agent_invocations"] == 0 for record in ledger["records"])
    for entry, inputs in [
        ("steps.click", {"x": 2, "y": 1}),
        ("steps.key_press", {"key": "esc"}),
        ("steps.drag", {"x": 2, "y": 1, "end_x": 4, "end_y": 3, "seconds": 0.0}),
    ]:
        state = run(entry, inputs)
        assert any(e["event"] == "input_released" for e in state["trace"])
    crop = run("steps.crop", {"asset": "ui/claim", "region": {"x": 2, "y": 1, "width": 2, "height": 2}})["result"]["output"]
    service = ApplicationService(manager.data_root, manifest_manager=manager, game_language="zh")
    assert service.tag_asset("ui/claim", Path(crop["image_path"]), ["zh"])["tags"] == ["zh"]
    detections = run("steps.match", {"asset": "ui/claim", "threshold": 0.999})["result"]["output"]
    assert [(d["x"], d["y"]) for d in detections] == [(2, 1), (8, 5)]
    assert run("steps.ocr", {"min_score": 0.9})["result"]["output"]["items"][0]["text"] == "战斗开始"
    assert {e["logical_name"] for e in traces if e["event"] == "trusted_action_started"} == set(application_actions())


@pytest.mark.parametrize("fail_exp", [False, True])
def test_exp_mirror_pages_feed_plan_and_shared_actions(tmp_path, fail_exp):
    """两个真实页面的配置、循环次数进入已发布 Plan，并产生动作及 Task 记录。"""
    from PySide6.QtWidgets import QApplication
    from qfluentwidgets import FluentIcon
    from lalc.user_pages import UserSettings, discover_pages, task_inputs
    app = QApplication.instance() or QApplication([])
    example = Path(__file__).resolve().parents[1] / "example"
    assert {path.name for path in example.iterdir() if not path.name.startswith(".")} == {"pages", "workflow", "acceptance"}
    manager = ManifestManager(tmp_path / "data", actions=application_actions())
    candidate = tmp_path / "candidate"
    shutil.copytree(example / "workflow", candidate)
    if fail_exp:
        path = candidate / "exp.py"
        path.write_text(path.read_text().replace(
            '    observation = ctx.call("subworkflows.observe", save=save)',
            '    raise ValueError("example: task failed")'))
    saved = manager.publish(candidate / "manifest.json")
    assert saved.ok, saved.errors
    store = UserSettings(manager.data_root)
    pages, errors = discover_pages(example / "pages", store)
    assert not errors
    assert {page.page_id for page in pages} == {"exp", "mirror", "legacy-language-example"}
    assert {page.page_id: page.icon for page in pages} == {
        "exp": FluentIcon.EDUCATION, "mirror": FluentIcon.GAME, "legacy-language-example": FluentIcon.APPLICATION}
    for page in pages:
        if page.task_id:
            page.widget.message.setText(page.page_id + " message")
        page.context.save(page.widget.submit())
        if page.task_id:
            store.save_task(page.task_id, True, 2 if page.task_id == "exp" else 1)
    repetitions, settings, warnings = task_inputs(pages, ("exp", "mirror"), store)
    assert not warnings
    service = ApplicationService(manager.data_root, manifest_manager=manager, window_platform=Window())
    service.start_plan(manifest_id=saved.loaded.manifest_id, task_repetitions=repetitions, settings=settings)
    state = service.wait_for(lambda current: current["phase"] == "finished")
    service._thread.join()
    result = state["result"]
    assert result["status"] == "completed" and result["all_tasks_succeeded"] == (not fail_exp), result
    assert [item["status"] for item in result["items"]] == [
        "failure" if fail_exp else "success", "failure" if fail_exp else "success", "success"]
    assert [item["output"]["message"] for item in result["items"] if item["status"] == "success"] == (
        ["mirror message"] if fail_exp else ["exp message", "exp message", "mirror message"])
    messages = [event["message"] for event in state["trace"] if event["event"] == "component_log"]
    for item, sequence in zip(result["items"], ["1/2", "2/2", "1/1"]):
        assert f"{item['task']} 第 {sequence} 次 status={item['status']}" in messages
        if item["status"] == "failure":
            assert f"failure_code={item['failure_code']} failure_message={item['failure_message']}" in messages
        else:
            assert f"output={item['output']}" in messages
    assert {event["logical_name"] for event in state["trace"] if event["event"] == "trusted_action_started"} == {
        "observe.capture_screen", "control.wait"}
    for page in pages:
        page.widget.close()
    app.processEvents()
