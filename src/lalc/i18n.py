"""GUI 语言的独立保存、启动解析与 Qt 翻译资源；不改变游戏语言。"""

import json
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QLibraryInfo, QLocale, QTranslator
from qfluentwidgets import FluentTranslator

from .runtime import atomic_write_json


LANGUAGES = ("system", "zh_CN", "en_US")


def load_language(data_root: Path) -> str:
    """缺少旧环境设置时跟随系统；无效文件保留并报告，不静默覆盖。"""
    path = data_root / "gui-settings.json"
    if not path.exists():
        return "system"
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict or set(value) != {"language"} or value["language"] not in LANGUAGES:
        raise ValueError("Invalid GUI language settings; the original file is preserved.")
    return value["language"]


def save_language(data_root: Path, language: str) -> None:
    """只保存下次启动的选择，不替换当前进程的翻译器。"""
    if language not in LANGUAGES:
        raise ValueError("Invalid GUI language selection.")
    atomic_write_json(data_root / "gui-settings.json", {"language": language})


def resolve_language(selection: str, system: QLocale | None = None) -> str:
    if selection not in LANGUAGES:
        raise ValueError("Invalid GUI language selection.")
    if selection == "system":
        return "zh_CN" if (system or QLocale.system()).language() == QLocale.Language.Chinese else "en_US"
    return selection


def install_translations(app, language: str) -> None:
    """在创建控件前安装并持有三类翻译器；生产路径每个应用仅安装一次。"""
    if language not in LANGUAGES[1:]:
        raise ValueError("GUI startup language must be resolved.")
    prepared = []
    if language == "zh_CN":
        qt = QTranslator(app)
        if not qt.load("qtbase_zh_CN", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
            raise RuntimeError("Qt Chinese translations are unavailable.")
        fluent = FluentTranslator(QLocale(language), app)
        own = QTranslator(app)
        if not own.load(str(Path(__file__).with_name("translations") / "lalc_zh_CN.qm")):
            raise RuntimeError("LALC Chinese translations are unavailable.")
        if fluent.isEmpty():
            raise RuntimeError("Fluent Chinese translations are unavailable.")
        prepared = [qt, fluent, own]
    for translator in getattr(app, "_lalc_translators", []):
        app.removeTranslator(translator)
        translator.deleteLater()
    for translator in prepared:
        app.installTranslator(translator)
    app._lalc_translators = prepared
    app._lalc_language = language


def current_language() -> str:
    """返回本进程已生效语言，不读取待重启的持久化选择。"""
    return getattr(QCoreApplication.instance(), "_lalc_language", "en_US")


def tr(source: str) -> str:
    return QCoreApplication.translate("LALC", source)


def activity_text(name: str) -> str:
    """仅翻译已知活动的显示名，不改服务互斥标识或日志。"""
    return {
        "Capture": tr("Capture"), "Capture 连接": tr("Connecting to window"),
        "Capture 截图": tr("Capturing screenshot"), "Capture 调整窗口尺寸": tr("Resizing window"),
        "Capture 保存": tr("Saving Asset"), "Candidate 初始化": tr("Initializing Candidate"),
        "Candidate 校验": tr("Validating Candidate"), "Candidate 发布": tr("Publishing Candidate"),
        "新对话": tr("New Conversation"), "Agent Settings 检查": tr("Checking Agent settings"),
    }.get(name, name)
