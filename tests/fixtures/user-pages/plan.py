"""使用页面配置与 Dashboard 次数调度消息任务；不操作游戏。"""
from typing import Any
from lalc import automation_plan

SUPPORTED_TASK_IDS = ["sample.loop"]


@automation_plan
def execute(ctx) -> None:
    for _ in range(ctx.run_state.task_repetitions.get("sample.loop", 0)):
        ctx.call("tasks.message", message=ctx.run_state.settings["sample.general"]["prefix"] + ctx.run_state.settings["sample.message"]["message"])
    return None
