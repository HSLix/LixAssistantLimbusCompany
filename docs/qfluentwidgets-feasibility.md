# QFluentWidgets 可行性调研与实验

2026-10-27 后续状态：开发者已授权正式完整窗口迁移，当前产品实现与验证见[迁移记录](fluent-gui-migration.md)。下文保留迁移前实验事实，不作为当前实现状态。

2026-10-27。结论：**可以作为现有控件和完整窗口壳的迁移候选，当前功能不要求放弃；需要显式适配，不能批量替换 Qt 类名。** 本轮只增加实验脚本、报告及忽略目录中的依赖/证据，没有修改产品 GUI、项目依赖或采纳新的架构决策。

## 实验环境与方法

使用官方 [PySide6-Fluent-Widgets](https://pypi.org/project/PySide6-Fluent-Widgets/) **1.11.3**、PySide6-Essentials **6.11.2**、PySideSix-Frameless-Window **0.8.2**。基础包已包含本轮需要的控件、InfoBar、MessageBox 和 FluentWindow，未用 Pro 或 full 扩展。

迁移前实验脚本曾提供两条路线；现已清理其源码替换机制，正式预览使用[产品原生探针](../tests/gui_native_probe.py)：

1. controls：保留当前 QMainWindow，替换按钮、输入框、下拉框、勾选框、次数框和列表；仅在实验中适配下拉框第二参数。
2. shell：在进程内创建 GUI 源码副本，基类换为 FluentWindow；复用原有协调器、应用服务、保存、活动门控和关闭方法。User 固定页/外置 QWidget 接入 Fluent 导航；Developer 整个现有工作台作为一个页面，保留三页签和 Selected Manifest。它证明完整窗口层的可行性，不代表 Developer 导航已重新设计。

原始产品文件不被覆写。正式实现应直接修改窗口构建和调用参数，**不能将实验中的源码字符串替换或测试适配类作为产品兼容层**。

依赖位于 `.generated/qfluentwidgets-lab/deps/`；所有设置和 Manifest 在临时目录中，重载实验使用临时 HOME/USERPROFILE/LOCALAPPDATA，不接触真实用户配置、游戏或模型。当前工作区外置示例已移动至 `example/pages/`，部分既有测试仍引用旧目录；实验仅在忽略目录重建样例副本供测试使用，没有改动这项用户变更。

## 功能对照

| 当前需求 | 实验结果与迁移边界 |
|---|---|
| 输入框失焦保存、选择立即保存 | 标准 editingFinished/currentIndexChanged 信号可继续使用；两条路线均实测保存成功。 |
| 共享 provider 内容、双侧独立选用、单一编辑入口 | 复用当前 SettingsPage 和协调器，Developer 打开禁用 User，独立关闭后恢复并读回原先选用项；重复打开仍复用同一窗口/服务。 |
| 外置页自动发现和 QWidget 契约 | 现有原生 QWidget 可直接加入 Fluent 导航，需设置非空 objectName，实验用稳定页面 ID；无需把页面并入 Manifest。原生外置页不会自动获得全部 Fluent 样式。 |
| 所属窗口模态 | 实际 Fluent MessageBox 设置 WindowModal 后，另一 Developer 窗口仍可获得原生焦点；现有运行/错误 QDialog 的功能回归也通过。必须继续显式设置父窗口和模态范围。 |
| 多条通知、手动关闭、详情入口 | InfoBar 设置 duration=-1、分别绑定所属窗口，可同时保留并添加详情按钮；经过默认超时时间仍在，关闭一条不影响另一条。不要沿用默认自动消失时长。 |
| 跳动圆圈告警及会话保留 | 复用原有告警状态与按钮动画，Fluent 按钮可承载；不使用会自行完成/消失的状态提示代替。 |
| 循环列表滚动条常驻 | 原生 QScrollArea 保留。Fluent ScrollArea 的平滑滚动代理会将原生策略改成 AlwaysOff，不能直接满足现有要求；完整窗口壳也允许混用原生滚动区。 |
| 截图框选和原始像素 | 自定义 CropView 保留。在 Retina DPR=2 下，原图区域计算、旧框清除及按比例采样的绘制探针通过，不需要重写捕获/裁剪链路。 |
| 独立关闭、活动取消与清理 | 复用当前方法，相关既有回归通过。 |
| 整应用重载、单实例交接与恢复 | 两个真实 Cocoa 进程实测：恢复 User/Developer FluentWindow、发现新增外置页、恢复编辑权禁用状态，并确认新实例正常退出。需要下文退出顺序适配。 |

## 已实证的适配点

- **ComboBox 的参数不同。** Qt 的 `addItem(text, userData)` 与 Fluent 的 `addItem(text, icon=None, userData=None)` 不同；直接替换会使 provider/Manifest/错误详情的 currentData 为空。迁移时统一用命名参数 `userData=`，无需创建新的业务下拉框。见[官方源码](https://raw.githubusercontent.com/zhiyiYo/PyQt-Fluent-Widgets/PySide6/qfluentwidgets/components/widgets/combo_box.py)。
- **LineEdit 构造不同。** `LineEdit("初始文本")` 会失败；应先构建再 setText。现有核心 Agent 表单无文本构造参数，外置页作者需要知道这个差异。
- **FluentWindow 不提供 setCentralWidget。** 当前两处窗口初始化及页面挂载必须迁移，不能只替换基类。外置页仍保持 QWidget，服务与执行器不需改写。[官方窗口源码](https://raw.githubusercontent.com/zhiyiYo/PyQt-Fluent-Widgets/PySide6/qfluentwidgets/window/fluent_window.py)。
- **页面动画改变索引更新时间。** 首次完整窗口回归中，切换后即时读取 currentIndex 的既有断言失败。实验关闭 stackedWidget 页面切换动画后通过；正式迁移可先沿用同步语义，其他按钮/通知动画不必一起关闭。
- **Cocoa 退出顺序必须适配。** 直接沿用 quit 的完整窗口实验曾在 closeEvent → coordinator.closed → quit 路径崩溃；原生 QMainWindow 对照也未完成正常重载，不能将现象简单认定为库缺陷。实验将“请求重载”和“最后窗口关闭”两处改成先 exit(0) 退出事件循环，再让既有 finally 顺序清理。最终验证包括新实例恢复、正常退出标记及无致命错误输出；不再只以 ready 标记判定通过。该修改仅在实验副本中。
- **窗口样式不能代替活动管理。** Mica/无边框/遮罩只负责表现；现有服务互斥、窗口归属、配置快照与清理仍由本项目代码负责。

## 执行证据

- 控件路线、offscreen：**95 passed, 2 deselected**。复用现有 User GUI、外置页、Developer GUI 和错误处理测试。
- 完整窗口路线、原生 Cocoa：**94 passed, 3 deselected**，并通过独立原生探针。排除两项另行验证的跨进程测试，以及一项既有截图断言；没有将失败断言计为通过。
- 该截图断言假设逻辑坐标等于物理截图像素：未替换任何控件的原生 Qt 基线也在 DPR=2 失败。实验保留产品 CropView，另按实际 DPR 检查并通过，未修改或降低实际截图/裁剪精度。
- 独立真实进程重载：**通过**，两窗口均为 FluentWindow，重新扫描后有 4 个页面，User Agent 区域保持禁用，新实例正常退出。
- 结果：`.generated/qfluentwidgets-lab/controls-results.json`、`shell-results.json`、`shell-restart-debug.json`；预览为同目录 `controls-dashboard.png`、`shell-dashboard.png`、`shell-settings.png`。

当前产品复现（macOS 原生检查需要图形会话；原型命令已由产品探针取代）：

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
QT_QPA_PLATFORM=cocoa .venv/bin/python tests/gui_native_probe.py
```

独立实验依赖安装：

```sh
UV_CACHE_DIR=.generated/uv-cache uv pip install --python .venv/bin/python \
  --target .generated/qfluentwidgets-lab/deps --no-deps \
  PySide6-Fluent-Widgets==1.11.3 PySideSix-Frameless-Window==0.8.2 darkdetect==0.8.0
# macOS 本轮实际导入所需桥接模块：
UV_CACHE_DIR=.generated/uv-cache uv pip install --python .venv/bin/python \
  --target .generated/qfluentwidgets-lab/deps --no-deps \
  pyobjc-core==12.2.2 pyobjc-framework-Cocoa==12.2.2 pyobjc-framework-Quartz==12.2.2 PyCocoa==25.12.4
```

上述 no-deps 只用于复用本项目已安装 Qt 的实验；不能直接作为正式发布依赖策略。库元数据声明完整 PySide6，项目目前只声明 Essentials；正式锁定/打包需检查实际 Qt 模块及平台桥接依赖。实验目录约 40 MiB，不包含项目已有 Qt，不是 Windows 成品体积估算。[官方依赖声明](https://raw.githubusercontent.com/zhiyiYo/PyQt-Fluent-Widgets/PySide6/setup.py)、[无边框库平台依赖](https://raw.githubusercontent.com/zhiyiYo/PyQt-Frameless-Window/PySide6/setup.py)。

## 建议和未验收项

建议将**完整 FluentWindow + 官方基础控件 + 现有业务服务/自定义画布**纳入正式迁移方案。统一修改参数与页面挂载，继续复用 SettingsPage，不另造重复业务组件；Developer 导航布局另行确认。原生滚动区和需要精确控制生命周期的现有对话框可以保留，不要求全部替换。

本轮未做 Windows 10/11 实机、Mica、拖动/缩放/系统按钮、焦点接管、打包资源与单实例联合验收；未做暗色、键盘/读屏完整无障碍或长时间稳定性验证。实验没有调用 Agent、真实模型或游戏。Windows 原生行为仍是正式迁移验收门槛，macOS 原生和 offscreen 证据不能替代。

当前项目 LICENSE 是 AGPLv3，库 PyPI 元数据为 GPLv3 并声明商业双授权；正式选型时需核对其发布授权信息，本次不改变项目许可证或声称已完成授权审查。[官方授权说明](https://pypi.org/project/PySide6-Fluent-Widgets/#license)。
