"""在本次 Run 的前台输入会话执行 click，接管时中断并释放。"""


def execute(ctx, *, x: int, y: int) -> None:
    ctx.control_input("click", x=x, y=y)
