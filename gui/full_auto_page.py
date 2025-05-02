# coding:utf-8
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget, QStackedWidget, QGroupBox, QSizePolicy
from qfluentwidgets import (
    CheckBox, SpinBox, ToolButton, PushButton, StrongBodyLabel, ComboBox, SingleDirectionScrollArea, FluentIcon as FIF
)
from PyQt5.QtCore import Qt
import json


from executor import lalc_cu, screen_record_thread
from json_manager import config_manager  
from i18n import _



class FullAutoPage(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.fullAutoLayout = QHBoxLayout(self)

        # 创建任务设置组
        self.taskGroupBox = QGroupBox(_("任务设置"))
        self.taskLayout = QVBoxLayout()
        self.taskGroupBox.setLayout(self.taskLayout)

        # 创建配置设置组
        self.configGroupBox = QGroupBox(_("配置设置"))
        self.scrollConfig = SingleDirectionScrollArea(orient=Qt.Vertical)
        self.configLayout = QVBoxLayout()
        self.scrollConfig.setWidgetResizable(True)
        widget = QWidget()
        widget.setLayout(self.configLayout)
        self.scrollConfig.setWidget(widget)

        # 将配置设置组添加到布局
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
            self.init_init_config_page(),
            self.init_exp_config_page(),
            self.init_thread_config_page(),
            self.init_mirror_config_page(),
            self.init_reward_config_page()
        ]
        for page in pages:
            self.config_pages.addWidget(page)

    def init_init_config_page(self):
        page = QWidget()
        page_layout = QVBoxLayout(page)

        # 创建标签
        game_window_size_label = StrongBodyLabel(_("游戏窗口大小"), page)
        game_window_size = ComboBox()
        game_window_size.addItems(['1600,900'])
        game_window_size.setEnabled(False)

        # 创建水平布局来放置标签和多选框
        h_layout1 = QHBoxLayout()
        h_layout1.addWidget(game_window_size_label)
        h_layout1.addWidget(game_window_size)

        page_layout.addLayout(h_layout1)

        # 创建标签
        assemble_enkephalin_label = StrongBodyLabel(_("AssembleEnkephalinModules"), page)
        assemble_enkephalin = ComboBox()
        assemble_enkephalin.addItems(["80%"])
        assemble_enkephalin.setEnabled(False)

        # 创建水平布局来放置标签和多选框
        h_layout2 = QHBoxLayout()
        h_layout2.addWidget(assemble_enkephalin_label)
        h_layout2.addWidget(assemble_enkephalin)

        page_layout.addLayout(h_layout2)
        
        return page

    def init_exp_config_page(self):
        page = QWidget()
        page_layout = QVBoxLayout(page)
        label = StrongBodyLabel("EXP Setting\n暂无自定义选项\nNo Custom Setting for now", page)
        page_layout.addWidget(label)
        return page

    def init_thread_config_page(self):
        page = QWidget()
        page_layout = QVBoxLayout(page)
        label = StrongBodyLabel("Thread Setting\n暂无自定义选项\nNo Custom Setting for now", page)
        page_layout.addWidget(label)
        return page

    def init_mirror_config_page(self):
        page = QWidget()
        page_layout = QVBoxLayout(page)
        label = StrongBodyLabel("Mirror Setting\n暂无自定义选项\nNo Custom Setting for now", page)
        page_layout.addWidget(label)
        return page

    def init_reward_config_page(self):
        page = QWidget()
        page_layout = QVBoxLayout(page)
        label = StrongBodyLabel("Reward Setting\n暂无自定义选项\nNo Custom Setting for now", page)
        page_layout.addWidget(label)
        return page

    def initTaskLayout(self):
        # 添加四个复选框和对应的 SpinBox
        self.checkBox0 = CheckBox(_("Init"), self)
        self.toolButton0 = ToolButton(FIF.SETTING)
        self.checkBox1 = CheckBox(_("EXP"), self)
        self.spinBox1 = SpinBox(self)
        self.toolButton1 = ToolButton(FIF.SETTING)
        self.checkBox2 = CheckBox(_("Thread"), self)
        self.spinBox2 = SpinBox(self)
        self.toolButton2 = ToolButton(FIF.SETTING)
        self.checkBox3 = CheckBox(_("Mirror"), self)
        self.spinBox3 = SpinBox(self)
        self.toolButton3 = ToolButton(FIF.SETTING)
        self.checkBox4 = CheckBox(_("Reward"), self)
        self.toolButton4 = ToolButton(FIF.SETTING)
        self.StartButton = PushButton(_("Start"))
        self.StartButton.setToolTip("Ctrl+Enter+F")
        self.StartButton.setFixedSize(200, 50)

        self.checkBox0.setChecked(True)
        self.checkBox0.setEnabled(False)
        self.checkBox4.setEnabled(False)

        # 设置 SpinBox 的范围和默认值
        for spinBox in [self.spinBox1, self.spinBox2, self.spinBox3]:
            spinBox.setRange(1, 99)
            spinBox.setValue(1)
            spinBox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

        for toolButton in [self.toolButton0, self.toolButton1, self.toolButton2, self.toolButton3, self.toolButton4]:
            toolButton.setEnabled(True)
            toolButton.setFixedSize(40, 40)

        def addHBoxLayout(layout: QVBoxLayout, a, b, c, alignment=Qt.AlignBottom):
            hBoxLayout = QHBoxLayout()
            hBoxLayout.setAlignment(alignment)
            hBoxLayout.addWidget(a)
            hBoxLayout.addStretch(1)
            hBoxLayout.addWidget(b)
            hBoxLayout.addStretch(1)
            hBoxLayout.addWidget(c)
            layout.addLayout(hBoxLayout)

        # 将复选框和 SpinBox 添加到布局中
        addHBoxLayout(self.taskLayout, self.checkBox0, QWidget(), self.toolButton0)
        addHBoxLayout(self.taskLayout, self.checkBox1, self.spinBox1, self.toolButton1)
        addHBoxLayout(self.taskLayout, self.checkBox2, self.spinBox2, self.toolButton2)
        addHBoxLayout(self.taskLayout, self.checkBox3, self.spinBox3, self.toolButton3)
        addHBoxLayout(self.taskLayout, self.checkBox4, QWidget(), self.toolButton4)
        addHBoxLayout(self.taskLayout, QWidget(), self.StartButton, QWidget(), Qt.AlignCenter)

        # 连接按钮点击信号到切换页面的槽函数
        self.toolButton0.clicked.connect(lambda: self.config_pages.setCurrentIndex(0))
        self.toolButton1.clicked.connect(lambda: self.config_pages.setCurrentIndex(1))
        self.toolButton2.clicked.connect(lambda: self.config_pages.setCurrentIndex(2))
        self.toolButton3.clicked.connect(lambda: self.config_pages.setCurrentIndex(3))
        self.toolButton4.clicked.connect(lambda: self.config_pages.setCurrentIndex(4))

        self.StartButton.clicked.connect(self.start_thread)

        # 连接复选框的状态改变信号到槽函数
        self.checkBox1.stateChanged.connect(lambda state: self.update_spinbox(state, self.spinBox1))
        self.checkBox2.stateChanged.connect(lambda state: self.update_spinbox(state, self.spinBox2))
        self.checkBox3.stateChanged.connect(lambda state: self.update_spinbox(state, self.spinBox3))

        # 初始化时根据复选框状态设置 SpinBox 可用性
        self.update_spinbox(self.checkBox1.checkState(), self.spinBox1)
        self.update_spinbox(self.checkBox2.checkState(), self.spinBox2)
        self.update_spinbox(self.checkBox3.checkState(), self.spinBox3)

    def update_spinbox(self, state, spinbox):
        if state == 0:  # 未选中
            spinbox.setEnabled(False)
        else:
            spinbox.setEnabled(True)

    def start_thread(self):
        # 收集参数
        params = self.collect_cu_params()
        save_params = self.collect_save_params()
        # 保存参数到配置文件
        global config_manager
        config_manager.save_config('full_auto', save_params)
        # 传递参数到 ControlUnit
        control_unit = lalc_cu
        control_unit.set_task_params(params)
        # 启动任务
        control_unit.set_start_task("FullAutoEntrance")
        control_unit.start()
        # 设置模式为全自动
        control_unit.mode = "FullAuto"
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
        if (config_manager.get_config("gui").get("recording", True)):
            self.window().show_message("INFO", _("录屏完成"), _("录屏已保存至:%s") % (screen_record_thread.output_path))

    def collect_save_params(self):
        """收集 FullAutoPage 要保存的配置参数"""
        return {
            'init': self.checkBox0.isChecked(),  # Init
            'EXPEnable': self.checkBox1.isChecked(),
            "EXP": self.spinBox1.value(),  # EXP 任务执行次数
            "ThreadEnable": self.checkBox2.isChecked(),
            'Thread': self.spinBox2.value(),  # Thread 任务执行次数
            "MirrorEnable": self.checkBox3.isChecked(),
            'Mirror': self.spinBox3.value(),  # Mirror 任务执行次数
            'reward': self.checkBox4.isChecked()  # Reward 类型
        }

    def collect_cu_params(self):
        """收集 FullAutoPage 要交给控制单元的参数"""
        exp_value = self.spinBox1.value() if self.checkBox1.isChecked() else 0
        thread_value = self.spinBox2.value() if self.checkBox2.isChecked() else 0
        mirror_value = self.spinBox3.value() if self.checkBox3.isChecked() else 0

        return {
            "EXP": exp_value,  # EXP 任务执行次数
            'Thread': thread_value,  # Thread 任务执行次数
            'Mirror': mirror_value,  # Mirror 任务执行次数
            'SkipEXPLuxcavationStart': self.checkBox1.isChecked(),
            "SkipThreadLuxcavationStart": self.checkBox2.isChecked(),
            "FullAutoMirrorCircleCenter": self.checkBox3.isChecked(),
        }

    def load_config(self):
        try:
            full_auto_config = config_manager.get_config("full_auto")
            self.checkBox0.setChecked(full_auto_config.get('init', True))
            self.checkBox1.setChecked(full_auto_config.get('EXPEnable', False))
            self.spinBox1.setValue(full_auto_config.get('EXP', 0))
            self.checkBox2.setChecked(full_auto_config.get('ThreadEnable', False))
            self.spinBox2.setValue(full_auto_config.get('Thread', 0))
            self.checkBox3.setChecked(full_auto_config.get('MirrorEnable', False))
            self.spinBox3.setValue(full_auto_config.get('Mirror', 0))
            self.checkBox4.setChecked(full_auto_config.get('reward', False))

            # 根据复选框状态设置 SpinBox 可用性
            self.update_spinbox(self.checkBox1.checkState(), self.spinBox1)
            self.update_spinbox(self.checkBox2.checkState(), self.spinBox2)
            self.update_spinbox(self.checkBox3.checkState(), self.spinBox3)
        except FileNotFoundError:
            raise FileNotFoundError("未找到 config.json 文件")
        except json.JSONDecodeError:
            raise json.JSONDecoder("config.json 文件格式错误")