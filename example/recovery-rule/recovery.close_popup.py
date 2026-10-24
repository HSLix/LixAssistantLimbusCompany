"""处理跨 Workflow 的教学弹窗；模板应取自可安全点击的关闭按钮。"""
from lalc import ExecutionFailure


def detect(ctx) -> bool:
    """只观察是否存在目标，不在检测阶段点击。"""
    ctx.action("observe.capture_screen", save=True)
    return bool(ctx.action("observe.match_asset", asset="tutorial/recovery-popup", threshold=0.95))


def recover(ctx) -> None:
    """重新观察，只有唯一关闭按钮才点击；不能确定时明确失败。"""
    ctx.action("observe.capture_screen", save=True)
    matches = ctx.action("observe.match_asset", asset="tutorial/recovery-popup", threshold=0.95)
    if len(matches) != 1:
        raise ExecutionFailure("关闭按钮不是唯一匹配，停止恢复。")
    target = matches[0]
    ctx.action("control.click", x=target["x"] + target["width"] // 2,
               y=target["y"] + target["height"] // 2)
