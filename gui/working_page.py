# coding:utf-8
from PyQt5.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout
from qfluentwidgets import PushButton, LargeTitleLabel
import os
from PyQt5.QtCore import Qt

from .gif_player import GifPlayer  
from executor import lalc_cu
from globals import LOG_DIR
from i18n import _


class WorkingPage(QFrame):
    def __init__(self, text:str, parent=None):
        super().__init__(parent=parent)
        self.setObjectName(text.replace(' ', '-'))
        self.initUI()
        self.pending_pause = False  
        self.pending_stop = False
        self.is_pausing = False

    def initUI(self):
        # 添加暂停和停止按钮
        self.PauseButton = PushButton(_("Pause"))
        self.PauseButton.setFixedSize(160, 40)
        self.StopButton = PushButton(_("Stop"))
        self.StopButton.setFixedSize(160, 40)
        self.OpenLogButton = PushButton(_("Open Log Folder"))
        self.OpenLogButton.setFixedSize(160, 40)

        # 设置快捷键提示
        self.PauseButton.setToolTip("Ctrl+P")
        self.StopButton.setToolTip("Ctrl+Q")

        # 初始禁用按钮
        self.PauseButton.setEnabled(False)
        self.StopButton.setEnabled(False)

        # 添加显示当前队伍和下一个队伍的标签
        self.current_team_label = LargeTitleLabel(_("Current Team:"))
        self.current_team_name_label = LargeTitleLabel("-")
        self.interrupt_label = LargeTitleLabel("; ")
        self.next_team_label = LargeTitleLabel(_("Next Team:"))
        self.next_team_name_label = LargeTitleLabel("-")

        # 创建一个水平布局来放置这四个标签
        team_info_layout = QHBoxLayout()
        team_info_layout.addWidget(self.current_team_label)
        team_info_layout.addWidget(self.current_team_name_label)
        team_info_layout.addWidget(self.interrupt_label)
        team_info_layout.addWidget(self.next_team_label)
        team_info_layout.addWidget(self.next_team_name_label)
        team_info_layout.setAlignment(Qt.AlignCenter)

        # 添加 GIF 播放器
        self.gif_player = GifPlayer(self)
        self.gif_player.set_play_area(0, 0, 640, 400)  # 设置播放区域
        self.gif_player.set_scale(640, 400)  # 设置缩放大小

        # 创建一个布局来让 GIF 居中
        gif_layout = QVBoxLayout()
        gif_layout.addWidget(self.gif_player, alignment=Qt.AlignCenter)

        # 创建控制按钮布局
        control_layout = QHBoxLayout()
        control_layout.setAlignment(Qt.AlignCenter)
        control_layout.addWidget(self.PauseButton)
        control_layout.addWidget(self.StopButton)
        control_layout.addWidget(self.OpenLogButton)

        # 主布局
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.addLayout(team_info_layout)  # 添加队伍信息布局
        self.vBoxLayout.addLayout(gif_layout)  # 添加 GIF 播放器布局
        self.vBoxLayout.addLayout(control_layout)  # 添加控制按钮布局

        # 连接按钮信号
        self.PauseButton.clicked.connect(self.pause_thread)
        self.StopButton.clicked.connect(self.stop_thread)
        self.OpenLogButton.clicked.connect(self.open_log_folder)

    def update_team_info(self, current_team_name, next_team_name):
        """更新当前队伍和下一个队伍的信息"""
        if current_team_name:
            self.current_team_name_label.setText(current_team_name)
        else:
            self.current_team_name_label.setText("-")

        if next_team_name:
            self.next_team_name_label.setText(next_team_name)
        else:
            self.next_team_name_label.setText("-")

    def enable_control_buttons(self):
        """启用控制按钮"""
        self.PauseButton.setEnabled(True)
        self.StopButton.setEnabled(True)

    def pause_thread(self):
        """暂停线程（新增中间状态处理）"""
        if self.pending_pause:  # 防止重复点击
            return
        control_unit = lalc_cu
        if self.is_pausing:
            control_unit.task_resumed.emit()
            self.resume_thread()
            return
        if control_unit.isRunning():
            # 1. 进入中间状态
            self.is_pausing = True
            self.pending_pause = True
            self.PauseButton.setEnabled(False)
            self.StopButton.setEnabled(False)
            self.window().show_message("INFO", "Pausing", _("正在暂停任务"))
            
            # 2. 触发暂停操作
            control_unit.pause_requested.emit()  # 新增信号

    def resume_thread(self):
        """恢复线程"""
        control_unit = lalc_cu
        if control_unit.isRunning():
            control_unit.resume()
        # 直接更新状态（恢复操作是即时的）
        self.PauseButton.setText(_("Pause"))
        self.enable_control_buttons()
        self.is_pausing = False
        self.pending_pause = False

    def stop_thread(self):
        """停止线程（新增中间状态处理）"""
        if self.pending_stop:  # 防止重复点击
            return
        self.is_pausing = False
        # 1. 进入中间状态
        self.pending_stop = True
        self.StopButton.setEnabled(False)
        self.PauseButton.setEnabled(False)
        self.window().show_message("INFO", "Stopping", _("正在停止任务"))
        
        # 2. 触发停止操作
        lalc_cu.stop_requested.emit()  # 新增信号

    def on_paused(self):
        """暂停完成回调"""
        self.pending_pause = False
        self.PauseButton.setText(_("Resume"))
        self.PauseButton.setEnabled(True)
        self.StopButton.setEnabled(True)
        self.window().show_message("INFO", "Paused", _("任务已暂停"))

    def on_stopped(self):
        """停止完成回调"""
        self.pending_stop = False
        self.PauseButton.setText(_("Pause"))
        self.window().show_message("INFO", "Stoped", _("任务已停止"))
        # 恢复开始按钮
        self.window().homeInterface.enableStartButtons()
        self.window().homeInterface.stopRecording()
    
    def thread_self_stop(self):
        """线程自己停止后处理"""
        self.PauseButton.setEnabled(False)
        self.StopButton.setEnabled(False)
        homepage = self.window().homeInterface
        homepage.enableStartButtons()
        homepage.stopRecording()

    def open_log_folder(self):
        """打开日志文件夹"""
        log_dir = LOG_DIR  # 替换为你的日志文件夹路径
        if os.path.exists(log_dir):
            if os.name == 'nt':  # Windows
                os.startfile(log_dir)
            elif os.name == 'posix':  # macOS and Linux
                os.system(f'open "{log_dir}"' if sys.platform == 'darwin' else f'xdg-open "{log_dir}"')
        else:
            print(f"Log directory does not exist: {log_dir}")