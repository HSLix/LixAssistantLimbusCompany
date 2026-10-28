"""示范外部弹窗打断 Step 后，由公共规则处理并重新调用本 Step。"""
from lalc import ExecutionFailure, step


@step
def execute(ctx) -> str:
    """弹窗仍可见时明确失败；重入后重新观察，不依赖上一次的局部状态。"""
    ctx.action("observe.capture_screen", save=True)
    matches = ctx.action("observe.match_asset", asset="tutorial/recovery-popup", threshold=0.95)
    if matches:
        raise ExecutionFailure("检测到外部教学弹窗，等待确定性恢复。")
    return "教学弹窗未出现或已关闭；Step 完成。"
