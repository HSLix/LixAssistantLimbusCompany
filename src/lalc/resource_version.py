"""读取默认资源包的导出版本并核对同一次导出的 ZIP。"""

from datetime import datetime, timezone
from hashlib import file_digest
import re

RESOURCE_VERSION_FORMAT = "%Y%m%dT%H%M%SZ"
RESOURCE_VERSION_PATTERN = r"[0-9]{8}T[0-9]{6}Z"


def parse_resource_version(version):
    """解析精确到秒的 UTC 资源版本。"""
    if not re.fullmatch(RESOURCE_VERSION_PATTERN, version):
        raise ValueError(f"无效的资源版本：{version}")
    return datetime.strptime(version, RESOURCE_VERSION_FORMAT).replace(tzinfo=timezone.utc)


def read_resource_version(archive):
    """校验时间文本与 ZIP 的对应关系，拒绝缺失或混用的导出文件。"""
    metadata = archive.with_suffix(".txt")
    if not metadata.is_file() or metadata.is_symlink():
        raise ValueError(f"缺少默认资源导出时间文件：{metadata}")
    lines = metadata.read_text(encoding="ascii").splitlines()
    if len(lines) != 2:
        raise ValueError(f"默认资源时间文件应依次包含 UTC 导出时间与 SHA-256：{metadata}")
    version, digest = lines
    parse_resource_version(version)
    with archive.open("rb") as stream:
        if file_digest(stream, "sha256").hexdigest() != digest:
            raise ValueError(f"默认资源 ZIP 与导出时间文件的 SHA-256 不匹配：{archive}")
    return version


def resource_asset_name(version):
    return f"default-resources-{version}.zip"
