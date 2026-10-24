"""显式截图后检测一个语义 Asset 的全部达标目标。"""

from lalc import step


@step
def execute(ctx, *, asset: str, priority_tags: list[str] | None = None, region: dict[str, int] | None = None,
            threshold: float = 0.9, nms: bool = True,
            nms_iou_threshold: float = 0.5) -> list[dict[str, str | int | float | list[str] | tuple[int, int] | dict[str, float]]]:
    """匹配默认不保存截图；返回完整客户区坐标。"""

    ctx.action("observe.capture_screen")
    return ctx.action("observe.match_asset", asset=asset, priority_tags=priority_tags, region=region,
                      threshold=threshold, nms=nms, nms_iou_threshold=nms_iou_threshold)
