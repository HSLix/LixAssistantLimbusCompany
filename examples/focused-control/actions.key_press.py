"""在本次 Run 的前台输入会话执行 key_press，接管时中断并释放。"""


def execute(ctx, *, key: str) -> None:
    ctx.control_input("key_press", key=key)
