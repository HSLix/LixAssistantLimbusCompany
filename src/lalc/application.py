from __future__ import annotations

import json
import logging
import sys
import threading
import time
import uuid
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from .focused import FocusedAutomationSession, WindowsWindowPlatform, WindowError
from .ledger import LedgerWriteError, WorkflowRunLedger, application_event_totals, workflow_health
from .manifest import LoadedManifest, ManifestManager
from .runtime import (
    InputValidationError,
    RunGate,
    RunCancelled,
    TraceWriteError,
    WorkingManifestWriteError,
    WorkflowExecutor,
    atomic_write_json,
)


class StartError(RuntimeError):
    """运行建立前的结构化同步拒绝。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ApplicationService:
    """GUI 与自动化测试共享的异步正式运行入口。"""

    def __init__(
        self,
        data_root: Path,
        *,
        manifest_manager: ManifestManager | None = None,
        on_change: Callable[[dict[str, Any]], None] | None = None,
        logger: logging.Logger | None = None,
        recovery_choice: Callable[[str, str, tuple[str, ...]], str | None] | None = None,
        window_platform: Any | None = None,
    ) -> None:
        self.data_root = Path(data_root)
        self.manifest_manager = manifest_manager or ManifestManager(self.data_root)
        self.on_change = on_change
        self.logger = logger or logging.getLogger(__name__)
        self.recovery_choice = recovery_choice
        self.window_platform = window_platform
        self._focused_session: FocusedAutomationSession | None = None
        self._condition = threading.Condition()
        self._thread: threading.Thread | None = None
        self._gate: RunGate | None = None
        self._trace_path: Path | None = None
        self._ledger: WorkflowRunLedger | None = None
        self._state: dict[str, Any] = {
            "phase": "idle",
            "paused": False,
            "default_manifest_id": self.manifest_manager.default_manifest_id(),
            "base_manifest_id": None,
            "working_manifest_id": None,
            "attempted_manifest_ids": [],
            "run_id": None,
            "entry": None,
            "result": None,
            "trace": [],
        }

    @property
    def state(self) -> dict[str, Any]:
        """返回不会与服务内部共享可变对象的公共状态快照。"""

        with self._condition:
            self._state["default_manifest_id"] = self.manifest_manager.default_manifest_id()
            return deepcopy(self._state)

    def wait_for(self, predicate: Callable[[dict[str, Any]], bool]) -> dict[str, Any]:
        """等待公共状态满足条件；等待本身不改变或终止运行。"""

        with self._condition:
            self._condition.wait_for(lambda: predicate(deepcopy(self._state)))
            return deepcopy(self._state)

    def start(
        self, logical_name: str, inputs: dict[str, Any], *, manifest_id: str | None = None
    ) -> int:
        """同步校验启动请求，再在单一后台线程执行已捕获的 Manifest。"""

        with self._condition:
            if self._state["phase"] == "running":
                raise StartError("run_already_active", "Another Run is already active.")
            manifest = self._loaded_manifest(manifest_id)
            component = manifest.components.get(logical_name)
            if component is None:
                raise StartError("entry_not_found", f"Unknown runnable Component: {logical_name}")
            try:
                normalized_inputs = WorkflowExecutor.prepare_inputs(component, inputs)
            except (InputValidationError, TypeError, ValueError) as error:
                raise StartError("inputs_invalid", str(error)) from error

            entry = {"logical_name": logical_name, "component_id": component.component_id, "role": component.role}
            run_id, snapshot, gate = self._begin_run(manifest, entry, normalized_inputs)

            self._thread = threading.Thread(
                target=self._run,
                args=(snapshot, logical_name, component.component_id, normalized_inputs, gate),
                name=f"lalc-run-{run_id}",
                daemon=True,
            )
            self._thread.start()
            self._changed_locked()
            return run_id

    def start_plan(self, path: Path, *, manifest_id: str | None = None) -> int:
        """启动用户保存的 JSON Plan；结构问题作为本次 Run 的 invalid_plan 结果。"""

        with self._condition:
            if self._state["phase"] == "running":
                raise StartError("run_already_active", "Another Run is already active.")
            manifest = self._loaded_manifest(manifest_id)
            try:
                source: str | Exception = Path(path).read_text(encoding="utf-8")
            except (OSError, UnicodeError) as error:
                source = error
            entry = {"role": "automation_plan", "path": str(path)}
            run_id, snapshot, gate = self._begin_run(manifest, entry, {})
            self._thread = threading.Thread(
                target=self._run_plan, args=(snapshot, source, gate),
                name=f"lalc-run-{run_id}", daemon=True,
            )
            self._thread.start()
            self._changed_locked()
            return run_id

    def connect(self) -> dict[str, Any]:
        """检查唯一游戏窗口并留下截图与文字连接日志，不创建 Run。"""

        with self._condition:
            if self._state["phase"] == "running":
                raise WindowError("Cannot connect while a Run is active.")
            session = FocusedAutomationSession(self._window_platform(), lambda _event, _fields: None)
            window = session.connect()
            image = session.capture()
            identity = uuid.uuid4().hex
            directory = self.data_root / "connections"
            image_path = directory / f"{identity}.png"
            log_path = directory / f"{identity}.log"
            try:
                session.save(image_path)
                log_path.write_text(
                    "\n".join((
                        f"recorded_at={datetime.now(UTC).isoformat()}",
                        f"hwnd={window['hwnd']}",
                        f"process_id={window['process_id']}",
                        f"process_path={window['process_path']}",
                        f"title={window['title']}",
                        f"class={window['class']}",
                        f"image_path={image_path}",
                        f"width={image['width']}",
                        f"height={image['height']}",
                    )) + "\n", encoding="utf-8",
                )
            except Exception:
                image_path.unlink(missing_ok=True)
                log_path.unlink(missing_ok=True)
                raise
            return {"window": window, "image": image, "image_path": str(image_path), "log_path": str(log_path)}

    def _window_platform(self) -> Any:
        return self.window_platform if self.window_platform is not None else WindowsWindowPlatform()

    def _capture_screen(self, save: bool) -> dict[str, Any]:
        """Trusted Action 入口：刷新本次 Run 的内存图像并可显式保存。"""

        if self._focused_session is None:
            self._focused_session = FocusedAutomationSession(self._window_platform(), self._emit)
        result: dict[str, Any] = self._focused_session.capture()
        if save:
            run_id = self._state["run_id"]
            assert run_id is not None
            path = self.data_root / "evidence" / str(run_id) / f"{result['observation']}.png"
            evidence_id = f"{run_id}/{result['observation']}"
            saved = self._focused_session.save(path, evidence_id=evidence_id)
            result["evidence_path"] = saved["path"]
            result["evidence_id"] = evidence_id
        return result

    def ledger_records(self) -> list[dict[str, Any]]:
        """读取当前 Run 的持久化 Workflow 记录。"""

        with self._condition:
            return deepcopy(self._ledger.records) if self._ledger else []

    def workflow_health(self) -> dict[str, dict[str, Any]]:
        """从持久化记录重算各 Workflow Component 的健康统计。"""

        return workflow_health(self.data_root)

    def application_event_totals(self) -> dict[str, int]:
        """读取跨 Run 的唯一恢复和 Agent 事件计数。"""

        return application_event_totals(self.data_root)

    def _begin_run(
        self, manifest: LoadedManifest, entry: dict[str, Any], inputs: dict[str, Any]
    ) -> tuple[int, LoadedManifest, RunGate]:
        """为直接运行与 Plan 建立同一个持久 Run 边界。"""

        run_id = self._allocate_run_id()
        snapshot = _manifest_snapshot(manifest)
        gate = RunGate()
        trace_path = self.data_root / "traces" / f"{run_id}.jsonl"
        if trace_path.exists():
            raise StartError("trace_conflict", f"Trace already exists for Run {run_id}.")
        self._gate = gate
        self._focused_session = None
        self._trace_path = trace_path
        self._ledger = WorkflowRunLedger(self.data_root, run_id)
        self._state.update(
            phase="running", paused=False,
            default_manifest_id=self.manifest_manager.default_manifest_id(),
            base_manifest_id=snapshot.manifest_id,
            working_manifest_id=snapshot.manifest_id,
            attempted_manifest_ids=[snapshot.manifest_id], run_id=run_id,
            entry=entry, result=None, trace=[],
        )
        try:
            self._persist_working_locked()
            self._record_locked("run_started", {**entry, "base_manifest_id": snapshot.manifest_id, "inputs": deepcopy(inputs)})
        except TraceWriteError as error:
            self._state.update(phase="idle", base_manifest_id=None, working_manifest_id=None, attempted_manifest_ids=[], run_id=None, entry=None, trace=[])
            self._gate = None
            self._trace_path = None
            self._ledger = None
            code = "working_manifest_unavailable" if isinstance(error, WorkingManifestWriteError) else "trace_unavailable"
            raise StartError(code, str(error)) from error
        return run_id, snapshot, gate

    def pause(self) -> None:
        with self._condition:
            if self._state["phase"] != "running" or self._gate is None or not self._gate.pause():
                return
            self._state["paused"] = True
            self._record_locked("run_paused", {})

    def resume(self) -> None:
        with self._condition:
            if self._state["phase"] != "running" or self._gate is None or not self._gate.resume():
                return
            self._state["paused"] = False
            self._record_locked("run_resumed", {})

    def stop(self) -> None:
        with self._condition:
            if self._state["phase"] != "running" or self._gate is None or not self._gate.stop():
                return
            self._state["paused"] = False
            self._record_locked("run_cancel_requested", {})

    def _run(
        self,
        manifest: LoadedManifest,
        logical_name: str,
        component_id: str,
        inputs: dict[str, Any],
        gate: RunGate,
    ) -> None:
        component = manifest.components[logical_name]
        assert component.component_id == component_id
        executor = WorkflowExecutor(
            manifest, gate, self._emit,
            capture_screen=self._capture_screen,
            manifest_manager=self.manifest_manager,
            choose_manifest=self.recovery_choice,
            select_manifest=self._select_working_manifest,
        )
        started = time.monotonic()
        started_at = datetime.now(UTC).isoformat()
        try:
            result = executor.run(logical_name, component, inputs)
            if component.role == "task_workflow":
                assert self._ledger is not None
                self._ledger.finish_task(
                    {"logical_name": logical_name, "component_id": component.component_id,
                     "manifest_id": manifest.manifest_id, "inputs": inputs,
                     "recorded_at": started_at, "ended_at": datetime.now(UTC).isoformat()},
                    result, round((time.monotonic() - started) * 1000, 3),
                )
            elif component.role == "sub_workflow":
                assert self._ledger is not None
                self._ledger.finish_direct_subworkflow(
                    result, datetime.now(UTC).isoformat(),
                    round((time.monotonic() - started) * 1000, 3),
                )
        except LedgerWriteError as error:
            result = WorkflowExecutor._failure(logical_name, component, "ledger_write_failed", str(error))
        except WorkingManifestWriteError as error:
            result = {
                "status": "failure",
                "logical_name": logical_name,
                "component_id": component.component_id,
                "role": component.role,
                "failure_code": "working_manifest_write_failed",
                "failure_message": str(error),
            }
        except TraceWriteError as error:
            result = {
                "status": "failure",
                "logical_name": logical_name,
                "component_id": component.component_id,
                "role": component.role,
                "failure_code": "trace_write_failed",
                "failure_message": str(error),
            }

        self._complete(result)

    def _run_plan(self, manifest: LoadedManifest, source: str | Exception, gate: RunGate) -> None:
        """一次预检后按冻结顺序逐项执行，并复用同一个 Working Manifest。"""

        executor = WorkflowExecutor(
            manifest, gate, self._emit,
            capture_screen=self._capture_screen,
            manifest_manager=self.manifest_manager,
            choose_manifest=self.recovery_choice,
            select_manifest=self._select_working_manifest,
        )
        items, errors = _prepare_plan(source, manifest)
        if errors:
            self._complete({"status": "interrupted", "reason": "invalid_plan", "errors": errors, "items": []})
            return
        completed: list[dict[str, Any]] = []
        reason: str | None = None
        try:
            for index, item in enumerate(items):
                gate.checkpoint()
                assert self._ledger is not None
                self._ledger.item_index = index
                prior_records = len(self._ledger.records)
                name, frozen_inputs = item["task"], item["inputs"]
                component = executor.manifest.components.get(name)
                started = time.monotonic()
                started_at = datetime.now(UTC).isoformat()
                if component is None or component.role != "task_workflow":
                    task_result = {
                        "status": "failure", "failure_code": "working_manifest_incompatible",
                        "failure_message": f"Task Workflow is unavailable: {name}",
                    }
                else:
                    try:
                        current_inputs = WorkflowExecutor.prepare_inputs(component, frozen_inputs)
                    except (InputValidationError, TypeError, ValueError) as error:
                        task_result = {
                            "status": "failure", "failure_code": "working_manifest_incompatible",
                            "failure_message": str(error),
                        }
                    else:
                        task_result = executor.run(name, component, current_inputs)
                duration = round((time.monotonic() - started) * 1000, 3)
                if component is not None and component.role == "task_workflow":
                    self._ledger.finish_task(
                        {"logical_name": name, "component_id": component.component_id,
                         "manifest_id": executor.manifest.manifest_id, "inputs": frozen_inputs,
                         "recorded_at": started_at, "ended_at": datetime.now(UTC).isoformat()},
                        task_result, duration,
                    )
                if task_result.get("failure_code") == "user_cancelled" and len(self._ledger.records) == prior_records:
                    reason = "user_cancelled"
                    break
                completed.append({"index": index, "task": name, "inputs": frozen_inputs,
                                  "result": task_result["status"], "run_id": self._state["run_id"],
                                  "duration_ms": duration,
                                  **({"failure_code": task_result["failure_code"],
                                      "failure_message": task_result["failure_message"]}
                                     if task_result["status"] == "failure" else {})})
                self._emit("plan_item_finished", {"index": index, "task": name, "result": task_result})
                if gate.stopped:
                    reason = "user_cancelled"
                    break
        except RunCancelled:
            reason = "user_cancelled"
        except LedgerWriteError:
            reason = "ledger_write_failed"
        except WorkingManifestWriteError:
            reason = "working_manifest_write_failed"
        except TraceWriteError:
            reason = "trace_write_failed"
        except Exception as error:
            reason = "plan_execution_failed"
            self.logger.exception("Automation Plan scheduling failed: %s", error)
        self._complete({"status": "interrupted" if reason else "completed",
                        **({"reason": reason} if reason else {}), "items": completed})

    def _complete(self, result: dict[str, Any]) -> None:
        """写入最终事实并发布一次 Run 的结果。"""

        with self._condition:
            try:
                self._record_locked("run_finished", {"result": deepcopy(result)})
            except TraceWriteError as error:
                if self._state["entry"]["role"] == "automation_plan":
                    result = {"status": "interrupted", "reason": "trace_write_failed",
                              "items": result.get("items", [])}
                else:
                    result = {**{key: result[key] for key in ("logical_name", "component_id", "role")},
                              "status": "failure", "failure_code": "trace_write_failed",
                              "failure_message": str(error)}
            self._state.update(phase="finished", paused=False,
                               default_manifest_id=self.manifest_manager.default_manifest_id(), result=result)
            self._focused_session = None
            self._changed_locked()

    def _emit(self, event: str, fields: dict[str, Any]) -> None:
        with self._condition:
            self._record_locked(event, fields)

    def _select_working_manifest(self, manifest: LoadedManifest) -> None:
        """先持久化整份选择，再让执行器使用新 Manifest。"""

        with self._condition:
            previous = self._state["working_manifest_id"]
            attempts = self._state["attempted_manifest_ids"]
            self._state["working_manifest_id"] = manifest.manifest_id
            self._state["attempted_manifest_ids"] = list(dict.fromkeys([*attempts, manifest.manifest_id]))
            try:
                self._persist_working_locked()
            except WorkingManifestWriteError:
                self._state["working_manifest_id"] = previous
                self._state["attempted_manifest_ids"] = attempts
                raise
            self._changed_locked()

    def _persist_working_locked(self) -> None:
        """持久化当前与历史 Manifest ID，失败时阻止继续执行。"""

        try:
            atomic_write_json(
                self.data_root / "runs" / f"{self._state['run_id']}.json",
                {
                    "base_manifest_id": self._state["base_manifest_id"],
                    "working_manifest_id": self._state["working_manifest_id"],
                    "attempted_manifest_ids": self._state["attempted_manifest_ids"],
                },
            )
        except (OSError, TypeError, ValueError) as error:
            raise WorkingManifestWriteError(str(error)) from error

    def _record_locked(self, event: str, fields: dict[str, Any]) -> None:
        assert self._state["run_id"] is not None and self._trace_path is not None
        record = {
            "sequence": len(self._state["trace"]) + 1,
            "recorded_at": datetime.now(UTC).isoformat(),
            "run_id": self._state["run_id"],
            "event": event,
            **fields,
        }
        try:
            self._trace_path.parent.mkdir(parents=True, exist_ok=True)
            with self._trace_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
        except (OSError, TypeError, ValueError) as error:
            raise TraceWriteError(str(error)) from error
        self._state["trace"].append(record)
        if self._ledger is not None:
            self._ledger.observe(record)
        self._changed_locked()

    def _loaded_manifest(self, manifest_id: str | None) -> LoadedManifest:
        if manifest_id is not None:
            result = self.manifest_manager.load(manifest_id)
            if result.loaded is None:
                message = "; ".join(error.message for error in result.errors)
                raise StartError("manifest_unavailable", message)
            return result.loaded
        result = self.manifest_manager.load_default()
        if result.loaded is None:
            message = "; ".join(error.message for error in result.errors) or "No Default Manifest."
            raise StartError("default_manifest_unavailable", message)
        return result.loaded

    def _allocate_run_id(self) -> int:
        path = self.data_root / "run-sequence.json"
        try:
            if path.exists():
                value = json.loads(path.read_text(encoding="utf-8"))
                if type(value) is not dict or set(value) != {"last_run_id"} or type(value["last_run_id"]) is not int:
                    raise ValueError("run-sequence.json is invalid")
                last_run_id = value["last_run_id"]
            else:
                last_run_id = 0
            traces = self.data_root / "traces"
            existing_ids = [int(item.stem) for item in traces.glob("*.jsonl") if item.stem.isdecimal()]
            run_id = max([last_run_id, *existing_ids], default=0) + 1
            if run_id < 1:
                raise ValueError("Run ID must be positive")
            atomic_write_json(path, {"last_run_id": run_id})
            return run_id
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise StartError("run_id_allocation_failed", str(error)) from error

    def _changed_locked(self) -> None:
        self._condition.notify_all()
        if self.on_change is None:
            return
        try:
            self.on_change(deepcopy(self._state))
        except Exception:
            self.logger.exception("Application state callback failed")


def _manifest_snapshot(manifest: LoadedManifest) -> LoadedManifest:
    """复制 Manifest 映射，同时复用按内容寻址且不可变的已加载 Component。"""

    return LoadedManifest(
        deepcopy(manifest.manifest),
        dict(manifest.components),
        dict(manifest.recovery_rules),
        dict(manifest.trusted_actions),
    )


def _prepare_plan(
    source: str | Exception, manifest: LoadedManifest,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """一次收集 Plan 结构、Task 角色及输入错误，成功时冻结规范化输入。"""

    if isinstance(source, Exception):
        return [], [{"code": "plan_unreadable", "message": str(source)}]

    def unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"Duplicate JSON key: {key}")
            value[key] = item
        return value

    try:
        parsed = json.loads(source, object_pairs_hook=unique_keys)
    except (json.JSONDecodeError, ValueError) as error:
        return [], [{"code": "plan_invalid_json", "message": str(error)}]
    if type(parsed) is not dict or set(parsed) != {"items"} or type(parsed["items"]) is not list:
        return [], [{"code": "plan_invalid_structure", "message": "Plan must contain only an items list."}]
    errors: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    for index, item in enumerate(parsed["items"]):
        if type(item) is not dict:
            errors.append({"index": index, "code": "plan_item_invalid",
                           "message": "Each item must be a JSON object."})
            continue
        if set(item) - {"task", "inputs"}:
            errors.append({"index": index, "code": "plan_item_invalid",
                           "message": "Items may contain only task and inputs."})
        name, inputs = item.get("task"), item.get("inputs")
        component = manifest.components.get(name) if type(name) is str else None
        if type(name) is not str or not name:
            errors.append({"index": index, "code": "plan_task_invalid", "message": "task must be a nonempty logical name."})
        elif component is None:
            errors.append({"index": index, "code": "plan_task_missing", "message": f"Unknown Task Workflow: {name}"})
        elif component.role != "task_workflow":
            errors.append({"index": index, "code": "plan_task_role_invalid", "message": f"{name} is not a Task Workflow."})
        if "inputs" not in item or type(inputs) is not dict:
            errors.append({"index": index, "code": "plan_inputs_invalid", "message": "inputs must be a JSON object."})
        elif component is not None and component.role == "task_workflow":
            try:
                inputs = WorkflowExecutor.prepare_inputs(component, inputs)
            except (InputValidationError, TypeError, ValueError) as error:
                errors.append({"index": index, "code": "plan_inputs_invalid", "message": str(error)})
        items.append({"task": name, "inputs": inputs})
    return ([], errors) if errors else (items, [])


def default_data_root() -> Path:
    if sys.platform == "win32":
        import os

        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "LALC"
    return Path.home() / ".local" / "share" / "LALC"
