"""Public API frozen into the LALC application bundle."""

API_VERSION = 1

from .runtime import step

__all__ = ["API_VERSION", "api_version", "step"]


def api_version() -> int:
    return API_VERSION
