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

if TYPE_CHECKING:
    from .manifest import LoadedComponent, LoadedManifest, ManifestManager


class RunCancelled(Exception):
    """用户取消信号；它不属于 Component 可处理的业务异常。"""


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

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ExecutionInterruption(RuntimeError):
    """Step 或 Workflow 报告当前执行无法安全继续。"""


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
                raise RunCancelled

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


class RunContext:
    """向正式 Component 暴露统一的 Component 与 Trusted Action 调用边界。"""

    __slots__ = ("_executor",)

    def __init__(self, executor: WorkflowExecutor) -> None:
        self._executor = executor

    def call(self, logical_name: str, **arguments: Any) -> Any:
        return self._executor.call(logical_name, arguments)

    def action(self, logical_name: str, **arguments: Any) -> Any:
        return self._executor.trusted_action(logical_name, arguments)

    def capture_screen(self, *, save: bool = False) -> dict[str, Any]:
        """只供正在执行的 observe Trusted Action 刷新本次 Run 的截图。"""

        return self._executor.capture_screen(save)


class WorkflowExecutor:
    """在当前线程同步执行正式 Component，并在 Step 边界处理恢复。"""

    _ACTION_ACCESS = {
        ("task_workflow", "execute"): {"observe"},
        ("task_workflow", "condition"): {"observe"},
        ("task_workflow", "verify"): set(),
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
        manifest_manager: ManifestManager | None = None,
        choose_manifest: Callable[[str, str, tuple[str, ...]], str | None] | None = None,
        select_manifest: Callable[[LoadedManifest], None] | None = None,
    ) -> None:
        self.manifest = manifest
        self.gate = gate
        self.emit = emit
        self._capture_screen = capture_screen
        self._active_action: str | None = None
        self.context = RunContext(self)
        self._frames: list[_Frame] = []
        self._next_call_id = 1
        self._root_call_id: int | None = None
        self.manifest_manager = manifest_manager
        self.choose_manifest = choose_manifest
        self.select_manifest = select_manifest
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
            if component.role == "task_workflow":
                self.gate.checkpoint()
                self._verify_task(logical_name, component, output, inputs)
            return {
                "status": "success",
                "logical_name": logical_name,
                "component_id": component.component_id,
                "role": component.role,
                "output": _json_copy(output),
            }
        except RunCancelled:
            return self._failure(logical_name, component, "user_cancelled", "Run cancelled by user.")
        except OutputValidationError as error:
            return self._failure(logical_name, component, "invalid_output", str(error))
        except ExecutionFailure as error:
            return self._failure(logical_name, component, error.code, str(error))
        except TraceWriteError:
            raise
        except ExecutionInterruption as error:
            self._terminate_anomaly(str(error), logical_name)
            return self._failure(logical_name, component, "execution_anomaly", str(error))
        except Exception as error:
            return self._failure(logical_name, component, "execution_failed", str(error))

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
            return self._invoke_component(logical_name, component, inputs, parent_call_id=parent_call_id)
        except ExecutionInterruption as error:
            self.emit("step_interrupted", {"logical_name": logical_name, "component_id": component.component_id, **_exception_fields(error)})
            recovered, outcome = self._recover_step(logical_name, component, inputs, parent_call_id)
            if recovered:
                return outcome
            recovered, outcome = self._try_manifest_choices(logical_name, component, inputs, parent_call_id, str(outcome))
            if recovered:
                return outcome
            reason = str(outcome)
            self._terminate_anomaly(reason, logical_name)
            raise ExecutionFailure("execution_anomaly", reason) from error

    def _try_manifest_choices(
        self, logical_name: str, original: LoadedComponent, inputs: dict[str, Any],
        parent_call_id: int | None, reason: str,
    ) -> tuple[bool, Any]:
        """在原调用链仍暂停时，尝试完整 Manifest 选择或结束本次任务。"""

        if self.choose_manifest is None or self.manifest_manager is None or self.select_manifest is None:
            return False, reason
        while True:
            self.gate.checkpoint()
            try:
                manifest_id = self.choose_manifest(reason, logical_name, tuple(self.attempted_manifest_ids))
            except (RunCancelled, TraceWriteError):
                raise
            except Exception as error:
                return False, f"Recovery choice failed: {error}"
            self.gate.checkpoint()
            if manifest_id is None:
                return False, reason
            loaded = self.manifest_manager.load(manifest_id)
            if not loaded.ok:
                reason = "; ".join(error.message for error in loaded.errors)
                self.emit("manifest_selection_rejected", {"manifest_id": manifest_id, "reason": reason})
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
                    self._run_condition(
                        replacement, condition,
                        {"logical_name": logical_name, "component_id": replacement.component_id,
                         "role": "step", "manifest_id": manifest_id,
                         "call_id": self._allocate_call_id(), "inputs": _json_copy(inputs)},
                        inputs,
                    )
                except Exception as error:
                    if isinstance(error, (RunCancelled, TraceWriteError)):
                        raise
                    reason = f"Replacement Step cannot enter current state: {error}"
                    self.emit("manifest_selection_rejected", {"manifest_id": manifest_id, "reason": reason})
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
                if isinstance(error, (RunCancelled, TraceWriteError)):
                    raise
                reason = f"Selected Step failed: {error}"
                self.emit("step_reinvocation_failed", {"logical_name": logical_name, "component_id": replacement.component_id, **_exception_fields(error)})

    def _replacement_problem(
        self, original: LoadedComponent, replacement: LoadedComponent | None,
        candidate: LoadedManifest,
    ) -> str:
        """拒绝无法接回原 Step 调用链的整份 Manifest。"""

        if replacement is None or replacement.role != "step":
            return "Current logical name must still identify a Step."
        for section in ("trusted_actions", "recovery_rules", "assets"):
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
                if isinstance(error, (RunCancelled, TraceWriteError)):
                    raise
                return False, f"Recovery Rule {name} detect failed: {error}"
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
                if isinstance(error, (RunCancelled, TraceWriteError)):
                    raise
                return False, f"Recovery Rule {name} recover failed: {error}"
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
            if isinstance(error, (RunCancelled, TraceWriteError)):
                raise
            self.emit("step_reinvocation_failed", {"logical_name": logical_name, "component_id": current.component_id, **_exception_fields(error)})
            return False, f"Current Step failed again: {error}"

    def _invoke_recovery_rule(self, name: str, rule: LoadedComponent, phase: str) -> Any:
        self.gate.checkpoint()
        call_id = self._allocate_call_id()
        fields = {"call_id": call_id, "logical_name": name, "component_id": rule.component_id, "manifest_id": self.manifest.manifest_id, "phase": phase}
        self.emit("recovery_rule_started", fields)
        self._frames.append(_Frame(name, rule.component_id, "recovery_rule", phase, call_id))
        try:
            result = getattr(rule.module, phase)(self.context)
            self.emit("recovery_rule_returned", {**fields, "return_value": _trace_value(result)})
            return result
        except (RunCancelled, TraceWriteError):
            raise
        except Exception as error:
            self.emit("recovery_rule_failed", {**fields, **_exception_fields(error)})
            raise
        finally:
            self._frames.pop()

    def _terminate_anomaly(self, reason: str, logical_name: str) -> None:
        self.emit("execution_anomaly", {"logical_name": logical_name, "reason": reason})
        self.emit("safe_task_termination", {"logical_name": logical_name, "reason": reason})

    def trusted_action(self, logical_name: str, arguments: dict[str, Any]) -> Any:
        """校验调用角色并执行 Manifest 固定的 Trusted Action。"""

        if not self._frames:
            raise ExecutionFailure("execution_failed", "Trusted Action called without a Component frame.")
        if self._active_action is not None:
            raise ExecutionFailure("execution_failed", "Trusted Actions cannot call another Trusted Action.")
        caller = self._frames[-1]
        action = self.manifest.trusted_actions.get(logical_name)
        if action is None:
            raise ExecutionFailure("execution_failed", f"Unknown Trusted Action: {logical_name}")
        allowed = self._ACTION_ACCESS.get((caller.role, caller.phase), set())
        if action.classification not in allowed:
            raise ExecutionFailure(
                "execution_failed",
                f"{caller.role}.{caller.phase} cannot call {action.classification} Trusted Action.",
            )

        self.gate.checkpoint()
        inputs = _bind_and_normalize(action.module.execute, arguments)
        call_id = self._allocate_call_id()
        fields = {
            "call_id": call_id,
            "parent_call_id": caller.call_id,
            "manifest_id": self.manifest.manifest_id,
            "logical_name": logical_name,
            "component_id": action.component_id,
            "role": action.role,
            "classification": action.classification,
            "inputs": _json_copy(inputs),
        }
        self.emit("trusted_action_started", fields)
        started = time.monotonic()
        try:
            self._active_action = action.classification
            try:
                result = action.module.execute(self.context, **_json_copy(inputs))
            finally:
                self._active_action = None
            normalized = _normalize_output(
                result,
                get_type_hints(action.module.execute, globalns=action.module.execute.__globals__)["return"],
            )
            self.emit(
                "trusted_action_returned",
                {
                    **fields,
                    "return_value": _trace_value(normalized),
                    "duration_ms": _duration_ms(started),
                },
            )
            return normalized
        except (RunCancelled, TraceWriteError):
            raise
        except Exception as error:
            self.emit(
                "trusted_action_failed",
                {**fields, **_exception_fields(error), "duration_ms": _duration_ms(started)},
            )
            raise

    def capture_screen(self, save: bool) -> dict[str, Any]:
        """将原始像素留在会话中，仅返回可写入 Trace 的信息。"""

        if self._active_action != "observe" or self._capture_screen is None:
            raise ExecutionFailure("execution_failed", "Screenshot capture requires an observe Trusted Action.")
        return self._capture_screen(save)

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
        condition = getattr(component.module, "condition", None)
        if condition is not None and not skip_condition:
            self._run_condition(component, condition, identity, inputs)

        self.emit("component_started", identity)
        started = time.monotonic()
        self._frames.append(_Frame(logical_name, component.component_id, component.role, "execute", call_id))
        try:
            result = component.module.execute(self.context, **_json_copy(inputs))
            annotation = get_type_hints(
                component.module.execute, globalns=component.module.execute.__globals__
            )["return"]
            normalized = _normalize_output(result, annotation)
            self.emit(
                "component_returned",
                {
                    **identity,
                    "return_value": _trace_value(normalized),
                    "duration_ms": _duration_ms(started),
                },
            )
            return normalized
        except (RunCancelled, TraceWriteError):
            raise
        except Exception as error:
            self.emit(
                "component_failed",
                {**identity, **_exception_fields(error), "duration_ms": _duration_ms(started)},
            )
            raise
        finally:
            self._frames.pop()

    def _run_condition(
        self,
        component: LoadedComponent,
        condition: Callable[..., Any],
        identity: dict[str, Any],
        inputs: dict[str, Any],
    ) -> None:
        started = time.monotonic()
        self._frames.append(
            _Frame(
                identity["logical_name"],
                component.component_id,
                component.role,
                "condition",
                identity["call_id"],
            )
        )
        try:
            value = condition(self.context, **_json_copy(inputs))
            self.emit(
                "condition_evaluated",
                {**identity, "return_value": _trace_value(value), "duration_ms": _duration_ms(started)},
            )
            if value is not True:
                if component.role == "step":
                    raise ExecutionInterruption(f"Condition not satisfied: {identity['logical_name']}")
                code = "task_condition_not_satisfied" if component.role == "task_workflow" else "execution_failed"
                raise ExecutionFailure(code, f"Condition not satisfied: {identity['logical_name']}")
        except (ExecutionFailure, ExecutionInterruption, RunCancelled, TraceWriteError):
            raise
        except Exception as error:
            self.emit(
                "condition_failed",
                {**identity, **_exception_fields(error), "duration_ms": _duration_ms(started)},
            )
            code = "task_condition_check_failed" if component.role == "task_workflow" else "execution_failed"
            if component.role == "step":
                raise ExecutionInterruption(str(error)) from error
            raise ExecutionFailure(code, str(error)) from error
        finally:
            self._frames.pop()

    def _verify_task(
        self,
        logical_name: str,
        component: LoadedComponent,
        result: Any,
        inputs: dict[str, Any],
    ) -> None:
        verify = component.module.verify
        call_id = self._allocate_call_id()
        fields = {
            "call_id": call_id,
            "parent_call_id": self._root_call_id,
            "logical_name": logical_name,
            "component_id": component.component_id,
            "role": component.role,
            "inputs": _json_copy(inputs),
            "root_result": _trace_value(result),
        }
        self.emit("verification_started", fields)
        started = time.monotonic()
        self._frames.append(_Frame(logical_name, component.component_id, component.role, "verify", call_id))
        try:
            verified = verify(self.context, _json_copy(result), **_json_copy(inputs))
            self.emit(
                "verification_returned",
                {**fields, "return_value": _trace_value(verified), "duration_ms": _duration_ms(started)},
            )
            if verified is not True:
                raise ExecutionFailure("verification_rejected", "Task verifier did not return true.")
        except (ExecutionFailure, RunCancelled, TraceWriteError):
            raise
        except Exception as error:
            self.emit(
                "verification_failed",
                {**fields, **_exception_fields(error), "duration_ms": _duration_ms(started)},
            )
            raise ExecutionFailure("verification_failed", str(error)) from error
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


def _exception_fields(error: Exception) -> dict[str, Any]:
    return {
        "exception_type": type(error).__name__,
        "exception_message": str(error),
        "traceback": traceback.format_exc(),
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
