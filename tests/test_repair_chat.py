"""覆盖工作区打开、分轮富文本、工具合并/详情、滚动与主动 Diff 弹窗。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_repair_chat.py
"""

import shutil

import pytest

from test_developer_gui import gui, wait_jobs


def emit(page, kind, identity="call-1", name="action_contracts", number=1, **fields):
    value = {"type": kind, "toolCallId": identity, **fields}
    value["name" if kind == "repair_tool" else "toolName"] = name
    page.show_event({"round": number, "event": value})


def test_workspace_opens_actual_candidate_without_creating_missing_draft(gui, monkeypatch):
    from PySide6.QtGui import QDesktopServices
    app, window = gui
    page = window.repair_page
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toLocalFile()) or True)
    monkeypatch.setattr(window, "_interact", lambda operation: operation())
    page.open_workspace()
    assert opened == [str(window.host.candidate)]
    shutil.rmtree(window.host.candidate)
    with pytest.raises(ValueError, match="初始化 Candidate"):
        page.open_workspace()
    assert not window.host.candidate.exists() and len(opened) == 1


def test_removed_panels_return_space_and_answer_does_not_open_diff(gui, monkeypatch):
    app, window = gui
    page = window.repair_page
    assert not hasattr(page, "files") and not hasattr(page, "diff")
    assert not hasattr(page, "refresh_files")
    calls = []
    monkeypatch.setattr(page, "show_diff", lambda: calls.append(True))
    page.answered({"reason": "answered", "requests": 2, "round": 1, "answer": {"message": "完成"}})
    assert not calls
    assert "Agent · 第 1 轮" in page.chat.toPlainText()


@pytest.mark.parametrize("value", ["", "\n".join(f"+{i}: " + "x" * 200 for i in range(100))])
def test_diff_is_modeless_resizable_scrollable_and_readonly(gui, value):
    from PySide6.QtWidgets import QPlainTextEdit
    app, window = gui
    page = window.repair_page
    page.open_diff(value)
    dialog = page.diff_dialog
    assert dialog.isVisible() and not dialog.isModal() and dialog.isSizeGripEnabled()
    text = dialog.findChild(QPlainTextEdit)
    assert text.isReadOnly() and text.toPlainText() == (value or "暂无修改")
    dialog.resize(420, 260)
    app.processEvents()
    assert dialog.width() == 420
    if value:
        assert text.verticalScrollBar().maximum() > 0
        assert text.horizontalScrollBar().maximum() > 0
    dialog.close()


def test_diff_button_reads_current_fixed_baseline(gui):
    from PySide6.QtWidgets import QPlainTextEdit
    app, window = gui
    page = window.repair_page
    file = window.host.candidate / "steps.total.py"
    file.write_text(file.read_text().replace("if value > 0", "if value >= 0"))
    expected = window.host.diff()
    page.show_diff()
    wait_jobs(app, window)
    assert page.diff_dialog.findChild(QPlainTextEdit).toPlainText() == expected
    page.diff_dialog.close()


def test_roles_rounds_markdown_and_literal_user_text_are_distinct(gui):
    app, window = gui
    chat = window.repair_page.chat
    chat.add_message("你", "显示 <b>原文</b>", 1)
    chat.add_message("Agent", "## 观察类\n\n- 第一项\n- 第二项\n\n```python\nctx.action('observe.capture_screen')\n```", 1)
    chat.add_message("你", "继续", 2)
    text = chat.toPlainText()
    assert "你 · 第 1 轮" in text and "Agent · 第 1 轮" in text and "你 · 第 2 轮" in text
    assert "<b>原文</b>" in text
    assert "##" not in text and "```" not in text and "观察类" in text
    assert "ctx.action" in text and "#e8f2ff" in chat.toHtml() and "#f2f4f6" in chat.toHtml()


def test_tool_lifecycle_merges_same_call_and_preserves_repeated_calls_and_rounds(gui):
    from PySide6.QtCore import QUrl
    app, window = gui
    page, chat = window.repair_page, window.repair_page.chat
    emit(page, "tool_execution_start", args={"query": "original-argument"})
    emit(page, "repair_tool", arguments={"query": "original-argument"},
         result={"details": {"actions": "contract-result"}})
    assert len(chat.entries) == 1 and "等待完成确认" in chat.toPlainText()
    emit(page, "tool_execution_end", result={"content": [{"type": "text", "text": "contract-result"}]}, isError=False)
    assert len(chat.entries) == 1 and "成功" in chat.toPlainText()
    assert len(chat.entries[0]["events"]) == 3 and "contract-result" not in chat.toPlainText()
    chat.anchorClicked.emit(QUrl("tool:0"))
    assert chat.toPlainText().count("contract-result") == 1 and "original-argument" in chat.toPlainText()
    chat.anchorClicked.emit(QUrl("tool:0"))
    assert "contract-result" not in chat.toPlainText()
    emit(page, "tool_execution_end", identity="call-2", result={}, isError=False)
    emit(page, "tool_execution_end", number=2, result={}, isError=False)
    assert len(chat.entries) == 3


@pytest.mark.parametrize("host_failed", [True, False])
def test_tool_error_is_one_updated_diagnostic_with_both_event_sources(gui, host_failed):
    app, window = gui
    page = window.repair_page
    emit(page, "repair_tool", arguments={}, result={"isError": host_failed,
         "details": {"message": "specific host error", "traceback": "host traceback"} if host_failed else {}})
    emit(page, "tool_execution_end", isError=True,
         result={"content": [{"type": "text", "text": "pi read-result error"}]})
    assert len(page.chat.entries) == 1 and page.chat.entries[0]["status"] == "失败"
    assert page.diagnostics.errors.count() == 1
    details = page.diagnostics.errors.currentData()
    assert "repair_tool" in details["events"] and "tool_execution_end" in details["events"]
    page.diagnostics.copy_error()
    assert "pi read-result error" in app.clipboard().text()
    if host_failed:
        assert "host traceback" in app.clipboard().text()
    page.new()
    assert not page.chat.entries and not page.chat.tools and not page.tool_errors


def test_native_read_edit_and_validation_keep_completion_rows(gui):
    app, window = gui
    page = window.repair_page
    for name in ("read", "edit"):
        emit(page, "tool_execution_start", identity=name, name=name)
        emit(page, "tool_execution_end", identity=name, name=name, result={}, isError=False)
    emit(page, "validation", identity="validation-1", name="validate", ok=True, errors=[])
    emit(page, "tool_execution_end", identity="validation-1", name="validate", result={}, isError=False)
    assert len(page.chat.entries) == 3
    assert [entry["name"] for entry in page.chat.entries] == ["read", "edit", "validate"]
    assert all(entry["status"] == "成功" for entry in page.chat.entries)


def test_history_scroll_position_is_kept_and_bottom_can_follow(gui):
    app, window = gui
    page, chat = window.repair_page, window.repair_page.chat
    window.tabs.setCurrentWidget(page)
    window.resize(900, 800)
    window.show()
    app.processEvents()
    for i in range(12):
        chat.add_message("Agent", "段落内容\n\n" * 20, i + 1)
    app.processEvents()
    bar = chat.verticalScrollBar()
    assert bar.maximum() > 0
    position = bar.maximum() // 3
    bar.setValue(position)
    chat.add_message("Agent", "新的内容", 13)
    app.processEvents()
    assert bar.value() == position
    bar.setValue(bar.maximum())
    chat.add_message("你", "继续", 14)
    app.processEvents()
    assert bar.value() == bar.maximum()
