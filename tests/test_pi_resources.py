"""覆盖 pi ZIP 的独立版本检查、默认路径及损坏归档，不运行 pi。

项目根目录运行：.venv/bin/python -m pytest -q tests/test_pi_resources.py
"""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "pi_resources/check_version.py"


def test_version_uses_archive_metadata_and_script_directory(tmp_path):
    script = tmp_path / "resources/check_version.py"
    script.parent.mkdir()
    shutil.copyfile(SCRIPT, script)
    archive = script.with_name("pi-windows-x64.zip")
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("package.json", json.dumps({"version": "9.8.7"}))
        bundle.writestr("pi.exe", b"never executed")
    result = subprocess.run([sys.executable, str(script)], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "pi version: 9.8.7" in result.stdout and str(archive) in result.stdout


@pytest.mark.parametrize("problem", ["missing", "broken", "missing_metadata", "bad_json", "no_version", "wrong_type", "no_executable"])
def test_invalid_archive_reports_error(tmp_path, problem):
    archive = tmp_path / "pi.zip"
    if problem == "broken":
        archive.write_bytes(b"not a zip")
    elif problem != "missing":
        with zipfile.ZipFile(archive, "w") as bundle:
            if problem != "missing_metadata":
                metadata = {"version": "1.5.0"}
                if problem == "no_version":
                    metadata = {}
                elif problem == "wrong_type":
                    metadata = []
                bundle.writestr("package.json", "{" if problem == "bad_json" else json.dumps(metadata))
            if problem != "no_executable":
                bundle.writestr("pi.exe", b"never executed")
    result = subprocess.run([sys.executable, str(SCRIPT), str(archive)], capture_output=True, text=True)
    assert result.returncode == 1 and "检查失败" in result.stderr
    assert "pi version:" not in result.stdout
