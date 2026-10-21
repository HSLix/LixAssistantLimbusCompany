"""覆盖项目根目录 Developer Candidate、Manifest 命令和 model-free CLI Run。

在项目根目录运行：
UV_CACHE_DIR=.generated/uv-cache uv run --frozen pytest -q tests/test_cli.py
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import lalc.__main__ as cli
from lalc.manifest import ManifestManager, ManifestResult, ValidationError


EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "virtual-workflow"


def test_start_rejection_prints_every_import_traceback(tmp_path: Path, monkeypatch, capsys) -> None:
    """多个模块导入失败时，命令行不能只保留第一个异常链。"""

    errors = []
    for name in ("first", "second"):
        try:
            raise OSError(f"{name} import") from ValueError(f"{name} root")
        except OSError as error:
            errors.append(ValidationError("component_import_failed", str(error), name, cause=error))
    manager = ManifestManager(tmp_path)
    monkeypatch.setattr(manager, "load", lambda _: ManifestResult(errors=tuple(errors)))
    monkeypatch.setattr(cli, "ManifestManager", lambda _: manager)
    monkeypatch.setattr(cli, "default_data_root", lambda: tmp_path)
    assert cli.main(["run", "tasks.example", "--manifest", "unavailable"]) == 1
    diagnostic = capsys.readouterr().err
    for name in ("first", "second"):
        assert f"ValueError: {name} root" in diagnostic
        assert f"OSError: {name} import" in diagnostic
    assert "in test_start_rejection_prints_every_import_traceback" in diagnostic
    assert not (tmp_path / "run-sequence.json").exists()


def test_data_dir_prints_default_without_creating_it(tmp_path: Path, monkeypatch, capsys) -> None:
    target = tmp_path / "LALC"
    monkeypatch.setattr(cli, "default_data_root", lambda: target)
    assert cli.main(["data-dir"]) == 0
    assert capsys.readouterr().out == f"{target}\n"
    assert not target.exists()


def test_complete_developer_cli_lifecycle(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project = tmp_path / "project"
    runtime = tmp_path / "runtime"
    project.mkdir()
    monkeypatch.chdir(project)
    monkeypatch.setattr(cli, "default_data_root", lambda: runtime)

    assert cli.main(["init"]) == 0
    candidate = project / "candidate"
    manifest_path = candidate / "manifest.json"
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["components"] == {}

    for source in EXAMPLE.iterdir():
        shutil.copyfile(source, candidate / source.name)

    assert cli.main(["validate"]) == 0
    assert not (runtime / "manifests").exists()
    assert not (runtime / "components").exists()
    assert cli.main(["publish"]) == 0
    published_output = capsys.readouterr().out
    manifest_id = published_output.split("Published: ", 1)[1].splitlines()[0]
    assert candidate.exists()
    assert not (runtime / "manifests" / "default.json").exists()

    assert cli.main(
        ["run", "tasks.greet", "--manifest", manifest_id, "--inputs", '{"name":"Lix"}']
    ) == 0
    assert json.loads(capsys.readouterr().out)["output"] == "Hello, Lix！"
    trace = [
        json.loads(line)
        for line in (runtime / "traces" / "1.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    components = [item for item in trace if item["event"] == "component_started"]
    assert [item["logical_name"] for item in components] == [
        "tasks.greet",
        "subworkflows.greet",
        "steps.say_hello",
    ]
    assert components[1]["parent_call_id"] == components[0]["call_id"]
    assert components[2]["parent_call_id"] == components[1]["call_id"]
    actions = [item for item in trace if item["event"] == "trusted_action_started"]
    assert [item["classification"] for item in actions] == ["observe", "control"]
    assert any(item["event"] == "component_returned" and item["logical_name"] == "steps.say_hello"
               and item["return_value"] == "Hello, Lix！" for item in trace)

    assert cli.main(
        ["run", "tasks.greet", "--manifest", manifest_id, "--inputs", '{"name":"   "}']
    ) == 1
    assert json.loads(capsys.readouterr().out)["failure_code"] == "execution_failed"

    assert cli.main(["set-default", manifest_id]) == 0
    capsys.readouterr()
    inputs_path = project / "inputs.json"
    inputs_path.write_text('{"name":"文件"}', encoding="utf-8")
    assert cli.main(["run", "tasks.greet", "--inputs-file", "inputs.json"]) == 0
    assert json.loads(capsys.readouterr().out)["output"] == "Hello, 文件！"

    assert cli.main(["run", "steps.say_hello", "--inputs", '{"name":" "}']) == 1
    assert json.loads(capsys.readouterr().out)["failure_code"] == "execution_failed"

    assert cli.main(["list-manifests", "-n", "1"]) == 0
    listing = capsys.readouterr().out.splitlines()
    assert listing[0] == "Showing 1 of 1 manifests (use -n COUNT to change)."
    assert listing[-1] == f"Default Manifest: {manifest_id}"
    assert cli.main(["list-manifests", "-n", "0"]) == 1

    assert cli.main(["init"]) == 1
    assert "lalc clear" in capsys.readouterr().err
    monkeypatch.setattr("builtins.input", lambda _: "no")
    assert cli.main(["clear"]) == 1
    assert candidate.exists()
    monkeypatch.setattr("builtins.input", lambda _: "yes")
    assert cli.main(["clear"]) == 0
    assert not candidate.exists()

    (runtime / "manifests" / "default.json").write_text(
        '{"manifest_id":"00000000-0000-0000-0000-000000000000"}', encoding="utf-8"
    )
    assert cli.main(["init"]) == 1
    repair = capsys.readouterr()
    assert manifest_id in repair.out
    assert "lalc set-default" in repair.err
    assert not candidate.exists()
    assert cli.main(["set-default", manifest_id]) == 0

    assert cli.main(["init"]) == 0
    materialized = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert materialized["components"]["tasks.greet"] == {"source_path": "tasks.greet.py"}
    assert (candidate / "tasks.greet.py").read_bytes() == (EXAMPLE / "tasks.greet.py").read_bytes()

    assert cli.main(["clear"]) == 0
    assert cli.main(["init", "--from", manifest_id]) == 0
    assert (candidate / "actions.name_ready.py").read_bytes() == (
        EXAMPLE / "actions.name_ready.py"
    ).read_bytes()
