# coding:utf-8
from PyQt5.QtWidgets import QFrame, QVBoxLayout,QWidget, QGridLayout,QHBoxLayout
from qfluentwidgets import StrongBodyLabel, PushButton, ImageLabel, CheckBox, LargeTitleLabel
import os
import json
from PyQt5.QtCore import Qt


from i18n import _, getLang
from globals import CONFIG_DIR, GUI_DIR




class TeamPreviewWidget(QWidget):
    def __init__(self, team_name, parent=None):
        super().__init__(parent)
        self.team_name = team_name
        self.selected_order = []  # 记录复选框点击顺序
        self.initUI()

    def initUI(self):
        self.layout = QGridLayout(self)
        self.layout.setSpacing(10)
        self.layout.setContentsMargins(10, 10, 10, 10)

        self.characters = [
            "YiSang", "Faust", "DonQuixote", "Ryoshu", "Meursault", "HongLu",
            "Heathcliff", "Ishmael", "Rodion", "Sinclair", "Outis", "Gregor"
        ]

        self.load_teams()
        self.init_preview()
        self.load_saved_order()  # 从 json 文件中读取原先顺序

        # 添加恢复按钮
        self.restore_button = PushButton(_("恢复顺序"))
        self.restore_button.clicked.connect(self.load_saved_order)

        # 添加全部取消按钮
        self.cancel_all_button = PushButton(_("全部取消"))
        self.cancel_all_button.clicked.connect(self.cancel_all_checkboxes)

        # 添加保存按钮
        self.save_button = PushButton(_("保存队伍"))
        self.save_button.clicked.connect(self.save_order)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.restore_button)
        button_layout.addWidget(self.cancel_all_button)
        button_layout.addWidget(self.save_button)
        self.layout.addLayout(button_layout, 2, 0, 1, 6)  # 占据第三行全部六列

    def init_preview(self):
        self.widgets = {}
        team_data = self.teams.get(self.team_name, {})

        for idx, name in enumerate(self.characters):
            row = idx // 6
            col = idx % 6

            widget = self.create_character_widget(name, team_data.get(name, idx + 1))
            self.layout.addWidget(widget, row, col)
            self.widgets[name] = widget

    def load_teams(self):
        """从 team.json 加载队伍配置"""
        try:
            with open(os.path.join(CONFIG_DIR, "team.json"), "r", encoding="utf-8") as f:
                self.teams = json.load(f)
        except Exception as e:
            raise AttributeError(f"无法加载队伍配置：{e}")
            # self.teams = {self.team_name: {}}  # 提供默认空队伍

    def create_character_widget(self, name, order):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignCenter)

        # 图片部分
        img_path = f"{GUI_DIR}/{name}.png"
        img_label = ImageLabel(img_path)
        img_label.setFixedSize(100, 120)
        img_label.setAlignment(Qt.AlignCenter)

        # 名字标签
        name_mapping = {
            "YiSang": "李箱",
            "Faust": "浮士德",
            "DonQuixote": "堂吉诃德",
            "Ryoshu": "良秀",
            "Meursault": "默尔索",
            "HongLu": "鸿路",
            "Heathcliff": "希斯克里夫",
            "Ishmael": "以实玛丽",
            "Rodion": "罗佳",
            "Sinclair": "辛克莱",
            "Outis": "奥提斯",
            "Gregor": "格里高尔"
        }
        display_name = name_mapping[name] if getLang() == "zh_CN" else name
        name_label = StrongBodyLabel(display_name)
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setStyleSheet("font-weight: bold;font-size: 15px")

        # 顺序标签
        order_label = StrongBodyLabel(f"No.??")
        order_label.setAlignment(Qt.AlignCenter)
        order_label.setStyleSheet("color: red; font-weight: bold;font-size: 15px")
        order_label.setObjectName("order_label")

        # 复选框
        checkbox = CheckBox()
        checkbox.clicked.connect(lambda state, n=name: self.handle_checkbox_click(n))
        checkbox.setStyleSheet("QCheckBox::indicator { width: 20px; height: 20px;}")
        # 用于让复选框居中的布局
        checkbox_layout = QHBoxLayout()
        checkbox_layout.addWidget(checkbox)
        checkbox_layout.setAlignment(Qt.AlignHCenter)

        layout.addWidget(img_label)
        layout.addWidget(name_label)
        layout.addWidget(order_label)
        layout.addLayout(checkbox_layout)
        # widget.setFixedWidth(110)
        widget.setFixedSize(120, 240)
        widget.setStyleSheet("QWidget {border: 1px solid #ccc;}")
        return widget

    def handle_checkbox_click(self, character_name):
        """处理复选框点击事件，记录顺序并实时更新顺序标签"""
        checkbox = self.widgets[character_name].findChild(CheckBox)
        if checkbox.isChecked():
            self.selected_order.append(character_name)
        else:
            self.selected_order.remove(character_name)

        # 更新所有选中角色的顺序标签
        for i, name in enumerate(self.selected_order):
            widget = self.widgets[name]
            order_label = widget.findChild(StrongBodyLabel, "order_label")
            order_label.setText(f"No.{i + 1}")

        # 未选中的角色标签设为 No.??
        for name in self.characters:
            if name not in self.selected_order:
                widget = self.widgets[name]
                order_label = widget.findChild(StrongBodyLabel, "order_label")
                order_label.setText("No.??")

    def save_order(self):
        """保存顺序到 team.json"""
        # 在保存前再次加载队伍信息，确保获取到最新的其他字段信息
        self.load_teams()

        order = []
        # 处理已选中的角色
        for i, name in enumerate(self.selected_order):
            order.append((name, i + 1))

        # 处理未选中的角色，按原始顺序
        remaining = [name for name in self.characters if name not in self.selected_order]
        for i, name in enumerate(remaining, start=len(self.selected_order) + 1):
            order.append((name, i))
            # self.selected_order.append(name)
            # 自动勾选未选中的角色
            widget = self.widgets[name]
            checkbox = widget.findChild(CheckBox)
            if checkbox:
                checkbox.setChecked(True)

        # 更新队伍数据，只更新罪人的顺序信息
        team_data = self.teams.get(self.team_name, {})
        for name, new_order in order:
            team_data[name] = new_order

        self.teams[self.team_name] = team_data

        # 保存到文件
        try:
            with open(os.path.join(CONFIG_DIR, "team.json"), "w", encoding="utf-8") as f:
                json.dump(self.teams, f, indent=4, ensure_ascii=False)
            # QMessageBox.information(self, "成功", f"{self.team_name} 顺序已保存！")
            self.window().show_message("SUCCESS", "SaveSuccess", f"{self.team_name} 顺序保存成功！")
            self.update_order_labels()
        except Exception as e:
            self.window().show_message("ERROR", "SaveFailed", f"{self.team_name} 顺序保存失败！")
            # QMessageBox.critical(self, "错误", f"保存失败：{e}")

    def update_order_labels(self):
        """更新顺序标签"""
        self.load_teams()
        team_data = self.teams.get(self.team_name, {})

        for name, widget in self.widgets.items():
            order = team_data.get(name, self.characters.index(name) + 1)
            order_label = widget.findChild(StrongBodyLabel, "order_label")
            if order_label:
                order_label.setText(f"No.{order}")

    def load_saved_order(self):
        """从 json 文件中读取原先顺序"""
        self.load_teams()
        team_data = self.teams.get(self.team_name, {})
        self.selected_order = []
        sorted_members = sorted(
            [(name, order) for name, order in team_data.items() if name in self.characters],
            key=lambda x: x[1]
        )
        for name, _ in sorted_members:
            self.selected_order.append(name)
            checkbox = self.widgets[name].findChild(CheckBox)
            checkbox.setChecked(True)

        # 直接更新顺序标签
        for i, name in enumerate(self.selected_order):
            widget = self.widgets[name]
            order_label = widget.findChild(StrongBodyLabel, "order_label")
            order_label.setText(f"No.{i + 1}")

        # 未选中的角色标签设为 No.??
        for name in self.characters:
            if name not in self.selected_order:
                widget = self.widgets[name]
                order_label = widget.findChild(StrongBodyLabel, "order_label")
                order_label.setText("No.??")

    def cancel_all_checkboxes(self):
        """取消所有复选框的选中状态"""
        self.selected_order = []
        for name in self.characters:
            widget = self.widgets[name]
            checkbox = widget.findChild(CheckBox)
            checkbox.setChecked(False)
            order_label = widget.findChild(StrongBodyLabel, "order_label")
            order_label.setText("No.??")


class TeamEditPage(QFrame):
    def __init__(self, text:str, team_name:str, parent=None):
        super().__init__(parent=parent)
        self.team_name = team_name
        self.vBoxLayout = QVBoxLayout(self)
        self.initUI()
        self.setObjectName(text.replace(' ', '-'))

    def initUI(self):
        """初始化队伍编辑界面"""
        # 添加队伍名称标签
        self.team_name_label = LargeTitleLabel(_("编辑队伍: %s") % (self.team_name))
        self.team_name_label.setAlignment(Qt.AlignCenter)
        self.vBoxLayout.addWidget(self.team_name_label)

        # 添加队伍预览组件
        self.preview_widget = TeamPreviewWidget(self.team_name, self)
        self.vBoxLayout.addWidget(self.preview_widget)