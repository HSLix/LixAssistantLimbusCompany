"""显式截图后识别文字；OCR 不支持韩文，结果需由业务步骤判断。"""

from lalc import RunContext, step


@step
def execute(ctx: RunContext, *, region: dict[str, int] | None = None, min_score: float = 0.0) -> dict[str, int | dict[str, int] | list[dict[str, str | float | dict[str, int] | list[int] | list[list[int]]]]]:
    """返回完整 OCR 结果；文字匹配、数字解析和唯一性检查由调用者负责。"""
    ctx.action("observe.capture_screen", save=True)
    return ctx.action("observe.ocr", region=region, min_score=min_score)
