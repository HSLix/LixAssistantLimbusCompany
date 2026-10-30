"""Developer Policy 工具：候选开发、不可变版本试运行及运行证据读取。"""

from __future__ import annotations

import base64
import inspect
import json
import threading
import uuid

from .actions import application_actions
from .assets import AssetLibrary, asset_name
from .focused import FocusedAutomationSession, WindowsWindowPlatform
from .agent_diagnostics import error_details


REPAIR_TOOLS = ["read", "edit", "validate", "asset_tree", "asset_directory", "asset_images",
                "action_contracts", "game_screenshot", "crop_asset", "add_component", "add_recovery_rule",
                "publish", "trial_run", "list_runs", "read_run_log", "preview_crop", "remove_asset"]


class RepairTools:
    """通过宿主实现固定工具集；图片与返回值独立留存在本次交互目录。"""

    def __init__(self, data_root, log, *, platform=None, host=None):
        self.host = host
        self.created_files = set()
        self.library = AssetLibrary(data_root)
        self.log = log
        self.platform = platform
        self.cancelled = threading.Event()
        self.sequence = 0
        self.previews = {}

    def checkpoint(self):
        if self.cancelled.is_set():
            raise RuntimeError("Repair tool cancelled")

    def call(self, name, arguments, *, tool_call_id=None):
        """工具错误原样反馈模型；不把工具失败当作整个修复进程失败。"""
        self.sequence += 1
        self.checkpoint()
        try:
            methods = {"asset_tree": self.asset_tree, "asset_directory": self.asset_directory,
                       "asset_images": self.asset_images, "action_contracts": self.action_contracts,
                       "game_screenshot": self.game_screenshot, "crop_asset": self.crop_asset,
                       "add_component": self.add_component, "add_recovery_rule": self.add_recovery_rule,
                       "publish": self.publish, "trial_run": self.trial_run,
                       "list_runs": self.list_runs, "read_run_log": self.read_run_log,
                       "preview_crop": self.preview_crop, "remove_asset": self.remove_asset}
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

    def add_component(self, filename, logical_name, source):
        """创建普通 Component 并登记；角色由实际源码决定。"""
        return self.add_source("components", filename, logical_name, source)

    def publish(self):
        """在当前 Agent 活动中完整校验并保存不可变版本，不改变 Default。"""
        result = self.host.manager.publish(self.host.candidate / "manifest.json")
        if not result.ok:
            return {**self.text({"ok": False, "errors": [error.as_dict() for error in result.errors]}),
                    "isError": True}
        return self.text({"ok": True, "manifest_id": result.loaded.manifest_id,
                          "message": "已保存不可变版本，可用此 Manifest ID 试运行；Default 未改变。"})

    def trial_run(self, manifest_id, *, logical_name=None, inputs=None):
        """串行执行已保存版本；取消整轮时先停止运行并等输入释放，再返回宿主。"""
        from .application import StartError
        if not isinstance(manifest_id, str) or not manifest_id:
            raise ValueError("必须指定已 Publish 的 Manifest ID；修改 Candidate 后须先 Publish。")
        service = self.host.service
        request = {"manifest_id": manifest_id, "logical_name": logical_name,
                   "inputs": inputs if inputs is not None else {}}
        try:
            if logical_name is None:
                run_id = service.start_plan(**request["inputs"], manifest_id=manifest_id, _developer_trial=True)
            else:
                run_id = service.start(logical_name, request["inputs"], manifest_id=manifest_id,
                                       _developer_trial=True)
        except StartError as error:
            return self.text({**request, "status": "rejected", "run_id": None,
                              "code": error.code, "message": str(error), "errors": error.errors,
                              "feedback": "试运行启动失败，未创建 Run。请修正原因后再次调用 trial_run；Candidate 修改后须先 Publish。"})
        try:
            self.log.record({"type": "trial_started", "run_id": run_id, **request})
            while True:
                state = service.state
                if state["run_id"] != run_id:
                    raise RuntimeError("试运行的 Run ID 意外改变。")
                if state["phase"] == "finished":
                    break
                if self.cancelled.wait(.05):
                    service.stop()
                    service.wait_for(lambda current: current["phase"] == "finished")
        finally:
            # 工具日志写入失败也不能把正在操作游戏的运行遗留到 Agent 轮次之外。
            if service.state["run_id"] == run_id and service.state["phase"] == "running":
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
                                  "last_sequence": len(state["trace"])},
                          "feedback": "用户主动停止了本次运行，建议总结并等待用户的下个指示。" if stopped else
                          outcome + "按 Run ID 查看日志；需要再试时调用 trial_run，修改 Candidate 后须先 Publish。"})

    def list_runs(self, offset=0, limit=100):
        """列出仍有 Trace 的 Run ID，不把已清理记录当作空日志。"""
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("offset 必须非负，limit 必须为 1–200 的整数。")
        directory = self.library.data_root / "traces"
        ids = sorted((int(path.stem) for path in directory.glob("*.jsonl")
                      if path.stem.isdecimal() and not path.is_symlink()), reverse=True)
        return self.text({"run_ids": ids[offset:offset + limit],
                          "next_offset": offset + limit if offset + limit < len(ids) else None})

    def read_run_log(self, run_id, start_sequence=1, limit=100, evidence_id=None):
        """按事件序号读取 Trace；仅允许查看该 Trace 实际引用的截图。"""
        if (type(run_id) is not int or run_id < 1 or type(start_sequence) is not int or start_sequence < 1
                or type(limit) is not int or not 1 <= limit <= 200):
            raise ValueError("run_id/start_sequence 必须为正整数，limit 必须为 1–200 的整数。")
        root = self.library.data_root
        path = root / "traces" / f"{run_id}.jsonl"
        if path.is_symlink() or not path.is_file():
            raise ValueError("Run 日志不可用：记录不存在或已清理。")
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        selected = [record for record in records if record["sequence"] >= start_sequence]
        details = {"run_id": run_id, "events": selected[:limit],
                   "next_sequence": selected[limit]["sequence"] if len(selected) > limit else None}
        if evidence_id is None:
            return self.text(details)
        def referenced(value):
            if isinstance(value, dict):
                return value.get("evidence_id") == evidence_id or any(referenced(item) for item in value.values())
            return isinstance(value, list) and any(referenced(item) for item in value)
        prefix, separator, observation = str(evidence_id).partition("/")
        if prefix != str(run_id) or not separator or not observation.isdecimal() or not referenced(records):
            raise ValueError("截图必须是该 Run 日志引用的 evidence_id。")
        image_path = root / "evidence" / str(run_id) / f"{observation}.png"
        if image_path.is_symlink() or not image_path.resolve().is_relative_to((root / "evidence").resolve()):
            raise ValueError("截图路径越界。")
        return self.image(image_path.read_bytes(), {**details, "evidence_id": evidence_id})

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
        return self.text({"actions": [
            {"logical_name": name, "classification": action.classification,
             "signature": str(inspect.signature(action.execute)), "docstring": inspect.getdoc(action.execute)}
            for name, action in application_actions().items()]})

    def capture(self):
        """每次请求重新发现、恢复并置前唯一窗口；聚焦等待可被取消。"""
        self.checkpoint()
        platform = self.platform if self.platform is not None else WindowsWindowPlatform(checkpoint=self.checkpoint)
        session = FocusedAutomationSession(platform, lambda event, fields: self.log.record({"type": event, **fields}))
        session.capture()
        self.checkpoint()
        path = self.log.path / f"tool-{self.sequence}-screenshot.png"
        metadata = session.save(path)
        self.log.store.register_image(path)
        return session, metadata, path

    def game_screenshot(self):
        session, metadata, path = self.capture()
        result = self.image(path.read_bytes(), {**metadata, "view": "original"})
        overlay = self.image(self.marked_image(session, grid=True), {"view": "grid", "spacing": 40}, 2)
        result["content"].extend(overlay["content"])
        result["details"]["grid"] = overlay["details"]
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
                   "source_screenshot": metadata["path"], "interaction_id": self.log.path.name}
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
            raise ValueError("未知 preview_id；请先调用 preview_crop，不能引用其他对话的预览。")
        preview = self.previews[preview_id]
        self.checkpoint()
        result = self.library.save_crop(preview["logical_name"], preview["pixels"], preview["size"],
                                        preview["region"], run_id=None, observation=preview["observation"],
                                        tags=preview["tags"], preserve_existing_tags=True)
        # 来源同时指向独立留存的完整截图，不能依赖下次会被替换的 Candidate。
        result["source_screenshot"] = preview["source_screenshot"]
        result["preview_id"] = preview_id
        result["interaction_id"] = self.log.path.name
        from .runtime import atomic_write_json
        atomic_write_json(self.library.data_root / "asset-provenance" / f"{result['provenance_id']}.json", result)
        return self.image(self.library.read({"path": result["path"], "sha256": result["sha256"]}), result)

    def remove_asset(self, logical_name, sha, reason):
        """移除前重新截图；归档保留原始画面，并同步移除活跃图片及标签关系。"""
        asset_name(logical_name)
        self.library.read({"path": f"{logical_name}/{sha}.png", "sha256": sha})
        _, _, path = self.capture()
        result = self.library.remove(logical_name, sha, reason, path.read_bytes(), checkpoint=self.checkpoint)
        return self.text(result)
