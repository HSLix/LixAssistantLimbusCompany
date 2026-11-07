"""固定游戏重启流程；保留输入所有权、阶段日志和原进程身份。"""

from __future__ import annotations

from pathlib import Path
import time

from .game_version import installation, load_steam_root
from .focused import WindowError
from .runtime import EnvironmentFailure, InputReleaseFailure, TraceWriteError, UserInterruption, _exception_fields


CLOSE_SECONDS = 5.0
TERMINATE_SECONDS = 5.0
START_SECONDS = 60.0
POLL_SECONDS = 0.05


def restart_game(data_root: Path, inputs) -> None:
    """验证安装后关闭原进程并启动固定程序；过渡期暂停后续接，不重复启动。"""
    window, platform = inputs.window, inputs.window.platform
    paused_seconds = 0.0
    stage = "validate"

    def log(message, *, level="info", **fields):
        inputs.emit("component_log", {"logical_name": "control.restart_game", "role": "trusted_action",
                    "phase": "execute", "stage": stage, "level": level, "message": message, **fields})

    def checkpoint():
        nonlocal paused_seconds
        while True:
            try:
                inputs.check_ownership()
                return
            except UserInterruption as error:
                if error.reason == "cancel":
                    raise
                started = time.monotonic()
                log("游戏重启已暂停；手动恢复后继续当前阶段。", level="warning")
                inputs.gate.pause()
                inputs.emit("paused_by_user", {
                    "logical_name": "control.restart_game", "description": "游戏重启过渡期",
                    "has_condition": False, "restart_step": False, "reason": str(error),
                    "resume_description": "恢复后继续当前重启阶段，不会再次启动游戏。",
                })
                inputs.gate.checkpoint()
                with inputs.monitor.lock:
                    inputs.monitor.pause_requested = False
                try:
                    inputs.owned_generation = inputs.wait_quiet()
                except UserInterruption as pause_error:
                    paused_seconds += time.monotonic() - started
                    if pause_error.reason == "cancel":
                        raise
                    continue
                inputs.resume_focus = True
                inputs.paused = False
                paused_seconds += time.monotonic() - started
                inputs.emit("input_resumed", {"logical_name": "control.restart_game"})
                log("手动恢复游戏重启，继续当前阶段。")

    def wait_until(predicate, seconds, description):
        started = time.monotonic() - paused_seconds - (inputs.focus_wait_seconds if stage == "bind" else 0)
        log(f"等待{description}，最多 {seconds:g} 秒。", timeout_seconds=seconds)
        while True:
            checkpoint()
            if predicate():
                log(f"等待结束：{description}。")
                return True
            if time.monotonic() - paused_seconds - started - (inputs.focus_wait_seconds if stage == "bind" else 0) >= seconds:
                log(f"等待超时：{description}。", level="warning")
                return False
            time.sleep(POLL_SECONDS)

    previous_checkpoint = inputs.focus_checkpoint
    inputs.focus_checkpoint = checkpoint
    try:
        checkpoint()
        log("验证已保存的 Steam 路径与 Limbus 可执行文件。")
        root = load_steam_root(data_root)
        if root is None:
            raise ValueError("No saved Steam client directory; configure it before restarting the game.")
        _, game, _ = installation(root)
        executable = (game / "LimbusCompany.exe").resolve(strict=True)
        if not executable.is_file() or not executable.is_relative_to(game):
            raise ValueError("Invalid LimbusCompany.exe in the Steam installation.")
        process = inputs.process
        if process.path.resolve() != executable:
            raise ValueError("Bound game process does not match the saved Steam installation.")
        checkpoint()
        matches = platform.find_windows()
        if len(matches) > 1 or (matches and matches != [window.hwnd]):
            raise ValueError("Ambiguous game windows; refusing to restart another instance.")
        window.image = None
        window.size = None
        window.captured_at = None
        if not process.exited():
            stage = "close"
            log("请求正常关闭游戏窗口。", process_id=process.pid)
            try:
                platform.request_close(window.hwnd, process.pid)
            except (WindowError, OSError):
                if not process.exited():
                    raise
            if not wait_until(process.exited, CLOSE_SECONDS, "原游戏进程退出"):
                stage = "terminate"
                checkpoint()
                log("正常关闭超时，强制终止原游戏进程。", level="warning", process_id=process.pid)
                process.terminate()
                if not wait_until(process.exited, TERMINATE_SECONDS, "强制终止完成"):
                    raise TimeoutError("Game process did not exit after termination.")
        log("已确认原游戏进程退出。", process_id=process.pid)
        window.hwnd = None
        window.process_id = None
        stage = "start"
        checkpoint()
        if platform.find_windows():
            raise ValueError("Another game window appeared before launch.")
        log("启动游戏应用。", executable=str(executable))
        launched = platform.start_game(executable)
        log("已发起游戏启动。", process_id=launched.pid)
        stage = "bind"
        started = time.monotonic() - paused_seconds - inputs.focus_wait_seconds

        def bind_checkpoint():
            checkpoint()
            if time.monotonic() - paused_seconds - inputs.focus_wait_seconds - started >= START_SECONDS:
                raise TimeoutError("Timed out waiting for the new game window and foreground focus.")

        def bind():
            matches = platform.find_windows()
            if len(matches) > 1:
                raise ValueError("Multiple game windows appeared during restart.")
            if not matches:
                if launched.poll() not in (None, 0):
                    raise RuntimeError("LimbusCompany.exe exited before creating a window.")
                return False
            info = platform.window_info(matches[0])
            if not info["valid"] or not info["visible"] or info["width"] <= 0 or info["height"] <= 0:
                return False
            candidate = platform.open_game_process(info["process_id"])
            try:
                if candidate.path.resolve() != executable:
                    raise ValueError("New game window does not match the saved Steam installation.")
                log("发现新游戏窗口，正在置前并重新绑定。", hwnd=matches[0], process_id=candidate.pid)
                window.connect(checkpoint=bind_checkpoint)
                bind_checkpoint()
                if window.process_id != candidate.pid or candidate.exited():
                    raise ValueError("New game process changed during binding.")
            except BaseException:
                candidate.close()
                raise
            inputs.process = candidate
            process.close()
            return True

        if not wait_until(bind, START_SECONDS, "新游戏窗口出现并完成绑定及置前"):
            raise TimeoutError("Timed out waiting for the new game window.")
        log("游戏重启完成，已绑定并置前新窗口；业务状态由后续 Step 判断。",
            hwnd=window.hwnd, process_id=window.process_id)
    except UserInterruption:
        log("游戏重启已取消。", level="warning")
        raise
    except TraceWriteError:
        raise
    except InputReleaseFailure:
        log("无法确认输入已释放，终止游戏重启与本次运行。", level="error")
        raise
    except Exception as error:
        log(f"游戏重启失败：{error}", level="error", **_exception_fields(error))
        raise EnvironmentFailure("game_restart_failed", str(error), cause=error) from error
    finally:
        inputs.focus_checkpoint = previous_checkpoint
