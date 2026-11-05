"""专用 codesearch 查询进程与显式索引构建；不继承用户注册表或分析工具链。"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

from .file_content import require_disk
from .page_packages import real_directory
from .pi_probe import pi_process_environment

MODEL_REPO = "models--Xenova--all-MiniLM-L6-v2"
MODEL_REVISION = "751bff37182d3f1213fa05d7196b954e230abad9"
MODEL_FILES = {
    "config.json": "7135149f7cffa1a573466c6e4d8423ed73b62fd2332c575bf738a0d033f70df7",
    "tokenizer_config.json": "9261e7d79b44c8195c1cada2b453e55b00aeb81e907a6664974b4d7776172ab3",
    "special_tokens_map.json": "b6d346be366a7d1d48332dbc9fdf3bf8960b5d879522b7799ddba59e76237ee3",
    "tokenizer.json": "da0e79933b9ed51798a3ae27893d3c5fa4a201126cef75586296df9b4d2c62a0",
    "onnx/model_quantized.onnx": "afdb6f1a0e45b715d0bb9b11772f032c399babd23bfc31fed1c170afc848bdb1",
}


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def stop(process):
    """回收本实例的进程树，避免构建中断后仍持有索引文件。"""
    if process is None or process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait(timeout=5)


def spawn(command, env, **options):
    """冻结宿主沿用 pi 的 DLL 隔离，并回收环境恢复失败时已创建的进程。"""
    process = None
    try:
        with pi_process_environment(env) as prepared:
            process = subprocess.Popen(command, env=prepared, **options)
        return process
    except BaseException:
        stop(process)
        raise


class CodeSearch:
    """按需启动、按配置复用查询实例；索引只由独立宿主命令构建。"""

    def __init__(self, data_root):
        self.root = Path(data_root).resolve() / "codesearch"
        self.process = None
        self.log = None
        self.address = None
        self.registered = None
        self.binary = None
        self.env = None

    def close(self):
        stop(self.process)
        self.process = None
        if self.log is not None:
            self.log.close()
            self.log = None
        self.address = self.registered = None

    def prepare(self):
        """仅接受已准备的程序和固定模型文件，缺失时绝不启动下载。"""
        if self.binary is not None:
            return
        real_directory(self.root).mkdir(parents=True, exist_ok=True)
        bundled = Path(sys.executable).resolve().parent / "agent" if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2] / "codesearch_resources"
        name = "codesearch.exe" if os.name == "nt" else "codesearch"
        selected = os.environ.get("LALC_CODESEARCH") or (str(bundled / name) if (bundled / name).is_file() else shutil.which("codesearch"))
        if not selected:
            raise FileNotFoundError("codesearch 未准备；仍可使用 knowledge_search_literal 和 knowledge_read。")
        selected = Path(selected).resolve(strict=True)
        with pi_process_environment(os.environ) as prepared:
            version = subprocess.run([str(selected), "--version"], env=prepared, capture_output=True, text=True, timeout=10,
                                     **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}))
        words = version.stdout.strip().split()
        if version.returncode or len(words) != 2 or words[0] != "codesearch" or words[1].split("+", 1)[0] != "1.7.9":
            raise ValueError("codesearch 需要已验证的 1.7.9 基础版。")
        source = Path(os.environ.get("LALC_CODESEARCH_MODELS", bundled / "models"))
        if not source.exists():
            source = self.root / "models"
        snapshot = source / MODEL_REPO / "snapshots" / MODEL_REVISION
        for filename, expected in MODEL_FILES.items():
            if not (snapshot / filename).is_file() or digest(snapshot / filename) != expected:
                raise FileNotFoundError("默认 MiniLM 模型缺失或哈希不符；请离线准备模型，不会自动下载。")
        target = real_directory(self.root / "models" / MODEL_REPO / "snapshots" / MODEL_REVISION)
        runtime = real_directory(self.root / "bin")
        missing = [(snapshot / name, target / name) for name in MODEL_FILES
                   if not (target / name).is_file() or digest(target / name) != MODEL_FILES[name]]
        require_disk([(self.root, sum(a.stat().st_size for a, _ in missing) + selected.stat().st_size)])
        for original, destination in missing:
            real_directory(destination.parent).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, destination)
        refs = real_directory(self.root / "models" / MODEL_REPO / "refs")
        refs.mkdir(parents=True, exist_ok=True)
        (refs / "main").write_text(MODEL_REVISION)
        runtime.mkdir(exist_ok=True)
        executable = runtime / name
        if not executable.is_file() or digest(executable) != digest(selected):
            shutil.copy2(selected, executable)
        git = shutil.which("git")
        if not git:
            raise FileNotFoundError("系统 Git 不可用。")
        if os.name == "nt":
            path = os.pathsep.join([str(Path(git).parent), str(Path(os.environ["SystemRoot"]) / "System32")])
            if any(shutil.which(tool, path=path) for tool in ("npx", "scip-csharp", "scip-typescript")):
                raise ValueError("Git 工具路径包含额外分析工具，不能启动受控 codesearch。")
        else:
            tools = real_directory(self.root / "git-bin")
            tools.mkdir(exist_ok=True)
            link = tools / "git"
            if link.is_symlink() and link.resolve() != Path(git).resolve():
                link.unlink()
            if not link.exists():
                link.symlink_to(Path(git).resolve())
            path = str(tools)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("CODESEARCH_", "GIT_", "HF_"))}
        env.update(CODESEARCH_HOME=str(self.root), CODESEARCH_REPOS_CONFIG=str(self.root / "build-repos.json"),
                   CODESEARCH_EMBED_THREADS="2", HF_ENDPOINT="http://127.0.0.1:9", HF_HUB_OFFLINE="1",
                   CSHARP_PREWARM_ENABLED="false", PATH=path)
        self.binary, self.env = str(executable), env

    def build(self, repo, checkpoint):
        """构建独立 B；失败、取消与超时不修改当前服务注册的 A。"""
        self.prepare()
        assert self.binary is not None and self.env is not None
        top = subprocess.run(["git", "-C", str(repo), "rev-parse", "--show-toplevel"], env=self.env,
                             capture_output=True, text=True, timeout=10,
                             **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}))
        if top.returncode or Path(top.stdout.strip()).resolve() != repo.resolve():
            raise ValueError("索引目标必须是允许的独立 Git 根，不能上溯或指向外部工作区。")
        with tempfile.TemporaryFile() as output:
            if (repo / ".codesearch.db").exists():
                raise ValueError("索引构建目标必须为未发布的新副本。")
            process = spawn([self.binary, "index", "add", str(repo), "--local", "--model", "minilm-l6-q",
                             "--log-file", str(repo / ".codesearch-build.log")], self.env,
                stdout=output, stderr=subprocess.STDOUT,
                creationflags=(subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == "nt" else 0,
                start_new_session=os.name != "nt")
            try:
                started = time.monotonic()
                while process.poll() is None:
                    checkpoint()
                    if time.monotonic() - started > 600:
                        raise TimeoutError("codesearch 索引构建超时。")
                    if output.tell() > 4 * 1024 * 1024:
                        raise ValueError("codesearch 构建输出超过上限。")
                    time.sleep(.03)
                checkpoint()
                if process.returncode:
                    output.seek(0)
                    raise ValueError("codesearch 建索引失败：" + output.read(8000).decode(errors="replace"))
                metadata = json.loads((repo / ".codesearch.db/metadata.json").read_text())
                if metadata.get("partial") or metadata.get("model_short_name") != "minilm-l6-q":
                    raise ValueError("codesearch 索引未完整建立或模型不符。")
            finally:
                stop(process)

    def _request(self, path, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(self.address + path, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=30) as response:
            content = response.read(4 * 1024 * 1024 + 1)
        if len(content) > 4 * 1024 * 1024:
            raise ValueError("codesearch 查询输出超过上限。")
        return json.loads(content)

    def ensure(self, repositories, checkpoint):
        self.prepare()
        assert self.binary is not None and self.env is not None
        registered = tuple(sorted((key, str(value)) for key, value in repositories.items()))
        if self.process is not None and self.process.poll() is None and self.registered == registered:
            return
        self.close()
        config = {"repos": dict(registered), "groups": {}, "repo_read_only": {key: True for key, _ in registered}}
        (self.root / "repos.json").write_text(json.dumps(config), encoding="utf-8")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        self.address = f"http://127.0.0.1:{port}"
        env = dict(self.env, CODESEARCH_REPOS_CONFIG=str(self.root / "repos.json"))
        self.log = (self.root / "serve.log").open("ab")
        try:
            self.process = spawn([self.binary, "serve", "--host", "127.0.0.1", "--port", str(port), "--no-tui", "--quiet", "true"],
                env, stdout=self.log, stderr=subprocess.STDOUT,
                creationflags=(subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == "nt" else 0,
                start_new_session=os.name != "nt")
            started = time.monotonic()
            while True:
                checkpoint()
                if self.process.poll() is not None:
                    raise RuntimeError("codesearch 启动失败，请查看专用 serve.log。")
                try:
                    status = self._request("/status")
                except OSError:
                    if time.monotonic() - started > 15:
                        raise TimeoutError("codesearch 启动超时。")
                    time.sleep(.05)
                    continue
                if status.get("ts_helper") or status.get("csharp_helper"):
                    raise ValueError("codesearch 意外启用符号分析辅助程序，已停止。")
                self.registered = registered
                return
        except BaseException:
            self.close()
            raise

    def search(self, repositories, query, limit, checkpoint):
        self.ensure(repositories, checkpoint)
        checkpoint()
        result = self._request("/search", {"query": query, "mode": "semantic", "group": "all", "limit": limit, "compact": True})
        checkpoint()
        if result.get("is_error") or "results" not in result:
            raise RuntimeError("codesearch 查询失败：" + str(result.get("content", result))[:2000])
        return result
