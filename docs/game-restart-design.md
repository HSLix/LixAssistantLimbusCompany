# 游戏重启与内置崩溃恢复

## 2026-11-07 已确认决定

- 新增应用登记的 control Trusted Action `control.restart_game`，按已保存的 Steam 客户端路径及库配置定位 Limbus 可执行文件。
- 对已有目标先请求正常关闭；超时后只强制终止该目标窗口对应的游戏进程，确认退出后再启动，避免重复实例。
- 成功条件为新窗口出现、重新绑定并置前；登录、更新、主界面和业务可续接性由后续 Step 判断。
- 崩溃恢复采用应用内置 Recovery Rule，对所有 Manifest 自动生效，不要求各 Manifest 登记。
- 确认游戏进程已退出才自动重启；用户接管保留人工恢复。后续输入策略修订：失焦、最小化走活动等待后自动聚焦，见[输入所有权专项记录](input-ownership-design-impact-review.md)。
- 每次 Top-level Execution 最多自动重启一次；再次崩溃或重启失败终止本次运行。显式调用 Action 不消耗自动恢复额度。

## 已最终确认的实施边界

- 保留当前 Step 作为恢复边界和外层调用栈；内置规则优先处理进程退出，再重新调用当前 Step，不重放 Task/Plan。
- 执行开始前没有可连接窗口仍按现有启动规则报错；本次处理运行中进程退出，并允许正式恢复调用无窗口的重启动作。
- 关闭前验证保存路径、唯一安装及固定可执行文件；路径缺失或无效时明确失败，不另行扫描磁盘或接受 Workflow 自定义程序路径。
- 默认正常关闭等待 5 秒、强制终止确认等待 5 秒、启动窗口及绑定等待 60 秒；等待持续响应暂停、接管和取消。自动绑定前遵守其他应用连续空闲十秒的规则，用户活动等待不消耗绑定超时；明确手动恢复豁免本次聚焦的十秒等待，不重复启动游戏。
- 多个匹配窗口、进程身份无法确认、进程仍在但窗口消失均不判定为崩溃，不猜测或批量结束游戏。

2026-11-07 用户确认上述最终设计，并追加要求：等待、关闭、启动、重启与绑定等过程必须有日志。

## 实施前影响审查

设计变化：原先所有窗口失效都进入人工暂停；新增确认进程退出后的应用内置恢复规则，优先于 Manifest 业务规则，并经现有 control Action 边界重启。仅当前 Step 可重新调用，保持外层帧；不扩展 Runtime Agent 权限。

已确认影响（源码检查，尚未执行验证）：

- `control.py:InputSession.check` 将所有 `WindowError` 转为 `UserInterruption`；需要在检查所有权后单独识别进程退出，失焦/最小化/未知故障仍暂停。
- `runtime.py:_invoke_step` 直接传播 `EnvironmentFailure`；需要给确认的游戏退出增加专用分支，并记录内置规则 detect/recover 及一次性额度。普通恢复 `_recover_step` 会先检测 Manifest 业务规则；依赖窗口观察的规则无法处理无窗口崩溃，应在此前恢复窗口。
- `runtime.py:trusted_action` 在 Action 前检查窗口，`application.py:_control_input` 委托输入会话；重启动作需要在同一 control 权限下允许无窗口，但继续检查所有权、暂停、取消及输入释放状态。
- `focused.py:WindowsWindowPlatform` 只有查窗、聚焦及截图，无进程退出确认与关闭能力；必须持有目标进程句柄，防止 PID 重用误判或误杀。
- `game_version.py:load_steam_root/installation` 已验证保存配置、Steam 多库与唯一安装，可复用，不新增路径设置或程序参数入口。
- `run_logs.py:read_page` 仅显示 `component_log` 和 Action 结果；重启各阶段须写 `component_log`，否则只有底层 Trace 而用户不可见。等待记录开始/结束及超时，不逐次轮询刷屏。
- `actions.py`、`run_context.pyi`、动作全集断言和平台替身需同步；新增测试覆盖权限、关闭升级、路径失败前无副作用、重新绑定、自动次数、Plan 终止及日志可见性。

潜在风险：真实 Win32 关闭/终止、Steam 启动行为及游戏登录后 Step 可续接性只能在 Windows 现场验收；替身测试不证明这些行为通过。启动等待的暂停/接管需保留重启阶段，防止手动恢复后重复启动。

实施顺序：平台进程能力与所有权检查 → 重启动作和阶段日志 → 内置规则与 Step 入口 → 类型/测试/现行契约同步 → 串行执行相关默认测试。不会运行真实游戏或模型。

Win32 依据：[TerminateProcess](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-terminateprocess) 是异步终止，需用 [WaitForSingleObject](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject) 对持有的进程句柄确认退出。

## 实施与验证

- 平台通过 `WindowsGameProcess` 保留原进程句柄及路径；输入会话结束关闭句柄，不终止仍在运行的游戏。重启只终止原句柄指向的进程，不按名称批量结束。
- 新 Action 复用 `RunContext.control_input` 的 control 权限；签名与类型声明由应用动作表生成，没有额外可选命令或程序路径。
- 内置规则 detect/recover 经过执行器现有 Recovery Rule Trace，recover 经正式 Action 调用；每个执行器持有一次自动额度，自动重新调用 Step 的结果也进入 Trace 和 Ledger。
- `game_restart.py` 为阶段写用户可见 `component_log`；等待记录开始、结束或超时。Action 本身仍保留 Debug 输入、结果、原始错误链、耗时。重启阶段暂停在原流程中等待手动恢复，不重新发起关闭/启动；GUI／CLI 暂停说明同步。
- 最终相关默认测试：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_game_restart.py tests/test_input_control.py tests/test_recovery.py tests/test_focused_observation.py tests/test_stubgen.py tests/test_manifest_transition.py tests/test_assets.py tests/test_run_logs.py tests/test_python_plan.py tests/test_cli.py tests/test_developer_gui.py tests/test_example_workflow.py -k 'not test_exp_mirror_pages_feed_plan_and_shared_actions'`，**225 passed, 2 deselected**。覆盖正常/强制关闭、路径验证前无副作用、启动/聚焦超时、取消/接管后不重复启动、当前 Step 续接、显式动作不占自动额度、再次崩溃/检测错误终止 Plan、手动恢复后才处理接管期间的崩溃、阶段日志默认可见，以及原有恢复/输入/日志流程。
- 常规 `uv run --frozen` 在准备本地项目构建时因网络不可达而无法获取 setuptools，故使用已有 `.venv`；类型声明通过 `.venv/bin/python -m lalc generate-stubs` 生成并由相关测试核对。
- 默认全量首次执行：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`，**1000 passed, 106 skipped, 3 failed**。其中新增动作使教学样例“调用全部应用动作”的断言失效，已改为只检查观察与输入动作并复测通过，教学样例不承担重启游戏的演示。
- 另两项 `test_exp_mirror_pages_feed_plan_and_shared_actions[False/True]` 仍失败：前者期待三个 Task 结果而当前示例 Plan 只运行 mirror；后者读取已不存在的 `example/workflow/exp.py`。在同步动作断言后的单独相关回归中也实际复现这两项失败（224 passed, 2 failed，当时尚未追加最后一项检测错误测试）。本次未恢复旧 exp 示例，最终相关验证显式排除这两项，不能报告为通过。
- 全量与相关验证串行执行，未开启 Agent 测试；106 skipped 不算通过。未执行 Windows 成品或真实游戏验收，替身流程及 Win32 句柄 API 替身测试不代表实际游戏进程通过。
