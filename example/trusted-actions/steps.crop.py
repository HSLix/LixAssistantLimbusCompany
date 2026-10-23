"""从新截取的游戏画面裁剪模板，只保存图片与来源。"""
from lalc import step


@step
def execute(ctx, *, asset: str, region: dict[str, int], tags: list[str] | None = None) -> dict[str, str | int | list[str] | dict[str, int]]:
    """检查返回的图片后，可用 add-asset 继续追加标签。"""
    return ctx.action("observe.crop_asset", asset=asset, region=region, tags=tags)
