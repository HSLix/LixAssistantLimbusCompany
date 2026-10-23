"""Subworkflow 组合 Step，不调用另一个 Subworkflow。"""
from lalc import sub_workflow


@sub_workflow
def execute(ctx, *, save: bool = True) -> dict[str, int | str]:
    """通过 Step 获取当前客户区的观察信息。"""
    return ctx.call("steps.capture", save=save)
