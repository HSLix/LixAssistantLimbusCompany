# coding:utf-8
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget, QStackedWidget, QGroupBox, QSizePolicy
from qfluentwidgets import (
    CheckBox, SpinBox, ToolButton, PushButton, StrongBodyLabel, ComboBox, SingleDirectionScrollArea, FluentIcon as FIF
)
from PyQt5.QtCore import Qt
import json
import os
import subprocess


from executor import lalc_cu, screen_record_thread
from json_manager import config_manager  
from i18n import _



class FullAutoPage(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.fullAutoLayout = QHBoxLayout(self)

        # 创建任务设置组
        self.taskGroupBox = QGroupBox()
        self.taskLayout = QVBoxLayout()
        self.taskGroupBox.setLayout(self.taskLayout)

        # 创建配置设置组
        self.configGroupBox = QGroupBox()
        self.configLayout = QVBoxLayout()
        self.configGroupBox.setLayout(self.configLayout)

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
        # 直接使用 configLayout，不创建额外的 widget
        self.configLayout.setSpacing(15)
        
        # 添加基础设置
        self.addConfigSection(_("基础设置"), [
            (_("游戏窗口大小"), ComboBox(), ['1600,900']),
            (_("脑啡肽模组阈值"), ComboBox(), ["80%"])
        ])
        
        # 添加经验本设置
        self.addConfigSection(_("经验本设置"), [
            
        ])

        # 添加纽本设置
        self.addConfigSection(_("纽本设置"), [
            
        ])

        # 添加镜牢设置
        self.addConfigSection(_("镜牢设置"), [
            
        ])
    
    def addConfigSection(self, title, items):
        """添加配置区域"""
        # 创建配置组
        sectionGroup = QGroupBox(title)
        sectionGroup.setStyleSheet("""
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
        
        sectionLayout = QVBoxLayout(sectionGroup)
        sectionLayout.setSpacing(8)
        
        # 配置项
        for item in items:
            if isinstance(item, tuple):
                label, widget, *args = item
                if isinstance(widget, ComboBox) and args:
                    widget.addItems(args[0])
                    widget.setEnabled(False)
                
                itemLayout = QHBoxLayout()
                itemLayout.addWidget(StrongBodyLabel(label))
                itemLayout.addWidget(widget)
                itemLayout.addStretch()
                sectionLayout.addLayout(itemLayout)
            else:
                sectionLayout.addWidget(item)
        
        self.configLayout.addWidget(sectionGroup)



    def initTaskLayout(self):
        # 添加复选框和对应的 SpinBox，去掉设置按钮
        self.checkBox0 = CheckBox(_("Init"), self)
        self.checkBox1 = CheckBox(_("EXP"), self)
        self.spinBox1 = SpinBox(self)
        self.checkBox2 = CheckBox(_("Thread"), self)
        self.spinBox2 = SpinBox(self)
        self.checkBox3 = CheckBox(_("Mirror"), self)
        self.spinBox3 = SpinBox(self)
        self.checkBox4 = CheckBox(_("Reward"), self)
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

        def addHBoxLayout(layout: QVBoxLayout, checkbox, spinbox=None, alignment=Qt.AlignBottom):
            hBoxLayout = QHBoxLayout()
            hBoxLayout.setAlignment(alignment)
            hBoxLayout.addWidget(checkbox)
            if spinbox:
                hBoxLayout.addStretch(1)  # 在 SpinBox 左边添加弹簧
                hBoxLayout.addWidget(spinbox)
            hBoxLayout.addStretch(1)
            layout.addLayout(hBoxLayout)

        # 将复选框和 SpinBox 添加到布局中
        addHBoxLayout(self.taskLayout, self.checkBox0)
        addHBoxLayout(self.taskLayout, self.checkBox1, self.spinBox1)
        addHBoxLayout(self.taskLayout, self.checkBox2, self.spinBox2)
        addHBoxLayout(self.taskLayout, self.checkBox3, self.spinBox3)
        addHBoxLayout(self.taskLayout, self.checkBox4)
        
        # 添加结束动作选择
        endActionLayout = QHBoxLayout()
        endActionLayout.addStretch(1)
        endActionLabel = StrongBodyLabel(_("结束后动作:"))
        self.endActionComboBox = ComboBox()
        self.endActionComboBox.addItems([_("无"), _("关闭 LALC 和 Limbus"), _("关机")])
        self.endActionComboBox.setCurrentText(_("无"))
        
        endActionLayout.addWidget(endActionLabel)
        endActionLayout.addWidget(self.endActionComboBox)
        endActionLayout.addStretch(1)
        self.taskLayout.addLayout(endActionLayout)
        
        # 添加间隔
        self.taskLayout.addSpacing(20)
        
        # 添加开始按钮
        startLayout = QHBoxLayout()
        startLayout.addStretch(1)
        startLayout.addWidget(self.StartButton)
        startLayout.addStretch(1)
        self.taskLayout.addLayout(startLayout)

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
    
    def execute_end_action(self):
        """执行结束后的动作"""
        end_action = self.endActionComboBox.currentText()
        
        if end_action == _("无"):
            return
        elif end_action == _("关闭 LALC 和 Limbus"):
            self.close_lalc_and_limbus()
        elif end_action == _("关机"):
            self.shutdown_computer()
    
    def close_lalc_and_limbus(self):
        """关闭 LALC 和 Limbus 游戏"""
        try:
            # 关闭 LALC 进程
            subprocess.run(['taskkill', '/f', '/im', 'LixAssistantLimbusCompany.exe'], 
                         capture_output=True, check=False)
            
            # 关闭 Limbus Company 进程
            subprocess.run(['taskkill', '/f', '/im', 'LimbusCompany.exe'], 
                         capture_output=True, check=False)
            
            # 关闭 Steam 进程（如果游戏是通过 Steam 启动的）
            subprocess.run(['taskkill', '/f', '/im', 'steam.exe'], 
                         capture_output=True, check=False)
            
            print("已关闭 LALC 和 Limbus Company")
        except Exception as e:
            print(f"关闭进程时出错: {e}")
    
    def shutdown_computer(self):
        """关机"""
        try:
            # 使用 Windows 关机命令，30秒后关机
            subprocess.run(['shutdown', '/s', '/t', '30'], check=True)
            print("系统将在30秒后关机")
        except Exception as e:
            print(f"关机命令执行失败: {e}")

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
            "EXPCheckpoint": self.spinBox1.value(),  # EXP 任务执行次数
            "ThreadEnable": self.checkBox2.isChecked(),
            'ThreadCheckpoint': self.spinBox2.value(),  # Thread 任务执行次数
            "MirrorEnable": self.checkBox3.isChecked(),
            'MirrorCheckpoint': self.spinBox3.value(),  # Mirror 任务执行次数
            'reward': self.checkBox4.isChecked(),  # Reward 类型
            'EndAction': self.endActionComboBox.currentText()  # 结束动作
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
            
            # 加载结束动作设置
            end_action = full_auto_config.get('EndAction', _("无"))
            if end_action in [_("无"), _("关闭 LALC 和 Limbus"), _("关机")]:
                self.endActionComboBox.setCurrentText(end_action)
            else:
                self.endActionComboBox.setCurrentText(_("无"))

            # 根据复选框状态设置 SpinBox 可用性
            self.update_spinbox(self.checkBox1.checkState(), self.spinBox1)
            self.update_spinbox(self.checkBox2.checkState(), self.spinBox2)
            self.update_spinbox(self.checkBox3.checkState(), self.spinBox3)
        except FileNotFoundError:
            raise FileNotFoundError("未找到 config.json 文件")
        except json.JSONDecodeError:
            raise json.JSONDecoder("config.json 文件格式错误")