"""已发布 Manifest 的纯数据参考；不导入 Python，不变更任何选择。"""

import hashlib
import json
import re
import uuid
from datetime import datetime

from .manifest import OPTIONAL_FIELDS, SAVED_TOP_LEVEL_FIELDS, SCHEMA_VERSION, SECTIONS


class ManifestReference:
    """按 Manifest 成员定位源码；每次访问验证真实路径、身份和内容哈希。"""

    def __init__(self, manager):
        self.manager = manager

    def _file(self, path):
        root = self.manager.data_root
        relative = path.relative_to(root)
        current = root
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                raise ValueError("参考内容不允许符号链接。")
        if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError("参考内容不存在或路径越界。")
        return path.read_bytes()

    def read(self, manifest_id):
        """只解析登记关系，不走会执行源码的 load / validate。"""
        if not isinstance(manifest_id, str) or str(uuid.UUID(manifest_id)) != manifest_id:
            raise ValueError("Manifest ID 必须是标准 UUID。")
        value = json.loads(self._file(self.manager.manifests_dir / f"{manifest_id}.json"))
        if (not isinstance(value, dict) or not SAVED_TOP_LEVEL_FIELDS <= set(value) <= SAVED_TOP_LEVEL_FIELDS | OPTIONAL_FIELDS
                or type(value.get("schema_version")) is not int or value["schema_version"] != SCHEMA_VERSION
                or value.get("manifest_id") != manifest_id):
            raise ValueError("Manifest 结构或身份校验失败。")
        if not isinstance(value.get("AdditionalMessage", ""), str):
            raise ValueError("AdditionalMessage 必须是字符串。")
        if "published_at" in value:
            if not isinstance(value["published_at"], str) or datetime.fromisoformat(value["published_at"]).tzinfo is None:
                raise ValueError("published_at 必须是带时区的时间。")
        for section in SECTIONS:
            if not isinstance(value[section], dict):
                raise ValueError("Manifest 分区无效。")
            for name, entry in value[section].items():
                if (not self.manager._valid_logical_name(name) or not isinstance(entry, dict)
                        or set(entry) != {"component_id"} or not isinstance(entry["component_id"], str)
                        or not re.fullmatch(r"sha256:[0-9a-f]{64}", entry["component_id"])):
                    raise ValueError("Manifest 成员登记无效。")
        return value

    def list(self, offset=0, limit=50):
        self._bounds(offset, limit)
        if self.manager.manifests_dir.is_symlink():
            raise ValueError("Manifest 目录不允许符号链接。")
        if any(path.is_symlink() for path in self.manager.manifests_dir.glob("*.json")):
            raise ValueError("Manifest 文件不允许符号链接。")
        values = self.manager.list_manifests()
        return self._page(values, offset, limit)

    @staticmethod
    def _bounds(offset, limit):
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("offset 必须非负，limit 必须为 1–200。")

    @staticmethod
    def _page(values, offset, limit):
        end = min(offset + limit, len(values))
        return {"items": values[offset:end], "offset": offset, "total": len(values),
                "next_offset": end if end < len(values) else None, "truncated": end < len(values)}

    def structure(self, manifest_id, offset=0, limit=50):
        self._bounds(offset, limit)
        value = self.read(manifest_id)
        items = [{"section": section, "logical_name": name, **entry}
                 for section in SECTIONS for name, entry in value[section].items()]
        return {"manifest_id": manifest_id, **self._page(items, offset, limit)}

    def source(self, manifest_id, section, logical_name, offset=0, limit=100):
        self._bounds(offset, limit)
        value = self.read(manifest_id)
        if section not in SECTIONS or logical_name not in value[section]:
            raise ValueError("指定成员不属于该 Manifest 分区。")
        identity = value[section][logical_name]["component_id"]
        digest = identity.removeprefix("sha256:")
        content = self._file(self.manager.components_dir / f"{digest}.py")
        if hashlib.sha256(content).hexdigest() != digest:
            raise ValueError("Component 内容哈希校验失败。")
        lines = content.decode("utf-8").splitlines(keepends=True)
        page = self._page(lines, offset, limit)
        return {"manifest_id": manifest_id, "section": section, "logical_name": logical_name,
                "component_id": identity, "start_line": offset + 1,
                "source": "".join(page.pop("items")), **page}
