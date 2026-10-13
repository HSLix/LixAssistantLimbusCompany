from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from .application import ApplicationService, StartError, default_data_root
from .focused import WindowError
from .manifest import ManifestManager, ValidationError


class _Parser(argparse.ArgumentParser):
    """统一让所有无效命令以退出码 1 返回。"""

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="lalc")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("--from", dest="manifest_id")
    commands.add_parser("validate")
    commands.add_parser("publish")
    commands.add_parser("clear")
    commands.add_parser("connect")
    commands.add_parser("data-dir")
    run = commands.add_parser("run")
    run.add_argument("logical_name")
    run.add_argument("--manifest")
    inputs = run.add_mutually_exclusive_group()
    inputs.add_argument("--inputs")
    inputs.add_argument("--inputs-file", type=Path)
    plan = commands.add_parser("run-plan")
    plan.add_argument("path", type=Path)
    plan.add_argument("--manifest")
    listing = commands.add_parser("list-manifests")
    listing.add_argument("-n", type=int, default=9)
    default = commands.add_parser("set-default")
    default.add_argument("manifest_id")
    return parser


def _print_errors(errors: tuple[ValidationError, ...]) -> None:
    for error in errors:
        location = ""
        if error.logical_name:
            location += f" [{error.logical_name}]"
        if error.line is not None:
            location += f" line {error.line}"
            if error.column is not None:
                location += f":{error.column}"
        print(f"{error.code}{location}: {error.message}", file=sys.stderr)


def _print_exception(error: BaseException) -> None:
    """显示命令错误及其原始异常链，保留类型和系统错误信息。"""

    traceback.print_exception(error, file=sys.stderr, chain=True)


def _print_manifests(manager: ManifestManager, limit: int) -> bool:
    if limit < 1:
        print("-n must be a positive integer.", file=sys.stderr)
        return False
    manifests = manager.list_manifests()
    shown = manifests[:limit]
    print(f"Showing {len(shown)} of {len(manifests)} manifests (use -n COUNT to change).")
    print("MANIFEST ID                          SAVED AT            COMPONENTS  RULES  ACTIONS")
    for item in shown:
        saved_at = datetime.fromtimestamp(item["saved_at"]).strftime("%Y-%m-%d %H:%M")
        print(
            f"{item['manifest_id']:<36} {saved_at:<19} "
            f"{item['components']:<11} {item['recovery_rules']:<6} {item['trusted_actions']}"
        )
    print(f"Default Manifest: {manager.default_manifest_id() or 'unavailable'}")
    return True


def _read_inputs(args: argparse.Namespace) -> dict[str, Any]:
    if args.inputs is not None:
        value = json.loads(args.inputs)
    elif args.inputs_file is not None:
        value = json.loads(args.inputs_file.read_text(encoding="utf-8"))
    else:
        value = {}
    if type(value) is not dict:
        raise ValueError("inputs must be a JSON object")
    return value


def _run(args: argparse.Namespace, manager: ManifestManager, data_root: Path) -> int:
    try:
        service = ApplicationService(data_root, manifest_manager=manager)
        if args.command == "run-plan":
            run_id = service.start_plan(args.path, manifest_id=args.manifest)
        else:
            inputs = _read_inputs(args)
            run_id = service.start(args.logical_name, inputs, manifest_id=args.manifest)
        try:
            while True:
                state = service.wait_for(lambda current: current["run_id"] == run_id and (
                    current["phase"] == "finished" or
                    (current["pause_info"] is not None and not current["resume_pending"])
                ))
                if state["phase"] == "finished":
                    break
                info = state["pause_info"]
                print(f"\n自动化已暂停：{info['reason']}\n{info['description']}", file=sys.stderr)
                instruction = "恢复时检查当前 Step 的 condition。" if info["has_condition"] else \
                    "没有 condition，恢复后将从头执行当前 Step。"
                if not info.get("restart_step", True):
                    instruction = "恢复后继续 Workflow 的观察与调度。"
                print(instruction, file=sys.stderr)
                if info.get("traceback"):
                    sys.stderr.write(info["traceback"])
                try:
                    choice = input("处理游戏后输入 r 恢复，其他输入结束运行：")
                except EOFError:
                    choice = "q"
                if choice.strip().lower() == "r":
                    service.resume()
                else:
                    service.stop()
        except KeyboardInterrupt:
            service.stop()
            state = service.wait_for(
                lambda current: current["run_id"] == run_id and current["phase"] == "finished"
            )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, StartError) as error:
        _print_exception(error)
        return 1
    print(json.dumps(state["result"], ensure_ascii=False, indent=2))
    result = state["result"]
    if result.get("traceback"):
        sys.stderr.write(result["traceback"])
    for item in result.get("items", []):
        if item.get("traceback"):
            sys.stderr.write(item["traceback"])
    return 0 if state["result"]["status"] in {"success", "completed"} else 1


def _dispatch(args: argparse.Namespace) -> int:
    data_root = default_data_root()
    if args.command == "data-dir":
        print(data_root)
        return 0
    manager = ManifestManager(data_root)
    candidate = Path.cwd() / "candidate"
    manifest_path = candidate / "manifest.json"

    if args.command == "init":
        errors = manager.initialize_candidate(candidate, manifest_id=args.manifest_id)
        if errors:
            _print_errors(errors)
            if (
                args.manifest_id is None
                and errors[0].code != "candidate_not_empty"
                and any(path.name != "default.json" for path in manager.manifests_dir.glob("*.json"))
            ):
                _print_manifests(manager, 9)
                print("Run lalc set-default <manifest-id>, then retry lalc init.", file=sys.stderr)
            return 1
        print(f"Initialized Developer Candidate: {candidate.resolve()}")
        return 0
    if args.command == "validate":
        errors = manager.validate(manifest_path)
        if errors:
            _print_errors(errors)
            return 1
        print("Candidate is valid.")
        return 0
    if args.command == "publish":
        result = manager.publish(manifest_path)
        if not result.ok:
            _print_errors(result.errors)
            return 1
        manifest_id = result.loaded.manifest_id
        print(f"Published: {manifest_id}")
        print(f"Run: lalc run <logical-name> --manifest {manifest_id}")
        print(f"Set as default: lalc set-default {manifest_id}")
        print("Remove developer candidate: lalc clear")
        return 0
    if args.command == "clear":
        if not candidate.exists():
            print(f"Candidate does not exist: {candidate.resolve()}", file=sys.stderr)
            return 1
        answer = input(f"Delete every file under {candidate.resolve()}? [y/N] ")
        if answer.strip().lower() not in {"y", "yes"}:
            print("Candidate cleanup cancelled.", file=sys.stderr)
            return 1
        shutil.rmtree(candidate)
        print(f"Cleared Developer Candidate: {candidate.resolve()}")
        return 0
    if args.command == "connect":
        result = ApplicationService(data_root, manifest_manager=manager).connect()
        print(f"Connected: {result['window']['title']} ({result['image']['width']}x{result['image']['height']})")
        print(f"Screenshot: {result['image_path']}")
        print(f"Log: {result['log_path']}")
        return 0
    if args.command in {"run", "run-plan"}:
        return _run(args, manager, data_root)
    if args.command == "list-manifests":
        return 0 if _print_manifests(manager, args.n) else 1
    if args.command == "set-default":
        result = manager.set_default(args.manifest_id)
        if not result.ok:
            _print_errors(result.errors)
            return 1
        print(f"Default Manifest: {args.manifest_id}")
        return 0
    raise AssertionError(args.command)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) == 3 and args[0] == "--packaging-probe":
        from .packaging_probe import run_probe

        return run_probe(args[1], args[2])
    if not args:
        from .gui import run_gui

        return run_gui()
    try:
        return _dispatch(_parser().parse_args(args))
    except (EOFError, KeyboardInterrupt, OSError, WindowError) as error:
        _print_exception(error)
        return 1
    except Exception as error:
        logging.getLogger(__name__).exception("CLI command failed")
        print(f"Command failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
