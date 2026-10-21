"""交互层与进程最外层共用的错误文本和持久日志。"""

from __future__ import annotations

import logging
from pathlib import Path

FATAL_MESSAGE = (
    "程序出现致命错误，无法继续运行。\n"
    "以下是可报告给开发者的原始错误信息，可以直接复制。\n\n"
    "A fatal error occurred. The application cannot continue.\n"
    "You can copy the original error information below and report it to the developer."
)


def configure_logging(data_root: Path) -> None:
    """GUI 和 CLI 共用持久日志；同一路径只安装一个处理器。"""

    path = (data_root / "logs" / "lalc.log").resolve()
    logger = logging.getLogger("lalc")
    if any(isinstance(handler, logging.FileHandler) and handler.baseFilename == str(path)
           for handler in logger.handlers):
        return
    for handler in list(logger.handlers):
        if handler.name == "lalc-file":
            logger.removeHandler(handler)
            handler.close()
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.set_name("lalc-file")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def result_diagnostics(result: dict) -> str:
    """完整展示串联失败，包含原任务结果、清理错误和 Plan 条目。"""

    parts = []
    if result.get("previous_result"):
        parts.append(result_diagnostics(result["previous_result"]))
    for error in result.get("fatal_errors", []):
        parts.append(error.get("traceback", error.get("failure_message", "")))
    diagnostic = result.get("traceback") or result.get("failure_message") or result.get("reason", "")
    if diagnostic and diagnostic not in parts:
        parts.append(diagnostic)
    for item in result.get("items", []):
        if item.get("result") == "failure":
            parts.append(result_diagnostics(item))
    for error in result.get("errors", []):
        parts.append(error.get("traceback") or error.get("message", str(error)))
    return "\n".join(part for part in parts if part)
