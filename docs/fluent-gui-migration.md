# 完整 FluentWindow 迁移实施记录

## User 导航分组与页面图标

2026-10-28：按[接受规格](stage-4-extensible-user-gui.md#导航分组与页面图标)和[实施前影响审查](user-navigation-impact-review.md)完成本地实施。

- User 使用原生 `addItemHeader()` 与 `addSeparator()`：`GENERAL` 下为 Dashboard、General Settings；`WORKFLOW SETTINGS` 下为全部已加载业务页。空业务分组也保留；收起导航时原生标题高度归零，分隔线和图标分组仍可见。Developer 导航不变。
- 页面模块可选 `PAGE_ICON = FluentIcon.…`；缺省/None 使用 APPLICATION，无效值记录带模块文件名、页面 ID 的日志警告并回退，不进入“页面加载失败”通知。模块本身导入失败仍按原规则隔离。元数据不写入配置或 Manifest，旧页面无需迁移。例子 exp 使用 EDUCATION、mirror 使用 GAME。
- 展开宽度仍为 220，固定页面索引和业务页发现顺序保持；继续使用原生选中效果、配色和路由。页面保存、任务匹配、Plan、Runtime 及重载机制不变。

验证：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_user_pages.py tests/test_user_gui.py tests/test_user_gui_p0.py tests/test_example_workflow.py`，**52 passed，3 skipped**。覆盖图标声明/默认/None/无效值、警告与配置可用性、固定/业务/纯设置页分组、空分组、展开/收起及窄窗口菜单、页面选中与 exp/mirror 的配置进入 Plan。跳过项未计为通过，未启用 Agent 测试。

已生成并检查 `.generated/user-navigation/expanded.png`、`compact.png`、`empty.png`、`menu.png`。预览使用临时数据及既有 macOS 标题栏替身，不操作用户已安装页面、配置、模型或游戏。未做 Windows/macOS 原生窗口验收，offscreen 不能替代原生验收；之前记录的原生启动和个别测试组收尾问题不在本次范围内。

## 重载与终端启动链

2026-10-28：修正重载使用 Popen 后旧启动程序提前返回、重载实例继续向原终端输出的问题。保存、停止活动、双窗口清理及单实例锁释放的顺序保持；清理完成后改为 `os.execv` 替换当前程序入口。macOS/POSIX 下原 PID 和终端启动链保留，最后一个窗口关闭后启动命令才结束；认证仍不进入命令参数，源码与打包入口分别使用自身解释器/程序。

聚焦回归：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_user_pages.py tests/test_error_handling.py tests/test_user_gui.py`，**68 passed，3 skipped**。新增源码/冻结入口替换参数检查，保留清理失败禁止重载及启动失败报错测试。

另在允许本地 IPC 的环境单独运行 `tests/test_user_pages.py::test_reload_through_real_process_restores_both_windows_and_rescans`，**1 passed**：临时用户目录、真实 macOS Cocoa 窗口，重载后恢复双窗口并发现新增页；恢复窗口保持打开时原启动进程仍在，随后调用两个窗口各自的 close 路径，最终正常退出并写入 atexit 标记。该检查不再以直接 QApplication.quit 代替用户关窗。没有调用模型或游戏；Windows 原生打包重载及 VS Code 运行指示器自身未验收。

## 初始迁移记录

2026-10-27：开发者在[可行性调研](qfluentwidgets-feasibility.md)后明确授权正式迁移完整窗口层。本轮已将 User/Developer 产品窗口迁到 FluentWindow；不再通过实验中的源码副本、临时替换或适配下拉框运行。

## 当前实现

- 两个入口、重复唤起、共享 ApplicationService/DeveloperHost、活动归属和单实例锁继续沿用原服务。User/Developer 均直接继承完整 FluentWindow。
- User 的 Dashboard、General Settings 固定置顶，随后加入外置页；页面沿用 QWidget、稳定页面 ID 与 submit/save 契约，宿主将页面 ID 设置为导航 objectName。页面切换使用原生 Fluent 路由，关闭切换动画以保留同步选中语义，不保留隐藏 QListWidget 或额外导航兼容层。
- Developer 的 Capture、Agent Settings、Agent Repair 直接进入 Fluent 导航，替代旧页签。Selected Manifest、刷新与试运行按钮保留在窗口级内容区，独立于 Default 与 Candidate。长设置页使用原生滚动区，避免撑出屏幕。
- 复用现有 SettingsPage、CapturePage、RepairPage、CropView 和 RepairChat。基础按钮、标签、输入框、下拉框、次数框使用官方 Fluent 控件；下拉框统一使用命名 userData，文本输入先构造再 setText，没有新增业务控件适配类。
- NotificationList 的公开 API 保持，内部使用 duration=-1 的 InfoBar，保留多条通知、手动关闭和详情入口。文本按 PlainText 展示，详情仍走已有脱敏及可复制错误对话框。
- 任务滚动区保留原生 QScrollArea 与 AlwaysOn；运行/错误 QDialog 的所属窗口模态、取消、输入释放和日志清理逻辑保持。告警按钮仍使用会话级状态与脉冲动画。
- 请求重载和最后窗口关闭先 exit(0) 退出事件循环，再执行既有 finally 清理与锁释放；清理失败不启动新实例。禁止任一侧活动/后台操作期间重载、恢复窗口及临时密钥边界保持。

不改变 Manifest、用户页面设置、共享 provider 设置格式、Agent 权限、截图像素或 Workflow 调用契约。保留工作区将外置示例移到 example/pages 的变更，修正相关测试/说明路径；两个示例也使用官方 Fluent 输入框/标签，旧原生 QWidget 页面仍受支持。

## 依赖、预览和打包

GUI extra 正式锁定 PySide6 6.11.2 与 PySide6-Fluent-Widgets 1.11.3，按上游声明解析 PySideSix-Frameless-Window、darkdetect 及平台依赖，不再依赖忽略目录或 no-deps 安装。Mac 的上游 pyobjc 元包会引入多个框架，完整 PySide6 也会包含 Addons；这些只随 GUI extra 安装，Windows 不安装 Mac 桥接依赖。CLI 基础安装仍不要求 GUI extra。

```sh
uv sync --frozen --extra gui --extra automation
uv run --frozen --extra gui lalc
uv run --frozen --extra gui lalc --developer
```

原生预览直接运行产品类，设置和 Manifest 使用临时目录：

```sh
QT_QPA_PLATFORM=cocoa .venv/bin/python tests/gui_native_probe.py
# 添加 --show 可人工查看；自动探针不会启动游戏、Agent 或模型。
```

预览图片位于 .generated/fluent-gui/。旧实验脚本已从源码树清理，历史副本保留在 .generated/qfluentwidgets-lab/pre-migration-experiment.py，不能作为正式运行入口。

PyInstaller spec 加入本项目 LICENSE、THIRD_PARTY_NOTICES.md 与 GUI 依赖元数据/原始许可文件。Qt 样式和图标使用官方资源，不依赖开发工作目录。macOS 本地构建：

```sh
PYINSTALLER_CONFIG_DIR=.generated/pyinstaller-cache .venv/bin/python -m PyInstaller \
  --noconfirm --distpath .generated/fluent-build/dist \
  --workpath .generated/fluent-build/build LALC.spec
```

## 验证

- 正式依赖环境普通回归：**459 passed, 53 skipped**。命令为 QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q。49 个 Agent 测试、Windows 原生 DPAPI、两个受本地 IPC 限制的进程检查及原生焦点检查未计为通过。
- Mac offscreen 没有真实 NSWindow，测试层仅替代系统标题栏的原生调用；FluentWindow 类、路由、控件和应用逻辑保持真实。该替身不进入产品代码。
- 真实 Cocoa 会话下，先创建 QApplication 再运行 test_user_gui/test_user_pages/test_developer_gui/test_error_handling/test_repair_chat：**110 passed**。该轮不采用标题栏替身，覆盖原生焦点、独立关闭、跨进程唤起与重载恢复后正常退出。
- 既有 CropView 截图断言修正为按实际 devicePixelRatio 采样；原图区域断言保持不变，DPR=2 的原生检查通过。
- macOS PyInstaller 构建成功。同一打包程序通过临时用户目录中的外置页启动检查：两 FluentWindow、外置发现、QSS/图标资源、通知以及正常退出。证据位于 .generated/fluent-build/bundle-smoke.json，产物位于 .generated/fluent-build/dist/LALC/。第一次启动检查超时，复测同一产物成功，冷启动时长尚未稳定性验收。
- 锁文件一致性、源码编译与 git diff --check 通过。本轮未启用 --run-agent-tests，没有调用 pi、模型或实际游戏。

以上是分开执行且有重叠的检查，不相加为独立用例总数。Windows 10/11 成品、Mica/系统按钮/拖动缩放、游戏焦点与 DPAPI 的联合验收仍属于 #334；本轮 macOS 构建不能代替 Windows 验收。未扩充 #333 双语/Release 信息面板、暗色设置或 Stage 6 Runtime Agent。本轮未提交 Git 或关闭议题。
