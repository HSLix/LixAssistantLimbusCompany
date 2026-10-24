"""正式 Component 与 Trusted Action 共用的 Run Context 接口。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .runtime import WorkflowExecutor


class RunContext:
    """向正式 Component 暴露统一的 Component 与 Trusted Action 调用边界。"""

    __slots__ = ("_executor",)

    def __init__(self, executor: WorkflowExecutor) -> None:
        self._executor = executor

    def call(self, logical_name: str, **arguments: Any) -> Any:
        return self._executor.call(logical_name, arguments)

    def action(self, logical_name: str, **arguments: Any) -> Any:
        return self._executor.trusted_action(logical_name, arguments)

    def capture_screen(self, *, save: bool = False) -> dict[str, Any]:
        """只供正在执行的 observe Trusted Action 刷新本次 Run 的截图。"""

        return self._executor.capture_screen(save)

    @property
    def game_language(self) -> str:
        return self._executor.game_language

    def match_asset(
        self, logical_name: str, *, priority_tags: list[str] | None = None, region: dict[str, int] | None = None,
        threshold: float = 0.9, nms: bool = True, nms_iou_threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """仅供 observe Action 在现有内存截图中匹配语义 Asset。"""

        return self._executor.match_asset(logical_name, {
            "priority_tags": priority_tags, "region": region, "threshold": threshold, "nms": nms,
            "nms_iou_threshold": nms_iou_threshold,
        })

    def crop_asset(self, logical_name: str, *, region: dict[str, int], tags: list[str] | None = None) -> dict[str, Any]:
        """仅供 observe Action 请求现场截图裁剪；只新增文件，不改 Manifest。"""

        return self._executor.crop_asset(logical_name, region, tags)

    def control_input(self, operation: str, **arguments: Any) -> None:
        """仅供 control Trusted Action 进入应用拥有的输入会话。"""

        self._executor.control_input(operation, arguments)
