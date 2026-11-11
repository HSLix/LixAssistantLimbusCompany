from __future__ import annotations

import hashlib
import inspect
import json
import math
import threading
import time
import traceback
import types
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Literal, Union, get_args, get_origin, get_type_hints

from .run_context import RunContext as RunContext, RunState as RunState

if TYPE_CHECKING:
    from .manifest import LoadedComponent, LoadedManifest, ManifestManager


class UserInterruption(Exception):
    """用户控制信号；保留取消、暂停或接管意图，不进入任务恢复。"""

    def __init__(
        self, message: str = "Run cancelled by user.", *,
        reason: Literal["cancel", "pause", "takeover", "focus"] = "cancel",
    ) -> None:
        super().__init__(message)
        self.reason = reason


class InputValidationError(ValueError):
    """调用参数不能满足已发布的 Python 类型契约。"""


class OutputValidationError(ValueError):
    """Component 返回值不能满足其声明的结果契约。"""


class TraceWriteError(RuntimeError):
    """Trace 持久化失败；继续执行会丢失必要证据。"""
    code = "trace_write_failed"


class WorkingManifestWriteError(TraceWriteError):
    """Working Manifest 持久化失败；禁止继续执行新 Component。"""
    code = "working_manifest_write_failed"


class ExecutionFailure(RuntimeError):
    """Executor 已分类的运行失败。"""

    def __init__(self, code: str, message: str | None = None, *, cause: Exception | None = None) -> None:
        if message is None:
            code, message = "execution_failed", code
        super().__init__(message)
        self.code = code
        if cause is not None:
            self.__cause__ = cause


class RecoveryTerminated(ExecutionFailure):
    """下层恢复已结束；穿过调用者时不得再当成外层自身调度失败。"""


class EnvironmentFailure(ExecutionFailure):
    """游戏环境无法继续；不得降为可继续的 Task 失败。"""


class GameProcessExited(EnvironmentFailure):
    """输入会话已确认原游戏进程退出，可由内置规则恢复当前 Step。"""

    def __init__(self) -> None:
        super().__init__("game_process_exited", "Limbus Company process exited.")


class InputReleaseFailure(EnvironmentFailure):
    """无法确认输入释放，必须终止整个 Run，不能再恢复控制。"""

    def __init__(self, message: str) -> None:
        super().__init__("input_release_failed", message)


def _mark_role(function: Callable[..., Any], role: str) -> Callable[..., Any]:
    function.__lalc_role__ = role
    return function


def automation_plan(function: Callable[..., Any]) -> Callable[..., Any]:
    """标记 Manifest 唯一的正式 Python 调度入口。"""
    return _mark_role(function, "automation_plan")


def task_workflow(function: Callable[..., Any]) -> Callable[..., Any]:
    return _mark_role(function, "task_workflow")


def sub_workflow(function: Callable[..., Any]) -> Callable[..., Any]:
    return _mark_role(function, "sub_workflow")


def step(function: Callable[..., Any]) -> Callable[..., Any]:
    return _mark_role(function, "step")


class RunGate:
    """在 Component 与 Trusted Action 边界实施协作式暂停和取消。"""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._paused = False
        self._stopped = False

    def checkpoint(self) -> None:
        with self._condition:
            self._condition.wait_for(lambda: not self._paused or self._stopped)
            if self._stopped:
                raise UserInterruption

    def pause(self) -> bool:
        with self._condition:
            if self._stopped or self._paused:
                return False
            self._paused = True
            return True

    def resume(self) -> bool:
        with self._condition:
            if self._stopped or not self._paused:
                return False
            self._paused = False
            self._condition.notify_all()
            return True

    def stop(self) -> bool:
        with self._condition:
            if self._stopped:
                return False
            self._stopped = True
            self._paused = False
            self._condition.notify_all()
            return True

    @property
    def paused(self) -> bool:
        with self._condition:
            return self._paused

    @property
    def stopped(self) -> bool:
        with self._condition:
            return self._stopped


@dataclass(frozen=True)
class _Frame:
    logical_name: str
    component_id: str
    role: str
    phase: str
    call_id: int


class WorkflowExecutor:
    """同步执行 Component；各入口处理自身失败，共享一次 Run 的状态。"""

    _ACTION_ACCESS = {
        ("task_workflow", "execute"): {"observe"},
        ("sub_workflow", "execute"): {"observe"},
        ("step", "execute"): {"observe", "control"},
        ("step", "condition"): {"observe"},
        ("recovery_rule", "detect"): {"observe"},
        ("recovery_rule", "recover"): {"observe", "control"},
    }

    def __init__(
        self,
        manifest: LoadedManifest,
        gate: RunGate,
        emit: Callable[[str, dict[str, Any]], None],
        *,
        capture_screen: Callable[[bool], dict[str, Any]] | None = None,
        control_input: Callable[[str, dict[str, Any]], None] | None = None,
        check_input: Callable[[], None] | None = None,
        game_process_exited: Callable[[], bool] | None = None,
        prepare_resume: Callable[[], None] | None = None,
        manifest_manager: ManifestManager | None = None,
        choose_manifest: Callable[[str, str, tuple[str, ...]], str | None] | None = None,
        select_manifest: Callable[[LoadedManifest], None] | None = None,
        game_language: str = "en",
        match_asset: Callable[..., list[dict[str, Any]]] | None = None,
        ocr: Callable[..., dict[str, Any]] | None = None,
        crop_asset: Callable[..., dict[str, Any]] | None = None,
        save_screenshot: Callable[[], dict[str, Any]] | None = None,
        debug_screenshot: Callable[[], dict[str, Any]] | None = None,
        task_finished: Callable[[dict[str, Any], dict[str, Any], float], None] | None = None,
        run_state: RunState | None = None,
        recovery_limit: int = 10,
        repair: Callable[[dict[str, Any]], str | None] | None = None,
    ) -> None:
        self.task_results: list[dict[str, Any]] = []
        self.task_finished = task_finished
        self.manifest = manifest
        self.gate = gate
        self.emit = emit
        self._save_screenshot = save_screenshot
        self._debug_screenshot = debug_screenshot
        self._capture_screen = capture_screen
        self._control_input = control_input
        self._check_input = check_input
        self._game_process_exited = game_process_exited
        self.run_state = run_state if run_state is not None else RunState()
        self.recovery_limit = recovery_limit
        self.repair = repair
        self._recovery_key: int | None = None
        self._prepare_resume = prepare_resume
        self._active_action: str | None = None
        self.context = RunContext(self)
        self._frames: list[_Frame] = []
        self._next_call_id = 1
        self._root_call_id: int | None = None
        self.manifest_manager = manifest_manager
        self.choose_manifest = choose_manifest
        self.select_manifest = select_manifest
        self.game_language = game_language
        self._match_asset = match_asset
        self._ocr = ocr
        self._crop_asset = crop_asset
        self.attempted_manifest_ids = [manifest.manifest_id]

    @staticmethod
    def prepare_inputs(component: LoadedComponent, arguments: dict[str, Any]) -> dict[str, Any]:
        """绑定默认值并按 execute 注解生成独立的 JSON 输入副本。"""

        return _bind_and_normalize(component.module.execute, arguments)

    def run(
        self, logical_name: str, component: LoadedComponent, inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """执行一个直接入口，并把所有终止归一为公开 Run Result。"""

        self._root_call_id = None
        try:
            output = self._invoke_entry(logical_name, component, inputs, None)
            return {
                "status": "success",
                "logical_name": logical_name,
                "component_id": component.component_id,
                "role": component.role,
                "output": _json_copy(output),
            }
        except UserInterruption as error:
            if error.reason != "cancel":
                raise
            return self._failure(logical_name, component, "user_cancelled", "Run cancelled by user.")
        except OutputValidationError as error:
            return {**self._failure(logical_name, component, "invalid_output", str(error)), **_exception_fields(error)}
        except ExecutionFailure as error:
            return {**self._failure(logical_name, component, error.code, str(error)), **_exception_fields(error)}
        except TraceWriteError:
            raise
        except Exception as error:
            return {**self._failure(logical_name, component, "execution_failed", str(error)), **_exception_fields(error)}

    @staticmethod
    def _failure(
        logical_name: str,
        component: LoadedComponent | None,
        code: str,
        message: str,
    ) -> dict[str, Any]:
        return {
            "status": "failure",
            "logical_name": logical_name,
            "component_id": component.component_id if component else None,
            "role": component.role if component else "task_workflow",
            "failure_code": code,
            "failure_message": message,
        }

    def call(self, logical_name: str, arguments: dict[str, Any]) -> Any:
        """从当前 Task/Subworkflow 帧调用一个合法的 Subworkflow 或 Step。"""

        if not self._frames or self._frames[-1].phase != "execute":
            raise ExecutionFailure("execution_failed", "ctx.call is unavailable outside execute().")
        caller = self._frames[-1]
        if caller.role == "automation_plan":
            return self._call_task(logical_name, arguments, caller.call_id)
        if caller.role not in {"task_workflow", "sub_workflow"}:
            raise ExecutionFailure("execution_failed", f"{caller.role} cannot call a Component.")
        component = self.manifest.components.get(logical_name)
        if component is None:
            raise ExecutionFailure("execution_failed", f"Unknown Component: {logical_name}")
        if component.role not in {"sub_workflow", "step"} or (
            caller.role == "sub_workflow" and component.role != "step"
        ):
            raise ExecutionFailure("execution_failed", f"Illegal Component target role: {component.role}")
        return self._invoke_entry(logical_name, component, arguments, caller.call_id)

    def _call_task(self, name: str, arguments: dict[str, Any], parent_call_id: int) -> dict[str, Any]:
        """Plan 的 Task 结果边界；环境故障和用户控制信号始终向外传播。"""
        from datetime import UTC, datetime
        self.gate.checkpoint()
        component = self.manifest.components.get(name)
        if component is not None and component.role != "task_workflow":
            component = None
        started = time.monotonic()
        event = {"logical_name": name, "component_id": component.component_id if component else None,
                 "manifest_id": self.manifest.manifest_id, "inputs": _json_copy(arguments),
                 "recorded_at": datetime.now(UTC).isoformat()}
        terminal = None
        next_call_id = self._next_call_id
        try:
            if component is None:
                raise ExecutionFailure("working_manifest_incompatible", f"Task unavailable: {name}")
            output = self._invoke_entry(name, component, arguments, parent_call_id)
            self.gate.checkpoint()
            result = {"status": "success", "output": _json_copy(output)}
        except (UserInterruption, TraceWriteError, EnvironmentFailure) as error:
            if isinstance(error, UserInterruption) and self._next_call_id == next_call_id:
                raise
            terminal = error
            code = "user_cancelled" if isinstance(error, UserInterruption) else error.code
            result = {**self._failure(name, component, code, str(error)), **_exception_fields(error)}
        except Exception as error:
            code = error.code if isinstance(error, ExecutionFailure) else (
                "working_manifest_incompatible" if isinstance(error, InputValidationError) else "execution_failed")
            result = {**self._failure(name, component, code, str(error)), **_exception_fields(error)}
        duration = _duration_ms(started)
        item = {"index": len(self.task_results), "task": name, "inputs": event["inputs"],
                "result": result["status"], "duration_ms": duration, **result}
        # items 的 status 属于 Task；Plan 的遍历状态在应用服务单独汇总。
        self.task_results.append(_json_copy(item))
        event["ended_at"] = datetime.now(UTC).isoformat()
        if self.task_finished is not None:
            self.task_finished(event, result, duration)
        if not isinstance(terminal, TraceWriteError):
            self.emit("plan_item_finished", {"index": item["index"], "task": name, "result": result})
        if terminal is not None:
            raise terminal
        return _json_copy(result)

    def _invoke_step(self, logical_name, component, arguments, parent_call_id):
        """保留手动恢复路径使用的 Step 入口。"""
        return self._invoke_entry(logical_name, component, arguments, parent_call_id)

    def _invoke_entry(self, logical_name, component, arguments, parent_call_id):
        """仅在所属调用边界修复；仍在等待的调用者帧不退出。"""
        call_id = self._next_call_id
        try:
            result = self._invoke_component(logical_name, component, arguments, parent_call_id=parent_call_id)
        except (RecoveryTerminated, TraceWriteError):
            raise
        except UserInterruption as error:
            if error.reason == "cancel" or component.role != "step":
                raise
            try:
                result = self._resume_step(logical_name, self.manifest.components[logical_name],
                                           arguments, parent_call_id, error)
            except GameProcessExited as exited:
                result = self._recover_call(logical_name, component, arguments, parent_call_id, exited, call_id)
        except GameProcessExited as error:
            result = self._recover_call(logical_name, component, arguments, parent_call_id, error, call_id)
        except EnvironmentFailure:
            raise
        except (ExecutionFailure, InputValidationError) as error:
            result = self._recover_call(logical_name, component, arguments, parent_call_id, error, call_id)
        if component.role == "step":
            self.run_state._recovery_count = 0
        return result

    def _recover_game(self, step_name: str, parent_call_id: int | None) -> None:
        """优先执行内置崩溃规则，额度由统一连续恢复计数控制。"""
        fields = {"logical_name": "builtin.game_crash", "role": "recovery_rule",
                  "parent_call_id": parent_call_id, "step": step_name}

        def recover():
            self.log("已确认游戏进程退出，执行内置崩溃恢复。", level="warning")
            self.trusted_action("control.restart_game", {})
            self.log("游戏已重启并重新绑定窗口，重新调用当前 Step。")

        try:
            detected = self._invoke(
                lambda: self._game_process_exited is not None and self._game_process_exited(),
                {**fields, "call_id": self._allocate_call_id()}, phase="detect", event="recovery_rule",
            )
            if not detected:
                raise EnvironmentFailure("game_restart_failed", "Game exit could not be confirmed.")
            self._invoke(recover, {**fields, "call_id": self._allocate_call_id()},
                         phase="recover", event="recovery_rule")
        except (UserInterruption, TraceWriteError, EnvironmentFailure):
            raise
        except Exception as error:
            raise EnvironmentFailure("game_restart_failed", str(error), cause=error) from error
        self.emit("step_reinvocation_started", {"logical_name": step_name, "reason": "game_restart"})

    def _wait_manual_resume(
        self, logical_name: str, component: LoadedComponent, inputs: dict[str, Any],
        parent_call_id: int | None, error: UserInterruption,
    ) -> None:
        """保持暂停，直至一次手动恢复完成观察和适用的 Step condition 检查。"""

        reason = str(error)
        diagnostic = _exception_fields(error)
        restart_step = component.role == "step"
        condition = getattr(component.module, "condition", None) if restart_step else None
        while True:
            self.gate.pause()
            self.emit("paused_by_user", {
                "logical_name": logical_name,
                "description": (
                    inspect.getdoc(component.module.execute) or inspect.getdoc(component.module) or logical_name
                ) if restart_step else "尚未进入下一 Step；恢复后重新观察并继续 Workflow 调度。",
                "has_condition": callable(condition), "restart_step": restart_step,
                "reason": reason, **diagnostic,
            })
            self.gate.checkpoint()
            try:
                if self._prepare_resume is None:
                    raise ExecutionFailure("execution_failed", "Input Resume is unavailable.")
                self._prepare_resume()
                if condition is not None:
                    self._run_condition(component, condition, {
                        "logical_name": logical_name, "component_id": component.component_id,
                        "role": "step", "call_id": self._allocate_call_id(),
                        "parent_call_id": parent_call_id, "inputs": _json_copy(inputs),
                    }, inputs)
            except UserInterruption as pause_error:
                if pause_error.reason == "cancel":
                    raise
                reason = str(pause_error)
                diagnostic = _exception_fields(pause_error)
                continue
            except (TraceWriteError, EnvironmentFailure):
                raise
            except Exception as check_error:
                reason = str(check_error)
                diagnostic = _exception_fields(check_error)
                self.emit("input_resume_rejected", {"logical_name": logical_name, **diagnostic})
                continue
            self.emit("input_resumed", {"logical_name": logical_name})
            return

    def _resume_step(
        self, logical_name: str, component: LoadedComponent, inputs: dict[str, Any],
        parent_call_id: int | None, error: UserInterruption,
    ) -> Any:
        """用户接管只走手动恢复；保留调用者帧，不进入自动恢复阶梯。"""

        while True:
            self.emit("step_interrupted", {"logical_name": logical_name,
                      "component_id": component.component_id, "outcome": "unknown", **_exception_fields(error)})
            automatic = error.reason == "focus"
            try:
                if automatic:
                    if self._check_input is not None:
                        self._check_input()
                else:
                    self._wait_manual_resume(logical_name, component, inputs, parent_call_id, error)
            except UserInterruption as next_error:
                if next_error.reason == "cancel":
                    raise
                error = next_error
                continue
            self.emit("step_reinvocation_started", {"logical_name": logical_name,
                      "component_id": component.component_id, "reason": "focus" if automatic else "manual_resume"})
            try:
                try:
                    result = self._invoke_component(logical_name, component, inputs,
                                                    parent_call_id=parent_call_id, skip_condition=not automatic)
                except UserInterruption:
                    raise
                except EnvironmentFailure:
                    raise
                except ExecutionFailure as interrupted:
                    self.emit("step_interrupted", {"logical_name": logical_name,
                              "component_id": component.component_id, **_exception_fields(interrupted)})
                    result = self._invoke_step_recovery(logical_name, component, inputs, parent_call_id, interrupted)
            except UserInterruption as next_error:
                if next_error.reason == "cancel":
                    raise
                error = next_error
                continue
            self.emit("step_reinvocation_returned", {"logical_name": logical_name,
                      "component_id": component.component_id, "reason": "focus" if automatic else "manual_resume"})
            return result

    def _invoke_step_recovery(self, logical_name, component, inputs, parent_call_id, error):
        """手动恢复后普通错误继续使用同一入口恢复流程。"""
        return self._recover_call(logical_name, component, inputs, parent_call_id, error)

    def _recover_call(self, logical_name, original, inputs, parent_call_id, error, call_id=None):
        """规则与 Agent 串行交接；失败尝试不回滚 RunState 或已选择版本。"""
        outermost = self._recovery_key is None
        if outermost:
            self._recovery_key = self._allocate_call_id()
        recheck = False
        must_agent = False
        interrupted_call_id = call_id
        try:
            self.emit("step_interrupted" if original.role == "step" else "workflow_interrupted",
                      {"logical_name": logical_name, "component_id": original.component_id,
                       "recovery_id": self._recovery_key, **_exception_fields(error)})
            while True:
                self.gate.checkpoint()
                execute = False
                if not must_agent and self.run_state.recovery_count < self.recovery_limit:
                    if isinstance(error, GameProcessExited):
                        self._recover_game(logical_name, parent_call_id)
                        recovered, problem = True, None
                    else:
                        recovered, problem = self._recover_rules()
                    if recovered:
                        self.run_state._recovery_count += 1
                        execute = True
                    elif problem is None and recheck:
                        execute = True
                    elif problem is not None:
                        error = problem
                if not execute:
                    if self.repair is None and self.choose_manifest is None:
                        self._end_recovery(logical_name, error)
                    if self.repair is None:
                        self.run_state._recovery_count = 0
                    context = {"recovery_id": self._recovery_key, "logical_name": logical_name,
                               "role": original.role, "parent_call_id": parent_call_id,
                               "interrupted_call_id": interrupted_call_id, "failed_call_id": call_id,
                               "inputs": _json_copy(inputs), "manifest_id": self.manifest.manifest_id,
                               "attempted_manifest_ids": list(self.attempted_manifest_ids),
                               **_exception_fields(error)}
                    try:
                        manifest_id = (self.repair(context) if self.repair is not None else
                                       self.choose_manifest(str(error), logical_name, tuple(self.attempted_manifest_ids)))
                    except (UserInterruption, TraceWriteError, EnvironmentFailure):
                        raise
                    except Exception as failure:
                        self.emit("recovery_choice_failed", {"logical_name": logical_name, **_exception_fields(failure)})
                        if isinstance(error, GameProcessExited):
                            raise EnvironmentFailure("game_recovery_exhausted", str(failure), cause=failure) from failure
                        raise RecoveryTerminated("execution_failed", str(failure), cause=failure) from failure
                    if manifest_id is None:
                        self._end_recovery(logical_name, error)
                    loaded = self.manifest_manager.load(manifest_id)
                    candidate = loaded.loaded
                    replacement = candidate.components.get(logical_name) if candidate else None
                    if not loaded.ok or replacement is None or replacement.role != original.role:
                        error = ExecutionFailure("manifest_selection_rejected", "; ".join(e.message for e in loaded.errors)
                                                 or "恢复入口必须保留原逻辑名及角色。")
                        self.emit("manifest_selection_rejected", {"manifest_id": manifest_id, "reason": str(error)})
                        must_agent = True
                        continue
                    self.select_manifest(candidate)
                    self.manifest = candidate
                    if manifest_id not in self.attempted_manifest_ids:
                        self.attempted_manifest_ids.append(manifest_id)
                    self.emit("working_manifest_selected", {"manifest_id": manifest_id,
                              "recovery_id": self._recovery_key})
                    recheck, must_agent = True, False
                    continue
                current = self.manifest.components[logical_name]
                fields = {"logical_name": logical_name, "component_id": current.component_id,
                          "recovery_id": self._recovery_key, "parent_call_id": parent_call_id,
                          "attempt_call_id": self._next_call_id}
                self.emit("step_reinvocation_started" if current.role == "step" else "workflow_reinvocation_started", fields)
                try:
                    call_id = self._next_call_id
                    result = self._invoke_component(logical_name, current, _json_copy(inputs), parent_call_id=parent_call_id)
                    self.emit("step_reinvocation_returned" if current.role == "step" else "workflow_reinvocation_returned", fields)
                    if current.role == "step":
                        self.run_state._recovery_count = 0
                    return result
                except (RecoveryTerminated, TraceWriteError):
                    raise
                except UserInterruption as interrupted:
                    if interrupted.reason == "cancel" or current.role != "step":
                        raise
                    try:
                        return self._resume_step(logical_name, current, inputs, parent_call_id, interrupted)
                    except GameProcessExited as exited:
                        error = exited
                except GameProcessExited as interrupted:
                    error = interrupted
                except EnvironmentFailure:
                    raise
                except (ExecutionFailure, InputValidationError) as interrupted:
                    error = interrupted
                self.emit("step_reinvocation_failed" if current.role == "step" else "workflow_reinvocation_failed",
                          {**fields, **_exception_fields(error)})
                self.emit("step_interrupted" if current.role == "step" else "workflow_interrupted",
                          {**fields, **_exception_fields(error)})
                recheck, must_agent = False, False
        finally:
            if outermost:
                self._recovery_key = None

    def _end_recovery(self, logical_name, error):
        """无 Agent 可接续时保留失败归属；重启耗尽终止整个 Run。"""
        if isinstance(error, GameProcessExited):
            raise EnvironmentFailure("game_recovery_exhausted", "重启恢复达到上限且 Agent 无法继续。", cause=error) from error
        self._terminate_anomaly(str(error), logical_name)
        code = getattr(error, "code", "working_manifest_incompatible" if isinstance(error, InputValidationError) else "execution_failed")
        raise RecoveryTerminated(code, str(error), cause=error) from error

    def _recover_rules(self):
        """完整检测一轮；零匹配不伪称已恢复，多匹配或规则错误交 Agent。"""
        matches = []
        for name, rule in sorted(self.manifest.recovery_rules.items()):
            try:
                matched = self._invoke_recovery_rule(name, rule, "detect")
                if type(matched) is not bool:
                    raise ExecutionFailure(f"Recovery Rule {name} detect did not return bool.")
            except (UserInterruption, TraceWriteError, EnvironmentFailure):
                raise
            except Exception as error:
                return False, error
            if matched:
                matches.append((name, rule))
        if len(matches) > 1:
            return False, ExecutionFailure("recovery_rule_ambiguous", "Multiple Recovery Rules matched: " +
                                           ", ".join(name for name, _ in matches))
        if not matches:
            return False, None
        name, rule = matches[0]
        try:
            result = self._invoke_recovery_rule(name, rule, "recover")
            if result is not None:
                raise ExecutionFailure(f"Recovery Rule {name} recover did not return None.")
            return True, None
        except (UserInterruption, TraceWriteError, EnvironmentFailure):
            raise
        except Exception as error:
            return False, error

    def _invoke_recovery_rule(self, name: str, rule: LoadedComponent, phase: str) -> Any:
        self.gate.checkpoint()
        call_id = self._allocate_call_id()
        fields = {"call_id": call_id, "logical_name": name, "component_id": rule.component_id, "manifest_id": self.manifest.manifest_id, "phase": phase}
        fields.update(role="recovery_rule", parent_call_id=self._frames[-1].call_id if self._frames else None)
        return self._invoke(
            lambda: getattr(rule.module, phase)(self.context), fields,
            phase=phase, event="recovery_rule",
        )

    def _terminate_anomaly(self, reason: str, logical_name: str) -> None:
        self.emit("execution_anomaly", {"logical_name": logical_name, "reason": reason})
        self.emit("safe_task_termination", {"logical_name": logical_name, "reason": reason})

    def trusted_action(self, logical_name: str, arguments: dict[str, Any]) -> Any:
        """校验调用角色并执行应用注册的 Trusted Action。"""

        if not self._frames:
            raise ExecutionFailure("execution_failed", "Trusted Action called without a Component frame.")
        if self._active_action is not None:
            raise ExecutionFailure("execution_failed", "Trusted Actions cannot call another Trusted Action.")
        caller = self._frames[-1]
        action = self.manifest_manager.actions.get(logical_name) if self.manifest_manager else None
        if action is None:
            raise ExecutionFailure("execution_failed", f"Unknown Trusted Action: {logical_name}")
        allowed = self._ACTION_ACCESS.get((caller.role, caller.phase), set())
        if action.classification not in allowed:
            raise ExecutionFailure(
                "execution_failed",
                f"{caller.role}.{caller.phase} cannot call {action.classification} Trusted Action "
                f"{logical_name!r}; caller={caller.logical_name!r}, component_id={caller.component_id}.",
            )

        self.gate.checkpoint()
        if self._check_input is not None and logical_name != "control.restart_game":
            try:
                self._check_input()
            except UserInterruption as error:
                if error.reason == "cancel":
                    raise
                if caller.role == "recovery_rule" or any(frame.role == "step" for frame in self._frames):
                    raise
                # 没有活动 Step 时保留当前观察调用，不重启已经返回的 Step。
                component = self.manifest.components[caller.logical_name]
                self._wait_manual_resume(caller.logical_name, component, {}, caller.call_id, error)
        inputs = _bind_and_normalize(action.execute, arguments)
        call_id = self._allocate_call_id()
        fields = {
            "call_id": call_id,
            "parent_call_id": caller.call_id,
            "manifest_id": self.manifest.manifest_id,
            "logical_name": logical_name,
            "role": "trusted_action",
            "classification": action.classification,
            "inputs": _json_copy(inputs),
        }
        def invoke() -> Any:
            self._active_action = action.classification
            try:
                result = action.execute(self.context, **deepcopy(inputs))
                return _normalize_output(result, get_type_hints(
                    action.execute, globalns=action.execute.__globals__
                )["return"])
            finally:
                self._active_action = None

        while True:
            self.gate.checkpoint()
            try:
                if logical_name in {"control.click", "control.drag", "observe.ocr", "observe.match_asset"}:
                    fields = {**fields, "debug_image": self._debug_screenshot() if self._debug_screenshot
                              else {"image_unavailable": True}}
                return self._invoke(invoke, fields, phase="execute", event="trusted_action")
            except UserInterruption as error:
                if (error.reason == "cancel" or caller.role == "recovery_rule"
                        or any(frame.role == "step" for frame in self._frames)):
                    raise
                # 只重做无副作用的观察；在这里等待可保留 Workflow 调用栈。
                component = self.manifest.components[caller.logical_name]
                self._wait_manual_resume(caller.logical_name, component, {}, caller.call_id, error)
                fields = {**fields, "call_id": self._allocate_call_id()}


    def log(self, message: str, *, level: str = "info", screenshot: bool = False) -> None:
        """校验并统一日志级别，将语义和可选截图引用写入当前调用的 Trace。"""
        if type(message) is not str or type(screenshot) is not bool:
            raise ValueError("log requires a string message and a bool screenshot")
        if type(level) is not str or level.lower() not in {"debug", "info", "warning", "error"}:
            raise ValueError("log level must be debug, info, warning or error (case-insensitive)")
        if not self._frames or self._active_action is not None:
            raise ExecutionFailure("execution_failed", "ctx.log requires a Component invocation")
        self.gate.checkpoint()
        frame = self._frames[-1]
        fields = {"logical_name": frame.logical_name, "component_id": frame.component_id,
                  "call_id": frame.call_id, "role": frame.role, "phase": frame.phase,
                  "manifest_id": self.manifest.manifest_id, "message": message, "level": level.lower()}
        if screenshot:
            if self._save_screenshot is None:
                raise ExecutionFailure("execution_failed", "No current screenshot to attach")
            fields.update(self._save_screenshot())
        self.emit("component_log", fields)

    def capture_screen(self, save: bool) -> dict[str, Any]:
        """将原始像素留在会话中，仅返回可写入 Trace 的信息。"""

        if self._active_action != "observe" or self._capture_screen is None:
            raise ExecutionFailure("execution_failed", "Screenshot capture requires an observe Trusted Action.")
        return self._capture_screen(save)

    def match_asset(self, logical_name: str, options: dict[str, Any]) -> list[dict[str, Any]]:
        if self._active_action != "observe" or self._match_asset is None:
            raise ExecutionFailure("execution_failed", "Asset matching requires an observe Trusted Action.")
        return self._match_asset(logical_name, **options)

    def ocr(self, *, region: dict[str, int] | None = None, min_score: float = 0.0) -> dict[str, Any]:
        """保持 OCR 的 observe 权限边界，原始失败交由现有执行路径处理。"""
        if self._active_action != "observe" or self._ocr is None:
            raise ExecutionFailure("execution_failed", "OCR requires an observe Trusted Action.")
        return self._ocr(region=region, min_score=min_score)

    def crop_asset(self, logical_name: str, region: dict[str, int], tags: list[str] | None = None) -> dict[str, Any]:
        if self._active_action != "observe" or self._crop_asset is None:
            raise ExecutionFailure("execution_failed", "Asset cropping requires an observe Trusted Action.")
        return self._crop_asset(logical_name, region, tags)

    def control_input(self, operation: str, arguments: dict[str, Any]) -> None:
        """原生输入仅允许 control Action；observe Action 只可复用无输入的等待。"""

        allowed = self._active_action == "control" or (self._active_action == "observe" and operation == "wait")
        if not allowed or self._control_input is None:
            raise ExecutionFailure("execution_failed", "Input requires a control Trusted Action.")
        self._control_input(operation, arguments)

    def _invoke_component(
        self,
        logical_name: str,
        component: LoadedComponent,
        arguments: dict[str, Any],
        *,
        parent_call_id: int | None,
        skip_condition: bool = False,
    ) -> Any:
        self.gate.checkpoint()
        inputs = self.prepare_inputs(component, arguments)
        call_id = self._allocate_call_id()
        if self._root_call_id is None:
            self._root_call_id = call_id
        identity = {
            "call_id": call_id,
            "parent_call_id": parent_call_id,
            "manifest_id": self.manifest.manifest_id,
            "logical_name": logical_name,
            "component_id": component.component_id,
            "role": component.role,
            "inputs": _json_copy(inputs),
        }
        condition = getattr(component.module, "condition", None) if component.role == "step" else None
        if condition is not None and not skip_condition:
            self._run_condition(component, condition, identity, inputs)

        def invoke() -> Any:
            result = component.module.execute(self.context, **_json_copy(inputs))
            if component.role == "step" and self._check_input is not None:
                self._check_input()
            if component.role == "automation_plan":
                self.gate.checkpoint()
                if get_type_hints(component.module.execute)["return"] is Any:
                    try:
                        return _strict_json(result)
                    except (TypeError, ValueError) as error:
                        raise OutputValidationError(str(error)) from error
            return _normalize_output(result, get_type_hints(
                component.module.execute, globalns=component.module.execute.__globals__
            )["return"])

        return self._invoke(invoke, identity, phase="execute", event="component")

    def _run_condition(
        self, component: LoadedComponent, condition: Callable[..., Any],
        identity: dict[str, Any], inputs: dict[str, Any],
    ) -> None:
        """Step 前置检查使用同一调用入口；失败由整个 Step 的恢复边界接住。"""

        value = self._invoke(
            lambda: condition(self.context, **_json_copy(inputs)),
            identity, phase="condition", event="condition", returned="condition_evaluated",
        )
        if value is not True:
            raise ExecutionFailure(f"Condition not satisfied: {identity['logical_name']}")

    def _invoke(
        self, invoke: Callable[[], Any], fields: dict[str, Any], *,
        phase: str, event: str, returned: str | None = None,
    ) -> Any:
        """统一记录调用、耗时和完整异常；保留已归一错误，只有原始错误需包装。"""

        fields = {"manifest_id": self.manifest.manifest_id, "inputs": {}, **fields, "phase": phase}
        if event == "trusted_action":
            fields = {**fields, "level": "debug"}
        self.emit(f"{event}_started", fields)
        started = time.monotonic()
        self._frames.append(_Frame(
            fields["logical_name"], fields.get("component_id", ""), fields["role"], phase, fields["call_id"],
        ))
        try:
            result = invoke()
            self.emit(returned or f"{event}_returned", {
                **fields, "return_value": _trace_value(result), "duration_ms": _duration_ms(started),
            })
            return result
        except UserInterruption as error:
            self.emit(f"{event}_interrupted", {
                **fields, "reason": error.reason, "message": str(error),
                "duration_ms": _duration_ms(started),
            })
            raise
        except TraceWriteError:
            raise
        except Exception as error:
            from .focused import WindowError
            if isinstance(error, WindowError):
                error = EnvironmentFailure("environment_unavailable", str(error), cause=error)
            self.emit(f"{event}_failed", {
                **fields, **_exception_fields(error), "duration_ms": _duration_ms(started),
            })
            if isinstance(error, ExecutionFailure):
                raise error
            code = "invalid_output" if isinstance(error, OutputValidationError) else "execution_failed"
            raise ExecutionFailure(code, str(error), cause=error) from error
        finally:
            self._frames.pop()

    def _allocate_call_id(self) -> int:
        call_id = self._next_call_id
        self._next_call_id += 1
        return call_id


def _bind_and_normalize(function: Callable[..., Any], arguments: dict[str, Any]) -> dict[str, Any]:
    if type(arguments) is not dict or any(type(name) is not str for name in arguments):
        raise InputValidationError("inputs must be a dictionary with string keys")
    try:
        bound = inspect.signature(function).bind(object(), **arguments)
    except TypeError as error:
        raise InputValidationError(str(error)) from error
    bound.apply_defaults()
    hints = get_type_hints(function, globalns=function.__globals__)
    return {
        name: _normalize_value(value, hints[name], name)
        for name, value in list(bound.arguments.items())[1:]
    }


def _normalize_value(value: Any, annotation: Any, path: str) -> Any:
    """按已校验注解执行严格、递归且无别名的 JSON 规范化。"""

    if annotation is str and type(value) is str:
        return value
    if annotation is bool and type(value) is bool:
        return value
    if annotation is int and type(value) is int:
        return value
    if annotation is float and type(value) in {int, float}:
        normalized = float(value)
        if math.isfinite(normalized):
            return normalized
    if annotation in {None, type(None)} and value is None:
        return None

    origin = get_origin(annotation)
    arguments = get_args(annotation)
    if origin is Literal:
        for choice in arguments:
            if type(value) is type(choice) and value == choice:
                return value
    elif origin in {types.UnionType, Union}:
        for option in arguments:
            try:
                return _normalize_value(value, option, path)
            except InputValidationError:
                pass
    elif origin is list and type(value) is list:
        return [_normalize_value(item, arguments[0], f"{path}[{index}]") for index, item in enumerate(value)]
    elif origin is tuple and type(value) is tuple and len(value) == len(arguments):
        return tuple(_normalize_value(item, item_type, f"{path}[{index}]")
                     for index, (item, item_type) in enumerate(zip(value, arguments)))
    elif origin is dict and type(value) is dict and all(type(key) is str for key in value):
        return {
            key: _normalize_value(item, arguments[1], f"{path}.{key}")
            for key, item in value.items()
        }
    raise InputValidationError(f"{path} does not match {annotation!r}")


def _normalize_output(value: Any, annotation: Any) -> Any:
    try:
        return _normalize_value(value, annotation, "return")
    except InputValidationError as error:
        raise OutputValidationError(str(error)) from error


def _strict_json(value: Any) -> Any:
    """复制 Plan 混合配置，拒绝非 JSON 类型、循环引用及非有限数值。"""
    json.dumps(value, allow_nan=False)
    def copy(item):
        if item is None or type(item) in {str, bool, int}:
            return item
        if type(item) is float and math.isfinite(item):
            return item
        if type(item) is list:
            return [copy(v) for v in item]
        if type(item) is dict and all(type(k) is str for k in item):
            return {k: copy(v) for k, v in item.items()}
        raise ValueError("settings must contain only JSON values and string object keys")
    return copy(value)


def _json_copy(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as error:
        raise OutputValidationError("value is not JSON-compatible") from error


def _trace_value(value: Any) -> Any:
    return _json_copy(value)


def _duration_ms(started: float) -> float:
    return round((time.monotonic() - started) * 1000, 3)


def _exception_fields(error: BaseException) -> dict[str, Any]:
    return {
        "failure_message": str(error),
        "traceback": "".join(traceback.TracebackException.from_exception(error).format(chain=True)),
    }


def sha256_bytes(source: bytes) -> str:
    return hashlib.sha256(source).hexdigest()


def require_json(value: Any, name: str) -> None:
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name}_not_json_compatible") from error


@contextmanager
def staging_directory(parent: Path, *, prefix: str):
    """创建继承父目录权限的提交工作区，退出时清理尚未移出的内容。"""
    from .work_files import WorkDirectory

    with WorkDirectory(dir=parent, prefix=prefix) as directory:
        yield Path(directory)


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
