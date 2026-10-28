# 外置页面与 Python Plan 最小示例

本示例只验证页面参数到正式 Task 的链路，不操作游戏，不是完整游戏业务迁移。实际运行仍使用应用原有游戏会话启动要求；自动化测试使用窗口替身。

## 安装和运行

1. 运行 `lalc data-dir` 查看 LALC 数据目录。在该目录创建 `pages/`，手动复制仓库 `example/pages/loop.py`、`example/pages/general.py`。同名文件先人工检查，不覆盖已有用户页。
2. 在一个独立工作目录的 `candidate/` 中放入本例 `manifest.json`、`plan.py`、`task.py`；不要覆盖现有 Candidate。从该工作目录运行 `lalc validate`、`lalc publish`。这些命令应使用已安装的 LALC，或项目虚拟环境的绝对路径入口。
3. 启动 User GUI；若应用已打开，使用 General Settings 的“保存并重新加载整个应用”。在 Dashboard 选择新发布的 Default Manifest。
4. 打开“消息循环示例”填写消息、“通用前缀示例”填写前缀；回 Dashboard 勾选消息任务并填写次数，再开始运行。Task 的实际结果是前缀加消息，每次调用均保留记录。

## 外置页契约

每个自包含 `.py` 模块声明：

- `PAGE_ID`：稳定页面 ID；不能使用 `dashboard` 或 `general-settings`。
- `PAGE_NAME`：显示名称。
- 可选 `TASK_ID`：一个稳定循环任务 ID；与页面 ID、Component 逻辑名分别定义。
- `create_page(context)`：返回提供 `submit() -> dict` 的 QWidget。

`context.load(defaults)` 返回本页保存配置或默认值的独立副本；`context.save(config)` 保存本页 JSON 对象。页面自行决定编辑/保存交互；`submit()` 应检查当前输入并返回配置，非法输入抛出明确错误。宿主在开始或重载前提交所有已加载页，失败就不启动；纯设置页和未启用任务的页面也参与校验。

页面默认可信，与 GUI 同进程运行；普通导入/创建异常只跳过本页，冲突注册全部排除。页面不能假定独立进程或安全沙箱。启动时按文件名排序发现非下划线开头的 Python 文件，页面 ID 和任务 ID 分别唯一。关闭再打开 User 沿用本次加载的页面；修改模块需整应用重载，不使用模块热替换。页面不随 Manifest 发布，内置 Developer Agent 无权编辑页面。

Plan 用模块级字面量列表 `SUPPORTED_TASK_IDS = ["sample.loop"]` 声明支持项；缺失按空列表处理，非法或重复项拒绝发布/加载。Dashboard 只显示页面与 Plan 的任务 ID 交集。不匹配项传 0、保存次数不清空；纯设置页配置仍进入 `settings`。空支持列表以及双向缺项通过循环列表旁跳动的圆圈感叹号报告，关闭弹窗、切换 Manifest 或关闭再打开 User 都不清除本会话告警；整应用重启后重新检查。

次数与页面配置保存在数据目录的 `user-settings.json`，跨 Manifest 共用，不随页面卸载或切换版本删除。开始时复制输入，运行中配置修改只影响后续执行。

## Fluent GUI

User/Developer 均使用完整 FluentWindow，页面仍是 QWidget。当前外置示例使用官方 Fluent LineEdit/BodyLabel；输入框先构造再 setText，不把文本传入父窗口参数。原有原生 Qt QWidget 页面仍受支持，页面 ID、提交及保存契约不变；导航对象名由宿主按页面 ID 设置。
