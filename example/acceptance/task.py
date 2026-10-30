"""验收 Task：可主动失败，正常时通过 Step 协作等待，不发送游戏按键。"""
from lalc import ExecutionFailure, RunContext, task_workflow


@task_workflow
def execute(ctx: RunContext, *, message: str, fail: bool = False) -> dict[str, str]:
    """普通失败留在 Task 边界，避免把失败演示变成 Step 恢复流程。"""
    if fail:
        raise ExecutionFailure("acceptance: intentional Task failure")
    ctx.call("steps.acceptance_wait")
    return {"message": message}
