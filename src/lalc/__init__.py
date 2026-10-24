"""Public API frozen into the LALC application bundle."""

API_VERSION = 1

from .run_context import RunContext as RunContext
from .runtime import ExecutionFailure, UserInterruption, step, sub_workflow, task_workflow

__all__ = ["API_VERSION", "RunContext", "ExecutionFailure", "UserInterruption", "api_version", "step", "sub_workflow", "task_workflow"]


def api_version() -> int:
    return API_VERSION
