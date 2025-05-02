# coding:utf-8
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget, QGroupBox, QStackedWidget
from qfluentwidgets import (
    CheckBox, ToolButton, PushButton, StrongBodyLabel, SingleDirectionScrollArea, FluentIcon as FIF
)
from PyQt5.QtCore import Qt
import json


from executor import lalc_cu, screen_record_thread
from json_manager import config_manager  
from i18n import _


class SemiAutoPage(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.fullAutoLayout = QHBoxLayout(self)

        # 创建 taskLayout 的 QGroupBox
        self.taskGroupBox = QGroupBox(_("任务设置"))
        self.taskLayout = QVBoxLayout()
        self.taskGroupBox.setLayout(self.taskLayout)

        # 创建 configLayout 的 QGroupBox
        self.configGroupBox = QGroupBox(_("配置设置"))
        self.scrollConfig = SingleDirectionScrollArea(orient=Qt.Vertical)
        self.configLayout = QVBoxLayout()
        self.scrollConfig.setWidgetResizable(True)
        widget = QWidget()
        widget.setLayout(self.configLayout)
        self.scrollConfig.setWidget(widget)

        # 创建一个布局来包含 scrollConfig
        group_box_layout = QVBoxLayout()
        group_box_layout.addWidget(self.scrollConfig)
        self.configGroupBox.setLayout(group_box_layout)

        # 设置 QGroupBox 标题的字号
        self.taskGroupBox.setStyleSheet("QGroupBox { font-size: 20px; }")
        self.configGroupBox.setStyleSheet("QGroupBox { font-size: 20px; }")

        # 将 QGroupBox 添加到主布局中
        self.fullAutoLayout.addWidget(self.taskGroupBox)
        self.fullAutoLayout.addWidget(self.configGroupBox)

        # 设置布局间距
        self.fullAutoLayout.setSpacing(60)

        # 初始化任务布局和配置布局
        self.initTaskLayout()
        self.initConfigLayout()

        # 读取配置文件
        self.load_config()

        self.record_thread = screen_record_thread

    def initConfigLayout(self):
        # 创建一个 QStackedWidget 来管理多个配置页面
        self.config_pages = QStackedWidget()
        self.configLayout.addWidget(self.config_pages)

        # 为每个设置按钮创建对应的配置页面
        pages = [
            self.init_semi_auto_p_battle_config_page(),
            self.init_semi_auto_skip_event_config_page(),
            self.init_semi_auto_next_stage_config_page(),
            self.init_semi_auto_reward_card_config_page(),
            self.init_semi_auto_ego_gift_get_config_page(),
            self.init_semi_auto_enter_mirror_config_page()
        ]
        for page in pages:
            self.config_pages.addWidget(page)

    def init_semi_auto_p_battle_config_page(self):
        page = QWidget()
        page_layout = QVBoxLayout(page)
        self.full_team_to_battle_box = CheckBox(_("Full(12/12) Team to Battle"))
        page_layout.addWidget(self.full_team_to_battle_box)
        # 创建标签
        # label = StrongBodyLabel("Semi Auto Setting 1\nNo Custom Setting for now", page)
        # page_layout.addWidget(label)
        return page

    def init_semi_auto_skip_event_config_page(self):
        page = QWidget()
        page_layout = QVBoxLayout(page)

        # 创建标签
        # label = StrongBodyLabel("Semi Auto Setting 2\n暂无自定义选项\nNo Custom Setting for now", page)
        # page_layout.addWidget(label)
        self.event_select_ego_box = CheckBox(_("Select \"Ego\" Choice"))
        page_layout.addWidget(self.event_select_ego_box)


        return page

    def init_semi_auto_next_stage_config_page(self):
        page = QWidget()
        page_layout = QVBoxLayout(page)

        # 创建标签
        label = StrongBodyLabel("Semi Auto Setting 3\n暂无自定义选项\nNo Custom Setting for now", page)
        page_layout.addWidget(label)
        return page

    def init_semi_auto_reward_card_config_page(self):
        page = QWidget()
        page_layout = QVBoxLayout(page)

        # 创建标签
        label = StrongBodyLabel("Semi Auto Setting 4\n暂无自定义选项\nNo Custom Setting for now", page)
        page_layout.addWidget(label)
        return page

    def init_semi_auto_ego_gift_get_config_page(self):
        page = QWidget()
        page_layout = QVBoxLayout(page)

        # 创建标签
        label = StrongBodyLabel("Semi Auto Setting 5\n暂无自定义选项\nNo Custom Setting for now", page)
        page_layout.addWidget(label)
        return page

    def init_semi_auto_enter_mirror_config_page(self):
        page = QWidget()
        page_layout = QVBoxLayout(page)

        # 创建标签
        label = StrongBodyLabel("Semi Auto Setting 6\n暂无自定义选项\nNo Custom Setting for now", page)
        page_layout.addWidget(label)
        return page

    def initTaskLayout(self):
        # 保持原来的几个box
        self.checkBox1 = CheckBox(_('Auto P Battle'), self)
        self.toolButton1 = ToolButton(FIF.SETTING)
        self.checkBox2 = CheckBox(_('Skip Event'), self)
        self.toolButton2 = ToolButton(FIF.SETTING)
        self.checkBox3 = CheckBox(_('Auto Click Next Stage'), self)
        self.toolButton3 = ToolButton(FIF.SETTING)
        self.checkBox4 = CheckBox(_('Auto Select Reward Card'), self)
        self.toolButton4 = ToolButton(FIF.SETTING)
        self.checkBox5 = CheckBox(_('Auto Skip EgoGiftGet'), self)
        self.toolButton5 = ToolButton(FIF.SETTING)
        self.checkBox6 = CheckBox(_('Auto Enter Mirror(Begin)'), self)
        self.toolButton6 = ToolButton(FIF.SETTING)

        # 创建设置开始按钮
        self.StartButton = PushButton(_("Start"))
        self.StartButton.setToolTip("Ctrl+Enter+S")
        self.StartButton.setFixedSize(200, 50)

        # 创建水平布局并将复选框和按钮添加到其中
        hbox1 = QHBoxLayout()
        hbox1.addWidget(self.checkBox1)
        hbox1.addStretch(1)
        hbox1.addWidget(self.toolButton1)
        self.taskLayout.addLayout(hbox1)

        hbox2 = QHBoxLayout()
        hbox2.addWidget(self.checkBox2)
        hbox2.addStretch(1)
        hbox2.addWidget(self.toolButton2)
        self.taskLayout.addLayout(hbox2)

        hbox3 = QHBoxLayout()
        hbox3.addWidget(self.checkBox3)
        hbox3.addStretch(1)
        hbox3.addWidget(self.toolButton3)
        self.taskLayout.addLayout(hbox3)

        hbox4 = QHBoxLayout()
        hbox4.addWidget(self.checkBox4)
        hbox4.addStretch(1)
        hbox4.addWidget(self.toolButton4)
        self.taskLayout.addLayout(hbox4)

        hbox5 = QHBoxLayout()
        hbox5.addWidget(self.checkBox5)
        hbox5.addStretch(1)
        hbox5.addWidget(self.toolButton5)
        self.taskLayout.addLayout(hbox5)

        hbox6 = QHBoxLayout()
        hbox6.addWidget(self.checkBox6)
        hbox6.addStretch(1)
        hbox6.addWidget(self.toolButton6)
        self.taskLayout.addLayout(hbox6)
        # 添加开始按钮
        hbox_start = QHBoxLayout()
        hbox_start.addStretch(1)
        hbox_start.addWidget(self.StartButton)
        hbox_start.addStretch(1)
        self.taskLayout.addLayout(hbox_start)

        for toolButton in [self.toolButton1, self.toolButton2, self.toolButton3, self.toolButton4, self.toolButton5, self.toolButton6]:
            toolButton.setEnabled(True)
            toolButton.setFixedSize(40, 40)

        # 连接按钮点击信号到切换页面的槽函数
        self.toolButton1.clicked.connect(lambda: self.config_pages.setCurrentIndex(0))
        self.toolButton2.clicked.connect(lambda: self.config_pages.setCurrentIndex(1))
        self.toolButton3.clicked.connect(lambda: self.config_pages.setCurrentIndex(2))
        self.toolButton4.clicked.connect(lambda: self.config_pages.setCurrentIndex(3))
        self.toolButton5.clicked.connect(lambda: self.config_pages.setCurrentIndex(4))
        self.toolButton6.clicked.connect(lambda: self.config_pages.setCurrentIndex(5))

        # 连接开始按钮的点击信号到开始线程的槽函数
        self.StartButton.clicked.connect(self.start_thread)

    def start_thread(self):
        # 获取全局的 ControlUnit 实例
        control_unit = lalc_cu
        if not control_unit.isRunning():
            # 收集并保存参数
            global config_manager
            params = self.collect_cu_params()
            save_params = self.collect_save_params()
            config_manager.save_config('semi_auto', save_params)

            # 传递参数到ControlUnit
            control_unit.set_task_params(params)

            # 设置模式半自动
            control_unit.mode = "SemiAuto"

            # 原有启动逻辑
            control_unit.set_max_stack_size(1)
            control_unit.set_start_task("SemiAutoEntrance")
            control_unit.start()

            # 通知 WorkingPage 启用控制按钮
            window = self.window()
            working_interface = window.workingInterface
            working_interface.enable_control_buttons()

            # 跳转到 WorkingInterface
            window.stackWidget.setCurrentWidget(window.workingInterface)

            window.homeInterface.disableStartButtons()

            if config_manager.get_config("gui").get("recording", True):
                self.record_thread.start()

    def stop_recording(self):
        self.record_thread.stop_recording()
        # if (config_manager.get_config("gui").get("recording", True)):
        #     self.window().show_message("INFO", _("录屏完成"), _("录屏已保存至:%s" % (screen_record_thread.output_path)))


    def collect_save_params(self):
        """
        收集 SemiAutoPage 要保存的配置参数
        """
        return {
            'AutoPBattle': self.checkBox1.isChecked(),  # Auto P Battle
            "SkipEvent": self.checkBox2.isChecked(),  # Skip Event
            'AutoClickNextStage': self.checkBox3.isChecked(),  # Auto Click Next Stage
            'AutoSelectRewardCard': self.checkBox4.isChecked(),  # Auto Select Reward Card
            'AutoSkipEgoGiftGet': self.checkBox5.isChecked(),  # Auto Skip EgoGiftGet
            'AutoEnterMirror': self.checkBox6.isChecked(),
            "SemiAutoFullTeamToBattle":self.full_team_to_battle_box.isChecked(),
            "SemiAutoEventMakeChoiceGetEgo": self.event_select_ego_box.isChecked()
        }

    def collect_cu_params(self):
        """
        收集 SemiAutoPage 要传给控制单元的参数
        """
        return {
            'SemiAutoPEncounter': self.checkBox1.isChecked(),  # Auto P Battle
            "SemiAutoEnterEncounter": self.checkBox1.isChecked(),
            'SemiAutoSkipEvent': self.checkBox2.isChecked(),  # Skip Event
            'SemiAutoReadyFindWay': self.checkBox3.isChecked(),  # Auto Click Next Stage
            'SemiAutoReadySelectRewardCard': self.checkBox4.isChecked(),  # Auto Select Reward Card
            'SemiAutoPassEgoGiftGet': self.checkBox5.isChecked(),  # Auto Skip EgoGiftGet
            'SemiAutoReadyEnterMirror': self.checkBox6.isChecked()  # Auto Enter Mirror
        }

    def load_config(self):
        try:
            semi_auto_config = config_manager.get_config("semi_auto")
            self.checkBox1.setChecked(semi_auto_config.get('AutoPBattle', False))
            self.checkBox2.setChecked(semi_auto_config.get('SkipEvent', False))
            self.checkBox3.setChecked(semi_auto_config.get('AutoClickNextStage', False))
            self.checkBox4.setChecked(semi_auto_config.get('AutoSelectRewardCard', False))
            self.checkBox5.setChecked(semi_auto_config.get('AutoSkipEgoGiftGet', False))
            self.checkBox6.setChecked(semi_auto_config.get('AutoEnterMirror', False))
        except FileNotFoundError:
            raise FileNotFoundError("未找到 config.json 文件")
        except json.JSONDecodeError:
            raise json.JSONDecoder("config.json 文件格式错误")