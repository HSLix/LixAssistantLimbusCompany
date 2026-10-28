"""独立点击样例；开发者先确认安全区域及实际客户区坐标。"""
from lalc import RunContext, step


@step
def execute(ctx: RunContext, *, x: int, y: int) -> None:
    """点击前后刷新截图；真实任务还须判断动作效果和已完成状态。"""
    ctx.action("observe.capture_screen")
    ctx.action("control.click", x=x, y=y)
    ctx.action("observe.capture_screen", save=True)
