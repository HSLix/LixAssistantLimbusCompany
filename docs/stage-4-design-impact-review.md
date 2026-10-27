# Stage 4 — Design Impact Review

2026-10-27：按 design-impact-review 对已确认 grill 结论进行只读源码/测试检查；开发者已同意结论。本文由随后授权的文档同步落盘，不表示已实施。接受设计见[Stage 4](stage-4-extensible-user-gui.md)，替代关系见 [ADR 0032](adr/0032-use-python-plans-and-coexisting-user-developer-guis.md)。

## 已确认的迁移缺口

| 范围 | 已检查证据 | 影响 |
|---|---|---|
| Manifest/调用 | manifest.py 的 ROLES、_validate_component_source、_validate_component_calls；runtime.py 的 call | 只识别原三角色，Task 不能被 ctx.call 调用；新增唯一 Plan 必须贯穿身份、哈希、完整校验、发布、加载与调用权限，不只加装饰器。 |
| 调度/结果 | application.py 的 start_plan、_run_plan、_fatal_result；runtime.py 的 run；ledger.py 的 observe | 旧 JSON 调度器持有预检、Ledger、取消和错误退出；迁移时保留 Task 失败继续与环境错误退出、同一 Working Manifest、实际调用结果及原始证据。 |
| 配置输入 | manifest.py 的 _input_annotation_allowed；runtime.py 的 _bind_and_normalize/_normalize_value | 正式输入注解不接受任意混合 JSON 字典。settings 需 Plan 边界的 JSON 规范化与独立复制，不全面放宽其他角色契约。 |
| Agent | developer.py 的 editable_files/add_source；agent_repair.py 的系统规则；pi_probe.ts 编辑检查；repair_tools.py 的 trial_run | 仍含 plan.json 只读和 JSON plan_path 执行；Python Plan 的 Candidate 编辑、提示词、工具参数、快照、完整校验与已发布试运行必须一起迁移。 |
| 窗口/互斥 | gui.py 的 run_gui、closeEvent、shutdown、render_state；application.py 的 activity；developer_gui.py 的 TrialDialog | 当前单窗口生命周期会停服务，统一 busy 会禁用页面；需应用级共享服务、工作所属窗口清理、细分控件禁用及窗口模态范围。活动门控可复用，保留 Agent 所属 trial 的授权例外。 |
| Agent 配置 | agent_settings.py 的 load_settings/save_settings；developer_gui.py 的 SettingsPage | 只持久化一份当前连接；provider 密钥分离不等于多套完整配置保存。需共享内容、独立选用及 User 开关，保留 DPAPI/临时密钥边界。 |
| GUI/打包 | gui.py 的固定四页；LALC.spec、packaging_entry.py、LALC.version；__main__.py 的启动分支 | 外置页、通知、双语、双入口和重载需要接入；现有打包 spike 不是新框架验证。旧四页/JSON 测试断言需要迁移而非直接删除核心回归。 |

以上为新设计相对旧实现的差距，不把尚未迁移的代码描述为回归缺陷。

## 实现风险与落实边界

- Python 动态调度不再具备旧 JSON 完整任务列表预检；保留源码/引用校验及实际调用输入校验，避免虚构静态覆盖保证。执行器保留调用汇总，不由业务 output 决定所有任务成功。
- 第二独立入口启动必须转交到已有应用，不能只在进程内加锁就宣称重复进程也互斥；只需要最小窗口唤起通道，不建立多进程 Runtime。
- 旧 Manifest 缺少唯一 Plan 时明确不兼容，通过重新发布迁移，不修改其原始数据。
- GUI i18n 与 game_language 分开；重载等待保存和清理，不留下活动或旧窗口对象。
- 最终 Windows 打包版需验证外置 Python 加载、翻译资源、通知、双窗口关闭/互斥及重启。真实平台结果尚未知，不以源码搜索或 offscreen 代替。

## 检查证据

本轮定向执行 test_plan、test_manifest、test_developer_gui、test_agent_settings：**85 passed，1 skipped**，约 1.59 秒。跳过项为 Windows 原生 DPAPI；没有运行 Agent/模型测试、pi-probe 或 Windows 打包验收。上述通过是旧实现基线，不证明 Stage 4 已适配。

后续按[垂直阶段](stage-4-implementation-slices.md)迁移：先完成 Python Plan 与双窗口执行闭环，再交付外置业务页面与共享 Agent 设置、双语信息界面，最后完成 Windows 成品验收。每阶段保留取消、证据、不可变源码及活动互斥回归。

## #331 补充评审（2026-10-27，开发者已确认）

本节保留实施前依据源码与 #331 进行的定向只读检查：评审当时仅记录已确认决策、修正术语并撰写报告，未修改运行代码或执行测试。开发者随后确认并授权实现；迁移差距的处理及新验证证据见[实施记录](stage-4-331-implementation.md)。上文 85 passed / 1 skipped 是前轮基线，不是本轮检查结果。

### 本轮确认的设计细化

- Plan 正常结束为 completed；all_tasks_succeeded 独立表达实际 Task 是否全部成功，output 保留业务返回，执行器拥有全部实际 Task 结果。成功→失败→成功表示完成但含失败；取消、无法继续的环境故障或 Plan 自身错误为 interrupted。
- 失焦、最小化、用户接管保留现有暂停/手动恢复及当前 Step 重入，暂停仍占用执行权限，不直接终止 Plan。
- 同一系统用户下 GUI/CLI 实际游戏活动跨进程互斥；重复 GUI 启动转交已有应用。查询、校验等不占用游戏的命令不因游戏占用一律拒绝；涉及同一 Candidate 的读写仍须遵守其冲突边界。
- 全新 Candidate 初始化即生成并登记空调度 plan.py 骨架；合法新版复制已有 Plan。旧 Candidate 由开发者明确补写，不自动转换旧 JSON，不改写旧不可变发布物，不增设 Agent 通用创建权限。
- CLI：正常完成且所有 Task 成功才返回 0；含失败或中断返回 1；空 Plan 正常返回为 0。

### 已确认的实现差距及影响

| 范围 | 当前证据 | #331 必须落实 |
|---|---|---|
| 身份与初始化 | manifest.py: ROLES、initialize_candidate、_validate_component_source、_input_annotation_allowed；__init__.py 的导出 | 增加正式 Plan 角色及唯一性检查，贯穿初始化、源码引用、发布、哈希加载；初始化登记空 Plan。混合 JSON 规范化只开放在 Plan 输入边界。旧数据报告不兼容而不重写。 |
| 调用与中断 | runtime.py: run、call、_invoke、trusted_action；control.py: InputSession.check | call 目前只允许 Task/Subworkflow 调用下层；_invoke 会将非 ExecutionFailure/TraceWriteError 异常包装成 execution_failed。新增 Plan→Task 结果边界时须保留明确的终止信号，不能仅凭通用 execution_failed 断言环境可继续，也不能把可手动恢复的暂停视作不可恢复故障。保持原 Step 恢复和动作权限。 |
| 结果与 Ledger | application.py: _run_plan、_fatal_result、_complete；ledger.py: observe、finish_task | 当前循环承担 Task 收尾、取消判断、输入释放失败中断和 items 汇总；迁到实际 Plan→Task 调用边界后须保留 Task 父子调用关系、每次调用独立记录及共享 Working Manifest。保留已完成结果，业务 output 不得覆盖统计。 |
| Agent 闭环 | developer.py: editable_files、initialize、add_source；agent_repair.py: SYSTEM 规则及轮次快照；repair_tools.py: trial_run；pi_probe.ts: 编辑边界和 trial_run 参数 | 当前工具仍读取 Candidate 内 JSON plan_path；改为已发布 Manifest 的唯一 Python Plan，Python/TypeScript 参数、提示词、权限及日志同步迁移。保留同一 Agent 活动内 trial 例外，不引入可变 Candidate 执行或外置页面写权限。 |
| 窗口与执行所有权 | gui.py: MainWindow.__init__、closeEvent、shutdown、render_state、run_gui；developer_gui.py: TrialDialog；application.py: activity、start、start_plan | 当前 MainWindow 自建 DeveloperHost、全局 busy 禁用页面，shutdown 停止共享服务；需单一应用持有服务/宿主，记录活动所属窗口，空闲窗口关闭不影响另一侧，最后窗口才退出。复用窗口模态试运行，分开普通配置和冲突操作。 |
| CLI 与跨进程入口 | __main__.py: _parser、_run、main；application.py: activity；packaging_entry.py | 当前 CLI 每次创建独立服务，互斥只在服务实例内；需 GUI 唤起转交与实际游戏活动跨进程排他。移除 run-plan 任意 JSON 路径，并同步退出码及调用方。打包入口需能识别 User/Developer 请求。 |
| 测试与样例 | tests/test_plan.py、test_cli.py、test_manifest.py、test_manifest_transition.py、test_developer_gui.py、test_agent_repair.py、test_agent_repair_agent.py；example/trusted-actions、tests/fixtures | 当前 test_plan 明确断言含失败的 completed 返回 CLI 0；test_cli 断言初始化 components 为空，GUI 断言固定四页，Agent 测试锁定 plan.json 只读。应迁移断言并保留原安全回归，不能只删除旧测试。同步所有需发布的完整 Manifest 夹具及教学样例。 |

以上为接受目标相对现实现的迁移差距，不作为已发生的回归缺陷。

### 潜在风险与验证要求

- 跨进程协调尚未实现，无法据现有线程锁推断其有效。用两个真实进程验证重复 GUI 唤起、GUI/CLI 争用、不同数据目录不能绕过同一用户的游戏排他，以及进程退出后的正常释放；不因增加锁重入而阻断 Agent 自己的 trial。
- Plan 动态调用不能保留 JSON 静态列表全量输入预检的保证。保留字面量引用校验及实际调用输入检查；用成功→失败→成功、参数快照独立复制、输入/返回契约失败证明边界。
- Python 执行栈增加 Plan 帧后，恢复、Ledger 和取消的关联结果尚未实测。定向验证普通失败后继续重复、取消不启动下一 Task、必要持久化/输入释放失败中断、Plan 自身报错保留先前结果、不可变源码篡改拒绝。
- 窗口焦点、输入释放、原生窗口模态及打包入口的 Windows 行为仍未知。offscreen 与进程级自动化可验证结构，但 Windows 打包现场验收仍属于 #334，不能提前报告通过。

### 实施顺序与范围

1. 正式 Plan 角色、初始化、完整校验/发布/加载、公共导出、Plan 输入边界及对应 Manifest 夹具。
2. Plan→Task 调用与结果记录、中断/暂停、Ledger/Trace、CLI 和 Developer Agent 发布后试运行；一起删除 JSON 执行路径，补齐相关测试和示例。
3. 应用级双窗口生命周期、活动所属与服务门控、GUI 唤起转交和跨进程排他；补 Dashboard/General Settings 最小壳、运行控制及持久通知，保留 Developer Selected 独立于 Default。
4. 普通回归；仅显式选择相关 Agent 集成文件执行 --run-agent-tests，分别记录 pi/HTTP 替身、真实模型、Windows/真实游戏的证据。同步 #331 文档和状态。

本票不实现 #332 的外置页面、次数列表及共享多套 Agent 设置，不实现 #333 的双语/Release 信息面板，也不实现 Stage 6 Runtime Agent。Plan 次数和配置输入契约在本票可验证，业务页面对接由 #332 完成。旧 Candidate 的显式迁移步骤须写入使用说明；不增加自动转换器或自动删除旧数据。
