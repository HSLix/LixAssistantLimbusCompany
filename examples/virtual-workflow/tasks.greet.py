"""虚拟问候任务：检查输入、组织流程并验证最终结果。"""

from lalc import task_workflow


@task_workflow
def execute(ctx, *, name: str) -> str:
    """通过一个 Subworkflow 完成问候。"""
    return ctx.call("subworkflows.greet", name=name)
