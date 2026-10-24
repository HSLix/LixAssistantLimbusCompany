"""独立修复的素材、动作契约和现场观察工具；不执行候选或游戏控制。"""

from __future__ import annotations

import base64
import inspect
import json
import threading

from .actions import application_actions
from .assets import AssetLibrary, asset_name
from .focused import FocusedAutomationSession, WindowsWindowPlatform
from .agent_diagnostics import error_details


REPAIR_TOOLS = ["read", "edit", "validate", "asset_tree", "asset_directory", "asset_images",
                "action_contracts", "game_screenshot", "crop_asset", "add_component", "add_recovery_rule"]


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
                       "add_component": self.add_component, "add_recovery_rule": self.add_recovery_rule}
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
        self.log.save_json(filename, result)
        return str(self.log.path / filename)

    def add_component(self, filename, logical_name, source):
        """创建普通 Component 并登记；角色由实际源码决定。"""
        return self.add_source("components", filename, logical_name, source)

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
        return session, metadata, path

    def game_screenshot(self):
        _, metadata, path = self.capture()
        return self.image(path.read_bytes(), metadata)

    def crop_asset(self, logical_name, region, tags=None):
        asset_name(logical_name)
        self.library.tags(tags)
        session, metadata, _ = self.capture()
        self.checkpoint()
        result = self.library.save_crop(logical_name, session.image, session.size, region, run_id=None,
                                        observation=session.observation, tags=tags, preserve_existing_tags=True)
        # 来源同时指向独立留存的完整截图，不能依赖下次会被替换的 Candidate。
        result["source_screenshot"] = metadata["path"]
        result["interaction_id"] = self.log.path.name
        from .runtime import atomic_write_json
        atomic_write_json(self.library.data_root / "asset-provenance" / f"{result['provenance_id']}.json", result)
        return self.image(self.library.read({"path": result["path"], "sha256": result["sha256"]}), result)
