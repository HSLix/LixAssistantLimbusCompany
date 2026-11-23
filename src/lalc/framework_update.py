"""查询框架版本，下载经过校验的完整程序包并交给 Windows 更新进程。"""

from dataclasses import dataclass
import hashlib
from http.client import HTTPException
from importlib.metadata import PackageNotFoundError, version as distribution_version
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import stat
import subprocess
import sys
import tomllib
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import zipfile

from .agent_settings import dpapi, save_secret, secret_path
from .work_files import create_work_directory

REPOSITORY = "HSLix/LixAssistantLimbusCompany"
REPOSITORY_URL = f"https://github.com/{REPOSITORY}"
CDK_SECRET = "lalc-mirrorchyan-cdk"
VERSION_PATTERN = r"v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
REQUIRED_FILES = ("LALC.exe", "LALC-console.exe", "build-info.json", "install-update.ps1",
                  "_internal/lalc/translations/lalc_zh_CN.qm")


class UpdateRedirects(HTTPRedirectHandler):
    """下载允许跨站 HTTPS 跳转；带 CDK 的查询只发往 Mirror酱。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        destination = urlsplit(newurl)
        mirror_query = req.host == "mirrorchyan.com" and urlsplit(req.full_url).path.startswith("/api/resources/")
        if destination.scheme != "https" or (mirror_query and destination.netloc != req.host):
            raise ValueError("Unexpected update redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


urlopen = build_opener(UpdateRedirects()).open


@dataclass(frozen=True)
class Package:
    """只持有本次请求返回的完整包信息。"""

    version: tuple[int, int, int]
    url: str
    sha256: str


@dataclass(frozen=True)
class ReleaseStatus:
    """公告和两个渠道的版本可独立取得。"""

    announcement: str | None
    github: Package | None
    mirror: tuple[int, int, int] | None


def version_number(value):
    match = re.fullmatch(VERSION_PATTERN, value) if isinstance(value, str) else None
    return tuple(map(int, match.groups())) if match else None


def installed_build():
    """以随包交付的版本为准，源码运行时读取项目元数据。"""
    if getattr(sys, "frozen", False):
        try:
            build = json.loads((Path(sys.executable).parent / "build-info.json").read_text(encoding="utf-8"))
            if version_number(build["version"]):
                return build
        except (OSError, ValueError, KeyError, TypeError):
            pass
        return {"version": ""}
    project = Path(__file__).resolve().parents[2] / "pyproject.toml"
    if project.is_file():
        return {"version": tomllib.loads(project.read_text(encoding="utf-8"))["project"]["version"]}
    try:
        return {"version": distribution_version("lix-assistant-limbus-company")}
    except PackageNotFoundError:
        return {"version": ""}


def installed_variant(directory):
    return "with-agent" if (directory / "agent/codesearch.exe").is_file() else "without-agent"


def set_mirror_cdk(root, value):
    """保存或清除当前用户的加密下载凭证。"""
    if value := value.strip():
        save_secret(root, CDK_SECRET, value)
    else:
        secret_path(root, CDK_SECRET).unlink(missing_ok=True)


def _read_cdk(root):
    try:
        return dpapi(secret_path(root, CDK_SECRET).read_bytes(), decrypt=True).decode("utf-8")
    except FileNotFoundError:
        return ""


def _json(url):
    github = urlsplit(url).hostname == "api.github.com"
    request = Request(url, headers={"User-Agent": "LALC", "Cache-Control": "no-cache",
                                    "Accept": "application/vnd.github+json" if github else "application/json"})
    with urlopen(request, timeout=8) as response:
        content = response.read(2 * 1024 * 1024 + 1)
    if len(content) > 2 * 1024 * 1024:
        raise ValueError("Release metadata is too large")
    value = json.loads(content)
    if not isinstance(value, dict):
        raise ValueError("Expected a release object")
    return value


def _github(variant):
    data = _json(f"https://api.github.com/repos/{REPOSITORY}/releases/latest")
    announcement = data.get("body")
    tag = data.get("tag_name")
    version = version_number(tag)
    package = None
    assets = data.get("assets")
    if version and version[0] >= 6 and isinstance(assets, list):
        name = f"LALC-{'.'.join(map(str, version))}-windows-x64-{variant}.zip"
        for asset in assets:
            if not isinstance(asset, dict) or asset.get("name") != name:
                continue
            digest = asset.get("digest")
            if isinstance(digest, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
                package = Package(version, f"{REPOSITORY_URL}/releases/download/{tag}/{name}", digest[7:])
                break
    return (announcement if isinstance(announcement, str) else ""), package


def _mirror(config, cdk=""):
    rid = config.get("rid") if isinstance(config, dict) else None
    if not isinstance(rid, str) or not re.fullmatch(r"[a-zA-Z0-9_-]+", rid):
        return {}
    params = {"user_agent": "LALC", "channel": "stable", "cdk": cdk,
              "os": config.get("os"), "arch": config.get("arch")}
    query = urlencode({key: value for key, value in params.items() if value})
    response = _json(f"https://mirrorchyan.com/api/resources/{rid}/latest?{query}")
    if response.get("code") != 0 or not isinstance(response.get("data"), dict):
        return {}
    return response["data"]


def check_releases(variant, mirror):
    """单个服务不可用时仍返回另一方的结果。"""
    try:
        announcement, github = _github(variant)
    except (OSError, ValueError, TypeError, AttributeError, HTTPException):
        announcement, github = None, None
    try:
        mirror_version = version_number(_mirror(mirror).get("version_name"))
    except (OSError, ValueError, TypeError, HTTPException):
        mirror_version = None
    return ReleaseStatus(announcement, github, mirror_version if mirror_version and mirror_version[0] >= 6 else None)


def _extract(archive, destination, cancelled=lambda: False):
    """检查 Windows 路径、文件类型和大小，再在独立目录中解压。"""
    with zipfile.ZipFile(archive) as bundle:
        paths = set()
        for entry in bundle.infolist():
            parts = entry.filename.removesuffix("/").split("/")
            mode = stat.S_IFMT(entry.external_attr >> 16)
            if (entry.orig_filename != entry.filename or parts[0] != "LALC" or len(parts) == 1 and not entry.is_dir() or
                    any(not part or part in {".", ".."} or part.endswith((".", " ")) or
                        PureWindowsPath(part).is_reserved() or re.search(r'[\\:<>"|?*\x00-\x1f]', part) for part in parts) or
                    mode not in (0, stat.S_IFDIR if entry.is_dir() else stat.S_IFREG)):
                raise ValueError("Unsafe update archive")
            key = entry.filename.removesuffix("/").casefold()
            if key in paths:
                raise ValueError("Duplicate update archive entry")
            paths.add(key)
        if sum(entry.file_size for entry in bundle.infolist()) > shutil.disk_usage(destination).free:
            raise OSError("Insufficient disk space to extract the update")
        for entry in bundle.infolist():
            if cancelled():
                raise InterruptedError
            bundle.extract(entry, destination)


def _prepare(package, workspace, variant, cancelled):
    archive = workspace / "download.zip"
    try:
        digest = hashlib.sha256()
        request = Request(package.url, headers={"User-Agent": "LALC"})
        with urlopen(request, timeout=30) as response, archive.open("xb") as output:
            if urlsplit(response.geturl()).scheme != "https":
                raise ValueError("Download requires HTTPS")
            while chunk := response.read(1024 * 1024):
                if cancelled():
                    raise InterruptedError
                output.write(chunk)
                digest.update(chunk)
        if digest.hexdigest() != package.sha256:
            raise ValueError("Update checksum mismatch")
        _extract(archive, workspace, cancelled)
        payload = workspace / "LALC"
        if not all((payload / name).is_file() for name in REQUIRED_FILES):
            raise ValueError("Incomplete update package")
        build = json.loads((payload / "build-info.json").read_text(encoding="utf-8"))
        if version_number(build["version"]) != package.version or installed_variant(payload) != variant:
            raise ValueError("Unexpected update version or variant")
    finally:
        archive.unlink(missing_ok=True)


def prepare_update(root, status, target_version, variant, mirror, cancelled=lambda: False):
    """优先尝试同版镜像完整包，失败则向 GitHub 取同一版。"""
    providers = []
    if variant == "with-agent" and status.mirror == target_version:
        try:
            if cdk := _read_cdk(root):
                data = _mirror(mirror, cdk)
                url, digest = data.get("url", ""), data.get("sha256", "")
                if (version_number(data.get("version_name")) == target_version and data.get("update_type") == "full"
                        and urlsplit(url).scheme == "https" and re.fullmatch(r"[0-9a-fA-F]{64}", digest)):
                    providers.append(Package(target_version, url, digest.lower()))
        except (OSError, ValueError, TypeError, HTTPException):
            pass
    if status.github and status.github.version == target_version:
        providers.append(status.github)
    for package in providers:
        if cancelled():
            break
        work = root / "work"
        work.mkdir(parents=True, exist_ok=True)
        workspace = Path(create_work_directory(dir=work, prefix="framework-update-"))
        try:
            _prepare(package, workspace, variant, cancelled)
            shutil.copyfile(Path(sys.executable).parent / "install-update.ps1", workspace / "install-update.ps1")
            return workspace
        except (OSError, ValueError, KeyError, TypeError, HTTPException, zipfile.BadZipFile, NotImplementedError):
            shutil.rmtree(workspace, ignore_errors=True)
    # 下载地址可能携带 CDK 或时效凭证，只向界面报告固定错误信息。
    return None


def hand_off_update(workspace, windows):
    """清理 GUI 后启动目录外的更新进程，由它等待本进程退出。"""
    import ctypes

    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    target = Path(sys.executable).parent
    try:
        # 退出阶段不再载入程序 DLL，系统 PowerShell 应使用自己的依赖。
        ctypes.windll.kernel32.SetDllDirectoryW(None)
        subprocess.Popen([str(powershell), "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                          str(workspace / "install-update.ps1"), "-Source", str(workspace / "LALC"),
                          "-Target", str(target), "-ParentProcessId", str(os.getpid()),
                          "-RestoreGui", ",".join(windows)], cwd=target.parent, creationflags=subprocess.CREATE_NEW_CONSOLE,
                         env={**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"})
    except OSError:
        shutil.rmtree(workspace, ignore_errors=True)
        raise


def confirm_update_start(nonce):
    """窗口进入事件循环后，确认更新进程可以保留新安装。"""
    import ctypes
    from ctypes import wintypes

    if not re.fullmatch(r"[0-9a-f]{32}", nonce):
        raise ValueError("Invalid update confirmation")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.OpenEventW.restype = wintypes.HANDLE
    kernel.SetEvent.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenEventW(2, False, "Local\\LALC-update-" + nonce)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not kernel.SetEvent(handle):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.CloseHandle(handle)
