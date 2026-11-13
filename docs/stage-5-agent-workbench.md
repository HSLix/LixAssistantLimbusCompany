# Stage 5 — Agent 工作台

2026-11-11 Stage 6 接受复用同一 Repair Session、Candidate、对话与日志，由程序组织 active Manifest 和故障反馈，Run 后可在 Developer GUI 接续；Runtime 工具仍按入口授权。全模式历史检索总开关默认开启、下一轮生效；Runtime 只读知识库／Skills 已获准，人工反馈由 User GUI 默认关闭的开关控制。Stage 6 已完成本地接入，接口与验证边界见[实施记录](stage-6-implementation.md)。 目标见 [Stage 6](stage-3.5-agent-runtime-step-recovery-and-maintenance.md#2026-11-11-设计讨论已确认边界)、[ADR 0040](adr/0040-share-run-state-and-reuse-agent-sessions-for-runtime-repair.md)，影响见 [审查报告](stage-6-design-impact-review.md)。

2026-11-08 已接受页面多任务与人工确认启停设计：TASKS 逐项声明任务名称及次数开关，不兼容旧单任务声明；停用页面保留配置和 ID，占用不释放，覆盖安装不改变本机状态，启停重启后生效。仅 GUI Construct Agent 提供专用确认工具，不提供永久删除；Session 顶栏显示固定来源 Manifest。设计、影响及实施验证见[专项记录](page-tasks-and-availability-design-impact-review.md)。


本文为当前规格，依据 [ADR 0034](adr/0034-extend-developer-agent-with-reviewed-page-drafts.md) 及明确的后续修订维护；原决定和实施时点保留在[讨论记录](stage-5-2026-10-31-decisions.md)及相关实施记录。页面包由 ADR 0036 扩展，外部版本同步由 ADR 0038 替代旧 fetch-only 约定。页面三 Tab 依据[已确认的试用修订](stage-5-339-340-decisions.md#2026-11-02-试用反馈后的修订讨论)。

截至 2026-11-05，#335–#339 已关闭；#340 本地已实现、仍 OPEN，等待开发者 Windows 实验与另行确认。分项状态和验收边界见[当前状态](current-state.md)。关闭不等于 Windows 成品、真实模型或游戏验收。

## 目标与责任

构建工具与业务使用交替迭代：每个工具增量可先交给开发者使用，再根据反馈调整。业务选择、流程搭建、覆盖及业务验收由开发者负责，不指定首个业务，不以邮箱或旧业务全部覆盖作为工具交付前置。工具完成不等于游戏业务成功。

Developer GUI 统一为一个“Agent 工作台 / Agent Workbench”页面，保留 Construct / Repair 两种模式，复用模型接入、Agent Loop、工具实现、校验及日志，不复制两套核心。Construct 面向开发、扩展和修复 Workflow 及业务配置页；Repair 面向 Workflow / Asset 修复。二者均是开发能力，与 Stage 6 Runtime Repair 分开。

## 工作台与运行入口

#336 聊天交互重构已本地实施，当前界面使用分段模式选择、底部集成输入 / 取消 / 附件及 More 工具菜单；来源仅在新聊天上下文中显示，已开始会话使用只读模式标识。历史标题从首条实际用户消息本地提取，后续消息不自动覆盖，不调用模型。2026-11-11 增加持久重命名与彻底删除：悬停会话项右侧显示子设置，运行／试跑／等待反馈／取消清理期间统一禁用；删除前提示不可恢复，清除会话私有草稿、对话及历史检索记录，保留已发布版本、已安装页及共享素材。删除当前会话后回到空白新建聊天。完整规则与验证见[确认记录](session-management-decisions.md)及[影响审查](session-management-impact-review.md)。当前操作和验证见[实施记录](stage-5-336-chat-ui-implementation.md)，决定及边界见[对齐记录](stage-5-336-chat-ui-decisions.md)。

- 工作台包含可查看及恢复的历史 Session 侧栏、聊天主体和底部输入区；新建入口使用 New Chat，历史侧栏可折叠。保留图片 / Manifest 参考附件、工具进展、取消、诊断、累计 Diff、Validate 和 Publish 能力，按当前 Session 路由。
- 新建并选好 Construct / Repair 模式和来源后，首条用户消息提交前仍可调整两者；首次提交时固定模式、来源及其对应 Candidate / Diff 基线。开始对话后，更换模式或来源须新建 Session。打开历史 Session 显示其真实模式。
- 删除 Developer GUI 各页上方共用的 Manifest 选择、刷新和手动试运行区域，不移入工作台，不新增 Runner 页或“应用到 User GUI”快捷设置。普通启动继续使用 User GUI。
- 保留 Agent 的完整开发试运行闭环：修改、完整 Validate、Publish 后以明确已发布 Manifest ID 和输入调用 trial_run，再读取 Run 结果和日志。保留活动互斥、取消收尾及试运行日志窗口；删除人工入口不撤销 Agent 工具权限。
- 创建 Session 的来源选择和消息的 Manifest 参考附件选择继续存在，分别服务初始化和只读参考，不是运行版本选择；Publish 不自动修改 Default 或 Session 来源 / 固定基线。
- 旧 Developer Selected Manifest 不再作为工作台状态或运行依据；旧设置文件不迁移、不删除，停止读写其中已废弃的选择。
- 工作台和新增交互遵守现有启动语言及中英文本机制，Capture / Agent Settings 的既有职责不变。

## Developer Session 与 Candidate

一个 Developer Session 对应一段可继续的开发对话，拥有独立 Candidate、固定 Diff 基线、聊天、模式及页面草稿，关联完整 Agent Interaction Log。Session 是持久开发状态，日志是证据，二者不能混为一个目录快照或仅靠聊天文字推断状态。

### 创建与来源

- Construct 可从空白草稿（含最小 Python Plan）开始，或显式选择已发布 Manifest 作为扩展基线；Repair 必须选择已发布 Manifest 作为修复基线。
- 来源在首条用户消息提交时确定，每轮读取本 Session 的最新草稿；选择空白不能被现有隐式选用 Default 的初始化行为替代。创建失败不能损坏既有 Session 或留下一个被误报为可用的会话。
- 首条用户消息提交前，模式和来源属于可调整的准备状态，不视为重建已开始的 Session。开始对话后不提供“重建 Candidate”；换基线或从头开始就新建 Session，旧 Session 保留。新建 Session 不清空其他会话，不借用开发者手工 Candidate。
- Candidate 是准备、校验、发布完整 Manifest 的临时草稿台，不是长期正式源码仓库或运行中的 Working Manifest。“临时”不代表自动清空；草稿在本 Session 生命周期内持续保留。

### 保存、恢复与互斥

- Session 保存在 LALC 数据目录，聊天、Candidate、固定基线和模式在切换与重启后可恢复并继续。首版不提供 Session 删除入口，不自动清理；归档、清理留后续，持续磁盘占用是已知限制。
- Agent 执行、等待人工反馈或试运行期间禁止切换 / 新建 Session；当前聊天显示和取消入口可用，完成或取消收尾后再恢复切换。不提供多个 Session 后台并行执行。
- 同一 Session 的跨入口执行互斥；已有游戏活动互斥继续生效。工具结果、人工答复、校验及试运行证据绑定发起 Session，不跟随界面选择漂移。
- 2026-10-31 #335 补充确认：CLI 交互聊天空闲等待输入时释放 Session 锁，允许其他入口继续；每轮执行前重新加锁并读取最新持久状态，执行、工具调用及取消收尾期间保持持锁，锁竞争明确报告占用。
- 意外退出后保留已落盘内容，未完成轮次标为已中断。重启不自动重发模型请求、重跑工具、恢复试运行或沿用未完成的人工作业确认；开发者再次发消息后，Agent 检查文件和实际状态再继续。已完成的全局变更不自动回滚，尚未保存内容不保证恢复。
- 打开历史仅重建聊天、工具记录和错误详情，不把旧请求、工具调用或格式纠正显示为当前正在处理。空闲时状态栏与悬停详情读取该 Session 最新轮次的持久结果；无轮次时清空。实时人工等待、取消收尾和退出提示仍由当前作业驱动，恢复历史不弹出旧错误窗口，也不解除活动互斥。
- 恢复须保留消息、图片和工具结果的完整关联，不能向模型传入悬空工具调用；不得补造“执行成功”结果。具体中断记录和协议整理方式在实施中验证，不能演变为自动重放操作或裁剪历史的授权。
- 2026-10-31 #335 补充确认：未取得工具结果时只记录中断及结果未知，不据此认定操作未执行或成功，也不自动重放。开发者再次发送消息后，由 Agent 根据已有证据和实际状态判断如何继续；其判断不扩大当前入口的工具权限。
- 2026-10-31 #335 补充确认：Session 恢复聊天、附件和工具结果，不恢复仅存在内存中的现场裁剪预览 ID。重启后使用旧 ID 明确返回失效，由 Agent 判断是否重新截图、预览及保存；宿主不自动重做，已保存 Asset 保持不变。

### 历史按需呈现

打开 Developer Session 时，聊天区优先加载最新一轮并定位到底部；上滚到顶部时，后台按完整轮次逐轮补载更早内容，补载后保留当前阅读位置。短内容未出现滚动条时，向上滚动也可补载。工具记录及原始输出仍可展开；旧轮次的错误详情随该轮加载，不覆盖最新轮次状态。

界面只索引紧凑事件的位置，按需展开对应轮次的内容引用，每批事件合并后统一排版。浏览历史延后恢复模型上下文；下一次续聊、手动校验或发布前仍按既有流程完整恢复并校验，不裁剪持久日志或发给模型的历史，不重放工具。中断轮次仍记录结果未知。

### CLI 与手工开发

CLI Agent Repair 使用同一 Session 存储，可创建 Repair Session 或按 Session ID 继续；GUI 历史可打开 CLI 创建的 Repair Session。CLI 不运行 Construct，不暴露 GUI 弹窗工具；恢复时按当前入口重新计算权限，旧对话中的 GUI 工具记录不构成 CLI 授权。

项目根目录 Candidate 仅供开发者手工使用；手工初始化、编辑、校验、发布等命令保持原职责。成品手工 Candidate 仍按既有数据目录规则保存。GUI / CLI Agent 均不隐式接管、迁移或清空这份草稿。旧 Agent 日志原样保留，不自动转成可恢复 Session。

### 全局资源

Asset Library、已发布 Manifest、正式页面、业务配置及外部知识库仍全局共享。某 Session 新增 / 归档移除 Asset 会影响之后的匹配，安装页面会修改正式页面；切换 Session 不撤销这些变更。独立 Candidate 不代表整套环境隔离。页面预览的试填配置独立于正式配置。

## Prompt 与工具权限

2026-11-06 后续：详细流程和规范已迁入 Developer Skills，现行目录、只读加载及每轮固定语义见 [Skills 用法](agent-skills.md)，验证见[实施记录](agent-skills-implementation.md)。以下 SOP 描述保留历史时点。

2026-11-01 Prompt 重构：Core / Mode / 模式 SOP 及实际启用工具概览分开组织，宿主上下文与用户需求通过用户消息中的独立标签区分。每条消息执行时读取随程序发布的单一 `sop.md`，按固定模式选择 Construct + Asset 或 Repair + Asset，轮内固定，下一轮及历史续聊读取新内容。SOP 是默认指导，不改变程序权限；空正文合法，缺失或损坏在发出模型请求前报错。填写方式及输出语义见 [Agent 指南](agent-repair.md#prompt-与-skills)，决定及影响见 [审查报告](agent-prompt-impact-review.md)，验证见 [实施记录](agent-prompt-implementation.md)。


每种模式有自己的初始 Prompt 和工具白名单：Construct 遵循开发者指示开发 Workflow 和页面，Repair 聚焦修复。实际权限取模式白名单与当前入口能力的交集；pi 工具声明和宿主实际分发都必须执行，不只在 Prompt 中限制。共享核心不意味着任意目录读写或共享全部工具。

| 能力 | GUI Repair | GUI Construct | CLI Repair |
| --- | --- | --- | --- |
| 本 Session Candidate 读 / 编辑、专用 Component / Recovery Rule 新增、完整校验 | 是 | 是 | 是 |
| Asset / Trusted Action 契约检查、游戏截图、专用 crop / 归档 remove_asset | 是 | 是 | 是 |
| Publish、显式已发布版本 trial_run、Run 日志 | 是 | 是 | 是 |
| 任意已发布 Manifest 结构及登记源码只读查看 | 是 | 是 | 是 |
| 外部知识库只读检索及受控 Git | 是 | 是 | 否 |
| 请求人工答复或操作并等待反馈 | 是 | 是 | 否 |
| 页面草稿构建、当前正式页受控只读访问、预览及人工版本确认安装流程 | 否 | 是 | 否 |

Candidate Python Plan、Task Workflow、Subworkflow、Step、Recovery Rule 的调用层级与专用新增路径保持；正式源码不可变、完整 Validate、Publish 后才可执行、不自动设置 Default 的边界保持。read 的新增根目录不能自动扩大 edit。正式页面只通过人工确认安装流程写入，不加入通用编辑范围。保留认证、日志脱敏、Trusted Action 和用户取消要求；无通用终端、任意文件创建 / 删除、任意外部程序执行权限。

2026-10-31 #336 实施前补充确认：两种模式分别定义初始 Prompt 和白名单，本票已实现工具集合可以相同；Repair 保留新增修复所需 Component / Recovery Rule 的能力。后续知识库、人工反馈及页面工具分别在 #337 / #338 / #339 实现后接入，页面构建仅 Construct，未实现工具不提前暴露。

Stage 6 Runtime Repair 不提供删除工具或删除权限，不整体继承上述开发工具集；任意已发布 Manifest 内容只读查看已单独获准纳入其白名单，见下节。其人工交互只在有人监督 / 值守时开放，无人值守时不开放；值守来源、变化及已有等待如何处理留 Stage 6。其余 Recovery Rule 修改、生效、Working Manifest / Recheck 等见 [Stage 6 TODO](stage-3.5-agent-runtime-step-recovery-and-maintenance.md#stage-6-todo-repair-integration)，不为 Stage 5 放宽运行时替换检查。

## 已发布 Manifest 参考附件与只读查看

### 聊天附件托盘

2026-11-13：待发送附件位于输入框内部、正文上方；已发送附件位于对应用户消息正文上方，重开 Session 和补载旧轮次时恢复。图片显示缩略图并可点击打开只读大图预览；Manifest 参考卡片显示 UUID 前八位，完整 UUID 和长文件名通过悬停提示提供。显示缩写不改变实际引用标识。

附件默认显示一行，随可用宽度调整；超出部分以“+N · 展开全部”呈现。展开后最多两行高度，更多附件在托盘内滚动，可收起；折叠不减少实际提交的附件。只为可见行及滚动余量创建卡片，不新增附件数量限制。待发送卡片悬停或键盘聚焦时出现 ×，仅移除该待发送条目；历史附件只读，缺失或损坏图片显示不可用占位。图片预览按窗口大小保持比例适配。

设计取舍、实现与验证边界见[聊天附件托盘影响审查](chat-attachment-tray-impact-review.md)。

### 参考权限

2026-10-31 补充确认，纳入 #336；[讨论记录](stage-5-manifest-reference-decisions.md)与[专项影响审查](stage-5-manifest-reference-impact-review.md)保留设计及证据。

GUI 附件可选择一个或多个已发布 Manifest，参考整个版本还是其中部分内容由开发者直接在聊天消息说明，例如某版本的 Workflow 或 Recovery Rules；首版不做逐 Component 树形勾选。Manifest ID 及参考提示作为消息信息随 Session 上下文保存 / 恢复，不因发送附件把整个版本源码一次性注入模型上下文。

附件是参考提示，不是访问授权清单。GUI Construct / Repair、CLI Repair 均可通过专用只读工具自行查阅任意已发布 Manifest，无须先附加；不维护按附件 / Session 的 Manifest 访问白名单或撤销机制。按需列出已发布版本、查看 Manifest 结构及其登记源码，返回明确 Manifest ID、分区 / 逻辑名、Component ID 和所读位置，避免混淆同名 Component 的不同版本；输出截断明确并可继续读取。不存在、损坏或源码身份校验失败时如实报错，不静默换版本。

查看只读取数据与源码，不导入或执行参考 Python，不能直接使用会导入模块的执行加载路径。按已发布 Manifest 的成员关系解析源码并核验内容哈希，限定真实路径与符号链接，不允许任意文件读取，也不扩大当前 Candidate 的 edit 权限。该工具不提供创建、编辑、删除、复制落盘或执行入口；Agent 如需借鉴逻辑，仍通过当前模式已有的 Candidate 编辑 / 新增路径完成开发。

附加或查看不改变当前 Candidate、来源 / 固定基线、Default 或运行中的 Working Manifest，不启动试运行或切换执行版本。已有 trial_run 权限仍是另一条显式执行路径，不能把查看权限当作执行授权。

Stage 6 已确定将同一“任意已发布 Manifest 内容只读查看”能力纳入 Runtime Repair 工具白名单，不受有人 / 无人值守限制；本阶段提供可复用只读核心及 GUI / CLI 工具，Runtime 接入仍在 Stage 6，不在 #336 提前实现运行时恢复。此授权不包括工作台 GUI 附件界面、其他开发工具或修改 / 切换 Working Manifest。

## 外部知识与 Git 内容的版本语义

知识库位于 LALC 数据目录，支持 Git 仓库、普通文档和图片。GUI 工作台两种模式均提供文件夹入口和只读检索 / 查看；开发者准备初始资料，不开放 Agent clone、外部项目执行或参考资料编辑。外部内容是参考材料，不是指令或权限来源，采用逻辑仍需遵守 LALC 契约，复用前核对实际许可证；未指定外部项目为既定来源。

2026-11-01 #337 细化：固定目录为 `data_root/knowledge`，GUI 点击打开时缺失则创建空目录，不要求先开始 Session，不授予 Agent 写权限。列目录不触发 fetch；读取内容、内容检索及 Git 历史访问触发，跨库检索按实际参与仓库分别处理。首版读取 UTF-8 文本、查看原图，不做资料图片 OCR；PDF / Word 等仅列出并提示需转换。使用系统 Git，不捆绑或自动安装，不可用则跳过、记日志、继续读取本地，不能声称已检查远端。认证由开发者预先配置为非交互，fetch 最长 30 秒；禁用内容查看中的非必要转换器，不建立全面 Git 配置审查机制。详见[专项决定](stage-5-337-decisions.md)及[当前工具与限制](stage-5-337-implementation.md)。

当前同步与检索遵循 [ADR 0038](adr/0038-use-versioned-reference-search-and-reusable-agent-processes.md) 和[外部搜索用法](external-code-search.md)：

- 列目录不触发同步；每轮首次内容访问按实际参与仓库尝试一次完整更新，可显式 fetch，不自动重试。
- 在独立 B 副本 fetch 明确 upstream、reset、建索引并查询验证，成功才切换文件／索引指针。磁盘不足、fetch 或构建失败保留可用 A 并报告，不把失败当作零命中或最新版本。
- 工具返回明确提交、可用版本及同步结果；没有 upstream 或 detached HEAD 不猜分支。原 clone 是发现与初次准备入口，默认读取可用版本，不用原 clone 的 HEAD 推断 Agent 所读版本。
- Agent 的 Git 接口仍限受控 fetch／show／log／diff，无通用终端、参考资料编辑或项目执行权限。内部 reset 仅用于构建受控参考副本；路径、链接、Git 元数据、参数与非交互认证边界保持。
- 字面工具为 `knowledge_search_literal`，新增向量＋BM25 的 `knowledge_search_hybrid`；缺索引保留字面搜索和读取，混合搜索明确不可用。哈希绑定读取拒绝搜索后已变化的文件。CLI／Runtime 不继承 GUI 知识库权限。

## 页面草稿、对比预览与安装

仅 GUI Construct 提供页面构建。新增从空白创建完整草稿，编辑从当前正式页复制；可通过受控只读入口重读最新正式页，在自己的 Session 草稿继续适配，不直接改正式目录、不重建 Candidate。页面不进入 Manifest，不随 Publish 发布。

每份草稿是完整 Page Package，保存在 `developer-sessions/<Session ID>/page-drafts/`，包含 `page.py` 与页内资源；资源通过 `context.resource_path(...)` 定位。旧单文件草稿继续兼容，复制／安装或增加资源时按 [Sharing 页面包规则](sharing.md#页面包与-agent-工具)处理，不批量迁移。此边界由 [ADR 0036](adr/0036-share-selected-objects-and-install-complete-page-packages.md) 明确替代原单文件限制。复制正式页时固定原文件名为安装目标。2026-11-06 修订：草稿不保存新增／替换元数据，不因预览关闭或安装与否改变编辑能力；完整源码也可创建同名正式页的草稿，每次人工批准均可覆盖该文件名对应的正式页面包。旧元数据忽略，安装后草稿继续保留。固定程序不检验配置兼容、不自动调用 submit()，也不增加检查配置按钮；下节“兼容检查”指 Agent 代码审查与影响总结，宿主只保留加载 / 页面契约 / 必要路径和 ID 检查。

### 兼容检查

Agent 检查页面接口、PAGE_ID / TASKS 中各任务 ID、现有配置及对应 Plan 参数使用，尝试保持兼容。默认保留原页面 ID 和旧配置，不自动清空字段、不建设通用迁移系统。页面负责读取及校验旧配置，不兼容时明确提示；Agent 修正或人重新填写保存。破坏接口兼容的方案须说明理由和影响，先取得明确授权，再完成草稿；这不替代安装确认。

### 同进程应用级模态对比

1. Qt 主线程先加载拟安装页并检查页面契约 / ID 注册，失败直接把具体错误返回同轮 Agent，不打开人工审批，也不等待人关闭错误页。成功后打开应用级模态窗口，提供 Current / Proposed / Review 三 Tab，默认 Proposed。Current / Proposed 各有独立页面实例；无同名正式页时 Current 标明新增 / 不存在，旧页加载失败则显示错误，仍允许审查正常修复版。
2. 拟安装页来自指定 Session 的实际草稿版本，检查后复用同一个实例，尚不写正式目录；Current 加载当前正式代码。切换 Tab 不重新执行或创建页面，不重置试填状态。Review 展示 Agent 改动 / 影响总结，集中显示文件名、页面 / Task ID 及版本哈希；不强制先浏览其他 Tab 才能安装。
3. 两页分别从已有配置复制，缺少配置时用页面默认值；context.load / context.save 只操作各自内存副本，宿主不自动调用 submit()。试填互不影响，不写正式配置或独立试验配置文件，关闭丢弃，安装不导入试填值。
4. 对比窗口内两页可交互，锁住其他 LALC User / Developer 窗口；尝试点击被锁窗口时提醒并强调 / 聚焦对比窗口，不再弹一层警告。游戏和其他应用不被锁住。
5. 预览期间不切换 / 新建 Session，不启动新的 Agent 修改；关闭后解锁。Agent 发起预览若需等待审查，关闭 / 取消入口必须能解除等待，不依赖被锁住的主窗口按钮。已有运行活动未结束时不绕过活动门控启动预览。
6. 修改草稿后重新打开预览，加载该版本的代码；不承诺卸载其导入的所有模块或隔离任意 Python 副作用。独立模块身份和页面实例不能混用两侧注册及配置，沿用现有页面契约，不做主 GUI 页面热替换。

同进程方案用于简化实现，不是安全沙箱或故障隔离。任意 Python 页面可能绕过配置接口写盘 / 联网，卡死或崩溃可能影响主应用；“内存试填”只约束宿主提供的配置路径，不能宣称阻止所有副作用。

### 人工确认与覆盖

开发者对照两页，在统一入口“确认安装此版本”。确认只批准实际预览的草稿版本，后续修改必须重新预览；普通人工答复和旧确认不能批准新代码。

2026-11-02 细化及试用修订：窗口始终提供“安装此版本”“关闭不安装”“取消本轮”；关闭 / Esc 返回未安装并允许 Agent 继续，取消结束当前轮次。旧正式页加载失败时在 Current 单独展示错误，不阻止安装正常修复草稿；拟安装页加载 / 契约 / 注册失败直接返回 Agent，不进入人工审批。安装提交窗口固定的字节快照，后续草稿修改不进入该次批准。

不引入自动版本冲突检测、自动阻止覆盖或智能合并。正式页若在另一个 Session 被更新，由人检查当前正式页与本草稿；需要适配就关闭预览，让当前 Agent 重读最新正式页后修改，再预览。人工确认可覆盖其他 Session 的改动，不将此视为程序已证明兼容。

安装仍须校验目标路径及页面契约、页面 / Task ID 注册边界，不能把“不检测版本冲突”解释为取消必要验证。安装失败保留原正式页并报告，草稿保留供继续工作。安装不修改 Default；本轮 Agent 后台作业结束并清理完成后，统一检查本轮实际安装结果：至少一个页面安装成功才显示一次专门弹窗“页面安装完成，重启 LALC 以应用修改”，提供“取消”和“现在重启”。本轮无安装、仅预览或关闭不安装不弹；本轮失败或取消前已有安装仍弹，恢复历史不补弹。取消仅关闭提示；现在重启通过既有整应用重载接入 User GUI，不绕过活动门控。

导入、显示及提交配置不等于 Dashboard / Plan 集成成功，交付须说明兼容处理、已执行检查、未验证项及获授权的接口变化，不虚构游戏验收。

## 请求人工答复或操作并等待反馈

GUI Construct / Repair 均可在当前轮次请求信息、方案意见，或请求人把游戏操作到指定状态。使用统一的普通非模态反馈窗口，展示 Agent 的交互内容 / 意图与同一个文字输入框，不区分请求类型，不置顶、不锁住其他 LALC 窗口。提供 Skip / Confirm / 取消本轮；等待不设自动超时，GUI 保持响应，不妨碍切换游戏，也不并行试运行或自动输入，不能切换或新建 Session。该窗口与锁住其他 LALC 窗口的页面对比预览是不同交互。

- Confirm 返回实际答复 / 操作情况；允许空答复，明确返回已确认且答复为空，与 Skip 区分。不证明目标状态已达成。Agent 按需要重新观察；不隐式解除人工暂停，也不构成永久授权或页面安装批准。
- Skip / 关闭 / Esc 返回明确跳过，不等于操作完成，不授予破坏兼容或安装权限；缺少必要授权时保留该事项，继续独立工作或说明阻塞。
- 取消本轮必须解除等待并沿已有路径收尾；空答复、重复或迟到回调、Developer 窗口退出需有明确结果，不绕过退出确认。若主窗口因等待界面不可操作，等待界面必须保留取消出口。
- 请求内容、选择和答复按 Session / 轮次 / 工具调用关联记录在本 Session 的 Agent Interaction Log，并返回当前上下文，沿用脱敏；等待期间不发起新模型请求，不重置本轮请求额度。不增加请求类型字段、选项表单、反馈图片附件或操作成功勾选框。补充决定与审查见 [#338 决策记录](stage-5-338-decisions.md)及[影响审查](stage-5-338-design-impact-review.md)。

## 实施与验证边界

先完成可创建 / 恢复的 Repair Session 和手工草稿保护，再在统一工作台提供 Construct、模式权限及会话导航；后续知识库、人工反馈、页面对比 / 安装按可独立验证的垂直增量交付，不做长期只有底层结构而无可用行为的横向拆分。最终 tickets 的粒度及真正阻塞边需经开发者确认。

开发者已确认的六票拆分见 [Stage 5 tickets](stage-5-implementation-slices.md)，原工作台页面及 Construct 模式合并验收；已发布为 #335–#340，原生阻塞关系及标签已核验。

检查必须覆盖 GUI / CLI 互通、模式与入口权限、跨进程互斥、空白 / 指定来源、恢复与中断不重放；共享资源不回滚；Manifest 选择刷新与无隐式切换；受控 Git 和来源版本；人工等待取消；页面双实例内存配置、全应用模态、安装版本绑定及失败保留原页，及既有 Dashboard / Plan 参数对接。

普通源码 / 替身 / offscreen 测试、真实 pi、真实模型、Windows 成品和真实游戏证据分别记录。真实 pi 进程、Agent 工具循环或模型服务测试标记 pytest.mark.agent，默认跳过，按相关测试文件显式选择；不得因本机装了 pi 就自动执行，不把跳过计为通过。本轮文档与审查不提供这些产品运行证据。

2026-11-12：Session 页面标题下显示可选中复制的完整 Session UUID，空白新会话不显示；导出选择列表补充标题和时间，见[决定、影响审查与验证](session-sharing-display-impact-review.md)。

2026-11-12 上下文修订：由持久 pi Session 恢复有效模型历史和压缩边界，LALC 日志保留原始证据；旧会话一次性迁入、图片按 ID 回读、轮内压缩和额度显示见 [ADR 0041](adr/0041-let-pi-own-effective-agent-context.md) 与 [实施记录](context-compaction-implementation.md)。本项替代每轮从完整业务历史重建模型输入的方式，当前权限仍逐轮固定。
