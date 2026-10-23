"""覆盖真实 pi 二进制的受限读取、图片传输、请求上限、错误停止与取消。

在项目根目录运行：
UV_CACHE_DIR=.generated/uv-cache uv run --frozen pytest --run-agent-tests -q tests/test_pi_probe.py
默认回归跳过；仅在确需验证 Agent 功能时显式运行。
模型服务使用本机 HTTP 替身；不代替 Gemma4 或 Windows 验收。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread

import pytest

import lalc.__main__ as cli


pytestmark = pytest.mark.agent


@pytest.fixture
def probe(tmp_path):
    if not shutil.which("pi"):
        pytest.skip("Requires pi 0.86.1 standalone executable")
    root = tmp_path / "source"
    root.mkdir()
    (root / "sample.py").write_text('"""只读样例。"""\nANSWER = "source evidence"\n', encoding="utf-8")
    outside = tmp_path / "outside.py"
    outside.write_text("PRIVATE_OUTSIDE_CONTENT", encoding="utf-8")
    (root / "link.py").symlink_to(outside)
    image = tmp_path / "image.png"
    # 图片由 HTTP 替身检查原样传入，不需要替身执行视觉推理。
    import base64
    image.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII="))
    state = {"calls": [], "path": "sample.py", "status": 200, "started": Event(), "release": Event()}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            body = json.dumps({"data": [{"id": "gemma4-test", "architecture": {
                "input_modalities": ["text", "image"]}}]}).encode()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["authorization"] = self.headers.get("Authorization")
            state["calls"].append(body)
            state["started"].set()
            if state.get("block"):
                state["release"].wait(15)
            self.send_response(state["status"])
            self.send_header("Content-Type", "text/event-stream" if state["status"] == 200 else "application/json")
            self.end_headers()
            try:
                if state["status"] != 200:
                    self.wfile.write(b'{"error":{"message":"test provider unavailable"}}')
                    return
                if "respond" in state:
                    delta, finish = state["respond"](body)
                elif len(state["calls"]) == 1:
                    delta = {"role": "assistant", "tool_calls": [{"index": 0, "id": "read-1", "type": "function",
                             "function": {"name": "read", "arguments": json.dumps({"path": state["path"]})}}]}
                    finish = "tool_calls"
                else:
                    delta = {"role": "assistant", "content": "Source inspected; image received."}
                    finish = "stop"
                for change, reason in ((delta, None), ({}, finish)):
                    chunk = {"id": "test", "model": "gemma4-test", "choices": [
                        {"index": 0, "delta": change, "finish_reason": reason}]}
                    self.wfile.write(("data: " + json.dumps(chunk) + "\n\n").encode())
                self.wfile.write(b"data: [DONE]\n\n")
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    command = [sys.executable, "-m", "lalc", "pi-probe", "--base-url", f"http://127.0.0.1:{server.server_port}",
               "--image", str(image), "--source-root", str(root), "--source", "sample.py"]
    try:
        yield command, state, tmp_path
    finally:
        state["release"].set()
        server.shutdown()
        server.server_close()
        worker.join()


def test_cli_probe_skips_persistent_logging(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "configure_logging", lambda _: pytest.fail("Unexpected persistent log"))
    import lalc.pi_probe
    monkeypatch.setattr(lalc.pi_probe, "run_probe", lambda _: 0)
    assert cli.main(["pi-probe", "--image", "a.png", "--source-root", str(tmp_path), "--source", "a.py"]) == 0


def test_image_and_restricted_read_with_real_pi(probe):
    command, state, directory = probe
    # 私人上下文与扩展发现必须被关闭，即使进程继承了已有配置路径。
    private = directory / "personal"
    private.mkdir()
    (private / "AGENTS.md").write_text("UNAUTHORIZED_CONTEXT_MARKER", encoding="utf-8")
    extensions = private / "extensions"
    extensions.mkdir()
    (extensions / "unauthorized.ts").write_text('throw new Error("UNAUTHORIZED_EXTENSION_MARKER");', encoding="utf-8")
    result = subprocess.run(command + ["--ask-api-key"], input="test-memory-only-key\n", capture_output=True, text=True, timeout=40,
                            env={**os.environ, "PI_CODING_AGENT_DIR": str(private)})
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(state["calls"]) == 2
    first, second = state["calls"]
    assert [tool["function"]["name"] for tool in first["tools"]] == ["read"]
    assert any(part["type"] == "image_url" for message in first["messages"]
               if isinstance(message.get("content"), list) for part in message["content"])
    assert any(message["role"] == "tool" and "source evidence" in message["content"] for message in second["messages"])
    assert "UNAUTHORIZED_CONTEXT_MARKER" not in json.dumps(state["calls"])
    assert "UNAUTHORIZED_EXTENSION_MARKER" not in result.stdout + result.stderr
    assert state["authorization"] == "Bearer test-memory-only-key"
    assert "test-memory-only-key" not in result.stdout + result.stderr + json.dumps(state["calls"])
    assert not (private / "auth.json").exists()
    assert '"result": "completed"' in result.stdout
    assert "iVBORw0KGgoAAAANSUhEUgAAAAE" not in result.stdout
    assert not list(directory.rglob("*.jsonl"))


@pytest.mark.parametrize("path", ["../outside.py", "link.py"])
def test_actual_read_rejects_escape(probe, path):
    command, state, _ = probe
    state["path"] = path
    result = subprocess.run(command, capture_output=True, text=True, timeout=40)
    assert result.returncode == 1, result.stdout
    assert "outside allowed directory" in result.stdout
    assert "PRIVATE_OUTSIDE_CONTENT" not in result.stdout
    assert "PRIVATE_OUTSIDE_CONTENT" not in json.dumps(state["calls"])


def test_limit_rejects_next_request_before_http(probe):
    command, state, _ = probe
    result = subprocess.run(command + ["--max-requests", "1"], capture_output=True, text=True, timeout=40)
    assert result.returncode == 1, result.stdout
    assert len(state["calls"]) == 1
    assert "LALC request limit reached" in result.stdout


def test_provider_error_has_no_hidden_retries(probe):
    command, state, _ = probe
    state["status"] = 503
    result = subprocess.run(command, capture_output=True, text=True, timeout=40)
    assert result.returncode == 1, result.stdout
    assert len(state["calls"]) == 1
    assert '"result": "incomplete"' in result.stdout


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX SIGINT delivery; Windows needs actual exe acceptance")
def test_cancel_stops_probe(probe):
    command, state, _ = probe
    state["block"] = True
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert state["started"].wait(15)
        process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate(timeout=15)
        assert process.returncode == 130, stdout + stderr
        assert '"result": "cancelled"' in stdout
        assert len(state["calls"]) == 1
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
