"""示例 Python Plan；发布后由执行器按不可变源码调用。"""
from typing import Any
from lalc import automation_plan

@automation_plan
def execute(ctx, *, task_repetitions: dict[str, int], settings: dict[str, Any]) -> None:
    ctx.call('tasks.greet', name='Lix')
    ctx.call('tasks.greet', name='朋友')
