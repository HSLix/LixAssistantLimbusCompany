# Fluent Gallery 参考

[`gallery/`](gallery/) 是完整的离线 PySide6 Gallery 副本，来自[上游固定版本](https://github.com/zhiyiYo/PyQt-Fluent-Widgets/tree/d6f5a01f7f3fe285c6900e476349467810267839/examples/gallery)，对应 LALC 使用的 QFluentWidgets 1.11.3。保留[上游许可证](gallery/LICENSE)，不修改示例、不把它作为 LALC 的运行入口。

## 从哪里找

按用途直接读 `gallery/app/view/` 下的示例，不必先联网搜索，也不必读生成的 `app/common/resource.py`：

- 按钮、开关、下拉框：[基本输入](gallery/app/view/basic_input_interface.py)；文本控件：[文本](gallery/app/view/text_interface.py)。
- 顶部标签和分段导航：[导航](gallery/app/view/navigation_view_interface.py)；设置卡：[设置](gallery/app/view/setting_interface.py)，容器排版：[布局](gallery/app/view/layout_interface.py)。
- 弹窗：[对话框](gallery/app/view/dialog_interface.py)；错误和提示：[状态反馈](gallery/app/view/status_info_interface.py)。

## 配置页常用搭配

- 设置行：`CardWidget` 搭配 `SwitchButton`（开关）或 `ComboBox`（选一项），不为简单设置额外套卡片。
- 文本和操作：`PlainTextEdit` 用于多行输入；通常用 `PushButton`，`PrimaryPushButton` 留给弹窗「确定」等主要操作。
- 页内切换：`Pivot` 搭配 `QStackedWidget`，可用 `currentItemChanged` 接收路由键。若直接绑定点击回调，核对信号参数，不要把点击传出的布尔值当成路由键；验证实际点击，不只验证截图。
