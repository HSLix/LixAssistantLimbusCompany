"""正式 Run 的统一平台替身与应用注册，避免回归测试依赖 Windows 游戏。"""
import pytest


@pytest.fixture(autouse=True)
def application_environment(monkeypatch):
    import lalc.application as application
    import lalc.manifest as manifest
    from runtime_support import test_actions
    from test_input_control import FakeWindow

    monkeypatch.setattr(application, "WindowsWindowPlatform", lambda **_: FakeWindow())
    monkeypatch.setattr(manifest, "application_actions", test_actions)
