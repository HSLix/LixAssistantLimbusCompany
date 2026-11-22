from PySide6.QtWidgets import QWidget, QVBoxLayout
from qfluentwidgets import BodyLabel

PAGE_ID = "sample.notice"
PAGE_NAME = "Notice"

class NoticePage(QWidget):
    """展示提示的最小设置页。"""

    def __init__(self, context):
        super().__init__()
        QVBoxLayout(self).addWidget(BodyLabel(context.translate("页面创建成功", "Page created successfully")))

    def submit(self) -> dict:
        """本页没有可保存字段，提交空配置。"""
        return {}

def create_page(context):
    """返回带 submit 方法的页面实例。"""
    return NoticePage(context)
