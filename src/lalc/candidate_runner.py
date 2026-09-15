from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .runtime import ExampleRunContext, atomic_write_json, load_verified_module, require_json

REQUIRED_FIELDS = {
    "protocol_version",
    "source_path",
    "expected_sha256",
    "arguments",
    "example_scenario",
    "result_path",
}


def run_candidate(request_path: str) -> int:
    try:
        request = json.loads(Path(request_path).read_text(encoding="utf-8"))
        if not isinstance(request, dict) or "context" in request:
            raise ValueError("invalid_candidate_request")
        if not REQUIRED_FIELDS.issubset(request) or request["protocol_version"] != 1:
            raise ValueError("invalid_candidate_request")
        arguments = request["arguments"]
        scenario = request["example_scenario"]
        require_json(arguments, "arguments")
        require_json(scenario, "example_scenario")
        if not isinstance(arguments, dict) or not isinstance(scenario, dict):
            raise ValueError("invalid_candidate_request")

        source_path = Path(request["source_path"]).resolve()
        source = source_path.read_bytes()
        module = load_verified_module(source_path, source, request["expected_sha256"])
        entry = getattr(module, "execute", None)
        if not callable(entry):
            raise ValueError("candidate_entry_missing")
        context = ExampleRunContext(scenario)
        result = entry(context, **arguments)
        require_json(result, "result")
        output: dict[str, Any] = {
            "status": "success",
            "component_sha256": request["expected_sha256"],
            "result": result,
            "action_events": context.action_events,
        }
    except Exception as error:
        output = {
            "status": "failure",
            "failure_code": str(error) if isinstance(error, ValueError) else "candidate_exception",
            "failure_message": str(error),
        }
    result_path = request.get("result_path") if isinstance(locals().get("request"), dict) else None
    if not isinstance(result_path, str):
        return 2
    atomic_write_json(Path(result_path), output)
    return 0 if output["status"] == "success" else 1
