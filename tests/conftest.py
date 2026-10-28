"""统一平台替身与应用注册；真实 Agent 测试必须显式开启。"""
import pytest
import os
import sys


@pytest.fixture(autouse=True)
def stable_gui_language(request):
    """既有 GUI 回归固定中文；语言专项测试自行切换，不依赖机器区域设置。"""
    if request.module.__name__ not in {
        "test_user_gui", "test_user_gui_p0", "test_user_pages", "test_developer_gui",
        "test_error_handling", "test_gui_language",
        "test_repair_chat", "test_input_control", "test_example_workflow",
    }:
        yield
        return
    from PySide6.QtWidgets import QApplication
    from lalc.i18n import install_translations
    app = QApplication.instance() or QApplication([])
    install_translations(app, "zh_CN")
    yield
    install_translations(app, "en_US")


def pytest_addoption(parser):
    """仅在确需验证 Agent 功能时显式开启相关测试。"""
    parser.addoption("--run-agent-tests", action="store_true", help="Run explicitly selected Agent/pi tests")


def pytest_collection_modifyitems(config, items):
    """默认跳过 Agent 测试，避免普通回归启动 pi 或模型服务。"""
    if not config.getoption("--run-agent-tests"):
        skip = pytest.mark.skip(reason="Agent tests require explicit --run-agent-tests")
        for item in items:
            if item.get_closest_marker("agent"):
                item.add_marker(skip)


@pytest.fixture(autouse=True)
def application_environment(monkeypatch):
    if sys.platform == "darwin":
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        platform = app.platformName() if app is not None else os.environ.get("QT_QPA_PLATFORM")
        if platform == "offscreen":
            from qframelesswindow.mac import MacFramelessWindowBase
            # offscreen 无真实 NSWindow；只替代系统标题栏调用，原生验收不走此路径。
            for name in ("updateFrameless", "setSystemTitleBarButtonVisible", "_updateSystemTitleBar"):
                monkeypatch.setattr(MacFramelessWindowBase, name, lambda *args: None)
    import lalc.application as application
    import lalc.manifest as manifest
    from runtime_support import test_actions
    from test_input_control import FakeWindow

    monkeypatch.setattr(application, "WindowsWindowPlatform", lambda **_: FakeWindow())
    monkeypatch.setattr(manifest, "application_actions", test_actions)
