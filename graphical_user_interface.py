# coding:utf-8
import sys
import os
from PyQt5.QtCore import Qt,  QUrl, QTimer
from PyQt5.QtGui import QIcon, QDesktopServices
from PyQt5.QtWidgets import (QApplication, QStackedWidget, QHBoxLayout, QVBoxLayout, QDialog, QDialogButtonBox)
from qfluentwidgets import (NavigationInterface, NavigationItemPosition, MessageBox, InfoBar, InfoBarIcon,
                            InfoBarPosition, isDarkTheme, setTheme, Theme, NavigationAvatarWidget, Dialog, BodyLabel)
from qfluentwidgets import FluentIcon as FIF
from qframelesswindow import FramelessWindow, StandardTitleBar
from pynput.keyboard import GlobalHotKeys
from traceback import format_exception
from os.path import join
from ctypes import windll
from win32api import GetLastError
from winerror import ERROR_ALREADY_EXISTS
from win32event import CreateEvent
from requests import get


from globals import LOG_DIR, ignoreScaleAndDpi, GUI_DIR, EVENT_NAME, ZH_SUPPORT_URL, EN_SUPPORT_URL, VERSION, GITHUB_REPOSITORY
from config_manager import config_manager
from gui import TeamManagePage, TeamEditPage, HomePage, WorkingPage, SettingPage
from i18n import _, getLang
from executor import ControlUnit, lalc_logger





class Window(FramelessWindow):

    def __init__(self):
        super().__init__()
        self.setTitleBar(StandardTitleBar(self))
        self.setWindowTitle("LixAssistantLimbusCompany")
        self.setWindowIcon(QIcon(join(GUI_DIR, "MagicGirl.png")))
        setTheme(Theme.LIGHT)
        
        # self.splashScreen = SplashScreen(self.windowIcon(), self)
        # self.splashScreen.setIconSize(QSize(102, 102))
        # self.resize(900, 700)

        # self.show()


        self.hBoxLayout = QHBoxLayout(self)
        self.navigationInterface = NavigationInterface(self, showMenuButton=True)
        self.stackWidget = QStackedWidget(self)

        # create sub interface
        self.homeInterface = HomePage("HomePage")
        self.workingInterface = WorkingPage("WorkingPage")
        self.settingInterface = SettingPage()
        self.teamManageInterface = TeamManagePage("TeamManagePage")
        self.team1EditInterface = TeamEditPage("Team1EditInterface", "Team1")
        self.team2EditInterface = TeamEditPage("Team2EditInterface", "Team2")
        self.team3EditInterface = TeamEditPage("Team3EditInterface", "Team3")
        self.team4EditInterface = TeamEditPage("Team4EditInterface", "Team4")
        self.team5EditInterface = TeamEditPage("Team5EditInterface", "Team5")

        # initialize layout
        self.initLayout()

        # add items to navigation interface
        self.initNavigation()

        # 添加消息条管理
        self.info_bar = None

        
        # 连接信号
        self.connect_signals()

        # 其余窗口初始化事项
        self.initWindow()
        
        self.showSupportDialog()

        # self.splashScreen.finish()

        self.show()

        self.check_for_updates()  # 调用版本检测函数

    def check_for_updates(self):
        """检测当前版本是否是最新版本"""
        def get_latest_release(repo):
            url = f"https://api.github.com/repos/{repo}/releases/latest"
            try:
                response = get(url)
                if response.status_code == 200:
                    release_info = response.json()
                    latest_release = release_info["tag_name"]
                    return latest_release
                else:
                    return None
            except Exception as e:
                print(f"Failed to fetch release information: {e}")
                return None

        repo = GITHUB_REPOSITORY  # 从 globals 中导入的仓库名称
        latest_release = get_latest_release(repo)

        if latest_release:
            if latest_release == VERSION:
                # 当前版本是最新版本
                self.show_message(
                    'success',
                    _('Update Check Successful'),
                    _('You are using the latest version.\nCurrent version: {0}, GitHub version: {1}').format(VERSION, latest_release)
                )
            else:
                # 当前版本落后
                self.show_message(
                    'error',
                    _('Update Check Successful'),
                    _('Your version is outdated. Please update.\nCurrent version: {0}, GitHub version: {1}').format(VERSION, latest_release)
                )
        else:
            # 网络检测失败
            self.show_message(
                'error',
                _('Update Check Failed'),
                _('Failed to check for updates. \nPlease check your internet connection.')
            )


    def showSupportDialog(self):
        """显示支持对话框"""
        self.supportDialog = QDialog(self)
        # 去除QDialog右上角的问号
        self.supportDialog.setWindowFlags(self.supportDialog.windowFlags() & ~Qt.WindowContextHelpButtonHint & ~Qt.WindowCloseButtonHint)
        self.supportDialog.setWindowTitle("QAQ")
        self.supportDialog.setMinimumSize(400, 200)
        layout = QVBoxLayout(self.supportDialog)

        # 主文本改为类属性，并美化文字和排版，用_()包裹文字串
        self.main_text = BodyLabel(
            _("请问可以在 GitHub 上给 LALC 点颗 Star✨吗？\n\n") +
            _("这是对陆爻齐莫大的肯定，谢谢啦！\n\n") +
            _("PS：如果能打赏一点点就更好了哈哈\n\n") +
            _("(不打赏也没关系，但一定要过好自己的生活哦)\n\n") +
            _("PPS：陆爻齐马上就关闭这个窗口，请不要讨厌陆爻齐QAQ")
        )
        self.main_text.setWordWrap(True)
        self.main_text.setAlignment(Qt.AlignCenter)

        # 倒计时标签
        self.countdown_label = BodyLabel(_("还有<nobr><b>6</b></nobr>秒。"))
        self.countdown_label.setAlignment(Qt.AlignCenter)
        self.countdown_label.setTextFormat(Qt.RichText)

        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self.supportDialog)
        button_box.button(QDialogButtonBox.Ok).setText(_("现在就去"))
        button_box.button(QDialogButtonBox.Cancel).setText(_("下次一定"))
        
        # 创建一个新的水平布局用于居中按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(button_box)
        button_layout.addStretch(1)

        # 布局
        layout.addWidget(self.main_text)
        layout.addSpacing(10)
        layout.addWidget(self.countdown_label)
        layout.addSpacing(20)
        layout.addLayout(button_layout)

        # 倒计时定时器
        self.timer = QTimer(self.supportDialog)
        self.timer.timeout.connect(self.updateCountdown)
        self.remaining_seconds = 6
        self.timer.start(1000)
        self.updateCountdown()  # 初始显示


        # **新增信号连接**
        button_box.accepted.connect(self.onStarClicked)  # 确认按钮
        button_box.rejected.connect(self.onCancelClicked)  # 取消按钮

        self.supportDialog.exec_()


    def updateCountdown(self):
        """更新倒计时显示"""
        self.remaining_seconds -= 1
        self.countdown_label.setText(_("还有<nobr><b>%d</b></nobr>秒。") % (self.remaining_seconds))
        if self.remaining_seconds <= 0:
            self.timer.stop()
            self.supportDialog.accept()  # 自动关闭


    def onStarClicked(self):
        """处理确认按钮点击"""
        # 修改文本
        self.main_text.setText(_("谢谢 !祝你生活愉快！✨\n\n不管你到底有没有给 Star\n\n谢谢你愿意多了解一点 LALC"))
        self.countdown_label.setText(_("还有<nobr><b>%d</b></nobr>秒。") % (self.remaining_seconds))
        # 延长一点时间
        self.remaining_seconds += 1
        # 打开链接
        QDesktopServices.openUrl(QUrl("https://github.com/HSLix/LixAssistantLimbusCompany"))
        # self.supportDialog.accept()


    def onCancelClicked(self):
        """处理取消按钮点击"""
        # 修改文本
        self.main_text.setText(_("也祝你生活愉快！(^_−)☆"))
        # self.countdown_label.setText("")
        # 停止倒计时
        # self.timer.stop()
        # self.supportDialog.reject()


    # 保存语言配置
    def _save_language_config(self, value):
        self.gui_config["language"] = value
        config_manager.save_config("gui", self.gui_config)


    def connect_signals(self):
        """连接信号到消息显示"""
        control_unit = ControlUnit()
        self.teamManageInterface.last_enabled_team_disable_attempt.connect(
            lambda: self.show_message(
                "warning",
                _("NotRecommandAction"),
                _("You had better keep one team enabled at least.")
            )
        )
        
        
        # 任务完成信号
        control_unit.task_finished.connect(
            lambda task_name, count: self.show_message(
                'success', 
                _('TaskFinished'), 
                _('{0} have finished {1} time(s)').format(task_name, count)
            )
        )
        control_unit.pause_completed.connect(
            self.workingInterface.on_paused
        )
        control_unit.stop_completed.connect(
            self.workingInterface.on_stopped
        )

        # 屏幕缩放警告
        # control_unit.screen_scale_warning.connect(
        #     lambda: self.show_message(
        #         'warning', 
        #         _('ScreenScaleWarning'), 
        #         _('检测到屏幕的缩放不是 150%，可能会导致运行不正常\nDetecting of screen scaling other than 150%\nwhich may result in malfunctioning.')
        #     )
        # )
            
        # 任务停止信号
        control_unit.task_stopped.connect(
            self.workingInterface.thread_self_stop
        )

        
        # 任务错误信号
        control_unit.task_error.connect(
            lambda msg: self.show_message('error', 'Error', msg)
        )
        control_unit.task_error.connect(
            self.workingInterface.thread_self_stop
        )
        control_unit.task_warning.connect(
            lambda msg: self.show_message('warning', "Warning", msg)
        )

        
            
        # 所有任务完成信号
        control_unit.task_completed.connect(
            lambda : self.show_message('success', 'FinshAll', _("所有任务顺利执行"))
        )
        # 任务暂停/继续信号
        control_unit.task_paused.connect(
            lambda: self.show_message('info', 'Paused', _('任务执行已暂停'))
        )
        control_unit.task_resumed.connect(
            lambda: self.show_message('info', 'Resumed', _('任务执行已继续'))
        )

        # 连接队伍信息更新信号
        control_unit.team_info_updated.connect(
            lambda current_team_name, next_team_name: self.workingInterface.update_team_info(current_team_name, next_team_name)
        )
        control_unit.team_info_updated.connect(
            lambda current_team_name, next_team_name: lalc_logger.log_task(
                "INFO",
                "UpdateTeamRotate",
                "SUCCESS",
                "Update:CurrentTeam:[{0}]; NextTeam:[{1}]".format(current_team_name, next_team_name)
            )
        )


    def show_message(self, msg_type, title, content):
        """
        统一显示消息条
        msg_type:info,success,warning,error
        """
        # 创建新消息条
        self.info_bar = InfoBar(
            icon={
                'info': InfoBarIcon.INFORMATION,
                'success': InfoBarIcon.SUCCESS,
                'warning': InfoBarIcon.WARNING,
                'error': InfoBarIcon.ERROR
            }[msg_type],
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=False if msg_type != "error" else True,
            position=InfoBarPosition.TOP,
            duration=5000 if msg_type != 'error' else -1,
            parent=self
        )

        # 显示消息条
        self.info_bar.show()


        # 根据消息类型触发 GIF 播放
        if msg_type == "success":
            self.workingInterface.gif_player.push_gif_to_queue("heart")
        elif msg_type == "error" or msg_type == "warning":
            self.workingInterface.gif_player.push_gif_to_queue("black1")

        lalc_logger.log_task("INFO", "show_message", "COMPLETED", "bar [{0}];title [{1}]; show [{2}]".format(msg_type, title, content))


    

    def initLayout(self):
        self.hBoxLayout.setSpacing(0)
        self.hBoxLayout.setContentsMargins(0, self.titleBar.height(), 0, 0)
        self.hBoxLayout.addWidget(self.navigationInterface)
        self.hBoxLayout.addWidget(self.stackWidget)
        self.hBoxLayout.setStretchFactor(self.stackWidget, 1)

    def initNavigation(self):
        # enable acrylic effect
        # self.navigationInterface.setAcrylicEnabled(True)

        self.addSubInterface(self.homeInterface, FIF.HOME, _('Home'))
        self.addSubInterface(self.workingInterface, FIF.PLAY, _('Working'))

        self.navigationInterface.addSeparator()

        self.addSubInterface(self.teamManageInterface, FIF.BUS, _('Teams'), NavigationItemPosition.SCROLL)
        self.addSubInterface(self.team1EditInterface, FIF.BUS, _('Team1'), parent=self.teamManageInterface)
        self.addSubInterface(self.team2EditInterface, FIF.BUS, _('Team2'), parent=self.teamManageInterface)
        self.addSubInterface(self.team3EditInterface, FIF.BUS, _('Team3'), parent=self.teamManageInterface)
        self.addSubInterface(self.team4EditInterface, FIF.BUS, _('Team4'), parent=self.teamManageInterface)
        self.addSubInterface(self.team5EditInterface, FIF.BUS, _('Team5'), parent=self.teamManageInterface)


        self.navigationInterface.addItem(
            routeKey='price',
            icon=FIF.CAFE,
            text=_("Support"),
            onClick=self.onSupport,
            selectable=False,
            tooltip=_("Support"),
            position=NavigationItemPosition.BOTTOM
        )


        # add custom widget to bottom
        self.navigationInterface.addWidget(
            routeKey='avatar',
            widget=NavigationAvatarWidget('陆爻齐-LuYaoQi', 'resource/gui/MagicGirl.png'),
            onClick=self.showMessageBox,
            position=NavigationItemPosition.BOTTOM,
        )

        self.addSubInterface(self.settingInterface, FIF.SETTING, _('Settings'), NavigationItemPosition.BOTTOM)


        self.stackWidget.currentChanged.connect(self.onCurrentInterfaceChanged)
        self.stackWidget.setCurrentIndex(0) # 默认打开第一个

        # always expand
        # self.navigationInterface.setCollapsible(False)

    def onSupport(self):
        language = getLang()
        if language == "zh_CN":
            QDesktopServices.openUrl(QUrl(ZH_SUPPORT_URL))
        else:
            QDesktopServices.openUrl(QUrl(EN_SUPPORT_URL))

    def initWindow(self):
        # self.resize(900, 700)
        # self.setWindowIcon(QIcon('resource/gui/MagicGirl.png'))
        # self.setWindowTitle('LixAssistantLimbusCompany')
        self.titleBar.setAttribute(Qt.WA_StyledBackground)

        desktop = QApplication.desktop().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w//2 - self.width()//2, h//2 - self.height()//2)

        # NOTE: set the minimum window width that allows the navigation panel to be expanded
        # self.navigationInterface.setMinimumExpandWidth(900)
        # self.navigationInterface.expand(useAni=False)

        # 设置快捷键
        self.setup_shortcuts()

        self.setQss()

    def setup_shortcuts(self):
        """设置快捷键"""
        hotkey_listener = GlobalHotKeys({
            '<ctrl>+<enter>+f': self.homeInterface.fullAutoInterface.StartButton.click,
            '<ctrl>+<enter>+s': self.homeInterface.semiAutoInterface.StartButton.click,
            '<ctrl>+q': self.workingInterface.StopButton.click,
            '<ctrl>+p': self.workingInterface.PauseButton.click
        })
        hotkey_listener.start()


    def addSubInterface(self, interface, icon, text: str, position=NavigationItemPosition.TOP, parent=None):
        """ add sub interface """
        self.stackWidget.addWidget(interface)
        self.navigationInterface.addItem(
            routeKey=interface.objectName(),
            icon=icon,
            text=text,
            onClick=lambda: self.switchTo(interface),
            position=position,
            tooltip=text,
            parentRouteKey=parent.objectName() if parent else None
        )

    def setQss(self):
        color = 'dark' if isDarkTheme() else 'light'
        with open(f'resource/{color}/demo.qss', encoding='utf-8') as f:
            self.setStyleSheet(f.read())

    def switchTo(self, widget):
        self.stackWidget.setCurrentWidget(widget)

    def onCurrentInterfaceChanged(self, index):
        widget = self.stackWidget.widget(index)
        self.navigationInterface.setCurrentItem(widget.objectName())

        #!IMPORTANT: This line of code needs to be uncommented if the return button is enabled
        # qrouter.push(self.stackWidget, widget.objectName())

    def showMessageBox(self):
        w = MessageBox(
            _('支持作者🥰'),
            _('个人开发不易，如果这个项目帮助到了您，可以考虑请给该项目点个 Star⭐。您的支持就是作者开发和维护项目的动力🚀'),
            self
        )
        w.yesButton.setText(_('来啦老弟'))
        w.cancelButton.setText(_('下次一定'))

        if w.exec():
            QDesktopServices.openUrl(QUrl("https://github.com/HSLix/LixAssistantLimbusCompany"))



def my_excepthook(exc_type, exc_value, exc_traceback):
    error_msg = ''.join(format_exception(exc_type, exc_value, exc_traceback))
    print(f"全局异常捕获:\n{error_msg}")
    lalc_logger.log_task(
            "ERROR",
            "Graphical User Interface",
            "UNEXPECTED ERROR",
            f"{error_msg}"
        )
    print(exc_type)
    if exc_type == RuntimeError and "TopInfoBarManager" in error_msg:
        # 忽略特定错误
        pass

    msg_box = Dialog("Unexpected Error", _("捕获到未知，是否打开日志查看？\n%s") % (error_msg))

    if msg_box.exec_():
        log_dir = LOG_DIR  
        if os.path.exists(log_dir):
            if os.name == 'nt':  # Windows
                os.startfile(log_dir)
            elif os.name == 'posix':  # macOS and Linux
                os.system(f'open "{log_dir}"' if sys.platform == 'darwin' else f'xdg-open "{log_dir}"')
        else:
            print(f"Log directory does not exist: {log_dir}")

    sys.exit(1)

def shutdown_splash():
    try:
        from contextlib import suppress
        with suppress(ModuleNotFoundError):
            import pyi_splash
            pyi_splash.close()
    except ImportError:
        pass




def main(*args, **kwargs):
    shutdown_splash()
    event = CreateEvent(None, 0, 0, EVENT_NAME)

    
    if GetLastError() == ERROR_ALREADY_EXISTS:
        lalc_logger.log_task(
            "WARNING",
            "Graphical User Interface",
            "Over Open LALC",
            "Program is Running!"
        )
        print("程序已经在运行中！")
        # shutdown_splash()
        sys.exit(1)
        
    if not windll.shell32.IsUserAnAdmin():
        windll.shell32.ShellExecuteW(None,"runas", sys.executable, __file__, None, 1)
        # shutdown_splash()
        sys.exit(0)

    lalc_logger.log_task(
        "INFO",
        "MAIN",
        "COMPLETED",
        "VERSION:{0}".format(VERSION)
    )

    # 获取项目根目录
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.append(project_root)
        
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    ignoreScaleAndDpi()
    app = QApplication(sys.argv)
    sys.excepthook = my_excepthook
    # shutdown_splash()
    w = Window()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()

   