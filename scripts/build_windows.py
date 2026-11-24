"""构建同源 Windows 双包和旧版迁移包，校验打包资源。"""

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
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lalc.work_files import WorkDirectory
from lalc.ocr import MODEL_HASHES
from lalc.codesearch import MODEL_REPO, MODEL_REVISION, MODEL_FILES
from lalc.agent_skills import DEFAULT_SKILL_NAMES

PI_VERSION = "1.5.0"
PI_SHA256 = "12d58a70e80b16ba9f764950b7a42bdeb07959495c0db68396cf2988c0b71af3"
CODESEARCH_VERSION = "1.7.9"
CODESEARCH_SHA256 = "235d47228f53b6cc822a6cf924f83011aefc0f098fd8fb9f8f8c8f9091e20f6a"
CODESEARCH_ARCHIVE = ROOT / "codesearch_resources/codesearch-windows-x86_64.zip"
MODEL_ROOT = ROOT / "codesearch_resources/models"

PI_URL = f"https://github.com/earendil-works/pi/releases/download/v{PI_VERSION}/pi-windows-x64.zip"


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def check_pi(archive: Path) -> None:
    """只接受固定官方归档；校验所有路径后才允许解压。"""
    if digest(archive) != PI_SHA256:
        raise ValueError(f"pi ZIP 与官方 {PI_VERSION} Windows x64 摘要不一致，请勿重压缩或替换内容。")
    with zipfile.ZipFile(archive) as bundle:
        for item in bundle.infolist():
            path = PurePosixPath(item.filename)
            if (item.orig_filename != item.filename or path.is_absolute() or ".." in path.parts or "\\" in item.filename or
                    ":" in item.filename or item.external_attr >> 16 & 0o170000 == 0o120000):
                raise ValueError(f"Unsafe pi archive path: {item.filename}")
        metadata = json.loads(bundle.read("package.json"))
        if metadata.get("version") != PI_VERSION or "pi.exe" not in bundle.namelist():
            raise ValueError(f"Expected pi {PI_VERSION} Windows binary and metadata")


def file_manifest(directory: Path, *, exclude_pi=False) -> dict[str, str]:
    """以相对路径和内容摘要核对两个包的公共文件。"""
    result = {}
    for path in sorted(directory.rglob("*")):
        relative = path.relative_to(directory)
        if exclude_pi and relative.parts[0] in {"pi", "agent"}:
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


def check_codesearch(archive: Path, models: Path) -> None:
    """固定程序与模型哈希；不接受辅助程序或不安全归档路径。"""
    if digest(archive) != CODESEARCH_SHA256:
        raise ValueError("codesearch ZIP 摘要不符。")
    with zipfile.ZipFile(archive) as bundle:
        if bundle.namelist() != ["codesearch.exe"]:
            raise ValueError("codesearch 基础归档必须仅包含 codesearch.exe。")
        if bundle.infolist()[0].external_attr >> 16 & 0o170000 == 0o120000:
            raise ValueError("codesearch 可执行文件不能为符号链接。")
    snapshot = models / MODEL_REPO / "snapshots" / MODEL_REVISION
    for filename, expected in MODEL_FILES.items():
        if not (snapshot / filename).is_file() or digest(snapshot / filename) != expected:
            raise ValueError("MiniLM model hash mismatch: " + filename)


def assemble(application: Path, archive: Path, destination: Path, info: dict, *, codesearch_archive=None, models=None,
             default_resources: Path | None = None, beta_number: int | None = None) -> list[Path]:
    """只复制冻结产物，另加官方 pi 目录；全部校验完成后替换输出 ZIP。"""
    check_pi(archive)
    for relative in ("LALC.exe", "LALC-console.exe", "_internal/lalc/MagicAndWonder.ico",
                     "_internal/lalc/mirror_chyan.png", "_internal/lalc/pi_probe.ts", "_internal/lalc/pi_context.ts",
                     *[f"_internal/lalc/skills/{name}/SKILL.md" for name in DEFAULT_SKILL_NAMES],
                     "_internal/lalc/translations/lalc_zh_CN.qm", "_internal/PySide6/translations/qtbase_zh_CN.qm",
                     "_internal/rapidocr/config.yaml", "_internal/rapidocr/default_models.yaml",
                     "_internal/UnityPy/resources/lzma.tpk"):
        if not (application / relative).is_file():
            raise ValueError(f"Missing packaged resource: {relative}")
    for name, expected in MODEL_HASHES.items():
        if digest(application / "_internal/rapidocr/models" / name) != expected:
            raise ValueError(f"Packaged OCR model hash mismatch: {name}")
    codesearch_archive = Path(codesearch_archive or CODESEARCH_ARCHIVE)
    models = Path(models or MODEL_ROOT)
    check_codesearch(codesearch_archive, models)
    destination.mkdir(parents=True, exist_ok=True)
    with WorkDirectory(prefix="lalc-release-", dir=destination) as directory:
        stage = Path(directory)
        base = stage / "without-agent" / "LALC"
        shutil.copytree(application, base)
        (base / "Developer.cmd").write_bytes(b'@echo off\r\nstart "" "%~dp0LALC.exe" --developer\r\n')
        shutil.copyfile(ROOT / "packaging/install-update.ps1", base / "install-update.ps1")
        if default_resources is not None:
            from lalc.default_resources import DEFAULT_RESOURCE_NAME, check_default_package, export_default_resources
            from lalc.sharing import SharingPackage
            resource_zip = base / DEFAULT_RESOURCE_NAME
            if default_resources.is_dir():
                print("默认资源已导出：", export_default_resources(default_resources, resource_zip))
            else:
                shutil.copyfile(default_resources, resource_zip)
            package = SharingPackage(resource_zip, stage)
            try:
                check_default_package(package)
            finally:
                package.close()
            info = {**info, "default_resources_sha256": digest(resource_zip)}
        package_version = info["version"]
        if beta_number is not None:
            info = {**info, "version": f"{info['version']}-beta.{beta_number}"}
        (base / "build-info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        with_pi = stage / "with-agent" / "LALC"
        shutil.copytree(base, with_pi)
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(with_pi / "pi")
        shutil.copyfile(ROOT / "packaging/pi-LICENSE.txt", with_pi / "pi/LICENSE.txt")
        agent = with_pi / "agent"
        agent.mkdir()
        with zipfile.ZipFile(codesearch_archive) as bundle:
            bundle.extractall(agent)
        snapshot = Path(MODEL_REPO) / "snapshots" / MODEL_REVISION
        for filename in MODEL_FILES:
            target = agent / "models" / snapshot / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(models / snapshot / filename, target)
        refs = agent / "models" / MODEL_REPO / "refs"
        refs.mkdir(parents=True)
        (refs / "main").write_text(MODEL_REVISION, encoding="utf-8")
        for name in ("codesearch-LICENSE.txt", "MiniLM-LICENSE.txt", "agent-resources-NOTICE.txt"):
            shutil.copyfile(ROOT / "packaging" / name, agent / name)

        if file_manifest(base) != file_manifest(with_pi, exclude_pi=True):
            raise ValueError("Two packages have different application files")
        archives = [(f"LALC-{package_version}-windows-x64-without-agent", base, "LALC"),
                    (f"LALC-{package_version}-windows-x64-with-agent", with_pi, "LALC")]
        if beta_number is None:
            archives.append(("lalc", with_pi, "lalc"))
        outputs = []
        for name, source, prefix in archives:
            output = stage / f"{name}.zip"
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
                for path in sorted(source.rglob("*")):
                    if path.is_file():
                        bundle.write(path, prefix + "/" + path.relative_to(source).as_posix())
                if prefix == "lalc":
                    bundle.write(ROOT / "packaging/update_to.bat", "lalc/update_to.bat")
            outputs.append(output)
        if default_resources is not None and beta_number is None:
            outputs.append(base / DEFAULT_RESOURCE_NAME)
        checksums = "".join(f"{digest(path)}  {path.name}\n" for path in outputs)
        for path in outputs:
            path.replace(destination / path.name)
        (destination / "SHA256SUMS").write_text(checksums, encoding="utf-8")
    return [destination / path.name for path in outputs]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pi-zip", type=Path, default=ROOT / "pi_resources/pi-windows-x64.zip")
    parser.add_argument("--codesearch-zip", type=Path, default=CODESEARCH_ARCHIVE)
    parser.add_argument("--models", type=Path, default=MODEL_ROOT)
    parser.add_argument("--default-resources", type=Path, help="默认资源来源，可指定 LALC 数据目录或分享 ZIP。")
    parser.add_argument("--beta", type=int, metavar="NUMBER", help="构建指定编号的 Beta 双包。")
    args = parser.parse_args(argv)
    if args.beta is not None and args.beta < 1:
        parser.error("--beta 需要正整数编号。")
    if sys.platform != "win32" or platform.machine().lower() not in {"amd64", "x86_64"}:
        parser.error("请在 Windows x64 构建，macOS 不能交叉生成该成品。")
    archive = args.pi_zip.resolve(strict=True)
    check_pi(archive)
    check_codesearch(args.codesearch_zip, args.models)
    from lalc.application import default_data_root
    from lalc.default_resources import DEFAULT_RESOURCE_NAME
    source = args.default_resources
    if source is None:
        local_data = default_data_root()
        approved_zip = ROOT / "packaging" / DEFAULT_RESOURCE_NAME
        if not os.environ.get("GITHUB_ACTIONS") and (local_data / "manifests").is_dir():
            source = local_data
        elif approved_zip.is_file():
            source = approved_zip
    if source is None:
        print("未发现默认资源包或正式数据目录，此次只构建框架。")
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
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
            "mirror": {"rid": os.environ.get("LALC_MIRROR_RID", ""), "os": os.environ.get("LALC_MIRROR_OS", ""),
                       "arch": os.environ.get("LALC_MIRROR_ARCH", "")},
            "environment": installed,
            "pi": {"version": PI_VERSION, "archive_sha256": PI_SHA256, "source": PI_URL}, "codesearch": {"version": CODESEARCH_VERSION,
            "archive_sha256": CODESEARCH_SHA256, "model_revision": MODEL_REVISION, "model_files": MODEL_FILES}}
    for path in assemble(work / "dist/LALC", archive, ROOT / "dist", info,
                         codesearch_archive=args.codesearch_zip, models=args.models, default_resources=source, beta_number=args.beta):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
