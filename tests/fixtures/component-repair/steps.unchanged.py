"""不应被修复修改的相邻 Component。"""

from lalc import step


@step
def execute(ctx) -> str:
    """提供检查单文件写入边界的固定返回值。"""
    return "unchanged"
