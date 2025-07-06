# coding:utf-8
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget, QGroupBox, QStackedWidget
from qfluentwidgets import (
    ComboBox, CheckBox, ToolButton, PushButton, StrongBodyLabel, SingleDirectionScrollArea, FluentIcon as FIF
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

        # 创建任务设置组
        self.taskGroupBox = QGroupBox()
        self.taskLayout = QVBoxLayout()
        self.taskGroupBox.setLayout(self.taskLayout)

        # 设置 QGroupBox 标题的字号
        self.taskGroupBox.setStyleSheet("QGroupBox { font-size: 20px; }")

        # 将 QGroupBox 添加到主布局中
        self.fullAutoLayout.addWidget(self.taskGroupBox)

        # 设置布局间距
        self.fullAutoLayout.setSpacing(60)

        # 初始化任务布局
        self.initTaskLayout()

        # 读取配置文件
        self.load_config()

        self.record_thread = screen_record_thread


    




    def initTaskLayout(self):
        # 创建水平布局来放置左侧和右侧的内容
        mainLayout = QHBoxLayout()
        
        # 左侧布局（战斗设置和事件设置）
        leftLayout = QVBoxLayout()
        
        # 战斗设置组
        battleGroup = QGroupBox(_("战斗设置"))
        battleLayout = QVBoxLayout()
        battleGroup.setLayout(battleLayout)
        battleGroup.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 5px 0 5px;
            }
        """)
        
        self.checkBox1 = CheckBox(_('Auto P Battle'), self)
        
        battleLayout.addWidget(self.checkBox1)
        leftLayout.addWidget(battleGroup)
        
        # 事件设置组
        eventGroup = QGroupBox(_("事件设置"))
        eventLayout = QVBoxLayout()
        eventGroup.setLayout(eventLayout)
        eventGroup.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 5px 0 5px;
            }
        """)
        
        self.checkBox2 = CheckBox(_('Skip Event'), self)
        self.event_select_ego_box = CheckBox(_("Select \"Ego\" Choice"))
        
        
        eventLayout.addWidget(self.checkBox2)
        eventLayout.addWidget(self.event_select_ego_box)
        leftLayout.addWidget(eventGroup)
        
        # 右侧布局（镜牢设置）
        rightLayout = QVBoxLayout()
        
        # 镜牢设置组
        mirrorGroup = QGroupBox(_("镜牢设置"))
        mirrorLayout = QVBoxLayout()
        mirrorGroup.setLayout(mirrorLayout)
        mirrorGroup.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 5px 0 5px;
            }
        """)
        
        self.full_team_to_battle_box = CheckBox(_("Full(12/12) Team to Battle"))
        self.checkBox3 = CheckBox(_('Auto Click Next Stage'), self)
        self.checkBox4 = CheckBox(_('Auto Select Reward Card'), self)
        self.checkBox5 = CheckBox(_('Auto Skip EgoGiftGet'), self)
        self.checkBox6 = CheckBox(_('Auto Enter Mirror(Begin)'), self)
        
        mirrorLayout.addWidget(self.full_team_to_battle_box)
        mirrorLayout.addWidget(self.checkBox3)
        mirrorLayout.addWidget(self.checkBox4)
        mirrorLayout.addWidget(self.checkBox5)
        mirrorLayout.addWidget(self.checkBox6)
        
        rightLayout.addWidget(mirrorGroup)
        
        # 将左侧和右侧布局添加到主布局
        mainLayout.addLayout(leftLayout)
        mainLayout.addLayout(rightLayout)
        
        # 创建开始按钮
        self.StartButton = PushButton(_("Start"))
        self.StartButton.setToolTip("Ctrl+Enter+S")
        self.StartButton.setFixedSize(200, 50)
        
        # 添加开始按钮到底部
        buttonLayout = QHBoxLayout()
        buttonLayout.addStretch(1)
        buttonLayout.addWidget(self.StartButton)
        buttonLayout.addStretch(1)
        
        # 将所有布局添加到任务布局
        self.taskLayout.addLayout(mainLayout)
        self.taskLayout.addSpacing(20)
        self.taskLayout.addLayout(buttonLayout)

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
            "SemiAutoFullTeamToBattle": self.full_team_to_battle_box.isChecked(),
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
            
            # 加载配置区域的设置
            self.full_team_to_battle_box.setChecked(semi_auto_config.get('SemiAutoFullTeamToBattle', False))
            self.event_select_ego_box.setChecked(semi_auto_config.get('SemiAutoEventMakeChoiceGetEgo', False))
        except FileNotFoundError:
            raise FileNotFoundError("未找到 config.json 文件")
        except json.JSONDecodeError:
            raise json.JSONDecoder("config.json 文件格式错误")