# Agent Repair — Developer Candidate 开发与修复

2026-10-27 Fluent GUI：User/Developer 已正式迁到完整 FluentWindow，固定页/外置页及三页开发工具使用 Fluent 导航；原有共享服务、即时保存、单一编辑入口和重载边界保持。当前操作与验证见[迁移记录](fluent-gui-migration.md)。


2026-10-27：#331 已替换 JSON Plan 与独立 Runner，使用并存 User/Developer 窗口及唯一 Python Plan；见[实施记录](stage-4-331-implementation.md)。本文保留的 Stage 3 历史验收只代表对应版本。

#330 按 [ADR 0029](adr/0029-use-explicit-candidate-edit-selection-and-continuous-developer-chat.md) 升级了 GUI/CLI 共用修复宿主，[ADR 0030](adr/0030-developer-policy-publish-and-trial-tools.md) 增加 Developer Policy 的自主发布和试运行。使用当前 Candidate，可编辑全部已有文件（含已有 Python Plan），按每条用户消息处理一轮并保留上下文；不自动重建草稿、不执行可变 Candidate、不设置 Default。Agent 可 Publish 后显式选择保存的 Manifest 进行试运行。

> Capture 窗口宽高与放大预览、专用源码新增工具、多图片附件及 Recovery Rule 示例已实现；Windows/真实游戏验收仍单列。完整边界见 [GUI 增量要求](developer-gui-design.md)。

## Developer GUI

安装已有 `gui`、`automation` extras 后运行 `uv run --frozen lalc --developer`；无参数启动 User Dashboard，可在 General Settings 打开 Developer。普通执行不启动 pi；Agent 当前接入回归基线为 pi 1.4.0；其他版本也允许启动，版本不匹配会写 WARNING 日志，在 CLI 终端及 GUI 对话提示，兼容性须另行验证。

- **Capture**：宽/高输入默认 1280×720 客户区物理像素，“重置窗口宽高”保持位置、层叠顺序和焦点，核对实际尺寸；窗口最小化时先恢复。截图预览鼠标附近原图像素通过 5× 小窗辅助定位，不改变框选与保存像素。主动截图后拖动框选，填写完整 Asset 逻辑名和逗号分隔标签，查看裁剪预览并确认保存。保存使用同一张原图和同一区域；取消不写 Asset。已有图片预览不依赖游戏继续前台。坐标监测须手动刷新，显示客户区物理像素坐标及客户区外状态，失效后停止，等待再次刷新。监测不抢焦点，主动截图按原有规则恢复并置前游戏。Agent 使用 `preview_crop` 新截图预览，再以 `crop_asset(preview_id)` 保存同一份像素。
- **Developer Selected Manifest**：窗口上方独立选择已保存版本，点击“试运行所选 Plan”运行其唯一不可变 Python Plan。不修改 Default 或 Candidate 来源；没有独立 Runner 页。Task/Subworkflow/Step 的直接启动仍可用 CLI 或 Agent trial_run。
- **Agent Settings**：User/Developer 复用同一控件，每 provider 保存一套完整设置，两侧分别选用；输入框失焦保存、选择项立即保存，无需保存按钮。Developer 打开时 User Agent 设置不可编辑，关闭时提交后交还编辑权。保存完整 Base URL、Model 和每轮请求上限，默认 20、最小 2。API Key 普通空输入保留原值；新输入覆盖，明确清除解除凭据。界面仅显示是否设置，不回读旧明文。Windows 使用当前用户 DPAPI；其他平台仅在本次 GUI 内存中保留输入的临时密钥。不会读写其他 pi 实例的个人配置。
- **Agent Repair**：从已有 Manifest 明确初始化或重建 Candidate；非空替换须确认，成功后开启新对话，失败保留原草稿及原对话。通过“打开 Agent 工作区”在系统文件管理器查看 Candidate，无需选择编辑目标；Agent 可修改多个已有文件，已有 Python Plan 可编辑，不开放任意文件创建。支持纯文字及任意数量的可选图片，每条消息启动一轮，最终回答后等待主动发送下一条。New Conversation 保留 Candidate 和固定 Diff 基线，旧日志保留。提问和最终回答按轮分块，工具默认显示可展开摘要；“查看累计 Diff”主动打开可伸缩滚动窗口，无常驻预览框。

实际 Diff 与 Validator 结果供人工审阅。Publish 重新校验并生成新的不可变 Manifest，不运行它，也不设置 Default；设置 Default 是另一个明确操作。GUI 不增加运行时审批流程。

User Run/Developer Trial（包括暂停）、Agent 一轮处理、人工截图和保存由同一应用服务互斥；Agent 所属的串行试运行是内部执行入口，仍阻止外部 Run/Capture。被动坐标和已有图片框选/预览可以继续。候选初始化、手动校验、发布也通过共享宿主活动检查。关闭时可返回继续，或取消并等待输入释放、日志保存和 pi 回收；切换页面不取消任务。

## CLI

```sh
uv run --frozen lalc init --from <saved-manifest-uuid>
# 明确确认替换现有草稿时才使用：
uv run --frozen lalc init --from <saved-manifest-uuid> --replace

# Agent 自行读取和修改所需已有文件，包括现有 Python Plan
uv run --frozen lalc repair \
  --problem '问题、复现步骤和预期行为' \
  --image /absolute/path/to/optional.png --image /absolute/path/to/another.jpg

# 可通过消息要求只分析
uv run --frozen lalc repair --problem '请分析这个问题'

# 主动续聊，空行退出
uv run --frozen lalc repair --chat --problem '请修复所述问题'
```

CLI 的 `--image` 可省略或重复提供，`--chat` 的下一条消息沿用当前对话。模型连接可由 `agent-config` 保存，也可用本次 `--base-url`、`--model`、`--max-requests` 覆盖，覆盖不回写。`--ask-api-key` 从终端临时输入，不接受明文参数。Windows 的 `secret-set <name>` 保存命名 DPAPI 密钥；`agent-config --secret-name <name>` 引用它，`--clear-secret` 解除引用。

旧 `repair <Component逻辑名>`、自动 Default 重建及必填图片不再是当前契约。`pi-probe` 仍是独立的图片/受限读取检查，不使用连续修复宿主，不作为普通回归附带运行。

## 新增源码与多图片

- `add_component(filename, logical_name, source)`：写入完整源码，登记到候选 Manifest 的 components。
- `add_recovery_rule(filename, logical_name, source)`：写入完整 detect/recover 源码，登记到 recovery_rules。教学用法见 [Recovery Rule 示例](../example/workflow/README.md)。

工具拒绝已有文件/逻辑名覆盖和越界，先按既有源码结构契约检查，不导入执行新源码；创建和登记在提交前失败或取消会回退。其他已有文件校验失败不一概禁止新增。新文件可在同一轮继续编辑，进入快照和累计 Diff；完整校验、Publish 和 Default 仍分别操作。取消工具请求时先等待工具线程回退/完成，再生成最终快照。

图片按实际内容由 Pillow 识别和校验，原始 MIME、字节和顺序独立留存，不转码、不设应用附件数量上限。预检携带整组图片，仅消耗一次模型请求；原图通过 context hook 进入 pi 上下文，绕开 RPC 图片转码及静默丢弃。下一轮沿用原始历史图片；格式纠正不重复添加附件。服务拒绝格式/载荷走正常诊断，不自动删图或重发。Asset Library 的 PNG 规则独立保留。

## 权限、上下文和日志

按轮开始时的已有文件固定编辑范围，允许修改多个已有 Candidate 文件，包括候选 `manifest.json` 和 Recovery Rule。拒绝目录外路径、符号链接、通用新建及删除文件；Asset 仅允许下述专用移除归档例外；成功通过专用新增工具创建的文件立即加入本轮编辑范围。修复入口不区分候选或文件是否校验失败；失败结果保留在上下文。完整候选仍由既有 Validator 检查，Publish 校验失败不发布。

pi 继续使用原有 read/edit 工厂、受限 Asset 工具、动作契约查询和 Validator RPC；Developer Policy 增加下述发布、试运行和日志工具，不提供终端、通用写入、删除或设置 Default 工具。Candidate Python 校验会导入模块，Validator 不是操作系统沙箱；生成代码的副作用约束不能被描述为进程隔离保证。

## Agent 素材预览与归档

[ADR 0031](adr/0031-preview-agent-crops-and-archive-removed-assets.md) 取代旧的 Agent 裁剪直接保存与禁止移除规则。Workflow 的 `observe.crop_asset` 不变。

- `game_screenshot()` 返回原始截图和独立的 40px 横纵坐标网格图，均在交互日志留存。
- `preview_crop(logical_name, region, threshold=0.9, tags=...)` 从当前游戏新截图，返回区域标线全图、干净裁剪图、同图匹配结果及 `preview_id`。结果含命中数、坐标、分数和中心点；不自动判断模板合格，不加入活跃库。
- `crop_asset(preview_id)` 保存本对话预览的相同原始像素、名称、区域和标签，不重新截图。预览可跨同一对话的轮次复用；New Conversation/重建 Candidate 后须重新预览。既有同名同哈希图片及标签仍保留。
- `remove_asset(logical_name, sha, reason)` 先验完整哈希及路径、新截当前原始画面，归档完成准备后移除活跃图片及同逻辑名的 SHA→Tags 关系；其他逻辑名不变。不需要 Publish，但会影响所有后续使用该 Asset 的匹配。

归档位于数据目录 `agent_removed_asset/<UTC时间-UUID>/`，包含原图、移除时的原始截图及 `record.json`（原名、SHA、Tags 快照、理由、时间、原路径和状态），结果返回记录 ID 与归档位置。截图/准备失败不移除；修改活跃数据中途发生普通失败或取消会回退。中断可能留下 `prepared` 记录及完整恢复数据，不提供自动恢复工具、GUI 或永久删除。网格/标线不会进入模板、模拟匹配或原始截图证据。

## 连接错误诊断

LALC 启动 pi 子进程时默认设置 `NODE_USE_SYSTEM_CA=1`，使支持该选项的 Node 运行环境同时使用当前系统信任的 CA，适用于系统已信任而 Node 默认未信任的网络 CA。不修改父进程或系统环境变量；用户显式设置的值及 `NODE_EXTRA_CA_CERTS` 继续保留。不关闭 TLS 证书校验。GUI/CLI 的 Agent 预检、正式请求及 pi-probe 共用此启动配置，更新并重启 LALC 后无需再逐次手动设置 PowerShell。

pi 请求的连接异常和响应流读取异常会分别记录 `lalc_transport_error`，含请求序号、地址（去掉查询及认证信息）、阶段、耗时及底层异常的 name/message/code/cause；不记录认证头或请求体，不自动重试。失败详情会关联该次请求的 transport 证据，下一请求开始即清除旧错误，避免跨请求误归因。预检与正式请求均覆盖；原有预检日志仍在 round-N/events.jsonl，正式交互日志位于对话根 events.jsonl。

旧记录中的 `Connection error.` 本身不能证明代理、TLS、服务端或工具定义是根因。更新后需在实际出错的 Windows 环境复现，根据新增错误码确定修复；本机 HTTP 替身检查只验证诊断链路。

## Developer Policy 开发调试循环（工具）

[ADR 0030](adr/0030-developer-policy-publish-and-trial-tools.md) 允许 Agent 在一次开发者消息中自主重复修改、校验、发布、试运行和读日志。此规则优先于旧有“Agent 不自动 Publish/运行”的说明，与 Stage 3.5 Runtime Policy 分开。

- `publish()`：完整校验并保存哈希源码及新的 Manifest UUID，返回 `manifest_id`，不改变 Default，不授予运行时永久批准。
- `trial_run(manifest_id, logical_name=..., inputs=...)`：试运行已保存版本中的 Task Workflow、Subworkflow 或 Step。Plan 使用 `trial_run(manifest_id, inputs={"task_repetitions": {}, "settings": {}})`，省略 logical_name，只加载该已发布 Manifest 的唯一 Python Plan；不接受文件路径。修改 Candidate 后先重新 Publish 才能运行新代码。
- 启动拒绝返回 `run_id: null`、原因及修正后重试的提示；实际启动的运行结果包含 Run ID、请求信息、真实结果及日志事件索引。正常返回只代表该入口契约满足，不能代替整个开发目标的验收。
- `list_runs(offset=0, limit=100)`：列出仍有 Trace 的 Run ID，按新到旧分页。
- `read_run_log(run_id, start_sequence=1, limit=100, evidence_id=...)`：分段读取日志，可选查看该日志引用的截图；记录已清理时明确报不可用。两个日志工具均只读，不做内容搜索。

GUI 试运行期间显示模态日志窗口，只含日志、暂停/恢复、停止；阻止操作主界面，显示时不主动抢游戏焦点。暂停/接管仅人工恢复。结束、报错或停止后窗口自动关闭，结果作为工具响应交给同轮 Agent，后续请求继续计入原额度；不会自动创建新一轮。停止只结束当前运行并建议总结等待，不禁用后续工具。取消本轮则停止试运行、等待输入释放及收尾，再结束 Agent。CLI 复用相同工具与结果，模态窗口仅用于 GUI。

每个对话在数据目录 `agent-interactions/<UTC日期>/<UUID4>/` 下独立留存：

- `events.jsonl`：实际模型/工具/校验和逐轮结束事件；预检事件也在相应轮目录保留。
- `baseline/`：该对话首次处理时固定的候选物化基线。
- `round-N/input.json`、可选 `input-序号.实际格式`：用户消息、附件、已有可编辑文件清单、基础 Manifest UUID、实际 pi 版本、已验证版本、非密钥配置与提示词。
- `round-N/request-K.json`：实际模型请求；连接预检消耗计入同一轮额度。
- `round-N/original/`、`final/`、`cumulative.diff`、`result.json`：真实候选快照、相对固定基线的累计 Diff、请求次数及结束原因。
- `context.json`、`tool-N.json` 和图片：保留消息、图片及工具结果；工具序号跨轮递增，不覆盖旧产物。

2026-10-28 起新对话采用 [ADR 0033](adr/0033-deduplicate-agent-logs-with-conversation-local-references.md) 的去重表示：log-format.json 标识格式，重复内容通过对话内相对路径和 SHA-256 引用保存，图片优先引用本对话已留存的原图。上述请求、事件、上下文和工具 JSON 可包含引用，完整信息、事件顺序、模型实际接收内容与 GUI 实时事件不变。复制整个对话目录即可按需展开；旧日志不迁移、不重写。本次不提供历史加载/展示界面。诊断命令与验证见[日志设计](agent-interaction-log-design.md)。

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


## 历史：2026-10-24 文件选择修订

2026-10-24 修订：取消 selected files 设置及 CLI 文件参数/`--all`。Agent 每轮可尝试修改 Candidate 内全部已有文件（含候选 `manifest.json`、Recovery Rule），已有 Python Plan 可编辑，不开放任意文件创建；不开放新建、删除、重命名、符号链接、目录外或正式源码写入。宿主按轮开始时的已有文件冻结边界，工具检查与结束快照共同执行约束。文件是否被 Manifest 引用、是否通过校验均不决定编辑权限；临时测试文件不新增警告，不自动登记 Component，新增 Component 接口留待后续。手动 Validate 在已有对话中立即写入 `context.json` 和事件日志，成功/失败在聊天区各只显示一次，失败保留详情入口；尚无对话时不隐式创建对话。此规则覆盖首次发送前、发送后和 New Conversation 后。


## 2026-10-25 固定上下文前缀与相对路径

本节替代下文历史记录中的“额度注入 system、计数不加入长期历史”。请求按固定规则、按时间追加的历史消息/工具调用及结果、本次额度提醒组织。system 不包含动态额度或 pi 自动添加的真实工作目录；文件路径相对于 Candidate 根目录，已有文件列表继续随用户消息提供。实际工作目录、路径解析及访问边界仍由宿主管理，不扩展为所有工具反馈的路径脱敏。

额度提醒作为宿主状态消息进入实际请求和对话历史，旧提醒原位保留，最新提醒有效；不触发新轮、不替换旧消息、不拆开一组工具调用与结果。每条用户消息重新计数，预检和格式纠正继续计入；预检消息不混入修复历史，格式纠正继续禁用工具，发送前的硬性上限保持有效。GUI/CLI 共用此行为，不新增设置。连接预检及 pi-probe 同样移除 system 中的工作目录，但保留各自原有的文件访问与计数规则。

实施验证：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --run-agent-tests -q -x tests/test_agent_repair_agent.py tests/test_pi_probe.py` 为 **43 passed, 4 skipped**。真实 pi 1.4.0 与本机 HTTP 替身验证固定 system 不含工作目录、末尾额度、预检隔离、同轮及跨轮消息前缀一致、DeepSeek reasoning/连续工具、原图、格式纠正与硬性上限。首次检查因沙箱禁止本机监听而未能建立替身服务，授权监听后重新运行得到上述结果。相关普通检查 `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_agent_repair.py tests/test_agent_settings.py tests/test_developer_gui.py` 为 **86 passed, 1 skipped**。未调用真实模型、测量 DeepSeek 实际缓存收益或执行 Windows 实机验收，跳过项不计通过。

## 历史：2026-10-24 Agent Repair 命名与请求额度

共享连续对话、文件编辑、素材工具及日志宿主统一命名为 `agent_repair.py`，使用指南为 `agent-repair.md`；CLI `repair` 命令不变，Component 缺陷种子仍保留原名称。GUI 独立显示对话轮次和本条消息内模型请求次数/上限，不随工具状态提示覆盖；新对话或重建 Candidate 后重置。每次实际请求前，在模型 system prompt 中注入当前对话轮次、当前请求序号、总请求上限及剩余次数，提示最后一次请求需给出最终回答，达到上限后停止，不再调用工具或继续请求。额度仍是每条用户消息的请求额度，预检与格式纠正均计入，下一条用户消息重新计数；宿主强制限制不依赖模型遵守提示。该动态提示进入实际请求日志，不把过时计数追加进长期对话历史。


### 命名与请求额度实施验证

模块及导入统一为 `agent_repair.py`，测试为 `test_agent_repair.py` / `test_agent_repair_agent.py`，指南为 `agent-repair.md`；CLI `repair` 和既有用户数据路径不变。GUI 显示独立的对话轮次和请求次数/上限，工具状态不覆盖计数，新对话和 Candidate 重建重置显示。每个实际 HTTP 请求的 system prompt 含最新计数、总额度和停止说明，包含预检及最终格式纠正；计数不追加进长期历史。

首次实际载荷测试发现 SDK 未保留上下文字段中的动态提示，已按失败即停流程改为最终载荷注入，单项重测通过后继续。相关普通检查 **89 passed**；全量普通回归 **304 passed, 30 skipped**（29 项 Agent 默认跳过、1 项 Windows DPAPI）；显式 Agent 回归 **25 passed, 4 skipped**，使用真实 pi + 本机 HTTP 替身，跳过 2 项真模型、1 项 Windows DPAPI 认证、1 项 Windows 现场截图。命令：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -x -ra`；`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -x --run-agent-tests tests/test_agent_repair_agent.py tests/test_pi_probe.py`。`git diff --check` 通过，未重新调用真实模型或执行 Windows 实机验收，#330 保持打开。


## 2026-10-24 当前增量实施与验证

- Capture 增加宽/高输入（默认 1280×720 客户区物理像素）及“重置窗口宽高”。Win32 按实测边框补偿调整，保持位置/层叠顺序/焦点，核对实际尺寸；最小化、窗口失效、Win32 调用失败及目标尺寸不符报错，受共享活动互斥约束，不覆盖旧截图。
- 框选提供 5× 原图像素放大窗及中心十字，跟随鼠标更新，在边缘补底色，离开或换图隐藏；鼠标事件穿透，不改变框选和保存像素。Capture 已做 offscreen 渲染检查，示意产物位于本次本机 `/tmp/lalc-capture-increment.png`，不计 Windows 实机证据。
- add_component / add_recovery_rule 接收 filename、logical_name、source；复用源码结构检查，不导入新源码。新建文件与 Manifest 登记以替换 Manifest 为提交点，失败/提交前取消会清理文件和新增目录。拒绝覆盖、跨分区重名、越界与符号链接；仅工具成功创建的文件可同轮继续编辑，进入快照和累计 Diff。取消时等待工具线程完成或回退再保存最终快照。
- GUI 可累计多选图片，按钮显示数量和文件路径，清除整组；CLI 重复 --image。新增 Pillow 到 automation 依赖及 uv.lock，按实际内容识别 MIME 并校验图片，不自建格式白名单、转码或设置附件数量上限；纯文字不导入可选图片解码依赖。预检整组只计一次请求。原图通过 context hook 注入，跳过 pi RPC 的转码/静默丢图；日志独立保存附件名称/类型/顺序/原字节，格式纠正及后续消息沿用原图。服务拒绝走既有错误路径，不自动删图或重发。
- 新增 example/workflow/（独立 Manifest、Step、规则和 README），复用生产 observe/control 动作及确定性恢复；覆盖无弹窗、唯一目标恢复、点击无效、目标不唯一与多规则匹配。不新增运行时 Agent 或专属 Trusted Action。

验证：

- 普通全量回归：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -x -ra`，**335 passed, 35 skipped**。跳过 34 项 Agent 测试及 1 项 Windows 原生 DPAPI。
- 显式 Agent 回归：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -x --run-agent-tests tests/test_agent_repair_agent.py tests/test_pi_probe.py`，**30 passed, 4 skipped**。通过项使用真实 pi + 本机 HTTP 替身；2 项真实模型、1 项 Windows DPAPI 认证、1 项 Windows 现场截图因环境条件跳过。
- 实际请求逐项验证 PNG/JPEG/WebP/GIF/BMP/TIFF/AVIF 的 MIME、数量及字节原样到达，预检、正常消息、格式纠正和跨轮历史均检查；服务 413 保留正文且仅发送一次。新增文件工具的同轮编辑、完整校验、快照及线程取消回退通过。
- 第一处失败为 pi 转码/丢弃附件，已停止并改为 context hook 原图注入，单项重测通过后继续；随后恢复示例测试误用输入事件元组末项统计点击，已更正并重测。未跳过失败项继续宣称成功。
- `git diff --check`、`uv lock --check --offline` 通过。新增 Pillow 后应同步依赖（例如 `uv sync --frozen --extra gui --extra automation`）。本机原有构建依赖已保留。

Windows 实机尺寸、DPI、焦点、放大定位及真实游戏恢复仍待独立验收，未重新调用真实模型。本记录不将替身/offscreen 当作实机通过，#330 保持打开，#329 继续承担真实游戏与最终交付验收。


## Agent Repair 对话区与审阅入口调整（已实现，验收单列）

- 移除“刷新文件”按钮和文件列表；新增“打开 Agent 工作区”，使用系统默认文件管理器打开当前 Candidate。目录不存在时提示先初始化，不隐式创建草稿。
- 删除常驻累计 Diff 预览框，保留“查看累计 Diff”。仅主动点击时读取现有固定基线下的累计 Diff，显示可拉伸、可滚动、只读且可复制的非阻塞弹窗；无修改显示“暂无修改”。每轮结束不自动打开弹窗。释放的纵向空间交给对话区。
- 对话按轮分组并分隔；开发者提问采用浅蓝背景和“你 · 第 N 轮”标识，Agent 最终回答采用独立背景/间距和“Agent · 第 N 轮”标识，均左对齐、可选中复制。Agent 文本支持 Markdown 标题、列表和代码块；身份不能只用颜色区分。
- 工具调用默认显示一行摘要与状态（执行中/等待完成确认/成功/失败），点击展开参数和结果。每次调用按 toolCallId 与所属轮次关联，合并宿主 repair_tool、validation 和 pi 的 tool_execution_start/end；相同工具的多次调用仍分别显示。不删除原始事件或改变送给模型的结果。
- 合并的是界面呈现，不将宿主执行成功误当成 pi 完成；pi 读取结果或扩展后续检查失败时，仍可将该调用更新为失败。read/edit 等只有 pi 事件的工具也须显示。对应失败在错误详情列表只保留一个可更新入口，底层诊断与日志保持完整。
- 工具正文默认收起，错误明确标识，保留现有日志、错误详情、校验、Publish、Default 入口。阅读历史时保留滚动位置，新增进度不强制拉到底部。
- 影响范围：RepairPage 布局与对话呈现，工具 RPC 中的调用 ID 传递，RepairTools 事件，GUI 和相关 Agent 契约测试。累计 Diff 继续由现有 DeveloperHost.diff 生成，Candidate 生命周期与实际编辑权限沿用现有决定。

验收覆盖文件管理器打开/缺目录、文件区与常驻 Diff 移除、手动打开可伸缩滚动 Diff 且回答结束不自动弹出、角色/轮次/Markdown 显示、详情展开收起、宿主/pi 同一次调用合并但重复调用不合并、工具失败仅一个详情入口、read/edit 保留、滚动位置与 New Conversation 清空，以及完整原始日志留存。Windows 实机呈现另列，普通回归不隐式调用模型。


## Agent Repair 对话区调整：实施与验证

- 已移除刷新文件、文件列表和常驻 Diff 框，主区域交给对话；新增系统默认文件管理器打开当前 Candidate 的按钮，缺目录时报错且不创建草稿。
- 原生 QTextBrowser 按轮分隔，你/Agent 使用文字身份、独立背景和间距，Agent 回答支持 Markdown。阅读历史保留滚动位置，本来在底部时才跟随新消息；New Conversation 清空呈现记录与工具索引。
- 宿主 repair_tool / validation 经 RPC 携带实际 toolCallId，与 pi start/end 按所属轮次及调用 ID 合并。默认一行状态，详情展开仅展示一份参数与结果；宿主已返回但 pi 未完成时显示等待确认，pi 后续失败仍更新为失败。相同名称的不同调用、不同轮次不会合并；read/edit 等直接工具仍有记录。
- 工具失败仅保留一个可更新的错误入口，同时保留宿主精确异常、pi 完成/错误及全部原始日志。界面合并不改变模型上下文、工具返回值或计数。
- Diff 按主动点击读取固定基线的当前累计内容，采用非阻塞可拉伸、可双向滚动、只读可复制的独立窗口；无修改显示“暂无修改”。回答结束不自动弹出。

检查结果：

- 相关普通测试：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -x tests/test_repair_chat.py tests/test_developer_gui.py tests/test_agent_diagnostics.py tests/test_repair_tools.py`，**85 passed**。
- 全量普通回归：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -x -ra`，**346 passed, 36 skipped**（35 项 Agent 默认跳过、1 项 Windows 原生 DPAPI）。
- 显式 Agent 回归：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -x --run-agent-tests tests/test_agent_repair_agent.py tests/test_pi_probe.py`，**31 passed, 4 skipped**。真实 pi + 本机 HTTP 替身验证两次同名工具的 ID 独立、宿主/pi 完成 ID 一致、validation 关联、read/edit 及原始日志保留，并完成既有编辑、图片、额度和取消回归。
- 已核对 offscreen 页面及 Diff 窗口渲染：本机 `/tmp/lalc-repair-chat.png`、`/tmp/lalc-repair-diff.png` 为示意内容的布局检查，不是实际模型运行证据。`git diff --check` 通过。

未重新调用真实模型，2 项真实模型、1 项 Windows DPAPI 认证、1 项 Windows 现场截图因环境条件跳过；Windows 实机交互/DPI 验收仍待独立完成。#330 保持打开，不将 offscreen/HTTP 替身当作 Windows 或真实游戏通过。


## DeepSeek and platform credentials — 2026-10-24

Agent Settings supports `llama.cpp` and `deepseek`. The llama.cpp form and request behavior remain
unchanged. Selecting DeepSeek defaults to `https://api.deepseek.com` and the only supported model,
`deepseek-flash`; additional controls select thinking enabled/disabled and effort `low/high/max`.
Defaults are enabled and `high`. Disabling thinking retains the chosen effort but disables its control.
The saved current connection remains one configuration; API Key references are independently retained
in `provider_secrets` by platform, never by model. Existing `secret_name` migrates to its original
platform. Switching, testing, sending, replacing or clearing uses only the selected platform's key.
Windows retains DPAPI storage; macOS retains separate platform keys only in the current GUI's memory,
never after restart. Empty API Key input preserves the selected platform's key; clear removes only it.

```bash
uv run lalc agent-config --provider deepseek --thinking --reasoning-effort high
# Windows: first save a named key using secret-set, then reference it:
uv run lalc agent-config --secret-name deepseek-service
# macOS: use the GUI's temporary platform key, or prompt in the CLI:
uv run lalc repair --problem "检查候选流程" --ask-api-key
```

CLI repair overrides `--provider`, `--thinking/--no-thinking` and `--reasoning-effort` affect only the
current invocation. Full API base paths remain unchanged (no automatic `/v1`). Standard DeepSeek model
list metadata is sufficient for availability checks; actual image preflight remains a real request and
counts toward the round's budget. pi explicitly uses DeepSeek's thinking format and preserves streamed
`reasoning_content` across tool calls and subsequent conversation rounds. Original tool permissions,
request caps, cancellation, disabled automatic retry and candidate review/Publish boundaries remain.

Workflow source may use `ctx.log("语义说明", screenshot=True)` to attach its current screenshot without
recapturing. Matched targets provide `centerxy` tuples for `control.click`; see the execution contract.

本次增量自动化验证（2026-10-24）：普通回归
`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -x` 为 **381 passed, 40 skipped**；
相关 Agent 回归
`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -x -ra --run-agent-tests tests/test_agent_repair_agent.py tests/test_pi_probe.py`
为 **35 passed, 4 skipped**。通过项使用真实 pi 1.4.0 + 本机 HTTP 替身，覆盖 DeepSeek 图片预检、
思考开关及 low/high/max 参数、连续工具调用和跨轮 reasoning_content；4 项跳过为 2 项真模型、
1 项 Windows DPAPI 真实认证及 1 项 Windows 游戏窗口。平台密钥加密替身检查不能代替 Windows
原生验收。普通回归同时覆盖中心元组与点击互斥、直接 Run/Plan 语义日志的原图内容与截图次数、
平台 Key 隔离、旧配置迁移及生成声明/Pyright。已检查 offscreen 的 llama.cpp/DeepSeek 设置页，
未重新调用真实模型或执行 Windows/真实游戏验收。探针的大图测试改为生成测试自有截图，不依赖
仓库外的个人图片。`git diff --check` 通过。

#332 的外置页面、配置交接、整应用重载及验证边界见[实施记录](stage-4-332-implementation.md)。CLI 未指定 provider 时使用 Developer 当前选用项；显式覆盖仍不回写。
