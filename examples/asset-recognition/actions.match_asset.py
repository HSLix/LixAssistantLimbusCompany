"""按语义名在当前内存截图中检测模板。"""


def execute(ctx, *, asset: str, region: dict[str, int] | None = None,
            threshold: float = 0.9, nms: bool = True,
            nms_iou_threshold: float = 0.5) -> list[dict[str, str | int | float | dict[str, float]]]:
    """只返回识别结果，不重新截图，也不操作游戏。"""

    return ctx.match_asset(asset, region=region, threshold=threshold,
                           nms=nms, nms_iou_threshold=nms_iou_threshold)
