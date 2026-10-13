"""从本次运行的前台会话取得新的客户区截图。"""


def execute(ctx, *, save: bool = False) -> dict[str, int | str]:
    """刷新内存截图；明确要求时保存这张图。"""

    return ctx.capture_screen(save=save)
