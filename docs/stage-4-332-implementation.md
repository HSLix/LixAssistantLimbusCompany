# #332 — 外置业务页面与共享 Agent 设置闭环

2026-10-27：关键决策、追加 grill 与影响审查经开发者确认后授权实现。源码与本地自动化验证已完成；本记录不表示代码已提交、GitHub 议题已关闭或 Windows 打包版已验收。设计依据见 [接受规格](stage-4-extensible-user-gui.md)、[影响审查](stage-4-332-design-impact-review.md)。

## 当前行为

- 外置页面位于 LALC 数据目录的 `pages/`，按稳定页面 ID 保存 JSON 配置；可选注册一个循环任务。目录与当前工作目录、Manifest、Candidate 均独立。页面默认可信，普通导入/创建错误和注册冲突在通知与告警中呈现，其他页面继续可用。
- Dashboard 只显示当前 Plan 支持与可用页面注册的任务交集；正整数次数在失焦时保存，勾选后立即保存。未启用和不匹配项传 0，保存值保留。页面 ID 与任务 ID 不混用，纯设置页也进入 Plan 配置快照。
- Plan 声明 `SUPPORTED_TASK_IDS` 字面量列表；缺失为空，空列表产生告警但允许运行，非法列表校验失败。不改写旧不可变发布物。双向不匹配通过跳动的圆圈感叹号弹窗报告，告警在应用会话内保留，只有整应用重启且检查干净才消失。
- 外置页自行决定保存交互，宿主提供 `load/save`；开始/重载前要求所有已加载页提交、校验、保存。失败保留输入，阻止启动或重启。页面设置、次数及运行输入分别保存/复制，切换 Manifest 不重置。
- User 与 Developer 复用同一 Agent Settings 控件，均采用编辑框失焦、选择项立即保存。每个 provider 一套完整共享内容，独立保存两侧选用项；只有 User 有开关，且明确显示运行时修复未接入。旧设置读取不落盘，首次成功保存迁移，保留已有凭据引用；旧文件从未保存的另一 provider 参数采用默认值。
- Developer 打开前提交 User Agent 输入，失败不打开；Developer 打开期间 User 整个 Agent 区域不可编辑。独立入口与重复唤起共用协调器，Developer 关闭前提交尚未失焦的输入，成功后 User 重读最新配置并恢复；禁用的旧表单不回写。
- 本地设置保存不占用 Agent 后台队列；连接检查、Agent 和运行仍遵守活动互斥。Agent 每轮开始时以同一临界区固定完整有效配置与实际认证；连接检查也使用独立快照。清除/替换只影响新活动，当前轮次继续旧快照。沿用 Windows DPAPI、macOS 进程内临时密钥及现有对话级脱敏；报错不主动拼接认证值。
- 重载先提交并保存，禁止任一侧活动/未结束线程或后台操作；封闭新入口后，等待最终清理、关闭双窗口及本地通道、释放单实例锁，再启动新进程恢复原先打开的窗口。保存/清理失败不重启，进程创建失败有明确错误。macOS 存在临时密钥时重载前提示，重启后需重新输入。关闭再打开 User 不重新扫描模块。

最小例子和开发契约见 [extensible-pages](../example/extensible-pages/README.md)。该例包含循环页、纯设置页、唯一 Plan 与消息 Task，不迁移完整游戏业务，不自动安装或覆盖外置页。

## 验证证据

普通回归（允许本地 IPC；不启用 Agent 测试）：

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
```

结果：**460 passed, 50 skipped**。跳过项为标记 Agent 的 49 项及 Windows 原生 DPAPI 1 项，未计为通过。普通回归包含两个真实进程的窗口唤起与整应用重载，后者证明恢复双窗口、重新扫描新增页；还包含配置深拷贝、双向告警、纯设置页、错误/冲突隔离、无效提交不建立 Run、即时保存和编辑权交接、重载失败分支。

显式选择本地 HTTP 替身的 Agent 接入用例：

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q --run-agent-tests tests/test_agent_repair_agent.py -k 'text_only_and_context_retained or request_limit_ends_round_and_next_round_resets or python_plan_edit_publish_and_saved_trial_ignore_unpublished_changes or deepseek_thinking_survives_tools_and_next_round or round_freezes_shared_config_and_auth_until_next_message'
```

所列 **8 项通过**（分两次定向执行）；使用真实 pi 与本机 HTTP 替身，不调用外部模型。新增用例在当前轮次中清除/替换认证和额度，确认当前工具循环继续用旧值，下一轮读新值，产物不含测试密钥。其余 Agent 用例未作为本票新验证证据。

已检查 Dashboard 和 General Settings 的 offscreen 截图；`git diff --check` 与源码编译检查通过。额外尝试的独立 pyright 检查未通过：当前检查环境存在 PySide6 类型路径解析及既有未标注 GUI/诊断类型问题，不能声称静态类型全绿；本票以实际导入、执行和回归证据为准。

## 未验收边界

Windows 打包版入口/外置页/DPAPI 联合验收仍属于 #334；本次未运行真实模型、真实游戏和 Windows 原生 DPAPI。双语及 Release 信息面板属于 #333，Runtime Agent 属于 Stage 6。进程成功创建后的应用初始化错误沿用新实例致命错误出口，不增加启动握手或自动回滚机制。多个页面保存失败时保证不运行/重启，不保证回滚其他页面已成功保存的独立配置。
