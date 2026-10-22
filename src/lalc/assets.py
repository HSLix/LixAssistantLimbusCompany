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

    def validate(self, mapping: dict[str, Any]) -> dict[str, Any]:
        """校验完整映射及所有文件；技术错误交给 Manifest 层保留原始原因。"""

        from .recognition import decode_image

        if type(mapping) is not dict:
            raise ValueError("Asset Library must be an object.")
        result = {}
        for name, languages in mapping.items():
            asset_name(name)
            if type(languages) is not dict or not languages:
                raise ValueError("Each Asset requires at least one language mapping.")
            result[name] = {}
            for language, entry in languages.items():
                game_language(language)
                decode_image(self.read(entry))
                result[name][language] = dict(entry)
        return result

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
        self, name: str, language: str, pixels: bytes, size: tuple[int, int],
        region: dict[str, int], *, run_id: int | None, observation: int,
    ) -> dict[str, Any]:
        """保存现场截图的裁剪和来源；相同内容可复用，失败不删除已经保存的文件。"""

        asset_name(name)
        game_language(language)
        content, area = self.crop_content(pixels, size, region)
        digest = sha256_bytes(content)
        relative = f"{name}-{language}-{digest}.png"
        path = self.path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
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
            finally:
                Path(temporary).unlink(missing_ok=True)
        provenance_id = uuid.uuid4().hex
        result = {"logical_name": name, "source_language": language, "path": relative,
                  "sha256": digest, "image_path": str(path), "run_id": run_id,
                  "observation": observation, "region": area,
                  "client_size": {"width": size[0], "height": size[1]},
                  "provenance_id": provenance_id, "created_at": datetime.now(UTC).isoformat()}
        atomic_write_json(self.data_root / "asset-provenance" / f"{provenance_id}.json", result)
        return result

    def match(
        self, mapping: dict[str, Any], name: str, language: str, pixels: bytes,
        size: tuple[int, int], *, run_id: int, observation: int,
        emit: Callable[[str, dict[str, Any]], None], region: dict[str, int] | None = None,
        threshold: float = 0.9, nms: bool = True, nms_iou_threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """匹配语义名；语言回退不改 Manifest，非空结果直接更新 Usage Index。"""

        from .recognition import checked_region, client_image, decode_image, detect_template

        asset_name(name)
        game_language(language)
        languages = mapping[name]
        selected = [(language, languages[language])] if language in languages else sorted(
            languages.items(), key=lambda item: (item[1]["path"], item[0]),
        )
        image = client_image(pixels, size)
        area = checked_region(region, *size)
        matches = []
        for source_language, entry in selected:
            template = decode_image(self.read(entry))
            detections = detect_template(image, template, region=area, threshold=threshold,
                                         nms=nms, nms_iou_threshold=nms_iou_threshold)
            if detections:
                matches.append((detections[0]["score"], entry["path"], source_language, entry, detections))
        identity = {"logical_name": name, "running_language": language, "run_id": run_id,
                    "observation": observation, "search_region": area,
                    "trace_path": f"traces/{run_id}.jsonl", "threshold": threshold,
                    "nms": nms, "nms_iou_threshold": nms_iou_threshold}
        if not matches:
            emit("asset_matched", {**identity, "detections": []})
            return []
        _, _, source_language, entry, detections = min(matches, key=lambda item: (-item[0], item[1], item[2]))
        output = []
        for detection in detections:
            normalized = {key: value / (size[0] if key in {"x", "width"} else size[1])
                          for key, value in detection.items() if key != "score"}
            output.append({**detection, "normalized_region": normalized, "logical_name": name,
                           "running_language": language, "source_language": source_language, **entry,
                           "observation": observation})
        event = {**identity, "source_language": source_language, **entry, "detections": output}
        emit("asset_matched", event)
        index_path = self.data_root / "asset-usage.json"
        index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
        key = json.dumps([name, language, entry["sha256"]], ensure_ascii=False)
        index[key] = {**event, "last_used_at": datetime.now(UTC).isoformat()}
        atomic_write_json(index_path, index)
        return output
