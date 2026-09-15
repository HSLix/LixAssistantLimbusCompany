from __future__ import annotations

import importlib.util
from pathlib import Path

from .runtime import atomic_write_json, require_json


def run_probe(source_path: str, result_path: str) -> int:
    try:
        spec = importlib.util.spec_from_file_location("lalc_packaging_probe_external", source_path)
        if spec is None or spec.loader is None:
            raise ValueError("probe_module_unloadable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.probe()
        require_json(result, "probe_result")
        output = {"status": "success", "result": result}
    except Exception as error:
        output = {"status": "failure", "failure_code": "probe_failure", "failure_message": str(error)}
    atomic_write_json(Path(result_path), output)
    return 0 if output["status"] == "success" else 1
