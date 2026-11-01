"""正式 Agent 集成测试共用的本机 HTTP 服务替身；不会连接真实模型服务。"""

import json
import shutil
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread

import pytest


@pytest.fixture
def agent_server(tmp_path):
    if not shutil.which("pi"):
        pytest.skip("Requires an installed pi executable")
    state = {"calls": [], "path": "sample.py", "status": 200, "started": Event(), "release": Event()}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            state.setdefault("get_paths", []).append(self.path)
            body = json.dumps({"data": state.get("models", [{"id": "gemma4-test", "status": {"value": "loaded"},
                                "architecture": {"input_modalities": ["text", "image"]}}])}).encode()
            self.send_response(state.get("get_status", 200))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            state.setdefault("post_paths", []).append(self.path)
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["authorization"] = self.headers.get("Authorization")
            state["calls"].append(body)
            state["started"].set()
            if state.get("block"):
                state["release"].wait(15)
            if state.get("disconnect_at") == len(state["calls"]):
                self.connection.shutdown(socket.SHUT_RDWR)
                self.close_connection = True
                return
            self.send_response(state["status"])
            self.send_header("Content-Type", "text/event-stream" if state["status"] == 200 else "application/json")
            if state.get("broken_body_at") == len(state["calls"]):
                self.send_header("Content-Length", "10000")
                self.end_headers()
                self.wfile.write(b"data: ")
                self.wfile.flush()
                self.connection.shutdown(socket.SHUT_RDWR)
                self.close_connection = True
                return
            self.end_headers()
            try:
                if state["status"] != 200:
                    self.wfile.write(json.dumps({"error": {"message": state.get("error_message", "test provider unavailable")}}).encode())
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
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", state, tmp_path
    finally:
        state["release"].set()
        server.shutdown()
        server.server_close()
        worker.join()

