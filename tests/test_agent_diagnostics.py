"""覆盖 Provider 兼容、只读诊断、HTTP 原因、脱敏和修复错误留证；不启动 pi 或模型。

在项目根目录运行：QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_agent_diagnostics.py
"""

import asyncio
import io
import json
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest

from lalc.agent_diagnostics import check_settings, error_details, redact
from lalc.agent_settings import load_settings, validate_settings
from lalc.pi_probe import _models
from test_agent_repair import host_for, candidate_files


def test_old_settings_keep_complete_path_and_secret_reference(tmp_path):
    path = tmp_path / "agent-settings.json"
    path.write_text(json.dumps({"base_url": "http://host/custom/api", "model": "Gemma4", "secret_name": "old"}))
    before = path.read_bytes()
    settings = load_settings(tmp_path)
    assert settings["provider"] == "llama.cpp"
    assert settings["base_url"] == "http://host/custom/api" and settings["secret_name"] == "old"
    assert before == path.read_bytes()
    with pytest.raises(ValueError, match="provider"):
        validate_settings({"provider": "deepseek"})


@pytest.mark.parametrize("status", ["loaded", "unloaded", "loading", "failed", None])
def test_status_check_is_read_only_and_records_unknown_state(tmp_path, monkeypatch, status):
    calls = []
    def models(base, key):
        calls.append((base, key))
        return [{"id": "Gemma4", **({"status": {"value": status}} if status else {})}]
    monkeypatch.setattr("lalc.pi_probe._models", models)
    result = check_settings(tmp_path, {"base_url": "http://host/custom/api/", "model": "Gemma4"},
                            key="test-secret", check_model=True)
    assert result["ok"] and result["model_status"] == (status or "unknown")
    assert calls == [("http://host/custom/api", "test-secret")]
    assert not (tmp_path / "agent-settings.json").exists()
    assert not (tmp_path / "agent-interactions").exists()
    assert not (tmp_path / "candidate").exists()
    assert len(list(tmp_path.rglob("result.json"))) == 1
    assert "test-secret" not in "".join(p.read_text() for p in tmp_path.rglob("*.json*"))


def test_connection_does_not_require_model_but_model_check_does(tmp_path, monkeypatch):
    monkeypatch.setattr("lalc.pi_probe._models", lambda *args: [])
    assert check_settings(tmp_path, {}, key="lalc-no-key")["ok"]
    result = check_settings(tmp_path, {"model": "missing"}, key="lalc-no-key", check_model=True)
    assert not result["ok"] and result["error"]["stage"] == "model_status"
    assert "missing" in result["message"] and "traceback" in result["error"]


@pytest.mark.parametrize("code", [401, 403, 502])
def test_http_details_keep_body_cause_and_redact_before_logging(tmp_path, monkeypatch, caplog, code):
    def fail(request, timeout):
        assert request.full_url == "http://host/full/api/models" and timeout == 10
        raise HTTPError(request.full_url, code, "upstream failure", {},
                        io.BytesIO(b'upstream says test-secret; Authorization: Bearer other-token'))
    monkeypatch.setattr("lalc.pi_probe.urlopen", fail)
    result = check_settings(tmp_path, {"base_url": "http://host/full/api"}, key="test-secret")
    error = result["error"]
    assert error["http_status"] == code and error["stage"] == "service_check"
    assert "upstream says" in error["response_body"] and "HTTPError" in error["traceback"]
    assert "direct cause" in error["traceback"]
    text = json.dumps(result) + caplog.text + "".join(p.read_text() for p in tmp_path.rglob("*.json*"))
    assert "test-secret" not in text and "other-token" not in text
    assert "ERROR" in caplog.text


@pytest.mark.parametrize("reason", [URLError("connection refused"), URLError(TimeoutError()), TimeoutError()])
def test_unreachable_errors_keep_nonempty_reason(monkeypatch, reason):
    def fail(*args, **kwargs):
        raise reason
    monkeypatch.setattr("lalc.pi_probe.urlopen", fail)
    with pytest.raises(ValueError) as caught:
        _models("http://host/v1", "lalc-no-key")
    details = error_details(caught.value, "check")
    assert details["message"] and details["cause"] and details["traceback"]
    assert details["url"] == "http://host/v1/models"


@pytest.mark.parametrize("body", [b"not json", b'{}', b'{"data":[1]}'])
def test_invalid_model_responses_are_diagnostic(monkeypatch, body):
    monkeypatch.setattr("lalc.pi_probe.urlopen", lambda *a, **k: io.BytesIO(body))
    with pytest.raises(ValueError, match="响应"):
        _models("http://host/v1", "lalc-no-key")


@pytest.mark.parametrize("error_stage", ["settings", "pi_start", "model_preflight", "agent", "cancel_cleanup"])
def test_repair_failure_preserves_candidate_context_and_full_details(tmp_path, monkeypatch, caplog, error_stage):
    from contextlib import contextmanager
    from lalc.agent_diagnostics import AgentDiagnosticError
    host, _ = host_for(tmp_path)
    chat = host.conversation
    before = candidate_files(host.candidate)
    history = {"role": "user", "content": [{"type": "text", "text": "prior"}]}
    chat.history.append(history)
    @contextmanager
    def fail(*args, **kwargs):
        raise AgentDiagnosticError("test-secret failure", error_stage)
        yield
    monkeypatch.setattr("lalc.agent_repair.configured_pi", fail)
    result = asyncio.run(chat.run("test", SimpleNamespace(pi="pi", ask_api_key=False), key="test-secret"))
    assert result["status"] == "incomplete" and result["diagnostics"]["stage"] == error_stage
    assert result["diagnostics"]["round"] == 1 and "traceback" in result["diagnostics"]
    assert candidate_files(host.candidate) == before and chat.history[0] == history
    assert host.conversation is chat and result["requests"] == 0
    assert "test-secret" not in json.dumps(result) + caplog.text
    assert "test-secret" not in "".join(p.read_text() for p in chat.log.path.rglob("*.json*"))
    assert list(chat.log.path.glob("round-1/result.json"))


def test_redaction_covers_nested_auth_fields_and_rotated_keys():
    value = {"Authorization": "anything", "headers": {"API-Key": "other"},
             "body": "old-key new-key Bearer unknown-token"}
    result = redact(value, ["old-key", "new-key"])
    assert result["Authorization"] == result["headers"]["API-Key"] == "[REDACTED]"
    assert all(secret not in str(result) for secret in ["old-key", "new-key", "unknown-token", "anything", "other"])
    assert "opaque" not in redact("Authorization: Basic opaque\nAPI-Key=opaque\naccess_token: opaque")


def test_next_round_reads_new_saved_settings_without_new_conversation(tmp_path, monkeypatch):
    from contextlib import contextmanager
    from lalc.agent_settings import save_settings
    host, _ = host_for(tmp_path)
    chat, models = host.conversation, []
    @contextmanager
    def fail(options, *args, **kwargs):
        models.append(options.model)
        raise ValueError("stop before pi")
        yield
    monkeypatch.setattr("lalc.agent_repair.configured_pi", fail)
    options = SimpleNamespace(pi="pi", ask_api_key=False)
    save_settings(host.service.data_root, {"model": "first"})
    asyncio.run(chat.run("first", options))
    save_settings(host.service.data_root, {"model": "second"})
    asyncio.run(chat.run("second", options))
    assert models == ["first", "second"] and host.conversation is chat
    assert chat.log.group == 2 and len(chat.history) == 2


def test_rpc_spawn_error_reports_original_cause(monkeypatch):
    from lalc.pi_probe import rpc_session
    async def fail(*args, **kwargs):
        raise FileNotFoundError("missing pi")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fail)
    async def exercise():
        async with rpc_session(["pi"], {}, ".", lambda _: None):
            pytest.fail("spawn failure accepted")
    with pytest.raises(ValueError) as caught:
        asyncio.run(exercise())
    details = error_details(caught.value, "unknown")
    assert details["stage"] == "pi_start" and "FileNotFoundError" in details["traceback"]


def test_cancel_cleanup_error_is_distinct_and_process_is_reaped(monkeypatch):
    from lalc.pi_probe import rpc_session
    class Input:
        def write(self, value):
            raise BrokenPipeError("abort failed")
        def close(self):
            pass
    class Output:
        async def readline(self):
            return b""
    class Process:
        returncode = None
        stdin, stderr = Input(), Output()
        async def wait(self):
            self.returncode = 0
            return 0
    process = Process()
    async def spawn(*args, **kwargs):
        return process
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    async def exercise():
        async with rpc_session(["pi"], {}, ".", lambda _: None):
            raise asyncio.CancelledError()
    with pytest.raises(ValueError) as caught:
        asyncio.run(exercise())
    details = error_details(caught.value, "unknown")
    assert details["stage"] == "cancel_cleanup" and "BrokenPipeError" in details["traceback"]
    assert process.returncode == 0
