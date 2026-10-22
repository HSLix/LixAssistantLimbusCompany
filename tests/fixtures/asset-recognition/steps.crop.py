"""开发者直接运行的现场模板裁剪入口。"""

from lalc import step


@step
def execute(ctx, *, asset: str, region: dict[str, int]) -> dict[str, str | int | dict[str, int]]:
    """只新增模板，检查图片及编辑候选 Manifest 由调用方完成。"""

    return ctx.action("observe.crop_asset", asset=asset, region=region)
