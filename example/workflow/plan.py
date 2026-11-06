"""按 exp、mirror 页面配置与 Dashboard 次数调用对应教学 Task。"""
from typing import Any
from lalc import RunContext, automation_plan

SUPPORTED_TASK_IDS = ["exp", "mirror"]


@automation_plan
def execute(ctx: RunContext, *, task_repetitions: dict[str, int], settings: dict[str, Any]) -> None:
    """只读取本次配置快照；未启用任务不会访问其页面配置。"""
    for index in range(task_repetitions.get("exp", 0)):
        result = ctx.call("tasks.exp", message=settings["exp"]["message"])
        ctx.log(f"tasks.exp 第 {index + 1}/{task_repetitions['exp']} 次 status={result['status']}")
        if result["status"] == "failure":
            ctx.log(f"failure_code={result['failure_code']} failure_message={result['failure_message']}")
        else:
            ctx.log(f"output={result['output']}")
    for index in range(task_repetitions.get("mirror", 0)):
        result = ctx.call("tasks.mirror", message=settings["mirror"]["message"])
        ctx.log(f"tasks.mirror 第 {index + 1}/{task_repetitions['mirror']} 次 status={result['status']}")
        if result["status"] == "failure":
            ctx.log(f"failure_code={result['failure_code']} failure_message={result['failure_message']}")
        else:
            ctx.log(f"output={result['output']}")
