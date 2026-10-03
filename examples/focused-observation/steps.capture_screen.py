"""供监督式 Windows 验收使用的一次真实观察。"""

from lalc import step


@step
def execute(ctx, *, save: bool = False) -> dict[str, int | str]:
    """经正式 Trusted Action 边界刷新截图并返回可记录的信息。"""

    return ctx.action("observe.capture_screen", save=save)
