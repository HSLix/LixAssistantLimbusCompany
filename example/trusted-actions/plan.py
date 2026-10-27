"""示例 Python Plan；发布后由执行器按不可变源码调用。"""
from typing import Any
from lalc import automation_plan

@automation_plan
def execute(ctx, *, task_repetitions: dict[str, int], settings: dict[str, Any]) -> None:
    ctx.call('tasks.example', save=True, seconds=0)
    ctx.call('tasks.example', save=False, seconds=1)
