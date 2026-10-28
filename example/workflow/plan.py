"""按 exp、mirror 页面配置与 Dashboard 次数调用对应教学 Task。"""
from typing import Any
from lalc import RunContext, automation_plan

SUPPORTED_TASK_IDS = ["exp", "mirror"]


@automation_plan
def execute(ctx: RunContext, *, task_repetitions: dict[str, int], settings: dict[str, Any]) -> None:
    """只读取本次配置快照；未启用任务不会访问其页面配置。"""
    for _ in range(task_repetitions.get("exp", 0)):
        ctx.call("tasks.exp", message=settings["exp"]["message"])
    for _ in range(task_repetitions.get("mirror", 0)):
        ctx.call("tasks.mirror", message=settings["mirror"]["message"])
