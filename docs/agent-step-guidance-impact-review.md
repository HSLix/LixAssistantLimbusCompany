# Agent Step 职责与开发指导影响审查

2026-11-06，开发者通过 grill-with-docs 逐项确认，最终确认以下实现范围。本文记录决策及实施前的只读影响审查，不代表真实模型或游戏验收。现有术语及架构边界不变，无需新增术语或 ADR。

## 已确认的设计

- 匹配层继续返回选定批次经 NMS 后的全部命中，保留中心点、分数、来源等字段；多个结果不自动判失败或无目标，也不要求对所有结果执行动作。业务 Step 决定如何使用，有歧义时记录 warning 语义的日志。
- Step 承担当前职责的状态识别、动作、完成确认及业务异常；恢复时重建判断，已完成则直接返回。业务完成不能仅以点击返回或固定等待结束为依据。观察、等待等基础 Step 只确认自身职责；完成证据不限定为模板，可以使用 OCR 或其他可靠状态。
- Task Workflow／Subworkflow 负责流程排布、参数传递及按 Step 结果进行分支、循环和汇总；不把游戏状态识别、业务成功判断或相应恢复异常移到 Workflow 层。
- 页面注册循环任务时，同步检查 Plan 的模块级字面量 `SUPPORTED_TASK_IDS`，使用页面 `TASK_ID`；配置通过 `settings[PAGE_ID]` 读取。安装页面、发布 Workflow、选择 Default 是独立操作。
- 点击指导在 Agent 了解 `ctx.action` 的动作契约入口先说明 `centerxy`，再说明完整 `x/y`，两者不可混用。优先复用匹配返回的中心点，不丢弃后重新计算；已有 Step 包装要先检查其签名，不能把 Action 参数直接套给不支持它的包装。开发者随后纠正指导层次：Core 和 SOP 不承载中心点等具体 API 用法；Core 只保留通用复用原则，SOP 指引按需读取契约。
- Plan 记录 Task 逻辑名、循环序号和 `status`；失败保留 `failure_code`／`failure_message`，成功记录有意义的 `output`。普通 Task 失败仍可继续调度；取消和不可恢复的环境故障仍向外传播。
- 本轮完善通用指导、契约说明和示例，不新增 Validator 强制业务校验，不改导出包、已发布 Manifest、Default 或运行时日志存储。

## 已确认的影响与证据

| 范围 | 检查结果与影响 |
| --- | --- |
| `src/lalc/sop.md`、`agent_prompts.py` | 默认指导补充 Step 职责及开发检查项，覆盖 Construct 与 Repair；具体动作参数归动作契约，Core／SOP 只保留通用复用与读取契约指导，页面指导仍不扩大权限。 |
| `src/lalc/pi_probe.ts` 的 `page_create`／`action_contracts` | 工具是 Agent 可直接读到的契约入口；页面描述未说明与 Plan 支持列表的接线，动作工具描述未突出中心点及全量匹配。需同步提示。 |
| `src/lalc/actions.py`、`repair_tools.py:action_contracts`、`stubgen.py` | 点击能力已存在；工具通过真实签名及 docstring 提供契约，声明通过 overload 顺序生成。调整说明与展示顺序，重新生成声明；不增加新调用形式。 |
| `src/lalc/assets.py:AssetLibrary.match` | 已返回完整结果及 `centerxy`，无需改变算法、NMS 或结果筛选；歧义的业务意义由 Step 决定。 |
| `manifest.py:plan_task_ids` → `gui.py:refresh_tasks` → `user_pages.py:task_inputs` | 已按页面与 Plan 任务 ID 交集提供循环次数。缺支持声明合法地视为空，不应通过改变 Validator 或自动修改不可变版本修复。 |
| `runtime.py:call/_call_task/_invoke_step` | 已具备结构化 Task 结果、Trace 与 Step 恢复边界。需指导作者把业务检查放对位置，不重写执行器或新增日志表。 |
| `example/workflow/plan.py`、`example/acceptance/plan.py` | 现有样例丢弃 `ctx.call` 返回结果；应示范成功和失败日志，并保留教学及故障演示行为。 |
| 执行契约、开发教程、页面与 Workflow 示例说明 | 现有规格已规定重要输入后观察及 Step 续跑；补充指导与现行规则的关系、页面 ID 和任务 ID 的区别，避免把基础动作样例误用为业务 Step。 |

## 检查与潜在风险

新增示例日志需通过实际 Plan 调用边界验证：失败字段保留，失败后仍执行下一次 Task。动作契约工具需确认先展示中心点且描述不丢字段；声明生成检查需覆盖新顺序且原 x/y 仍可用。SOP 是可编辑指导，不用逐句字符串测试冒充模型遵循性验证。

本轮不连接模型或操作游戏；普通回归默认跳过 Agent 测试。真实 Agent 是否遵循新指导、完成标识是否可靠、窗口布局和坐标适用范围仍需另行验收。导出包未含 Agent 历史，不能据此断言当时是否读取过最新契约。

## 实施与验证

已同步 Core／Construct 提醒、四段默认 SOP、页面创建与动作契约工具说明、Action docstring、点击签名及 overload 展示顺序、重新生成的 Context 声明、开发教程和页面／Workflow 示例说明。两个 Plan 样例读取实际 Task 返回并记录状态、成功输出或原始失败字段；原有调度及失败传播规则保持。已修正 Agent 用法中“三段 SOP 留空”的过时描述。导出包未修改。

后续按开发者纠正收窄：删除 Core 和 SOP 中的 centerxy／x/y 用法及手算中心点等具体提醒，保留在 `action_contracts` 工具说明、实际 Action 签名／docstring 和相关开发文档中。保留 SOP 中开发者新增的外部知识库参考指导。

此次指导层次修正后仅运行针对性检查：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_agent_prompts.py tests/test_repair_tools.py`：25 passed；未重复全量回归。以下全量结果属于修正前的上一轮验证。

- 针对性检查：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_agent_prompts.py tests/test_repair_tools.py tests/test_stubgen.py tests/test_windows_packaging.py`：50 passed；`tests/test_example_workflow.py` 单独运行：3 passed。包含生产动作签名及生成声明／Pyright、实际工具契约返回、两个 Plan 的成败日志及失败后继续调度。
- 默认回归：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`：924 passed，98 skipped，退出码 0。未添加 `--run-agent-tests`，跳过项不计通过。
- 单独运行 `tests/test_user_pages.py` 及首次组合针对性检查时，测试进度达到 100% 后进程以 139 退出，无正常汇总；用 `git archive HEAD` 的未修改源码／测试／示例快照重跑该单文件，同样复现。不能将这两次崩溃检查计为通过；其退出问题未在本轮修复。随后默认全量回归正常退出。
- `.venv/bin/python -m lalc generate-stubs` 已生成新声明，`git diff --check` 无格式错误。未运行真实模型、Windows 成品或游戏验收；通过项使用平台替身，不能证明 Agent 遵循性或真实业务完成标识可靠。
