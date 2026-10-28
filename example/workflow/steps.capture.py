"""显式刷新内存截图，可选保存同次观察的证据。"""
from lalc import RunContext, step


@step
def execute(ctx: RunContext, *, save: bool = True) -> dict[str, int | str]:
    """图片不穿越结果边界，只返回观察和证据元数据。"""
    return ctx.action("observe.capture_screen", save=save)
