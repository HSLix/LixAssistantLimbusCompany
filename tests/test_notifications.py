"""覆盖跨页通知浮层、展开滚动、手动清除和详情边界，不调用模型或游戏。

从项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_notifications.py
"""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from test_user_gui import windows


def test_overlay_survives_navigation_resize_and_timeout(windows):
    app, _, user, developer = windows
    notices = user.notifications
    assert notices.parentWidget() is user
    user.switchTo(user.pages.widget(0))
    app.processEvents()
    before = user.task_scroll.geometry()
    notices.notify('第一条 <plain>', '原始详情')
    notices.notify('第二条')
    app.processEvents()
    assert user.task_scroll.geometry() == before
    assert notices.cards[0].isVisible() and not notices.cards[1].isVisible()
    assert notices.cards[0].badge.text() == '2'
    user.switchTo(user.general_settings)
    app.processEvents()
    assert notices.isVisible()
    user.resize(900, 650)
    app.processEvents()
    assert notices.x() + notices.width() == user.width() - 20
    assert notices.y() + notices.height() == user.height() - 20
    QTest.qWait(1250)
    assert len(notices.cards) == 2 and notices.isVisible()
    assert developer.notifications.isHidden()
    notices.cards[0].close_button.click()
    app.processEvents()
    assert notices.cards[0].title_label.text() == '第一条 <plain>'
    assert not notices.cards[0].badge.isVisible()


def test_expansion_is_bounded_and_new_notifications_do_not_shift_reading(windows):
    app, _, user, _ = windows
    notices = user.notifications
    for i in range(12):
        notices.notify(f'通知 {i}')
    notices.cards[0].badge.click()
    app.processEvents()
    assert notices.expanded and all(card.isVisible() for card in notices.cards)
    assert notices.height() <= (user.height() - 60) // 2
    scrollbar = notices.scroll.verticalScrollBar()
    assert scrollbar.maximum() > 0
    scrollbar.setValue(scrollbar.maximum() // 2)
    previous = scrollbar.value()
    notices.notify('新到达')
    app.processEvents()
    assert not notices.cards[0].isVisible()
    assert notices.new_button.isVisible()
    assert scrollbar.value() == previous
    notices.new_button.click()
    app.processEvents()
    assert notices.cards[0].isVisible() and scrollbar.value() == 0
    notices.collapse_button.click()
    assert not notices.expanded
    assert sum(card.isVisible() for card in notices.cards) == 1
    assert notices.cards[0].badge.text() == '13'


def test_escape_outside_click_and_clear(windows):
    app, _, user, _ = windows
    notices = user.notifications
    notices.notify('one')
    notices.notify('two')
    notices.cards[0].badge.click()
    QTest.keyClick(notices.collapse_button, Qt.Key.Key_Escape)
    assert not notices.expanded and len(notices.cards) == 2
    notices.expand()
    QTest.mouseClick(user.manifest_label, Qt.MouseButton.LeftButton)
    assert not notices.expanded and len(notices.cards) == 2
    notices.expand()
    user.switchTo(user.general_settings)
    app.processEvents()
    assert notices.expanded and notices.isVisible()
    notices.clear_button.click()
    assert notices.isHidden() and not notices.cards
    notices.notify('again')
    assert notices.isVisible() and not notices.expanded
    notices.cards[0].close_button.click()
    assert notices.isHidden()


def test_details_remain_plain_and_use_existing_dialog(windows, monkeypatch):
    from lalc.gui import ErrorDialog
    app, _, user, _ = windows
    opened = []
    monkeypatch.setattr(ErrorDialog, 'open', lambda dialog: opened.append(dialog))
    user.notifications.notify('<b>title</b>', '<raw>\n原始详情')
    card = user.notifications.cards[0]
    assert card.title_label.textFormat() == Qt.TextFormat.PlainText
    card.details_button.click()
    assert opened[0].details.toPlainText() == '<raw>\n原始详情'
    assert opened[0].parentWidget() is user
    assert len(user.notifications.cards) == 1
    opened[0].close()


def test_count_limit_long_text_and_opaque_dark_panel(windows):
    from qfluentwidgets import Theme, qconfig, setTheme
    app, _, user, _ = windows
    notices = user.notifications
    previous_theme = qconfig.theme
    try:
        setTheme(Theme.DARK)
        for i in range(100):
            notices.notify(f'{i} ' + '很长的通知' * 40)
        user.resize(760, 550)
        app.processEvents()
        assert notices.cards[0].badge.text() == '99+'
        assert notices.cards[0].title_label.height() <= notices.cards[0].title_label.maximumHeight()
        assert notices.width() <= user.width() - 40
        assert notices._normalBackgroundColor().alpha() == 255
        assert notices._hoverBackgroundColor() == notices._normalBackgroundColor()
        assert not notices.scroll.widget().autoFillBackground()
        assert not notices.scroll.viewport().autoFillBackground()
        notices.cards[0].close_button.click()
        assert notices.cards[0].badge.text() == '99'
    finally:
        setTheme(previous_theme)


@pytest.mark.parametrize('result, expected', [
    ({'status': 'completed', 'all_tasks_succeeded': True}, 'Execution completed'),
    ({'status': 'completed', 'all_tasks_succeeded': False}, 'Execution completed with failed tasks'),
    ({'status': 'interrupted', 'reason': 'user_cancelled'}, 'Execution stopped'),
    ({'status': 'interrupted', 'reason': 'execution_failed'}, 'Execution interrupted'),
])
def test_run_result_presentation(windows, result, expected):
    from lalc.i18n import tr
    _, _, user, _ = windows
    user.notifications.notify_result(result)
    assert user.notifications.cards[0].message == tr(expected)
