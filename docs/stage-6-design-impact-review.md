# Stage 6 设计影响审查

后续：开发者已授权实施，并逐项确认初始化来源、试运行权限、Default 写入失败、重启耗尽及旧版本修复迁移边界；落地与证据见[实施记录](stage-6-implementation.md)。以下源码差距保留为审查当时的快照。

日期：2026-11-11。输入为本轮逐项确认的[设计](stage-3.5-agent-runtime-step-recovery-and-maintenance.md#2026-11-11-设计讨论已确认边界)，架构取舍由 [ADR 0040](adr/0040-share-run-state-and-reuse-agent-sessions-for-runtime-repair.md)记录。审查包含源码与测试阅读、当前基线定向测试，以及经授权的文档修改；**未修改产品代码、提示词或随包 Skills，未创建 tickets**。

## 设计变化

| 原边界 | 已接受的替代边界 |
| --- | --- |
| 仅 Step 可恢复，Plan 自身错误终止 | Plan／Workflow／Step 分别恢复自己的失败，从入口重调，保留调用者；下层终止不冒充外层调度失败 |
| 配置经 Plan 参数与普通局部变量传递，禁止共享业务状态 | 一次 Run 内存 RunState，直接读写、失败不回滚；框架恢复计数只读，Agent 只有查看工具 |
| 固定 Plan 两参数 | 迁入 `ctx.run_state`，无旧签名兼容层；不可变旧源码不重写，须修改后重发 |
| 独立 Runtime Turn／恢复架构 | 同一现有 Repair Session，由程序组织来源、Prompt 和反馈，Run 后在 Developer GUI 接续 |
| 人工逐次批准、硬性旧新签名一致、Recovery Rule 不可改 | 自动校验／发布／执行；调用约定仅 Skill 建议；允许新增修改 Manifest Recovery Rule |
| 恢复最多一次／游戏每 Run 重启一次 | 连续规则恢复默认上限 10；Step 返回或 Agent 介入清零；共用恢复会话请求上限默认 50 |
| Default 仅人工选择 | User GUI 默认开启“运行成功后自动使用修复版本”；Plan 正常结束即采用最终 Working Manifest，不要求所有 Task 成功；取消／中断不切换 |
| 工具权限仅由入口和模式决定 | 同机制加历史检索总开关（默认开）和 Runtime 人工反馈开关（默认关），均下一轮生效 |

## 已确认的实现差距

### 1. RunState 与 Plan 契约需要一起迁移

**已确认**：`src/lalc/run_context.py:11` 仅持有 `_executor`，无 RunState。`runtime.py:225` 的 `prepare_inputs()` 要求 Plan 输入恰为两个配置字段并深复制；`manifest.py:29` 的空 Plan 模板与 `manifest.py:1173` 的 `_validate_execute_signature()` 强制旧签名。只添加 Context 属性会让新 Plan 仍被 Validator 拒绝，旧 Plan 仍通过加载。

调用路径：`gui.py:936` 收集页面／次数 → `ApplicationService.start_plan()`（`application.py:218`）→ `start()` 输入预检 → `WorkflowExecutor.prepare_inputs()` → `_invoke_component()` 再复制入参。CLI `__main__.py:159`、Developer `RepairTools.trial_run()` 的 Plan 分支也接旧输入。

需同时调整初始化与入口的职责、运行中共享对象、Validator／加载器、`__init__.py` 公开类型与 `stubgen.py:83` 生成声明。生成器当前只自动推导 RunContext 方法，若注解引用 RunState 还需正确导入类型。`API_VERSION=1`、Manifest schema 2 当前都不代表新接口，是否需要版本标识须明确，不能只改数字冒充迁移。

相关材料：`tests/test_python_plan.py:80` 断言原输入不变、返回配置局部变化；仍应保留启动数据隔离，新增共享 RunState 的可见性测试。所有 `tests/fixtures/*/plan.py`、`tests/runtime_support.py` 和 `manifest.EMPTY_PLAN` 是实际迁移点；现有已发布版本及 Sharing 导入数据不可自动改写。

### 2. 现有恢复封装只覆盖 Step，且强制旧约束

**已确认**：`runtime.py:290` 的 `call()` 对 Step 走 `_invoke_step()`，Subworkflow 走普通 `_invoke_component()`；`run()` 的非 Step 根入口也无恢复 wrapper。`_recover_step()`（635）最多重调一次，零匹配仍重调；`_replacement_problem()`（609）拒绝规则变化并强制旧参数／返回契约；`_try_manifest_choices()`（532）试跑成功后又按原返回注解校验。只放松 `_replacement_problem()` 仍会留下 599–600、669–670 的原返回类型校验，须与新版本自身输出校验区分。

必须按失败归属扩展入口 wrapper，保持普通参数校验和新版本自身输出校验，去除旧新契约必须相同的专门门槛。下层已耗尽／终止须穿过外层 wrapper 而不触发外层调度修复；当前所有普通错误都能成为 `ExecutionFailure`，新恢复边界不能只按异常类一概捕获。

`_call_task()`（317）已有 `status=failure` 结果封装和实际 Task 记录；`application.py:713` 汇总 Plan 的 `completed/interrupted`、items 及 `all_tasks_succeeded`。应复用，不能在 Plan 入口重试时清空已发生的 Task 结果或把 Agent 的成功声明当执行成功。

现有 `tests/test_recovery.py:294` 拒绝签名／返回变化，313 断言 Step 外错误无恢复，`tests/test_python_plan.py:118` 断言 Plan 错误结束；这些部分预期将被新设计替代，不能原封不动要求继续通过。保留现有调用者帧、后续调用使用新映射、失败不回滚和持久化失败不执行的测试。

### 3. Session 可复用，但活动锁、协议与请求额度不能原样套用

**已确认**：`developer_session.py:87` 的 `create()` 已有来源 Manifest、Candidate、固定基线和日志；`conversation()`／`restore()` 支持接续。`agent_history.py:56` 认可 `developer-sessions/<uuid>/log`，Developer GUI 也从同目录列 Session，支持融合方向，不需另建存储模型。

阻断路径：`RepairConversation.run()`（`agent_repair.py:268`）进入 `service.activity("Agent")`，而 `application.py:144` 明确拒绝任何仍在运行／暂停的 Run；父 Run 已持有系统游戏锁。Runtime 必须在父 Run 所属活动内串行让出和接回控制，不能调用 Developer 独立 trial 或简单移除共享互斥，也不能在等待 Agent 时持有阻止取消／UI反馈的锁。

`agent_repair.py:282–283` 每轮 `log.requests=0`，`pi_probe.ts:132` 初始化本轮计数，ROUND_REQUEST_LIMIT 仍是单轮值；直接反复调用现有 run() 会刷新额度。需复用现有轮次实现，但增加同一恢复会话剩余额度传递及实际消耗累计，不增加平行 Agent 框架。`final_answer()`（144）当前只识别 `revise_success/message`，它不是 Recheck 交接协议；应在同一工具循环提供终结式 Recheck，记录请求和 Runtime 的真实执行反馈。

### 4. 发布说明和结束时 Default 切换已有核心能力，但尚未接线

**已确认**：`manifest.py:147` 的 `publish()` 保存 `AdditionalMessage` 和时间，409 只校验说明是字符串，允许空；`repair_tools.py:298` 不检查本次修复说明。应复用字段，对 Runtime 发布落实简述要求，不强制所有旧数据补填，也不声称机器可验证文字说明的真实性。

`application.py:766` 已持久化 Working Manifest；`_worker()`（585）统一清理输入，`_complete()`（729）记录结束并释放锁，当前不会自动 `set_default()`。需在同一收尾流程按最终正常结束结果更新 active ID 对应的 Default，设置文案为“运行成功后自动使用修复版本”，默认开启，中英文翻译同步。自动采用版本的判定为 Plan 的 `status=completed`，不检查 `all_tasks_succeeded`；直接 Component 仍要求 `status=success`，且输入清理及必要记录成功。这与 `__main__.py:208` 现有 CLI 退出码语义不同，不应为复用而改动 CLI 成败判定。Plan 正常结束但含失败 Task 仍切换；取消、Plan 中断、直接 Component 失败及收尾故障不切换。不可取最新发布 ID 代替实际 active ID，不在 Default 写入成功前提示成功，不为重用而改变通用 Publish 行为。现有 GUI `gui.py:745/799` 已有手动 Default 选择可复用。本段按开发者反馈替代无论结果都切换的初稿。

### 5. 权限、全局开关和可继续 Session 需要一起接入

**已确认**：`agent_policy.py:16` 只接受 gui／cli 与 Construct／Repair，没有 Runtime 入口；BASE_TOOLS 包含 `remove_asset`、`trial_run` 和历史工具。`RepairTools.call()`（50）检查固定白名单，`agent_repair.py:273` 每轮刷新；`settings_snapshot()`（`agent_settings.py:146`）每轮读取设置。扩展入口策略和同一白名单即可，不得把整个 Developer Repair 工具集直接给 Runtime。

历史开关应覆盖查版本／查 Session／读历史详情及图片的三类历史工具，不能只隐藏搜索。保留当前会话续聊与新日志记录；当前 Run 诊断读取也不能误当跨 Session 历史而一并切断。Runtime 只读知识库不带 `knowledge_git`，不继承页面安装／构建或删除工具。新增 RunState 查看工具须返回快照，宿主拒绝直接写请求。读取资料、资产预览／裁剪、规则／普通源码编辑等工具需形成明确 Runtime 白名单。

`agent_settings.py:75` 读取后仅返回固定键，`_save_document()`（126）及 `save_selection()` 也是固定结构；只添加 GUI 控件可能在后续保存时丢失全局开关。新开关应与 provider profile 分开，覆盖双 GUI 交接保存、CLI 读取和旧配置缺省。默认 max_requests 当前为 20，改为 50 只补缺省，不覆盖已有值。

### 6. 游戏重启和证据归属有明确迁移影响

**已确认**：`runtime.py:397` 的 `_recover_game()` 用 `_automatic_restarts`／`game_restart_limit` 强制一次，`tests/test_game_restart.py:214` 明确断言第二次退出终止。应改为共同连续恢复计数，保留退出确认、无窗口时内置规则优先和不在无窗口状态检测业务规则。不能只删次数检查而留下无界重启循环。

当前 `ledger.py:44` 用 run_id／call_id 建记录，Trace 也有 parent_call_id；Agent 日志按 Session／轮次留存，但 `session.json` 当前只含身份、mode/source_manifest_id 等信息，没有父 Run 恢复关联。需在现有事实中补父 Run、原失败调用、每次 Recheck、轮次和 Manifest 的可追踪关联；记录一次逻辑 Task 与多次实际调用尝试的关系，避免重试被统计为用户新增任务或丢失已发生失败。Ledger 统计应保留实际累计事实，不能随用于限流的 RunState 计数清零而丢失历史。RunState 不做可恢复持久化，不等于禁止日志保留当时的只读工具快照。

## 待决定事项与潜在风险

以下不是已确认缺陷，也不阻止本次文档审查完成；相关决定影响实施票的验收条件。

1. **已确认：初始化与设置固定时点**：所有 Run 在启动边界初始化 RunState，包括直接 Task／Subworkflow／Step 和 Developer Trial，普通参数另传。连续恢复上限、自动使用修复版本选项在 Run 开始固定；历史／人工反馈按下一轮 Agent 生效。启动数据的具体接口与缺省处理属于实施落实，不恢复旧 Plan 参数兼容层。
2. **已确认：删除运行后永久批准**：不再保留独立 Capability Proposal／永久批准窗口或状态门槛。Validate、Publish、运行选择及正常结束后的 Default 更新保持分工；开发页面安装审批保留。ADR 0016 作为历史记录注明被替代。
3. **Recheck 中遇到新的下层失败**：例如正在修复 Task，Recheck 的 Task 调用一个 Step 又失败。已确认该 Step 负责自己的失败、不得递归新建 Agent Session；实施须证明同一 Session 能串行处理该现场，保留待返回调用者且共享额度。是否让父恢复目标等待子调用完成、如何记录关联，需用调用路径验证；不为此另造 Repair Process，必要时带具体场景反馈开发者。
4. **GUI 接续与现场互斥**：Run 结束前，Developer GUI 可能已看到同一个 Session。需要阻止人手在运行中并发改其 Candidate 或启动另一轮，不能靠“Session 同一套”推导并发安全；Run 结束后正常释放所有权。现有 candidate_lock 和父 Run 活动锁应复用。
5. **验收范围**：替身测试可以验证续栈／额度／权限／收尾；真实模型的工具交接、Windows 成品的焦点／暂停与提示、游戏现场恢复须分别验收。既有 Stage 5 本地通过或关闭 issue 都不能替代 Stage 6 证据。没有指定必须修复某一个业务，不把任意业务成功默认为已验收。
6. **已撤销：专用依赖／素材反向查询**：开发者最终取消专用素材反向引用工具及配套的 Publish 分析文件／查询补建方案；Component 调用图与正向引用也不纳入本阶段。现有 `asset_tree`／`asset_images`、`read_manifest`／`read_manifest_source` 及 Candidate 的 `read` 可供 Agent 自行定位引用，不新增索引或静态追踪实现，也不承诺穷尽动态引用。

## 文档处理与实施顺序

本次增加 ADR 0040 和本报告；现行 Stage 6 整合恢复图及状态，CONTEXT 改正 Step-only／独立 Runtime Session 等定义。旧词表及 ADR 0003 把 Recovery Point 当作保留的 Manifest；本轮实际指失败调用入口，现行术语已澄清，历史表述加说明。Stage 2、Stage 4／5、教程、Agent 用法、Skills 用法、历史及游戏重启用法增加明确的 Stage 6 目标与当前实现区分；相关旧 ADR 加局部替代指针，不抹去历史取舍和测试记录。**随包 Skills／Prompt 是实际产品输入，留到接口实现时同步修改，避免提前指导模型调用尚不存在的能力。**

后续依赖顺序（不是 tickets 拆分）：

1. 初始化／设置时点与删除永久批准已确认；专用依赖／素材反向查询及分析文件已取消，不再作为待决策或实施前置。
2. RunState／Plan 新入口与 Validator、声明、模板和夹具一并迁移，不增加旧接口分支。
3. 各层恢复 wrapper、统一规则计数与内置崩溃预算，保留普通 Task 失败／取消出口。
4. 同一 Session 的 Runtime 入口、终结式 Recheck、父 Run 活动交接、跨轮额度和只读工具／全局开关。
5. Run 结束 Default 更新与 GUI 提示、日志／Ledger 关联、Runtime 生成指导，然后分层验收。完成反馈修订后按 tracer-bullet 纵向切片讨论 tickets，不提前发布。

## 实施时需补充或更新的验证

| 范围／现有测试入口 | 必须覆盖的新增行为 |
| --- | --- |
| `test_python_plan.py`、`test_manifest.py`、`test_stubgen.py` | 新 Plan 签名通过、旧签名拒绝；初始配置与外部数据隔离，Run 内直接修改共享、失败保留、独立 Run 不继承；计数对业务代码只读 |
| `test_recovery.py`、`test_workflow_observability.py` | 各层只处理自身失败，原调用者不重复进入；新返回值不按旧注解强制拒绝；下层额度耗尽只形成一次 Task failure；Plan 重调保留实际任务记录 |
| `test_game_restart.py` | 达到上限恰好升级，不发生第 11 次连续成功恢复；Step 返回和 Agent 交接清零，发布不清零；多次独立崩溃不受旧一次限制；退出／绑定／重启失败边界保留 |
| `test_workbench.py`、`test_developer_session.py`、`test_agent_settings.py`、按需显式 Agent 测试 | 父 Run 能进入同一 Session，GUI 后续可接续；多轮总请求不刷新；Runtime 无删除／独立 trial／状态写工具；历史关时详情也拒绝、下一轮才变权限；两 GUI 保存不丢开关 |
| `test_user_gui.py`、`test_developer_policy.py`、`test_run_logs.py` | Plan completed 即按最终 active ID 更新 Default，包含最终失败 Task 也切换；取消／中断、直接 Component 失败、清理及必要记录故障不切换；直接 Component success 可切换；Default 写失败无成功提示；新设置文案与翻译、当前即 Default 的幂等行为；父 Run／轮次／Recheck 日志准确关联；Developer 独立 trial 仍可用 |

这些是后续验收要求，不声称现有测试已覆盖新行为。模型真实交接测试按仓库规则标记 agent，并与普通回归串行执行；Windows／游戏验收独立报告。

## 本次验证

执行 `.venv/bin/python -m pytest tests/test_recovery.py tests/test_python_plan.py tests/test_game_restart.py -q`：**75 passed**。这是当前旧实现的基线，不是新 Stage 6 功能通过；未开启 Agent 测试，未运行真实 pi／模型、Windows 或游戏。本次文档变更另做差异空白检查和本地相对链接核验。
