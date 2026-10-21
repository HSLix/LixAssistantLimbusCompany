"""现场截图并裁剪新增模板，不改变任何 Manifest。"""


def execute(ctx, *, asset: str, region: dict[str, int]) -> dict[str, str | int | dict[str, int]]:
    """返回新图片路径、哈希、实际截图编号和来源信息供检查。"""

    return ctx.crop_asset(asset, region=region)
