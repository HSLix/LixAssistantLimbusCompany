"""修复工具的固定纯计算缺陷：合计错误地忽略了负数。"""

from lalc import step


@step
def execute(ctx, *, values: list[int]) -> int:
    """返回全部整数之和，包括负数；当前过滤条件是待修复的缺陷种子。"""
    return sum(value for value in values if value > 0)
