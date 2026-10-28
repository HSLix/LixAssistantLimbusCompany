"""独立拖动样例；开发者先确认起终点处于安全区域。"""
from lalc import RunContext, step


@step
def execute(ctx: RunContext, *, x: int, y: int, end_x: int, end_y: int, seconds: float = 2.5) -> None:
    """长动作支持接管释放；人工恢复会重新进入 Step，须先检查游戏。"""
    ctx.action("observe.capture_screen")
    ctx.action("control.drag", x=x, y=y, end_x=end_x, end_y=end_y, seconds=seconds)
    ctx.action("observe.capture_screen", save=True)
