"""覆盖共享 OCR 的坐标、校验、懒加载、串行复用、中断及正式 Action 日志，不加载真实模型。

项目根目录运行：QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_ocr.py
"""

import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import numpy as np
import pytest

from lalc.actions import application_actions
from lalc.application import ApplicationService
from lalc.focused import FocusedAutomationSession, WindowError
from lalc.manifest import ManifestManager
from lalc.ocr import OcrService, model_files
from lalc.runtime import ExecutionFailure, RunGate, UserInterruption, WorkflowExecutor
from test_focused_observation import FakeWindowPlatform


def output():
    return SimpleNamespace(boxes=np.array([[[1, 2], [5, 2], [5, 4], [1, 4]],
                                            [[0, 0], [1, 0], [1, 1], [0, 1]]]),
                           txts=["战斗开始", "低分"], scores=[0.97, 0.2])


def test_roi_coordinates_and_no_text_rewriting():
    service = OcrService()
    seen = []
    service._engine = lambda image, **kwargs: seen.append((image.copy(), kwargs)) or output()
    image = np.zeros((20, 30, 3), dtype=np.uint8)
    area = {"x": 10, "y": 8, "width": 10, "height": 6}
    result = service.recognize(image, region=area, min_score=0.9, checkpoint=lambda: None)
    assert result == {"region": area, "items": [{"text": "战斗开始", "score": 0.97,
        "box": {"x": 11, "y": 10, "width": 5, "height": 3},
        "polygon": [[11, 10], [15, 10], [15, 12], [11, 12]], "centerxy": [13, 11]}]}
    assert seen[0][0].shape == (6, 10, 3)
    assert seen[0][1] == {"use_cls": False, "text_score": 0.0}
    assert np.array_equal(image, np.zeros_like(image))
    assert len(service.recognize(image, checkpoint=lambda: None)["items"]) == 2
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("score", [-1, 1.1, float("nan"), float("inf"), True, "0.5"])
def test_bad_threshold_never_loads_model(score):
    service = OcrService()
    with pytest.raises(ValueError, match="min_score"):
        service.recognize(np.zeros((4, 4, 3), dtype=np.uint8), min_score=score, checkpoint=lambda: None)
    assert service._engine is None


def test_region_validation_empty_output_and_malformed_output():
    service = OcrService()
    image = np.zeros((8, 8, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="inside"):
        service.recognize(image, region={"x": 7, "y": 0, "width": 2, "height": 1}, checkpoint=lambda: None)
    service._engine = lambda *args, **kwargs: SimpleNamespace(boxes=None, txts=None, scores=None)
    assert service.recognize(image, checkpoint=lambda: None)["items"] == []
    service._engine = lambda *args, **kwargs: SimpleNamespace(boxes=[], txts=["missing"], scores=[])
    with pytest.raises(ValueError):
        service.recognize(image, checkpoint=lambda: None)


def test_engine_is_lazy_reused_and_serialized(monkeypatch):
    service = OcrService()
    loads = []
    busy = threading.Lock()
    def engine(*args, **kwargs):
        assert busy.acquire(blocking=False)
        try:
            return output()
        finally:
            busy.release()
    monkeypatch.setattr(service, "_load_engine", lambda: loads.append(1) or engine)
    assert not loads
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: service.recognize(np.zeros((8, 8, 3), dtype=np.uint8),
                                                           checkpoint=lambda: None), range(4)))
    assert len(loads) == 1 and len(results) == 4


@pytest.mark.parametrize("engine_fails", [False, True])
def test_takeover_during_inference_discards_success_or_error(engine_fails):
    service = OcrService()
    cancelled = False
    def checkpoint():
        if cancelled:
            raise UserInterruption("physical input", reason="takeover")
    def engine(*args, **kwargs):
        nonlocal cancelled
        cancelled = True
        if engine_fails:
            raise OSError("inference failed")
        return output()
    service._engine = engine
    with pytest.raises(UserInterruption) as caught:
        service.recognize(np.zeros((8, 8, 3), dtype=np.uint8), checkpoint=checkpoint)
    assert caught.value.reason == "takeover"


def test_missing_or_tampered_model_is_rejected_before_sdk_load(tmp_path, monkeypatch):
    import lalc.ocr as ocr
    models = tmp_path / "models"
    models.mkdir()
    monkeypatch.setattr(ocr.importlib.util, "find_spec", lambda _: SimpleNamespace(origin=str(tmp_path / "__init__.py")))
    monkeypatch.setattr(ocr, "MODEL_HASHES", {"det.onnx": hashlib.sha256(b"model").hexdigest()})
    with pytest.raises(FileNotFoundError):
        model_files()
    (models / "det.onnx").write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash mismatch"):
        model_files()
    (models / "det.onnx").write_bytes(b"model")
    assert model_files() == {"det.onnx": models / "det.onnx"}


def test_application_requires_existing_valid_capture_and_checks_after_inference(tmp_path):
    service = ApplicationService(tmp_path, window_platform=FakeWindowPlatform())
    with pytest.raises(WindowError, match="capture explicitly"):
        service._ocr()
    session = FocusedAutomationSession(service.window_platform, lambda *args: None)
    service._focused_session = session
    session.capture()
    def recognize(*args, **kwargs):
        service.window_platform.foreground = False
        return {"region": {}, "items": []}
    service.ocr_service = SimpleNamespace(recognize=recognize)
    with pytest.raises(WindowError, match="foreground"):
        service._ocr()
    assert session.image is None and service.window_platform.captures == 1


def test_real_action_dispatch_validation_and_trace(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "step.py").write_text('''"""测试截图后 OCR 的正式调用。"""
from lalc import step
@step
def execute(ctx) -> list[str]:
    ctx.action("observe.capture_screen")
    result = ctx.action("observe.ocr", min_score=0.9)
    return [item["text"] for item in result["items"]]
''')
    manifest_path = candidate / "manifest.json"
    manifest_path.write_text(json.dumps({"schema_version": 2, "components": {
        "steps.ocr": {"source_path": "step.py"}}, "recovery_rules": {}}))
    from runtime_support import add_plan
    add_plan(manifest_path)
    manager = ManifestManager(tmp_path, actions=application_actions())
    published = manager.publish(manifest_path)
    assert published.ok, published.errors
    manager.set_default(published.loaded.manifest_id)
    service = ApplicationService(tmp_path, manifest_manager=manager, window_platform=FakeWindowPlatform())
    recognized = {"region": {"x": 0, "y": 0, "width": 2, "height": 2}, "items": [
        {"text": "战斗开始", "score": 0.97, "box": {"x": 0, "y": 0, "width": 2, "height": 2},
         "polygon": [[0, 0], [1, 0], [1, 1], [0, 1]], "centerxy": [0, 0]}]}
    service.ocr_service = SimpleNamespace(recognize=lambda *args, **kwargs: recognized)
    run = service.start("steps.ocr", {})
    state = service.wait_for(lambda state: state["phase"] == "finished")
    assert state["result"]["status"] == "success", state["result"]
    events = [json.loads(line) for line in (tmp_path / "traces" / f"{run}.jsonl").read_text().splitlines()]
    event = next(event for event in events if event["event"] == "trusted_action_returned"
                 and event["logical_name"] == "observe.ocr")
    assert event["inputs"] == {"region": None, "min_score": 0.9}
    assert event["return_value"] == {"observation": 1, **recognized}
    assert event["duration_ms"] >= 0 and service.window_platform.captures == 1
    executor = WorkflowExecutor(published.loaded, RunGate(), lambda *args: None, ocr=service._ocr)
    with pytest.raises(ExecutionFailure, match="observe Trusted Action"):
        executor.context.ocr()
