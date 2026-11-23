# Build on Windows x64; user data and optional pi are assembled separately.
import sys
import tomllib
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata, collect_data_files, collect_dynamic_libs
from PySide6.QtCore import QLibraryInfo
from lalc.ocr import model_files

root = Path(SPECPATH)
version_file = None
if sys.platform == "win32":
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    version_parts = tuple(int(part) for part in version.split("."))
    if len(version_parts) != 3 or any(not 0 <= part <= 65535 for part in version_parts):
        raise ValueError("Windows releases require three numeric version components")
    version_file = Path(workpath) / "LALC.version"
    template = (root / "LALC.version").read_text(encoding="utf-8")
    version_file.write_text(template.replace("@VERSION_TUPLE@", str((*version_parts, 0)))
                            .replace("@VERSION_STRING@", f"{version}.0"), encoding="utf-8")

a = Analysis(
    [str(root / "packaging_entry.py")],
    pathex=[str(root / "src")],
    binaries=collect_dynamic_libs("onnxruntime") + collect_dynamic_libs("PIL"),
    datas=[(str(root / "LICENSE"), "."), (str(root / "THIRD_PARTY_NOTICES.md"), "."),
           (str(root / "MagicAndWonder.ico"), "lalc"),
           (str(root / "src/lalc/pi_probe.ts"), "lalc"),
           (str(root / "src/lalc/pi_context.ts"), "lalc"),
           (str(root / "src/lalc/skills"), "lalc/skills"),
           (str(root / "src/lalc/translations/lalc_zh_CN.qm"), "lalc/translations"),
           (str(Path(QLibraryInfo.path(QLibraryInfo.TranslationsPath)) / "qtbase_zh_CN.qm"),
            "PySide6/translations" if sys.platform == "win32" else "PySide6/Qt/translations")]
    + collect_data_files("rapidocr", includes=["config.yaml", "default_models.yaml"])
    + collect_data_files("UnityPy", includes=["resources/*.tpk"])
    + copy_metadata("UnityPy", recursive=True)
    + copy_metadata("mcp", recursive=True)
    + [(str(path), "rapidocr/models") for path in model_files().values()]
    + sum((copy_metadata(name) for name in (
        "PySide6", "PySide6-Essentials", "PySide6-Addons", "PySide6-Fluent-Widgets",
        "PySideSix-Frameless-Window", "darkdetect",
        "rapidocr", "onnxruntime",
    )), []),
    hiddenimports=["onnxruntime", "rapidocr.inference_engine.onnxruntime", "UnityPy.resources", "PIL.AvifImagePlugin"],
    hookspath=[str(root / "packaging_hooks")],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LALC",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(root / "MagicAndWonder.ico"),
    version=version_file,
)
coll = COLLECT(
    exe,
    EXE(pyz, a.scripts, [], exclude_binaries=True, name="LALC-console", console=True,
        debug=False, strip=False, upx=False,
        icon=str(root / "MagicAndWonder.ico"),
        version=version_file),
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="LALC",
)
