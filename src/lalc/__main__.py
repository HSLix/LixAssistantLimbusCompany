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

from .application import ApplicationService, StartError, default_data_root, default_candidate_root
from .focused import WindowError
from .manifest import ManifestManager, ValidationError
from .errors import FATAL_MESSAGE, configure_logging, result_diagnostics


class _Parser(argparse.ArgumentParser):
    """统一让所有无效命令以退出码 1 返回。"""

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="lalc")
    commands = parser.add_subparsers(dest="command", required=True)
    probe = commands.add_parser("pi-probe", help="Verify pi image input and restricted source reading")
    probe.add_argument("--base-url", default="http://localhost:12138/v1")
    probe.add_argument("--model")
    probe.add_argument("--image", type=Path, required=True)
    probe.add_argument("--source-root", type=Path, required=True)
    probe.add_argument("--source", required=True)
    probe.add_argument("--prompt", default="识别图片中的游戏界面，并分析要进入关卡，下一个步骤应点击哪里。说明按钮文字和大致位置，不执行点击。")
    probe.add_argument("--max-requests", type=int, default=20)
    probe.add_argument("--pi", default="pi", help="Path to the fixed-version pi executable")
    probe.add_argument("--ask-api-key", action="store_true", help="Read an optional key without echo")
    repair = commands.add_parser("repair", help="Analyze or repair existing Candidate files")
    repair.add_argument("--chat", action="store_true", help="Continue the conversation with further messages")
    repair.add_argument("--problem", required=True, help="Problem, reproduction steps and expected behavior")
    repair.add_argument("--exception", help="Exception/traceback or additional reproduction details")
    repair.add_argument("--image", type=Path, action="append", help="Attach an image; repeat for multiple images")
    repair.add_argument("--base-url")
    repair.add_argument("--model")
    repair.add_argument("--max-requests", type=int)
    repair.add_argument("--pi", default="pi")
    repair.add_argument("--ask-api-key", action="store_true")
    repair.add_argument("--secret-name", help="Windows DPAPI secret name for this invocation")
    settings = commands.add_parser("agent-config", help="Show or update shared provider settings using Developer selection")
    settings.add_argument("--base-url", help="Complete API base URL; no path is appended")
    settings.add_argument("--model")
    settings.add_argument("--max-requests", type=int)
    for command in (probe, repair, settings):
        command.add_argument("--provider", choices=("llama.cpp", "deepseek"),
                             default="llama.cpp" if command is probe else None)
        command.add_argument("--thinking", action=argparse.BooleanOptionalAction, default=None)
        command.add_argument("--reasoning-effort", choices=("low", "high", "max"))
    secret = settings.add_mutually_exclusive_group()
    secret.add_argument("--secret-name")
    secret.add_argument("--clear-secret", action="store_true")
    secrets = commands.add_parser("secret-set", help="Save a named secret using Windows current-user DPAPI")
    secrets.add_argument("name")
    init = commands.add_parser("init")
    init.add_argument("--from", dest="manifest_id")
    init.add_argument("--replace", action="store_true", help="Explicitly confirm replacing the current Candidate")
    commands.add_parser("validate")
    commands.add_parser("publish")
    commands.add_parser("clear")
    commands.add_parser("connect")
    crop = commands.add_parser("crop-asset")
    crop.add_argument("asset")
    crop.add_argument("--tags", nargs="*", default=None)
    crop.add_argument("--region", required=True, help="JSON client-pixel rectangle")
    tag = commands.add_parser("tag-asset", help="Replace all tags on an existing crop")
    tag.add_argument("asset")
    tag.add_argument("--tags", nargs="*", default=None, help="Complete replacement list; omit to clear")
    tag.add_argument("--image", type=Path, required=True, help="Existing local crop image path")
    commands.add_parser("generate-stubs", help="Generate RunContext types from registered Trusted Actions")
    commands.add_parser("data-dir")
    run = commands.add_parser("run")
    run.add_argument("logical_name")
    run.add_argument("--manifest")
    run.add_argument("--language", default="en", help="Running game language (default: en)")
    inputs = run.add_mutually_exclusive_group()
    inputs.add_argument("--inputs")
    inputs.add_argument("--inputs-file", type=Path)
    plan = commands.add_parser("run-plan")
    plan_inputs = plan.add_mutually_exclusive_group()
    plan_inputs.add_argument("--inputs")
    plan_inputs.add_argument("--inputs-file", type=Path)
    plan.add_argument("--manifest")
    plan.add_argument("--language", default="en", help="Running game language (default: en)")
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
        logging.getLogger(__name__).error("%s%s: %s", error.code, location, error.message,
                                          exc_info=(type(error.cause), error.cause, error.cause.__traceback__)
                                          if error.cause is not None else None)
        print(f"{error.code}{location}: {error.message}", file=sys.stderr)
        if error.cause is not None:
            traceback.print_exception(error.cause, file=sys.stderr, chain=True)


def _print_exception(error: BaseException) -> None:
    """显示命令错误及其原始异常链，保留类型和系统错误信息。"""

    logging.getLogger(__name__).error("Command failed", exc_info=(type(error), error, error.__traceback__))
    traceback.print_exception(error, file=sys.stderr, chain=True)
    if isinstance(error, StartError):
        for diagnostic in error.errors[1:]:
            if diagnostic.get("traceback"):
                sys.stderr.write(diagnostic["traceback"])


def _print_manifests(manager: ManifestManager, limit: int) -> bool:
    if limit < 1:
        print("-n must be a positive integer.", file=sys.stderr)
        return False
    manifests = manager.list_manifests()
    shown = manifests[:limit]
    print(f"Showing {len(shown)} of {len(manifests)} manifests (use -n COUNT to change).")
    print("MANIFEST ID                          SAVED AT            COMPONENTS  RULES")
    for item in shown:
        saved_at = datetime.fromtimestamp(item["saved_at"]).strftime("%Y-%m-%d %H:%M")
        print(
            f"{item['manifest_id']:<36} {saved_at:<19} "
            f"{item['components']:<11} {item['recovery_rules']}"
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
        service = ApplicationService(data_root, manifest_manager=manager, game_language=args.language)
        if args.command == "run-plan":
            inputs = _read_inputs(args)
            if set(inputs) - {"task_repetitions", "settings"}:
                raise ValueError("Plan inputs may contain only task_repetitions and settings.")
            run_id = service.start_plan(**inputs, manifest_id=args.manifest)
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
    if result.get("fatal"):
        print(FATAL_MESSAGE, file=sys.stderr)
    details = result_diagnostics(result)
    if details:
        if result.get("failure_code", result.get("reason")) != "user_cancelled":
            logging.getLogger(__name__).error("Execution result: %s", details)
        print(details, file=sys.stderr)
    return 0 if result["status"] == "success" or (result["status"] == "completed" and result["all_tasks_succeeded"]) else 1


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "pi-probe":
        from .pi_probe import run_probe

        return run_probe(args)
    if args.command == "generate-stubs":
        from .stubgen import generate_stubs

        try:
            print(generate_stubs())
        except (OSError, ValueError, TypeError, NameError) as error:
            _print_exception(error)
            return 1
        return 0
    data_root = default_data_root()
    if args.command == "data-dir":
        print(data_root)
        return 0
    if args.command in {"agent-config", "secret-set"}:
        from .agent_settings import settings_command

        return settings_command(args, data_root)
    manager = ManifestManager(data_root)
    candidate = default_candidate_root(data_root)
    manifest_path = candidate / "manifest.json"

    if args.command == "repair":
        from .agent_repair import run_repair

        return run_repair(args, manager, candidate)

    if args.command in {"crop-asset", "tag-asset"}:
        service = ApplicationService(data_root, manifest_manager=manager)
        try:
            if args.command == "crop-asset":
                result = service.crop_developer_asset(args.asset, json.loads(args.region), args.tags)
            else:
                result = service.tag_asset(args.asset, args.image, args.tags)
        except (ValueError, StartError) as error:
            _print_exception(error)
            return 1
        print(json.dumps(result, ensure_ascii=False))
        return 0
    if args.command == "init":
        from .developer import DeveloperHost
        try:
            DeveloperHost(ApplicationService(data_root, manifest_manager=manager), candidate).initialize(args.manifest_id, replace=args.replace)
        except (ValueError, OSError) as error:
            print(str(error), file=sys.stderr)
            if args.manifest_id is None and not candidate.exists():
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
        print(f"Set as default: lalc set-default {manifest_id}")
        print("Run after setting default: lalc run <logical-name>")
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
    if len(args) == 1 and args[0].startswith("--restore-gui="):
        restore = tuple(args[0].split("=", 1)[1].split(","))
        if not restore or len(set(restore)) != len(restore) or set(restore) - {"user", "developer"}:
            raise ValueError("Invalid GUI restoration request")
        from .gui import run_gui
        from .lifecycle import run_application
        return run_application(lambda owner: run_gui(owner, restore=restore))
    if not args or args == ["--developer"]:
        from .lifecycle import run_application

        if args:
            from .gui import run_gui
            return run_application(lambda owner: run_gui(owner, developer=True))
        return run_application()
    try:
        if args[0] not in {"data-dir", "pi-probe", "generate-stubs"}:
            configure_logging(default_data_root())
        parsed = _parser().parse_args(args)
        if parsed.command in {"validate", "publish", "clear"}:
            from .process_lock import ProcessLock
            with ProcessLock("candidate:" + str(default_candidate_root(default_data_root()).resolve())):
                return _dispatch(parsed)
        return _dispatch(parsed)
    except (EOFError, KeyboardInterrupt, OSError, WindowError) as error:
        _print_exception(error)
        return 1
    except Exception as error:
        logging.getLogger(__name__).exception("CLI command failed")
        print(FATAL_MESSAGE, file=sys.stderr)
        _print_exception(error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
