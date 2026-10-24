"""独立按键样例；确认游戏状态允许对应按键后再运行。"""
from lalc import RunContext, step


@step
def execute(ctx: RunContext, *, key: str) -> None:
    """支持 esc、p、enter；本样例不判断业务效果。"""
    ctx.action("observe.capture_screen")
    ctx.action("control.key_press", key=key)
    ctx.action("observe.capture_screen", save=True)
