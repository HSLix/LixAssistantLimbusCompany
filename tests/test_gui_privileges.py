"""覆盖 GUI 提权、拒绝及启动前阻断，不实际请求 UAC。

项目根目录运行：.venv/bin/python -m pytest -q tests/test_gui_privileges.py
"""

from types import SimpleNamespace
from unittest.mock import Mock
import subprocess
import sys

import pytest

from lalc import gui_privileges as privileges
from lalc.lifecycle import run_application


@pytest.fixture
def windows(monkeypatch):
    shell = SimpleNamespace(IsUserAnAdmin=Mock(return_value=0), ShellExecuteW=Mock(return_value=42))
    user = SimpleNamespace(MessageBoxW=Mock())
    monkeypatch.setattr(privileges.ctypes, "windll", SimpleNamespace(shell32=shell, user32=user), raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    return shell, user


def test_other_platform_continues_without_windows_api(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    assert privileges.ensure_gui_privileges() is None


def test_administrator_continues_without_relaunch(windows):
    shell, user = windows
    shell.IsUserAnAdmin.return_value = 1
    assert privileges.ensure_gui_privileges() is None
    shell.ShellExecuteW.assert_not_called()
    user.MessageBoxW.assert_not_called()


@pytest.mark.parametrize("frozen", [False, True])
@pytest.mark.parametrize("args", [[], ["--developer"], ["--restore-gui=user,developer"]])
def test_elevation_preserves_entry_arguments_and_working_directory(windows, monkeypatch, tmp_path, frozen, args):
    shell, user = windows
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "frozen", frozen, raising=False)
    monkeypatch.setattr(sys, "argv", ["LALC.exe", *args])
    source_args = ["-X", "utf8", "-m", "lalc", *args]
    monkeypatch.setattr(sys, "orig_argv", [sys.executable, *source_args])
    assert privileges.ensure_gui_privileges() == 0
    shell.ShellExecuteW.assert_called_once_with(
        None, "runas", sys.executable, subprocess.list2cmdline(args if frozen else source_args), str(tmp_path), 1)
    user.MessageBoxW.assert_not_called()


@pytest.mark.parametrize("result", [None, 5, 32, OSError("cancelled")])
def test_denial_or_launch_failure_shows_both_languages_and_stops_before_data_access(windows, tmp_path, result):
    shell, user = windows
    if isinstance(result, OSError):
        shell.ShellExecuteW.side_effect = result
    else:
        shell.ShellExecuteW.return_value = result
    start = Mock()
    data = tmp_path / "must-not-be-created"
    assert run_application(start, data_root=data) == 1
    start.assert_not_called()
    assert not data.exists()
    message = user.MessageBoxW.call_args.args[1]
    assert "需要管理员权限才能启动" in message
    assert "requires administrator privileges" in message


def test_successful_relaunch_does_not_start_original_gui(windows, tmp_path):
    start = Mock()
    assert run_application(start, data_root=tmp_path) == 0
    start.assert_not_called()
