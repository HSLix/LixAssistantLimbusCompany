from __future__ import annotations

import hashlib
import inspect
import json
import math
import threading
import time
import traceback
import types
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Literal, Union, get_args, get_origin, get_type_hints

from .run_context import RunContext as RunContext

if TYPE_CHECKING:
    from .manifest import LoadedComponent, LoadedManifest, ManifestManager


class UserInterruption(Exception):
    """用户控制信号；保留取消、暂停或接管意图，不进入任务恢复。"""

    def __init__(
        self, message: str = "Run cancelled by user.", *,
        reason: Literal["cancel", "pause", "takeover"] = "cancel",
    ) -> None:
        super().__init__(message)
        self.reason = reason


class InputValidationError(ValueError):
    """调用参数不能满足已发布的 Python 类型契约。"""


class OutputValidationError(ValueError):
    """Component 返回值不能满足其声明的结果契约。"""


class TraceWriteError(RuntimeError):
    """Trace 持久化失败；继续执行会丢失必要证据。"""


class WorkingManifestWriteError(TraceWriteError):
    """Working Manifest 持久化失败；禁止继续执行新 Component。"""


class ExecutionFailure(RuntimeError):
    """Executor 已分类的运行失败。"""

    def __init__(self, code: str, message: str | None = None, *, cause: Exception | None = None) -> None:
        if message is None:
            code, message = "execution_failed", code
        super().__init__(message)
        self.code = code
        if cause is not None:
            self.__cause__ = cause


class InputReleaseFailure(ExecutionFailure):
    """无法确认输入释放，必须终止整个 Run，不能再恢复控制。"""

    def __init__(self, message: str) -> None:
        super().__init__("input_release_failed", message)


def _mark_role(function: Callable[..., Any], role: str) -> Callable[..., Any]:
    function.__lalc_role__ = role
    return function


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
    """在当前线程同步执行正式 Component，并在 Step 边界处理恢复。"""

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
        prepare_resume: Callable[[], None] | None = None,
        manifest_manager: ManifestManager | None = None,
        choose_manifest: Callable[[str, str, tuple[str, ...]], str | None] | None = None,
        select_manifest: Callable[[LoadedManifest], None] | None = None,
        game_language: str = "en",
        match_asset: Callable[..., list[dict[str, Any]]] | None = None,
        crop_asset: Callable[..., dict[str, Any]] | None = None,
    ) -> None:
        self.manifest = manifest
        self.gate = gate
        self.emit = emit
        self._capture_screen = capture_screen
        self._control_input = control_input
        self._check_input = check_input
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
            if component.role == "step":
                output = self._invoke_step(logical_name, component, inputs, None)
            else:
                output = self._invoke_component(logical_name, component, inputs, parent_call_id=None)
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
        component: LoadedComponent,
        code: str,
        message: str,
    ) -> dict[str, Any]:
        return {
            "status": "failure",
            "logical_name": logical_name,
            "component_id": component.component_id,
            "role": component.role,
            "failure_code": code,
            "failure_message": message,
        }

    def call(self, logical_name: str, arguments: dict[str, Any]) -> Any:
        """从当前 Task/Subworkflow 帧调用一个合法的 Subworkflow 或 Step。"""

        if not self._frames or self._frames[-1].phase != "execute":
            raise ExecutionFailure("execution_failed", "ctx.call is unavailable outside execute().")
        caller = self._frames[-1]
        if caller.role not in {"task_workflow", "sub_workflow"}:
            raise ExecutionFailure("execution_failed", f"{caller.role} cannot call a Component.")
        component = self.manifest.components.get(logical_name)
        if component is None:
            raise ExecutionFailure("execution_failed", f"Unknown Component: {logical_name}")
        if component.role not in {"sub_workflow", "step"} or (
            caller.role == "sub_workflow" and component.role != "step"
        ):
            raise ExecutionFailure("execution_failed", f"Illegal Component target role: {component.role}")
        if component.role == "step":
            return self._invoke_step(logical_name, component, arguments, caller.call_id)
        return self._invoke_component(logical_name, component, arguments, parent_call_id=caller.call_id)

    def _invoke_step(
        self, logical_name: str, component: LoadedComponent, arguments: dict[str, Any],
        parent_call_id: int | None,
    ) -> Any:
        """只在当前 Step 调用边界恢复，保留仍在栈上的 Workflow 调用帧。"""

        inputs = _bind_and_normalize(component.module.execute, arguments)
        try:
            try:
                return self._invoke_component(logical_name, component, inputs, parent_call_id=parent_call_id)
            except UserInterruption:
                raise
            except InputReleaseFailure:
                raise
            except ExecutionFailure as error:
                self.emit("step_interrupted", {"logical_name": logical_name,
                          "component_id": component.component_id, **_exception_fields(error)})
                return self._invoke_step_recovery(logical_name, component, inputs, parent_call_id)
        except UserInterruption as error:
            if error.reason == "cancel":
                raise
            current = self.manifest.components[logical_name]
            return self._resume_step(logical_name, current, inputs, parent_call_id, error)

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
                "description": (inspect.getdoc(component.module) or logical_name) if restart_step else
                    "尚未进入下一 Step；恢复后重新观察并继续 Workflow 调度。",
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
            except (UserInterruption, TraceWriteError, InputReleaseFailure):
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
            self._wait_manual_resume(logical_name, component, inputs, parent_call_id, error)
            self.emit("step_reinvocation_started", {"logical_name": logical_name,
                      "component_id": component.component_id, "reason": "manual_resume"})
            try:
                try:
                    result = self._invoke_component(logical_name, component, inputs,
                                                    parent_call_id=parent_call_id, skip_condition=True)
                except UserInterruption:
                    raise
                except InputReleaseFailure:
                    raise
                except ExecutionFailure as interrupted:
                    self.emit("step_interrupted", {"logical_name": logical_name,
                              "component_id": component.component_id, **_exception_fields(interrupted)})
                    result = self._invoke_step_recovery(logical_name, component, inputs, parent_call_id)
            except UserInterruption as next_error:
                if next_error.reason == "cancel":
                    raise
                error = next_error
                continue
            self.emit("step_reinvocation_returned", {"logical_name": logical_name,
                      "component_id": component.component_id, "reason": "manual_resume"})
            return result

    def _invoke_step_recovery(self, logical_name: str, component: LoadedComponent,
                              inputs: dict[str, Any], parent_call_id: int | None) -> Any:
        """新调用发生普通中断时复用既有恢复阶梯。"""

        recovered, outcome = self._recover_step(logical_name, component, inputs, parent_call_id)
        if recovered:
            return outcome
        recovered, outcome = self._try_manifest_choices(logical_name, component, inputs, parent_call_id, outcome)
        if recovered:
            return outcome
        self._terminate_anomaly(str(outcome), logical_name)
        if isinstance(outcome, ExecutionFailure):
            raise outcome
        raise ExecutionFailure(str(outcome))

    def _try_manifest_choices(
        self, logical_name: str, original: LoadedComponent, inputs: dict[str, Any],
        parent_call_id: int | None, reason: str | ExecutionFailure,
    ) -> tuple[bool, Any]:
        """在原调用链仍暂停时，尝试完整 Manifest 选择或结束本次任务。"""

        if self.choose_manifest is None or self.manifest_manager is None or self.select_manifest is None:
            return False, reason
        while True:
            self.gate.checkpoint()
            try:
                manifest_id = self.choose_manifest(str(reason), logical_name, tuple(self.attempted_manifest_ids))
            except (UserInterruption, TraceWriteError, InputReleaseFailure):
                raise
            except Exception as error:
                self.emit("recovery_choice_failed", {"logical_name": logical_name, **_exception_fields(error)})
                return False, ExecutionFailure(str(error), cause=error)
            self.gate.checkpoint()
            if manifest_id is None:
                return False, reason
            loaded = self.manifest_manager.load(manifest_id)
            if not loaded.ok:
                reason = ExecutionFailure(
                    "execution_failed", "; ".join(error.message for error in loaded.errors),
                    cause=next((error.cause for error in loaded.errors if error.cause is not None), None),
                )
                self.emit("manifest_selection_rejected", {"manifest_id": manifest_id, "reason": str(reason),
                          "errors": [error.as_dict() for error in loaded.errors]})
                continue
            candidate = loaded.loaded
            assert candidate is not None
            replacement = candidate.components.get(logical_name)
            reason = self._replacement_problem(original, replacement, candidate)
            if reason:
                self.emit("manifest_selection_rejected", {"manifest_id": manifest_id, "reason": reason})
                continue
            assert replacement is not None
            condition = getattr(replacement.module, "condition", None)
            if condition is not None:
                try:
                    previous = self.manifest
                    self.manifest = candidate
                    try:
                        self._run_condition(
                            replacement, condition,
                            {"logical_name": logical_name, "component_id": replacement.component_id,
                             "role": "step", "manifest_id": manifest_id,
                             "call_id": self._allocate_call_id(), "inputs": _json_copy(inputs)},
                            inputs,
                        )
                    finally:
                        self.manifest = previous
                except Exception as error:
                    if isinstance(error, (UserInterruption, TraceWriteError, InputReleaseFailure)):
                        raise
                    reason = error
                    self.emit("manifest_selection_rejected", {"manifest_id": manifest_id, "reason": str(reason), **_exception_fields(error)})
                    continue
            self.gate.checkpoint()
            self.select_manifest(candidate)
            self.manifest = candidate
            if manifest_id not in self.attempted_manifest_ids:
                self.attempted_manifest_ids.append(manifest_id)
            self.emit("working_manifest_selected", {"manifest_id": manifest_id})
            self.emit("step_reinvocation_started", {"logical_name": logical_name, "component_id": replacement.component_id})
            try:
                result = self._invoke_component(logical_name, replacement, _json_copy(inputs), parent_call_id=parent_call_id, skip_condition=True)
                original_return = get_type_hints(original.module.execute, globalns=original.module.execute.__globals__)["return"]
                _normalize_output(result, original_return)
                self.emit("step_reinvocation_returned", {"logical_name": logical_name, "component_id": replacement.component_id})
                return True, result
            except Exception as error:
                if isinstance(error, (UserInterruption, TraceWriteError, InputReleaseFailure)):
                    raise
                reason = error
                self.emit("step_reinvocation_failed", {"logical_name": logical_name, "component_id": replacement.component_id, **_exception_fields(error)})

    def _replacement_problem(
        self, original: LoadedComponent, replacement: LoadedComponent | None,
        candidate: LoadedManifest,
    ) -> str:
        """拒绝无法接回原 Step 调用链的整份 Manifest。"""

        if replacement is None or replacement.role != "step":
            return "Current logical name must still identify a Step."
        for section in ("recovery_rules",):
            if candidate.manifest[section] != self.manifest.manifest[section]:
                return f"Runtime replacement cannot modify {section}."
        old = inspect.signature(original.module.execute)
        new = inspect.signature(replacement.module.execute)
        old_hints = get_type_hints(original.module.execute, globalns=original.module.execute.__globals__)
        new_hints = get_type_hints(replacement.module.execute, globalns=replacement.module.execute.__globals__)
        if old_hints["return"] != new_hints["return"]:
            return "Current Step return contract changed."
        for name, parameter in list(old.parameters.items())[1:]:
            updated = new.parameters.get(name)
            if updated is None or updated.kind != parameter.kind or updated.default != parameter.default or new_hints[name] != old_hints[name]:
                return f"Current Step parameter changed: {name}."
        for name, parameter in list(new.parameters.items())[1:]:
            if name not in old.parameters and (parameter.kind is not inspect.Parameter.KEYWORD_ONLY or parameter.default is inspect.Parameter.empty):
                return f"New Step parameter must be optional keyword-only: {name}."
        return ""

    def _recover_step(
        self, logical_name: str, component: LoadedComponent, inputs: dict[str, Any],
        parent_call_id: int | None,
    ) -> tuple[bool, Any]:
        """检查公共规则并最多重新调用当前 Step 一次。"""

        matches: list[tuple[str, LoadedComponent]] = []
        for name, rule in sorted(self.manifest.recovery_rules.items()):
            try:
                matched = self._invoke_recovery_rule(name, rule, "detect")
            except Exception as error:
                if isinstance(error, (UserInterruption, TraceWriteError, InputReleaseFailure)):
                    raise
                return False, error
            if type(matched) is not bool:
                return False, f"Recovery Rule {name} detect did not return bool."
            if matched:
                matches.append((name, rule))
        if len(matches) > 1:
            return False, "Multiple Recovery Rules matched."
        if matches:
            name, rule = matches[0]
            try:
                recovered = self._invoke_recovery_rule(name, rule, "recover")
            except Exception as error:
                if isinstance(error, (UserInterruption, TraceWriteError, InputReleaseFailure)):
                    raise
                return False, error
            if recovered is not None:
                return False, f"Recovery Rule {name} recover did not return None."
        current = self.manifest.components[logical_name]
        self.emit("step_reinvocation_started", {"logical_name": logical_name, "component_id": current.component_id})
        try:
            result = self._invoke_component(logical_name, current, _json_copy(inputs), parent_call_id=parent_call_id)
            original_return = get_type_hints(component.module.execute, globalns=component.module.execute.__globals__)["return"]
            _normalize_output(result, original_return)
            self.emit("step_reinvocation_returned", {"logical_name": logical_name, "component_id": current.component_id})
            return True, result
        except Exception as error:
            if isinstance(error, (UserInterruption, TraceWriteError, InputReleaseFailure)):
                raise
            self.emit("step_reinvocation_failed", {"logical_name": logical_name, "component_id": current.component_id, **_exception_fields(error)})
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
        if self._check_input is not None:
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
                result = action.execute(self.context, **_json_copy(inputs))
                return _normalize_output(result, get_type_hints(
                    action.execute, globalns=action.execute.__globals__
                )["return"])
            finally:
                self._active_action = None

        while True:
            self.gate.checkpoint()
            try:
                return self._invoke(invoke, fields, phase="execute", event="trusted_action")
            except UserInterruption as error:
                if (error.reason == "cancel" or caller.role == "recovery_rule"
                        or any(frame.role == "step" for frame in self._frames)):
                    raise
                # 只重做无副作用的观察；在这里等待可保留 Workflow 调用栈。
                component = self.manifest.components[caller.logical_name]
                self._wait_manual_resume(caller.logical_name, component, {}, caller.call_id, error)
                fields = {**fields, "call_id": self._allocate_call_id()}


    def capture_screen(self, save: bool) -> dict[str, Any]:
        """将原始像素留在会话中，仅返回可写入 Trace 的信息。"""

        if self._active_action != "observe" or self._capture_screen is None:
            raise ExecutionFailure("execution_failed", "Screenshot capture requires an observe Trusted Action.")
        return self._capture_screen(save)

    def match_asset(self, logical_name: str, options: dict[str, Any]) -> list[dict[str, Any]]:
        if self._active_action != "observe" or self._match_asset is None:
            raise ExecutionFailure("execution_failed", "Asset matching requires an observe Trusted Action.")
        return self._match_asset(logical_name, **options)

    def crop_asset(self, logical_name: str, region: dict[str, int], tags: list[str] | None = None) -> dict[str, Any]:
        if self._active_action != "observe" or self._crop_asset is None:
            raise ExecutionFailure("execution_failed", "Asset cropping requires an observe Trusted Action.")
        return self._crop_asset(logical_name, region, tags)

    def control_input(self, operation: str, arguments: dict[str, Any]) -> None:
        """运行角色校验之外，再约束原生输入只能由 control Trusted Action 发起。"""

        if self._active_action != "control" or self._control_input is None:
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
        inputs = _bind_and_normalize(component.module.execute, arguments)
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
            self.emit(f"{event}_failed", {
                **fields, **_exception_fields(error), "duration_ms": _duration_ms(started),
            })
            if isinstance(error, ExecutionFailure):
                raise
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


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
