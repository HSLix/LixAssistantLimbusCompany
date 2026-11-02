"""开发知识库的受控只读访问；Git 同步仅更新对象与引用，不更新工作区。"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import subprocess
import tempfile
import time

from .process_lock import ProcessLock


MAX_BYTES = 2 * 1024 * 1024
MAX_OUTPUT = 4 * 1024 * 1024
TEXT_SUFFIXES = {".md", ".txt", ".rst", ".py", ".ts", ".js", ".tsx", ".jsx", ".json",
                 ".toml", ".yaml", ".yml", ".ini", ".cfg", ".csv", ".xml", ".html",
                 ".css", ".sql", ".sh", ".ps1", ".bat", ".c", ".h", ".cpp", ".cs",
                 ".go", ".rs", ".java", ".log", ".gitignore", ".gitattributes"}


def knowledge_root(data_root, *, create=False):
    """只允许数据目录中的固定真实目录；创建不覆盖已有内容。"""
    base = Path(data_root).resolve()
    root = base / "knowledge"
    if root.is_symlink() or root.is_junction() or not root.resolve().is_relative_to(base):
        raise ValueError("知识库目录不允许符号链接或越界。")
    if root.exists() and not root.is_dir():
        raise ValueError("知识库目录被普通文件占用。")
    if create:
        root.mkdir(parents=True, exist_ok=True)
    return root


def git_diagnostic(text):
    """Git 错误可能含 URL 认证信息，进入日志或模型前先移除。"""
    text = re.sub(r"(?i)([a-z][a-z0-9+.-]*://)[^\s/@]+(?::[^\s/@]*)?@", r"\1[REDACTED]@", text)
    return re.sub(r"(?i)([?&](?:token|access_token|auth|key|password|signature)=)[^\s&#]+",
                  r"\1[REDACTED]", text)


class KnowledgeLibrary:
    """每轮记录已尝试同步的仓库；读取结果明确区分工作区与提交内容。"""

    def __init__(self, data_root, checkpoint):
        self.root = Path(data_root).resolve() / "knowledge"
        self.checkpoint = checkpoint
        self.attempted = {}
        self.git = shutil.which("git")

    def begin_round(self):
        self.attempted.clear()
        self.git = shutil.which("git")

    def path(self, name="."):
        if not isinstance(name, str) or not name or "\\" in name or ":" in name:
            raise ValueError("知识库路径必须为相对路径。")
        parts = PurePosixPath(name).parts
        if PurePosixPath(name).is_absolute() or any(p in {"..", ".git"} for p in parts):
            raise ValueError("知识库路径越界或指向 Git 元数据。")
        current = knowledge_root(self.root.parent)
        for part in parts:
            current /= part
            if current.is_symlink() or current.is_junction():
                raise ValueError("知识库内容不允许符号链接。")
        if not current.resolve().is_relative_to(self.root.resolve()):
            raise ValueError("知识库路径越界。")
        return current

    def relative(self, path):
        return path.relative_to(self.root).as_posix()

    @staticmethod
    def page(items, offset, limit, expected=None, *, maximum=200):
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= maximum:
            raise ValueError(f"offset 必须非负，limit 必须为 1–{maximum}。")
        encoded = items.encode() if isinstance(items, str) else json.dumps(items, ensure_ascii=False).encode()
        identity = hashlib.sha256(encoded).hexdigest()
        if expected is not None and expected != identity:
            raise ValueError("资料或输出已变化，请从头读取。")
        end = min(offset + limit, len(items))
        return {"items": items[offset:end], "offset": offset, "total": len(items),
                "next_offset": end if end < len(items) else None, "truncated": end < len(items),
                "version": identity}

    @staticmethod
    def text_file(path):
        return path.suffix.lower() in TEXT_SUFFIXES or path.name.lower() in {
            "license", "licence", "readme", "dockerfile", "makefile", ".gitignore", ".gitattributes"}

    def list(self, path=".", offset=0, limit=100, version=None):
        directory = self.path(path)
        if not directory.exists() and directory == self.root:
            return {"path": path, "exists": False, **self.page([], offset, limit, version)}
        items = []
        for item in directory.iterdir():
            self.checkpoint()
            if item.name == ".git":
                continue
            # 不跟随资料中的链接；目录清单仍能说明其被跳过的原因。
            kind = "symlink_unavailable" if item.is_symlink() or item.is_junction() else "directory" if item.is_dir() else "file"
            items.append({"path": self.relative(item), "kind": kind})
            if len(items) > 10000:
                raise ValueError("目录条目过多，请按子目录查看。")
        return {"path": path, "exists": True, **self.page(sorted(items, key=lambda item: item['path']), offset, limit, version)}

    def repository(self, path):
        current = path if path.is_dir() else path.parent
        while current.is_relative_to(self.root):
            metadata = current / ".git"
            if metadata.exists() or metadata.is_symlink():
                if metadata.is_symlink() or metadata.is_junction() or not metadata.is_dir():
                    raise ValueError("首版仅支持知识库内含真实 .git 目录的普通仓库。")
                for index, item in enumerate(metadata.rglob("*")):
                    self.checkpoint()
                    if item.is_symlink() or item.is_junction() or index > 100000:
                        raise ValueError("Git 元数据含符号链接或过大，无法受控访问。")
                if any((metadata / name).exists() for name in ("commondir", "objects/info/alternates", "objects/info/http-alternates")):
                    raise ValueError("不允许仓库引用外部对象目录。")
                return current
            if current == self.root:
                break
            current = current.parent
        return None

    def _run(self, repo, args, *, timeout=10, binary=False):
        """有界捕获输出；超时或取消时终止整组子进程并等待回收。"""
        self.checkpoint()
        if not self.git:
            return {"ok": False, "unavailable": True, "error": "系统 Git 不可用，已跳过。"}
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        # 连接/认证仍使用开发者配置；拒绝交互提示及可改变仓库目标的环境覆盖。
        for key in ("GIT_SSH", "GIT_SSH_COMMAND", "GIT_SSH_VARIANT"):
            if key in os.environ:
                env[key] = os.environ[key]
        env.update(GIT_TERMINAL_PROMPT="0", GIT_ASKPASS="", SSH_ASKPASS="", SSH_ASKPASS_REQUIRE="never", GCM_INTERACTIVE="never",
                   GIT_OPTIONAL_LOCKS="0", GIT_CONFIG_NOSYSTEM="0", GIT_NO_LAZY_FETCH="1")
        if args[0] == "fetch" and not any(key in env for key in ("GIT_SSH", "GIT_SSH_COMMAND")):
            if not self._value(repo, ["config", "--get", "core.sshCommand"]):
                env["GIT_SSH_COMMAND"] = "ssh -oBatchMode=yes"
        command = [self.git, "--no-pager", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=" + os.devnull,
                   "-c", "credential.interactive=false", "-c", "protocol.ext.allow=never",
                   "-c", "protocol.file.allow=never", "-c", "gc.auto=0", "-C", str(repo),
                   "--git-dir=" + str(repo / ".git"), "--work-tree=" + str(repo)]
        if args[0] in {"diff", "status"}:
            # 工作区比较也可能触发 clean/process filter；只看原始资料，不运行转换器。
            filters = self._run(repo, ["config", "--null", "--name-only", "--get-regexp",
                                       r"^filter\..*\.(clean|smudge|process|required)$"])
            for key in filters.get("stdout", "").split("\0"):
                if key:
                    command += ["-c", key + ("=false" if key.endswith(".required") else "=")]
        command += args
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=out, stderr=err, env=env,
                                       creationflags=(subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == "nt" else 0,
                                       start_new_session=os.name != "nt")
            try:
                started = time.monotonic()
                while process.poll() is None:
                    self.checkpoint()
                    if time.monotonic() - started > timeout:
                        raise TimeoutError("Git 操作超时。")
                    if os.fstat(out.fileno()).st_size + os.fstat(err.fileno()).st_size > MAX_OUTPUT:
                        raise ValueError("Git 输出超过上限，请缩小路径或提交范围。")
                    time.sleep(.03)
                self.checkpoint()
                out.seek(0)
                err.seek(0)
                stdout, stderr = out.read(MAX_OUTPUT + 1), err.read(MAX_OUTPUT + 1)
                if len(stdout) + len(stderr) > MAX_OUTPUT:
                    raise ValueError("Git 输出超过上限，请缩小路径或提交范围。")
                return {"ok": process.returncode == 0,
                        **({"bytes": stdout} if binary else {"stdout": git_diagnostic(stdout.decode("utf-8", errors="replace"))}),
                        "error": git_diagnostic(stderr.decode("utf-8", errors="replace"))[:8000]}
            finally:
                if process.poll() is None:
                    if os.name == "nt":
                        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
                    else:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    process.wait(timeout=5)

    def _value(self, repo, args):
        result = self._run(repo, args)
        return result.get("stdout", "").strip() if result["ok"] else None

    def commit(self, repo, ref):
        if (not isinstance(ref, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./-]*", ref)
                or ".." in ref or len(ref) > 200):
            raise ValueError("引用必须为明确分支、标签或提交 ID。")
        value = self._value(repo, ["rev-parse", "--verify", "--end-of-options", ref + "^{commit}"])
        if value is None or not re.fullmatch(r"[0-9a-f]{40,64}", value):
            raise ValueError("指定提交不存在或 Git 不可用。")
        return value

    def synchronize(self, repo, *, explicit=False):
        key = self.relative(repo)
        if not explicit and key in self.attempted:
            return self.attempted[key]
        result = {"repository": key, "fetch": {"ok": False, "skipped": True}, "reference": None,
                  "before": None, "after": None, "checked_remote": False}
        self.attempted[key] = result
        if not self.git:
            result["fetch"]["reason"] = "系统 Git 不可用"
            logging.getLogger(__name__).info("知识库 Git 不可用，跳过同步：%s", key)
            return result
        try:
            with ProcessLock("knowledge:" + str(repo.resolve())):
                branch = self._value(repo, ["symbolic-ref", "--quiet", "HEAD"])
                upstream = self._value(repo, ["for-each-ref", "--format=%(upstream)", branch]) if branch else None
                if not upstream:
                    result["fetch"]["reason"] = "无 upstream 或 detached HEAD，未确定参考分支。"
                else:
                    remote = self._value(repo, ["for-each-ref", "--format=%(upstream:remotename)", branch])
                    result["reference"] = upstream
                    result["before"] = self._value(repo, ["rev-parse", "--verify", upstream + "^{commit}"])
                    if not remote or remote == "." or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", remote):
                        result["fetch"]["reason"] = "未确定可同步的远端。"
                    else:
                        url = self._value(repo, ["remote", "get-url", remote]) or ""
                        if not (re.match(r"^(?:https?|ssh|git)://", url) or re.match(r"^[\w.-]+@[\w.-]+:[^\s]+$", url)):
                            result["fetch"]["reason"] = "远端连接协议不受支持。"
                        else:
                            try:
                                result["fetch"] = self._run(repo, ["fetch", "--no-recurse-submodules", "--no-tags",
                                                                  "--no-auto-maintenance", remote], timeout=30)
                            except (TimeoutError, OSError, ValueError) as error:
                                result["fetch"] = {"ok": False, "error": git_diagnostic(str(error))}
                            result["checked_remote"] = result["fetch"]["ok"]
                    result["after"] = self._value(repo, ["rev-parse", "--verify", upstream + "^{commit}"])
                result["head"] = self._value(repo, ["rev-parse", "--verify", "HEAD"])
                result["status"] = self._run(repo, ["status", "--porcelain=v1", "--untracked-files=normal"])
                status = result["status"]
                if status["ok"]:
                    entries = status.pop("stdout").splitlines()
                    status.update(dirty=bool(entries), entry_count=len(entries),
                                  untracked_count=sum(line.startswith("??") for line in entries))
                fetch = result["fetch"]
                if "stdout" in fetch:
                    fetch["output_truncated"] = len(fetch["stdout"]) > 2000
                    fetch["stdout"] = fetch["stdout"][:2000]
                result["changed"] = result["before"] != result["after"] if result["before"] and result["after"] else None
                if result["changed"]:
                    result["range"] = {"before": result["before"], "after": result["after"],
                                       "hint": "使用 knowledge_git diff 的 before / after 查看完整区间。"}
        except (OSError, TimeoutError, ValueError) as error:
            result["error"] = git_diagnostic(str(error))
        return result

    def read(self, path, offset=0, limit=8000, version=None):
        target = self.path(path)
        repo = self.repository(target)
        sync = self.synchronize(repo) if repo else None
        target = self.path(path)
        if not target.is_file() or target.stat().st_size > MAX_BYTES:
            raise ValueError("文件不存在或超过 2 MiB；请先拆分资料。")
        with target.open("rb") as stream:
            content = stream.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            raise ValueError("文件超过 2 MiB；请先拆分资料。")
        metadata = {"path": self.relative(target), "source": "worktree" if repo else "file",
                    "sha256": hashlib.sha256(content).hexdigest(), "sync": sync}
        return self.view(content, target, metadata, offset, limit, version)

    def view(self, content, target, metadata, offset, limit, version):
        """工作区与提交字节共用格式检查；图片原样返回，不解释为替换字符文本。"""
        if len(content) > MAX_BYTES:
            raise ValueError("文件超过 2 MiB；请先拆分资料。")
        if self.text_file(target):
            try:
                text = content.decode("utf-8-sig")
            except UnicodeError as error:
                raise ValueError("不是可读取的 UTF-8 文本。") from error
            if "\0" in text:
                raise ValueError("不是可读取的 UTF-8 文本。")
            page = self.page(text, offset, limit, version, maximum=16000)
            return {**metadata, "text": page.pop("items"), **page}, None
        from io import BytesIO
        from PIL import Image, UnidentifiedImageError
        try:
            with Image.open(BytesIO(content)) as image:
                if not image.format or image.format not in Image.MIME:
                    raise ValueError("图片格式没有可用的 MIME 类型。")
                mime, extension = Image.MIME.get(image.format), image.format.lower()
                image.verify()
            if offset != 0 or version is not None and version != metadata["sha256"]:
                raise ValueError("图片不支持分页，或图片内容已变化。")
            return {**metadata, "version": metadata["sha256"], "mime_type": mime, "extension": extension}, content
        except (UnidentifiedImageError, OSError):
            return {**metadata, "unsupported": True, "message": "暂不支持解析此格式，请转换为 UTF-8 文本或图片。"}, None

    def search(self, query, path=".", offset=0, limit=50, version=None):
        """字面文本检索，不建立索引；扫描上限与跳过项如实返回。"""
        if not isinstance(query, str) or not query or len(query) > 500:
            raise ValueError("query 必须为 1–500 字符的文本。")
        target = self.path(path)
        hits, skipped, syncs, identities = [], [], {}, []
        total_bytes = 0
        complete = True
        if not target.is_dir():
            raise ValueError("检索路径必须为已有目录。")
        def unreadable(error):
            skipped.append(self.relative(Path(error.filename)))
        for directory, dirs, files in os.walk(target, followlinks=False, onerror=unreadable):
            self.checkpoint()
            dirs[:] = sorted(d for d in dirs if d != ".git" and not (Path(directory) / d).is_symlink()
                             and not (Path(directory) / d).is_junction())
            for name in sorted(files):
                self.checkpoint()
                file = Path(directory) / name
                if name == ".git" or file.is_symlink() or not file.is_file() or not self.text_file(file):
                    continue
                file = self.path(self.relative(file))
                if len(identities) + len(skipped) >= 5000 or total_bytes > 16 * MAX_BYTES:
                    complete = False
                    break
                repo = self.repository(file)
                if repo:
                    syncs[self.relative(repo)] = self.synchronize(repo)
                if file.stat().st_size > MAX_BYTES:
                    skipped.append(self.relative(file))
                    continue
                with file.open("rb") as stream:
                    content = stream.read(MAX_BYTES + 1)
                if len(content) > MAX_BYTES:
                    skipped.append(self.relative(file))
                    continue
                total_bytes += len(content)
                identities.append((self.relative(file), hashlib.sha256(content).hexdigest()))
                try:
                    text = content.decode("utf-8-sig")
                    if "\0" in text:
                        raise UnicodeError()
                except UnicodeError:
                    skipped.append(self.relative(file))
                    continue
                for line, value in enumerate(text.splitlines(), 1):
                    if query.casefold() in value.casefold():
                        location = value.casefold().find(query.casefold())
                        start = max(0, location - 150)
                        hits.append({"path": self.relative(file), "line": line, "text": value[:600],
                                     "excerpt": value[start:start + 600],
                                     "line_truncated": len(value) > 600, "sha256": identities[-1][1]})
                        if len(hits) >= 10000:
                            complete = False
                            break
                if not complete:
                    break
            if not complete:
                break
        snapshot = hashlib.sha256(json.dumps(identities).encode()).hexdigest()
        if version is not None and version != snapshot:
            raise ValueError("检索资料已变化，请从头检索。")
        page = self.page(hits, offset, limit)
        return {**page, "version": snapshot, "source": "worktree", "complete_scan": complete and not skipped,
                "skipped": skipped[:100], "skipped_truncated": len(skipped) > 100, "sync": list(syncs.values())}

    def git_operation(self, repository, operation, ref="HEAD", before=None, after=None, path=None,
                      offset=0, limit=8000, version=None, history_offset=0):
        """仅提供结构化的 fetch / show / log / diff，引用解析后只传提交 ID。"""
        repo = self.path(repository)
        if self.repository(repo) != repo:
            raise ValueError("repository 必须指向知识库中的普通 Git 仓库根目录。")
        if operation not in {"fetch", "show", "log", "diff"}:
            raise ValueError("仅允许 fetch / show / log / diff。")
        sync = self.synchronize(repo, explicit=operation == "fetch")
        if operation == "fetch" or not self.git:
            return {"sync": sync, "unavailable": not bool(self.git)}
        selected = None
        if path is not None:
            if not isinstance(path, str) or PurePosixPath(path).is_absolute():
                raise ValueError("Git 文件路径必须相对于仓库。")
            selected = self.path(self.relative(repo) + "/" + path).relative_to(repo).as_posix()
        revision = self.commit(repo, ref)
        args = [operation, "--no-ext-diff", "--no-textconv", "--no-color"]
        next_history_offset = None
        if operation == "log":
            if type(history_offset) is not int or not 0 <= history_offset <= 1000000:
                raise ValueError("history_offset 必须为 0–1000000。")
            args += ["--max-count=200", f"--skip={history_offset}", "--format=fuller", revision]
            commits = self._run(repo, ["rev-list", "--max-count=201", f"--skip={history_offset}", revision])
            if not commits["ok"]:
                raise ValueError(commits.get("error") or "无法读取提交列表。")
            if len(commits["stdout"].splitlines()) > 200:
                next_history_offset = history_offset + 200
        elif operation == "show":
            if selected:
                args = ["show", revision + ":" + selected]
            else:
                args += ["--format=fuller", revision]
        else:
            if (before is None) != (after is None):
                raise ValueError("提交区间必须同时提供 before 和 after。")
            args += ["--ignore-submodules=all"]
            args += [self.commit(repo, before), self.commit(repo, after)] if before else [revision]
        if selected and operation != "show":
            args += ["--", selected]
        if selected and operation == "show":
            result = self._run(repo, args, binary=True)
            if not result["ok"]:
                raise ValueError(result.get("error") or "提交内容读取失败。")
            content = result["bytes"]
            metadata = {"repository": repository, "path": selected, "source": "commit", "ref_commit": revision,
                        "sha256": hashlib.sha256(content).hexdigest(), "sync": sync}
            details, image = self.view(content, Path(selected), metadata, offset, limit, version)
            if image is not None:
                details["_image"] = image
            return details
        result = self._run(repo, args)
        if not result["ok"]:
            raise ValueError(result.get("error") or "Git 操作失败。")
        page = self.page(result["stdout"], offset, limit, version, maximum=16000)
        return {"repository": repository, "operation": operation, "ref_commit": revision,
                "source": "worktree_diff" if operation == "diff" and before is None else "commit",
                "before_commit": self.commit(repo, before) if before else None,
                "after_commit": self.commit(repo, after) if after else None,
                "text": page.pop("items"), **page, "sync": sync,
                "history_limit": 200 if operation == "log" else None,
                "next_history_offset": next_history_offset}
