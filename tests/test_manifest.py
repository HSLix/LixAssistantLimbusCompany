"""覆盖正式 Component Manifest 的校验、发布、加载、启用和失败后保持原选择。

在项目根目录运行：
UV_CACHE_DIR=.generated/uv-cache uv run --frozen pytest -q tests/test_manifest.py
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

import pytest

import lalc.manifest as manifest_module
from lalc.manifest import ManifestManager
from lalc.application import ApplicationService, StartError


SOURCES = {
    "task.py": '''"""Test Task Workflow."""
from lalc import task_workflow

@task_workflow
def execute(ctx, *, amount: int = 1) -> dict[str, int]:
    result = ctx.call("flow.sub", amount=amount)
    ctx.call("steps.finish", amount=amount)
    return result

''',
    "sub.py": '''"""Test Subworkflow."""
from lalc import sub_workflow

@sub_workflow
def execute(ctx, *, amount: int = 1) -> dict[str, int]:
    return ctx.call("steps.finish", amount=amount)
''',
    "step.py": '''"""Test Step."""
from lalc import step

@step
def execute(ctx, *, amount: int = 1) -> dict[str, int]:
    return {"amount": amount}

def condition(ctx, *, amount: int = 1) -> bool:
    return amount >= 0
''',
    "recovery.py": '''"""Test Recovery Rule."""
def detect(ctx) -> bool:
    return False

def recover(ctx) -> None:
    return None
''',

}


def _write_candidate(directory: Path, *, sources: dict[str, str] | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    for name, source in (sources or SOURCES).items():
        (directory / name).write_text(source, encoding="utf-8")
    manifest = {
        "schema_version": 2,
        "components": {
            "tasks.example": {"source_path": "task.py"},
            "flow.sub": {"source_path": "sub.py"},
            "steps.finish": {"source_path": "step.py"},
        },
        "recovery_rules": {"recovery.dismiss": {"source_path": "recovery.py"}},
    }
    path = directory / "candidate.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def _codes(result) -> set[str]:
    return {error.code for error in result.errors}


def test_validate_does_not_allocate_manifest_id_before_publish(tmp_path: Path, monkeypatch) -> None:
    """校验完整导入但不分配 Manifest ID，正式发布才建立持久身份。"""

    manager = ManifestManager(tmp_path / "formal")
    candidate = _write_candidate(tmp_path / "candidate")
    loaded_manifests = []
    load = manager._load

    def record_load(manifest, prepared, *, cache=True):
        loaded_manifests.append(dict(manifest))
        return load(manifest, prepared, cache=cache)

    monkeypatch.setattr(manager, "_load", record_load)
    assert not manager.validate(candidate)
    assert len(loaded_manifests) == 1
    assert "manifest_id" not in loaded_manifests[0]
    assert not manager.manifests_dir.exists()
    assert not manager.components_dir.exists()

    result = manager.publish(candidate)
    assert result.ok, result.errors
    assert result.loaded.manifest_id
    assert (manager.manifests_dir / f"{result.loaded.manifest_id}.json").is_file()


def test_candidate_validation_cannot_supply_formal_modules(tmp_path: Path) -> None:
    """校验后移除草稿，正式运行仍使用各自存储中的哈希源码与报错行。"""

    sources = dict(SOURCES)
    sources["step.py"] = '''"""返回实际源码位置或产生带原因链的错误。"""
from lalc import step

def fail():
    raise OSError("stored source failure") from ValueError("original cause")

@step
def execute(ctx, *, amount: int = 1) -> str:
    if amount < 0:
        fail()
    return __file__
'''
    for name in ("first", "second"):
        manager = ManifestManager(tmp_path / name / "formal")
        candidate = _write_candidate(tmp_path / name / "candidate", sources=sources)
        assert not manager.validate(candidate)
        assert not manager.components_dir.exists()
        published = manager.publish(candidate)
        assert published.ok, published.errors
        component = published.loaded.components["steps.finish"]
        stored = (manager.components_dir / f"{component.component_id.split(':')[1]}.py").resolve()
        shutil.rmtree(candidate.parent)
        service = ApplicationService(manager.data_root, manifest_manager=manager)
        run_id = service.start("steps.finish", {}, manifest_id=published.loaded.manifest_id)
        state = service.wait_for(lambda s: s["run_id"] == run_id and s["phase"] == "finished")
        assert state["result"]["output"] == str(stored)
        assert manager.load(published.loaded.manifest_id).loaded.components["steps.finish"].module is component.module
        run_id = service.start("steps.finish", {"amount": -1}, manifest_id=published.loaded.manifest_id)
        state = service.wait_for(lambda s: s["run_id"] == run_id and s["phase"] == "finished")
        diagnostic = state["result"]["traceback"]
        assert str(stored) in diagnostic
        assert str(candidate.parent) not in diagnostic
        assert "in fail" in diagnostic
        assert 'raise OSError("stored source failure")' in diagnostic
        assert "ValueError: original cause" in diagnostic
        assert "OSError: stored source failure" in diagnostic


def test_import_error_retains_serializable_diagnostics_and_start_cause(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """导入失败在日志、校验结果和同步启动拒绝中保留原始原因链。"""

    sources = dict(SOURCES)
    sources["step.py"] = '''"""导入时报告完整错误链。"""
from lalc import step
raise OSError("import failed") from ValueError("import root cause")
@step
def execute(ctx, *, name: str = "state") -> dict[str, str]:
    return {"name": name}
'''
    manager = ManifestManager(tmp_path / "formal")
    candidate = _write_candidate(tmp_path / "candidate", sources=sources)
    with caplog.at_level(logging.ERROR):
        result = manager.publish(candidate)
    assert not result.ok
    error = result.errors[0]
    payload = json.loads(json.dumps(error.as_dict()))
    assert "cause" not in payload
    assert "OSError:" in payload["traceback"]
    assert "ValueError: import root cause" in payload["traceback"]
    assert "OSError: import failed" in payload["traceback"]
    assert "import root cause" in caplog.text
    assert "Traceback" in caplog.text
    assert not list(manager.manifests_dir.glob("*.json"))
    monkeypatch.setattr(manager, "load", lambda _: result)
    service = ApplicationService(manager.data_root, manifest_manager=manager)
    with pytest.raises(StartError) as rejected:
        service.start("tasks.example", {}, manifest_id="unavailable")
    assert rejected.value.__cause__ is error.cause
    assert rejected.value.errors[0]["traceback"] == payload["traceback"]
    assert service.state["run_id"] is None


def test_publish_loads_complete_manifest_and_uses_content_ids(tmp_path: Path) -> None:
    candidate = _write_candidate(tmp_path / "candidate")
    manager = ManifestManager(tmp_path / "formal")

    result = manager.publish(candidate)

    assert result.ok
    assert manager.default is None
    assert result.loaded.components["tasks.example"].role == "task_workflow"
    assert result.loaded.components["flow.sub"].role == "sub_workflow"
    assert result.loaded.components["steps.finish"].role == "step"
    assert manager.actions["control"].classification == "control"
    saved_path = manager.manifests_dir / f"{result.loaded.manifest_id}.json"
    saved = json.loads(saved_path.read_text(encoding="utf-8"))
    assert set(saved) == {
        "schema_version",
        "manifest_id",
        "components",
        "recovery_rules",
    }
    assert "source_path" not in saved_path.read_text(encoding="utf-8")
    assert not (manager.manifests_dir / "default.json").exists()
    ids = {
        entry["component_id"]
        for section in ("components", "recovery_rules")
        for entry in saved[section].values()
    }
    assert all(component_id.startswith("sha256:") for component_id in ids)
    assert {
        path.stem for path in manager.components_dir.glob("*.py")
    } == {component_id.removeprefix("sha256:") for component_id in ids}

    assert manager.set_default(result.loaded.manifest_id).ok
    reloaded = ManifestManager(tmp_path / "formal").load_default()
    assert reloaded.ok
    assert (
        reloaded.loaded.components["tasks.example"].module
        is result.loaded.components["tasks.example"].module
    )


def test_validation_collects_independent_manifest_errors_without_switching(tmp_path: Path) -> None:
    manager = ManifestManager(tmp_path / "formal")
    valid = manager.publish(_write_candidate(tmp_path / "valid"))
    assert valid.ok
    assert manager.set_default(valid.loaded.manifest_id).ok
    default_id = valid.loaded.manifest_id
    invalid = {
        "schema_version": 1,
        "components": {"not valid!": {"source_path": "../outside.py", "extra": True}},
        "recovery_rules": {"not valid!": {"component_id": "bad"}},
        "trusted_actions": {
            "bad.action": {"source_path": "../outside.py", "classification": "bad"}
        },
        "assets": {"not": "implemented"},
        "unknown": True,
    }
    path = tmp_path / "invalid" / "candidate.json"
    path.parent.mkdir()
    path.write_text(json.dumps(invalid), encoding="utf-8")

    result = manager.publish(path)

    assert {
        "field_unknown",
        "schema_version_unsupported",
        "logical_name_invalid",
        "logical_name_duplicate",
        "source_path_escape",
        "component_id_invalid",
    } <= _codes(result)
    assert manager.default.manifest_id == default_id
    assert json.loads((manager.manifests_dir / "default.json").read_text(encoding="utf-8")) == {
        "manifest_id": default_id
    }


def test_duplicate_keys_and_candidate_manifest_id_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "candidate.json"
    path.write_text(
        '{"schema_version":1,"schema_version":1,"manifest_id":"x",'
        '"components":{},"recovery_rules":{},"trusted_actions":{},"assets":{}}',
        encoding="utf-8",
    )

    errors = ManifestManager(tmp_path / "formal").validate(path)

    assert {"json_key_duplicate", "field_unknown", "manifest_id_forbidden"} <= {
        error.code for error in errors
    }


def test_source_validation_reports_calls_roles_permissions_and_control_flow(tmp_path: Path) -> None:
    sources = dict(SOURCES)
    sources["task.py"] = '''"""Invalid Task Workflow."""
from lalc import task_workflow

@task_workflow
def execute(ctx, *, amount: int = 1) -> dict[str, int]:
    ctx.action("control")
    ctx.call(amount)
    ctx.call("missing.component", amount=amount)
    ctx.call("tasks.example", amount=amount)
    return ctx.call("flow.sub", amount=amount)

'''
    sources["sub.py"] = '''"""Invalid nested Subworkflow call."""
from lalc import sub_workflow

@sub_workflow
def execute(ctx, *, amount: int = 1) -> dict[str, int]:
    return ctx.call("flow.other", amount=amount)
'''
    sources["other.py"] = '''"""Other Subworkflow."""
from lalc import sub_workflow

@sub_workflow
def execute(ctx, *, amount: int = 1) -> dict[str, int]:
    return ctx.call("steps.finish", amount=amount)
'''
    sources["step.py"] = '''"""Invalid Step."""
import third_party
from lalc import step

@step
def execute(ctx, *, amount: int = 1) -> dict[str, int]:
    try:
        return ctx.call(amount)
    except Exception:
        return {"amount": amount}
    finally:
        return {"amount": amount}
'''
    candidate = _write_candidate(tmp_path / "candidate", sources=sources)
    data = json.loads(candidate.read_text(encoding="utf-8"))
    data["components"]["flow.other"] = {"source_path": "other.py"}
    candidate.write_text(json.dumps(data), encoding="utf-8")

    errors = ManifestManager(tmp_path / "formal").validate(candidate)
    codes = {error.code for error in errors}

    assert {
        "trusted_action_forbidden",
        "component_call_forbidden",
        "component_call_dynamic",
        "component_call_unresolved",
        "component_call_role_invalid",
        "except_forbidden",
        "finally_control_flow_forbidden",
        "import_forbidden",
    } <= codes
    assert any(
        error.code == "component_call_role_invalid"
        and error.logical_name == "flow.sub"
        and "Subworkflow cannot call another Subworkflow" in error.message
        for error in errors
    )
    assert all(error.line is not None for error in errors if error.code in {"except_forbidden", "import_forbidden"})


def test_path_escape_and_manifest_action_registration_are_rejected(tmp_path: Path) -> None:
    candidate = _write_candidate(tmp_path / "candidate")
    data = json.loads(candidate.read_text(encoding="utf-8"))
    data["components"]["steps.finish"] = {"source_path": "../outside.py"}
    data["trusted_actions"] = {
        "source_path": "control.py",
        "classification": "observe",
    }
    candidate.write_text(json.dumps(data), encoding="utf-8")

    errors = ManifestManager(tmp_path / "formal").validate(candidate)

    assert {"source_path_escape", "field_unknown"} <= {
        error.code for error in errors
    }


def test_import_failure_and_default_write_failure_keep_old_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    manager = ManifestManager(tmp_path / "formal")
    initial = manager.publish(_write_candidate(tmp_path / "initial"))
    assert initial.ok
    assert manager.set_default(initial.loaded.manifest_id).ok
    default_id = initial.loaded.manifest_id

    failing_sources = dict(SOURCES)
    failing_sources["step.py"] = '''"""Broken trusted observation."""
from lalc import step
raise RuntimeError("import failed")
@step
def execute(ctx, *, name: str = "state") -> dict[str, str]:
    return {"name": name}
'''
    failed_import = manager.publish(_write_candidate(tmp_path / "failed-import", sources=failing_sources))
    assert _codes(failed_import) == {"component_import_failed"}
    assert manager.default.manifest_id == default_id

    changed_sources = dict(SOURCES)
    changed_sources["step.py"] = SOURCES["step.py"].replace("amount >= 0", "amount > -1")
    candidate = _write_candidate(tmp_path / "write-failure", sources=changed_sources)
    real_atomic_write = manifest_module.atomic_write_json

    def fail_default(path: Path, value: dict) -> None:
        if path.name == "default.json":
            raise OSError("scripted default write failure")
        real_atomic_write(path, value)

    monkeypatch.setattr(manifest_module, "atomic_write_json", fail_default)
    published = manager.publish(candidate)
    assert published.ok
    with caplog.at_level(logging.ERROR):
        failed_write = manager.set_default(published.loaded.manifest_id)

    assert _codes(failed_write) == {"manifest_update_failed"}
    assert manager.default.manifest_id == default_id
    assert "Manifest update failed during set_default" in caplog.text
    assert "scripted default write failure" in caplog.text
    assert json.loads((manager.manifests_dir / "default.json").read_text(encoding="utf-8")) == {
        "manifest_id": default_id
    }
    assert len(list(manager.manifests_dir.glob("*.json"))) >= 3


def test_static_error_prevents_every_component_import(tmp_path: Path) -> None:
    marker = tmp_path / "imported.txt"
    sources = dict(SOURCES)
    sources["task.py"] = SOURCES["task.py"].replace(
        'ctx.call("steps.finish", amount=amount)', "ctx.call(amount)"
    )
    sources["step.py"] = f'''"""Observation with a visible import side effect."""
from pathlib import Path
from lalc import step
Path({str(marker)!r}).write_text("imported", encoding="utf-8")
@step
def execute(ctx, *, name: str = "state") -> dict[str, str]:
    return {{"name": name}}
'''

    result = ManifestManager(tmp_path / "formal").publish(
        _write_candidate(tmp_path / "candidate", sources=sources)
    )

    assert "component_call_dynamic" in _codes(result)
    assert not marker.exists()


def test_existing_saved_manifest_can_be_selected_without_creating_another(tmp_path: Path) -> None:
    manager = ManifestManager(tmp_path / "formal")
    first = manager.publish(_write_candidate(tmp_path / "first"))
    changed_sources = dict(SOURCES)
    changed_sources["step.py"] = SOURCES["step.py"].replace("amount >= 0", "amount > -1")
    second = manager.publish(_write_candidate(tmp_path / "second", sources=changed_sources))
    assert first.ok and second.ok
    assert manager.set_default(second.loaded.manifest_id).ok
    saved_before = set(manager.manifests_dir.glob("*.json"))

    selected = manager.set_default(first.loaded.manifest_id)

    assert selected.ok
    assert manager.default.manifest_id == first.loaded.manifest_id
    assert set(manager.manifests_dir.glob("*.json")) == saved_before
    assert json.loads((manager.manifests_dir / "default.json").read_text(encoding="utf-8")) == {
        "manifest_id": first.loaded.manifest_id
    }


def test_candidate_can_mix_existing_component_id_with_new_source(tmp_path: Path) -> None:
    manager = ManifestManager(tmp_path / "formal")
    first = manager.publish(_write_candidate(tmp_path / "first"))
    assert first.ok
    old_task = first.loaded.components["tasks.example"]
    sources = dict(SOURCES)
    sources["step.py"] = SOURCES["step.py"].replace("amount >= 0", "amount > -1")
    candidate = _write_candidate(tmp_path / "second", sources=sources)
    data = json.loads(candidate.read_text(encoding="utf-8"))
    data["components"]["tasks.example"] = {"component_id": old_task.component_id}
    candidate.write_text(json.dumps(data), encoding="utf-8")

    second = manager.publish(candidate)

    assert second.ok
    assert second.loaded.components["tasks.example"].module is old_task.module
    assert (
        second.loaded.components["steps.finish"].component_id
        != first.loaded.components["steps.finish"].component_id
    )


def test_changed_formal_source_is_rejected_before_loading(tmp_path: Path) -> None:
    manager = ManifestManager(tmp_path / "formal")
    published = manager.publish(_write_candidate(tmp_path / "candidate"))
    assert published.ok
    assert manager.set_default(published.loaded.manifest_id).ok
    component_id = published.loaded.components["steps.finish"].component_id
    path = manager.components_dir / f"{component_id.removeprefix('sha256:')}.py"
    path.write_text("changed", encoding="utf-8")

    reloaded = ManifestManager(tmp_path / "formal").load_default()
    reselected = manager.set_default(published.loaded.manifest_id)

    assert "component_id_mismatch" in _codes(reloaded)
    assert "component_id_mismatch" in _codes(reselected)
    assert reloaded.loaded is None
