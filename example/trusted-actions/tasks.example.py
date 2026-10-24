"""三层调用样例：默认只截图、保存证据并协作等待，不点击游戏。"""
from lalc import RunContext, task_workflow


@task_workflow
def execute(ctx: RunContext, *, save: bool = True, seconds: float = 0.0) -> dict[str, str]:
    """Task 组织 Subworkflow 和 Step，返回可检查的观察信息。"""
    observation = ctx.call("subworkflows.observe", save=save)
    ctx.call("steps.wait", seconds=seconds)
    return {"observation": str(observation["observation"]),
            "evidence_path": str(observation.get("evidence_path", ""))}
