"""不使用语言接口的旧式纯设置页，演示原文回退与配置保存。"""

from PySide6.QtWidgets import QWidget, QVBoxLayout
from qfluentwidgets import BodyLabel, LineEdit

PAGE_ID = "legacy-language-example"
PAGE_NAME = "固定语言兼容示例"


class LegacyPage(QWidget):
    """文案固定中文；不注册循环任务，也不影响已有 Plan。"""

    def __init__(self, context):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(BodyLabel("此页面不支持语言切换，展示旧接口兼容行为。"))
        self.note = LineEdit()
        self.note.setText(context.load({"note": ""})["note"])
        layout.addWidget(self.note)
        layout.addStretch()

    def submit(self):
        return {"note": self.note.text()}


def create_page(context):
    return LegacyPage(context)
