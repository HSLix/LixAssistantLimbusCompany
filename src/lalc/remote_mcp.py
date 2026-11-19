"""远程开发宿主：独立授权、持久草稿和断线后可查询的串行操作。"""

from __future__ import annotations

import base64
from collections import deque
from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import threading
import uuid

from .application import StartError
from .agent_log import read_json
from .developer import DeveloperHost, candidate_files
from .process_lock import ProcessLock
from .repair_tools import RepairTools
from .runtime import atomic_write_json, staging_directory

# 独立列举，pi 权限变化不会自动扩张远程权限。
MCP_TOOLS = (
    "read", "edit", "asset_tree", "asset_directory", "asset_images", "action_contracts",
    "game_screenshot", "preview_crop", "crop_asset", "remove_asset", "restore_asset",
    "add_component", "add_recovery_rule", "delete_component", "validate_and_publish", "trial_run",
    "list_runs", "read_run_log", "search_run_logs", "list_manifests", "read_manifest", "read_manifest_source", "search_manifest_source",
    "list_game_versions", "search_agent_sessions", "read_agent_session",
    "knowledge_list", "knowledge_read", "knowledge_search_literal", "knowledge_search_hybrid", "knowledge_git",
    "request_feedback", "page_list", "page_read", "page_create", "page_update", "page_resource",
    "page_preview", "page_set_enabled",
)
READ_TOOLS = frozenset(("read", "asset_tree", "asset_directory", "asset_images", "action_contracts",
    "list_runs", "read_run_log", "search_run_logs", "list_manifests", "read_manifest", "read_manifest_source", "search_manifest_source",
    "list_game_versions", "search_agent_sessions", "read_agent_session", "page_list", "page_read", "list_skills"))


def now():
    return datetime.now(UTC).isoformat()


def object_json(path):
    """拒绝链接及非对象元数据，损坏时不以空白数据覆盖旧状态。"""
    if path.is_symlink():
        raise ValueError("MCP 元数据不允许符号链接。")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("MCP 元数据损坏。")
    return value


class RemoteWorkbench:
    """应用级远程工作台；网络连接不拥有任务生命周期，控制凭据只保存在内存。"""

    LOCAL_READS = frozenset({"OCR", "Template Match", "Feature Match", "Candidate Diff"})
    LOCAL_ASSISTS = frozenset({"Capture 截图", "Capture 保存", "Capture"})

    def __init__(self, service):
        self.service = service
        self.root = service.data_root / "remote-mcp"
        from .page_packages import real_directory
        real_directory(self.root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "workspace"
        self.entry, self.mode = "mcp", "Construct"
        self.host = DeveloperHost(service, self.path / "candidate")
        self.host.session = self
        self.config_path = self.root / "config.json"
        self.config = object_json(self.config_path) if self.config_path.exists() else {"port": 8765, "url": ""}
        self.owner = None
        self.authorized = False
        self.enabled = False
        self.game_lock = None
        self.control_lock = None
        self.control_hash = None
        self._context = threading.local()
        self.active = None
        self._readers = 0
        self.pending_request = None
        self.on_feedback = self.on_page_preview = None
        self.previews = {}
        self.allowed = frozenset(MCP_TOOLS)
        self.recent = deque(maxlen=20)
        self._jobs = set()
        self._server = None
        self._server_thread = None
        self._skills = None
        self._revoking = False
        self.failure = None
        self.operations = self.root / "operations"
        if self.operations.is_symlink():
            raise ValueError("MCP 操作目录不允许符号链接。")
        self.operations.mkdir(exist_ok=True)
        self._recover_operations()
        audit = self.root / "events.jsonl"
        if audit.is_symlink():
            raise ValueError("MCP 审计日志不允许符号链接。")
        if audit.exists():
            with audit.open(encoding="utf-8") as stream:
                for line in deque(stream, maxlen=20):
                    try:
                        row = json.loads(line)
                        if not isinstance(row, dict):
                            raise ValueError("Invalid audit row")
                    except ValueError:
                        self.failure = "MCP 审计日志存在损坏记录，原始内容已保留。"
                    else:
                        self.recent.append(row)

    @property
    def in_operation(self):
        return bool(getattr(self._context, "identity", None))

    @property
    def operation_id(self):
        return getattr(self._context, "identity", None)

    def check(self):
        """为复用页面服务校验独立工作区，不伪造 pi Session 或对话历史。"""
        if not self.path.exists():
            raise ValueError("MCP 工作台尚未初始化，请在开发者面板选择来源版本。")
        if self.path.is_symlink() or self.host.candidate.is_symlink():
            raise ValueError("MCP 工作台不允许符号链接。")
        value = object_json(self.path / "workspace.json")
        if value.get("version") != 1 or not isinstance(value.get("source_manifest_id"), str):
            raise ValueError("MCP 工作台元数据无效。")
        from .page_packages import real_directory
        real_directory(self.host.candidate)
        return value

    def _changed(self):
        with self.service._condition:
            self.service._changed_locked()

    def audit(self, event, **fields):
        """记录非凭据审计信息，与工具的自包含证据分开。"""
        with self.service._condition:
            row = {"time": now(), "event": event, **fields}
            target = self.root / "events.jsonl"
            if target.is_symlink() or target.is_junction():
                raise ValueError("MCP 日志不允许符号链接。")
            with target.open("ab+") as stream:
                end = stream.tell()
                if end:
                    stream.seek(end - 1)
                    if stream.read(1) != b"\n":
                        stream.write(b"\n")
                stream.write((json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"))
            self.recent.append(row)
            self._changed()

    def snapshot(self):
        with self.service._condition:
            workspace = self.check() if self.path.exists() and self.service._activity != "MCP 工作台初始化" else None
            return {"enabled": self.enabled, "authorized": self.authorized, "controller": deepcopy(self.owner),
                    "workspace": workspace, "operation_id": self.active, "revoking": self._revoking,
                    "port": self.config["port"], "url": self.config["url"], "failure": self.failure,
                    "recent": list(self.recent)}

    def configure(self, port, url):
        """仅本地关闭服务后配置固定回环端口和私网 HTTPS 地址。"""
        from urllib.parse import urlsplit
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("端口须为 1–65535。")
        parsed = urlsplit(url)
        if url and (parsed.scheme != "https" or not (parsed.hostname or "").endswith(".ts.net")
                    or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path != "/mcp"):
            raise ValueError("连接地址须为 https://设备.私网.ts.net/mcp。")
        with self.service._condition:
            if self.enabled or self.owner:
                raise ValueError("请先关闭 MCP 服务。")
            value = {**self.config, "port": port, "url": url}
            atomic_write_json(self.config_path, value)
            self.config = value

    def reset_token(self):
        """仅返回一次明文；磁盘只保存高熵连接令牌的校验哈希。"""
        self.revoke()
        token = secrets.token_urlsafe(32)
        with self.service._condition:
            value = {**self.config, "token_hash": hashlib.sha256(token.encode()).hexdigest()}
            atomic_write_json(self.config_path, value)
            self.config = value
        return token

    def authenticate(self, token):
        expected = self.config.get("token_hash", "")
        return bool(self.enabled and isinstance(token, str) and expected and
                    hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(), expected))

    def allow(self):
        with self.service._condition:
            if not self.enabled or self._revoking:
                raise ValueError("请先开启服务并等待停止清理完成。")
            self.authorized = True
            self.audit("authorized")

    def initialize(self, manifest_id=None, *, replace=False):
        """本地按明确版本事务替换 Candidate；保留独立页面草稿、审计和操作结果。"""
        with self.service.activity("MCP 工作台初始化"), self.host.candidate_lock():
            if self.owner or self.active:
                raise ValueError("请先释放远程控制权。")
            if self.path.exists() and not replace:
                raise ValueError("替换现有 Candidate 须本地明确确认。")
            if manifest_id is None:
                versions = self.host.manager.list_manifests()
                if not versions:
                    raise ValueError("没有已发布 Manifest，请先在本地创建并发布版本。")
                manifest_id = versions[0]["manifest_id"]
            with staging_directory(self.root, prefix=".workspace-") as stage:
                prepared = stage / "prepared"
                prepared.mkdir()
                errors = self.host.manager.initialize_candidate(prepared / "candidate", manifest_id=manifest_id)
                if errors:
                    raise ValueError(json.dumps([e.as_dict() for e in errors], ensure_ascii=False))
                old = self.check() if self.path.exists() else {}
                atomic_write_json(prepared / "workspace.json", {"version": 1, "source_manifest_id": manifest_id,
                    "generation": str(uuid.uuid4()), "last_used_at": old.get("last_used_at")})
                atomic_write_json(prepared / ".candidate-baseline.json", {"manifest_id": manifest_id, "files": {
                    name: base64.b64encode(content).decode() for name, content in candidate_files(prepared / "candidate").items()}})
                backup = stage / "previous"
                if self.path.exists():
                    self.path.replace(backup)
                try:
                    prepared.replace(self.path)
                    if (backup / "page-drafts").exists():
                        (backup / "page-drafts").replace(self.path / "page-drafts")
                except BaseException:
                    # 回滚失败保留唯一旧副本，不交给工作目录自动清理。
                    if backup.exists():
                        try:
                            import shutil
                            if self.path.exists():
                                shutil.rmtree(self.path)
                            backup.replace(self.path)
                        except OSError:
                            retained = self.root / ("retained-" + uuid.uuid4().hex)
                            stage.replace(retained)
                            raise OSError(f"恢复失败，旧工作台保留于 {retained}")
                    raise
            self.audit("workspace_initialized", manifest_id=manifest_id)

    def check_local(self, name):
        """服务端统一阻止本地写入；已确认的截图／保存例外仍须空闲和串行。"""
        if self.in_operation:
            cancelled = getattr(self._context, "cancelled", None)
            if not self.authorized or not self.owner or self._revoking or (cancelled and cancelled.is_set()):
                raise StartError("remote_revoked", "远程操作已停止或授权已撤销。")
            return
        if not self.owner:
            return
        if name in self.LOCAL_READS:
            return
        if name in self.LOCAL_ASSISTS and not self.active and not self._readers and self.service._state["phase"] != "running":
            return
        raise StartError("remote_controlled", "远程 MCP 持有控制权，请先释放或撤销。")

    def acquire(self, label="Mac Codex"):
        with self.service._condition:
            if not self.enabled or not self.authorized or self._revoking:
                raise ValueError("本地尚未授权远程控制，或授权已撤销。")
            if self.owner or self.active or self.service._activity or self.service._state["phase"] == "running":
                raise ValueError("开发控制权或执行环境正忙。")
            if not isinstance(label, str) or not label.strip() or len(label) > 100:
                raise ValueError("控制者名称须为 1–100 字符，仅供显示。")
            workspace = self.check()
            from .agent_settings import settings_document
            from .agent_policy import HISTORY_TOOLS, KNOWLEDGE_TOOLS, MANIFEST_REFERENCE_TOOLS
            options = settings_document(self.service.data_root)
            allowed = set(MCP_TOOLS)
            for setting, names in (("history_enabled", HISTORY_TOOLS), ("knowledge_enabled", KNOWLEDGE_TOOLS),
                                   ("manifest_reference_enabled", MANIFEST_REFERENCE_TOOLS)):
                if not options[setting]:
                    allowed.difference_update(names)
            control_lock, game_lock = ProcessLock("remote-mcp-control"), ProcessLock("game")
            control_lock.acquire()
            try:
                game_lock.acquire()
                from .agent_skills import prepare_skills
                from .work_files import WorkDirectory
                self._skills = WorkDirectory(prefix="mcp-skills-")
                prepare_skills(self.service.data_root, Path(self._skills.name), threading.Event())
                previous = workspace.get("last_used_at")
                workspace["last_used_at"] = now()
                atomic_write_json(self.path / "workspace.json", workspace)
            except BaseException:
                game_lock.release()
                control_lock.release()
                if self._skills:
                    self._skills.cleanup()
                    self._skills = None
                raise
            token = secrets.token_urlsafe(32)
            self.control_hash = hashlib.sha256(token.encode()).hexdigest()
            self.allowed = frozenset(allowed)
            self.control_lock, self.game_lock = control_lock, game_lock
            self.owner = {"id": str(uuid.uuid4()), "label": label, "acquired_at": workspace["last_used_at"]}
            try:
                self.audit("acquired", controller=self.owner, previous_used_at=previous)
            except BaseException:
                self._release_locked()
                workspace["last_used_at"] = previous
                atomic_write_json(self.path / "workspace.json", workspace)
                raise
            return {"control_token": token, "controller": deepcopy(self.owner), "previous_used_at": previous,
                    "workspace": workspace, "message": "续接须保留 control_token；丢失后在本地撤销，不能靠连接令牌接管。"}

    def verify_control(self, token):
        if (not self.enabled or not self.authorized or not self.owner or self._revoking
                or not isinstance(token, str) or not self.control_hash
                or not hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(), self.control_hash)):
            raise ValueError("控制凭据无效或已撤销，请在 LALC 检查授权。")

    def _release_locked(self):
        self.previews.clear()
        if self._skills:
            try:
                self._skills.cleanup()
            except OSError as error:
                self.failure = str(error)
            finally:
                self._skills = None
        for name in ("game_lock", "control_lock"):
            if (lock := getattr(self, name)) is not None:
                lock.release()
                setattr(self, name, None)
        self.owner = self.control_hash = None
        self._revoking = False
        self._changed()

    def release(self, control_token):
        with self.service._condition:
            self.verify_control(control_token)
            assert self.owner is not None
            if self.service._fatal or self.active or self._readers or self.service._activity or self.service._state["phase"] == "running":
                raise ValueError("仍有操作或 Run，请先等待完成或 Stop。")
            self.audit("released", controller_id=self.owner["id"])
            self._release_locked()
            return {"released": True}

    def revoke(self):
        """立即拒绝新调用；复用停止与协作取消，清理完成后才交还游戏锁。"""
        with self.service._condition:
            self.authorized = False
            self._revoking = bool(self.owner)
            if self.active:
                for job in tuple(self._jobs):
                    job[1].set()
            if self.pending_request is not None:
                self.pending_request.close()
            if self.owner:
                self.service.stop()
            try:
                self.audit("revoked")
            finally:
                self._finish_revoke()

    def cancel_active(self):
        """本地 Stop 取消当前远程操作，但不自动撤销之后的开发授权。"""
        with self.service._condition:
            for _, cancelled in tuple(self._jobs):
                cancelled.set()
            if self.pending_request is not None:
                self.pending_request.close()
            if self.owner:
                self.service.stop()

    def _finish_revoke(self):
        with self.service._condition:
            if (self._revoking and not self.active and not self._readers and not self.service._activity
                    and self.service._state["phase"] != "running"):
                if self.service._fatal:
                    self.failure = "运行发生致命错误；保留执行互斥，请检查日志并退出 LALC。"
                    self._changed()
                    return
                self._release_locked()

    def operation(self, operation_id):
        if not isinstance(operation_id, str) or str(uuid.UUID(operation_id)) != operation_id:
            raise ValueError("操作编号须为标准 UUID。")
        return object_json(self.operations / (operation_id + ".json"))

    def _save_operation(self, value):
        atomic_write_json(self.operations / (value["operation_id"] + ".json"), value)
        self._changed()

    def _recover_operations(self):
        """崩溃后只核对已提交证据，无法证明的操作标未知，不自动重放。"""
        for path in self.operations.glob("*.json"):
            op = object_json(path)
            if op.get("status") in {"running", "waiting_local"}:
                result = None
                if op.get("name") == "validate_and_publish" and op.get("manifest_id"):
                    saved = self.host.manager.manifests_dir / (op["manifest_id"] + ".json")
                    if saved.is_file():
                        from .manifest_reference import ManifestReference
                        try:
                            ManifestReference(self.host.manager).read(op["manifest_id"])
                        except (ValueError, OSError):
                            pass
                        else:
                            result = RepairTools.text({"ok": True, "manifest_id": op["manifest_id"]})
                if op.get("name") == "trial_run":
                    for trace in (self.service.data_root / "traces").glob("*.jsonl"):
                        if trace.is_symlink():
                            continue
                        with trace.open(encoding="utf-8") as stream:
                            first = stream.readline()
                        try:
                            event = json.loads(first)
                        except ValueError:
                            continue
                        if event.get("remote_operation_id") == op["operation_id"]:
                            result = RepairTools.text({"run_id": event["run_id"]})
                            break
                op.update(status="finished" if result is not None else "unknown", result=result,
                          message="宿主重启；不自动重放。按版本／Run 证据核对结果。")
                atomic_write_json(path, op)

    def _request(self, request, callback, op):
        with self.service._condition:
            if not self.authorized or not self.owner or callback is None:
                request.close()
                raise ValueError("本地审批界面不可用或授权已撤销。")
            self.pending_request = request
            op["status"] = "waiting_local"
            self._save_operation(op)
        callback(request)

    def _tools(self, identity, cancelled, op=None):
        from .agent_repair import RepairLog
        log = RepairLog(self.service.data_root, path=self.root / "evidence" / identity)
        tools = RepairTools(self.service.data_root, log, host=self.host, allowed=self.allowed)
        tools.cancelled = cancelled
        tools.previews = self.previews
        if op is not None:
            tools.on_feedback = lambda request: self._request(request, self.on_feedback, op)
            tools.on_page_preview = lambda request: self._request(request, self.on_page_preview, op)
        return tools

    def _file(self, path, scope):
        if scope not in {"candidate", "skills"} or not isinstance(path, str) or not path:
            raise ValueError("只允许 Candidate 或 Skills 内的明确相对文件。")
        if scope == "candidate":
            base = self.host.candidate
        elif self._skills is not None:
            base = Path(self._skills.name)
        else:
            raise ValueError("没有活动的 Skills 副本。")
        from .page_packages import real_directory, _relative
        real_directory(base)
        _relative(path)
        relative = Path(path)
        if relative.is_absolute() or "\\" in path or ":" in path or ".." in relative.parts or relative.as_posix() != path:
            raise ValueError("文件路径越界。")
        target = base
        for part in relative.parts:
            target /= part
            if target.is_symlink():
                raise ValueError("不允许链接文件。")
        if not target.is_file() or not target.resolve().is_relative_to(base.resolve()):
            raise ValueError("文件不存在或越界。")
        return target

    def read(self, path, scope="candidate", offset=0, limit=16000):
        """分页读取普通文本或图片预览；Skills 使用接手时的固定副本。"""
        target = self._file(path, scope)
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 16000:
            raise ValueError("无效分页参数。")
        if target.suffix.lower() in {".png", ".jpg", ".jpeg", ".avif", ".webp", ".gif", ".bmp"}:
            from .file_content import FileContent, image_preview
            content = image_preview(FileContent.from_path(target))
            return {"content": [{"type": "image", "mimeType": "image/jpeg", "data": base64.b64encode(content).decode()}],
                    "details": {"path": path, "scope": scope}}
        start = offset
        with target.open(encoding="utf-8", newline="") as stream:
            while offset:
                chunk = stream.read(min(offset, 65536))
                if not chunk:
                    break
                offset -= len(chunk)
            text = stream.read(limit + 1)
        return RepairTools.text({"path": path, "scope": scope, "text": text[:limit],
            "next_offset": start + limit if len(text) > limit else None})

    def edit(self, path, old_text, new_text):
        """只替换已有 Candidate 文件中唯一匹配片段，原子提交且不新增任意文件。"""
        target = self._file(path, "candidate")
        if not isinstance(old_text, str) or not old_text or not isinstance(new_text, str):
            raise ValueError("须提供非空 old_text 和文字 new_text。")
        before = target.read_text(encoding="utf-8")
        if before.count(old_text) != 1:
            raise ValueError("原文未唯一匹配，请重新读取文件。")
        from .page_drafts import write_source
        write_source(target, before.replace(old_text, new_text, 1).encode("utf-8"))
        return RepairTools.text({"edited": path})

    def list_skills(self):
        from .agent_skills import skill_files
        if self._skills is None:
            raise ValueError("没有活动的 Skills 副本。")
        files = skill_files(Path(self._skills.name), [])
        return RepairTools.text({"skills": [{"path": p.as_posix(), "name": p.parent.as_posix()}
                                          for p in files if p.name == "SKILL.md"],
                                 "read_with": {"tool": "read", "scope": "skills"}})

    def _execute(self, name, arguments, tools, op):
        if name in {"read", "edit", "list_skills"}:
            return getattr(self, name)(**arguments)
        if name == "validate_and_publish":
            result = self.host.manager.publish(self.host.candidate / "manifest.json", manifest_id=op["manifest_id"])
            value = {"ok": result.ok, "manifest_id": result.loaded.manifest_id if result.ok else None,
                     "errors": [e.as_dict() for e in result.errors]}
            return {**RepairTools.text(value), "isError": not result.ok}
        if name == "trial_run":
            if not isinstance(arguments.get("manifest_id"), str):
                raise ValueError("必须指定已发布 Manifest。")
            config = arguments.get("run_state") or {}
            if type(config) is not dict or config.keys() - {"settings", "task_repetitions"}:
                raise ValueError("run_state 只允许 settings 和 task_repetitions。")
            logical_name, inputs = arguments.get("logical_name"), arguments.get("inputs") or {}
            if logical_name is None and inputs:
                raise ValueError("Plan 不接受业务入口参数。")
            run_id = self.service.start(logical_name, inputs, manifest_id=arguments["manifest_id"],
                _developer_trial=True, use_saved_config=arguments.get("use_saved_config", True), **config)
            return RepairTools.text({"run_id": run_id})
        if name == "remove_asset":
            arguments = {**arguments, "explicit_user_request": False}
        result_path = tools.call(name, arguments, tool_call_id=op["operation_id"] if op else str(uuid.uuid4()))
        # 工具结果落盘含去重引用；MCP 传输须完整展开并沿用日志路径及哈希校验。
        return read_json(result_path)

    def invoke(self, name, arguments, control_token, operation_id=None):
        """读操作立即返回；其余操作独立串行执行，HTTP 结束不取消后台任务。"""
        if name not in MCP_TOOLS + ("list_skills",) or type(arguments) is not dict:
            raise ValueError("未知 MCP 工具或参数。")
        if name != "list_skills" and name not in self.allowed:
            raise ValueError("当前授权关闭了此工具类别。")
        if name in READ_TOOLS:
            with self.service._condition:
                self.verify_control(control_token)
                if self.active:
                    raise ValueError("工具正在操作工作台，请稍后读取；状态和操作查询始终可用。")
                self._readers += 1
            try:
                tools = self._tools(str(uuid.uuid4()), threading.Event())
                result = self._execute(name, arguments, tools, None)
                tools.log.record({"type": "mcp_read", "name": name, "arguments": arguments, "result": result})
                self.audit("read", tool=name)
                return result
            finally:
                with self.service._condition:
                    self._readers -= 1
                    self._finish_revoke()
        with self.service._condition:
            self.verify_control(control_token)
            assert self.owner is not None
            if not isinstance(operation_id, str) or str(uuid.UUID(operation_id)) != operation_id:
                raise ValueError("写入／执行须提供标准 UUID operation_id；重试必须复用同一编号。")
            request = {"name": name, "arguments": arguments}
            stored = self.operations / (operation_id + ".json")
            if stored.exists():
                value = self.operation(operation_id)
                if value["request"] != request:
                    raise ValueError("同一操作编号不能使用不同工具或参数。")
                return RepairTools.text(value)
            if self.active or self._readers or self.service._activity or self.service._state["phase"] == "running":
                raise ValueError("仍有运行或工具操作，不能修改或重新截图。")
            op = {"operation_id": operation_id, "name": name, "request": request, "status": "running",
                  "created_at": now(), "controller_id": self.owner["id"], "workspace": self.check()["generation"]}
            if name == "validate_and_publish":
                op["manifest_id"] = str(uuid.uuid4())
            self._save_operation(op)
            cancelled = threading.Event()
            self.active = operation_id
            worker = threading.Thread(target=self._work, args=(op, cancelled), name="lalc-mcp-operation", daemon=True)
            self._jobs.add((worker, cancelled))
            worker.start()
            return RepairTools.text(deepcopy(op))

    def _work(self, op, cancelled):
        self._context.identity = op["operation_id"]
        self._context.cancelled = cancelled
        try:
            with self.host.candidate_lock(), self.service.activity("Remote MCP"):
                tools = self._tools(op["operation_id"], cancelled, op)
                tools.checkpoint()
                result = self._execute(op["name"], op["request"]["arguments"], tools, op)
                tools.log.record({"type": "mcp_result", "operation_id": op["operation_id"], "result": result})
                with self.service._condition:
                    op.update(status="finished", result=result, finished_at=now())
                    self._save_operation(op)
        except BaseException as error:
            from .agent_diagnostics import redact
            with self.service._condition:
                if op["name"] == "trial_run" and (self.service._state.get("entry") or {}).get("remote_operation_id") == op["operation_id"]:
                    self.service.stop()
                op.update(status="failed", error=redact(str(error)), finished_at=now())
                try:
                    self._save_operation(op)
                except OSError:
                    self.failure = "远程操作结果无法保存；已撤销授权，需检查磁盘与操作证据。"
                    self.authorized = False
                    self._revoking = True
        finally:
            with self.service._condition:
                if self.pending_request is not None:
                    self.pending_request.close()
                    self.pending_request = None
                self.active = None
                self._jobs = {job for job in self._jobs if job[0] is not threading.current_thread()}
                try:
                    self.audit("operation_finished", operation_id=op["operation_id"], tool=op["name"], status=op["status"])
                finally:
                    self._finish_revoke()
            self._context.identity = None
            self._context.cancelled = None

    def query(self, control_token, operation_id=None, run_id=None):
        with self.service._condition:
            self.verify_control(control_token)
            if operation_id is not None:
                return self.operation(operation_id)
            if run_id is None:
                return self.snapshot()
            if type(run_id) is not int or run_id < 1:
                raise ValueError("无效 Run ID。")
            state = self.service.status
            if state["run_id"] == run_id:
                logs = list(self.service._mcp_logs)
                value = {"run_id": run_id, "status": "已暂停" if state["paused"] else
                         "运行中" if state["phase"] == "running" else "已停止", "logs": deepcopy(logs)}
                if state["phase"] == "finished":
                    value["result"] = state["result"]
                value["logs"] = [self.log_entry(row) for row in logs]
                return value
        from .run_logs import ACTION_ENDS, trace_records
        logs, result = deque(maxlen=5), None
        for row in trace_records(self.service.data_root, run_id):
            if not row:
                continue
            if row.get("event") == "component_log" or row.get("event") in ACTION_ENDS:
                logs.append(row)
            if row.get("event") == "run_finished":
                result = row.get("result")
        return {"run_id": run_id, "status": "已停止", "logs": [self.log_entry(row) for row in logs], "result": result,
                "outcome": "known" if result is not None else "unknown"}

    @staticmethod
    def log_entry(record):
        """轮询只返回日志正文及定位信息，不暴露完整 Trace 记录。"""
        from .run_logs import ACTION_ENDS, log_text
        return {"sequence": record.get("sequence"), "recorded_at": record.get("recorded_at"),
                "level": record.get("level", "debug" if record.get("event") in ACTION_ENDS else "info"),
                "logical_name": record.get("logical_name"), "message": log_text(record)}

    def stop_run(self, control_token, run_id=None, operation_id=None):
        """显式停止当前远程 Run 或工具操作，不释放控制权。"""
        with self.service._condition:
            self.verify_control(control_token)
            if (run_id is None) == (operation_id is None):
                raise ValueError("必须且只能指定 run_id 或 operation_id。")
            if operation_id is not None:
                if operation_id != self.active:
                    raise ValueError("操作不是当前活动操作。")
                self.cancel_active()
                return {"stop_requested": True, "operation_id": operation_id}
            if self.service._state["run_id"] != run_id or not (self.service._state.get("entry") or {}).get("remote_operation_id"):
                raise ValueError("只能停止当前远程 Run。")
            self.service.stop()
            return {"stop_requested": True, "run_id": run_id}

    def open(self):
        """仅本地启动回环 HTTP；外部没有服务生命周期工具。"""
        with self.service._condition:
            if self.enabled:
                return
            if not self.config.get("token_hash"):
                raise ValueError("请先生成连接令牌。")
            if self._revoking:
                raise ValueError("停止清理尚未结束。")
        from .mcp_server import start_server
        server, thread = start_server(self)
        try:
            with self.service._condition:
                self._server, self._server_thread = server, thread
                if not thread.is_alive():
                    raise RuntimeError("MCP 服务已退出。")
                self.enabled = True
                self.audit("service_opened")
        except BaseException:
            self.close()
            raise

    def close(self):
        """先撤销并停止本地相关任务，再等待网络与执行线程收尾。"""
        self.enabled = False
        try:
            self.revoke()
        except OSError as error:
            self.failure = str(error)
        for thread, _ in tuple(self._jobs):
            if thread is not threading.current_thread():
                thread.join()
        with self.service._condition:
            self.service._condition.wait_for(lambda: not self._readers and (not self.owner or not self.service._activity))
        if self.owner and self.service._thread is not None:
            self.service._thread.join()
        with self.service._condition:
            self._finish_revoke()
        if self._server:
            self._server.should_exit = True
        if self._server_thread and self._server_thread is not threading.current_thread():
            self._server_thread.join()
        self._server = self._server_thread = None
        try:
            self.audit("service_closed")
        except OSError as error:
            self.failure = str(error)
