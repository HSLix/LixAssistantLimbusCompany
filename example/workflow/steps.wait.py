"""协作等待，期间继续响应接管和停止。"""
from lalc import RunContext, step


@step
def execute(ctx: RunContext, *, seconds: float = 0.0) -> None:
    """等待不用于断言游戏已完成转换，业务判断仍须重新观察。"""
    ctx.action("control.wait", seconds=seconds)
