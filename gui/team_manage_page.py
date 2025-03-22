# coding:utf-8
from PyQt5.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QMessageBox
from qfluentwidgets import SwitchButton, ComboBox, StrongBodyLabel, RadioButton
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
import os
import json

from i18n import _
from globals import CONFIG_DIR


class TeamManagePage(QFrame):
    # 定义一个信号，用于在尝试禁用最后一个启用的队伍时发出通知
    last_enabled_team_disable_attempt = pyqtSignal()

    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        self.vBoxLayout = QVBoxLayout(self)  # 主布局为垂直布局
        self.setObjectName(text.replace(' ', '-'))

        # 定义风格选项的英文和国际化映射
        self.style_options = {
            "Burn": _("Burn"),
            "Bleed": _("Bleed"),
            "Tremor": _("Tremor"),
            "Rupture": _("Rupture"),
            "Sinking": _("Sinking"),
            "Poise": _("Poise"),
            "Charge": _("Charge")
        }
        self.initUI()

    def initUI(self):
        """初始化队伍界面"""
        # 表头布局
        header_layout = QHBoxLayout()
        for text in [_("队伍名"), _("是否启用"), _("队伍流派"), _("首发队伍")]:
            label = StrongBodyLabel(text)
            # label.setFixedHeight(30)
            label.setAlignment(Qt.AlignCenter)
            header_layout.addWidget(label)
        self.vBoxLayout.addLayout(header_layout)

        # 初始化控件
        self.radio_buttons = []
        self.switch_buttons = []
        self.comboboxes = []
        for i in range(1, 6):
            self.add_team_row(f"Team{i}", i)

        # 加载初始状态
        self.load_all_states()

    def add_team_row(self, team_name, row_index):
        row_layout = QHBoxLayout()

        # 队伍名
        team_label = StrongBodyLabel(_(team_name))
        team_label.setAlignment(Qt.AlignCenter)
        row_layout.addWidget(team_label)

        # SwitchButton
        switch = SwitchButton()
        self.switch_buttons.append(switch)
        switch.checkedChanged.connect(
            lambda checked, tn=team_name, idx=row_index - 1:
            self.handle_switch_change(checked, tn, idx)
        )
        row_layout.addWidget(switch, alignment=Qt.AlignCenter)

        # ComboBox
        combo = ComboBox()
        combo.addItems([self.style_options[style] for style in self.style_options])
        combo.currentTextChanged.connect(
            lambda text, tn=team_name: self.save_style(tn, self.get_english_style(text))
        )
        self.comboboxes.append(combo)
        row_layout.addWidget(combo, alignment=Qt.AlignCenter)

        # RadioButton
        radio = RadioButton()
        self.radio_buttons.append(radio)
        radio.toggled.connect(
            lambda checked, tn=team_name: self.update_offset(tn, checked)
        )
        row_layout.addWidget(radio, alignment=Qt.AlignCenter)

        self.vBoxLayout.addLayout(row_layout)

    def handle_switch_change(self, checked, team_name, index):
        """处理启用状态变化"""
        # 保存状态
        self.save_switch_state(team_name, checked)

        # 更新控件状态
        self.comboboxes[index].setEnabled(checked)
        self.radio_buttons[index].setEnabled(checked)

        # 如果当前选中队伍被禁用
        if not checked and self.radio_buttons[index].isChecked():
            self.reset_radio_button()

        # 强制保留最后一个启用队伍
        if not any(switch.isChecked() for switch in self.switch_buttons):
            QTimer.singleShot(200, lambda: self.force_enable_last_team(index, team_name))
        else:
            QTimer.singleShot(0, self.update_offset_after_switch_change)

    def update_offset_after_switch_change(self):
        """在启用状态变化后更新offset"""
        try:
            with open(os.path.join(CONFIG_DIR, "team.json"), "r+") as f:
                teams = json.load(f)
                enabled_teams = [t for t in ["Team1", "Team2", "Team3", "Team4", "Team5"]
                                 if teams[t]["enabled"]]

                # 找出当前被选中的首发队伍
                current_selected_team = None
                for i, radio in enumerate(self.radio_buttons):
                    if radio.isChecked():
                        current_selected_team = f"Team{i + 1}"
                        break

                # 计算当前选中队伍在启用队伍中的排名
                if current_selected_team in enabled_teams:
                    new_offset = enabled_teams.index(current_selected_team)
                    teams["TeamOffset"] = new_offset
                elif enabled_teams:
                    # 如果当前选中队伍未启用，将第一个启用队伍设为首发
                    new_offset = 0
                    teams["TeamOffset"] = new_offset
                    self.radio_buttons[["Team1", "Team2", "Team3", "Team4", "Team5"].index(enabled_teams[new_offset])].setChecked(True)
                else:
                    teams["TeamOffset"] = 0

                f.seek(0)
                json.dump(teams, f, indent=4)
                f.truncate()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"更新offset失败: {str(e)}")

    def force_enable_last_team(self, index, team_name):
        """强制启用最后一个尝试禁用的队伍"""
        self.switch_buttons[index].setChecked(True)
        self.save_switch_state(team_name, True)
        # 发出信号
        self.last_enabled_team_disable_attempt.emit()

    def reset_radio_button(self):
        """重置 RadioButton 到第一个启用的队伍"""
        for i, switch in enumerate(self.switch_buttons):
            if switch.isChecked():
                self.radio_buttons[i].setChecked(True)
                self.update_offset(f"Team{i + 1}", True)
                break

    def update_offset(self, team_name, checked):
        """更新首发队伍offset"""
        if checked:
            try:
                with open(os.path.join(CONFIG_DIR, "team.json"), "r+") as f:
                    teams = json.load(f)
                    enabled_teams = [t for t in ["Team1", "Team2", "Team3", "Team4", "Team5"]
                                     if teams[t]["enabled"]]
                    if team_name in enabled_teams:
                        teams["TeamOffset"] = enabled_teams.index(team_name)
                        f.seek(0)
                        json.dump(teams, f, indent=4)
                        f.truncate()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存offset失败: {str(e)}")

    def load_all_states(self):
        """加载所有状态"""
        try:
            with open(os.path.join(CONFIG_DIR, "team.json"), "r") as f:
                teams = json.load(f)

                # 加载开关状态
                for i, team in enumerate(["Team1", "Team2", "Team3", "Team4", "Team5"]):
                    self.switch_buttons[i].setChecked(teams[team]["enabled"])
                    self.comboboxes[i].setEnabled(teams[team]["enabled"])
                    self.radio_buttons[i].setEnabled(teams[team]["enabled"])
                    self.comboboxes[i].setCurrentText(
                        self.style_options.get(teams[team]["style"], "")
                    )

                # 加载offset
                enabled_teams = [t for t in ["Team1", "Team2", "Team3", "Team4", "Team5"]
                                 if teams[t]["enabled"]]
                if enabled_teams:
                    offset = teams["TeamOffset"]
                    if offset < len(enabled_teams):
                        self.radio_buttons[["Team1", "Team2", "Team3", "Team4", "Team5"].index(
                            enabled_teams[offset]
                        )].setChecked(True)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载配置失败: {str(e)}")

    def load_offset_state(self):
        """加载 TeamOffset 的状态"""
        try:
            with open(os.path.join(CONFIG_DIR, "team.json"), "r", encoding="utf-8") as f:
                teams = json.load(f)
                offset = teams.get("TeamOffset", 0)
                enabled_teams = [i for i, switch in enumerate(self.switch_buttons) if switch.isChecked()]
                if 0 <= offset < len(enabled_teams):
                    index = enabled_teams[offset]
                    self.radio_buttons[index].setChecked(True)
        except Exception as e:
            raise AttributeError(f"无法加载队伍配置：{e}")

    def get_english_style(self, localized_style):
        """根据国际化值获取英文值"""
        for english_style, localized in self.style_options.items():
            if localized == localized_style:
                return english_style
        return ""

    def save_style(self, team_name, style):
        """保存 Style ComboBox 的状态"""
        try:
            with open(os.path.join(CONFIG_DIR, "team.json"), "r", encoding="utf-8") as f:
                teams = json.load(f)

            # 更新 style 状态
            if team_name in teams:
                teams[team_name]["style"] = style

            # 保存到文件
            with open(os.path.join(CONFIG_DIR, "team.json"), "w", encoding="utf-8") as f:
                json.dump(teams, f, indent=4, ensure_ascii=False)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败：{e}")

    def save_switch_state(self, team_name, enabled):
        """保存 SwitchButton 的状态"""
        try:
            with open(os.path.join(CONFIG_DIR, "team.json"), "r", encoding="utf-8") as f:
                teams = json.load(f)

            # 更新 enabled 状态
            if team_name in teams:
                teams[team_name]["enabled"] = enabled

            # 保存到文件
            with open(os.path.join(CONFIG_DIR, "team.json"), "w", encoding="utf-8") as f:
                json.dump(teams, f, indent=4, ensure_ascii=False)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败：{e}")
    