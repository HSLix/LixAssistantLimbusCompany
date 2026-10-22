"""虚拟问候 Step：检查条件后执行模拟控制动作。"""

from lalc import ExecutionFailure, step


@step
def execute(ctx, *, name: str) -> str:
    """通过 Trusted Action 返回模拟动作结果。"""
    result = ctx.action("actions.simulated_greeting", name=name)
    if result != f"Hello, {name}！":
        raise ExecutionFailure("问候结果与预期不符。")
    return result


def condition(ctx, *, name: str) -> bool:
    """独立启动 Step 时也拒绝空白名字。"""
    return ctx.action("actions.name_ready", name=name)
