"""将已提交并验证的默认资源包追加到指定的 GitHub Release。"""

from contextlib import closing
from hashlib import file_digest
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

from lalc.default_resources import DEFAULT_RESOURCE_NAME, check_default_package
from lalc.resource_version import read_resource_version, resource_asset_name
from lalc.sharing import SharingPackage
from lalc.work_files import WorkDirectory

ROOT = Path(__file__).resolve().parents[1]


def publish(repo, tag):
    """追加新附件。重跑时核对远端摘要并保留现有附件。"""
    if not re.fullmatch(r"v([6-9]|[1-9][0-9]+)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-beta\.[1-9][0-9]*)?", tag):
        raise ValueError("目标必须是已发布的 LALC 6 或更新版本的 Release 标签。")
    source = ROOT / "packaging" / DEFAULT_RESOURCE_NAME
    if not source.is_file() or source.is_symlink():
        raise ValueError(f"缺少可发布的默认资源 ZIP：{source}")
    metadata = source.with_suffix(".txt")
    if not metadata.is_file() or metadata.is_symlink():
        raise ValueError(f"缺少默认资源导出时间文件：{metadata}")
    with WorkDirectory(dir=ROOT, prefix=".resource-release-") as directory:
        directory = Path(directory)
        archive = directory / source.name
        shutil.copyfile(source, archive)
        shutil.copyfile(metadata, archive.with_suffix(".txt"))
        version = read_resource_version(archive)
        with closing(SharingPackage(archive, directory)) as package:
            check_default_package(package)
        asset = archive.rename(directory / resource_asset_name(version))
        with asset.open("rb") as stream:
            digest = "sha256:" + file_digest(stream, "sha256").hexdigest()
        release = json.loads(subprocess.check_output(
            ["gh", "api", f"repos/{repo}/releases/tags/{tag}"], text=True))
        if release["draft"]:
            raise ValueError(f"请先发布目标 Release：{tag}")
        for existing in release["assets"]:
            if existing["name"] == asset.name:
                if existing.get("digest") != digest or existing.get("state") != "uploaded":
                    raise ValueError(f"{tag} 已有同名附件，且无法确认内容一致：{asset.name}")
                print(f"{tag} 已有相同资源附件：{asset.name}")
                return
        subprocess.run(["gh", "release", "upload", tag, str(asset), "--repo", repo], check=True)
        print(f"已追加到 {tag}：{asset.name}")


if __name__ == "__main__":
    publish(*sys.argv[1:])
