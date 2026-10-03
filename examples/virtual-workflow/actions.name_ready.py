"""虚拟 observe Action：判断名字是否有非空白字符。"""


def execute(ctx, *, name: str) -> bool:
    """返回问候输入是否有效，不读取外部环境。"""
    return bool(name.strip())
