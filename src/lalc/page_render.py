"""在短生命周期 Qt 子进程中渲染草稿；不是操作系统安全沙箱。"""

import os
import subprocess
import sys

from .page_packages import materialized_page


def render_snapshot(snapshot, data_root, language, width, checkpoint):
    """固定页面整包，等待有界截图；取消或超时先停止子进程再清理。"""
    if type(width) is not int or not 480 <= width <= 1200:
        raise ValueError("截图宽度须为 480–1200。")
    from time import monotonic

    work = data_root / "work"
    work.mkdir(parents=True, exist_ok=True)
    with materialized_page(snapshot, work_dir=work) as entry:
        output = entry.parent.parent / "page.png"
        errors = output.with_suffix(".txt")
        command = [sys.executable]
        if not getattr(sys, "frozen", False):
            command += ["-m", "lalc"]
        command += ["--page-render-worker", str(entry), str(output), language, str(width)]
        checkpoint()
        with subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)) as worker:
            deadline = monotonic() + 20
            try:
                while True:
                    checkpoint()
                    try:
                        code = worker.wait(timeout=.1)
                        break
                    except subprocess.TimeoutExpired:
                        if monotonic() >= deadline:
                            raise RuntimeError("草稿渲染超过 20 秒。") from None
            finally:
                if worker.poll() is None:
                    worker.kill()
        checkpoint()
        if code:
            detail = errors.read_text(encoding="utf-8") if errors.is_file() else f"子进程退出码 {code}"
            raise RuntimeError(f"草稿渲染失败：{detail}")
        if not output.is_file() or output.stat().st_size > 8 * 1024 * 1024:
            raise RuntimeError("草稿截图不可用或过大。")
        return output.read_bytes()


def render_worker(entry, output, language, width):
    """启动独立 Qt 环境，用页面默认值截图；不调用 submit。"""
    from PySide6.QtWidgets import QApplication, QScrollArea
    from qfluentwidgets import Theme, setTheme

    from .i18n import install_translations
    from .page_drafts import MemorySettings
    from .user_pages import create_business_page, load_page_module

    try:
        if not 480 <= width <= 1200:
            raise ValueError("截图宽度须为 480–1200。")
        app = QApplication([])
        install_translations(app, language)
        setTheme(Theme.LIGHT)
        page = create_business_page(entry, *load_page_module(entry, entry.read_bytes()), MemorySettings({"pages": {}}))
        viewport = QScrollArea()
        viewport.setWidgetResizable(True)
        viewport.setWidget(page.widget)
        viewport.resize(width, 720)
        viewport.show()
        app.processEvents()
        if not viewport.grab().save(str(output), "PNG"):
            raise RuntimeError("Qt 未能保存草稿截图。")
    except Exception as error:
        output.with_suffix(".txt").write_text(f"{type(error).__name__}: {error}"[:2000], encoding="utf-8")
        return 1
    return 0
