"""验证真实 pi 复用、codesearch 离线读取与双版本切换；结果保留在 .generated。

项目根目录运行：QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --run-agent-tests -q -s tests/experiments/test_external_search_validation.py
仅使用本机 HTTP 替身、临时参考仓库与本地嵌入模型，不调用付费模型或操作游戏。
"""

import asyncio
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
from types import SimpleNamespace
import urllib.request

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))
from agent_test_server import agent_server
from lalc.work_files import create_work_directory
from lalc.pi_probe import PiExited, configured_pi, rpc_session

pytestmark = pytest.mark.agent
EXPERIMENT = Path(os.environ.get("LALC_CODESEARCH_VALIDATION_RESOURCES",
                               ROOT / ".generated/external-search-validation/resources"))


@pytest.fixture
def retained():
    """每次运行建立独立目录，不自动清理验证证据。"""
    base = ROOT / ".generated/external-search-validation"
    base.mkdir(parents=True, exist_ok=True)
    folder = Path(create_work_directory(prefix="run-", dir=base))
    print(f"RETAINED={folder}", flush=True)
    return folder


def save(folder, name, value):
    (folder / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


async def until(event, predicate, rows):
    """有界等待协议事件；错误事件与超时均保留给测试报告。"""
    while True:
        item = await asyncio.wait_for(event(), timeout=30)
        rows.append(item)
        if predicate(item):
            return item


def test_current_extension_new_session_resets_budget_but_keeps_environment(agent_server, retained):
    """实测 new_session 重载扩展、重置额度，但宿主改 env 不会改变子进程根目录。"""
    address, state, _ = agent_server
    state["respond"] = lambda _: ({"role": "assistant", "content": "done"}, "stop")
    source = retained / "source"
    source.mkdir()
    options = SimpleNamespace(pi="pi", model="gemma4-test", base_url=address, max_requests=1)
    rows = []

    async def run():
        with configured_pi(options, source, "lalc-no-key", "validation", require_image=False) as (command, env, cwd, _):
            async with rpc_session(command, env, cwd, rows.append) as (send, event):
                await until(event, lambda e: e.get("type") == "lalc_ready", rows)
                await send({"type": "prompt", "message": "round-one"})
                await until(event, lambda e: e.get("type") == "agent_settled", rows)
                other = retained / "other-root"
                other.mkdir()
                env["LALC_PI_SOURCE_ROOT"] = str(other)
                await send({"type": "new_session", "id": "reset"})
                await until(event, lambda e: e.get("id") == "reset" and e.get("type") == "response", rows)
                await send({"type": "prompt", "message": "round-two"})
                await until(event, lambda e: e.get("type") == "agent_settled", rows)
    try:
        asyncio.run(run())
        assert len(state["calls"]) == 2
        ready = [e for e in rows if e.get("type") == "lalc_ready"]
        assert len(ready) >= 2 and all(e["root"] == str(source) for e in ready)
    finally:
        save(retained, "current-pi-events.json", rows)
        save(retained, "current-pi-http.json", state["calls"])


def test_pi_reuse_reconfigures_round_and_recovers_after_abort(agent_server, retained):
    """同进程切换根目录／历史／工具／模型／额度，并在 abort 后开始新轮。"""
    address, state, _ = agent_server
    rows = []
    replies = iter([
        ({"role": "assistant", "content": "round-a-done"}, "stop"),
        ({"role": "assistant", "tool_calls": [{"index": 0, "id": "read-b", "type": "function",
          "function": {"name": "probe_read", "arguments": '{"path":"sample.txt"}'}}]}, "tool_calls"),
        ({"role": "assistant", "content": "round-b-done"}, "stop"),
    ])
    state["respond"] = lambda _: next(replies)
    options = SimpleNamespace(pi="pi", model="gemma4-test", base_url=address, max_requests=20)
    source = retained / "source"
    source.mkdir()
    for name in ("a", "b"):
        (source / name).mkdir()
        (source / name / "sample.txt").write_text("CONTENT_" + name.upper(), encoding="utf-8")

    async def run():
        with configured_pi(options, source, "lalc-no-key", "startup-system", require_image=False) as (command, env, cwd, _):
            command = list(command)
            command[command.index("--extension") + 1] = str(Path(__file__).with_name("reusable_pi_extension.ts"))
            command[command.index("--provider") + 1] = "validation"
            command[command.index("--model") + 1] = "model-a"
            command[command.index("--tools") + 1] = "probe_read,probe_write"
            async with rpc_session(command, env, cwd, rows.append) as (send, event):
                first = await until(event, lambda e: e.get("type") == "validation_ready", rows)

                async def begin(number, tools, history=()):
                    path = retained / f"round-{number}.json"
                    config = dict(number=number, root=str(source / ("a" if number == 1 else "b")),
                                  tools=tools, history=list(history), limit=1 if number == 1 else 2,
                                  model="model-a" if number == 1 else "model-b", system=f"SYSTEM_{number}")
                    save(retained, path.name, config)
                    await send({"type": "prompt", "message": "/validation_begin " + str(path)})
                    ready = await until(event, lambda e: e.get("type") == "validation_round_ready" and e["round"] == number, rows)
                    assert ready["pid"] == first["pid"] and ready["requests"] == 0
                    return ready

                await begin(1, ["probe_read", "probe_write"])
                await send({"type": "prompt", "message": "PROMPT_A_PRIVATE"})
                await until(event, lambda e: e.get("type") == "agent_settled", rows)
                await begin(2, ["probe_read"], [{"role": "user", "timestamp": 1,
                                               "content": [{"type": "text", "text": "HOST_HISTORY_B"}]}])
                await send({"type": "prompt", "message": "PROMPT_B"})
                await until(event, lambda e: e.get("type") == "agent_settled", rows)
                assert len(state["calls"]) == 3
                second = json.dumps(state["calls"][1:])
                assert "HOST_HISTORY_B" in second and "PROMPT_A_PRIVATE" not in second
                assert "SYSTEM_2" in second and "SYSTEM_1" not in second
                assert "CONTENT_B" in json.dumps(state["calls"][2]) and "CONTENT_A" not in second
                for body in state["calls"][1:]:
                    assert body["model"] == "model-b"
                    assert {t["function"]["name"] for t in body["tools"]} == {"probe_read"}

                await begin(3, ["probe_read"])
                state["started"].clear()
                state["release"].clear()
                state["block"] = True
                state["respond"] = lambda _: ({"role": "assistant", "content": "post-abort-done"}, "stop")
                await send({"type": "prompt", "message": "CANCEL_THIS"})
                assert await asyncio.to_thread(state["started"].wait, 5)
                await send({"type": "abort", "id": "abort"})
                await until(event, lambda e: e.get("id") == "abort" and e.get("type") == "response", rows)
                state["release"].set()
                state["block"] = False
                await begin(4, ["probe_read"])
                await send({"type": "prompt", "message": "AFTER_ABORT"})
                await until(event, lambda e: e.get("type") == "agent_settled", rows)
                assert "CANCEL_THIS" not in json.dumps(state["calls"][-1])
                pids = {e["pid"] for e in rows if e.get("type") == "validation_round_ready"}
                assert pids == {first["pid"]}
                await begin(5, ["probe_read"])
                state["started"].clear()
                state["release"].clear()
                state["block"] = True
                await send({"type": "prompt", "message": "DO_NOT_REPLAY_AFTER_CRASH"})
                assert await asyncio.to_thread(state["started"].wait, 5)
                calls_at_crash = len(state["calls"])
                await send({"type": "prompt", "message": "/validation_crash"})
                with pytest.raises(PiExited):
                    await until(event, lambda _e: False, rows)
            state["release"].set()
            state["block"] = False
            async with rpc_session(command, env, cwd, rows.append) as (send, event):
                replacement = await until(event, lambda e: e.get("type") == "validation_ready", rows)
                assert replacement["pid"] != first["pid"]
                save(retained, "round-6.json", dict(number=6, root=str(source / "b"), tools=["probe_read"],
                                                   history=[], limit=1, model="model-b", system="SYSTEM_6"))
                await send({"type": "prompt", "message": "/validation_begin " + str(retained / "round-6.json")})
                await until(event, lambda e: e.get("type") == "validation_round_ready" and e["round"] == 6, rows)
                assert len(state["calls"]) == calls_at_crash
                await send({"type": "prompt", "message": "NEW_ROUND_AFTER_CRASH"})
                await until(event, lambda e: e.get("type") == "agent_settled", rows)
                assert len(state["calls"]) == calls_at_crash + 1
                assert "DO_NOT_REPLAY_AFTER_CRASH" not in json.dumps(state["calls"][-1])
    try:
        asyncio.run(run())
    finally:
        state["release"].set()
        save(retained, "reused-pi-events.json", rows)
        save(retained, "reused-pi-http.json", state["calls"])


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.PIPE, text=True).strip()


def http(base, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


@contextmanager
def serve(binary, env, folder):
    """只回收本测试拥有的服务，保留配置、索引与进程日志。"""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    with (folder / f"serve-{time.time_ns()}.log").open("wb") as log:
        process = subprocess.Popen([str(binary), "serve", "--host", "127.0.0.1", "--port", str(port),
                                    "--no-tui", "--quiet", "true"], env=env, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            deadline = time.monotonic() + 30
            while True:
                try:
                    status = http(base, "/status")
                    break
                except OSError:
                    if process.poll() is not None or time.monotonic() > deadline:
                        raise
                    time.sleep(.1)
            yield base, process, status
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGINT)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)


def test_codesearch_offline_readonly_generations_and_failed_publication(retained):
    """真实索引验证 A 保留、B 发布、读块来源与只读服务拒绝更新。"""
    binary = EXPERIMENT / "bin/codesearch"
    if not binary.exists():
        pytest.skip("显式准备 codesearch v1.7.9 实验资源后运行")
    state = retained / "state"
    state.mkdir()
    shutil.copytree(EXPERIMENT / "state/models", state / "models", symlinks=True)
    env = dict(os.environ, CODESEARCH_HOME=str(state), CODESEARCH_EMBED_THREADS="2",
               HF_ENDPOINT="http://127.0.0.1:9", HF_HUB_OFFLINE="1", CSHARP_PREWARM_ENABLED="false")
    repo = retained / "reference"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.name", "Validation")
    git(repo, "config", "user.email", "validation@example.invalid")
    source = repo / "sample.py"
    source.write_text('def acquire_resource():\n    """Acquire resource using version ALPHA_ONLY."""\n    return "ALPHA_ONLY"\n', encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "A")
    a = git(repo, "rev-parse", "HEAD")
    source.write_text('def acquire_resource():\n    """Acquire resource using version BRAVO_ONLY."""\n    return "BRAVO_ONLY"\n', encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "B")
    b = git(repo, "rev-parse", "HEAD")
    versions = {}
    for name, commit in (("a", a), ("b", b)):
        target = retained / ("version-" + name)
        subprocess.run(["git", "clone", "--quiet", "--no-hardlinks", str(repo), str(target)], check=True)
        git(target, "reset", "--hard", commit)
        started = time.monotonic()
        indexed = subprocess.run([str(binary), "index", "add", str(target), "--local", "--log-file",
                                  str(retained / f"index-{name}.log")], env=env, capture_output=True, text=True, timeout=90)
        save(retained, f"index-{name}-result.json", dict(returncode=indexed.returncode, stdout=indexed.stdout,
                                                       stderr=indexed.stderr, seconds=time.monotonic() - started))
        assert indexed.returncode == 0, indexed.stderr
        versions[name] = target

    active = retained / "active.json"

    def publish(name):
        candidate = versions[name]
        assert (candidate / ".codesearch.db/metadata.json").exists()
        next_file = retained / "active-next.json"
        save(retained, next_file.name, {"generation": name, "root": str(candidate)})
        os.replace(next_file, active)

    publish("a")
    failed_b = retained / "failed-b"
    failed_b.mkdir()
    (failed_b / "sample.py").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    # 模拟 B 构建失败／构建中宿主退出：不发布新指针，旧文件和旧索引不被修改。
    assert json.loads(active.read_text(encoding="utf-8"))["generation"] == "a"
    assert "ALPHA_ONLY" in (versions["a"] / "sample.py").read_text(encoding="utf-8")
    records = []
    db_before = {}
    for name in ("a", "b"):
        if name == "b":
            publish("b")
        selected = Path(json.loads(active.read_text(encoding="utf-8"))["root"])
        config = {"repos": {"reference": str(selected)}, "groups": {}, "repo_read_only": {"reference": True}}
        save(state, "repos.json", config)
        db = selected / ".codesearch.db/data.mdb"
        db_before[name] = hashlib.sha256(db.read_bytes()).hexdigest()
        with serve(binary, env, retained) as (base, process, initial):
            result = http(base, "/search", {"query": "acquire resource", "mode": "semantic", "group": "all", "limit": 3})
            assert result.get("results"), result
            hit = result["results"][0]
            chunk = http(base, f'/chunk/{hit["chunk_id"]}?project=reference')
            expected = "ALPHA_ONLY" if name == "a" else "BRAVO_ONLY"
            other = "BRAVO_ONLY" if name == "a" else "ALPHA_ONLY"
            assert expected in chunk["content"] and other not in chunk["content"], chunk
            assert expected in (selected / "sample.py").read_text(encoding="utf-8")
            try:
                reindex = http(base, "/repos/reference/reindex", {})
            except urllib.error.HTTPError as error:
                reindex = {"http_status": error.code, "body": error.read().decode()}
            assert "read_only" in json.dumps(reindex) or "read-only" in json.dumps(reindex), reindex
            records.append(dict(generation=name, pid=process.pid, initial=initial, result=result, chunk=chunk,
                                reindex=reindex, commit=git(selected, "rev-parse", "HEAD")))
        assert hashlib.sha256(db.read_bytes()).hexdigest() == db_before[name]
    assert json.loads(active.read_text(encoding="utf-8"))["generation"] == "b"
    save(retained, "generation-results.json", records)
    save(retained, "summary.json", {"a": a, "b": b, "failure_injection": "unpublished B directory, no actual index corruption",
                                    "offline_endpoint": env["HF_ENDPOINT"], "disk_index_unchanged": True})


def test_codesearch_readonly_does_not_disable_background_symbol_helper(retained):
    """探测只读配置是否仍启动 TS 辅助程序；替身只写标记，不安装或分析项目。"""
    binary = EXPERIMENT / "bin/codesearch"
    if not binary.exists():
        pytest.skip("显式准备 codesearch 实验资源后运行")
    reference = retained / "reference"
    shutil.copytree(EXPERIMENT / "corpus/runtime-reference", reference)
    (reference / "tsconfig.json").write_text('{"compilerOptions":{},"include":["sample.ts"]}', encoding="utf-8")
    (reference / "sample.ts").write_text('export const value = "sentinel";', encoding="utf-8")
    marker = retained / "helper-invoked.json"
    helper = retained / "fake-scip-typescript"
    helper.write_text(f'#!{sys.executable}\nimport json,sys\nfrom pathlib import Path\nPath({str(marker)!r}).write_text(json.dumps(sys.argv), encoding="utf-8")\nraise SystemExit(3)\n', encoding="utf-8")
    helper.chmod(0o755)
    state = retained / "state"
    state.mkdir()
    save(state, "repos.json", {"repos": {"reference": str(reference)}, "groups": {},
                               "repo_read_only": {"reference": True}})
    env = dict(os.environ, CODESEARCH_HOME=str(state), CODESEARCH_SCIP_TYPESCRIPT=str(helper),
               HF_ENDPOINT="http://127.0.0.1:9", HF_HUB_OFFLINE="1", CSHARP_PREWARM_ENABLED="false")
    with serve(binary, env, retained) as (base, process, status):
        deadline = time.monotonic() + 8
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(.1)
        observed = {"readonly": True, "helper_invoked": marker.exists(), "pid": process.pid,
                    "status": http(base, "/status")}
        save(retained, "helper-observation.json", observed)
        assert marker.exists(), "本探针用于固定上游只读模式仍启动符号辅助程序的实际行为"

    # 验证最小候选防护：服务仅可发现系统 Git，不继承用户的 npm／SCIP 工具链。
    restricted = dict(env, PATH="/usr/bin:/bin")
    restricted.pop("CODESEARCH_SCIP_TYPESCRIPT", None)
    restricted.pop("CODESEARCH_SCIP_CSHARP", None)
    previous = marker.read_bytes()
    status_file = retained / "restricted-helper-status.json"
    with serve(binary, restricted, retained) as (base, _process, _status):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            status = http(base, "/status")
            if status.get("ts_helper") is False:
                break
            time.sleep(.1)
        save(retained, status_file.name, status)
        assert status["ts_helper"] is False and status["csharp_helper"] is False, status
        assert marker.read_bytes() == previous


def test_codesearch_chunk_staleness_is_not_a_hash_check(retained):
    """保留旧 mtime 替换源码，验证 get_chunk 的时间戳提示不能替代内容哈希。"""
    binary = EXPERIMENT / "bin/codesearch"
    if not binary.exists():
        pytest.skip("显式准备 codesearch 实验资源后运行")
    reference = retained / "reference"
    shutil.copytree(EXPERIMENT / "corpus/runtime-reference", reference)
    state = retained / "state"
    state.mkdir()
    shutil.copytree(EXPERIMENT / "state/models", state / "models", symlinks=True)
    save(state, "repos.json", {"repos": {"reference": str(reference)}, "groups": {},
                               "repo_read_only": {"reference": True}})
    env = dict(os.environ, CODESEARCH_HOME=str(state), HF_ENDPOINT="http://127.0.0.1:9", HF_HUB_OFFLINE="1")
    with serve(binary, env, retained) as (base, _process, _status):
        result = http(base, "/search", {"query": "git_diagnostic", "mode": "semantic", "project": "reference", "limit": 1})
        save(retained, "staleness-search.json", result)
        assert result.get("results"), result
        hit = result["results"][0]
        assert hit["path"].endswith("knowledge.py"), hit
        chunk_id = hit["chunk_id"]
        before = http(base, f"/chunk/{chunk_id}?project=reference")
        assert before.get("content"), before
        path = reference / "knowledge.py"
        old = path.stat()
        path.write_text('def git_diagnostic(text):\n    return "CHANGED_AFTER_INDEX"\n', encoding="utf-8")
        os.utime(path, ns=(old.st_atime_ns, old.st_mtime_ns))
        after = http(base, f"/chunk/{chunk_id}?project=reference")
        save(retained, "staleness-results.json", {"before": before, "after": after,
                                                  "disk": path.read_text(encoding="utf-8"), "mtime_preserved": True})
        assert "CHANGED_AFTER_INDEX" not in after["content"]
        assert not after.get("note"), after


def test_failed_and_killed_index_leave_retained_a_usable(retained):
    """真实缺模型失败与强杀构建后，重新打开 A 的文件和索引仍可查询。"""
    binary = EXPERIMENT / "bin/codesearch"
    if not binary.exists():
        pytest.skip("显式准备 codesearch 实验资源后运行")
    active = retained / "active-a"
    shutil.copytree(EXPERIMENT / "corpus/runtime-reference", active)
    before_file = hashlib.sha256((active / "knowledge.py").read_bytes()).hexdigest()
    before_db = hashlib.sha256((active / ".codesearch.db/data.mdb").read_bytes()).hexdigest()
    save(retained, "active.json", {"root": str(active), "version": "A"})
    broken = retained / "candidate-b-error"
    broken.mkdir()
    git(broken, "init", "-q")
    (broken / "sample.py").write_text('def b():\n    return "B"\n', encoding="utf-8")
    empty_state = retained / "empty-state"
    empty_state.mkdir()
    env = dict(os.environ, CODESEARCH_HOME=str(empty_state), HF_ENDPOINT="http://127.0.0.1:9", HF_HUB_OFFLINE="1")
    failed = subprocess.run([str(binary), "index", "add", str(broken), "--local", "--log-file",
                             str(retained / "failed-build.log")], env=env, capture_output=True, text=True, timeout=20)
    save(retained, "actual-failure.json", {"returncode": failed.returncode, "stdout": failed.stdout, "stderr": failed.stderr})
    assert failed.returncode != 0
    assert f"Database: {broken / '.codesearch.db'}" in failed.stdout
    assert "Found 1 indexable files" in failed.stdout
    state = retained / "state"
    state.mkdir()
    shutil.copytree(EXPERIMENT / "state/models", state / "models", symlinks=True)
    env.update(CODESEARCH_HOME=str(state), CODESEARCH_EMBED_THREADS="2")
    interrupted = retained / "candidate-b-killed"
    interrupted.mkdir()
    git(interrupted, "init", "-q")
    (interrupted / "sample.py").write_text("\n".join(
        f'def method_{n}(value):\n    """Process item number {n}."""\n    return value + {n}\n' for n in range(2000)), encoding="utf-8")
    stdout_path = retained / "killed-index-stdout.log"
    with stdout_path.open("wb") as output:
        process = subprocess.Popen([str(binary), "index", "add", str(interrupted), "--local", "--log-file",
                                    str(retained / "killed-build.log")], env=env, stdout=output,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            deadline = time.monotonic() + 10
            while "Phase 2" not in stdout_path.read_text(encoding="utf-8"):
                assert process.poll() is None, stdout_path.read_text(encoding="utf-8")
                assert time.monotonic() < deadline
                time.sleep(.01)
            assert f"Database: {interrupted / '.codesearch.db'}" in stdout_path.read_text(encoding="utf-8")
            assert process.poll() is None
            os.killpg(process.pid, signal.SIGKILL)
            assert process.wait(timeout=5) != 0
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
    assert json.loads((retained / "active.json").read_text(encoding="utf-8"))["version"] == "A"
    assert hashlib.sha256((active / "knowledge.py").read_bytes()).hexdigest() == before_file
    assert hashlib.sha256((active / ".codesearch.db/data.mdb").read_bytes()).hexdigest() == before_db
    save(state, "repos.json", {"repos": {"reference": str(active)}, "groups": {}, "repo_read_only": {"reference": True}})
    with serve(binary, env, retained) as (base, _process, _status):
        result = http(base, "/search", {"query": "git_diagnostic", "mode": "semantic", "project": "reference", "limit": 1})
        assert result.get("results"), result
        chunk = http(base, f'/chunk/{result["results"][0]["chunk_id"]}?project=reference')
        assert "git_diagnostic" in chunk["content"], chunk
        save(retained, "a-after-failure-and-kill.json", {"result": result, "chunk": chunk,
                                                       "file_sha256": before_file, "index_sha256": before_db})
