# Stage 3 — Agent-assisted Component Repair

Status: accepted scope under [ADR 0025](adr/0025-validate-component-repair-before-runtime-agent-recovery.md), revised by [ADR 0028](adr/0028-bound-manual-agent-repair-with-live-observation-and-asset-additions.md); the #325 repair CLI is implemented and verified with automated checks and a Mac model-backed pure-computation case; later tools and Windows/game acceptance remain to be completed.

Tracking: [GitHub Issue #312](https://github.com/HSLix/LixAssistantLimbusCompany/issues/312). Confirmed implementation spec: [GitHub Issue #323](https://github.com/HSLix/LixAssistantLimbusCompany/issues/323).

已确认并发布的六个垂直步骤及其阻塞关系见 [Stage 3 Implementation Slices](stage-3-implementation-slices.md)。发布状态本身不表示实现或验收完成；#325 的实现与 Mac 真模型检查见 [单 Component 修复](component-repair.md)，Windows 与真实游戏验收仍属后续切片。
本阶段以尽快验证 Agent 自主修复已有 Component 的可行性为核心。通过独立 CLI 手动启动一次修复，提供已有 Component、游戏截图、异常信息与必要上下文；Agent 优先接入 pi 阅读源码、分析问题、执行局部修改，并调用现有 Validator，根据反馈继续调整。无需先实现 Runtime Agent Session、自动异常接管或运行时恢复。

2026-10-23 补充确认：前置接入验证 #324 仅在 CLI 展示图片、模型请求、受限读取与最终回答，不持久化交互日志或 pi 会话，也不重建或编辑 Developer Candidate。下文的完整修复日志要求从 #325 起实现；验证入口见 [pi 最小接入验证](pi-probe.md)。

## Input and repair boundary

- 人工指定已有 Component 的逻辑名，Stage 3 从 Default Manifest 固定本次修复的来源 Manifest / 源码版本，保留原始字节和缺陷种子，使每次评估可以从相同版本开始。没有 Default Manifest、无法加载或目标不在其中时报告错误，不启动 Agent，也不清空已有 `candidate/`；不改选其他历史 Manifest。运行中 Working Manifest 的衔接留给 Stage 3.5，本阶段的独立修复不接入正在运行的任务或 Plan。
- 输入包括人工提供的游戏截图、异常信息（可含 traceback / Trace）及复现步骤、预期行为等必要上下文；Agent 可通过两个专用工具重新截取当前游戏或从新截图裁剪新增 Asset。只有这两个工具需要连接游戏，不要求重建暂停的 Python 调用栈；游戏状态由开发者准备或操作。
- 首版只修改一个已有 Task Workflow、Subworkflow 或 Step 的完整源文件；可只读查看相关源码、现有 Asset、应用注册的 Trusted Actions 及签名/docstring。Trusted Action、Recovery Rule 的修改、新 Component、已有图片或旧哈希标签的修改、多组件编辑均不在本阶段范围。
- Agent 开始前，由 LALC 把选定 Manifest 的完整 Component / Recovery Rule 源码物化到当前工作目录下的 `candidate/`。目录不存在时新建，已存在时先清空内容；本决定显式替换此前“不覆盖现有 Developer Candidate”的约定，现有未发布草稿会被替换。Agent 的代码读取范围为该目录内的全部文件，仍只允许修改指定 Component，不能修改候选 Manifest 或其他源码。先确认来源 Manifest 可用再替换草稿；无可用 Manifest 时报告错误，不启动 Agent。
- 完整候选 Manifest 的其余映射保持基线内容，用于现有校验路径；按 ADR 0027，Asset Library 独立于 Manifest，不复制为候选映射。除受限的现场裁剪新增工具外，Asset 仅可只读访问。修复调用日志、原始源码对照和最终产物的留存不能依赖下次会被清空的 `candidate/`。
- SDK 负责一次 CLI 调用中的源码阅读、局部编辑及工具循环；不套用 Runtime Agent Session 的三种 Turn 结果、暂停 Step 续接和 `max_turns` 协议。SDK 选型、具体命令参数与日志格式由最小实现实验确定。
- Agent 仅能通过显式提供的工具读取候选代码、提供的截图/异常、相关 Asset 及 Trusted Action 签名/说明，修改指定 Component，调用现有 Validator，以及通过专用工具实时截图和现场裁剪新增 Asset。关闭框架自带的终端及通用文件写入能力；读取范围和写入目标由工具实现检查，不仅依赖提示词。Agent 不执行任意命令、点击/按键等游戏控制、修改其他源码或已有 Asset、发布 Manifest 或切换 Default。现有 Validator 会导入候选 Python，这些工具限制不构成操作系统安全沙箱。

### Asset inspection tools

Agent 通过三个专用只读工具查看共享 Asset Library，不获得任意目录读取能力：

1. 全局逻辑名树：把库内全部 Asset 逻辑名按层级转为文字树，供 Agent 发现名称，不批量加载图片。
2. 逻辑名目录查看：输入一个完整 Asset 逻辑名，列出该目录内所有文件名，并返回 `asset-tag.json` 内容。标签文件缺失时明确报告缺失，沿用 ADR 0027 的未配置标签按空列表处理，不自动创建或修正文件。
3. 图片查看：以完整逻辑名与完整 SHA-256 哈希标识图片；一次调用支持查看一张或多张。向模型返回实际图片内容，并逐张关联逻辑名与哈希，不只返回本机路径或文件名。

工具复用现有逻辑名校验、库内路径约束及图片哈希校验，不接受任意绝对路径、相对越界路径或哈希前缀，不提供 Asset 写入能力。多图请求的具体参数结构在接入实现中确定。

### Trusted Action inspection tool

提供一个只读工具，一次列出应用注册的全部 Trusted Actions，返回逻辑名、observe/control 分类、参数与返回类型及 docstring。内容从实际应用注册与现有签名/docstring 派生，不维护另一份手写动作说明。工具不暴露 Trusted Action 实现源码，不执行动作，也不能注册、替换或重新分类动作。

### Live screenshot and Asset crop tools

- 当前游戏截图：每次调用重新截取唯一 Target Window 的客户区，复用现有窗口与焦点检查，向模型返回实际图片和尺寸，并将本次截图保留在交互日志中。不执行点击、按键或候选代码，不把旧截图冒充当前截图。
- 现场裁剪新增 Asset：输入完整逻辑名、客户区像素区域及可选标签，每次重新截图后裁剪，不从保存的截图或前次观察裁剪。复用现有区域、图片和完整哈希校验，保存新图片及裁剪来源，返回实际裁剪图片、完整哈希、标签及新增/复用结果。工具不开放任意文件导入或输出路径。
- 同逻辑名同哈希已存在时直接复用图片，保留旧标签并明确返回已存在；即使请求提供不同标签也不覆盖。新增哈希按 ADR 0027 保存标签，未提供标签明确写入 `[]`；保留同目录其他哈希的原标签。此为 Agent 工具的限制，不修改开发者裁剪/标签管理工具整体替换标签的既定语义。
- 新 Asset 进入共享库，无需候选 Manifest 映射或 Publish，下一次读取/匹配即可看到。失败、取消、信息不足或人工拒绝不删除已新增的图片和记录，不引入资源回收流程。
- Mac 可用人工输入的截图验证修复流程，但不能以替身冒充 Windows 真实截图/裁剪验收。不支持实时工具的平台明确报告不可用，不静默回退为旧图。

### Framework selection

2026-10-23 确认以 pi 为首选，接入方向为 LALC Python CLI 通过 RPC 启动 pi 子进程，以 LALC 专用扩展提供上述受限工具。先在 macOS 验证最小接入，再固定同一 pi 版本供 macOS 和 Windows 使用；不自行重写模型与工具循环。#324 已以 pi 0.86.1 完成 Mac 图片/RPC/受限读取接入并经开发者复测；#325 继续复用该版本，已检查受限编辑、Validator 反馈、逐组 JSON 和完整修复日志，并通过真模型纯计算修复案例。Windows 与真实游戏行为验收仍待后续切片。

候选源码读取与修改优先复用 pi 的 `read` / `edit` 工具及其编辑、反馈能力，通过扩展或可替换的文件操作接口加上候选目录/指定文件的权限检查，不自行实现文本替换或编辑引擎。仅设置工作目录不是访问限制；必须核对实际读取/写入目标，拒绝越界及指向候选外部的链接。无需新增文件，不开放通用 `write` 或终端工具；具体所选版本的工厂/扩展接口在最小接入实验中确认。

### Model connection and secrets

- LALC 显式管理模型服务地址（包括协议、IP/主机名、端口和 API 基础路径）、模型标识及所需的 API key，不以用户预先维护 pi 的模型与认证配置为前提。首个接入目标是另一台设备上的 llama.cpp 服务。
- 使用指定模型前检查图片输入支持，不能只因配置标注支持图片就视为已验证；具体能力查询及实际请求验证在最小接入实验中确定。一次修复不自动切换模型或供应商，失败时保留候选与诊断日志。
- Windows 持久化密钥使用 DPAPI。密钥存储与模型连接配置分离，以命名引用关联；不限定只能保存模型 API key，未来其他密钥复用同一存储边界，但本阶段不预建其他业务集成。
- 密钥不进入 Agent 可读材料、模型上下文、调用日志或候选输出，不以明文写入 pi 的持久化认证/模型配置。运行时供模型客户端认证使用的传递方式须在接入实验中验证。macOS 首版开发环境临时输入密钥，仅在进程内存中使用，不持久化；每次启动重新提供。Windows 正式交付仍要求 DPAPI 持久化。

### Repair completion and interruption

- 2026-10-23 补充确认（#325）：以模型一轮交互的最终回答为一组；该轮中的源码读取、编辑、Validator 工具调用及反馈归入同组，不能按每次模型请求或工具调用单独定性。最终回答必须为 JSON，使用布尔字段 `revise_success` 区分“完成修订”（`true`）与“改不了”（`false`），并包含说明；中间的工具调用与反馈不携带该结束标记。不新增结束工具，不通过自然语言关键词猜测结果。每组保留 Agent 当时的原始报告，实际校验及后续行为验收独立记录，不反向改写该组评价。最终校验失败也应将实际反馈交回 Agent 继续修订；由此产生的新一轮另记一组，仍归属于同一次 CLI 修复调用并共用请求上限。这里的分组不是 Stage 3.5 的 Agent Turn 或 Runtime Agent Session。
- 最终回答不是合法 JSON、缺少 `revise_success` 或其值不是布尔值时，把具体格式错误反馈给模型纠正；不猜测或强制转换结果。纠正仍计入同一次 CLI 调用的模型请求上限，保留原始回答及格式错误。
- 每次修复的模型请求上限默认 20 次，可在启动时设置；它约束独立修复调用，不复用 Stage 3.5 Runtime Agent Session 的协议。
- 请求上限保存在 LALC 普通本地配置中，未配置时为 20；保存设置后供后续调用沿用，单次启动可临时覆盖而不修改已保存值。服务地址和模型标识也属于普通本地配置；每次修复开始时固定实际使用的上限并记入日志，密钥另行存储。
- Agent 一轮交互结束后，对其声称完成修订的最终候选源码再次调用现有 Validator；失败时反馈给 Agent 开始下一轮，受同一次调用的请求上限约束。通过仅表示候选符合执行契约，不代表游戏行为已修复；行为修复仍以人工真实游戏验收为准。
- 达到请求上限时结束并标记未完成；用户取消或模型服务报错时停止，不自动重启修复。上述路径均保留已有候选与日志，不将失败或中断报告为成功。
- 信息不足时，Agent 结束本次调用，最终回答明确说明缺少的截图、异常、复现信息或其他必要材料；结果记为未完成并保留候选和日志。不增加交互追问工具，不等待开发者回复或在本次调用中补充附件后续接。

## Validation and outputs

- 每次候选修改复用 `ManifestManager.validate()` / 现有 Validator 检查完整候选 Manifest，并把实际校验反馈交回 Agent；校验失败不冒充修复成功，可以继续修改。
- 校验不发布、不分配 Manifest ID、不切换 Working Manifest 或 Default Manifest。当前校验会导入候选 Python，不能把它描述为纯静态分析或安全沙箱；校验本身不构成游戏行为验证。
- 最终输出完整候选 Component 源码、相对原始版本的 Diff，以及实际验证结果。未通过校验、模型失败或中断时保留已有诊断与候选内容，明确说明未完成。
- 后续人工审阅并通过既有 Developer Candidate / `ManifestManager.publish()` 路径发布完整 Manifest；Agent CLI 不自动 Publish，也不修改 Default Manifest。设置 Default 仍是另一次显式开发者操作。

## One-call logging

一次 CLI 调用必须保留可关联的模型输入、工具操作和最终输出日志：

- Agent Interaction Log 从 Stage 3 起实现，存放在 LALC 本地数据目录，按日期和交互 ID 分目录；交互 ID 使用 UUID4，日期与精确时间单独记录。一次独立修复调用对应一个交互 ID，调用内的全部模型请求和工具操作归入同一记录。它不放在当前工作目录的 `candidate/` 下，也不因下一次修复清空 `candidate/` 而丢失。

- 实际发送的系统提示、上下文、截图内容或可持久访问的截图引用，以及每次模型请求/响应；多轮修订属于同一次 CLI 调用。
- 工具名称、参数、返回结果或异常，源码读取/修改、Diff 和每次 Validator 的反馈，按发生顺序记录。
- 最终候选源码、Diff、验证结果与完成/失败/中断状态及结束原因，并保留模型/SDK 标识、本次实际生效的非密钥配置和实际模型请求次数以解释本次结果；不记录认证密钥。

该日志就是独立修复调用的 Agent Interaction Log，不要求建立 Workflow Run、Execution Trace 或 Runtime Agent Session。Stage 3.5 可继续复用其记录内容；与运行中任务和 Runtime Agent Session 的关联在该阶段实现。Stage 3 不要求数据库、历史检索或管理界面。

## Acceptance

### 2026-10-29 前的 demo 交付边界

具体行为缺陷案例由开发者准备，选择容易人工复现且只需修改一个已有 Component 的问题，提供截图、异常信息、输入与预期行为。当前规划优先确定 Agent 修复能力及其限制，不以前置完成具体游戏案例为条件。真实模型读取源码、修改并调用现有 Validator；人工审阅并通过既有路径发布后，在真实游戏中验证修复前失败、修复后成功，保留两次运行及 Agent 修复调用的证据。确定性的 Trusted Action 替身可用于测试修复工具本身，不作为 Component 行为修复成功的验收证据；不为此实现游戏状态模拟或 Agent 离线行为检查工具。只修语法或仅通过 Validator 不算完成，Agent CLI 不自动运行游戏验收。目标是在 2026-10-29 前将 demo 交付 TA。

1. 保留至少一个可重复失败的已有 Component 原始版本、截图/异常、输入、复现步骤及预期行为；重复评估不覆盖缺陷种子。
2. 通过一次独立 CLI 调用，让真实模型读取源码、执行单文件修复并调用现有 Validator，产出完整源码、Diff、验证结果和完整调用日志；替身测试不能替代这一证据。
3. 人工审阅候选，复用现有发布和运行方式，在可复现条件下验证修复后的 Component 解决原问题，保存修复前失败与修复后成功的对照证据。涉及游戏交互时由人工另行发起实机验收；Agent CLI 不自动实机试运行。
4. 检查正式源码、已有 Manifest、已有图片及旧哈希标签、Default 选择未被修复调用改变，候选仅包含指定 Component 的源码差异；仅允许专用裁剪工具新增图片、对应的新哈希标签及来源记录。
5. Windows 上让真实模型调用实时截图和现场裁剪工具，核对模型实际收到图片、新 Asset 可读、重复裁剪复用且不覆盖旧标签，并留存对应交互日志。平台替身测试不替代这项验收。

## Deferred to Stage 3.5

完整 Runtime Agent Recovery、自动异常接管、Runtime Agent Session / Adapter / Context Builder 协调、监督运行与运行时审批、完整 Working Manifest 试运行和暂停 Step 续接、多组件编辑及相关能力演进，见 [Stage 3.5](stage-3.5-agent-runtime-step-recovery-and-maintenance.md)。该阶段可复用 Stage 3 的截图、受限 Asset 新增和交互日志，不再重复实现这些独立工具。完整依赖/反向查询分析和 Stagehand 研究也保留在该阶段，不作为首个修复案例的前置条件。新增目标的 Workflow Drafting、自主 Capability Expansion 与 Unattended Operation 仍无本次交付承诺。
