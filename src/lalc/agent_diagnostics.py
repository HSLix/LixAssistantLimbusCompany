"""共享 Agent 错误证据与脱敏；Settings 检查不进入修复对话或触发推理。"""

from __future__ import annotations

import re
from pathlib import Path

from .runtime import _exception_fields


def redact(value, keys=()):
    """在展示和落盘前递归清除已知密钥及认证字段。"""
    if isinstance(value, str):
        for key in sorted(set(keys), key=len, reverse=True):
            if key and key != "lalc-no-key":
                value = value.replace(key, "[REDACTED]")
        value = re.sub(r'''(?i)(["']?(?:authorization|api[_-]?key|access[_-]?token)["']?\s*[:=]\s*)(?:"[^"\r\n]*"|'[^'\r\n]*'|[^\r\n,;}]+)''',
                       r"\1[REDACTED]", value)
        return re.sub(r"(?i)\bBearer\s+[^\s\"'<>]+", "Bearer [REDACTED]", value)
    if isinstance(value, list):
        return [redact(item, keys) for item in value]
    if isinstance(value, dict):
        return {name: "[REDACTED]" if name.lower().replace("-", "_") in {
            "authorization", "api_key", "access_token"} else redact(item, keys)
                for name, item in value.items()}
    return value


class AgentDiagnosticError(ValueError):
    """携带失败阶段和服务证据，保留底层异常链供脱敏后查看。"""

    def __init__(self, message, stage, **evidence):
        super().__init__(message)
        self.stage = stage
        self.evidence = evidence


def error_details(error, stage, context=None, keys=()):
    """保留非空摘要、原始异常链及同一次操作的配置与证据定位。"""
    return redact({**(context or {}), **_exception_fields(error),
                   "message": str(error) or type(error).__name__,
                   "stage": getattr(error, "stage", stage),
                   **getattr(error, "evidence", {})}, keys)


def details_text(details):
    """配置证据与原始多行异常链分别展示，便于阅读和复制。"""
    import json
    text = json.dumps({k: v for k, v in details.items() if k not in {"traceback", "raw_text", "json_text"}},
                      ensure_ascii=False, indent=2)
    if "raw_text" in details:
        text += "\n\n模型实际回复（raw_text）：\n" + (details["raw_text"] or "（没有文本内容）")
    if "json_text" in details and details["json_text"] != details.get("raw_text"):
        text += "\n\nJSON 解析输入（json_text）：\n" + details["json_text"]
    return text + "\n\n" + details.get("traceback", "")


def check_settings(data_root: Path, values: dict, *, key=None, check_model=False, snapshot=False):
    """检查表单快照并独立留证；不保存设置、不请求推理、不加载模型。"""
    from types import SimpleNamespace
    from .agent_settings import load_settings, resolve_key, validate_settings
    from .agent_repair import RepairLog
    from .pi_probe import _models
    log = RepairLog(data_root, key or "lalc-no-key", category="agent-diagnostics")
    context = {"operation": "model_status" if check_model else "connection",
               "settings": values, "log_path": str(log.path)}
    try:
        settings = validate_settings(values) if snapshot else load_settings(data_root, values)
        log.key = key if key is not None else resolve_key(SimpleNamespace(ask_api_key=False), settings, data_root)
        models = _models(settings["base_url"].rstrip("/"), log.key)
        result = {"ok": True, "message": f"连接成功，认证通过，可读取模型列表（{len(models)} 项）；未测试推理。"}
        if check_model:
            if not settings["model"]:
                raise AgentDiagnosticError("请填写需要检查的模型 ID。", "model_status")
            matches = [item for item in models if item["id"] == settings["model"]]
            if len(matches) != 1:
                raise AgentDiagnosticError(f"模型不存在或 ID 不唯一：{settings['model']}", "model_status")
            if settings["provider"] == "deepseek":
                result.update(message="deepseek-flash 可用；支持图片输入，未测试推理。")
                status = "unknown"
            else:
                status = matches[0].get("status", {}).get("value", "unknown")
            labels = {"loaded": "已加载", "unloaded": "未加载", "loading": "加载中", "unknown": "服务未提供状态"}
            result["model_status"] = status
            if settings["provider"] != "deepseek":
                result["message"] = f"模型状态：{labels.get(status, status)}（{status}）；未测试推理。"
    except Exception as error:
        result = {"ok": False, "error": error_details(error, "settings", context, log.keys)}
        result["message"] = result["error"]["message"]
        import logging
        logging.getLogger("lalc").error("Agent Settings 检查失败：%s", result["error"])
    result = log.clean({**context, **result})
    log.save_json("result.json", result)
    log.record({"type": "settings_check", **result})
    return result
