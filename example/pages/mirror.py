"""镜牢教学页：配置消息，次数由 Dashboard 管理。"""

from PySide6.QtWidgets import QWidget, QVBoxLayout
from qfluentwidgets import BodyLabel as QLabel, LineEdit

PAGE_ID = "mirror"
PAGE_NAME = "镜牢教学示例"
TASK_ID = "mirror"


class MirrorPage(QWidget):
    """页面自行校验业务输入，宿主在启动/重载前统一提交。"""

    def __init__(self, context):
        super().__init__()
        self.context = context
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("消息（必填；在开始运行或重载时保存）"))
        self.message = LineEdit()
        self.message.setText(context.load({"message": "Hello"})["message"])
        layout.addWidget(self.message)
        layout.addStretch()

    def submit(self):
        message = self.message.text().strip()
        if not message:
            raise ValueError("消息不能为空。")
        return {"message": message}


def create_page(context):
    return MirrorPage(context)
