"""使用页面配置与 Dashboard 次数调度消息任务；不操作游戏。"""
from typing import Any
from lalc import automation_plan

SUPPORTED_TASK_IDS = ["sample.loop"]


@automation_plan
def execute(ctx, *, task_repetitions: dict[str, int], settings: dict[str, Any]) -> None:
    for _ in range(task_repetitions.get("sample.loop", 0)):
        ctx.call("tasks.message", message=settings["sample.general"]["prefix"] + settings["sample.message"]["message"])
    return None
