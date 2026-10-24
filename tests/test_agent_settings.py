"""覆盖当前配置、CLI 覆盖、命名密钥边界及 Windows 原生 DPAPI。

在项目根目录运行：uv run --frozen pytest -q tests/test_agent_settings.py
Windows 原生检查在其他平台跳过，不用替身冒充平台验收。
"""

import argparse
import json
import sys

import pytest

import lalc.__main__ as cli
import lalc.agent_settings as settings
from lalc.pi_probe import configured_pi


def arguments(**values):
    return argparse.Namespace(**{**dict.fromkeys(settings.FIELDS), "ask_api_key": False, **values})


def test_saved_settings_and_per_call_overrides(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "default_data_root", lambda: tmp_path)
    assert cli.main(["agent-config", "--base-url", "http://example.test/custom/api", "--model", "chosen",
                     "--max-requests", "8", "--secret-name", "service-token"]) == 0
    saved = (tmp_path / "agent-settings.json").read_bytes()
    assert settings.effective_settings(arguments(model="temporary", max_requests=2), tmp_path) == {
        "base_url": "http://example.test/custom/api", "model": "temporary", "max_requests": 2,
        "secret_name": "service-token", "provider": "llama.cpp", "output_limit": "server_default"}
    assert (tmp_path / "agent-settings.json").read_bytes() == saved
    assert cli.main(["agent-config"]) == 0
    assert "chosen" in capsys.readouterr().out
    assert cli.main(["agent-config", "--clear-secret"]) == 0
    assert settings.load_settings(tmp_path)["secret_name"] is None


@pytest.mark.parametrize("limit", [0, 1, -1])
def test_invalid_limit_does_not_replace_saved_value(tmp_path, monkeypatch, limit):
    monkeypatch.setattr(cli, "default_data_root", lambda: tmp_path)
    assert cli.main(["agent-config", "--max-requests", "4"]) == 0
    assert cli.main(["agent-config", "--max-requests", str(limit)]) == 1
    assert settings.load_settings(tmp_path)["max_requests"] == 4


@pytest.mark.parametrize("address", ["host:8080/v1", "file:///tmp/api", "http://key@host/v1",
                                     "http://host/v1?key=secret", "http://host/v1#secret"])
def test_invalid_or_credential_bearing_addresses_rejected(address):
    with pytest.raises(ValueError):
        settings.validate_settings({"base_url": address})


def test_corrupt_settings_are_not_ignored(tmp_path):
    (tmp_path / "agent-settings.json").write_text('{"max_requests":true}')
    with pytest.raises(ValueError):
        settings.load_settings(tmp_path)


def test_output_limit_only_supports_server_default_and_legacy_settings(tmp_path):
    assert settings.load_settings(tmp_path)["output_limit"] == "server_default"
    with pytest.raises(ValueError, match="服务端默认值"):
        settings.validate_settings({"output_limit": 4096})


def test_invalid_saved_limit_can_be_explicitly_reset(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "default_data_root", lambda: tmp_path)
    (tmp_path / "agent-settings.json").write_text('{"max_requests":1,"model":"chosen"}')
    assert cli.main(["agent-config", "--max-requests", "2"]) == 0
    assert settings.load_settings(tmp_path)["max_requests"] == 2


def test_full_api_path_and_explicit_loaded_model(monkeypatch, tmp_path):
    import lalc.pi_probe as probe
    observed = []
    monkeypatch.setattr(probe.shutil, "which", lambda _: "/pi")
    monkeypatch.setattr(probe.subprocess, "run", lambda *a, **kw: argparse.Namespace(stdout=probe.PI_VERSION))
    models = [{"id": "explicit", "status": {"value": "loaded"}, "architecture": {"input_modalities": ["image"]}}]
    monkeypatch.setattr(probe, "_models", lambda address, key: observed.append(address) or models)
    args = arguments(base_url="http://host:80/full/api/", model="explicit", max_requests=2, pi="pi")
    with configured_pi(args, tmp_path, "memory-secret", "prompt") as (command, env, temporary, model):
        assert env["LALC_PI_BASE_URL"] == "http://host:80/full/api"
        assert "memory-secret" not in str(command)
        from pathlib import Path
        assert all(b"memory-secret" not in p.read_bytes() for p in Path(temporary).rglob("*") if p.is_file())
    assert observed == ["http://host:80/full/api"]
    models[0]["status"]["value"] = "unloaded"
    models[0].pop("architecture")
    with configured_pi(args, tmp_path, "memory-secret", "prompt", require_image=False):
        pass  # 不触发模型请求；仅验证 unloaded 不再被启动配置拦截。
    with pytest.raises(ValueError, match="image input support"):
        with configured_pi(args, tmp_path, "memory-secret", "prompt"):
            pytest.fail("missing image capability accepted")
    args.model = None
    with pytest.raises(ValueError, match="model is required"):
        with configured_pi(args, tmp_path, "memory-secret", "prompt"):
            pytest.fail("implicit model accepted")


def test_secret_separation_and_temporary_override(tmp_path, monkeypatch):
    # 替身仅证明存储分离及选择规则；原生加密另由 Windows 测试验证。
    monkeypatch.setattr(settings, "dpapi", lambda value, **kw: value[7:] if kw.get("decrypt") else b"opaque:" + value)
    settings.save_secret(tmp_path, "../named", "test-only")
    path = settings.secret_path(tmp_path, "../named")
    assert path.parent == tmp_path / "secrets"
    assert not (tmp_path / "agent-settings.json").exists()
    monkeypatch.setattr(settings.sys, "platform", "win32")
    value = settings.validate_settings({"secret_name": "../named"})
    assert settings.resolve_key(arguments(), value, tmp_path) == "test-only"
    monkeypatch.setattr(settings.getpass, "getpass", lambda _: "temporary")
    assert settings.resolve_key(arguments(ask_api_key=True), value, tmp_path) == "temporary"
    assert path.read_bytes() == b"opaque:test-only"
    path.unlink()
    with pytest.raises(FileNotFoundError):
        settings.resolve_key(arguments(), value, tmp_path)


@pytest.mark.skipif(sys.platform == "win32", reason="Mac/non-Windows boundary")
def test_non_windows_refuses_persistence_and_named_read(tmp_path):
    with pytest.raises(ValueError, match="Windows DPAPI"):
        settings.save_secret(tmp_path, "name", "secret")
    assert not (tmp_path / "secrets").exists()
    with pytest.raises(ValueError, match="ask-api-key"):
        settings.resolve_key(arguments(), {"secret_name": "name"}, tmp_path)


@pytest.mark.skipif(sys.platform != "win32", reason="Requires real Windows current-user DPAPI")
def test_windows_native_dpapi_roundtrip_and_corruption(tmp_path):
    secret = "windows-dpapi-evidence-中文"
    settings.save_secret(tmp_path, "named-service", secret)
    path = settings.secret_path(tmp_path, "named-service")
    assert secret.encode() not in path.read_bytes()
    assert settings.resolve_key(arguments(), {"secret_name": "named-service"}, tmp_path) == secret
    path.write_bytes(b"invalid DPAPI blob")
    with pytest.raises(OSError, match="DPAPI decrypt failed"):
        settings.resolve_key(arguments(), {"secret_name": "named-service"}, tmp_path)


@pytest.mark.parametrize("version", ["0.86.1", "1.4.0", "0.85.0"])
def test_pi_version_mismatch_warns_and_continues(monkeypatch, tmp_path, caplog, capsys, version):
    """版本差异不阻止启动；日志、终端及 GUI 共用事件包含实际版本。"""
    import logging
    import lalc.pi_probe as probe
    from lalc.agent_repair import RepairLog
    monkeypatch.setattr(probe.shutil, "which", lambda _: "/pi")
    monkeypatch.setattr(probe.subprocess, "run", lambda *args, **kwargs: argparse.Namespace(stdout=version))
    monkeypatch.setattr(probe, "_models", lambda *args: [{"id": "test", "architecture": {"input_modalities": ["image"]}}])
    args = arguments(base_url="http://host/v1", model="test", max_requests=2, pi="pi")
    events = []
    log = RepairLog(tmp_path, on_event=events.append)
    with caplog.at_level(logging.WARNING, logger="lalc.pi_probe"):
        with configured_pi(args, tmp_path, "lalc-no-key", "prompt", on_warning=log.record) as (command, env, *_):
            assert command[0] == "/pi"
            assert env["LALC_PI_VERSION"] == version
    warning = version != probe.PI_VERSION
    assert bool(events) == warning
    assert bool(caplog.records) == warning
    assert bool(capsys.readouterr().err) == warning
    if warning:
        event = events[0]["event"]
        assert event["type"] == "pi_version_warning"
        assert event["actual_version"] == version and event["expected_version"] == probe.PI_VERSION
        assert caplog.records[0].levelno == logging.WARNING
        assert version in (log.path / "events.jsonl").read_text()
