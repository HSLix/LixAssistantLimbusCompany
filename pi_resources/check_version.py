#!/usr/bin/env python3
"""只读检查同目录的 pi ZIP 版本；可传入另一个归档路径，不解压或运行程序。"""

import argparse
import json
from pathlib import Path
import sys
import zipfile


def main(argv=None):
    """显示包内实际版本；缺失或损坏的归档返回非零状态。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", nargs="?", type=Path,
                        default=Path(__file__).with_name("pi-windows-x64.zip"))
    archive = parser.parse_args(argv).archive
    try:
        with zipfile.ZipFile(archive) as bundle:
            metadata = json.loads(bundle.read("package.json"))
            version = metadata.get("version") if isinstance(metadata, dict) else None
            if not isinstance(version, str) or not version.strip():
                raise ValueError("package.json 缺少有效的 version")
            if "pi.exe" not in bundle.namelist():
                raise ValueError("归档缺少 pi.exe，不是 Windows pi 资源包")
        print(f"ZIP: {archive.resolve()}\npi version: {version}")
        return 0
    except (OSError, KeyError, ValueError, RuntimeError, zipfile.BadZipFile) as error:
        print(f"检查失败: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
