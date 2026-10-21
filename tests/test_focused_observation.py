"""覆盖窗口连接、异步聚焦确认、原始异常、内存截图及 Run 观察证据。

在项目根目录运行：
UV_CACHE_DIR=.generated/uv-cache uv run --frozen pytest -q tests/test_focused_observation.py
"""

from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path
from types import SimpleNamespace

import pytest

import lalc.__main__ as cli
import lalc.application as application
import lalc.focused as focused
from lalc.application import ApplicationService
from lalc.focused import FocusedAutomationSession, WindowError, WindowsWindowPlatform
from lalc.manifest import ManifestManager
from lalc.runtime import UserInterruption


EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "focused-observation"


def png_image(path: Path) -> tuple[tuple[int, int], bytes]:
    """解码本例的 RGB PNG，核对尺寸及实际像素，而非只看扩展名。"""

    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert data[12:16] == b"IHDR"
    width, height = struct.unpack(">II", data[16:24])
    assert data[24:29] == bytes([8, 2, 0, 0, 0])
    offset = 33
    assert data[offset + 4:offset + 8] == b"IDAT"
    length = struct.unpack(">I", data[offset:offset + 4])[0]
    pixels = zlib.decompress(data[offset + 8:offset + 8 + length])
    return (width, height), pixels


class FakeWindowPlatform:
    """用可控前台状态代替 Windows API，不模拟游戏输入。"""

    def __init__(self, windows: list[int] | None = None, *, checkpoint=None) -> None:
        self.windows = [42] if windows is None else windows
        self.foreground = False
        self.minimized = True
        self.visible = True
        self.width = 2
        self.height = 2
        self.captures = 0
        self.focus_calls = 0
        self.blur_during_capture = False

    def find_windows(self) -> list[int]:
        return self.windows

    def focus(self, hwnd: int) -> None:
        self.focus_calls += 1
        self.foreground = True
        self.minimized = False

    def window_info(self, hwnd: int) -> dict:
        return {
            "hwnd": hwnd, "process_id": 7, "process_path": "C:/Games/LimbusCompany.exe",
            "title": "LimbusCompany", "class": "UnityWndClass", "valid": hwnd in self.windows,
            "visible": self.visible, "minimized": self.minimized,
            "foreground": self.foreground, "width": self.width, "height": self.height,
        }

    def capture(self, hwnd: int, width: int, height: int) -> bytes:
        self.captures += 1
        if self.blur_during_capture:
            self.foreground = False
        return bytes([self.captures, 2, 3, 255]) * (width * height)


def test_connect_saves_exact_screenshot_without_creating_run(tmp_path: Path) -> None:
    platform = FakeWindowPlatform()
    service = ApplicationService(tmp_path, window_platform=platform)
    result = service.connect()

    assert platform.focus_calls == platform.captures == 1
    assert result["image"] == {"observation": 1, "width": 2, "height": 2}
    assert Path(result["image_path"]).suffix == ".png"
    assert png_image(Path(result["image_path"])) == ((2, 2), bytes([0, 3, 2, 1, 3, 2, 1]) * 2)
    log = Path(result["log_path"]).read_text(encoding="utf-8")
    assert f"image_path={result['image_path']}" in log
    assert "width=2\nheight=2\n" in log
    assert service.state["run_id"] is None
    assert not (tmp_path / "traces").exists()
    assert not (tmp_path / "ledger").exists()


def test_connect_cli_reports_saved_paths(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "default_data_root", lambda: tmp_path)
    monkeypatch.setattr(application, "WindowsWindowPlatform", FakeWindowPlatform)
    assert cli.main(["connect"]) == 0
    output = capsys.readouterr().out
    assert "Connected: LimbusCompany (2x2)" in output
    assert "Screenshot: " in output and "Log: " in output
    assert len(list((tmp_path / "connections").glob("*.png"))) == 1
    assert len(list((tmp_path / "connections").glob("*.log"))) == 1


def test_focus_waits_for_async_activation_on_repeated_connections(monkeypatch) -> None:
    now = [0.0]
    foreground = [10]
    requests: list[int] = []
    platform = WindowsWindowPlatform.__new__(WindowsWindowPlatform)
    platform.checkpoint = None
    platform.user32 = SimpleNamespace(
        GetForegroundWindow=lambda: foreground[0],
        IsWindow=lambda hwnd: True,
        IsIconic=lambda hwnd: False,
        SetForegroundWindow=lambda hwnd: requests.append(hwnd) or 1,
    )

    def sleep(duration: float) -> None:
        now[0] += duration
        foreground[0] = 42

    monkeypatch.setattr(focused.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(focused.time, "sleep", sleep)
    for _ in range(2):
        foreground[0] = 10
        platform.focus(42)
        assert foreground[0] == 42
    platform.focus(42)
    assert requests == [42, 42]


@pytest.mark.parametrize("returned", [0, 1])
def test_focus_wait_has_no_deadline_and_can_be_cancelled(monkeypatch, returned: int) -> None:
    now = [0.0]
    requests = []
    platform = WindowsWindowPlatform.__new__(WindowsWindowPlatform)
    platform.user32 = SimpleNamespace(
        GetForegroundWindow=lambda: 10,
        IsWindow=lambda hwnd: True,
        IsIconic=lambda hwnd: False,
        SetForegroundWindow=lambda hwnd: requests.append(hwnd) or returned,
    )

    def checkpoint():
        if now[0] >= 4:
            raise UserInterruption()

    platform.checkpoint = checkpoint
    monkeypatch.setattr(focused.time, "sleep", lambda duration: now.__setitem__(0, now[0] + duration))
    with pytest.raises(UserInterruption) as captured:
        platform.focus(42)
    assert captured.value.reason == "cancel"
    assert requests == [42]
    assert now[0] >= 4


def test_connect_cli_shows_original_exception(tmp_path: Path, monkeypatch, capsys) -> None:
    platform = FakeWindowPlatform()

    def focus(hwnd: int) -> None:
        try:
            raise OSError(5, "Access is denied")
        except OSError as error:
            raise WindowError("Cannot focus the game window") from error

    platform.focus = focus
    monkeypatch.setattr(cli, "default_data_root", lambda: tmp_path)
    monkeypatch.setattr(application, "WindowsWindowPlatform", lambda **_: platform)
    assert cli.main(["connect"]) == 1
    output = capsys.readouterr().err
    assert "WindowError: Cannot focus the game window" in output
    assert "direct cause" in output
    assert "Traceback (most recent call last):" in output
    assert 'raise OSError(5, "Access is denied")' in output
    assert "[Errno 5] Access is denied" in output
    assert not (tmp_path / "connections").exists()


@pytest.mark.parametrize("windows", [[], [42, 43]])
def test_connect_rejects_missing_or_ambiguous_window(tmp_path: Path, windows: list[int]) -> None:
    service = ApplicationService(tmp_path, window_platform=FakeWindowPlatform(windows))
    with pytest.raises(WindowError, match="Expected one"):
        service.connect()
    assert not (tmp_path / "connections").exists()


@pytest.mark.parametrize("invalid", ["visible", "width", "foreground"])
def test_connect_rejects_invalid_window_before_capture(tmp_path: Path, invalid: str) -> None:
    platform = FakeWindowPlatform()
    if invalid == "visible":
        platform.visible = False
    elif invalid == "width":
        platform.width = 0
    else:
        platform.focus = lambda hwnd: None
    with pytest.raises(WindowError):
        ApplicationService(tmp_path, window_platform=platform).connect()
    assert platform.captures == 0
    assert not (tmp_path / "connections").exists()


def test_focus_loss_discards_old_image_until_fresh_capture(tmp_path: Path) -> None:
    platform = FakeWindowPlatform()
    events: list[str] = []
    session = FocusedAutomationSession(platform, lambda event, fields: events.append(event))
    assert session.capture()["observation"] == 1
    platform.foreground = False
    with pytest.raises(WindowError, match="not foreground"):
        session.save(tmp_path / "stale.png")
    assert session.image is None
    assert not (tmp_path / "stale.png").exists()
    platform.foreground = True
    with pytest.raises(WindowError, match="No current screenshot"):
        session.save(tmp_path / "stale.png")
    assert session.capture()["observation"] == 2
    session.save(tmp_path / "fresh.png")
    assert png_image(tmp_path / "fresh.png") == ((2, 2), bytes([0, 3, 2, 2, 3, 2, 2]) * 2)
    assert "target_window_invalid" in events


def test_client_resize_discards_old_image(tmp_path: Path) -> None:
    platform = FakeWindowPlatform()
    session = FocusedAutomationSession(platform, lambda event, fields: None)
    session.capture()
    platform.width = 3
    with pytest.raises(WindowError, match="client area changed"):
        session.save(tmp_path / "stale.png")
    assert session.image is None
    assert not (tmp_path / "stale.png").exists()


def test_run_capture_uses_service_trace_and_explicit_evidence(tmp_path: Path) -> None:
    manager = ManifestManager(tmp_path)
    published = manager.publish(EXAMPLE / "manifest.json")
    assert published.ok, published.errors
    assert manager.set_default(published.loaded.manifest_id).ok
    platform = FakeWindowPlatform()
    service = ApplicationService(tmp_path, manifest_manager=manager, window_platform=platform)

    run_id = service.start("steps.capture_screen", {"save": True})
    state = service.wait_for(lambda current: current["run_id"] == run_id and current["phase"] == "finished")
    assert state["result"]["status"] == "success"
    output = state["result"]["output"]
    assert output["observation"] == 1
    assert output["evidence_id"] == f"{run_id}/1"
    assert Path(output["evidence_path"]).suffix == ".png"
    assert png_image(Path(output["evidence_path"])) == ((2, 2), bytes([0, 3, 2, 1, 3, 2, 1]) * 2)
    events = [item["event"] for item in state["trace"]]
    assert events.index("target_window_connected") < events.index("screenshot_refreshed")
    assert events.index("screenshot_refreshed") < events.index("screenshot_saved")
    assert "trusted_action_returned" in events
    saved_trace = [json.loads(line) for line in (tmp_path / "traces" / f"{run_id}.jsonl").read_text(encoding="utf-8").splitlines()]
    assert saved_trace == state["trace"]

    next_run = service.start("steps.capture_screen", {})
    next_state = service.wait_for(lambda current: current["run_id"] == next_run and current["phase"] == "finished")
    assert next_state["result"]["status"] == "success"
    assert "evidence_path" not in next_state["result"]["output"]
    assert not (tmp_path / "evidence" / str(next_run)).exists()


def test_focus_loss_during_run_capture_never_saves_image(tmp_path: Path) -> None:
    manager = ManifestManager(tmp_path)
    published = manager.publish(EXAMPLE / "manifest.json")
    assert published.ok, published.errors
    platform = FakeWindowPlatform()
    platform.blur_during_capture = True
    service = ApplicationService(tmp_path, manifest_manager=manager, window_platform=platform)
    run_id = service.start("steps.capture_screen", {"save": True}, manifest_id=published.loaded.manifest_id)
    state = service.wait_for(lambda current: current["run_id"] == run_id and current["phase"] == "finished")
    assert state["result"]["status"] == "failure"
    events = [item["event"] for item in state["trace"]]
    assert "target_window_invalid" in events
    assert "screenshot_refresh_failed" in events
    assert "screenshot_saved" not in events
    assert not (tmp_path / "evidence" / str(run_id)).exists()
