"""显式截图后匹配当前逻辑名目录，无需登记白名单或发布素材。"""
from lalc import RunContext, step


@step
def execute(ctx: RunContext, *, asset: str, priority_tags: list[str] | None = None, region: dict[str, int] | None = None,
            threshold: float = 0.9, nms: bool = True,
            nms_iou_threshold: float = 0.5) -> list[dict[str, str | int | float | list[str] | tuple[int, int] | dict[str, float]]]:
    """返回完整客户区坐标，空匹配不等于业务完成。"""
    ctx.action("observe.capture_screen", save=True)
    return ctx.action("observe.match_asset", asset=asset, priority_tags=priority_tags, region=region,
                      threshold=threshold, nms=nms, nms_iou_threshold=nms_iou_threshold)
