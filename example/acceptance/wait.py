"""协作等待为暂停、接管和 Stop 提供观察时间，不判断游戏业务结果。"""
from lalc import RunContext, step


@step
def execute(ctx: RunContext) -> None:
    """通过既有 Trusted Action 等待五秒，保留运行取消与输入清理语义。"""
    ctx.action("control.wait", seconds=5.0)
