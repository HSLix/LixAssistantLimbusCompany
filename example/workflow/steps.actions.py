"""在一个 Step 中展示全部可信工具；每次只执行指定操作，不判断游戏业务完成。"""
from lalc import RunContext, step


@step
def execute(ctx: RunContext, *, operation: str = "capture", save: bool = True,
            seconds: float | None = None, x: int | None = None, y: int | None = None,
            end_x: int | None = None, end_y: int | None = None, key: str = "",
            asset: str = "", region: dict[str, int] | None = None, tags: list[str] | None = None,
            priority_tags: list[str] | None = None, min_score: float = 0.0,
            threshold: float = 0.9, nms: bool = True, nms_iou_threshold: float = 0.5) -> (
    dict[str, int | str]
    | dict[str, str | int | list[str] | dict[str, int]]
    | list[dict[str, str | int | float | list[str] | tuple[int, int] | dict[str, float]]]
    | dict[str, int | dict[str, int] | list[dict[str, str | float | dict[str, int] | list[int] | list[list[int]]]]]
    | None
):
    """参数直接传给对应工具；控制操作会发送真实输入，裁剪会写入素材库。"""
    if operation == "capture":
        return ctx.action("observe.capture_screen", save=save)
    if operation == "ocr":
        ctx.action("observe.capture_screen", save=True)
        return ctx.action("observe.ocr", region=region, min_score=min_score)
    if operation == "wait":
        ctx.action("control.wait", seconds=0.0 if seconds is None else seconds)
        return None
    if operation == "click":
        ctx.action("observe.capture_screen")
        ctx.action("control.click", x=x, y=y)
        ctx.action("observe.capture_screen", save=True)
        return None
    if operation == "key_press":
        ctx.action("observe.capture_screen")
        ctx.action("control.key_press", key=key)
        ctx.action("observe.capture_screen", save=True)
        return None
    if operation == "drag":
        ctx.action("observe.capture_screen")
        ctx.action("control.drag", x=x, y=y, end_x=end_x, end_y=end_y, seconds=2.5 if seconds is None else seconds)
        ctx.action("observe.capture_screen", save=True)
        return None
    if operation == "crop":
        return ctx.action("observe.crop_asset", asset=asset, region=region, tags=tags)
    if operation == "match":
        ctx.action("observe.capture_screen", save=True)
        return ctx.action("observe.match_asset", asset=asset, priority_tags=priority_tags, region=region,
                          threshold=threshold, nms=nms, nms_iou_threshold=nms_iou_threshold)
    raise ValueError(f"未知教学操作：{operation}")
