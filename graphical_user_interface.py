# coding:utf-8
import sys
import os
from PyQt5.QtCore import Qt,  QUrl, QTimer
from PyQt5.QtCore import Qt,  QUrl, QTimer
from PyQt5.QtGui import QIcon, QDesktopServices
from PyQt5.QtWidgets import (QApplication, QStackedWidget, QHBoxLayout, QVBoxLayout, QDialog, QDialogButtonBox)
from qfluentwidgets import (NavigationInterface, NavigationItemPosition, MessageBox, InfoBar, InfoBarIcon)
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
from requests import get




from globals import LOG_DIR, ignoreScaleAndDpi, GUI_DIR, EVENT_NAME, ZH_SUPPORT_URL, EN_SUPPORT_URL, VERSION, GITHUB_REPOSITORY, DISCORD_LINK, checkWorkDirAllEnglish
from json_manager import config_manager
from gui import TeamManagePage, TeamEditPage, HomePage, WorkingPage, SettingPage
from i18n import _, getLang
from executor import lalc_cu, lalc_logger, screen_record_thread






class Window(FramelessWindow):

    def __init__(self):
        checkWorkDirAllEnglish()
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
        self.team5EditInterface = TeamEditPage("Team5EditInterface", "Team5")

        # initialize layout
        self.initLayout()
        
        # add items to navigation interface
        self.initNavigation()

        # 添加消息条管理
        self.info_bar = None
        
        # 连接信号
        self.connect_signals()

        self.initWindow()

        self.show()
        QTimer.singleShot(100, self.showSupportDialog)
        # self.showSupportDialog()
        self.checkForUpdates()  # 调用版本检测函数
        lalc_logger.clean_old_logs()
        # self.show_announcement_dialog()

    def show_announcement_dialog(self):
        """显示公告窗口"""
        dialog = Dialog(
            title="紧急通告！| Emergency Announcement！",
            content="由于听说月亮计划将在4月3日更新反作弊，暂时不知其是否会波及LALC。\n保险起见，4月3日更新后请勿轻易使用 LALC。\n\nSomebody says Project Moon will update its anti cheating measures on April 3rd, it is currently unknown whether it will affect LALC. \nFor safety reasons, please do not use LALC easily after the April 3rd update.",
            parent=self
        )
        dialog.exec_()

    def checkForUpdates(self):
        """检测当前版本是否是最新版本"""
        def get_latest_release(repo):
            url = f"https://api.github.com/repos/{repo}/releases/latest"
            try:
                response = get(url, timeout=3)
                if response.status_code == 200:
                    release_info = response.json()
                    latest_release = release_info["tag_name"]
                    release_body = release_info.get("body", "")  # 获取 release 公告内容
                    return latest_release, release_body
                else:
                    lalc_logger.log_task("WARNING", "checkForUpdates", "FAILED", str(response))
                    return None, None
            except Exception as e:
                print(f"Failed to fetch release information: {e}")
                lalc_logger.log_task("ERROR", "checkForUpdates", "FAILED", str(e))
                return None, None

        repo = GITHUB_REPOSITORY  # 从 globals 中导入的仓库名称
        latest_release, release_body = get_latest_release(repo)

        if latest_release:
            if latest_release == VERSION:
                # 当前版本是最新版本
                self.show_message(
                    "SUCCESS",
                    _('Update Check Successful'),
                    _('You are using the latest version.\nCurrent version: {0}, GitHub version: {1}').format(VERSION, latest_release)
                )
            elif latest_release > VERSION:
                # 当前版本落后
                message = _(
                    'Your version is outdated. Please update.\n'
                    'Current version: {0}, GitHub version: {1}'
                ).format(VERSION, latest_release, release_body)  # 增加公告内容
                self.show_message("ERROR", _('Update Check Successful'), message)
            else:
                self.show_message(
                    "SUCCESS",
                    _('Update Check Successful'),
                    _('Welcome back! Coder :)\nCurrent version: {0}, GitHub version: {1}').format(VERSION, latest_release)
                )
            lalc_logger.log_task("INFO", "checkForUpdates", "FINISHED", "Current version: {0}, GitHub version: {1}".format(VERSION, latest_release))
        else:
            # 网络检测失败
            self.show_message(
                "ERROR",
                _('Update Check Failed'),
                _('Failed to check for updates. \nPlease check your internet connection.')
            )


    def showSupportDialog(self):
        """显示支持对话框"""
        supportDialog = Dialog(
            title="QAQ",
            content=_(
                "请问可以在 GitHub 上给 LALC 点颗 Star✨吗？\n"
                "这是对陆爻齐莫大的肯定，谢谢啦！\n"
                "PS：如果能打赏一点点就更好了哈哈\n"
                "(不打赏也没关系，但一定要过好自己的生活哦)\n"
                "PPS：陆爻齐马上就关闭这个窗口，请不要讨厌陆爻齐QAQ\n"
                "\n3秒后自动关闭。"
            ),
            parent=self
        )
        supportDialog.titleLabel.setAlignment(Qt.AlignCenter)
        supportDialog.contentLabel.setAlignment(Qt.AlignCenter)

        
        supportDialog.yesButton.setText(_("现在就去"))
        supportDialog.cancelButton.setText(_("下次一定"))

        # 修改为非模态对话框
        supportDialog.setModal(False)
        supportDialog.show()

        # 自动关闭定时器
        self.timer = QTimer(self)
        self.timer.timeout.connect(supportDialog.close)  # 使用close而不是accept
        self.timer.start(3000)

        # 连接按钮信号
        supportDialog.yesButton.clicked.connect(
            lambda: [
                self.timer.stop(),
                supportDialog.close(),
                self.show_message("INFO", "Thanks", _("谢谢 !祝你生活愉快！✨不管你到底有没有给 Star\n谢谢你愿意多了解一点 LALC")),
                QDesktopServices.openUrl(QUrl("https://github.com/HSLix/LixAssistantLimbusCompany"))
            ]
        )
        supportDialog.cancelButton.clicked.connect(
            lambda: [
                self.timer.stop(),
                supportDialog.close(),
                self.show_message("INFO", "", _("也祝你生活愉快！(^_−)☆"))
            ]
        )

    def showMessageBox(self):
        w = MessageBox(
            _('支持作者🥰'),
            _('个人开发不易，如果这个项目帮助到了您，可以考虑请给该项目点个 Star⭐。您的支持就是作者开发和维护项目的动力🚀'),
            self
        )
        w.yesButton.setText(_('来啦老弟'))
        w.cancelButton.setText(_('下次一定'))
        
        # 修改为非模态对话框
        w.setModal(False)
        w.show()

        # 连接按钮信号
        w.yesButton.clicked.connect(
            lambda: [
                w.close(),
                QDesktopServices.openUrl(QUrl("https://github.com/HSLix/LixAssistantLimbusCompany"))
            ]
        )
        w.cancelButton.clicked.connect(w.close)

    # 保存语言配置
    def _save_language_config(self, value):
        self.gui_config["language"] = value
        config_manager.save_config("gui", self.gui_config)


    def connect_signals(self):
        """连接信号到消息显示"""
        self.teamManageInterface.last_enabled_team_disable_attempt.connect(
            lambda: self.show_message(
                "WARNING",
                _("NotRecommandAction"),
                _("You had better keep one team enabled at least.")
            )
        )
        
        
        # 任务完成信号
        lalc_cu.task_finished.connect(
            lambda task_name, count: self.show_message(
                "SUCCESS", 
                _('TaskFinished'), 
                _('{0} have finished {1} time(s)').format(task_name, count)
            )
        )
        lalc_cu.pause_completed.connect(
            self.workingInterface.on_paused
        )
        lalc_cu.stop_completed.connect(
            self.workingInterface.on_stopped
        )

        # 屏幕缩放警告
        # lalc_cu.screen_scale_warning.connect(
        #     lambda: self.show_message(
        #         "WARNING", 
        #         _('ScreenScaleWarning'), 
        #         _('检测到屏幕的缩放不是 150%，可能会导致运行不正常\nDetecting of screen scaling other than 150%\nwhich may result in malfunctioning.')
        #     )
        # )
            
        # 任务停止信号
        lalc_cu.task_stopped.connect(
            self.workingInterface.thread_self_stop
        )

        
        # 任务错误信号
        lalc_cu.task_error.connect(
            lambda msg: self.show_message("ERROR", 'Error', msg)
        )
        lalc_cu.task_error.connect(
            self.workingInterface.thread_self_stop
        )
        lalc_cu.task_warning.connect(
            lambda msg: self.show_message("WARNING", "Warning", msg)
        )

        
            
        # 所有任务完成信号
        lalc_cu.task_completed.connect(
            lambda : self.show_message("SUCCESS", 'FinshAll', _("所有任务顺利执行"))
        )
        # 任务暂停/继续信号
        lalc_cu.task_paused.connect(
            lambda: self.show_message("INFO", 'Paused', _('任务执行已暂停'))
        )
        lalc_cu.task_resumed.connect(
            lambda: self.show_message("INFO", 'Resumed', _('任务执行已继续'))
        )

        # 连接队伍信息更新信号
        lalc_cu.team_info_updated.connect(
            lambda current_team_name, next_team_name: self.workingInterface.update_team_info(current_team_name, next_team_name)
        )
        lalc_cu.team_info_updated.connect(
            lambda current_team_name, next_team_name: lalc_logger.log_task(
                "INFO",
                "UpdateTeamRotate",
                "SUCCESS",
                "Update:CurrentTeam:[{0}]; NextTeam:[{1}]".format(current_team_name, next_team_name)
            )
        )

        screen_record_thread.video_count_warning.connect(
            lambda: self.show_message("WARNING", _("Too Much Video"), _("The amount of Video is about to overcome 11.\nNext time the earlist one would be deleted."))
        )
        screen_record_thread.video_count_warning.connect(
            lambda : lalc_logger.log_task("WARNING", "record_thread_video_count_warning", "COMPLETED", "The amount of Video is about to overcome 12.")
        )
        screen_record_thread.video_count_exceeded.connect(
            lambda : self.show_message("WARNING", _("WhiteNight"), _("Twelfth, why have I not chosen thee? Because there is among you a devil that hath betrayed his master."), default_gif_config=False)
        )
        screen_record_thread.video_count_exceeded.connect(
            lambda : self.workingInterface.gif_player.push_gif_to_queue("white_night")
        )
        screen_record_thread.video_count_exceeded.connect(
            lambda : self.show_message("WARNING", _("Delete Video"), _("The earliest Video has been deleted."), default_gif_config=False)
        )
        screen_record_thread.video_count_exceeded.connect(
            lambda : lalc_logger.log_task("WARNING", "record_thread_video_count_exceeded", "COMPLETED", "The earliest Video has been deleted.")
        )

        global lalc_logger
        lalc_logger.deleteOutdatedLogSignal.connect(
            lambda : self.show_message("WARNING", "lalc_logger", _("Delete outdated log from seven days ago successfully."))
        )

    def show_message(self, msg_type, title, content, default_gif_config = True):
        """
        统一显示消息条
        msg_type:INFO,SUCCESS,WARNING,ERROR
        """
        # 创建新消息条
        self.info_bar = InfoBar(
            icon={
                'INFO': InfoBarIcon.INFORMATION,
                'SUCCESS': InfoBarIcon.SUCCESS,
                'WARNING': InfoBarIcon.WARNING,
                'ERROR': InfoBarIcon.ERROR
            }[msg_type],
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=False if msg_type != "ERROR" else True,
            position=InfoBarPosition.TOP,
            duration=30000 if msg_type == "WARNING" else (5000 if msg_type != "ERROR" else -1),
            parent=self
        )

        # 显示消息条
        self.info_bar.show()

        lalc_logger.log_task("INFO", "show_message", "COMPLETED", "bar [{0}];title [{1}]; show [{2}]".format(msg_type, title, content))
        
        if (not default_gif_config):
            return

        # 根据消息类型触发 GIF 播放
        if msg_type == "SUCCESS":
            self.workingInterface.gif_player.push_gif_to_queue("heart")
        elif msg_type == "ERROR" or msg_type == "WARNING":
            self.workingInterface.gif_player.push_gif_to_queue("black1")

        
    

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
            routeKey='discord',
            icon=FIF.CHAT,
            text=_("Chat"),
            onClick=lambda : QDesktopServices.openUrl(QUrl(DISCORD_LINK)),
            selectable=False,
            tooltip=_("Chat"),
            position=NavigationItemPosition.BOTTOM
        )

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





def my_excepthook(exc_type, exc_value, exc_traceback):
    # 格式化异常信息
    error_msg = ''.join(format_exception(exc_type, exc_value, exc_traceback))
    print(f"全局异常捕获:\n{error_msg}")
    
    # 记录错误日志
    lalc_logger.log_task(
        "ERROR",
        "Graphical User Interface",
        "ERROR",
        f"{error_msg}"
    )
    
    # 判断是否为特定错误
    if exc_type == RuntimeError and "TopInfoBarManager" in error_msg:
        print("忽略特定错误：RuntimeError with TopInfoBarManager")
        sys.exit(1)

    # 弹出错误提示对话框
    msg_box = Dialog(
        "Unexpected Error",
        _("捕获到未知错误，是否打开日志查看？\n%s") % (error_msg)
    )

    if msg_box.exec_():
        log_dir = LOG_DIR  
        if os.path.exists(log_dir):
            os.startfile(log_dir)
        else:
            print(f"Log directory does not exist: {log_dir}")

    # 退出程序
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

   