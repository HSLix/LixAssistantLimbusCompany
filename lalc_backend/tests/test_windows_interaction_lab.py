"""Platform-neutral tests for the Win32 message construction in the lab."""

from __future__ import annotations

import ctypes
import importlib
import sys
import types
import unittest
from unittest import mock


class _CallableApi:
    def __call__(self, *_args):
        return True


class WindowsInteractionLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.messages = []

        win32con = types.ModuleType("win32con")
        constants = {
            "VK_ESCAPE": 0x1B,
            "VK_RETURN": 0x0D,
            "WM_MOUSEMOVE": 0x0200,
            "WM_LBUTTONDOWN": 0x0201,
            "WM_LBUTTONUP": 0x0202,
            "WM_KEYDOWN": 0x0100,
            "WM_KEYUP": 0x0101,
            "MK_LBUTTON": 0x0001,
            "SMTO_BLOCK": 0x0001,
            "SMTO_ABORTIFHUNG": 0x0002,
        }
        for name, value in constants.items():
            setattr(win32con, name, value)

        win32api = types.ModuleType("win32api")
        win32api.MAKELONG = lambda low, high: (low & 0xFFFF) | ((high & 0xFFFF) << 16)
        win32api.MapVirtualKey = lambda _vk, _mode: 0x19
        win32api.GetCursorPos = lambda: (0, 0)

        win32gui = types.ModuleType("win32gui")
        win32gui.error = RuntimeError
        win32gui.IsWindow = lambda hwnd: hwnd == 42
        win32gui.IsIconic = lambda _hwnd: False
        win32gui.GetClientRect = lambda _hwnd: (0, 0, 1280, 720)
        win32gui.PostMessage = lambda *args: cls.messages.append(args)
        win32gui.SendMessageTimeout = (
            lambda hwnd, message, wparam, lparam, _flags, _timeout: cls.messages.append(
                (hwnd, message, wparam, lparam)
            )
        )
        win32gui.GetForegroundWindow = lambda: 1
        win32gui.ScreenToClient = lambda _hwnd, point: point

        win32ui = types.ModuleType("win32ui")
        fake_user32 = types.SimpleNamespace(PrintWindow=_CallableApi())

        pil = types.ModuleType("PIL")
        pil.Image = types.SimpleNamespace()

        modules = {
            "PIL": pil,
            "win32api": win32api,
            "win32con": win32con,
            "win32gui": win32gui,
            "win32ui": win32ui,
        }
        cls.module_patch = mock.patch.dict(sys.modules, modules)
        cls.module_patch.start()
        cls.windll_patch = mock.patch.object(
            ctypes, "WinDLL", return_value=fake_user32, create=True
        )
        cls.windll_patch.start()
        cls.lab = importlib.import_module("experiments.windows_interaction_lab")

    @classmethod
    def tearDownClass(cls):
        cls.windll_patch.stop()
        cls.module_patch.stop()
        sys.modules.pop("experiments.windows_interaction_lab", None)

    def setUp(self):
        self.messages.clear()

    def test_keyboard_lparam_contains_scan_code_and_release_flags(self):
        down = self.lab._keyboard_lparam(ord("P"), key_up=False)
        up = self.lab._keyboard_lparam(ord("P"), key_up=True)

        self.assertEqual(down, 1 | (0x19 << 16))
        self.assertEqual(up, down | (1 << 30) | (1 << 31))

    def test_client_coordinate_must_be_inside_client_area(self):
        self.assertEqual(
            self.lab._client_lparam(42, 1279, 719),
            1279 | (719 << 16),
        )
        with self.assertRaises(self.lab.InteractionLabError):
            self.lab._client_lparam(42, 1280, 719)

    def test_background_click_posts_client_relative_message_sequence(self):
        with mock.patch.object(self.lab.time, "sleep"):
            self.lab.background_click(42, 100, 200)

        packed = 100 | (200 << 16)
        self.assertEqual(
            self.messages,
            [
                (42, self.lab.win32con.WM_MOUSEMOVE, 0, packed),
                (42, self.lab.win32con.WM_LBUTTONDOWN, self.lab.win32con.MK_LBUTTON, packed),
                (42, self.lab.win32con.WM_LBUTTONUP, 0, packed),
            ],
        )

    def test_send_delivery_dispatches_without_queueing(self):
        with mock.patch.object(self.lab.time, "sleep"):
            self.lab.background_key_press(42, "p", delivery="send")

        self.assertEqual(
            [message[1] for message in self.messages],
            [self.lab.win32con.WM_KEYDOWN, self.lab.win32con.WM_KEYUP],
        )

    def test_minimized_window_has_explicit_scope_error(self):
        with mock.patch.object(self.lab.win32gui, "IsIconic", return_value=True):
            with self.assertRaisesRegex(
                self.lab.InteractionLabError, "当前实验只支持未最小化窗口"
            ):
                self.lab._client_size(42)

    def test_only_requested_keys_are_supported(self):
        self.assertEqual(self.lab._virtual_key("ESC"), self.lab.win32con.VK_ESCAPE)
        self.assertEqual(self.lab._virtual_key("p"), ord("P"))
        self.assertEqual(self.lab._virtual_key("Enter"), self.lab.win32con.VK_RETURN)
        with self.assertRaises(ValueError):
            self.lab._virtual_key("space")


if __name__ == "__main__":
    unittest.main()
