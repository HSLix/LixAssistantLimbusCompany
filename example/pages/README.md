# exp、mirror 教学页面

2026-11-02：GUI Construct 已可通过专用工具创建 / 修改 Session 页面草稿，加载检查通过后进入默认 Proposed 的三 Tab 审批，由人批准固定版本安装；正式目录仍不开放通用编辑，Repair / CLI 不继承页面工具。当前用法及验收边界见[实施记录](../../docs/stage-5-339-340-implementation.md)和[审批修订](../../docs/page-review-tabs-implementation.md)。

将本目录 `exp.py`、`mirror.py` 手动复制到 `lalc data-dir` 显示的数据目录下的 `pages/`。同名用户页先检查，不能直接覆盖。重启应用或在通用设置中保存并重新加载整个应用。

两个页面分别使用 `PAGE_ID = TASK_ID = "exp"`、`"mirror"`，配置教学消息；Dashboard 管理是否启用和重复次数。页面 ID、任务 ID 与 Component 名称是不同概念，这里只是有意取相同字符串。

搭配 [workflow](../workflow/README.md) 发布的 Plan 使用，链路为页面消息 → `settings[任务 ID]` → Plan → `tasks.exp` / `tasks.mirror` → 共享 Subworkflow / Step → 应用 Trusted Actions。样例只观察和等待，不实现经验本或镜牢的真实游戏流程。

外置页是可信、同进程的 Python 模块，契约分三个层级，即使只显示一个标签也必须满足：

1. **模块**：导入后提供非空字符串属性 `PAGE_ID`、`PAGE_NAME`；不能只放在 `create_page` 的局部变量或页面实例上。`TASK_ID` 可选，纯设置页可省略。属性不必是字面量常量，下面只是最小示例。
2. **工厂函数**：模块提供可调用的 `create_page(context)`，返回一个 QWidget 实例。
3. **返回实例**：该实例提供可调用的 `submit()`；正式运行 / 重载提交时返回 JSON 兼容的配置字典，无字段页返回 `{}`。`submit` 属于返回实例，不是工厂函数或模块；不强制返回类型注解。预览只检查方法存在，不主动调用它检验配置。

最小完整纯设置页（不注册循环任务）：

```python
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
```

有输入字段的页面应在 submit 中读取并校验输入，非法时抛出明确错误。`context.load(defaults)` 读取配置副本，`context.save(config)` 保存 JSON 配置；宿主开始运行和整应用重载前提交所有已加载页面，包括未启用的任务与纯设置页。页面不随 Manifest 发布；Agent 只能通过专用工具修改草稿，经人工审批安装，不能通用编辑正式目录。

可与 `PAGE_ID` 并列声明可选导航图标，例如 `from qfluentwidgets import FluentIcon` 后设置 `PAGE_ICON = FluentIcon.EDUCATION`。exp 使用 EDUCATION，mirror 使用 GAME；未声明或设为 `None` 时统一使用 APPLICATION。图标值必须是 `FluentIcon` 成员；无效值会记录带页面身份的警告并回退默认图标，页面仍可用。若声明引用不存在的枚举成员，导致模块本身导入/求值失败，仍按原有加载失败规则处理。图标属于展示元数据，不保存到 `user-settings.json`，修改后需整应用重载。

导航展开时，Dashboard 与 General Settings 位于 `GENERAL`，其下以原生分隔线和 `WORKFLOW SETTINGS` 标题列出全部已加载业务页，包括纯设置页和当前 Plan 不支持的页。收起为图标栏后隐藏标题、保留分隔线；没有业务页时也保留该分组。General Settings 继续使用齿轮，页面顺序和配置保存规则不变。

页面 ID、任务 ID 各自唯一；冲突注册全部排除，普通导入或创建失败只跳过本页。配置保存在数据目录 `user-settings.json`，切换 Manifest 不删除配置。页面改动需整应用重载。Plan 的 `SUPPORTED_TASK_IDS` 必须是模块级字面量字符串列表；Dashboard 只提供页面与 Plan 的任务 ID 交集，缺项会提示。纯设置页可省略 `TASK_ID`，其配置仍传入 Plan。


## GUI 语言与旧页面兼容

User GUI → General Settings → 应用 → 界面语言可选“跟随系统 / 简体中文 / English”；选择立即保存，通过“保存并重新加载整个应用”生效。中文系统（含繁体地区）跟随到简体中文，其余用英文。两窗口共享语言，Developer 不提供独立入口；活动期间可保存语言选择，但不能重载。GUI 语言不影响游戏识别语言。

`context.language` 是本次已生效的 `zh_CN` 或 `en_US`；`context.translate(中文文案, English_text)` 按该语言选择页面自带文案，无需编译翻译资源。导航名可选声明 `PAGE_NAMES = {"zh_CN": "中文名称", "en_US": "English name"}`，键只允许这两个语言，值须为非空字符串；未提供当前语言时回退原有 `PAGE_NAME`。`PAGE_NAME` 仍必需，原有 create_page、submit、配置保存契约不变。

`exp.py` 和 `mirror.py` 同时翻译导航、页面标签及输入校验提示，保持现有页面/任务 ID 和 message 配置键。新增 `legacy.py` 是不使用语言接口的纯设置页：导航和标签固定中文，不注册循环任务，切换英文仍保留原文，用于验证旧页面兼容；其 note 配置仍正常保存。页面作者负责自己的翻译，宿主不调用模型翻译页面，也不翻译用户填写的内容。旧页面无需迁移，修改已安装页面后仍需整应用重载。
