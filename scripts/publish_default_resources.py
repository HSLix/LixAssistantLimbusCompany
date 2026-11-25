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
RELEASE_TAG = re.compile(r"v(?:[6-9]|[1-9][0-9]+)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(-beta\.[1-9][0-9]*)?")


def resolve_release_tag(repo, tag, target):
    """从 GitHub 确定实际发布标签，避免把手填标签与自动选择混用。"""
    tag = tag.strip()
    if target == "指定 Release":
        if not tag:
            raise ValueError("选择「指定 Release」时必须填写目标标签。")
        return tag
    if tag:
        raise ValueError("选择最新版本时请留空目标标签。")
    endpoint = f"repos/{repo}/releases"
    if target == "最新正式版":
        release = json.loads(subprocess.check_output(["gh", "api", f"{endpoint}/latest"], text=True))
        match = RELEASE_TAG.fullmatch(release["tag_name"])
        if not match or match[1]:
            raise ValueError(f"GitHub 当前最新正式版 {release['tag_name']} 不是受支持的 LALC 正式版。")
        return release["tag_name"]
    if target == "最新 Beta":
        pages = json.loads(subprocess.check_output(
            ["gh", "api", "--paginate", "--slurp", endpoint], text=True))
        candidates = []
        for page in pages:
            for release in page:
                if release["draft"] or not release["prerelease"] or not release["published_at"]:
                    continue
                match = RELEASE_TAG.fullmatch(release["tag_name"])
                if match and match[1]:
                    candidates.append(release)
        if not candidates:
            raise ValueError("找不到已发布的 LALC 6 或更新版本的 Beta Release。")
        return max(candidates, key=lambda release: (release["published_at"], release["id"]))["tag_name"]
    raise ValueError(f"无效的 Release 选择方式：{target}")


def publish(repo, tag, target="指定 Release"):
    """追加新附件。重跑时核对远端摘要并保留现有附件。"""
    tag = resolve_release_tag(repo, tag, target)
    if not RELEASE_TAG.fullmatch(tag):
        raise ValueError("目标必须是已发布的 LALC 6 或更新版本的 Release 标签。")
    print(f"目标 Release：{tag}", flush=True)
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
