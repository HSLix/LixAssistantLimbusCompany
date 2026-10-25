"""语义 Asset 的校验、完整哈希保存、模板匹配与独立使用索引。"""

from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from .runtime import atomic_write_json, sha256_bytes


def asset_name(value: str) -> str:
    """语义名允许目录层级，不接受扩展名或越界路径。"""

    if type(value) is not str or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*(/[A-Za-z_][A-Za-z0-9_-]*)*", value):
        raise ValueError("Asset name must contain semantic names separated by '/'.")
    return value


def game_language(value: str) -> str:
    if type(value) is not str or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", value) or value == "general":
        raise ValueError("A concrete game language is required; 'general' is not supported.")
    return value


class AssetLibrary:
    """读取并验哈希；新文件原子加入共享库，绝不覆盖旧文件。"""

    def __init__(self, data_root: Path) -> None:
        self.data_root = Path(data_root)
        self.root = self.data_root / "assets"

    def path(self, relative: str) -> Path:
        if (type(relative) is not str or not relative or "\\" in relative
                or PurePosixPath(relative).is_absolute() or ".." in relative.split("/")
                or ":" in relative):
            raise ValueError("Asset path must be relative to the Asset Library.")
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError("Asset path escapes the Asset Library.")
        return path

    def read(self, entry: dict[str, str]) -> bytes:
        if type(entry) is not dict or set(entry) != {"path", "sha256"}:
            raise ValueError("Asset entry requires exactly path and sha256.")
        digest = entry["sha256"]
        if type(digest) is not str or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("Asset sha256 must be 64 lowercase hexadecimal characters.")
        content = self.path(entry["path"]).read_bytes()
        if sha256_bytes(content) != digest:
            raise ValueError(f"Asset hash mismatch: {entry['path']}")
        return content

    @staticmethod
    def tags(value: list[str] | None) -> list[str]:
        """校验并复制标签列表，保留输入顺序及重复项；None 表示空列表。"""
        if value is None:
            return []
        if type(value) is not list or any(type(tag) is not str or not tag.strip() for tag in value):
            raise ValueError("Tags must be a list of nonempty strings.")
        return list(value)

    def _tag_mapping(self, name: str) -> dict[str, list[str]]:
        path = self.path(f"{asset_name(name)}/asset-tag.json")
        try:
            mapping = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        if type(mapping) is not dict:
            raise ValueError("asset-tag.json must map full hashes to tag lists.")
        for digest, tags in mapping.items():
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("Asset tag keys must be complete SHA-256 hashes.")
            if type(tags) is not list:
                raise ValueError("Stored Asset tags must be lists.")
            self.tags(tags)
        return mapping

    def _set_tags(self, name: str, digest: str, tags: list[str] | None) -> tuple[list[str], bool]:
        """原子替换完整标签列表；省略标签将其清空。"""
        replacement = self.tags(tags)
        mapping = self._tag_mapping(name)
        unchanged = digest in mapping and mapping[digest] == replacement
        if not unchanged:
            mapping[digest] = replacement
            atomic_write_json(self.path(f"{name}/asset-tag.json"), mapping)
        return replacement, unchanged

    def crop_reference(self, name: str, image: Path) -> dict[str, str]:
        """核对现有本地裁剪及完整哈希，不接受外部图片导入。"""
        from .recognition import decode_image
        asset_name(name)
        relative = Path(image).resolve().relative_to(self.root.resolve()).as_posix()
        digest = Path(relative).stem
        if relative != f"{name}/{digest}.png":
            raise ValueError("Crop image does not belong to this Asset logical name.")
        entry = {"path": relative, "sha256": digest}
        decode_image(self.read(entry))
        for source in sorted((self.data_root / "asset-provenance").glob("*.json")):
            crop = json.loads(source.read_text(encoding="utf-8"))
            if crop["path"] == relative and crop["logical_name"] == name and crop["sha256"] == digest:
                return entry
        raise ValueError("No crop provenance matches this image and Asset name.")

    def set_tags(self, name: str, image: Path, tags: list[str] | None = None) -> dict[str, Any]:
        """覆盖已有裁剪的标签，无需 Candidate、游戏窗口或 Manifest 发布。"""
        self.tags(tags)
        entry = self.crop_reference(name, image)
        replacement, unchanged = self._set_tags(name, entry["sha256"], tags)
        return {"logical_name": name, **entry, "image_path": str(self.path(entry["path"])),
                "tags": replacement, "unchanged": unchanged}

    @staticmethod
    def crop_content(pixels: bytes, size: tuple[int, int], region: dict[str, int]) -> tuple[bytes, dict[str, int]]:
        """在内存编码现场裁剪，确认前不创建文件或来源记录。"""

        import cv2
        from .recognition import checked_region, client_image

        area = checked_region(region, *size)
        image = client_image(pixels, size)
        x, y, w, h = (area[key] for key in ("x", "y", "width", "height"))
        ok, encoded = cv2.imencode(".png", image[y:y + h, x:x + w])
        if not ok:
            raise ValueError("PNG encoding failed.")
        return encoded.tobytes(), area

    def save_crop(
        self, name: str, pixels: bytes, size: tuple[int, int],
        region: dict[str, int], *, run_id: int | None, observation: int,
        tags: list[str] | None = None,
        preserve_existing_tags: bool = False,
    ) -> dict[str, Any]:
        """保存现场裁剪和来源；开发者替换标签，Agent 可要求保留已有图的标签。"""
        asset_name(name)
        self.tags(tags)
        self._tag_mapping(name)
        content, area = self.crop_content(pixels, size, region)
        digest = sha256_bytes(content)
        relative = f"{name}/{digest}.png"
        path = self.path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        existed = path.exists()
        if existed:
            if path.read_bytes() != content:
                raise FileExistsError(f"Asset content differs at full-hash path: {relative}")
        else:
            descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".asset-")
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                try:
                    os.link(temporary, path)
                except FileExistsError:
                    if path.read_bytes() != content:
                        raise FileExistsError(f"Asset content differs at full-hash path: {relative}")
                    existed = True
            finally:
                Path(temporary).unlink(missing_ok=True)
        mapping = self._tag_mapping(name)
        if preserve_existing_tags and (existed or digest in mapping):
            replacement = list(mapping.get(digest, []))
        else:
            replacement, _ = self._set_tags(name, digest, tags)
        provenance_id = uuid.uuid4().hex
        result = {"logical_name": name, "tags": replacement, "path": relative,
                  "sha256": digest, "image_path": str(path), "run_id": run_id,
                  "observation": observation, "region": area,
                  "client_size": {"width": size[0], "height": size[1]},
                  "provenance_id": provenance_id, "created_at": datetime.now(UTC).isoformat()}
        if preserve_existing_tags:
            result["existed"] = existed
        atomic_write_json(self.data_root / "asset-provenance" / f"{provenance_id}.json", result)
        return result

    def remove(self, name: str, digest: str, reason: str, screenshot: bytes, *, checkpoint: Callable[[], None]) -> dict:
        """先完整归档，再移除活跃图片和标签；中途失败回退，归档始终保留恢复数据。"""
        from .recognition import decode_image
        asset_name(name)
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("移除 Asset 必须提供非空理由。")
        relative = f"{name}/{digest}.png"
        content = self.read({"path": relative, "sha256": digest})
        if (self.path(relative) != self.root.resolve() / relative
                or self.path(f"{name}/asset-tag.json") != self.root.resolve() / name / "asset-tag.json"):
            raise ValueError("移除不接受指向其他目录或标签文件的符号链接。")
        decode_image(content)
        decode_image(screenshot)
        if not screenshot.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("归档截图必须是原始 PNG。")
        mapping = self._tag_mapping(name)
        updated = dict(mapping)
        updated.pop(digest, None)
        now = datetime.now(UTC)
        identity = now.strftime("%Y%m%dT%H%M%S%fZ-") + uuid.uuid4().hex
        directory = self.data_root / "agent_removed_asset" / identity
        if not directory.resolve().is_relative_to(self.data_root.resolve()):
            raise ValueError("Asset 归档目录越界。")
        directory.mkdir(parents=True, exist_ok=False)
        record = {"archive_id": identity, "logical_name": name, "sha256": digest,
                  "tags": list(mapping.get(digest, [])), "removed_at": now.isoformat(), "reason": reason,
                  "source_path": relative, "image": "asset.png", "screenshot": "screenshot.png",
                  "archive_path": str(directory), "state": "prepared"}
        # 多文件不能一次原子提交；先保留完整副本与准备记录，进程中断后仍可从此恢复。
        for filename, data in (("asset.png", content), ("screenshot.png", screenshot)):
            with (directory / filename).open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        atomic_write_json(directory / "record.json", record)
        with (directory / "record.json").open("rb") as stream:
            os.fsync(stream.fileno())
        path = self.path(relative)
        tags_changed = removed = False
        try:
            checkpoint()
            if updated != mapping:
                atomic_write_json(self.path(f"{name}/asset-tag.json"), updated)
                tags_changed = True
            path.unlink()
            removed = True
            record["state"] = "completed"
            atomic_write_json(directory / "record.json", record)
        except BaseException:
            try:
                if removed:
                    with path.open("xb") as stream:
                        stream.write(content)
            finally:
                if tags_changed:
                    atomic_write_json(self.path(f"{name}/asset-tag.json"), mapping)
            raise
        return record

    def match(
        self, name: str, pixels: bytes, size: tuple[int, int], *, run_id: int,
        observation: int, emit: Callable[[str, dict[str, Any]], None],
        priority_tags: list[str] | None = None, region: dict[str, int] | None = None,
        threshold: float = 0.9, nms: bool = True, nms_iou_threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """每次读取目录及标签；优先组命中则短路，否则匹配剩余模板。"""
        import math
        from .recognition import checked_region, client_image, decode_image, detect_template, suppress_overlaps
        asset_name(name)
        preferred_tags = self.tags(priority_tags)
        for value in (threshold, nms_iou_threshold):
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("Detection thresholds must be finite and between 0 and 1.")
        if type(nms) is not bool:
            raise ValueError("nms must be bool.")
        directory = self.path(name)
        if not directory.is_dir():
            raise FileNotFoundError(f"Asset logical name does not exist: {name}")
        mapping = self._tag_mapping(name)
        candidates = []
        for path in sorted(directory.glob("*.png")):
            if not re.fullmatch(r"[0-9a-f]{64}", path.stem):
                raise ValueError(f"Asset filename must be a complete SHA-256: {path.name}")
            candidates.append({"path": f"{name}/{path.name}", "sha256": path.stem,
                               "tags": list(mapping.get(path.stem, []))})
        image = client_image(pixels, size)
        area = checked_region(region, *size)
        preferred = [entry for entry in candidates if set(entry["tags"]) & set(preferred_tags)]
        remaining = [entry for entry in candidates if not set(entry["tags"]) & set(preferred_tags)]
        attempted = []
        output = []
        batch = "remaining"
        for label, entries in (("preferred", preferred), ("remaining", remaining)):
            detections = []
            for entry in entries:
                attempted.append(entry)
                template = decode_image(self.read({key: entry[key] for key in ("path", "sha256")}))
                # 跨模板统一 NMS，避免先抑制同模板的框导致最终结果丢失。
                found = detect_template(image, template, region=area, threshold=threshold, nms=False)
                for detection in found:
                    normalized = {key: value / (size[0] if key in {"x", "width"} else size[1])
                                  for key, value in detection.items() if key != "score"}
                    detections.append({**detection, **entry,
                                       "centerxy": (detection["x"] + detection["width"] // 2,
                                                    detection["y"] + detection["height"] // 2),
                                       "normalized_region": normalized,
                                       "logical_name": name, "observation": observation})
            if detections:
                detections.sort(key=lambda d: (-d["score"], d["y"], d["x"], d["sha256"]))
                output = suppress_overlaps(detections, nms_iou_threshold) if nms else detections
                batch = label
                break
        event = {"logical_name": name, "run_id": run_id, "observation": observation,
                 "search_region": area, "trace_path": f"traces/{run_id}.jsonl",
                 "threshold": threshold, "nms": nms, "nms_iou_threshold": nms_iou_threshold,
                 "priority_tags": preferred_tags, "matched_batch": batch,
                 "templates": attempted, "detections": output}
        emit("asset_matched", event)
        if output:
            index_path = self.data_root / "asset-usage.json"
            index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
            index[name] = {**event, "last_used_at": datetime.now(UTC).isoformat()}
            atomic_write_json(index_path, index)
        return output
