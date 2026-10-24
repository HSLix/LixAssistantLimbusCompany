"""覆盖客户区尺寸、Win32 失败、活动互斥及原图像素放大框选。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_capture_increment.py
"""

from types import SimpleNamespace

import pytest

from lalc.focused import WindowsWindowPlatform, WindowError
from test_agent_repair import host_for
from test_developer_gui import gui, wait_jobs


def platform_for_resize(*, fail=None, apply=True):
    platform = object.__new__(WindowsWindowPlatform)
    platform.checkpoint = None
    state = dict(valid=True, visible=True, minimized=False, process_id=1, width=600, height=300)
    calls = []
    def rect(hwnd, pointer):
        pointer._obj.left, pointer._obj.top = 10, 20
        pointer._obj.right, pointer._obj.bottom = 626, 359
        return fail != "rect"
    def position(*args):
        calls.append(args)
        if apply:
            state.update(width=args[4] - 16, height=args[5] - 39)
        return fail != "position"
    platform.user32 = SimpleNamespace(GetWindowRect=rect, SetWindowPos=position)
    platform.window_info = lambda _: dict(state)
    return platform, state, calls


def test_resize_compensates_borders_and_preserves_position_zorder_focus():
    platform, state, calls = platform_for_resize()
    result = platform.resize_client(42, 1280, 720)
    assert calls == [(42, None, 0, 0, 1296, 759, 0x0016)]
    assert result["before"]["width"] == 600
    assert (result["after"]["width"], result["after"]["height"]) == (1280, 720)


@pytest.mark.parametrize("fail", ["rect", "position"])
def test_resize_reports_win32_failure(monkeypatch, fail):
    import lalc.focused as focused
    monkeypatch.setattr(focused.ctypes, "get_last_error", lambda: 5, raising=False)
    monkeypatch.setattr(focused.ctypes, "WinError", lambda code: OSError(code, "denied"), raising=False)
    platform, _, _ = platform_for_resize(fail=fail)
    with pytest.raises(OSError, match="denied"):
        platform.resize_client(42, 1280, 720)


def test_resize_rejects_minimized_invalid_size_and_reports_actual_mismatch(monkeypatch):
    platform, state, calls = platform_for_resize(apply=False)
    state["minimized"] = True
    with pytest.raises(WindowError, match="恢复"):
        platform.resize_client(42, 1280, 720)
    assert calls == []
    state["minimized"] = False
    with pytest.raises(ValueError):
        platform.resize_client(42, 0, 720)
    ticks = iter([0, 2])
    monkeypatch.setattr("lalc.focused.time.monotonic", lambda: next(ticks))
    with pytest.raises(WindowError, match="实际 600 × 300"):
        platform.resize_client(42, 1280, 720)


def test_resize_host_preserves_preview_and_respects_activity(tmp_path):
    host, _ = host_for(tmp_path)
    platform, _, _ = platform_for_resize()
    platform.find_windows = lambda: [42]
    host.service.window_platform = platform
    host.preview = snapshot = (b"fixed", (1, 1), {})
    assert host.resize_window()["after"]["width"] == 1280
    assert host.preview is snapshot
    with host.service.activity("Agent"):
        with pytest.raises(Exception, match="Agent"):
            host.resize_window()
    platform.find_windows = lambda: []
    with pytest.raises(WindowError, match="found 0"):
        host.resize_window()


def test_capture_defaults_and_magnifier_tracks_original_pixels_without_changing_crop(gui):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor
    app, window = gui
    page, view = window.capture_page, window.capture_page.view
    assert (page.window_width.value(), page.window_height.value()) == (1280, 720)
    view.resize(400, 400)
    pixels = bytes([30, 50, 80, 255]) * 200 * 100
    view.set_image(pixels, (200, 100))
    # 400×200 的图像上下各有 100 留白，中心映射到原图 (100, 50)。
    view.update_magnifier(QPointF(200, 200))
    assert not view.magnifier.isHidden()
    assert view.magnifier.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    magnified = view.magnifier.pixmap().toImage()
    assert magnified.pixelColor(81, 81) == QColor(80, 50, 30)
    view.update_magnifier(QPointF(0, 100))
    assert view.magnifier.pixmap().toImage().pixelColor(0, 0) == QColor("black")
    view.region = dict(x=1, y=2, width=3, height=4)
    view.update_magnifier(QPointF(300, 250))
    assert view.region == dict(x=1, y=2, width=3, height=4)
    view.update_magnifier(QPointF(0, 0))
    assert view.magnifier.isHidden()
    view.update_magnifier(QPointF(200, 200))
    view.set_image(pixels, (200, 100))
    assert view.magnifier.isHidden()
    page.render(True)
    assert not page.resize_button.isEnabled()
