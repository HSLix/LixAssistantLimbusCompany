# Stage 4 — Extensible User GUI and Python Plan

状态（2026-10-27）：grill 已结束，设计及影响审查结论已获开发者确认；#331 已在本地实现，后续 #332–#334 尚未实现，当前用法及验证边界见[实施记录](stage-4-331-implementation.md)。本文是 Stage 4 接受规格，阶段排期见[路线图](reconstruction-plan.md)，架构替代范围见 [ADR 0032](adr/0032-use-python-plans-and-coexisting-user-developer-guis.md)，影响证据见[影响审查](stage-4-design-impact-review.md)，实施拆分见[垂直阶段](stage-4-implementation-slices.md)。文档完成不等于源码或 Windows 打包版验收完成。

## 目标与非目标

搭建可扩展 User GUI 框架，用最小 Python 页面及 Plan 示例证明配置、保存、执行、暂停/继续/停止、页面扩展及双窗口互斥可行可用。重点是 User GUI，Developer GUI 轻量调整；完整游戏业务 Workflow 和内置 Agent 创建/编辑业务设置页属于 Stage 5。原 Stage 3.5 的完整 Runtime Agent Maintenance 延至 Stage 6；包括 Plan 失败后 Agent 评估、修复及试跑。Stage 4 不实现运行时自动修复、Python 热重载、自动表单、复杂插件生态、可视化 Workflow 编辑器、通用业务配置兼容层或自动更新器。

## User GUI

左侧导航、右侧页面；导航最上方固定 Dashboard（默认首页）、General Settings，随后为自动发现的业务设置页。

### Dashboard

左侧从上到下：

- 任务次数列表：可滚动且滚动条常驻。每行依次是启用勾选框、任务名称、次数（至少为 1 的正整数）、对应设置页跳转。未启用时传入次数为 0，保留用户已填次数，不必把显示值清零。只有主动注册循环任务的页面才出现在列表，纯设置页无需循环任务。
- 当前 Default Manifest 及选择小按钮：每次打开选择子窗口重新枚举可用 Manifest；User 的选择修改 Default。更改后刷新当前 Plan 的支持信息。不设额外 Plan 选择器，每 Manifest 使用其唯一 Plan。
- Agent 启用设置及状态、小设置按钮：按钮跳转 General Settings 的 Agent 部分。Stage 4 明确运行时 Agent 尚未接入，不能把可见开关描述为已实现自动修复。
- 开始运行：读取 Default，固定本次 Manifest、次数、页面配置及所需运行设置，然后执行当前 Manifest 的唯一 Python Plan。

右侧从上到下：最新 GitHub Release 的文字公告、沿用旧版的软件声明、本地/远端版本检测及更新按钮。只有远端版本较新才可进入更新操作；Stage 4 按钮文本带 TODO，点击仅提示尚未实现。比较版本不能使用字符串字典序；请求在后台、有超时，失败明确显示但不阻塞启动或任务运行。不下载或安装更新。版本数据使用统一来源，旧版声明从历史源码核对后复用，不能编造。

### General Settings

参考 Windows 官方设置，从上到下排列选项，包含：

- Agent 配置编辑、User 当前选用项及启用状态。
- 打开 Developer GUI：提示目标界面供开发者使用；已有窗口则激活，不重复创建，不关闭 User。
- 重新加载页面：保存配置并重启整个应用，重新扫描外置页面，恢复已保存设置；活动期间禁止重载。
- 语言：跟随系统（默认）、简体中文、English。系统为中文时跟随到简体中文，其余为英文。切换后保存并通过同一重启重载流程生效。GUI 语言与游戏识别语言是不同设置，不联动替换。

## 外置页面、任务注册与配置

设置页独立存放于明确的外置页面目录，不随 Manifest 发布；启动时自动发现，不修改 GUI 核心或维护第二份注册清单。每个模块声明稳定页面 ID、显示名、创建入口及可选循环任务 ID。仅支持手写 Python 页面，各页负责业务输入限制；Dashboard 只限制通用次数。不实现自动表单或跨版本业务配置兼容层。

Plan 显式声明支持的任务 ID，Dashboard 按任务 ID 与页面关联，不通过解析 ctx.call 代码猜支持项。Plan 不支持的项目仍显示 warning，本次不执行；不能把所有已安装页面直接等同于当前 Plan 的可执行任务。稳定任务 ID 不等于 Component 逻辑名，页面显示名/布局变化不改变它。注册冲突应明确报告，不能静默覆盖别页。

单个页面导入/创建失败则跳过该页，其他页和 Dashboard 可用；通过统一应用内持久通知说明页面及错误，失败页不提供可执行的任务注册。修复代码后重启重载。不把业务页异常提升为整个应用无法打开。

用户设置按稳定页面/任务 ID 保存到本地 LALC 数据目录，跨 Manifest 共用，退出后保留，切换版本不静默重置。启动时组装独立的 task_repetitions（任务 ID → 实际次数）和 settings（页面 ID → 配置字典）；纯通用页面配置也在 settings 内。Plan 不访问 GUI 对象、不在运行中重读配置文件。关闭当前运行窗口前，不将未结束的活动留在后台。

## Python Plan 执行契约

### 身份、源码与输入

每个 Manifest 必须各有且只有一份正式 Python Plan，按稳定逻辑名及精确内容哈希解析不可变源码。Plan 与 Task Workflow 分开，是新的正式执行角色；应用通过统一调用边界启动它，Plan 再通过 ctx.call 调用 Task。plan.py 是源码文件，不是任意路径执行接口。Task/Subworkflow/Step/Recovery Rule 不能反向调用 Plan，Plan 不直接调用下层 Step/Recovery Rule 或 control 动作绕过 Task 边界。

保留正式源码的完整校验、字面量调用目标、哈希验证、原始错误、取消及 Trace 边界；不把 Python Plan 当作绕过验证的脚本。Manifest 的唯一引用、角色标记等具体字段遵循现有形式，由第一个垂直阶段实现并用测试锁定，不引入多个可选 Plan。Plan 接收已确认的 task_repetitions 和 settings。settings 可包含 JSON 兼容的混合嵌套数据，需在 Plan 输入边界规范化并复制；不能用新增业务参数 schema 或全面放宽所有 Component 注解来代替。

旧 JSON Plan 的执行入口直接替换，不兼容、不自动转换、不自动删除旧数据，也不补写旧的不可变 Manifest。旧 Manifest 无合法唯一 Plan 时报告不兼容并通过显式重新发布迁移。CLI、示例、fixtures、GUI 与 Agent 工具同步迁移，不保留隐藏的 JSON 执行分支。

2026-10-27，#331 补充确认：全新初始化 Candidate 时由宿主生成并登记 `plan.py`，仅含通过正式校验所需的空调度入口，默认不调用 Task、返回 None；从合法新版 Manifest 初始化则复制已有 Plan。已有旧 Candidate 不自动改写，由开发者明确补写 Python Plan 并登记后校验、发布，不自动转换 plan.json。Developer Agent 仍只编辑已有 Plan，不新增通用创建文件权限。

### 返回、失败与记录

Plan→Task 的 ctx.call 返回结构化执行结果：成功含 status=success 与业务 output；普通失败含 status=failure、原始 failure_code/failure_message。Plan 无需捕获异常即可继续下一次调用，包括同一任务剩余重复次数。Task/Subworkflow 调用下层 Component 的既有业务返回/异常规则不变。

Stop/取消、输入释放失败、日志/Manifest/Ledger 持久化失败或其他无法继续的环境错误必须中断 Plan，不包装成可继续的普通 Task 失败。Plan 自身报错在 Stage 4 直接结束，保留已执行结果、Trace 与通知；不重放、不原地续接、不触发运行时 Agent。

2026-10-27，#331 补充确认：暂时失焦、最小化及用户接管沿用现有暂停/手动恢复机制，不直接判为 Plan 中断；暂停期间仍占用执行权限，手动恢复后重新进入当前 Step。取消、输入释放失败、必要记录无法保存或执行环境确认无法继续才中断整个 Plan；普通 Task 执行失败仍返回失败结果，允许 Plan 继续。

Plan 使用普通 Python 控制流；正常返回仍遵循 JSON 兼容返回契约，可返回 None。执行器记录全部实际 Task 调用及结果、维持一份 Working Manifest，并汇总遍历完成或中断的事实，不要求业务作者额外维护结果账本。正常返回和“每个 Task 都成功”分开表达；不要把某个业务 output 当作全部执行成功证明。当前 JSON Plan 的完整静态任务列表预检不再照搬到动态 Python 调度：正式源码/引用先校验，实际 Task 调用仍绑定校验输入；不以此新增通用业务配置验证机制。

2026-10-27，#331 补充确认：Plan 正常结束使用 `status=completed`，以独立的 `all_tasks_succeeded` 表达实际 Task 是否全部成功，并保留全部实际 Task 结果；Plan 业务返回保存于 `output`，不能覆盖执行器统计。成功→失败→成功后正常返回，显示“执行完成，含失败任务”，且 `all_tasks_succeeded=false`。取消、无法继续的环境故障或 Plan 自身错误使用 `status=interrupted`，保留此前结果。

同轮补充确认：CLI 仅在 Plan 正常完成且全部实际 Task 成功时返回退出码 0；正常完成但含失败 Task，或执行中断，均返回 1。空 Plan 正常返回时退出码为 0。这替代旧 CLI 仅依据 completed 返回 0 的行为。

Stage 6 才在 User Agent 已启用时，对 Plan 自身故障最终触发一次 Agent 评估和修复尝试，修复后可试运行；试跑起点、续接、预算和副作用另行讨论，不预设从任意故障行恢复。

### Developer Policy

允许内置 Developer Agent 编辑已有 Candidate Python Plan，沿用 Validate、Publish、明确选择已保存 Manifest 试运行及读取 Run 日志的闭环。运行的是发布后不可变 Plan，不执行可变 Candidate 文件，不改变 Default。新 Python Plan 不继承旧 plan.json 只读限制，但不因此开放任意新建/删除文件或外置页面目录写入。

## 双窗口与应用生命周期

提供 User/Developer 两个独立启动入口；默认 User。窗口同进程、同 Qt 事件循环，共享一个 ApplicationService 和 DeveloperHost。重复入口启动只请求现有应用打开/激活窗口，不能另建并发执行服务；实现最小的唤起转交即可，不建设多进程 Runtime。

2026-10-27，#331 补充确认：同一系统用户下，GUI 与独立 CLI 的实际游戏活动也必须跨进程互斥，冲突时 CLI 明确拒绝；不能只依赖单个服务内的门控。重复 GUI 启动转交已有应用打开或激活对应窗口。查询、校验等不占用游戏环境的命令仍可使用。

删除 Developer 独立 Runner 页，保留 Capture、Agent Settings、Agent Repair，保留底层 Runtime/CLI 和 Agent 独立试运行窗口。Developer 运行使用 Selected Manifest，独立于 User 的 Default 与 Candidate 基础版本。

- 同一时间只能有一个占用游戏环境/当前 Candidate 的活动；User Run（含暂停）期间禁止 Developer Agent、Capture 和冲突的 Candidate 操作；Developer 活动期间 User Start 被拒绝。
- Agent 所属独立试运行是同一授权活动的内部操作，保留现有例外，不因统一门控而把 Agent 自己的 trial_run 锁死。
- 活动限制由服务层强制，同时在 UI 禁用相关动作并解释原因。另一侧仍可编辑普通配置；当前活动只使用已固定快照。Agent 已回答、等待新消息不是活动占用。
- User 执行窗口阻止其主窗口操作，提供暂停/继续/停止；采用窗口所属的模态范围，避免 Developer 试运行导致 User 普通配置也无法操作。
- 空闲窗口可独立关闭；关闭活动所属窗口时确认停止当前工作，等待输入释放、日志及 Agent 清理后关闭；取消确认则保留窗口。关闭另一空闲窗口不停止活动；最后一个窗口关闭才退出服务。重载同样先完成保存与必要清理。

## 共享 Agent 设置

两侧共享完整配置内容（provider、地址、模型、请求额度及对应 Agent 选项），分别保存当前选用项；例如 User 用 DeepSeek、Developer 用 llama.cpp，编辑同一套配置后两侧切换读取到一致内容。只有 User 有运行时启用开关；Developer 默认启用，指不受 User 开关控制，仍需合法连接和开发者主动发起。

保留现有 provider 限制、认证传递、DPAPI、macOS 进程内临时密钥、不回显及脱敏日志。活动配置在开始时冻结；修改共享配置不能改变进行中的 Agent 轮次，不把共享改为两份会漂移的连接设置。

## 通知与验收

统一通知 API 显示应用内 toast 风格通知：运行结果和页面加载错误不自动消失，多条可同时保留，用户手动关闭；重启不恢复，详细历史沿用日志。不要求系统通知或额外通知中心。

必须在 Windows 打包版证明页面逻辑，不以源码启动/offscreen 测试代替。最小示例覆盖新增外置页无需改核心、自动发现、页面错误通知与隔离、设置保存与跨 Manifest 共用、任务支持 warning、参数快照进入 Plan、重复调用失败后继续、暂停/继续/Stop、双窗口互斥与独立关闭、语言/页面重启重载、Agent 两侧独立选用及信息面板离线行为。Windows DPAPI、实际焦点/接管等按证据范围单列；真实模型及完整游戏 Workflow 不作为页面逻辑通过的替身，也不扩为本阶段全业务验收。
