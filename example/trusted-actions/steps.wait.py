"""协作等待，期间继续响应接管和停止。"""
from lalc import step


@step
def execute(ctx, *, seconds: float = 0.0) -> None:
    """等待不用于断言游戏已完成转换，业务判断仍须重新观察。"""
    ctx.action("control.wait", seconds=seconds)
