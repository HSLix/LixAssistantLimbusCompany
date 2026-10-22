"""手动输入验收：请先将游戏恢复到允许本次点击、按键或拖动的页面。

接管后本 Step 从头执行，请在恢复前自行处理已产生的部分效果。
"""

from lalc import step


@step
def execute(ctx, *, operation: str = "key_press", key: str = "esc", x: int = 100,
            y: int = 100, end_x: int = 300, end_y: int = 100, seconds: float = 2.5) -> None:
    ctx.action("observe.capture_screen")
    if operation == "key_press":
        ctx.action("control.key_press", key=key)
    elif operation == "click":
        ctx.action("control.click", x=x, y=y)
    elif operation == "drag":
        ctx.action("control.drag", x=x, y=y, end_x=end_x, end_y=end_y, seconds=seconds)
    elif operation == "wait":
        ctx.action("control.wait", seconds=seconds)
    else:
        raise ValueError("Unknown acceptance operation")
    ctx.action("observe.capture_screen", save=True)
