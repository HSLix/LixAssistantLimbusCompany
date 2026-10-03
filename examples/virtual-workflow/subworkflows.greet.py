"""虚拟问候 Subworkflow：把一个完整动作交给 Step。"""

from lalc import sub_workflow


@sub_workflow
def execute(ctx, *, name: str) -> str:
    """调用问候 Step 并返回其结果。"""
    return ctx.call("steps.say_hello", name=name)
