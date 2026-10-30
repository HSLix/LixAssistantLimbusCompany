# Build on Windows x64; user data and optional pi are assembled separately.
import sys
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata
from PySide6.QtCore import QLibraryInfo

root = Path(SPECPATH)

a = Analysis(
    [str(root / "packaging_entry.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=[(str(root / "LICENSE"), "."), (str(root / "THIRD_PARTY_NOTICES.md"), "."),
           (str(root / "src/lalc/pi_probe.ts"), "lalc"),
           (str(root / "src/lalc/translations/lalc_zh_CN.qm"), "lalc/translations"),
           (str(Path(QLibraryInfo.path(QLibraryInfo.TranslationsPath)) / "qtbase_zh_CN.qm"),
            "PySide6/translations" if sys.platform == "win32" else "PySide6/Qt/translations")]
    + sum((copy_metadata(name) for name in (
        "PySide6", "PySide6-Essentials", "PySide6-Addons", "PySide6-Fluent-Widgets",
        "PySideSix-Frameless-Window", "darkdetect",
    )), []),
    hiddenimports=[],  # Add only imports promised by the Component Runtime Capability Contract.
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
    icon=None,  # Placeholder until approved artwork exists.
    version=str(root / "LALC.version") if sys.platform == "win32" else None,
)
coll = COLLECT(
    exe,
    EXE(pyz, a.scripts, [], exclude_binaries=True, name="LALC-console", console=True,
        debug=False, strip=False, upx=False,
        version=str(root / "LALC.version") if sys.platform == "win32" else None),
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="LALC",
)
