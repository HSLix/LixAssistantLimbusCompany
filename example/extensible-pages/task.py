"""返回消息的最小 Task，用真实执行结果验证页面参数。"""
from lalc import task_workflow


@task_workflow
def execute(ctx, *, message: str) -> str:
    return message
