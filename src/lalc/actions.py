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


def capture_screen(ctx, *, save: bool = False) -> dict[str, int | str]:
    """刷新客户区内存截图，按要求保存证据。"""
    return ctx.capture_screen(save=save)


def match_asset(ctx, *, asset: str, priority_tags: list[str] | None = None, region: dict[str, int] | None = None,
                threshold: float = 0.9, nms: bool = True,
                nms_iou_threshold: float = 0.5) -> list[dict[str, str | int | float | list[str] | tuple[int, int] | dict[str, float]]]:
    """使用当前有效截图识别模板，返回全部符合条件的目标。"""
    return ctx.match_asset(asset, priority_tags=priority_tags, region=region, threshold=threshold, nms=nms,
                           nms_iou_threshold=nms_iou_threshold)


def crop_asset(ctx, *, asset: str, region: dict[str, int], tags: list[str] | None = None) -> dict[str, str | int | list[str] | dict[str, int]]:
    """重新截图并保存哈希模板、标签和来源，不修改 Manifest。"""
    return ctx.crop_asset(asset, region=region, tags=tags)


@overload
def click(ctx, *, x: int, y: int) -> None: ...


@overload
def click(ctx, *, centerxy: tuple[int, int]) -> None: ...


def click(ctx, *, x: int | None = None, y: int | None = None, centerxy: tuple[int, int] | None = None) -> None:
    """使用完整 x/y 或二元整数 centerxy 点击客户区，两种形式不可混用。"""
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
    """协作等待指定时长，期间继续检查接管与取消。"""
    ctx.control_input("wait", seconds=seconds)


def application_actions() -> dict[str, TrustedAction]:
    """构建应用唯一动作表；测试可由应用层提供替身表。"""
    return {
        "observe.capture_screen": TrustedAction(capture_screen, "observe"),
        "observe.match_asset": TrustedAction(match_asset, "observe"),
        "observe.crop_asset": TrustedAction(crop_asset, "observe"),
        "control.click": TrustedAction(click, "control"),
        "control.key_press": TrustedAction(key_press, "control"),
        "control.drag": TrustedAction(drag, "control"),
        "control.wait": TrustedAction(wait, "control"),
    }
