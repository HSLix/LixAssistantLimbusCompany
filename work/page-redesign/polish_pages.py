from pathlib import Path
base = Path('work/page-redesign/pages')
p = base / 'mirror/page.py'
s = p.read_text(encoding='utf-8')
s = s.replace('                button.setCheckable(True)', '''                button.setCheckable(True)
                button.setStyleSheet(
                    "QPushButton:checked { background-color: #3a2d1a; color: #ffe9b5;"
                    " border: 2px solid #d9a441; border-radius: 6px; font-weight: bold; }"
                )''')
p.write_text(s, encoding='utf-8')
p = base / 'team_presets/page.py'
s = p.read_text(encoding='utf-8').replace('    QLabel,', '    QLabel,\n    QListWidget,\n    QListWidgetItem,')
start = s.index('        self._order_label = QLabel()')
end = s.index('        self._clear_button = QPushButton(', start)
s = s[:start] + '''        self._order_list = QListWidget()
        self._order_list.setFixedWidth(170)
        self._order_list.setMinimumHeight(280)
        column.addWidget(self._order_list)
        actions = QHBoxLayout()
        for caption, callback in (
            ("↑", lambda: self._move_sinner(-1)),
            ("↓", lambda: self._move_sinner(1)),
            (self._context.translate("移除", "Remove"), self._remove_sinner),
        ):
            button = QPushButton(caption)
            button.clicked.connect(callback)
            actions.addWidget(button)
        column.addLayout(actions)
''' + s[end:]
s = s.replace('        self._order_label.setText(self._order_text(team))', '''        current = self._order_list.currentRow()
        self._order_list.clear()
        for position, sinner_id in enumerate(team, 1):
            _, zh, en = self._sinner_buttons[sinner_id]
            self._order_list.addItem(f"{position}. {self._context.translate(zh, en)}")
        if team:
            self._order_list.setCurrentRow(min(max(current, 0), len(team) - 1))''')
start = s.index('    def _order_text(self, team):')
end = s.index('    def _refresh(self):', start)
s = s[:start] + '''    def _move_sinner(self, delta):
        """调整当前罪人顺序，边界外保持不变。"""
        row = self._order_list.currentRow()
        team = self._teams[self._active]
        target = row + delta
        if row < 0 or not 0 <= target < len(team):
            return
        team[row], team[target] = team[target], team[row]
        self._refresh()
        self._order_list.setCurrentRow(target)

    def _remove_sinner(self):
        """移除已选列表中的当前罪人并同步卡片编号。"""
        row = self._order_list.currentRow()
        if row >= 0:
            self._teams[self._active].pop(row)
            self._refresh()

''' + s[end:]
s = s.replace('    QListWidgetItem,\n', '').replace('BodyLabel, ComboBox, FluentIcon', 'BodyLabel, FluentIcon')
p.write_text(s, encoding='utf-8')
for p in (base / 'mirror/page.py', base / 'team_presets/page.py'):
    s = p.read_text(encoding='utf-8')
    s = s.replace('        self._tabs = QTabWidget()', '''        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            "QTabWidget::pane { border: 0; }"
            "QTabBar::tab { padding: 10px 18px; border: 0; margin-right: 4px; }"
            "QTabBar::tab:selected { border-bottom: 3px solid #b08a4a; font-weight: bold; }"
        )''')
    p.write_text(s, encoding='utf-8')
