"""虚拟问候任务：检查输入、组织流程并验证最终结果。"""

from lalc import task_workflow


@task_workflow
def execute(ctx, *, name: str) -> str:
    """通过一个 Subworkflow 完成问候。"""
    return ctx.call("subworkflows.greet", name=name)


def condition(ctx, *, name: str) -> bool:
    """只在观察到有效名字时进入任务。"""
    return ctx.action("actions.name_ready", name=name)


def verify(ctx, result: str, *, name: str) -> bool:
    """核对最终结果与最初输入。"""
    return result == f"Hello, {name}！"
