"""Public API frozen into the LALC application bundle."""

API_VERSION = 1

from .runtime import ExecutionFailure, UserInterruption, step, sub_workflow, task_workflow

__all__ = ["API_VERSION", "ExecutionFailure", "UserInterruption", "api_version", "step", "sub_workflow", "task_workflow"]


def api_version() -> int:
    return API_VERSION
