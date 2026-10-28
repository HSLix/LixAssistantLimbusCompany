"""正式 Fluent GUI 的原生预览与双窗口检查；所有配置使用临时目录。

从项目根目录运行（macOS）：
QT_QPA_PLATFORM=cocoa .venv/bin/python tests/gui_native_probe.py
添加 --show 可保持窗口供人工检查；不调用 Agent、游戏或真实用户配置。
"""

import argparse
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from qfluentwidgets import FluentWindow

from lalc.application import ApplicationService
from lalc.developer import DeveloperHost
from lalc.gui import GuiCoordinator
from lalc.lifecycle import ApplicationLifecycle
from lalc.manifest import ManifestManager


def main():
    args = argparse.ArgumentParser()
    args.add_argument("--show", action="store_true")
    options = args.parse_args()
    project = Path(__file__).resolve().parents[1]
    output = project / ".generated/fluent-gui"
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    with TemporaryDirectory(prefix="lalc-fluent-gui-") as directory:
        root = Path(directory)
        shutil.copytree(project / "example/pages", root / "pages")
        manager = ManifestManager(root)
        saved = manager.publish(project / "example/extensible-pages/manifest.json")
        assert saved.ok, saved.errors
        assert manager.set_default(saved.loaded.manifest_id).ok
        owner = GuiCoordinator(ApplicationService(root, manifest_manager=manager), ApplicationLifecycle())
        owner.host = DeveloperHost(owner.service, root / "candidate")
        user, developer = owner.open_window(), owner.open_window(True)
        assert isinstance(user, FluentWindow) and isinstance(developer, FluentWindow)
        assert not user.agent_controls.isEnabled()
        for window in (user, developer):
            window.navigationInterface.expand(useAni=False)
        user.activateWindow()
        QTest.qWait(400)
        user.grab().save(str(output / "user-dashboard.png"))
        user.switchTo(user.general_settings)
        QTest.qWait(400)
        user.grab().save(str(output / "user-settings.png"))
        developer.switchTo(developer.settings_view)
        developer.activateWindow()
        QTest.qWait(400)
        developer.grab().save(str(output / "developer-settings.png"))
        result = {
            "user_is_fluent": isinstance(user, FluentWindow),
            "developer_is_fluent": isinstance(developer, FluentWindow),
            "user_routes": [user.pages.widget(i).objectName() for i in range(user.pages.count())],
            "developer_routes": [developer.pages.widget(i).objectName() for i in range(developer.pages.count())],
            "shared_service": user.service is developer.service,
            "output": str(output),
        }
        (output / "native-probe.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        user.switchTo(user.pages.widget(0))
        if options.show:
            app.exec()
        else:
            developer.close()
            user.close()
            app.processEvents()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        owner.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
