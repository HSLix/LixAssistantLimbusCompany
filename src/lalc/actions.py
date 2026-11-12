"""应用统一注册的 Trusted Actions；Manifest 和 Agent 不拥有注册权限。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, overload


@dataclass(frozen=True)
class TrustedAction:
    """由应用提供的固定分类与可调用实现，签名和 docstring 即调用契约。"""

    execute: Callable[..., Any]
    classification: str

    def __post_init__(self) -> None:
        if self.classification not in {"observe", "control"} or not callable(self.execute):
            raise ValueError("Trusted Action requires a callable and observe/control classification.")


def capture_screen(ctx, *, save: bool = False, auto_park_cursor: bool = True) -> dict[str, int | str]:
    """刷新客户区截图，默认受控移开鼠标；可关闭 auto_park_cursor，按要求保存证据。"""
    return ctx.capture_screen(save=save, auto_park_cursor=auto_park_cursor)


def ocr(ctx, *, region: dict[str, int] | None = None, min_score: float = 0.0) -> dict[str, int | dict[str, int] | list[dict[str, str | float | dict[str, int] | list[int] | list[list[int]]]]]:
    """识别当前帧，返回 observation、region 和完整 items；不刷新，执行器自动保留诊断图，不支持韩文。"""
    return ctx.ocr(region=region, min_score=min_score)


def match_asset(ctx, *, asset: str, priority_tags: list[str] | None = None, region: dict[str, int] | None = None,
                threshold: float = 0.9, nms: bool = True,
                nms_iou_threshold: float = 0.5) -> list[dict[str, str | int | float | list[str] | tuple[int, int] | dict[str, float]]]:
    """返回选定批次经 NMS 后全部命中，保留 centerxy、分数和来源，不自动保存截图；业务 Step 判断多命中歧义并记录 warning 日志。"""
    return ctx.match_asset(asset, priority_tags=priority_tags, region=region, threshold=threshold, nms=nms,
                           nms_iou_threshold=nms_iou_threshold)


def crop_asset(ctx, *, asset: str, region: dict[str, int], tags: list[str] | None = None) -> dict[str, str | int | list[str] | dict[str, int]]:
    """重新截图并保存哈希模板、标签和来源，不修改 Manifest。"""
    return ctx.crop_asset(asset, region=region, tags=tags)


@overload
def click(ctx, *, centerxy: tuple[int, int]) -> None: ...


@overload
def click(ctx, *, x: int, y: int) -> None: ...


def click(ctx, *, centerxy: tuple[int, int] | None = None, x: int | None = None, y: int | None = None) -> None:
    """优先使用 centerxy=target["centerxy"] 点击客户区，也支持完整 x/y，两种形式不可混用；点击返回不证明业务完成。"""
    if centerxy is not None:
        if x is not None or y is not None:
            raise ValueError("click requires either centerxy or x/y, not both")
        x, y = centerxy
    elif x is None or y is None:
        raise ValueError("click requires centerxy or both x and y")
    ctx.control_input("click", x=x, y=y)


def key_press(ctx, *, key: str) -> None:
    """发送一个前台按键，支持 Esc、P 和 Enter。"""
    ctx.control_input("key_press", key=key)


def drag(ctx, *, x: int, y: int, end_x: int, end_y: int, seconds: float = 2.5) -> None:
    """在客户区拖动，持续响应物理接管与取消。"""
    ctx.control_input("drag", x=x, y=y, end_x=end_x, end_y=end_y, seconds=seconds)


def wait(ctx, *, seconds: float) -> None:
    """协作等待 0–60 秒，不注入输入；期间响应暂停、接管与取消，Workflow 接管恢复后重新等待完整时长。"""
    ctx.control_input("wait", seconds=seconds)


def restart_game(ctx) -> None:
    """从保存的 Steam 安装重启游戏：正常关闭超时强制终止，等待新窗口绑定置前；不保证登录或业务就绪，失败终止运行。"""
    ctx.control_input("restart_game")


def application_actions() -> dict[str, TrustedAction]:
    """构建应用唯一动作表；测试可由应用层提供替身表。"""
    return {
        "observe.capture_screen": TrustedAction(capture_screen, "observe"),
        "observe.ocr": TrustedAction(ocr, "observe"),
        "observe.match_asset": TrustedAction(match_asset, "observe"),
        "observe.crop_asset": TrustedAction(crop_asset, "observe"),
        "control.click": TrustedAction(click, "control"),
        "control.key_press": TrustedAction(key_press, "control"),
        "control.drag": TrustedAction(drag, "control"),
        "observe.wait": TrustedAction(wait, "observe"),
        "control.restart_game": TrustedAction(restart_game, "control"),
    }
