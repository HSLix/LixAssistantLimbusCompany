"""纯设置示例页：不注册循环任务，配置同样传入 Plan。"""

from PySide6.QtWidgets import QWidget, QVBoxLayout
from qfluentwidgets import BodyLabel as QLabel, LineEdit

PAGE_ID = "sample.general"
PAGE_NAME = "通用前缀示例"


class GeneralPage(QWidget):
    """独立配置前缀，用于证明纯设置页不需要任务注册。"""

    def __init__(self, context):
        super().__init__()
        self.context = context
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("消息前缀"))
        self.prefix = LineEdit()
        self.prefix.setText(context.load({"prefix": "LALC: "})["prefix"])
        layout.addWidget(self.prefix)
        layout.addStretch()

    def submit(self):
        return {"prefix": self.prefix.text()}


def create_page(context):
    return GeneralPage(context)
