from __future__ import annotations

import hashlib
import json
import threading
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


class TaskCancelled(Exception):
    pass


class ExecutionAnomaly(Exception):
    pass


def step(function):
    function.__lalc_role__ = "step"
    return function


class RunGate:
    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._paused = False
        self._stopped = False

    def wait(self) -> None:
        with self._condition:
            self._condition.wait_for(lambda: not self._paused or self._stopped)
            if self._stopped:
                raise TaskCancelled

    def pause(self) -> None:
        with self._condition:
            self._paused = True

    def resume(self) -> None:
        with self._condition:
            self._paused = False
            self._condition.notify_all()

    def stop(self) -> None:
        with self._condition:
            self._stopped = True
            self._condition.notify_all()

    @property
    def paused(self) -> bool:
        with self._condition:
            return self._paused

    @property
    def stopped(self) -> bool:
        with self._condition:
            return self._stopped


@dataclass
class ExampleRunContext:
    scenario: dict[str, Any]
    action_events: list[dict[str, Any]] = field(default_factory=list)
    before_action: Callable[[], None] | None = None
    event_sink: Callable[[dict[str, Any]], None] | None = None

    def observe(self, name: str) -> Any:
        if self.before_action:
            self.before_action()
        value = self.scenario.get(name)
        self._record({"action": "observe", "name": name, "result": value})
        return value

    def control(self, name: str, value: Any = None) -> None:
        if self.before_action:
            self.before_action()
        self._record({"action": "control", "name": name, "value": value})

    def _record(self, event: dict[str, Any]) -> None:
        self.action_events.append(event)
        if self.event_sink:
            self.event_sink(event)


def sha256_bytes(source: bytes) -> str:
    return hashlib.sha256(source).hexdigest()


def load_verified_module(path: Path, source: bytes, expected_sha256: str) -> types.ModuleType:
    actual = sha256_bytes(source)
    if actual != expected_sha256:
        raise ValueError("candidate_sha256_mismatch")
    module = types.ModuleType(f"lalc_candidate_{actual[:12]}")
    module.__file__ = str(path)
    exec(compile(source, str(path), "exec"), module.__dict__)
    return module


def require_json(value: Any, name: str) -> None:
    try:
        json.dumps(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name}_not_json_compatible") from error


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
