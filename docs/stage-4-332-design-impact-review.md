# #332 — 外置页面与共享 Agent 设置影响审查

2026-10-27：基于本轮已确认决策及当前工作区源码进行审查；评审结论及追加 grill 已获开发者确认并授权实现，现已完成本地实现，见[实施记录](stage-4-332-implementation.md)。下文保留实施前审查证据。已有 #331 基线保留，不将当前基线差距报告为 #331 回归。接受规格见 [Stage 4](stage-4-extensible-user-gui.md)，架构依据为 [ADR 0032](adr/0032-use-python-plans-and-coexisting-user-developer-guis.md)。审查阶段仅修改设计文档与术语；后续授权实现及验证另见上述实施记录。

## 设计细化与替代

- 明确外置目录为 LALC 数据目录 `pages/`。手动安装的 Python 页面默认可信，在 GUI 进程运行；隔离普通导入、创建错误，不建设不可信代码沙箱，Developer Agent 不得写入。
- 原“不支持项在循环行显示 warning”细化为按任务 ID 双向检查：页面注册但 Plan 不支持、Plan 支持但无可用注册均从循环行隐藏，在列表旁跳动的圆圈感叹号中集中报告。告警会话内保留，只有整应用重启重载且检查无问题才清除。
- 告警不阻止匹配任务运行；不匹配项本次次数为 0，保存的次数和页面配置保留。纯设置页没有任务 ID，不参与匹配，其配置仍传入 Plan。
- Plan 未声明支持项按空列表处理；空列表本身产生 warning，不禁止运行。非法声明校验失败。不改写旧不可变 Manifest，也不分析调度代码推测支持范围。
- Dashboard/General Settings 的输入框失焦保存，选择与勾选变更立即保存。外置页自行决定交互，通过宿主统一接口保存；运行/重载前所有已加载业务页提交、校验、保存，失败则不启动或重启。
- 每个 provider 一套完整共享配置，两侧各自持久选用 provider；无多套命名配置。旧配置及凭据引用保留，两侧初始选旧 provider，User 开关默认关，Developer 不受影响。另一 provider 未保存过的参数只能采用现有默认值。
- 追加 grill 已确认：Developer 打开期间仅 Developer 可编辑 Agent 设置；交接前先保存 User 当前输入，失败不打开 Developer，关闭后 User 重读最新值再恢复。每轮 Agent 的完整设置与实际认证一起固定。重载覆盖双窗口，严格在旧服务/线程/单实例通道和锁清理后启动新实例；失败明确报错，不提前启动等待交接。

这些是 ADR 0032 内的框架细化，不替代正式 Plan 的内容哈希、Task 调用权限或 Developer Policy，也不接入 Stage 6 Runtime Agent。

## 实施前已确认的差距（历史）

| 范围与证据 | 实施前可达行为 | 必须落实的影响 |
|---|---|---|
| `src/lalc/gui.py: UserWindow.__init__ / start_plan` | 固定两页；开始直接调用无参数的 `service.start_plan()` | 增加目录发现、最小页面声明/创建/提交保存契约、循环列表及告警、固定页自动保存、配置汇总；错误页面不提供有效任务注册。无需修改核心即可安装新页。 |
| `src/lalc/manifest.py: _validate_component_source / _load_module`；`src/lalc/runtime.py: automation_plan` | Plan 装饰器只标记角色；校验/加载路径未定义支持任务声明 | 增加可静态校验的显式支持列表并从已验证 Plan 源码读取。建议模块级字面量 `SUPPORTED_TASK_IDS`，缺失为空；非法值/重复 ID 校验失败。保留 plain decorator、哈希和旧 Manifest 身份，不新增 Manifest schema 或改变调用权限。 |
| `src/lalc/application.py: start_plan / start`；`src/lalc/runtime.py: WorkflowExecutor.prepare_inputs` | 已规范化并复制两份 Plan 输入，但不负责页面/任务匹配 | 复用已有输入快照边界。GUI 按本次固定 Default 的支持声明生成次数，包含不匹配 ID 的 0；相同 Manifest ID 随输入一起提交，避免按 A 匹配后启动 B。纯设置页及保留配置进入独立 settings。无需重写执行器调度和结果账本。 |
| `src/lalc/gui.py: NotificationList / GuiCoordinator / run_gui`；`src/lalc/gui_instance.py: GuiInstance.close`；`src/lalc/lifecycle.py: run_application` | 有持久通知、双窗口及最终清理；正常路径结束后返回退出码，没有重载协议 | 页面错误复用通知；告警标识另保留本会话诊断，关闭弹窗不清除。重载须先保存、拒绝活动或未结束的后台操作，完成窗口/线程/服务/IPC 锁清理后再启动新进程，不能只重建页面或提前启动而被旧实例接收。启动失败明确报告。 |
| `src/lalc/agent_settings.py: load_settings / save_settings / effective_settings` | JSON 仅保存当前完整连接与各 provider 凭据引用；切换 provider 会用默认地址/模型覆盖读取结果 | 引入每 provider 完整配置存储及两侧选择/User 开关；首次成功保存时平稳迁移旧文件，保留所有已有凭据引用。继续复用配置校验、原子写入及 DPAPI，CLI 参数覆盖不回写；默认 CLI 开发用途读取 Developer 选用项。 |
| `src/lalc/developer_gui.py: SettingsPage / RepairPage.send`；`src/lalc/developer.py: DeveloperHost.secret`；`src/lalc/agent_repair.py: RepairConversation.run`；`src/lalc/agent_diagnostics.py: check_settings` | GUI 提前读取额度，后台另读 provider/密钥，轮次再读取有效设置；SettingsPage 使用私有草稿和保存按钮 | User 编辑面板复用已有连接字段与验证能力；两侧读写同一 provider 内容但分别选用。额度、有效设置和认证应在活动开始形成同一快照，后续不再读可变配置或凭据引用；下一轮读取新值。连接检查保持活动互斥，普通配置保存不被 Agent 活动禁用。 |

## 潜在风险及针对性验证

- 双侧覆盖风险已通过追加 grill 选择单一编辑入口：Developer GUI 打开期间 User Agent Settings 不可用/不可编辑，关闭后恢复，不建设字段合并/同字段冲突弹窗。切换前先提交、校验并保存 User 当前 Agent 输入，失败不打开 Developer；恢复后重新读取最新共享值，禁用的旧表单不回写。用两入口唤起及双窗口关闭测试验证该交接，而非只禁用按钮。
- 认证不同步风险已通过追加 grill 固定边界：每轮通过活动检查后、任何请求前一起固定完整设置与实际认证，读取/解密失败不发送请求；轮次内不重读设置/凭据文件。清除或替换只影响下一轮，当前轮次使用旧认证直到结束或停止。所有错误、日志、告警不得回显密钥，旧认证仍参与脱敏；用认证替身检查快照与删除行为，Windows 原生 DPAPI 另验。
- 追加要求：自行生成的错误不拼接密钥、认证头或带认证值的完整请求配置；第三方错误进入显示、复制详情和日志前沿用现有脱敏。轮次认证快照清理与对话级脱敏记录分开，不新增密钥清零机制；假设的第三方错误夹带认证值并非已观察到的泄露。Developer 设置交互也已追加改为即时保存，复用现有通用 GUI 控件与保存逻辑，保存失败不得默默丢弃输入。
- macOS 临时密钥仅在进程内，真正重启后需重新输入；不通过明文磁盘、命令行或重启参数转交。重载前提示这一既有约束，不能把 provider 配置持久化说成密钥也持久化。
- 页面 ID/任务 ID 冲突不能“后者覆盖前者”；需对冲突注册明确报错并排除歧义项，其他页仍可用。加载失败页的历史设置要保留；新页默认配置的校验失败也遵循阻止启动规则。
- 所有已加载业务页均参与运行前校验，包括未启用或不匹配任务对应页。错误页虽不加载，已成功加载页的提交错误也必须被捕获并显示，不能触发全局致命错误或继续运行旧配置。
- 保存失败可保证不开始执行/重启，不能假称多个页面的独立成功保存已全部回滚；本票不增加跨页面事务。测试失败时已保存数据仍完整，失败页不会被静默重置。
- Python Plan 作者仍可忽略次数自行调用 Task；支持声明是配置对接契约，并非运行许可沙箱。不扩为全局执行次数配额或源码行为证明。
- 重启交接已通过追加 grill 明确：整应用重载，任一侧活动或后台操作未结束都禁止；保存后依次清理双窗口/线程/服务、关闭通道并释放锁，再启动新实例并恢复原先打开的窗口。清理失败不启动新实例；新实例启动失败明确报错，由用户手动重启。不建设提前启动等待旧实例的机制。实现仍须验证顺序与失败分支；启动方式区分源码入口与未来冻结入口，#332 验证源码真实进程再启动和单实例释放，#334 才确认 Windows 打包版。

## 实施顺序与检查

1. 页面声明/发现与统一配置保存接口、稳定 ID 校验、失败隔离；支持列表的正式源码校验/读取。同步最小循环页、纯设置页和已发布 Plan/Task 示例，保留旧数据。
2. Dashboard 匹配行、双向告警及空列表告警、失焦/选择保存、运行前提交；验证跨 Manifest 共享、隐藏再恢复次数、配置深拷贝、保存失败不分配 Run。
3. 共享 provider 配置及迁移、User/Developer 独立选择、User 开关和状态、双侧共享编辑；迁移 GUI/CLI/诊断/Agent 调用方和凭据断言，固定轮次有效快照。User 开关显示“运行时 Agent 尚未接入”。
4. 整应用重启协议与保存检查，验证任一侧活动/后台操作禁止重载、保存或清理失败不启动新实例、释放单实例通道与锁后才启动、新实例启动失败明确报错、双窗口清理/恢复、重新扫描与告警清除条件。保留 #331 所属窗口清理和 Agent trial 内部授权例外。
5. 定向自动化覆盖上述边界及原有 GUI/Plan/凭据回归；涉及 Agent 接入后，仅显式选择相关 `pytest.mark.agent` 文件运行，不默认探测或调用真实模型。同步用户/开发者说明和 Stage 4 状态。

直接受影响测试：`tests/test_user_gui.py`、`test_developer_gui.py`、`test_python_plan.py`、`test_manifest.py`、`test_cli.py`、`test_agent_settings.py`、`test_agent_diagnostics.py`、`test_agent_repair.py`、`test_agent_repair_agent.py`；新增聚焦页面发现/保存/冲突/重载的测试。示例放在 `example/`，通过明确安装步骤复制到数据目录，不自动覆盖用户同名页。相关 `docs/agents/domain.md`、开发者 GUI/教程、Stage 4 规格/分阶段状态与实施证据随实现同步。

## 本轮已执行证据与验收边界

命令：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_user_gui.py tests/test_python_plan.py tests/test_agent_settings.py tests/test_agent_diagnostics.py`

结果：**82 passed, 2 skipped**。这是实现前基线，不是 #332 功能通过。两项跳过对应当前环境的真实本地 IPC 与 Windows 原生 DPAPI 限制；未启用 Agent 测试，未启动 pi 或真实模型。源码检查与该定向测试以外行为均未声称实测。

本票不加入双语/Release 信息面板（#333）、Windows 打包现场验收（#334）、完整游戏业务（Stage 5）、Runtime Agent（Stage 6）、模块热替换、自动表单、多套命名连接或不可信插件隔离。
