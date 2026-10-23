"""显式截图后匹配；先用 add-asset 登记并发布模板才可运行。"""
from lalc import step


@step
def execute(ctx, *, asset: str, region: dict[str, int] | None = None,
            threshold: float = 0.9, nms: bool = True,
            nms_iou_threshold: float = 0.5) -> list[dict[str, str | int | float | dict[str, float]]]:
    """返回完整客户区坐标，空匹配不等于业务完成。"""
    ctx.action("observe.capture_screen", save=True)
    return ctx.action("observe.match_asset", asset=asset, region=region,
                      threshold=threshold, nms=nms, nms_iou_threshold=nms_iou_threshold)
