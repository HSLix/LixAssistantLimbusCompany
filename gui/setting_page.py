# coding:utf-8
from PyQt5.QtWidgets import QWidget
from qfluentwidgets import (
    ScrollArea, SettingCardGroup, OptionsSettingCard, SwitchSettingCard, PrimaryPushSettingCard, HyperlinkCard,
    ExpandLayout, OptionsConfigItem, OptionsValidator, ConfigSerializer, FluentIcon as FIF
)
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtCore import QUrl,Qt
from enum import Enum
import os

from executor import screen_record_thread
from json_manager import config_manager  
from globals import LOG_DIR, VIDEO_DIR, VERSION
from i18n import _
import shutil
import requests
import zipfile
import io


class SettingPage(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.scrollWidget = QWidget()
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.expandLayout = ExpandLayout(self.scrollWidget)
        self.gui_config = config_manager.get_config("gui")

        # 语言配置项
        class Language(Enum):
            """ Language enumeration """
            CHINESE_SIMPLIFIED = "zh_CN"
            ENGLISH = "en_US"

        class LanguageSerializer(ConfigSerializer):
            """ Language serializer """
            def serialize(self, language):
                return language.value

            def deserialize(self, value: str):
                return Language(value)

        # 语言设置组
        self.languageGroup = SettingCardGroup(_("语言设置"), self.scrollWidget)
        self.languageCard = OptionsSettingCard(
            OptionsConfigItem(
                "gui", "language", Language.CHINESE_SIMPLIFIED,
                OptionsValidator(Language), LanguageSerializer(), restart=True
            ),
            FIF.LANGUAGE,
            _("Language"),
            _("设置你偏好的 UI 语言"),
            texts=[
                '简体中文', 
                'English'
            ],
            parent=self.languageGroup
        )
        
        # 从配置文件中加载上次设置的语言
        current_language = self.gui_config.get("language", Language.CHINESE_SIMPLIFIED.value)
        try:
            current_language = Language(current_language)
        except ValueError:
            # 如果配置文件中的语言值无效，则使用默认值
            current_language = Language.CHINESE_SIMPLIFIED

        # 设置当前语言
        self.languageCard.setValue(current_language)
        self.languageGroup.addSettingCard(self.languageCard)

        # 连接信号，保存语言配置
        self.languageCard.optionChanged.connect(self._save_language_config)

        # 录屏设置组
        self.recordingGroup = SettingCardGroup(_("录屏设置"), self.scrollWidget)
        
        # 录屏开关
        self.recordingCard = SwitchSettingCard(
            FIF.VIDEO,
            _("是否录屏"),
            _("开启或关闭录屏功能"),
            configItem=OptionsConfigItem("gui", "recording", False),
            parent=self.recordingGroup,
        )
        # 从配置加载录屏设置
        self.recordingCard.setChecked(self.gui_config.get("recording", True))
        self.recordingCard.checkedChanged.connect(self._save_recording_config)
        self.recordingCard.checkedChanged.connect(self._on_recording_changed)
        self.recordingGroup.addSettingCard(self.recordingCard)
        
        # 录屏保存数量设置卡
        class VideoRetention(Enum):
            """ Video retention count enumeration """
            TWELVE = 12

        class VideoRetentionSerializer(ConfigSerializer):
            """ Video retention serializer """
            def serialize(self, count):
                return count.value

            def deserialize(self, value: int):
                return VideoRetention(value)

        self.videoRetentionCard = OptionsSettingCard(
            OptionsConfigItem(
                "gui", "video_retention", VideoRetention.TWELVE,
                OptionsValidator(VideoRetention), VideoRetentionSerializer()
            ),
            FIF.SAVE,
            _("录屏保存数量"),
            _("设置最大保存的录屏视频数量"),
            texts=['12'],
            parent=self.recordingGroup
        )
        self.recordingGroup.addSettingCard(self.videoRetentionCard)

        # 录屏文件夹
        self.recordingFolderCard = PrimaryPushSettingCard(
            _("打开录屏文件夹"),
            FIF.FOLDER,
            _("录屏文件夹"),
            _("点击打开录屏文件夹"),
            self.recordingGroup
        )
        self.recordingFolderCard.clicked.connect(lambda: self._open_folder(VIDEO_DIR))
        self.recordingGroup.addSettingCard(self.recordingFolderCard)

        # 日志设置组
        self.logGroup = SettingCardGroup(_("日志设置"), self.scrollWidget)
        
        # 日志保存天数设置卡
        class LogRetention(Enum):
            """ Log retention days enumeration """
            SEVEN = 7

        class LogRetentionSerializer(ConfigSerializer):
            """ Log retention serializer """
            def serialize(self, days):
                return days.value

            def deserialize(self, value: int):
                return LogRetention(value)

        self.logRetentionCard = OptionsSettingCard(
            OptionsConfigItem(
                "gui", "log_retention", LogRetention.SEVEN,
                OptionsValidator(LogRetention), LogRetentionSerializer()
            ),
            FIF.HISTORY,
            _("日志保留天数"),
            _("设置自动保留日志的天数"),
            texts=['7'],
            parent=self.logGroup
        )
        self.logGroup.addSettingCard(self.logRetentionCard)

        # 日志文件夹
        self.logFolderCard = PrimaryPushSettingCard(
            _("打开日志文件夹"),
            FIF.FOLDER,
            _("日志文件夹"),
            _("点击打开日志文件夹"),
            self.logGroup
        )
        self.logFolderCard.clicked.connect(lambda: self._open_folder(LOG_DIR))
        self.logGroup.addSettingCard(self.logFolderCard)

        # 帮助和反馈组
        self.helpFeedbackGroup = SettingCardGroup(_("帮助与反馈"), self.scrollWidget)
        self.helpCard = HyperlinkCard(
            "https://github.com/HSLix/LixAssistantLimbusCompany",
            _("打开帮助页面"),
            FIF.HELP,
            _("帮助"),
            _("发现新功能并学习有关本应用的有用提示"),
            self.helpFeedbackGroup
        )
        self.feedbackCard = HyperlinkCard(
            "https://github.com/HSLix/LixAssistantLimbusCompany/issues",
            _("前往反馈"),
            FIF.FEEDBACK,
            _("提供反馈"),
            _("通过提供反馈帮助改进本应用"),
            self.helpFeedbackGroup
        )
        self.helpFeedbackGroup.addSettingCard(self.helpCard)
        self.helpFeedbackGroup.addSettingCard(self.feedbackCard)

        # 更新组
        self.updateGroup = SettingCardGroup(_("关于"), self.scrollWidget)
        self.updateCard = HyperlinkCard(
            "https://github.com/HSLix/LixAssistantLimbusCompany/releases/latest",
            _("点击前往更新应用"),
            FIF.INFO,
            "LixAssistantLimbusCompany",
            VERSION + "; 陆爻齐-LuYaoQi",
            self.updateGroup
        )

        self.tryHotUpdate = PrimaryPushSettingCard(
            _("尝试拉取更新"),
            FIF.FOLDER,
            _("拉取更新"),
            _("请稍等一段时间，等待从仓库拉取成功后，退出程序后手动把./temp目录下的文件复制到软件根目录"),
            self.logGroup
        )
        self.tryHotUpdate.clicked.connect(lambda: self.download_and_extract_zip())

        self.updateGroup.addSettingCard(self.tryHotUpdate)
        self.updateGroup.addSettingCard(self.updateCard)

        # 初始化布局
        self.expandLayout.setSpacing(28)
        self.expandLayout.setContentsMargins(36, 10, 36, 0)
        self.expandLayout.addWidget(self.languageGroup)
        self.expandLayout.addWidget(self.recordingGroup)
        self.expandLayout.addWidget(self.logGroup)  
        self.expandLayout.addWidget(self.helpFeedbackGroup)
        self.expandLayout.addWidget(self.updateGroup)

    def _open_folder(self, folder_path):
        """
        打开指定文件夹
        """
        # 确保路径存在
        if not os.path.exists(folder_path):
            os.makedirs(folder_path, exist_ok=True)

        # 使用 QDesktopServices 打开文件夹
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(folder_path)):
            self.window().show_message("ERROR", "FileDirNotFound", _("无法打开文件夹：%s") % (folder_path))

    def _save_language_config(self):
        """保存语言配置"""
        value = self.languageCard.configItem.value
        self.gui_config["language"] = value.value
        config_manager.save_config("gui", self.gui_config)
        self.window().show_message("INFO", "语言切换通知", "设置将在重启后生效\nSettings will take effect after restarting the programme")

    def _save_recording_config(self, is_checked):
        self.gui_config["recording"] = is_checked
        config_manager.save_config("gui", self.gui_config)

    def _on_recording_changed(self, is_checked):
        """当录屏设置更改时，保存配置并更新录屏线程状态"""
        self.gui_config["recording"] = is_checked
        config_manager.save_config("gui", self.gui_config)

        # 更新录屏线程状态
        screen_record_thread.set_recording_enabled(is_checked)
    
    # 这里没有做一个异步或是线程什么的，拉的时候会卡一下
    def download_and_extract_zip(self):
        repo_url = "https://github.com/HSLix/LixAssistantLimbusCompany"
        target_dir="temp"
        
        zip_url = repo_url.replace("https://github.com", "https://api.github.com/repos") + "/zipball/main"
        import shutil, stat
        def force_remove_readonly(func, path, _):
            os.chmod(path, stat.S_IWRITE)
            func(path)
        try:
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir, onerror=force_remove_readonly)
            os.makedirs(target_dir, exist_ok=True)
            # 下载
            response = requests.get(zip_url, stream=True)
            response.raise_for_status()  # 检查请求是否成功
            # 解压
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
                zip_ref.extractall(target_dir)
            extracted_dir = os.path.join(target_dir, os.listdir(target_dir)[0])
            for item in os.listdir(extracted_dir):
                shutil.move(os.path.join(extracted_dir, item), target_dir)
            shutil.rmtree(extracted_dir)
            self.clean_temp_directory()
        except Exception as e:
            self.window().show_message("INFO", "出错", _(f"拉取失败{e}"))
            raise
        
    def clean_temp_directory(self, temp_dir='./temp'):
        # 添加要保留的目录
        keep_dirs = ['executor', 'gui', 'i18n','resource']  
        temp_dir = os.path.abspath(temp_dir)

        try:
            if not os.path.isdir(temp_dir):
                self.window().show_message("INFO", "出错", _(f"{temp_dir} 目录不存在"))
                return
            for entry in os.listdir(temp_dir):
                full_path = os.path.join(temp_dir, entry)
                # 保留指定目录和.py文件
                if os.path.isfile(full_path) and entry.endswith('.py'):
                    continue
                if os.path.isdir(full_path) and entry in keep_dirs:
                    continue
                # 其他删除
                if os.path.isdir(full_path):
                    shutil.rmtree(full_path)
                else:
                    os.remove(full_path)
            self.window().show_message("INFO", "成功", _("拉取仓库成功"))
        except Exception as e:
            self.window().show_message("INFO", "出错", _(f"清理过程中出错{e}"))
            
        