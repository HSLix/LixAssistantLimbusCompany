"""Developer Policy 工具：候选开发、不可变版本试运行及运行证据读取。"""

from __future__ import annotations

import base64
import hashlib
import inspect
import json
import threading
import uuid
from typing import Any, Callable

from .actions import application_actions
from .assets import AssetLibrary, asset_name
from .focused import FocusedAutomationSession, WindowsWindowPlatform
from .agent_diagnostics import error_details
from .ocr import ocr_service
from .runtime import UserInterruption


from .agent_policy import BASE_TOOLS
from .manifest_reference import DEFAULT_MANIFEST_LIST_LIMIT, ManifestReference
from .knowledge import KnowledgeLibrary

REPAIR_TOOLS = list(BASE_TOOLS)


class RepairTools:
    """通过宿主实现固定工具集；图片与返回值独立留存在本次交互目录。"""

    def __init__(self, data_root, log, *, platform=None, host=None, allowed=None):
        self.allowed = frozenset(REPAIR_TOOLS if allowed is None else allowed)
        self.host = host
        self.created_files = set()
        self.deleted_files = set()
        self.library = AssetLibrary(data_root)
        self.log = log
        self.platform = platform
        self.cancelled = threading.Event()
        self.requested_manifest_id = None
        self.run_state = None
        self.runtime_gate = None
        self.read_other_runs = True
        self.parent_run_id = None
        self.trial_run_ids = set()
        self.legacy_runtime = False
        self.on_feedback: Callable[[Any], None] | None = None
        self.on_page_preview: Callable[[Any], None] | None = None
        self.knowledge = KnowledgeLibrary(data_root, self.checkpoint, host.service.codesearch if host is not None else None)
        self.sequence = 0
        self.previews = {}
        self.ocr_service = host.service.ocr_service if host is not None else ocr_service

    def checkpoint(self):
        if self.cancelled.is_set():
            raise RuntimeError("Repair tool cancelled")
        if self.requested_manifest_id is not None:
            raise RuntimeError("Recheck 已提交，本轮不再接受工具调用。")
        if self.runtime_gate is not None:
            self.runtime_gate.checkpoint()

    def call(self, name, arguments, *, tool_call_id=None):
        """工具错误原样反馈模型；不把工具失败当作整个修复进程失败。"""
        self.sequence += 1
        self.log.record({"type": "tool_reserved", "sequence": self.sequence})
        self.checkpoint()
        try:
            if name not in self.allowed:
                raise ValueError("当前模式和入口不允许此工具。")
            methods = {"read": self.read_page_scope, "edit": self.edit_page_scope,
                       "asset_tree": self.asset_tree, "asset_directory": self.asset_directory,
                       "asset_images": self.asset_images, "action_contracts": self.action_contracts,
                       "game_screenshot": self.game_screenshot, "crop_asset": self.crop_asset,
                       "delete_component": self.delete_component,
                       "add_component": self.add_component, "add_recovery_rule": self.add_recovery_rule,
                       "validate_and_publish": self.publish, "trial_run": self.trial_run,
                       "read_run_state": self.read_run_state, "recheck": self.recheck,
                       "list_runs": self.list_runs, "read_run_log": self.read_run_log,
                       "search_run_logs": self.search_run_logs,
                       "preview_crop": self.preview_crop, "remove_asset": self.remove_asset,
                       "restore_asset": self.restore_asset,
                       "list_manifests": self.list_manifests, "read_manifest": self.read_manifest,
                       "read_manifest_source": self.read_manifest_source,
                       "search_manifest_source": self.search_manifest_source,
                       "knowledge_list": self.knowledge_list, "knowledge_read": self.knowledge_read,
                       "knowledge_search_literal": self.knowledge_search_literal,
                       "knowledge_search_hybrid": self.knowledge_search_hybrid, "knowledge_git": self.knowledge_git,
                       "request_feedback": self.request_feedback,
                       "page_list": self.page_list, "page_read": self.page_read,
                       "page_create": self.page_create, "page_update": self.page_update,
                       "page_resource": self.page_resource,
                       "page_preview": self.page_preview, "page_set_enabled": self.page_set_enabled}
            methods.update(list_game_versions=self.list_game_versions, search_agent_sessions=self.search_agent_sessions,
                           read_agent_session=self.read_agent_session)
            result = methods[name](**arguments)
        except Exception as error:
            details = error_details(error, "tool:" + name,
                                    {"log_path": str(self.log.path), "round": self.log.group}, self.log.keys)
            result = {"content": [{"type": "text", "text": details["message"]}],
                      "details": {"error": details["message"], **details}, "isError": True}
            import logging
            logging.getLogger(__name__).error("Agent 工具错误：%s", details)
        self.log.record({"type": "repair_tool", "toolCallId": tool_call_id or f"host-{self.sequence}",
                         "name": name, "arguments": arguments, "result": result})
        filename = f"tool-{self.sequence}.json"
        return self.log.tool_result(filename, result)

    def page_drafts(self):
        from .page_drafts import PageDrafts
        if self.host is None or not getattr(self.host, "session", None):
            raise ValueError("页面工具需要 GUI Construct Session。")
        return PageDrafts(self.host.session)

    def page_list(self, **arguments):
        return self.text(self.page_drafts().list(**arguments))

    def read_page_scope(self, scope, *, filename=None, path=None, image=False, **paging):
        """Agent 的页面读取沿用页面权限、分页和图片预览。"""
        if "page_list" not in self.allowed:
            raise ValueError("读取页面需要 Construct 页面权限。")
        if scope == "page_settings":
            if filename is not None or path is not None or image:
                raise ValueError("page_settings 只接受分页参数。")
            return self.page_read(scope="settings", **paging)
        if scope not in {"page_draft", "page_installed"} or not filename:
            raise ValueError("读取页面文件须指定页面范围和逻辑文件名。")
        return self.page_read(scope="drafts" if scope == "page_draft" else "installed",
                              filename=filename, path="page.py" if path is None else path,
                              image=image, **paging)

    def edit_page_scope(self, scope, path, *, source=None, edits=None):
        """只在具备页面权限时修改当前 Session 的草稿入口。"""
        if "page_list" not in self.allowed:
            raise ValueError("编辑页面需要 Construct 页面权限。")
        if scope != "page_draft":
            raise ValueError("页面编辑仅支持 page_draft。")
        return self.text(self.page_drafts().update(path, source, edits=edits))

    def page_read(self, *, image=False, **arguments):
        if not image:
            return self.text(self.page_drafts().read(**arguments))
        from pathlib import Path
        scope = arguments.get("scope", "installed")
        filename, path = arguments.get("filename", ""), arguments.get("path", "page.py")
        from .file_content import image_preview
        content = self.page_drafts().file_content(scope, filename, path)
        picture = image_preview(content)
        metadata = {"scope": scope, "filename": filename, "path": path, "sha256": content.sha256,
                    "mime_type": "image/jpeg", "extension": "jpg", "preview": True, "original_size": len(content)}
        return self.knowledge_result(metadata, picture)

    def page_create(self, **arguments):
        return self.text(self.page_drafts().create(**arguments))

    def page_update(self, filename, source):
        """远程 MCP 通过完整源码更新当前草稿。"""
        return self.text(self.page_drafts().update(filename, source))

    def page_resource(self, filename, path, *, content_base64=None, copy_from=None, remove=False):
        """只写 Session 草稿资源；复制来源限页面、Asset 和已授权知识库。"""
        from .file_content import FileContent, content_hash, require_memory
        if sum((content_base64 is not None, copy_from is not None, remove is True)) != 1:
            raise ValueError("必须且只能选择 Base64 内容、受控复制来源或移除资源。")
        content = None
        if content_base64 is not None:
            if not isinstance(content_base64, str):
                raise ValueError("页面资源必须是 Base64 字符串。")
            require_memory(len(content_base64) * 2)
            content = base64.b64decode(content_base64, validate=True)
        if copy_from is not None:
            if not isinstance(copy_from, dict):
                raise ValueError("资源复制来源无效。")
            scope = copy_from.get("scope")
            if scope in {"installed", "drafts"} and set(copy_from) == {"scope", "filename", "path"}:
                content = self.page_drafts().file_content(scope, copy_from["filename"], copy_from["path"])
            elif scope == "assets" and set(copy_from) == {"scope", "path", "sha256"}:
                from .page_packages import real_directory
                real_directory(self.library.root)
                asset = {key: copy_from[key] for key in ("path", "sha256")}
                source = self.library.path(asset["path"])
                real_directory(source.parent)
                content = FileContent.from_path(source)
                if content_hash(content) != asset["sha256"]:
                    raise ValueError("Asset 内容哈希不符。")
            elif scope == "knowledge" and set(copy_from) == {"scope", "path"}:
                if "knowledge_read" not in self.allowed:
                    raise ValueError("当前设置不允许查询外部知识库。")
                source = self.knowledge.path(copy_from["path"])
                content = FileContent.from_path(source)
            else:
                raise ValueError("资源复制仅允许页面、Asset 或知识库中的明确文件。")
        return self.text(self.page_drafts().write_resource(filename, path, content, remove=remove))

    def page_preview(self, filename, summary):
        """等待人审查固定版本；不把普通反馈或历史批准当成安装授权。"""
        from .page_preview import PreviewRequest
        from .file_content import content_hash
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError("请总结字段变化、旧配置和 Plan 影响及兼容授权情况。")
        if self.on_page_preview is None:
            raise ValueError("当前入口未连接页面预览界面。")
        drafts = self.page_drafts()
        request = PreviewRequest(drafts, drafts.snapshot(filename), summary,
                                 (self.log.identity, self.log.group, self.sequence))
        evidence = f"tool-{self.sequence}-page-package"
        self.log.snapshot(evidence, request.snapshot["package"].files)
        self.log.save_json(f"tool-{self.sequence}-page-preview.json", {
            "filename": filename, "sha256": request.snapshot["sha256"],
            "source": request.snapshot["source"].decode("utf-8"), "summary": summary,
            "package_path": evidence,
            "files": [{"path": path, "sha256": content_hash(content), "size": len(content)}
                      for path, content in sorted(request.snapshot["package"].files.items())]})
        try:
            self.on_page_preview(request)
            while not request.done.wait(.05):
                self.checkpoint()
            self.checkpoint()
            if request.result is None:
                raise RuntimeError("页面审查已取消。")
            result = self.text(request.result)
            if request.result.get("status") == "preview_failed":
                result["isError"] = True
            return result
        finally:
            request.close()

    def page_set_enabled(self, filename, enabled, summary):
        """启停正式页面必须等待当前轮次的专用人工批准。"""
        from .page_preview import PreviewRequest
        from .page_packages import snapshot_page
        if type(enabled) is not bool or not isinstance(summary, str) or not summary.strip():
            raise ValueError("必须提供布尔 enabled 和非空变更说明。")
        if self.on_page_preview is None:
            raise ValueError("当前入口未连接页面确认界面。")
        drafts = self.page_drafts()
        package = snapshot_page(drafts.package_path(filename, "installed"))
        snapshot = {"filename": filename, "package": package, "sha256": package.sha256}
        request = PreviewRequest(drafts, snapshot, summary,
                                 (self.log.identity, self.log.group, self.sequence))
        request.enabled = enabled
        self.log.snapshot(f"tool-{self.sequence}-page-availability", package.files)
        try:
            self.on_page_preview(request)
            while not request.done.wait(.05):
                self.checkpoint()
            self.checkpoint()
            if request.result is None:
                raise RuntimeError("页面启停确认已取消。")
            result = self.text(request.result)
            if request.result.get("status") == "failed":
                result["isError"] = True
            return result
        finally:
            request.close()

    def request_feedback(self, message):
        """等待 GUI 的真实答复；线程取消先作废请求再完成工具收尾。"""
        from .human_feedback import FeedbackRequest
        if not isinstance(message, str) or not message.strip():
            raise ValueError("人工反馈请求内容不能为空。")
        if self.on_feedback is None:
            raise ValueError("当前入口未连接人工反馈界面。")
        request = FeedbackRequest(message, (self.log.identity, self.log.group, self.sequence))
        try:
            self.on_feedback(request)
            while not request.done.wait(.05):
                self.checkpoint()
            self.checkpoint()
            if request.result is None:
                raise RuntimeError("人工反馈请求已取消。")
            return self.text(request.result)
        finally:
            request.close()

    def list_manifests(self, offset=0, limit=DEFAULT_MANIFEST_LIST_LIMIT):
        return self.text(ManifestReference(self.host.manager).list(offset, limit))

    def list_game_versions(self, **arguments):
        """只查版本索引，不遍历历史日志目录。"""
        from .agent_history import AgentHistory
        return self.text(AgentHistory(self.library.data_root).versions(**arguments))

    def search_agent_sessions(self, **arguments):
        """按观测字段筛选已索引对话；版本筛选不扩张文件读取权限。"""
        from .agent_history import AgentHistory
        return self.text(AgentHistory(self.library.data_root).search(**arguments))

    def read_agent_session(self, **arguments):
        """有界读取历史文字或显式图片，不恢复历史 Session 或执行工具。"""
        from .agent_history import AgentHistory
        metadata, content = AgentHistory(self.library.data_root).read(**arguments)
        result = self.text(metadata)
        if content is not None:
            extension = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp"}[metadata["mime_type"]]
            path = self.log.path / f"tool-{self.sequence}-history.{extension}"
            path.write_bytes(content)
            self.log.store.register_image(path)
            result["content"].append({"type": "image", "mimeType": metadata["mime_type"],
                                      "data": base64.b64encode(content).decode()})
        return result

    def knowledge_list(self, **arguments):
        return self.text(self.knowledge.list(**arguments))

    def knowledge_search_literal(self, **arguments):
        return self.text(self.knowledge.search(**arguments))

    def knowledge_search_hybrid(self, **arguments):
        return self.text(self.knowledge.search_hybrid(**arguments))

    def knowledge_git(self, **arguments):
        metadata = self.knowledge.git_operation(**arguments)
        return self.knowledge_result(metadata, metadata.pop("_image", None))

    def knowledge_read(self, **arguments):
        """保留资料原图与 MIME，不调用游戏截图 OCR 或 Asset PNG 专用路径。"""
        metadata, content = self.knowledge.read(**arguments)
        return self.knowledge_result(metadata, content)

    def knowledge_result(self, metadata, content):
        """知识库原图沿用同轮结果文件和自包含日志，不改变 Asset 专用行为。"""
        result = self.text(metadata)
        if content is not None:
            filename = f"tool-{self.sequence}-knowledge.{metadata['extension']}"
            path = self.log.path / filename
            path.write_bytes(content)
            self.log.store.register_image(path)
            result["content"].append({"type": "image", "mimeType": metadata["mime_type"],
                                      "data": base64.b64encode(content).decode()})
        return result

    def read_manifest(self, manifest_id, offset=0, limit=50):
        return self.text(ManifestReference(self.host.manager).structure(manifest_id, offset, limit))

    def read_manifest_source(self, manifest_id, section, logical_name, offset=0, limit=100):
        """按逻辑名分页读取指定 Manifest 的已校验源码。可先用 search_manifest_source 定位命中行。"""
        return self.text(ManifestReference(self.host.manager).source(manifest_id, section, logical_name, offset, limit))

    def search_manifest_source(self, manifest_id, query, offset=0, limit=50):
        """在指定已发布 Manifest 的全部已校验 Python 源码中搜索非空字面子串，包含 Recovery Rule，忽略大小写。

        不执行源码。每行命中返回 section、logical_name、component_id、从 1 开始的 line_number 和原文 text。
        offset 是从 0 开始的命中偏移，limit 为 1–200，使用 next_offset 续页。用 read_manifest_source 读取上下文。
        """
        return self.text(ManifestReference(self.host.manager).search_source(
            manifest_id, query, offset, limit, checkpoint=self.checkpoint))

    def delete_component(self, filename, impact):
        """仅删除经本次人工确认的候选 Python 文件；不修改登记或历史版本。"""
        from pathlib import Path
        from .developer import candidate_files
        if self.host is None or "request_feedback" not in self.allowed:
            raise ValueError("删除需要 Candidate 和本轮人工反馈权限。")
        if not isinstance(filename, str) or not filename:
            raise ValueError("必须指定 Candidate 内的相对 Python 文件路径。")
        path = Path(filename)
        if (path.is_absolute() or path.as_posix() != filename or ".." in path.parts
                or "\\" in filename or ":" in filename or path.suffix != ".py"):
            raise ValueError("只能删除 Candidate 内的普通 .py 文件。")
        if not isinstance(impact, str) or not impact.strip():
            raise ValueError("删除前必须说明用户请求、当前情景和影响范围。")
        before = candidate_files(self.host.candidate)
        if filename not in before:
            raise ValueError("目标文件不存在。")
        confirmation = f"确认删除 {filename}"
        result = self.request_feedback(
            f"请求删除 Candidate 文件：{filename}\n\n{impact}\n\n"
            "只删除该文件，不自动修改 Manifest、调用方或已发布版本。\n"
            f"如仍确认删除，请输入以下完整文字并提交：\n{confirmation}")
        feedback = result["details"]
        if feedback["status"] != "confirmed" or feedback["text"].strip() != confirmation:
            return self.text({"deleted": False, "filename": filename, "feedback": feedback})
        self.checkpoint()
        if candidate_files(self.host.candidate) != before:
            raise ValueError("确认期间 Candidate 已改变；请重新检查影响并请求确认。")
        (self.host.candidate / path).unlink()
        self.deleted_files.add(filename)
        return self.text({"deleted": True, "filename": filename})

    def add_component(self, filename, logical_name, source):
        """创建普通 Component 并登记；角色由实际源码决定。"""
        return self.add_source("components", filename, logical_name, source)

    def publish(self, summary=None):
        """在当前 Agent 活动中完整校验并保存不可变版本，不改变 Default。"""
        if self.run_state is not None:
            if not isinstance(summary, str) or not summary.strip():
                raise ValueError("Runtime 发布前必须提供本次修复问题的简要说明 summary。")
            from .runtime import atomic_write_json
            path = self.host.candidate / "manifest.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["AdditionalMessage"] = summary.strip()
            atomic_write_json(path, value)
        result = self.host.manager.publish(self.host.candidate / "manifest.json")
        if not result.ok:
            return {**self.text({"ok": False, "errors": [error.as_dict() for error in result.errors]}),
                    "isError": True}
        return self.text({"ok": True, "manifest_id": result.loaded.manifest_id,
                          "message": "已保存不可变版本，可用此 Manifest ID 试运行；Default 未改变。"})

    def read_run_state(self):
        """只返回当前父 Run 的状态副本，不向 Agent 暴露可写对象。"""
        if self.run_state is None:
            raise ValueError("当前入口没有活动 RunState。")
        return self.text(self.run_state.snapshot())

    def recheck(self, manifest_id):
        """登记本轮终结式交接；实际调用只能由父 Run 执行器完成。"""
        if self.run_state is None:
            raise ValueError("当前入口没有待恢复 Run。")
        ManifestReference(self.host.manager).read(manifest_id)
        result = self.text({"manifest_id": manifest_id, "handoff": "recheck"})
        self.requested_manifest_id = manifest_id
        return result

    def trial_run(self, manifest_id, *, logical_name=None, inputs=None, use_saved_config=True, run_state=None):
        """串行执行已保存版本；取消整轮时先停止运行并等输入释放，再返回宿主。"""
        from .application import StartError
        if not isinstance(manifest_id, str) or not manifest_id:
            raise ValueError("必须指定已 Publish 的 Manifest ID；修改 Candidate 后须先 Publish。")
        service = self.host.service
        request = {"manifest_id": manifest_id, "logical_name": logical_name,
                   "inputs": inputs if inputs is not None else {}, "use_saved_config": use_saved_config,
                   "run_state": run_state}
        configuration = {} if run_state is None else run_state
        if type(configuration) is not dict or configuration.keys() - {"settings", "task_repetitions"}:
            raise ValueError("run_state 仅接受 task_repetitions 和 settings。")
        try:
            if logical_name is None:
                if request["inputs"]:
                    raise ValueError("Plan 无业务入口参数，请通过 run_state 提供配置。")
                run_id = service.start_plan(**configuration, use_saved_config=use_saved_config,
                                            manifest_id=manifest_id, _developer_trial=True, _trial_session_id=self.log.identity)
            else:
                run_id = service.start(logical_name, request["inputs"], manifest_id=manifest_id,
                                       _developer_trial=True, _trial_session_id=self.log.identity,
                                       use_saved_config=use_saved_config, **configuration)
        except StartError as error:
            return self.text({**request, "status": "rejected", "run_id": None,
                              "code": error.code, "message": str(error), "errors": error.errors,
                              "feedback": "试运行启动失败，未创建 Run。请修正原因后再次调用 trial_run；Candidate 修改后须先 Publish。"})
        try:
            self.log.record({"type": "trial_started", "run_id": run_id, **request})
            while True:
                state = service.status
                if state["run_id"] != run_id:
                    raise RuntimeError("试运行的 Run ID 意外改变。")
                if state["phase"] == "finished":
                    break
                if self.cancelled.wait(.05):
                    service.stop()
                    service.wait_for(lambda current: current["phase"] == "finished")
        finally:
            # 工具日志写入失败也不能把正在操作游戏的运行遗留到 Agent 轮次之外。
            state = service.status
            if state["run_id"] == run_id and state["phase"] == "running":
                service.stop()
                service.wait_for(lambda current: current["phase"] == "finished")
        self.checkpoint()
        result = state["result"]
        stopped = result.get("failure_code", result.get("reason")) == "user_cancelled"
        outcome = ("试运行执行成功。" if result.get("status") == "success" else
                   "试运行执行失败。" if result.get("status") == "failure" else
                   "Plan 结果已返回；遍历完成不代表每个任务成功，请检查各项结果。")
        return self.text({**request, "run_id": run_id, "result": result,
                          "log": {"run_id": run_id, "first_sequence": 1,
                                  "last_sequence": state["last_sequence"]},
                          "feedback": "用户主动停止了本次运行，建议总结并等待用户的下个指示。" if stopped else
                          outcome + "按 Run ID 查看日志；需要再试时调用 trial_run，修改 Candidate 后须先 Publish。"})

    def can_read_run(self, run_id):
        """按宿主记录确定归属，兼容尚未登记试运行 Session 或父 Run 的旧记录。"""
        if self.read_other_runs or run_id == self.parent_run_id:
            return True
        from .run_logs import trace_records
        try:
            records = trace_records(self.library.data_root, run_id, check=self.checkpoint)
            start = next(records, None)
            if not start or start.get("event") != "run_started" or start.get("run_id") != run_id:
                return False
            if start.get("developer_trial") is True:
                owner = start.get("trial_session_id")
                return owner == self.log.identity if owner is not None else run_id in self.trial_run_ids
            if self.legacy_runtime and self.parent_run_id is None and any(
                record and record.get("event") == "agent_invoked" and record.get("session_id") == self.log.identity
                for record in records
            ):
                self.parent_run_id = run_id
                return True
        except (OSError, ValueError):
            return False
        return False

    def visible_run_ids(self):
        """先按权限筛选，再交给列表分页或检索。"""
        from .run_logs import retained_runs
        return [run_id for run_id in retained_runs(self.library.data_root) if self.can_read_run(run_id)]

    def list_runs(self, offset=0, limit=100):
        """列出保留 Run 的首尾元数据；旧记录不能确认的字段明确未知。"""
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("offset 必须非负，limit 必须为 1–200 的整数。")
        from .run_logs import run_summary
        root = self.library.data_root
        ids = self.visible_run_ids()
        runs = [run_summary(root, identity, check=self.checkpoint) for identity in ids[offset:offset + limit]]
        if self.host is not None:
            current = self.host.service.status
            for item in runs:
                if item["run_id"] == current.get("run_id") and current.get("phase") == "running":
                    item["status"] = "running"
        return self.text({"run_ids": ids[offset:offset + limit], "runs": runs,
                          "next_offset": offset + limit if offset + limit < len(ids) else None})

    def read_run_log(self, run_id, start_sequence=1, limit=100, evidence_id=None, levels=None, logical_name=None,
                     *, render_sequence=None):
        """读取 Trace；用 evidence_id 查看原图，或只传 run_id 和 render_sequence 查看指定匹配、OCR 或点击事件的标注图。

        先通过 search_run_logs 或本工具找到动作结束事件的 sequence，再传给 render_sequence。
        OCR 和匹配仅引用已保存的当前观察；点击保存或复用当前缓存帧。事件需有可读截图证据。
        """
        if type(run_id) is not int or run_id < 1:
            raise ValueError("run_id 必须为正整数。")
        from .run_logs import ACTION_ENDS, image_metadata, image_path, query_trace, run_log_counts, trace_records, trace_path
        from .file_content import FileContent, image_preview
        root = self.library.data_root
        try:
            if not self.can_read_run(run_id):
                raise ValueError("Run outside scope")
            trace_path(root, run_id)
        except (ValueError, OSError):
            raise ValueError("Run 日志不可用：没有访问权限、记录不存在或已清理。") from None
        if render_sequence is not None:
            if type(render_sequence) is not int or render_sequence < 1:
                raise ValueError("render_sequence 必须为正整数。")
            if (evidence_id is not None or levels is not None or logical_name is not None
                    or type(start_sequence) is not int or start_sequence != 1 or type(limit) is not int or limit != 100):
                raise ValueError("render_sequence 仅与 run_id 一起使用。")
            start_sequence, limit = render_sequence, 1
        page = query_trace(root, [run_id], start_sequence=start_sequence, limit=limit,
                           levels=levels, logical_name=logical_name, check=self.checkpoint)
        details = {"run_id": run_id, "events": [item["record"] for item in page["matches"]],
                   "next_sequence": page["next"]["start_sequence"] if page["next"] else None,
                   "damaged_records": page["damaged_records"],
                   "log_counts": run_log_counts(root, run_id, check=self.checkpoint)}
        annotations = []
        if render_sequence is not None:
            from .image_annotations import action_annotations

            events = details["events"]
            if not events or events[0]["sequence"] != render_sequence:
                raise ValueError("指定的事件序号不存在。")
            record = events[0]
            if (record.get("event") not in ACTION_ENDS
                    or record.get("logical_name") not in ("observe.match_asset", "observe.match_asset_group",
                                                             "observe.match_feature", "observe.ocr", "control.click")):
                raise ValueError("请选择匹配、OCR 或点击的动作结束事件。")
            metadata = image_metadata(record)
            evidence_id = metadata.get("evidence_id") if isinstance(metadata, dict) else None
            details.update(render_sequence=render_sequence, next_sequence=None)
            annotations = action_annotations(record)
        elif evidence_id is not None:
            def referenced(value):
                if isinstance(value, dict):
                    return value.get("evidence_id") == evidence_id or any(referenced(item) for item in value.values())
                return isinstance(value, list) and any(referenced(item) for item in value)

            prefix, separator, observation = str(evidence_id).partition("/")
            if (prefix != str(run_id) or not separator or not observation.isdecimal()
                    or not any(referenced(record) for record in trace_records(root, run_id, check=self.checkpoint) if record)):
                raise ValueError("截图必须是该 Run 日志引用的 evidence_id。")
        else:
            return self.text(details)
        path = image_path(root, run_id, {"evidence_id": evidence_id})
        if path is None or not path.is_file():
            raise ValueError("截图证据不可用：缺失、已清理或路径越界。")
        content = image_preview(FileContent.from_path(path), annotations=annotations)
        filename = self.log.path / f"tool-{self.sequence}-run-preview.jpg"
        filename.write_bytes(content)
        self.log.store.register_image(filename)
        result = self.text({**details, "evidence_id": evidence_id})
        result["content"].append({"type": "image", "mimeType": "image/jpeg", "data": base64.b64encode(content).decode()})
        return result

    def search_run_logs(self, keyword, run_id=None, *, all_runs=False, start_run_id=None,
                        start_sequence=1, limit=100, levels=None, logical_name=None):
        """显式选择单 Run 或所有保留 Run，按原文子串检索并返回可续读游标。"""
        from .run_logs import query_trace
        if not isinstance(keyword, str) or not keyword.strip() or type(all_runs) is not bool:
            raise ValueError("keyword 必须非空，all_runs 必须为布尔值。")
        if (all_runs and run_id is not None) or (not all_runs and (type(run_id) is not int or run_id < 1)):
            raise ValueError("指定正整数 run_id，或显式 all_runs=true，不能同时选择。")
        if start_run_id is not None and (type(start_run_id) is not int or start_run_id < 1):
            raise ValueError("start_run_id 必须为正整数。")
        if not all_runs and not self.can_read_run(run_id):
            raise ValueError("Run 日志不可用：没有访问权限、记录不存在或已清理。")
        ids = self.visible_run_ids() if all_runs else [run_id]
        if start_run_id is not None:
            if not all_runs and start_run_id != run_id:
                raise ValueError("游标不属于选定 Run。")
            ids = [identity for identity in ids if identity <= start_run_id]
            if ids and ids[0] != start_run_id:
                start_sequence = 1
        return self.text(query_trace(self.library.data_root, ids, start_sequence=start_sequence, limit=limit,
                                    levels=levels, logical_name=logical_name, keyword=keyword, check=self.checkpoint))

    def add_recovery_rule(self, filename, logical_name, source):
        """创建 Recovery Rule 并登记，不赋予通用写入权限。"""
        return self.add_source("recovery_rules", filename, logical_name, source)

    def add_source(self, section, filename, logical_name, source):
        if self.host is None:
            raise ValueError("新增源码需要已初始化的 Developer Candidate。")
        result = self.host.add_source(section, filename, logical_name, source, self.checkpoint)
        self.created_files.add(filename)
        return self.text(result)

    @staticmethod
    def text(value):
        return {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}], "details": value}

    def image(self, content, metadata, index=1):
        from .recognition import decode_image
        image = decode_image(content)
        if not content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Asset image must be PNG")
        filename = f"tool-{self.sequence}-image-{index}.png"
        (self.log.path / filename).write_bytes(content)
        self.log.store.register_image(self.log.path / filename)
        result = self.text({**metadata, "width": image.shape[1], "height": image.shape[0],
                            "evidence_path": str(self.log.path / filename)})
        result["content"].append({"type": "image", "mimeType": "image/png",
                                  "data": base64.b64encode(content).decode()})
        return result

    def asset_tree(self):
        lines = []
        for path in sorted(self.library.root.rglob("*")):
            name = path.relative_to(self.library.root).as_posix()
            self.library.path(name)
            if path.is_dir():
                asset_name(name)
                lines.append("  " * (len(path.relative_to(self.library.root).parts) - 1) + path.name + "/")
        return self.text({"tree": "\n".join(lines)})

    def asset_directory(self, logical_name):
        directory = self.library.path(asset_name(logical_name))
        files = sorted(path.name for path in directory.iterdir() if path.is_file())
        tag_file = self.library.path(f"{logical_name}/asset-tag.json")
        tags = tag_file.read_text(encoding="utf-8") if tag_file.exists() else None
        return self.text({"logical_name": logical_name, "files": files, "tag_content": tags,
                          "tags_missing": tags is None})

    def asset_images(self, images):
        """先核对全部图片，再返回完整批次，避免部分成功导致图片对应错误。"""
        from .recognition import decode_image
        if not isinstance(images, list) or not images:
            raise ValueError("images must be a nonempty list")
        checked = []
        for entry in images:
            if not isinstance(entry, dict) or set(entry) != {"logical_name", "sha256"}:
                raise ValueError("Each image requires logical_name and full sha256")
            try:
                name = asset_name(entry["logical_name"])
                content = self.library.read({"path": f"{name}/{entry['sha256']}.png", "sha256": entry["sha256"]})
                decode_image(content)
                if not content.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError("Asset image must be PNG")
            except (ValueError, OSError) as error:
                raise ValueError(f"Asset {entry['logical_name']}/{entry['sha256']}: {error}") from error
            checked.append((content, entry))
        result = {"content": [], "details": {"images": []}}
        for index, (content, entry) in enumerate(checked, 1):
            image = self.image(content, entry, index)
            result["content"].extend(image["content"])
            result["details"]["images"].append(image["details"])
        return result

    def action_contracts(self):
        """读取已注册 Trusted Action 的分类、签名和说明。observe.ocr 的 det_options 在这里查询。"""
        return self.text({"actions": [
            {"logical_name": name, "classification": action.classification,
             "signature": str(inspect.signature(action.execute)), "docstring": inspect.getdoc(action.execute)}
            for name, action in application_actions().items()]})

    def capture(self, *, auto_park_cursor: bool = True):
        """每次请求重新发现、恢复并置前唯一窗口；聚焦等待可被取消。"""
        self.checkpoint()
        platform = self.platform if self.platform is not None else WindowsWindowPlatform(checkpoint=self.checkpoint)
        session = FocusedAutomationSession(platform, lambda event, fields: self.log.record({"type": event, **fields}))
        session.capture(auto_park_cursor=auto_park_cursor)
        self.checkpoint()
        path = self.log.path / f"tool-{self.sequence}-screenshot.png"
        metadata = session.save(path)
        self.log.store.register_image(path)
        return session, metadata, path

    def game_screenshot(self, *, auto_park_cursor: bool = True):
        """返回同次原图、网格图及默认设置的完整 OCR；识别失败保留图片并说明错误，不支持韩文。

        Workflow 的局部识别与检测调参见 action_contracts 中的 observe.ocr。
        """
        from .recognition import client_image

        session, metadata, path = self.capture(auto_park_cursor=auto_park_cursor)
        result = self.image(path.read_bytes(), {**metadata, "view": "original"})
        overlay = self.image(self.marked_image(session, grid=True), {"view": "grid", "spacing": 40}, 2)
        result["content"].extend(overlay["content"])
        result["details"]["grid"] = overlay["details"]
        def checkpoint():
            self.checkpoint()
            session.check(record=False)

        try:
            recognized = self.ocr_service.recognize(client_image(session.image, session.size), checkpoint=checkpoint)
            ocr = {"ocr": {"observation": session.observation, **recognized}}
        except UserInterruption:
            raise
        except Exception as error:
            # 窗口失效或取消不能被 OCR 降级掩盖。
            checkpoint()
            details = error_details(error, "tool:game_screenshot:ocr", keys=self.log.keys)
            ocr = {"ocr_error": details}
        checkpoint()
        result["content"].extend(self.text(ocr)["content"])
        result["details"].update(ocr)
        return result

    @staticmethod
    def marked_image(session, *, grid=False, region=None):
        """只在复制的像素上画辅助线，不污染原始截图和模板。"""
        import cv2
        from .recognition import client_image
        image = client_image(session.image, session.size)
        width, height = session.size
        if grid:
            for x in range(0, width, 40):
                cv2.line(image, (x, 0), (x, height - 1), (0, 255, 255), 1)
                cv2.putText(image, str(x), (x + 2, 12), cv2.FONT_HERSHEY_SIMPLEX, .3, (0, 255, 255), 1)
            for y in range(0, height, 40):
                cv2.line(image, (0, y), (width - 1, y), (0, 255, 255), 1)
                cv2.putText(image, str(y), (2, max(12, y - 2)), cv2.FONT_HERSHEY_SIMPLEX, .3, (0, 255, 255), 1)
        if region is not None:
            x, y, w, h = (region[key] for key in ("x", "y", "width", "height"))
            for column in (x, min(width - 1, x + w)):
                cv2.line(image, (column, 0), (column, height - 1), (0, 0, 255), 1)
            for row in (y, min(height - 1, y + h)):
                cv2.line(image, (0, row), (width - 1, row), (0, 0, 255), 1)
        ok, encoded = cv2.imencode(".png", image)
        if not ok:
            raise ValueError("辅助图 PNG 编码失败。")
        return encoded.tobytes()

    def preview_crop(self, logical_name, region, threshold=.9, tags=None):
        """从新截图预览裁剪及同图匹配；仅留交互证据，不加入活跃素材库。"""
        from .recognition import client_image, decode_image, detect_template
        asset_name(logical_name)
        tags = self.library.tags(tags)
        session, metadata, _ = self.capture()
        content, area = self.library.crop_content(session.image, session.size, region)
        matches = detect_template(client_image(session.image, session.size), decode_image(content), threshold=threshold)
        for match in matches:
            match["centerxy"] = (match["x"] + match["width"] // 2, match["y"] + match["height"] // 2)
        identity = uuid.uuid4().hex
        details = {"preview_id": identity, "logical_name": logical_name, "region": area, "tags": tags,
                   "threshold": threshold, "matches": matches, "match_count": len(matches),
                   "source_screenshot": metadata["path"], "interaction_id": self.log.identity}
        result = self.image(self.marked_image(session, region=area), {**details, "view": "crop_region"})
        crop = self.image(content, {"view": "crop"}, 2)
        result["content"].extend(crop["content"])
        result["details"]["crop"] = crop["details"]
        self.checkpoint()
        self.previews[identity] = {"pixels": session.image, "size": session.size,
                                   "observation": session.observation, **details}
        return result

    def crop_asset(self, preview_id):
        """只保存本对话已预览的原始像素，不重新截图或接受外部路径。"""
        if not isinstance(preview_id, str) or preview_id not in self.previews:
            raise ValueError("未知或已失效的 preview_id；请重新调用 preview_crop，不能引用其他对话或重启前的预览。")
        preview = self.previews[preview_id]
        self.checkpoint()
        result = self.library.save_crop(preview["logical_name"], preview["pixels"], preview["size"],
                                        preview["region"], run_id=None, observation=preview["observation"],
                                        tags=preview["tags"], preserve_existing_tags=True)
        # 来源同时指向独立留存的完整截图，不能依赖下次会被替换的 Candidate。
        result["source_screenshot"] = preview["source_screenshot"]
        result["preview_id"] = preview_id
        result["interaction_id"] = self.log.identity
        from .runtime import atomic_write_json
        atomic_write_json(self.library.data_root / "asset-provenance" / f"{result['provenance_id']}.json", result)
        return self.image(self.library.read({"path": result["path"], "sha256": result["sha256"]}), result)

    def remove_asset(self, logical_name, sha, reason, explicit_user_request=False):
        """默认取得本次人工确认，再截图归档并移除活跃图片及标签；明确用户要求可直接执行。"""
        asset_name(logical_name)
        self.library.read({"path": f"{logical_name}/{sha}.png", "sha256": sha})
        if type(explicit_user_request) is not bool:
            raise ValueError("explicit_user_request 必须是布尔值。")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("移除 Asset 必须提供非空理由。")
        if not explicit_user_request:
            if "request_feedback" not in self.allowed:
                raise ValueError("用户未明确要求归档，当前入口也无人工反馈权限。")
            confirmation = f"确认归档 {logical_name}/{sha}"
            feedback = self.request_feedback(
                f"请求归档素材：{logical_name}\nSHA：{sha}\n理由：{reason}\n"
                "归档后将立即退出共享库匹配，影响所有 Session。保留原图及标签供恢复。\n"
                f"允许归档请输入以下完整文字并提交；否则跳过：\n{confirmation}")["details"]
            if feedback["status"] != "confirmed" or feedback["text"].strip() != confirmation:
                return self.text({"removed": False, "logical_name": logical_name, "sha256": sha, "feedback": feedback})
        self.checkpoint()
        _, _, path = self.capture()
        result = self.library.remove(logical_name, sha, reason, path.read_bytes(), checkpoint=self.checkpoint)
        return self.text(result)

    def restore_asset(self, logical_name, sha):
        """按原逻辑名和完整哈希恢复最新归档；权限由调用入口统一检查。"""
        return self.text(self.library.restore(logical_name, sha, checkpoint=self.checkpoint))
