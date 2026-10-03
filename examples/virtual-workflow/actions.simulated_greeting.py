"""虚拟 control Action：模拟一次问候，不操作真实设备。"""


def execute(ctx, *, name: str) -> str:
    """仅返回模拟动作结果。"""
    return f"Hello, {name}！"
