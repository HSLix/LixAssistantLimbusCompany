"""正式 Component 与 Trusted Action 共用的 Run Context 接口。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .runtime import WorkflowExecutor


class RunState:
    """单次 Run 的共享配置；业务数据可修改，恢复计数仅由执行器维护。"""

    __slots__ = ("task_repetitions", "settings", "_recovery_count")
    task_repetitions: dict[str, int]
    settings: dict[str, Any]

    def __init__(self, task_repetitions: dict[str, int] | None = None,
                 settings: dict[str, Any] | None = None) -> None:
        from .runtime import InputValidationError, _strict_json
        repetitions = {} if task_repetitions is None else task_repetitions
        configuration = {} if settings is None else settings
        if (type(repetitions) is not dict or any(type(k) is not str or type(v) is not int or v < 0
                                               for k, v in repetitions.items())):
            raise InputValidationError("task_repetitions must map task IDs to non-negative integers")
        if (type(configuration) is not dict or any(type(k) is not str or type(v) is not dict
                                                 for k, v in configuration.items())):
            raise InputValidationError("settings must map page IDs to JSON objects")
        try:
            self.task_repetitions = _strict_json(repetitions)
            self.settings = _strict_json(configuration)
        except (TypeError, ValueError) as error:
            raise InputValidationError(str(error)) from error
        self._recovery_count = 0

    @property
    def recovery_count(self) -> int:
        return self._recovery_count

    def snapshot(self) -> dict[str, Any]:
        """返回独立的 JSON 快照，非法业务值保留诊断而不伪装为空状态。"""
        from .runtime import _strict_json
        return _strict_json({"task_repetitions": self.task_repetitions, "settings": self.settings,
                             "recovery_count": self.recovery_count})


class RunContext:
    """向正式 Component 暴露统一的 Component 与 Trusted Action 调用边界。"""

    __slots__ = ("_executor",)

    def __init__(self, executor: WorkflowExecutor) -> None:
        self._executor = executor

    def call(self, logical_name: str, **arguments: Any) -> Any:
        return self._executor.call(logical_name, arguments)

    def action(self, logical_name: str, **arguments: Any) -> Any:
        return self._executor.trusted_action(logical_name, arguments)

    @property
    def run_state(self) -> RunState:
        return self._executor.run_state

    def log(self, message: str, *, level: str = "info", screenshot: bool = False) -> None:
        """记录带级别的语义日志；可附上已有截图，不重新截图。"""
        self._executor.log(message, level=level, screenshot=screenshot)

    def capture_screen(self, *, save: bool = False, auto_park_cursor: bool = True) -> dict[str, Any]:
        """只供正在执行的 observe Trusted Action 刷新本次 Run 的截图。"""

        return self._executor.capture_screen(save, auto_park_cursor=auto_park_cursor)

    @property
    def game_language(self) -> str:
        return self._executor.game_language

    def ocr(self, *, region: dict[str, int] | None = None, min_score: float = 0.0) -> dict[str, Any]:
        """仅供 observe Action 识别当前内存截图，不隐式刷新。"""
        return self._executor.ocr(region=region, min_score=min_score)

    def match_asset(
        self, logical_name: str, *, priority_tags: list[str] | None = None, region: dict[str, int] | None = None,
        threshold: float = 0.9, nms: bool = True, nms_iou_threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """仅供 observe Action 在现有内存截图中匹配语义 Asset。"""

        return self._executor.match_asset(logical_name, {
            "priority_tags": priority_tags, "region": region, "threshold": threshold, "nms": nms,
            "nms_iou_threshold": nms_iou_threshold,
        })

    def match_feature(self, logical_name: str, *, region: dict[str, int] | None = None,
                      nms: bool = True, nms_iou_threshold: float = 0.4,
                      grayscale: bool = True, scale: int = 3, clahe: bool = True,
                      nfeatures: int = 0, n_octave_layers: int = 3, contrast_threshold: float = 0.04,
                      edge_threshold: float = 10.0, sigma: float = 1.6, precise_upscale: bool = False,
                      pair_ratio: float = 0.75, ransac_threshold: float = 4 / 3, min_inliers: int = 6,
                      min_inlier_ratio: float = 0.4, min_scale: float = 0.5, max_scale: float = 2.0,
                      max_deformation: float = 2.0, min_coverage: float = 0.1) -> list[dict[str, Any]]:
        """仅供 observe Action 在已有帧中执行整组 SIFT 检测。"""
        return self._executor.match_feature(logical_name, {
            "region": region, "nms": nms, "nms_iou_threshold": nms_iou_threshold,
            "grayscale": grayscale, "scale": scale, "clahe": clahe,
            "nfeatures": nfeatures, "n_octave_layers": n_octave_layers, "contrast_threshold": contrast_threshold,
            "edge_threshold": edge_threshold, "sigma": sigma, "precise_upscale": precise_upscale,
            "pair_ratio": pair_ratio, "ransac_threshold": ransac_threshold, "min_inliers": min_inliers,
            "min_inlier_ratio": min_inlier_ratio, "min_scale": min_scale, "max_scale": max_scale,
            "max_deformation": max_deformation, "min_coverage": min_coverage,
        })

    def crop_asset(self, logical_name: str, *, region: dict[str, int], tags: list[str] | None = None) -> dict[str, Any]:
        """仅供 observe Action 请求现场截图裁剪；只新增文件，不改 Manifest。"""

        return self._executor.crop_asset(logical_name, region, tags)

    def control_input(self, operation: str, **arguments: Any) -> None:
        """供 control Action 进入输入会话；observe Action 仅可调用无输入的 wait。"""

        self._executor.control_input(operation, arguments)
