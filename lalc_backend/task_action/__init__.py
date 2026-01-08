# task_action/__init__.py
import importlib
import pathlib
import sys

pkg_path = pathlib.Path(__file__).parent
for py_file in pkg_path.glob("*.py"):
    if py_file.stem == "__init__":
        continue
    # print(f"{__name__}.{py_file.stem}")
    importlib.import_module(f"{__name__}.{py_file.stem}")