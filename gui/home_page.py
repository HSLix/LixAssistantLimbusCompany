# coding:utf-8
from PyQt5.QtWidgets import QFrame, QVBoxLayout, QStackedWidget, QLabel
from qfluentwidgets import Pivot
from PyQt5.QtCore import Qt


from .semi_auto_page import SemiAutoPage  
from .full_auto_page import FullAutoPage  
from i18n import _


class HomePage(QFrame):
    def __init__(self, text:str, parent=None):
        super().__init__(parent=parent)
        self.name = "HomePage"
        self.setObjectName(text.replace(' ', '-'))
        self.pivot = Pivot(self)
        self.stackedWidget = QStackedWidget(self)
        self.vBoxLayout = QVBoxLayout(self)

        self.fullAutoInterface = FullAutoPage(self)
        self.semiAutoInterface = SemiAutoPage(self)

        # 添加标签页
        self.addSubInterface(self.fullAutoInterface, 'fullAutoInterface', _('FullAuto'))
        self.addSubInterface(self.semiAutoInterface, 'semiAutoInterface', _('SemiAuto'))

        # 连接信号并初始化当前标签页
        self.stackedWidget.currentChanged.connect(self.onCurrentIndexChanged)
        self.stackedWidget.setCurrentWidget(self.fullAutoInterface)
        self.pivot.setCurrentItem(self.fullAutoInterface.objectName())

        self.vBoxLayout.setContentsMargins(30, 0, 30, 30)
        self.vBoxLayout.addWidget(self.pivot, 0, Qt.AlignHCenter)
        self.vBoxLayout.addWidget(self.stackedWidget)

    def addSubInterface(self, widget: QLabel, objectName: str, text: str):
        widget.setObjectName(objectName)
        self.stackedWidget.addWidget(widget)

        # 使用全局唯一的 objectName 作为路由键
        self.pivot.addItem(
            routeKey=objectName,
            text=text,
            onClick=lambda: self.stackedWidget.setCurrentWidget(widget)
        )

    def onCurrentIndexChanged(self, index):
        widget = self.stackedWidget.widget(index)
        self.pivot.setCurrentItem(widget.objectName())

    def disableStartButtons(self):
        """禁用开始按钮"""
        if self.fullAutoInterface:
            self.fullAutoInterface.StartButton.setEnabled(False)
        if self.semiAutoInterface:
            self.semiAutoInterface.StartButton.setEnabled(False)

    def enableStartButtons(self):
        """启用开始按钮"""
        if self.fullAutoInterface:
            self.fullAutoInterface.StartButton.setEnabled(True)
        if self.semiAutoInterface:
            self.semiAutoInterface.StartButton.setEnabled(True)

    def stopRecording(self):
        """停止录屏"""
        if self.fullAutoInterface:
            self.fullAutoInterface.stop_recording()
        if self.semiAutoInterface:
            self.semiAutoInterface.stop_recording()