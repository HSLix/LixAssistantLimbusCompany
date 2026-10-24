"""用于多文件编辑检查的相邻 Component。"""

from lalc import step


@step
def execute(ctx) -> str:
    """提供多文件修复检查的固定返回值。"""
    return "unchanged"
