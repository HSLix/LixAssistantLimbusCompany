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


def test_capture_match_preview_uses_default_algorithm_and_cancel_does_not_save(gui, monkeypatch):
    """同图默认匹配、编号分数与红框一致，取消不保存或重新截图。"""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QDialog
    from qfluentwidgets import PlainTextEdit
    from lalc.developer_gui import OcrView
    from lalc.assets import AssetLibrary
    from lalc.recognition import detect_template
    from test_assets import pixels, screenshot, template
    app, window = gui
    page = window.capture_page
    image = screenshot()
    snapshot = (pixels(image), (12, 8), 7)
    window.host.preview = snapshot
    page.view.set_image(snapshot[0], snapshot[1])
    region = dict(x=2, y=1, width=2, height=2)
    page.view.region = region
    page.name.setText('ui/match-preview')
    expected = detect_template(image, template(), threshold=0.8)
    assert len(expected) == 2
    content, matches = window.host.match_crop_preview(snapshot, region)
    assert matches == expected
    assert content == AssetLibrary.crop_content(snapshot[0], snapshot[1], region)[0]
    checked = []
    def inspect(dialog):
        view = dialog.findChild(OcrView)
        assert view.items == [{"box": match} for match in expected]
        assert view.color == Qt.GlobalColor.red and view.line_width == 1
        view.resize(600, 400)
        plain = OcrView()
        plain.set_image(snapshot[0], snapshot[1])
        plain.resize(view.size())
        assert view.image == plain.image
        marked = view.grab().toImage()
        assert marked != plain.grab().toImage()
        rect = view.image_rect()
        assert marked.pixelColor(rect.x() + round(2 * rect.width() / 12),
                                 rect.y() + round(2 * rect.height() / 8)) == QColor('red')
        text = dialog.findChild(PlainTextEdit).toPlainText()
        assert text.splitlines()[1:] == [f'{i}. {match["score"]!r}' for i, match in enumerate(expected, 1)]
        checked.append(True)
        # 即使当前截图被替换，弹窗仍展示固定快照。
        window.host.preview = (bytes(len(snapshot[0])), snapshot[1], 8)
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(QDialog, 'exec', inspect)
    page.save()
    wait_jobs(app, window)
    assert checked == [True]
    assert not (window.service.asset_library.root / 'ui/match-preview').exists()
