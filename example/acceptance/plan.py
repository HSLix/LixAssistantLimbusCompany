"""Windows 成品验收 Plan；通过页面消息显式选择失败演示，不属于游戏业务。"""
from typing import Any
from lalc import RunContext, automation_plan

SUPPORTED_TASK_IDS = ["exp", "mirror"]


@automation_plan
def execute(ctx: RunContext, *, task_repetitions: dict[str, int], settings: dict[str, Any]) -> None:
    """task-fail 在第二次调用制造普通失败；plan-fail 在第二次调用前中断 Plan。"""
    for identity in ["exp", "mirror"]:
        message = settings.get(identity, {}).get("message", "Hello")
        for index in range(task_repetitions.get(identity, 0)):
            if message == "plan-fail" and index == 1:
                raise ValueError("acceptance: intentional Plan failure")
            ctx.call("tasks.acceptance", message=message, fail=message == "task-fail" and index == 1)
