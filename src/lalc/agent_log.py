"""对话内无损日志去重与诊断展开；不迁移旧日志，不改变模型传输内容。"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile


FORMAT = {"format": "lalc-agent-log", "version": 1}
MARKER = "$lalc_log"


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class LogStore:
    """以固定对话根目录保存不可变内容；先完成内容写入，再允许写引用。"""

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.images = {}
        self.written = set()

    def initialize(self):
        with (self.root / "log-format.json").open("x", encoding="utf-8") as stream:
            json.dump(FORMAT, stream)

    def _path(self, relative):
        if (not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative
                or Path(relative).is_absolute() or ".." in Path(relative).parts):
            raise ValueError("日志引用必须是对话内的相对路径。")
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("日志引用越出对话目录。")
        return path

    def register_image(self, path):
        """引用已留存的原图文件，避免另存一份 Base64 或二进制副本。"""
        relative = Path(path).resolve().relative_to(self.root).as_posix()
        digest = hashlib.sha256(self._path(relative).read_bytes()).hexdigest()
        self.images.setdefault(digest, relative)

    def _put(self, content, kind):
        """按字节哈希原子加入内容对象，不覆盖既有同名内容。"""
        digest = hashlib.sha256(content).hexdigest()
        relative = f"objects/{digest}.{kind}"
        if relative not in self.written:
            path = self._path(relative)
            path.parent.mkdir(exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".pending-")
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                try:
                    os.link(temporary, path)
                except FileExistsError:
                    if path.read_bytes() != content:
                        raise ValueError(f"日志内容损坏：{relative}")
            finally:
                Path(temporary).unlink(missing_ok=True)
            self.written.add(relative)
        return {MARKER: {"path": relative, "sha256": digest, "kind": kind}}

    def _image(self, data, prefix=""):
        try:
            content = base64.b64decode(data, validate=True)
        except (ValueError, TypeError):
            return None
        # 非标准 Base64 原样作为普通文本保存，不通过重新编码改变原始字符串。
        if base64.b64encode(content).decode() != data:
            return None
        digest = hashlib.sha256(content).hexdigest()
        if digest in self.images:
            reference = {"path": self.images[digest], "sha256": digest, "kind": "bin"}
        else:
            reference = self._put(content, "bin")[MARKER]
        return {MARKER: {**reference, "base64": True, "prefix": prefix}}

    def pack(self, value, *, inline=True):
        """保留普通字段与顺序，仅用可辨识引用替代重复的大块内容。"""
        if isinstance(value, str):
            match = re.match(r"^(data:image/[^;,]+;base64,)(.*)$", value, re.DOTALL)
            if match:
                image = self._image(match[2], match[1])
                if image is not None:
                    return image
            return self._put(value.encode("utf-8"), "txt") if len(value.encode("utf-8")) >= 1024 else value
        if isinstance(value, list):
            packed = [self.pack(item, inline=False) for item in value]
        elif isinstance(value, dict):
            packed = {}
            for key, item in value.items():
                image = self._image(item) if key == "data" and value.get("type") == "image" and isinstance(item, str) else None
                packed[key] = image if image is not None else self.pack(item, inline=inline and key == "event")
            # 用户数据可能本来就含标记键，显式转义，不能误当成本地文件引用。
            if MARKER in value:
                packed = {MARKER: {"literal": [[key, item] for key, item in packed.items()]}}
        else:
            return value
        content = _json_bytes(packed)
        return self._put(content, "json") if not inline and len(content) >= 1024 else packed

    def unpack(self, value, *, _active=None):
        """完整展开并验哈希；缺失、损坏、循环或越界引用一律明确失败。"""
        active = set() if _active is None else _active
        if isinstance(value, list):
            return [self.unpack(item, _active=active) for item in value]
        if not isinstance(value, dict):
            return value
        if set(value) == {MARKER}:
            reference = value[MARKER]
            if not isinstance(reference, dict):
                raise ValueError("日志引用格式错误。")
            if set(reference) == {"literal"}:
                pairs = reference["literal"]
                if (not isinstance(pairs, list) or any(not isinstance(pair, list) or len(pair) != 2
                        or not isinstance(pair[0], str) for pair in pairs)
                        or len({pair[0] for pair in pairs}) != len(pairs)):
                    raise ValueError("日志字面量转义格式错误。")
                return {key: self.unpack(item, _active=active) for key, item in pairs}
            path = self._path(reference.get("path"))
            if path in active:
                raise ValueError("日志存在循环引用。")
            try:
                content = path.read_bytes()
            except OSError as error:
                raise ValueError(f"日志引用不可用：{reference.get('path')}") from error
            if hashlib.sha256(content).hexdigest() != reference.get("sha256"):
                raise ValueError(f"日志引用哈希不符：{reference.get('path')}")
            kind = reference.get("kind")
            if kind == "bin" and reference.get("base64") is True:
                prefix = reference.get("prefix", "")
                if not isinstance(prefix, str):
                    raise ValueError("日志图片前缀格式错误。")
                return prefix + base64.b64encode(content).decode()
            if kind == "txt":
                return content.decode("utf-8")
            if kind == "json":
                return self.unpack(json.loads(content), _active=active | {path})
            raise ValueError("未知日志引用类型。")
        return {key: self.unpack(item, _active=active) for key, item in value.items()}

    def write_json(self, path, value):
        """原子替换日志文档；内容对象失败时不发布新的引用文档。"""
        target = self._path(Path(path).resolve().relative_to(self.root).as_posix())
        content = _json_bytes(self.pack(value))
        descriptor, temporary = tempfile.mkstemp(dir=target.parent, prefix=".pending-")
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
            Path(temporary).replace(target)
        finally:
            Path(temporary).unlink(missing_ok=True)


def _store_for(path):
    path = Path(path).absolute()
    for parent in path.parents:
        marker = parent / "log-format.json"
        if marker.is_file():
            if json.loads(marker.read_text(encoding="utf-8")) != FORMAT:
                raise ValueError("不支持该日志格式。")
            store = LogStore(parent)
            store._path(path.relative_to(parent).as_posix())
            return store
    raise ValueError("未找到新格式对话日志；旧日志不会自动迁移或读取。")


def read_json(path):
    """供诊断与测试按需展开一个新格式 JSON 文件。"""
    store = _store_for(path)
    return store.unpack(json.loads(Path(path).read_text(encoding="utf-8")))


def read_events(path):
    """逐条展开事件，保留每个重复事件的顺序与身份。"""
    store = _store_for(path)
    with Path(path).open(encoding="utf-8") as stream:
        for line in stream:
            yield store.unpack(json.loads(line))


def main():
    parser = argparse.ArgumentParser(description="Expand one new-format Agent log JSON/JSONL file for diagnosis")
    parser.add_argument("path", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    created = False
    try:
        if args.path.suffix == ".jsonl":
            records = read_events(args.path)
        else:
            records = [read_json(args.path)]
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                created = True
                for value in records:
                    stream.write(json.dumps(value, ensure_ascii=False) + "\n")
        else:
            for value in records:
                print(json.dumps(value, ensure_ascii=False))
    except (ValueError, OSError) as error:
        if created:
            args.output.unlink(missing_ok=True)
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
