from pathlib import Path
base = Path('work/page-redesign/pages')
p = base / 'team_presets/page.py'
s = p.read_text(encoding='utf-8').replace('出战神人顺序', '出战罪人顺序')
s = s.replace('    QToolButton,', '    QToolButton,\n    QTabWidget,')
s = s.replace('SLOT_BOX_WIDTH = 320', 'SLOT_BOX_WIDTH = 180').replace('SLOT_BOX_HEIGHT = 66', 'SLOT_BOX_HEIGHT = 116')
s = s.replace('self.setFixedSize(SLOT_BOX_WIDTH, SLOT_BOX_HEIGHT)', 'self.setMinimumSize(SLOT_BOX_WIDTH, SLOT_BOX_HEIGHT)\n        self.setCheckable(True)')
s = s.replace('self.setText(f"{self._caption}　　　未使用")', 'self.setChecked(False)\n            self.setText(f"{self._caption}\\n—")')
s = s.replace('self.setText(f"{self._caption}　　　第 {order_index} 次点击")', 'self.setChecked(True)\n            self.setText(f"{self._caption}\\n{order_index}")')
s = s.replace('"QPushButton:pressed { background-color: #4a3a22; }"', '"QPushButton:pressed { background-color: #4a3a22; }"\n    "QPushButton:checked { border: 2px solid #e0b34a; background-color: #33270f; }"')
s = s.replace('        self._slot_boxes = {}', '        self._slot_boxes = {}\n        self._keyword_buttons = {}')
start = s.index('        top = QHBoxLayout()')
end = s.index('        body_layout.addStretch(1)', start)
s = s[:start] + '''        top = QHBoxLayout()
        top.setSpacing(14)
        top.addLayout(self._build_team_column(), 0)
        self._tabs = QTabWidget()
        formation = QWidget()
        formation_layout = QHBoxLayout(formation)
        formation_layout.addLayout(self._build_sinner_column(), 1)
        formation_layout.addLayout(self._build_side_column(), 0)
        self._tabs.addTab(formation, self._context.translate("罪人编队", "Sinner formation"))
        self._tabs.addTab(self._build_mirror_section(), self._context.translate("镜牢偏好", "Mirror preferences"))
        top.addWidget(self._tabs, 1)
        body_layout.addLayout(top, 0)
''' + s[end:]
start = s.index('        self._keyword_combo = ComboBox(section)')
end = s.index('        hint = QLabel(', start)
s = s[:start] + '''        keyword_grid = QGridLayout()
        for index, (value, zh_name, en_name) in enumerate(KEYWORDS):
            button = QPushButton(self._context.translate(zh_name, en_name))
            button.setCheckable(True)
            button.setMinimumHeight(52)
            button.setStyleSheet(TEAM_BUTTON_STYLE)
            button.clicked.connect(lambda checked=False, i=index: self._keyword_changed(i))
            self._keyword_buttons[value] = button
            keyword_grid.addWidget(button, index // 2, index % 2)
        left_layout.addLayout(keyword_grid)
''' + s[end:]
s = s.replace('        hint.setFixedWidth(360)', '        hint.setMaximumWidth(420)')
s = s.replace('        for slot, zh_name, en_name in SLOT_LABELS:', '        gift_row = QHBoxLayout()\n        for slot, zh_name, en_name in SLOT_LABELS:')
s = s.replace('            right_layout.addWidget(box)', '            gift_row.addWidget(box)')
s = s.replace('        self._clear_order_button = QPushButton(', '        right_layout.addLayout(gift_row)\n        self._gift_status = BodyLabel()\n        right_layout.addWidget(self._gift_status)\n        self._clear_order_button = QPushButton(')
s = s.replace('            self._gift_keywords[self._active] = KEYWORDS[index][0]', '            self._gift_keywords[self._active] = KEYWORDS[index][0]\n            self._refresh_mirror()')
start = s.index('        self._keyword_combo.blockSignals(True)')
end = s.index('        order = self._gift_orders[self._active]', start)
s = s[:start] + '''        for keyword, button in self._keyword_buttons.items():
            button.setChecked(keyword == self._gift_keywords[self._active])
''' + s[end:]
s = s.replace('            box.show_order(index)', '''            box.show_order(index)
        skipping = self._gift_keywords[self._active] == DEFAULT_KEYWORD or not order
        self._gift_status.setText(self._context.translate(
            "当前：跳过初始饰品" if skipping else "点击顺序：" + " → ".join(map(str, order)),
            "Current: refuse gifts" if skipping else "Click order: " + " → ".join(map(str, order)),
        ))''')
s = s.replace('"右侧第 1 个饰品（上）"', '"位置 1 · 上"').replace('"右侧第 2 个饰品（中）"', '"位置 2 · 中"').replace('"右侧第 3 个饰品（下）"', '"位置 3 · 下"')
s = s.replace('点击长条记录', '点击卡片记录').replace('Click the bars', 'Click the cards')
p.write_text(s, encoding='utf-8')
p = base / 'mirror/page.py'
s = p.read_text(encoding='utf-8').replace('from PySide6.QtCore import Qt, QTimer', 'from PySide6.QtCore import Qt, QTimer\nfrom PySide6.QtGui import QPixmap')
s = s.replace('    QHBoxLayout,', '    QHBoxLayout,\n    QGridLayout,\n    QScrollArea,\n    QTabWidget,')
pos = s.index('\ndef _team_name')
s = s[:pos] + '''
# 键按游戏卡片从左至右、从上至下固定，图片编号与用户提供的资源一致。
STAR_CARDS = (
    ("star_of_the_beginning", "起始之星", "Star of the Beginning"),
    ("cumulating_starcloud", "积聚星云", "Cumulating Starcloud"),
    ("interstellar_travel", "星际旅行", "Interstellar Travel"),
    ("star_shower", "流星雨", "Star-shower"),
    ("binary_star_shop", "双星商店", "Binary Star-shop"),
    ("moon_star_shop", "月星商店", "Moon Star-shop"),
    ("favor_of_the_nebulae", "星云眷顾", "Favor of the Nebulae"),
    ("starlight_guidance", "星光指引", "Starlight Guidance"),
    ("chance_comet", "机遇彗星", "Chance Comet"),
    ("perfected_possibility", "完美可能性", "Perfected Possibility"),
)


def _restore_star_levels(raw):
    """仅接受已知卡片的整数目标档位；旧配置默认全部不选。"""
    raw = raw if isinstance(raw, dict) else {}
    return {key: raw[key] if type(raw.get(key)) is int and raw[key] in (0, 1, 2) else 0
            for key, _, _ in STAR_CARDS}

''' + s[pos:]
s = s.replace('        self._teams = _restore_teams(config)', '        self._teams = _restore_teams(config)\n        self._star_levels = _restore_star_levels(config.get("star_levels"))\n        self._star_buttons = {}')
s = s.replace('        layout = QVBoxLayout(self)\n        layout.setSpacing(10)', '''        root = QVBoxLayout(self)
        self._tabs = QTabWidget()
        root.addWidget(self._tabs)
        teams_tab = QWidget()
        teams_layout = QVBoxLayout(teams_tab)
        teams_layout.addWidget(self._build_team_card())
        teams_layout.addStretch(1)
        self._tabs.addTab(teams_tab, context.translate("运行与队伍", "Run and teams"))
        self._tabs.addTab(self._build_star_tab(), context.translate("星光强化", "Starlight"))
        rewards_tab = QWidget()
        self._tabs.addTab(rewards_tab, context.translate("结算设置", "Rewards"))
        layout = QVBoxLayout(rewards_tab)
        layout.setSpacing(10)''')
s = s.replace('        layout.addWidget(self._build_team_card())\n', '')
s = s.replace('        layout.addWidget(note)', '        teams_layout.insertWidget(1, note)')
pos = s.index('    # ---------- 主页队伍卡片 ----------')
s = s[:pos] + '''    def _build_star_tab(self):
        """按游戏顺序展示十张卡，独立保存不选、+、++ 目标档位。"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        layout = QVBoxLayout(body)
        note = BodyLabel(self._context.translate(
            "设置目标档位：不选 / + / ++。当前仅保存配置，尚未接入自动购买。",
            "Target tier: off / + / ++. Configuration only; automatic purchasing is not connected yet.",
        ))
        note.setWordWrap(True)
        layout.addWidget(note)
        self._star_count = BodyLabel()
        layout.addWidget(self._star_count)
        grid = QGridLayout()
        grid.setSpacing(12)
        for index, (key, zh, en) in enumerate(STAR_CARDS):
            card = QFrame()
            card.setObjectName("mirrorTeamCard")
            card.setStyleSheet(_card_style())
            column = QVBoxLayout(card)
            icon = QLabel()
            pixmap = QPixmap(str(self._context.resource_path(f"assets/stars/{index + 1}.png")))
            if not pixmap.isNull():
                icon.setPixmap(pixmap.scaled(56, 56, Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation))
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            column.addWidget(icon)
            title = BodyLabel(self._context.translate(zh, en))
            title.setWordWrap(True)
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            column.addWidget(title)
            row = QHBoxLayout()
            buttons = []
            for level, caption in enumerate((self._context.translate("不选", "Off"), "+", "++")):
                button = PushButton(caption)
                button.setCheckable(True)
                button.setAccessibleName(self._context.translate(zh, en) + " " + caption)
                button.clicked.connect(lambda checked=False, k=key, value=level: self._set_star_level(k, value))
                row.addWidget(button)
                buttons.append(button)
            self._star_buttons[key] = buttons
            column.addLayout(row)
            grid.addWidget(card, index // 3, index % 3)
        layout.addLayout(grid)
        clear = PushButton(self._context.translate("清空星光配置", "Clear starlight configuration"))
        clear.clicked.connect(self._clear_stars)
        layout.addWidget(clear, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)
        scroll.setWidget(body)
        self._refresh_stars()
        return scroll

    def _set_star_level(self, key, level):
        """目标档位互斥；不根据未知费用或前置条件推断购买行为。"""
        self._star_levels[key] = level
        self._refresh_stars()

    def _clear_stars(self):
        """将所有卡片重置为不选。"""
        self._star_levels = _restore_star_levels(None)
        self._refresh_stars()

    def _refresh_stars(self):
        """同步每卡目标档位和已配置数量。"""
        for key, buttons in self._star_buttons.items():
            for level, button in enumerate(buttons):
                button.setChecked(level == self._star_levels[key])
        count = sum(level > 0 for level in self._star_levels.values())
        self._star_count.setText(self._context.translate(f"已配置 {count} / 10 项", f"{count} / 10 configured"))

''' + s[pos:]
s = s.replace('            "mirror_teams": list(self._teams),', '            "mirror_teams": list(self._teams),\n            "star_levels": dict(self._star_levels),')
p.write_text(s, encoding='utf-8')
