"""持久保存 Workflow 调用结果，并从已完成记录计算健康统计。"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from .runtime import TraceWriteError, atomic_write_json


class LedgerWriteError(TraceWriteError):
    """Workflow Run Ledger 无法持久化，执行必须停止。"""


_COUNTS = (
    "recovery_rule_attempts", "public_recoveries", "step_reinvocations",
    "successful_step_reinvocations", "agent_invocations", "working_manifest_trials",
    "agent_assisted_recoveries",
)


class WorkflowRunLedger:
    """按 Run 保存紧凑记录；Task 与活跃 Subworkflow 共享事实事件。"""

    def __init__(self, root: Path, run_id: int) -> None:
        self.path = root / "ledger" / f"{run_id}.json"
        self.run_id = run_id
        self.records: list[dict[str, Any]] = []
        self.event_totals = {name: 0 for name in _COUNTS}
        self.active: list[dict[str, Any]] = []
        self.item_index: int | None = None

    def _save(self) -> None:
        try:
            atomic_write_json(self.path, {"run_id": self.run_id, "records": self.records,
                                          "event_totals": self.event_totals})
        except (OSError, TypeError, ValueError) as error:
            raise LedgerWriteError(str(error)) from error

    def _new(self, event: dict[str, Any], kind: str) -> dict[str, Any]:
        call_id = event.get("call_id")
        record = {
            "record_id": f"{self.run_id}:call:{call_id}" if call_id is not None else f"{self.run_id}:item:{self.item_index if self.item_index is not None else 'direct'}",
            "run_id": self.run_id,
            "item_index": self.item_index if kind == "task" else None,
            "call_id": call_id,
            "parent_call_id": event.get("parent_call_id"),
            "logical_name": event["logical_name"],
            "component_id": event["component_id"],
            "manifest_id": event["manifest_id"],
            "workflow_kind": kind,
            "inputs": deepcopy(event.get("inputs", {})),
            "started_at": event.get("started_at", event["recorded_at"]),
            "ended_at": None,
            "duration_ms": None,
            "result": "incomplete",
            "failure_code": None,
            "failure_message": None,
            "safe_termination_performed": False,
            **{name: 0 for name in _COUNTS},
        }
        self.records.append(record)
        self.active.append(record)
        self._save()
        return record

    def observe(self, event: dict[str, Any]) -> None:
        """只把真实执行事件计入其所属 Task 和当前 Subworkflow。"""

        name = event["event"]
        role = event.get("role")
        if name == "component_started" and role in {"task_workflow", "sub_workflow"}:
            if role == "task_workflow" and any(
                record["workflow_kind"] == "task" and record["call_id"] == event["call_id"]
                for record in self.active
            ):
                return
            self._new(event, "task" if role == "task_workflow" else "sub")
            return
        if name in {"condition_evaluated", "condition_failed"} and role == "task_workflow":
            if not any(record["workflow_kind"] == "task" for record in self.active):
                self._new(event, "task")
            return
        if name in {"component_returned", "component_failed"} and role == "sub_workflow":
            record = next((item for item in reversed(self.active) if item["call_id"] == event["call_id"]), None)
            if record is not None:
                record["result"] = "success" if name == "component_returned" else "failure"
                record["ended_at"] = event["recorded_at"]
                record["duration_ms"] = event["duration_ms"]
                if name == "component_failed":
                    record["failure_message"] = event.get("exception_message", "Subworkflow failed.")
                self.active.remove(record)
                self._save()
            return
        changes = {
            ("recovery_rule_started", "recover"): "recovery_rule_attempts",
            ("recovery_rule_returned", "recover"): "public_recoveries",
            ("step_reinvocation_started", None): "step_reinvocations",
            ("step_reinvocation_returned", None): "successful_step_reinvocations",
            ("agent_invoked", None): "agent_invocations",
            ("working_manifest_selected", None): "working_manifest_trials",
            ("agent_assisted_recovery", None): "agent_assisted_recoveries",
        }
        counter = changes.get((name, event.get("phase")))
        if counter == "public_recoveries" and event.get("return_value") is not None:
            counter = None
        if counter:
            self.event_totals[counter] += 1
            for record in self.active:
                record[counter] += 1
            self._save()
        if name == "safe_task_termination":
            task = next((item for item in self.active if item["workflow_kind"] == "task"), None)
            if task is not None:
                task["safe_termination_performed"] = True
                self._save()

    def finish_task(
        self, event: dict[str, Any], result: dict[str, Any], duration_ms: float,
    ) -> None:
        """Task 验证之后才确定最终结果；未进入 execute 的失败也可入账。"""

        task = next((item for item in self.active if item["workflow_kind"] == "task"), None)
        if task is None:
            if result.get("failure_code") == "user_cancelled":
                return
            task = self._new(event, "task")
        for record in list(self.active):
            record["ended_at"] = event.get("ended_at", event["recorded_at"])
            if record is task:
                record["duration_ms"] = duration_ms
                record["result"] = result["status"]
                if result["status"] == "failure":
                    record["failure_code"] = result["failure_code"]
                    record["failure_message"] = result["failure_message"]
            else:
                record["result"] = "failure"
                if record["duration_ms"] is None:
                    record["duration_ms"] = round(
                        (datetime.fromisoformat(record["ended_at"]) - datetime.fromisoformat(record["started_at"])).total_seconds() * 1000, 3
                    )
                record["failure_code"] = result.get("failure_code", "execution_failed")
                record["failure_message"] = result.get("failure_message", "Task ended before return.")
            self.active.remove(record)
        # 已异常退出的 Subworkflow 与所属 Task 使用同一终止原因。
        if result["status"] == "failure":
            for record in self.records:
                if record["workflow_kind"] == "sub" and record["result"] == "failure" and record["failure_code"] is None:
                    record["failure_code"] = result["failure_code"]
                    record["failure_message"] = result["failure_message"]
        self._save()

    def finish_direct_subworkflow(
        self, result: dict[str, Any], ended_at: str, duration_ms: float,
    ) -> None:
        """直接启动的 Subworkflow 失败也保留执行器归类的原因。"""

        if self.active:
            record = self.active.pop()
            record.update(ended_at=ended_at, duration_ms=duration_ms,
                          result=result["status"])
        else:
            record = next((item for item in self.records if item["workflow_kind"] == "sub"), None)
        if record is not None and result["status"] == "failure":
            record["failure_code"] = result["failure_code"]
            record["failure_message"] = result["failure_message"]
        if record is not None:
            self._save()


def workflow_health(root: Path) -> dict[str, dict[str, Any]]:
    """从最终 Ledger 记录重算每个不可变 Workflow Component 的统计。"""

    groups: dict[str, list[dict[str, Any]]] = {}
    for path in sorted((root / "ledger").glob("*.json")):
        for record in json.loads(path.read_text(encoding="utf-8"))["records"]:
            if record["result"] != "incomplete":
                groups.setdefault(record["component_id"], []).append(record)
    result = {}
    for component_id, records in groups.items():
        total = len(records)
        strict = [r for r in records if r["result"] == "success" and not r["agent_invocations"]]
        assisted = [r for r in records if r["result"] == "success" and r["agent_invocations"]]
        result[component_id] = {
            "logical_name": records[0]["logical_name"],
            "workflow_kind": records[0]["workflow_kind"],
            "invocations": total,
            "successes": len(strict) + len(assisted),
            "failures": total - len(strict) - len(assisted),
            "strict_success_rate": len(strict) / total,
            "agent_assisted_completion_rate": len(assisted) / total,
            "average_duration_ms": sum(r["duration_ms"] or 0 for r in records) / total,
            "strict_average_duration_ms": sum(r["duration_ms"] or 0 for r in strict) / len(strict) if strict else None,
            "agent_assisted_average_duration_ms": sum(r["duration_ms"] or 0 for r in assisted) / len(assisted) if assisted else None,
            **{name: sum(r[name] for r in records) for name in _COUNTS},
            **{f"average_{name}": sum(r[name] for r in records) / total for name in _COUNTS},
        }
    return result


def application_event_totals(root: Path) -> dict[str, int]:
    """逐 Run 累加唯一事件，避免把 Task/Subworkflow 的重叠记录相加。"""

    totals = {name: 0 for name in _COUNTS}
    for path in (root / "ledger").glob("*.json"):
        saved = json.loads(path.read_text(encoding="utf-8"))
        for name in _COUNTS:
            totals[name] += saved.get("event_totals", {}).get(name, 0)
    return totals
