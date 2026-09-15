# Internal packaging spike. Build on Windows x64 for Windows acceptance.
import sys
from pathlib import Path

root = Path(SPECPATH)

a = Analysis(
    [str(root / "packaging_entry.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=[(".")],
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
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="LALC",
)
