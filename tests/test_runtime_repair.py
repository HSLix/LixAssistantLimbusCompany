"""用执行器与会话替身覆盖 RunState、跨轮预算、同一 Session 和结束时版本选择。

从项目根目录运行：.venv/bin/python -m pytest tests/test_runtime_repair.py -q
本文件不启动 pi 或模型服务；真实工具交接另见显式 Agent 测试。
"""

import json

import pytest

from lalc.application import ApplicationService
from lalc.agent_settings import save_options, save_selection, save_settings
from lalc.manifest import ManifestManager, ManifestResult, ValidationError
from lalc.agent_log import read_json
from test_recovery import _publish, _rule, NEW_STEP, TASK, SUB
from test_plan import _finished
from runtime_support import add_plan


def test_saved_configuration_has_explicit_priority_and_each_run_is_independent(tmp_path):
    from lalc.user_pages import UserSettings
    manager = ManifestManager(tmp_path)
    source = '''"""读取并修改运行配置。"""
from lalc import step
@step
def execute(ctx) -> dict[str, int]:
    result = {"value": ctx.run_state.settings.get("page", {}).get("value", 0),
              "left": ctx.run_state.task_repetitions.get("task", 0)}
    ctx.run_state.settings.clear()
    return result
'''
    identity = _publish(tmp_path, manager, step_source=source)
    store = UserSettings(tmp_path)
    store.save("pages", "page", {"value": 7})
    store.save_task("task", True, 3)
    service = ApplicationService(tmp_path, manifest_manager=manager)
    def run(**options):
        return _finished(service, service.start("steps.break", {}, manifest_id=identity, **options))["result"]["output"]
    assert run(settings={"page": {"value": 2}}) == {"value": 7, "left": 3}
    assert run() == {"value": 7, "left": 3}
    assert run(use_saved_config=False, settings={"page": {"value": 2}}) == {"value": 2, "left": 0}
    assert run(use_saved_config=False) == {"value": 0, "left": 0}
    assert UserSettings(tmp_path).value["pages"] == {"page": {"value": 7}}


def test_old_plan_signature_is_rejected_without_compatibility(tmp_path):
    manager = ManifestManager(tmp_path)
    _publish(tmp_path, manager, step_source=NEW_STEP)
    path = tmp_path / "candidate-0" / "plan.py"
    path.write_text(path.read_text(encoding="utf-8").replace("execute(ctx)",
        "execute(ctx, *, task_repetitions: dict[str, int], settings: dict[str, Any])"), encoding="utf-8")
    rejected = manager.publish(path.parent / "manifest.json")
    assert not rejected.ok and "signature_invalid" in {error.code for error in rejected.errors}


def test_old_published_plan_can_be_copied_for_repair_without_loading_code(tmp_path, monkeypatch):
    import hashlib
    from lalc.developer_session import DeveloperSession
    manager = ManifestManager(tmp_path)
    identity = _publish(tmp_path, manager, step_source=NEW_STEP)
    path = manager.manifests_dir / f"{identity}.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    old = b'"""Old Plan."""\nfrom typing import Any\nfrom lalc import automation_plan\n@automation_plan\ndef execute(ctx, *, task_repetitions: dict[str, int], settings: dict[str, Any]) -> None:\n    return None\n'
    digest = hashlib.sha256(old).hexdigest()
    (manager.components_dir / f"{digest}.py").write_bytes(old)
    value["components"]["plans.default"]["component_id"] = f"sha256:{digest}"
    path.write_text(json.dumps(value), encoding="utf-8")
    assert not manager.load(identity).ok
    service = ApplicationService(tmp_path, manifest_manager=manager)
    with monkeypatch.context() as patch:
        patch.setattr(manager, "_load_module", lambda *args, **kwargs: pytest.fail("Migration copy imported source"))
        session = DeveloperSession.create(service, identity)
    copied = session.host.candidate / "plans.default.py"
    assert copied.read_bytes() == old
    assert not manager.publish(session.host.candidate / "manifest.json").ok
    copied.write_bytes(old.replace(b'ctx, *, task_repetitions: dict[str, int], settings: dict[str, Any]', b'ctx'))
    assert manager.publish(session.host.candidate / "manifest.json").ok
    assert (manager.components_dir / f"{digest}.py").read_bytes() == old


def runtime_settings(root, requests=2):
    """启用 User 侧修复；模型请求由测试替身接管。"""
    save_settings(root, {"provider": "llama.cpp", "model": "unit", "max_requests": requests})
    save_selection(root, "user", "llama.cpp", enabled=True)


@pytest.mark.parametrize("role", ["task", "sub", "plan"])
def test_each_entry_repairs_its_own_failure_and_preserves_waiting_caller(tmp_path, role):
    manager = ManifestManager(tmp_path)
    failure = '    raise ExecutionFailure("own scheduling failed")\n'
    def failing(source):
        prefix = source[:source.index("    ", source.index("def execute"))]
        return prefix.replace("from lalc import ", "from lalc import ExecutionFailure, ") + failure
    base = _publish(tmp_path, manager, step_source=NEW_STEP,
                    task_source=failing(TASK) if role == "task" else TASK,
                    sub_source=failing(SUB) if role == "sub" else SUB)
    if role == "plan":
        candidate = tmp_path / "candidate-0" / "manifest.json"
        add_plan(candidate, failure)
        plan = candidate.with_name("plan.py")
        plan.write_text(plan.read_text(encoding="utf-8").replace("from lalc import automation_plan", "from lalc import automation_plan, ExecutionFailure"), encoding="utf-8")
        base = manager.publish(candidate).loaded.manifest_id
    selected = _publish(tmp_path, manager, step_source=NEW_STEP)
    seen = []
    def choose(reason, logical_name, attempts):
        seen.append(logical_name)
        return selected
    service = ApplicationService(tmp_path, manifest_manager=manager, recovery_choice=choose)
    state = _finished(service, service.start_plan(manifest_id=base) if role == "plan" else
                      service.start("tasks.run", {"value": 4}, manifest_id=base))
    assert state["result"]["status"] == ("completed" if role == "plan" else "success"), state["result"]
    assert seen == [{"plan": "plans.default", "task": "tasks.run", "sub": "flows.next"}[role]]
    if role != "plan":
        assert state["result"]["output"] == ["task-old", "step-new:4", "sub-old"]
        task_starts = [row for row in state["trace"] if row["event"] == "component_started" and row.get("logical_name") == "tasks.run"]
        assert len(task_starts) == (2 if role == "task" else 1)
        ledger = json.loads((tmp_path / "ledger" / f'{state["run_id"]}.json').read_text(encoding="utf-8"))
        tasks = [row for row in ledger["records"] if row["workflow_kind"] == "task"]
        assert len(tasks) == 1 and len(tasks[0]["attempts"]) == len(task_starts)


def test_recheck_failures_share_session_and_remaining_requests(tmp_path, monkeypatch):
    from lalc.agent_repair import RepairConversation
    manager = ManifestManager(tmp_path)
    broken = '''"""记录失败前的共享状态。"""
from lalc import step, ExecutionFailure
@step
def execute(ctx, *, value: int) -> str:
    state = ctx.run_state.settings.setdefault("progress", {})
    state["attempts"] = state.get("attempts", 0) + 1
    raise ExecutionFailure("broken")
'''
    base = _publish(tmp_path, manager, step_source=broken)
    assert manager.set_default(base).ok
    runtime_settings(tmp_path)
    seen = []
    async def round(self, message, args, *, request_limit, **kwargs):
        self.log.group += 1
        self.tools.requested_manifest_id = None
        self.tools.cancelled.clear()
        seen.append((self.session.identity, request_limit, self.tools.read_run_state()["details"]))
        if len(seen) == 2:
            (self.host.candidate / json.loads((self.host.candidate / "manifest.json").read_text(encoding="utf-8"))["components"]["steps.break"]["source_path"]).write_text(NEW_STEP, encoding="utf-8")
        published = read_json(self.tools.call("publish", {"summary": "修复失败入口"}))
        assert published["details"]["ok"]
        selected = published["details"]["manifest_id"]
        handoff = read_json(self.tools.call("recheck", {"manifest_id": selected}))
        assert not handoff.get("isError")
        return {"status": "recheck", "manifest_id": selected, "requests": 1, "round": self.log.group}
    monkeypatch.setattr(RepairConversation, "run", round)
    service = ApplicationService(tmp_path, manifest_manager=manager)
    state = _finished(service, service.start("tasks.run", {"value": 4}, manifest_id=base))
    assert state["result"]["status"] == "success", state["result"].get("traceback", state["result"])
    assert state["result"]["output"] == ["task-old", "step-new:4", "sub-old"]
    assert [remaining for _, remaining, _ in seen] == [2, 1]
    assert len({identity for identity, _, _ in seen}) == 1
    assert [snapshot["settings"]["progress"]["attempts"] for _, _, snapshot in seen] == [1, 2]
    assert state["default_update"]["status"] == "changed"
    assert service.manifest_manager.default_manifest_id() == state["working_manifest_id"]
    assert service._runtime_chat.tools.run_state is None
    # 相同存储和身份可在 Developer 入口继续，不继承原 Run 执行权。
    from lalc.developer_session import DeveloperSession
    continued = DeveloperSession(service, seen[0][0], entry="gui").conversation()
    assert continued.entry == "gui" and "recheck" not in continued.allowed


def test_rule_limit_hands_off_and_step_success_resets_counter(tmp_path, monkeypatch):
    from lalc.agent_repair import RepairConversation
    manager = ManifestManager(tmp_path)
    source = NEW_STEP.replace('return f"step-new:{value}"', 'raise ExecutionFailure("still broken")').replace(
        "from lalc import step", "from lalc import step, ExecutionFailure")
    base = _publish(tmp_path, manager, step_source=source, rules={"retry": _rule("return True")})
    runtime_settings(tmp_path)
    save_options(tmp_path, recovery_limit=3)
    counts = []
    async def round(self, message, args, **kwargs):
        counts.append(self.tools.run_state.recovery_count)
        (self.host.candidate / json.loads((self.host.candidate / "manifest.json").read_text(encoding="utf-8"))["components"]["steps.break"]["source_path"]).write_text(NEW_STEP, encoding="utf-8")
        saved = read_json(self.tools.call("publish", {"summary": "修复反复失败"}))["details"]["manifest_id"]
        return {"status": "recheck", "manifest_id": saved, "requests": 1}
    monkeypatch.setattr(RepairConversation, "run", round)
    service = ApplicationService(tmp_path, manifest_manager=manager)
    state = _finished(service, service.start("tasks.run", {"value": 1}, manifest_id=base))
    assert state["result"]["status"] == "success" and counts == [0], state["result"].get("traceback", state["result"])
    trace = state["trace"]
    assert sum(row["event"] == "recovery_rule_returned" and row["phase"] == "recover" for row in trace) == 4
    assert sum(row["event"] == "agent_invoked" for row in trace) == 1


@pytest.mark.parametrize("finish,automatic,update", [("completed", True, True), ("completed", False, False),
                                                    ("interrupted", True, False), ("cancelled", True, False)])
def test_default_selection_uses_plan_completion_not_all_task_success(tmp_path, finish, automatic, update):
    manager = ManifestManager(tmp_path)
    broken = NEW_STEP.replace('return f"step-new:{value}"', 'raise ExecutionFailure("broken")').replace(
        "from lalc import step", "from lalc import step, ExecutionFailure")
    base = _publish(tmp_path, manager, step_source=broken)
    candidate = tmp_path / "candidate-0" / "manifest.json"
    tail = ('    raise ExecutionFailure("plan broken")\n' if finish == "interrupted" else
            '    raise UserInterruption()\n' if finish == "cancelled" else
            '    ctx.call("tasks.run", value=-1)\n')
    add_plan(candidate, '    ctx.call("tasks.run", value=1)\n' + tail)
    plan = candidate.with_name("plan.py")
    plan.write_text(plan.read_text(encoding="utf-8").replace("from lalc import automation_plan", "from lalc import automation_plan, ExecutionFailure, UserInterruption"), encoding="utf-8")
    base = manager.publish(candidate).loaded.manifest_id
    repaired = NEW_STEP.replace('    return f"step-new:{value}"', '    if value < 0:\n        raise ExecutionFailure("task failed")\n    return f"step-new:{value}"').replace("from lalc import step", "from lalc import step, ExecutionFailure")
    selected = _publish(tmp_path, manager, step_source=repaired)
    assert manager.set_default(base).ok
    save_options(tmp_path, automatic_repair_default=automatic)
    choices = iter([selected])
    service = ApplicationService(tmp_path, manifest_manager=manager, recovery_choice=lambda *_: next(choices, None))
    state = _finished(service, service.start_plan(manifest_id=base))
    assert manager.default_manifest_id() == (selected if update else base)
    assert bool(state["default_update"]) == update
    if finish == "completed":
        assert state["result"]["status"] == "completed" and not state["result"]["all_tasks_succeeded"]


def test_default_write_rejection_does_not_change_successful_execution(tmp_path, monkeypatch):
    manager = ManifestManager(tmp_path)
    broken = NEW_STEP.replace('return f"step-new:{value}"', 'raise ExecutionFailure("broken")').replace(
        "from lalc import step", "from lalc import step, ExecutionFailure")
    base = _publish(tmp_path, manager, step_source=broken)
    selected = _publish(tmp_path, manager, step_source=NEW_STEP)
    manager.set_default(base)
    monkeypatch.setattr(manager, "set_default", lambda _: ManifestResult(errors=(ValidationError("write_failed", "cannot save"),)))
    service = ApplicationService(tmp_path, manifest_manager=manager, recovery_choice=lambda *_: selected)
    state = _finished(service, service.start_plan(manifest_id=base))
    assert state["result"]["status"] == "completed"
    assert state["default_update"]["status"] == "failed" and manager.default_manifest_id() == base


def test_developer_trial_never_starts_runtime_agent(tmp_path, monkeypatch):
    manager = ManifestManager(tmp_path)
    broken = NEW_STEP.replace('return f"step-new:{value}"', 'raise ExecutionFailure("broken")').replace(
        "from lalc import step", "from lalc import step, ExecutionFailure")
    base = _publish(tmp_path, manager, step_source=broken)
    runtime_settings(tmp_path)
    service = ApplicationService(tmp_path, manifest_manager=manager)
    monkeypatch.setattr(service, "_runtime_repair", lambda *_: pytest.fail("Developer Trial started Runtime Agent"))
    with service.activity("Agent"):
        state = _finished(service, service.start("steps.break", {"value": 1}, manifest_id=base, _developer_trial=True))
    assert state["result"]["status"] == "failure" and service._runtime_chat is None
