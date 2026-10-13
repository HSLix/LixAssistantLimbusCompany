"""在本次 Run 的前台输入会话执行 drag，接管时中断并释放。"""


def execute(ctx, *, x: int, y: int, end_x: int, end_y: int, seconds: float = 2.5) -> None:
    ctx.control_input("drag", x=x, y=y, end_x=end_x, end_y=end_y, seconds=seconds)
