# Agent Repair — Developer Candidate 开发与修复

#330 按 [ADR 0029](adr/0029-use-explicit-candidate-edit-selection-and-continuous-developer-chat.md) 升级了 GUI/CLI 共用修复宿主。使用当前 Candidate，可编辑全部已有文件（`plan.json` 只读），按每条用户消息处理一轮并保留上下文；不会自动重建草稿、执行候选、Publish 或设置 Default。

## Developer GUI

安装已有 `gui`、`automation` extras 后运行 `uv run --frozen lalc`。普通执行不启动 pi；Agent 当前接入回归基线为 pi 1.4.0；其他版本也允许启动，版本不匹配会写 WARNING 日志，在 CLI 终端及 GUI 对话提示，兼容性须另行验证。

- **Capture**：主动截图后拖动框选，填写完整 Asset 逻辑名和 JSON tag 列表，查看裁剪预览并确认保存。保存使用同一张原图和同一区域；取消不写 Asset。已有图片预览不依赖游戏继续前台。坐标监测须手动刷新，显示客户区物理像素坐标及客户区外状态，失效后停止，等待再次刷新。监测不抢焦点，主动截图按原有规则恢复并置前游戏。Agent 的 `crop_asset` 仍每次新截图。
- **Runner**：刷新 Manifest 与入口，选择 Task Workflow、Subworkflow、Step 或 Automation Plan。前三种输入 JSON 对象，空白按 `{}`；Plan 选择已有配置文件。可暂停、恢复、取消，查看真实 Base ID、结果、Trace 和 Ledger。Runner 选择持久保存，只作用于后续执行，不改变 Default 或 Candidate；重启恢复后先刷新核验，不可加载时禁止启动，须重新选择或清除。
- **Agent Settings**：保存完整 Base URL、Model 和每轮请求上限，默认 20、最小 2。API Key 普通空输入保留原值；新输入覆盖，明确清除解除凭据。界面仅显示是否设置，不回读旧明文。Windows 使用当前用户 DPAPI；其他平台仅在本次 GUI 内存中保留输入的临时密钥。不会读写其他 pi 实例的个人配置。
- **Agent Repair**：从已有 Manifest 明确初始化或重建 Candidate；非空替换须确认，成功后开启新对话，失败保留原草稿及原对话。展示已有文件，无需选择编辑目标；Agent 可修改多个已有文件，`plan.json` 始终只读。支持纯文字和可选 PNG，每条消息启动一轮，最终回答后等待主动发送下一条。New Conversation 保留 Candidate 和固定 Diff 基线，旧日志保留。

实际 Diff 与 Validator 结果供人工审阅。Publish 重新校验并生成新的不可变 Manifest，不运行它，也不设置 Default；设置 Default 是另一个明确操作。GUI 不增加运行时审批流程。

Runner（包括暂停）、Agent 一轮处理、人工截图和保存由同一应用服务互斥。被动坐标和已有图片框选/预览可以继续。候选初始化、校验、发布也通过共享宿主活动检查。关闭时可返回继续，或取消并等待输入释放、日志保存和 pi 回收；切换页面不取消任务。

## CLI

```sh
uv run --frozen lalc init --from <saved-manifest-uuid>
# 明确确认替换现有草稿时才使用：
uv run --frozen lalc init --from <saved-manifest-uuid> --replace

# Agent 自行读取和修改所需已有文件，plan.json 只读
uv run --frozen lalc repair \
  --problem '问题、复现步骤和预期行为' \
  --image /absolute/path/to/optional.png

# 可通过消息要求只分析
uv run --frozen lalc repair --problem '请分析这个问题'

# 主动续聊，空行退出
uv run --frozen lalc repair --chat --problem '请修复所述问题'
```

CLI 的 `--image` 可省略，`--chat` 的下一条消息沿用当前对话。模型连接可由 `agent-config` 保存，也可用本次 `--base-url`、`--model`、`--max-requests` 覆盖，覆盖不回写。`--ask-api-key` 从终端临时输入，不接受明文参数。Windows 的 `secret-set <name>` 保存命名 DPAPI 密钥；`agent-config --secret-name <name>` 引用它，`--clear-secret` 解除引用。

旧 `repair <Component逻辑名>`、自动 Default 重建及必填图片不再是当前契约。`pi-probe` 仍是独立的图片/受限读取检查，不使用连续修复宿主，不作为普通回归附带运行。

## 权限、上下文和日志

按轮开始时的已有文件固定编辑范围，允许修改多个已有 Candidate 文件，包括候选 `manifest.json` 和 Recovery Rule。拒绝目录外路径、符号链接、新建、删除、`plan.json`。修复入口不区分候选或文件是否校验失败；失败结果保留在上下文。完整候选仍由既有 Validator 检查，Publish 校验失败不发布。

pi 继续使用原有 read/edit 工厂、受限 Asset 工具、动作契约查询和 Validator RPC；不提供终端、通用写入、删除、发布或设置 Default 工具。Candidate Python 校验会导入模块，Validator 不是操作系统沙箱；生成代码的副作用约束不能被描述为进程隔离保证。

每个对话在数据目录 `agent-interactions/<UTC日期>/<UUID4>/` 下独立留存：

- `events.jsonl`：实际模型/工具/校验和逐轮结束事件；预检事件也在相应轮目录保留。
- `baseline/`：该对话首次处理时固定的候选物化基线。
- `round-N/input.json`、可选 `input.png`：用户消息、附件、已有可编辑文件清单、基础 Manifest UUID、实际 pi 版本、已验证版本、非密钥配置与提示词。
- `round-N/request-K.json`：实际模型请求；连接预检消耗计入同一轮额度。
- `round-N/original/`、`final/`、`cumulative.diff`、`result.json`：真实候选快照、相对固定基线的累计 Diff、请求次数及结束原因。
- `context.json`、`tool-N.json` 和图片：保留消息、图片及工具结果；工具序号跨轮递增，不覆盖旧产物。

每轮回收 pi 进程，下一轮通过 pi context hook 显式带入此前消息、图片和工具结果，不重写模型工具循环。最终回答必须是严格 JSON，不剥离说明或代码块；解析或字段错误自动反馈具体错误，要求在同一会话重新生成 JSON，同时禁用剩余工具，避免重复修改。纠正请求计入本轮共享上限；合法回答、超限、服务错误或取消结束本轮，不自动开启下一轮。最终 JSON 中 `revise_success` 是模型报告，不能代替 Validator、人工审阅或游戏验收。

单次输出上限仅提供“使用服务端默认值”，应用不发送输出 token 上限参数，不再强制 4096。Settings 中的每条消息请求次数上限是另一项设置；流式输出不改变二者的含义。服务仍可能因其自身配置或资源限制截断输出，诊断记录为 `output_limit`。

Candidate 基线保存在工作目录的 `.candidate-baseline.json`，不进入 Candidate 或正式 Manifest。它保存初始化时的 UUID 和物化文件，跨 New Conversation、Default 变化和 Runner 选择不变；明确重建时才更新。源码内容标识仍是 SHA-256，Manifest 标识仍是 UUID。

## 验证与验收

普通回归默认跳过 Agent 测试：

```sh
QT_QPA_PLATFORM=offscreen uv run --frozen --extra gui --extra automation pytest -q
```

本需求的真实 pi + 本机 HTTP 替身检查必须显式运行：

```sh
QT_QPA_PLATFORM=offscreen uv run --frozen --extra gui --extra automation pytest \
  --run-agent-tests -q tests/test_agent_repair_agent.py tests/test_pi_probe.py
```

真模型检查需另外提供 `LALC_REPAIR_TEST_BASE_URL`、`LALC_REPAIR_TEST_MODEL`，再显式选择 `test_real_model_repairs_fixed_pure_case` 或 `test_real_model_inspects_assets_and_actions`。Windows 实际认证另需 `LALC_REPAIR_TEST_SECRET_NAME`，选择 `test_windows_saved_dpapi_secret_authenticates_real_model`；实时截图/重复裁剪需 `LALC_REPAIR_TEST_REGION`，选择 `test_windows_real_model_captures_and_reuses_crop`。这些测试均使用测试自有 Candidate/数据目录，缺少环境时跳过，不报告通过。

Windows GUI 仍须人工核对跨 DPI、窗口移动/尺寸变化、客户区外、窗口失效后手动刷新、焦点、框选像素和真实保存内容，以及 DPAPI 的 GUI 设置/清除、实际认证、Runner/Agent/手工截图互斥和关闭清理。offscreen 和平台替身不替代这些证据。#329 仍需完成 #328 真实案例的游戏前后对照。

历史 #325–#327 的单目标 CLI、Mac Gemma4 纯计算修复、Asset 工具与 Windows 原生 DPAPI 验证证据保留于 [实施切片](stage-3-implementation-slices.md)。其中已记录的 Windows DPAPI `1 passed in 2.43s` 只证明当时的原生存取及损坏密文检查；早期真模型结果不能代替本次多文件连续修复和 GUI 验收。


## 2026-10-24 已确认修订

2026-10-24 修订：取消 selected files 设置及 CLI 文件参数/`--all`。Agent 每轮可尝试修改 Candidate 内全部已有文件（含候选 `manifest.json`、Recovery Rule），`plan.json` 始终只读；不开放新建、删除、重命名、符号链接、目录外或正式源码写入。宿主按轮开始时的已有文件冻结边界，工具检查与结束快照共同执行约束。文件是否被 Manifest 引用、是否通过校验均不决定编辑权限；临时测试文件不新增警告，不自动登记 Component，新增 Component 接口留待后续。手动 Validate 在已有对话中立即写入 `context.json` 和事件日志，成功/失败在聊天区各只显示一次，失败保留详情入口；尚无对话时不隐式创建对话。此规则覆盖首次发送前、发送后和 New Conversation 后。


## 2026-10-24 Agent Repair 命名与请求额度

共享连续对话、文件编辑、素材工具及日志宿主统一命名为 `agent_repair.py`，使用指南为 `agent-repair.md`；CLI `repair` 命令不变，Component 缺陷种子仍保留原名称。GUI 独立显示对话轮次和本条消息内模型请求次数/上限，不随工具状态提示覆盖；新对话或重建 Candidate 后重置。每次实际请求前，在模型 system prompt 中注入当前对话轮次、当前请求序号、总请求上限及剩余次数，提示最后一次请求需给出最终回答，达到上限后停止，不再调用工具或继续请求。额度仍是每条用户消息的请求额度，预检与格式纠正均计入，下一条用户消息重新计数；宿主强制限制不依赖模型遵守提示。该动态提示进入实际请求日志，不把过时计数追加进长期对话历史。


### 命名与请求额度实施验证

模块及导入统一为 `agent_repair.py`，测试为 `test_agent_repair.py` / `test_agent_repair_agent.py`，指南为 `agent-repair.md`；CLI `repair` 和既有用户数据路径不变。GUI 显示独立的对话轮次和请求次数/上限，工具状态不覆盖计数，新对话和 Candidate 重建重置显示。每个实际 HTTP 请求的 system prompt 含最新计数、总额度和停止说明，包含预检及最终格式纠正；计数不追加进长期历史。

首次实际载荷测试发现 SDK 未保留上下文字段中的动态提示，已按失败即停流程改为最终载荷注入，单项重测通过后继续。相关普通检查 **89 passed**；全量普通回归 **304 passed, 30 skipped**（29 项 Agent 默认跳过、1 项 Windows DPAPI）；显式 Agent 回归 **25 passed, 4 skipped**，使用真实 pi + 本机 HTTP 替身，跳过 2 项真模型、1 项 Windows DPAPI 认证、1 项 Windows 现场截图。命令：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -x -ra`；`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -x --run-agent-tests tests/test_agent_repair_agent.py tests/test_pi_probe.py`。`git diff --check` 通过，未重新调用真实模型或执行 Windows 实机验收，#330 保持打开。
