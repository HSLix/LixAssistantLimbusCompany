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
        cls.cursor_positions = []

        win32con = types.ModuleType("win32con")
        constants = {
            "VK_ESCAPE": 0x1B,
            "VK_RETURN": 0x0D,
            "WM_MOUSEMOVE": 0x0200,
            "WM_LBUTTONDOWN": 0x0201,
            "WM_LBUTTONUP": 0x0202,
            "WM_KEYDOWN": 0x0100,
            "WM_KEYUP": 0x0101,
            "WM_ACTIVATE": 0x0006,
            "WM_HOTKEY": 0x0312,
            "MK_LBUTTON": 0x0001,
            "WA_INACTIVE": 0,
            "WA_ACTIVE": 1,
            "KEYEVENTF_KEYUP": 0x0002,
            "GA_ROOT": 2,
            "SMTO_BLOCK": 0x0001,
            "SMTO_ABORTIFHUNG": 0x0002,
        }
        for name, value in constants.items():
            setattr(win32con, name, value)

        win32api = types.ModuleType("win32api")
        win32api.MAKELONG = lambda low, high: (low & 0xFFFF) | ((high & 0xFFFF) << 16)
        win32api.MapVirtualKey = lambda _vk, _mode: 0x19
        win32api.GetCursorPos = lambda: (0, 0)
        win32api.SetCursorPos = lambda point: cls.cursor_positions.append(point)

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
        win32gui.ClientToScreen = lambda _hwnd, point: (point[0] + 10, point[1] + 20)
        win32gui.WindowFromPoint = lambda _point: 42
        win32gui.GetAncestor = lambda hwnd, _flag: hwnd
        win32gui.IsChild = lambda _parent, _child: False

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
        cls.methods = importlib.import_module("experiments.windows_interaction_methods")

    @classmethod
    def tearDownClass(cls):
        cls.windll_patch.stop()
        cls.module_patch.stop()
        sys.modules.pop("experiments.windows_interaction_lab", None)
        sys.modules.pop("experiments.windows_interaction_methods", None)

    def setUp(self):
        self.messages.clear()
        self.cursor_positions.clear()

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
                (
                    42,
                    self.lab.win32con.WM_LBUTTONDOWN,
                    self.lab.win32con.MK_LBUTTON,
                    packed,
                ),
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

    def test_activate_cursor_click_wraps_mouse_messages_and_restores_cursor(self):
        with mock.patch.object(self.methods.time, "sleep"):
            self.methods.activate_cursor_click(42, 100, 200)

        packed = 100 | (200 << 16)
        self.assertEqual(
            [message[1] for message in self.messages],
            [
                self.lab.win32con.WM_ACTIVATE,
                self.lab.win32con.WM_MOUSEMOVE,
                self.lab.win32con.WM_LBUTTONDOWN,
                self.lab.win32con.WM_LBUTTONUP,
                self.lab.win32con.WM_ACTIVATE,
            ],
        )
        self.assertEqual(self.messages[2][3], packed)
        self.assertEqual(self.cursor_positions, [(110, 220), (0, 0)])

    def test_managed_key_uses_real_key_state_and_always_releases(self):
        state = {"pressed": False}
        sent = []
        unregister = mock.Mock(return_value=True)
        self.methods._user32.RegisterHotKey = mock.Mock(return_value=True)
        self.methods._user32.UnregisterHotKey = unregister
        self.methods._user32.PeekMessageW = mock.Mock(return_value=False)

        def send_key(vk_code, key_up):
            sent.append((vk_code, key_up))
            state["pressed"] = not key_up

        with (
            mock.patch.object(self.methods, "_configure_keyboard_api"),
            mock.patch.object(
                self.methods,
                "_is_key_pressed",
                side_effect=lambda _vk: state["pressed"],
            ),
            mock.patch.object(self.methods, "_send_input_key", side_effect=send_key),
            mock.patch.object(self.methods, "_remove_hotkey_messages"),
            mock.patch.object(self.methods.time, "sleep"),
        ):
            self.methods.managed_key_press(42, ord("P"))

        self.assertEqual(sent, [(ord("P"), False), (ord("P"), True)])
        unregister.assert_called_once_with(None, 0x4C00 + ord("P"))

    def test_managed_key_aborts_when_hotkey_cannot_guard_foreground(self):
        self.methods._user32.RegisterHotKey = mock.Mock(return_value=False)
        self.methods._user32.PeekMessageW = mock.Mock(return_value=False)
        with (
            mock.patch.object(self.methods, "_configure_keyboard_api"),
            mock.patch.object(self.methods, "_is_key_pressed", return_value=False),
            mock.patch.object(self.methods, "_send_input_key") as send_key,
        ):
            with self.assertRaisesRegex(
                self.methods.ExperimentalInputError, "无法注册临时全局热键"
            ):
                self.methods.managed_key_press(42, ord("P"))
        send_key.assert_not_called()

    def test_touch_path_rejects_a_point_owned_by_another_window(self):
        with mock.patch.object(
            self.methods, "_window_owns_point", side_effect=[True] * 5 + [False]
        ):
            with self.assertRaisesRegex(
                self.methods.ExperimentalInputError, "目标点被其他窗口遮挡"
            ):
                self.methods._assert_touch_path_visible(42, (10, 10), (20, 20))

    def test_touch_info_contains_contact_metadata(self):
        flags = self.methods._touch_flags("down")
        info = self.methods._make_touch_info(2, 100, 200, flags)

        self.assertEqual(info.type, self.methods.PT_TOUCH)
        self.assertEqual(info.touchInfo.pointerInfo.pointerId, 2)
        self.assertEqual(info.touchInfo.pointerInfo.pointerFlags, flags)
        self.assertEqual(info.touchInfo.rcContact.left, 98)
        self.assertEqual(info.touchInfo.rcContact.bottom, 202)


if __name__ == "__main__":
    unittest.main()
