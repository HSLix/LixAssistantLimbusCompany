"""覆盖 GUI 语言保存、Qt 资源、双窗口与示例页兼容；不调用模型或游戏。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_gui_language.py
"""

import ast
import json
import os
from pathlib import Path
import shutil
from string import Formatter
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest
from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QLabel, QDialogButtonBox

from lalc.gui import ErrorDialog
from lalc.i18n import (current_language, install_translations, load_language, resolve_language,
                       save_language, tr)
from lalc.user_pages import UserSettings, discover_pages, task_inputs
from test_user_pages import app, owner


@pytest.mark.parametrize("system, expected", [("zh_CN", "zh_CN"), ("zh_TW", "zh_CN"),
                                               ("zh_HK", "zh_CN"), ("en_US", "en_US"), ("ja_JP", "en_US")])
def test_system_language_and_explicit_override(system, expected):
    assert resolve_language("system", QLocale(system)) == expected
    assert resolve_language("en_US", QLocale(system)) == "en_US"
    assert resolve_language("zh_CN", QLocale(system)) == "zh_CN"


def test_language_file_is_independent_and_failed_write_preserves_choice(tmp_path, monkeypatch):
    import lalc.i18n as i18n
    store = UserSettings(tmp_path)
    store.save_task("exp", True, 3)
    before = store.path.read_bytes()
    assert load_language(tmp_path) == "system"
    save_language(tmp_path, "en_US")
    assert load_language(tmp_path) == "en_US"
    def fail(*args):
        raise OSError("disk failure")
    monkeypatch.setattr(i18n, "atomic_write_json", fail)
    with pytest.raises(OSError):
        save_language(tmp_path, "zh_CN")
    assert load_language(tmp_path) == "en_US"
    assert store.path.read_bytes() == before
    assert task_inputs([], (), UserSettings(tmp_path))[1] == {}
    with pytest.raises(ValueError):
        save_language(tmp_path, "fr_FR")


@pytest.mark.parametrize("value", [{"language": "bad"}, {"language": []}, {}, [], {"language": "en_US", "pages": {}}])
def test_invalid_language_file_is_preserved(tmp_path, value):
    path = tmp_path / "gui-settings.json"
    path.write_text(json.dumps(value))
    before = path.read_bytes()
    with pytest.raises(ValueError):
        load_language(tmp_path)
    assert path.read_bytes() == before


def test_selection_is_saved_during_activity_but_does_not_retranslate_or_allow_reload(owner, app):
    user = owner.user
    game_language = owner.service.game_language
    developer = owner.open_window(True)
    assert not user.agent_controls.isEnabled()
    assert user.language_choice.isEnabled()
    assert not hasattr(developer, "language_choice")
    before = user.start_button.text()
    with owner.service.activity("Agent"):
        user.language_choice.setCurrentIndex(user.language_choice.findData("en_US"))
        assert load_language(owner.service.data_root) == "en_US"
        assert current_language() == "zh_CN"
        assert not user.reload_button.isEnabled()
        with pytest.raises(ValueError, match="不能重载"):
            owner.request_reload()
    dialog = ErrorDialog("原始错误 mixed", "原文 traceback")
    assert dialog.details_button.text() == "展开错误详情"
    assert dialog.details.toPlainText() == "原文 traceback"
    dialog.close()
    user.close()
    reopened = owner.open_window()
    assert reopened.start_button.text() == before
    assert reopened.language_choice.currentData() == "en_US"
    assert owner.service.game_language == game_language
    developer.close()
    new_developer = owner.open_window(True)
    assert new_developer.trial_button.text() == "试运行所选 Plan"
    assert reopened.business_pages[0].context.language == "zh_CN"


@pytest.mark.parametrize("language", ["zh_CN", "en_US"])
def test_fresh_process_uses_saved_language_for_both_windows_and_pages(tmp_path, language):
    root = Path(__file__).resolve().parents[1]
    shutil.copytree(root / "example/pages", tmp_path / "pages")
    save_language(tmp_path, language)
    script = '''
import json, sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
app = QApplication([])
if sys.platform == 'darwin':
    from qframelesswindow.mac import MacFramelessWindowBase
    for name in ('updateFrameless', 'setSystemTitleBarButtonVisible', '_updateSystemTitleBar'):
        setattr(MacFramelessWindowBase, name, lambda *args: None)
from lalc.application import ApplicationService
from lalc.gui import GuiCoordinator
from lalc.lifecycle import ApplicationLifecycle
from lalc.i18n import current_language
owner = GuiCoordinator(ApplicationService(Path(sys.argv[1])), ApplicationLifecycle())
developer = owner.open_window(True)
user = owner.open_window()
print(json.dumps([current_language(), user.start_button.text(), developer.trial_button.text(),
                  [page.context.language for page in user.business_pages], owner.service.game_language]))
user.close()
developer.close()
'''
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path)], cwd=root,
                            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"}, capture_output=True,
                            text=True, timeout=20, check=True)
    values = json.loads(result.stdout.splitlines()[-1])
    assert values == [language, "开始运行 Plan" if language == "zh_CN" else "Start Plan",
                      "试运行所选 Plan" if language == "zh_CN" else "Trial selected Plan",
                      [language] * 3, "en"]


def test_save_failure_restores_language_control(owner, monkeypatch):
    import lalc.i18n as i18n
    errors = []
    monkeypatch.setattr(ErrorDialog, "open", lambda dialog: errors.append(dialog.details.toPlainText()))
    def fail(*args):
        raise OSError("language disk failure")
    monkeypatch.setattr(i18n, "atomic_write_json", fail)
    owner.user.language_choice.setCurrentIndex(owner.user.language_choice.findData("en_US"))
    assert owner.user.language_choice.currentData() == "system"
    assert load_language(owner.service.data_root) == "system"
    assert len(errors) == 1 and "language disk failure" in errors[0]


@pytest.mark.parametrize("language, settings, cancel", [("zh_CN", "通用设置", "取消"),
                                                       ("en_US", "General Settings", "Cancel")])
def test_qt_fluent_and_application_resources(app, language, settings, cancel):
    from qfluentwidgets import FluentTranslator
    install_translations(app, language)
    assert tr("General Settings") == settings
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
    assert buttons.button(QDialogButtonBox.StandardButton.Cancel).text() == cancel
    if language == "zh_CN":
        assert len(app._lalc_translators) == 3
        assert any(isinstance(item, FluentTranslator) and not item.isEmpty() for item in app._lalc_translators)


@pytest.mark.parametrize("language", ["zh_CN", "en_US"])
def test_examples_translate_navigation_content_and_validation_but_legacy_does_not(app, tmp_path, language):
    install_translations(app, language)
    store = UserSettings(tmp_path)
    store.save("pages", "exp", {"message": "用户 input"})
    directory = Path(__file__).resolve().parents[1] / "example/pages"
    pages, errors = discover_pages(directory, store)
    assert not errors and len(pages) == 3
    by_id = {page.page_id: page for page in pages}
    for identity in ("exp", "mirror"):
        page = by_id[identity]
        assert page.context.language == language
        assert page.name == ({"exp": "经验本教学示例", "mirror": "镜牢教学示例"}[identity]
                             if language == "zh_CN" else {"exp": "EXP example", "mirror": "Mirror example"}[identity])
        label = page.widget.findChildren(QLabel)[0].text()
        assert ("必填" in label) if language == "zh_CN" else ("required" in label)
        if identity == "exp":
            assert page.widget.message.text() == "用户 input"
        page.widget.message.clear()
        with pytest.raises(ValueError, match="消息不能为空" if language == "zh_CN" else "Message cannot be empty"):
            page.widget.submit()
    legacy = by_id["legacy-language-example"]
    assert legacy.name == "固定语言兼容示例" and legacy.task_id is None
    assert "不支持语言切换" in legacy.widget.findChildren(QLabel)[0].text()
    legacy.widget.note.setText("retained")
    legacy.context.save(legacy.widget.submit())
    assert UserSettings(tmp_path).value["pages"][legacy.page_id] == {"note": "retained"}
    for page in pages:
        page.widget.close()


def test_catalog_covers_literal_gui_messages_and_preserves_format_fields(app):
    root = Path(__file__).resolve().parents[1] / "src/lalc"
    catalog = ET.parse(root / "translations/lalc_zh_CN.ts")
    messages = {item.findtext("source"): item.findtext("translation") for item in catalog.findall("context/message")}
    fields = lambda value: sorted(field for _, field, _, _ in Formatter().parse(value) if field is not None)
    install_translations(app, "zh_CN")
    for filename in ("gui.py", "developer_gui.py", "repair_chat.py", "lifecycle.py", "i18n.py"):
        for node in ast.walk(ast.parse((root / filename).read_text())):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "tr":
                assert isinstance(node.args[0], ast.Constant), (filename, node.lineno)
                source = node.args[0].value
                assert messages[source]
                assert fields(source) == fields(messages[source])
                assert tr(source) == messages[source]


def test_page_name_falls_back_and_bad_translation_metadata_is_isolated(app, tmp_path):
    install_translations(app, "en_US")
    directory = tmp_path / "pages"
    directory.mkdir()
    source = '''
from PySide6.QtWidgets import QWidget
PAGE_ID = "partial"
PAGE_NAME = "Original name"
PAGE_NAMES = {"zh_CN": "中文名称"}
class Page(QWidget):
    def submit(self): return {}
def create_page(context): return Page()
'''
    (directory / "partial.py").write_text(source)
    (directory / "bad.py").write_text(source.replace('"partial"', '"bad"').replace('{"zh_CN": "中文名称"}', '{"en_US": ""}'))
    pages, errors = discover_pages(directory, UserSettings(tmp_path))
    assert len(pages) == 1 and pages[0].name == "Original name"
    assert len(errors) == 1 and "PAGE_NAMES" in errors[0]
    pages[0].widget.close()


@pytest.mark.parametrize("language", ["zh_CN", "en_US"])
def test_dynamic_controls_chat_and_notifications_keep_original_details(owner, app, language):
    install_translations(app, language)
    developer = owner.open_window(True)
    chat = developer.repair_page.chat
    chat.add_message("你", "用户 <raw>", 1)
    chat.upsert_tool(1, "call-1", "validate", "tool_execution_end", {"isError": False})
    assert ("你 · 第 1 轮" if language == "zh_CN" else "You · Round 1") in chat.toPlainText()
    assert ("成功" if language == "zh_CN" else "Succeeded") in chat.toPlainText()
    assert "用户 <raw>" in chat.toPlainText()
    state = owner.service.state
    state["activity"] = "Candidate 初始化"
    developer.render_state(state)
    assert developer.status.text() == ("当前活动：初始化 Candidate" if language == "zh_CN"
                                       else "Current activity: Initializing Candidate")
    from lalc.developer_gui import TrialDialog
    dialog = TrialDialog(owner.service, developer)
    state.update(paused=True, trace=[], pause_info=None)
    dialog.render(state)
    assert dialog.pause.text() == ("恢复" if language == "zh_CN" else "Resume")
    assert dialog.stop.text() == ("停止" if language == "zh_CN" else "Stop")
    dialog.done(0)
    developer.notifications.notify(tr("Execution completed"), "原始结果 raw")
    from qfluentwidgets import InfoBar
    bar = developer.notifications.findChildren(InfoBar)[0]
    assert bar.titleLabel.text() == ("执行完成" if language == "zh_CN" else "Execution completed")
    error = ErrorDialog("原文错误", "原文 details", fatal=True)
    assert error.windowTitle() == ("致命错误" if language == "zh_CN" else "Fatal error")
    assert error.details.toPlainText() == "原文 details"
    error.close()
