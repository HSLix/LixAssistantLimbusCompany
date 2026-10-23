"""开发者直接运行的现场模板裁剪入口。"""

from lalc import step


@step
def execute(ctx, *, asset: str, region: dict[str, int], tags: list[str] | None = None) -> dict[str, str | int | list[str] | dict[str, int]]:
    """新增模板与来源，可独立替换标签，无需发布 Manifest。"""

    return ctx.action("observe.crop_asset", asset=asset, region=region, tags=tags)
