"""从新截取的游戏画面裁剪模板，只保存图片与来源。"""
from lalc import step


@step
def execute(ctx, *, asset: str, region: dict[str, int]) -> dict[str, str | int | dict[str, int]]:
    """检查返回的图片后，用 add-asset 登记到 Developer Candidate。"""
    return ctx.action("observe.crop_asset", asset=asset, region=region)
