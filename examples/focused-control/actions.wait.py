"""在本次 Run 的前台输入会话执行 wait，接管时中断并释放。"""


def execute(ctx, *, seconds: float) -> None:
    ctx.control_input("wait", seconds=seconds)
