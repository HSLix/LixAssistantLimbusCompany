"""在 Windows x64 本地构建同源双包；不收集用户数据，不调用 pi 或模型。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PI_VERSION = "1.4.0"
PI_SHA256 = "0f7256ea8bdac3af20012b94fdc1252a31cc6dc0d2f9b9eb539555d22e3e321b"
PI_URL = "https://github.com/earendil-works/pi/releases/download/v1.4.0/pi-windows-x64.zip"


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def check_pi(archive: Path) -> None:
    """只接受固定官方归档；校验所有路径后才允许解压。"""
    if digest(archive) != PI_SHA256:
        raise ValueError("pi ZIP 与官方 1.4.0 Windows x64 摘要不一致，请勿重压缩或替换内容。")
    with zipfile.ZipFile(archive) as bundle:
        for item in bundle.infolist():
            path = PurePosixPath(item.filename)
            if (path.is_absolute() or ".." in path.parts or "\\" in item.filename or
                    ":" in item.filename or item.external_attr >> 16 & 0o170000 == 0o120000):
                raise ValueError(f"Unsafe pi archive path: {item.filename}")
        metadata = json.loads(bundle.read("package.json"))
        if metadata.get("version") != PI_VERSION or "pi.exe" not in bundle.namelist():
            raise ValueError("Expected pi 1.4.0 Windows binary and metadata")


def file_manifest(directory: Path, *, exclude_pi=False) -> dict[str, str]:
    """以相对路径和内容摘要核对两个包的公共文件。"""
    result = {}
    for path in sorted(directory.rglob("*")):
        relative = path.relative_to(directory)
        if exclude_pi and relative.parts[0] == "pi":
            continue
        if path.is_file():
            result[relative.as_posix()] = digest(path)
    return result


def source_snapshot() -> dict:
    """记录实际源码内容；忽略目录不会进入源码快照或归档。"""
    names = subprocess.check_output(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT)
    files = {name: digest(ROOT / name) for name in sorted(set(names.decode("utf-8").split("\0")))
             if name and (ROOT / name).is_file()}
    content = json.dumps(files, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return {"commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "files_sha256": hashlib.sha256(content).hexdigest(), "files": files}


def assemble(application: Path, archive: Path, destination: Path, info: dict) -> list[Path]:
    """只复制冻结产物，另加官方 pi 目录；全部校验完成后替换输出 ZIP。"""
    check_pi(archive)
    for relative in ("LALC.exe", "LALC-console.exe", "_internal/lalc/pi_probe.ts",
                     "_internal/lalc/translations/lalc_zh_CN.qm", "_internal/PySide6/translations/qtbase_zh_CN.qm"):
        if not (application / relative).is_file():
            raise ValueError(f"Missing packaged resource: {relative}")
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lalc-release-", dir=destination) as directory:
        stage = Path(directory)
        base = stage / "without-pi" / "LALC"
        shutil.copytree(application, base)
        (base / "Developer.cmd").write_bytes(b'@echo off\r\nstart "" "%~dp0LALC.exe" --developer\r\n')
        (base / "build-info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        with_pi = stage / "with-pi" / "LALC"
        shutil.copytree(base, with_pi)
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(with_pi / "pi")
        shutil.copyfile(ROOT / "packaging/pi-LICENSE.txt", with_pi / "pi/LICENSE.txt")
        if file_manifest(base) != file_manifest(with_pi, exclude_pi=True):
            raise ValueError("Two packages have different application files")
        names = [f"LALC-{info['version']}-windows-x64", f"LALC-{info['version']}-windows-x64-with-pi"]
        outputs = []
        for name, source in zip(names, (base, with_pi)):
            output = stage / f"{name}.zip"
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
                for path in sorted(source.rglob("*")):
                    if path.is_file():
                        bundle.write(path, "LALC/" + path.relative_to(source).as_posix())
            outputs.append(output)
        checksums = "".join(f"{digest(path)}  {path.name}\n" for path in outputs)
        for path in outputs:
            path.replace(destination / path.name)
        (destination / "SHA256SUMS").write_text(checksums, encoding="utf-8")
    return [destination / f"{name}.zip" for name in names]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pi-zip", type=Path, default=ROOT / "pi_resources/pi-windows-x64.zip")
    args = parser.parse_args(argv)
    if sys.platform != "win32" or platform.machine().lower() not in {"amd64", "x86_64"}:
        parser.error("请在 Windows x64 构建，macOS 不能交叉生成该成品。")
    archive = args.pi_zip.resolve(strict=True)
    check_pi(archive)
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    if f"StringStruct('ProductVersion', '{version}.0')" not in (ROOT / "LALC.version").read_text(encoding="utf-8"):
        raise ValueError("LALC.version and pyproject.toml versions differ")
    work = ROOT / ".generated/windows-build"
    env = {**os.environ, "UV_PROJECT_ENVIRONMENT": str(work / "venv")}
    subprocess.run(["uv", "sync", "--locked", "--no-editable", "--no-default-groups", "--group", "build", "--all-extras"],
                   cwd=ROOT, env=env, check=True)
    subprocess.run(["uv", "run", "--no-sync", "pyinstaller", "--clean", "--noconfirm", "--distpath", str(work / "dist"),
                    "--workpath", str(work / "build"), str(ROOT / "LALC.spec")], cwd=ROOT, env=env, check=True)
    installed = json.loads(subprocess.check_output(
        ["uv", "run", "--no-sync", "python", "-c",
         "import sys,json,importlib.metadata as m; print(json.dumps({'python':sys.version,'packages':"
         "{d.metadata['Name']:d.version for d in m.distributions()}}))"], cwd=ROOT, env=env, text=True, encoding="utf-8"))
    info = {"version": version, "source": source_snapshot(), "uv_lock_sha256": digest(ROOT / "uv.lock"),
            "environment": installed,
            "pi": {"version": PI_VERSION, "archive_sha256": PI_SHA256, "source": PI_URL}}
    for path in assemble(work / "dist/LALC", archive, ROOT / "dist", info):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
