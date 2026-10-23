# Developer GUI — Accepted Design

状态：设计已接受，四页及共享宿主已实现；自动化、真模型和 Windows 验收分开记录，见文末实施状态。[GitHub #330](https://github.com/HSLix/LixAssistantLimbusCompany/issues/330) 已创建并标记 ready-for-agent，作为 #329 的原生 blocker。架构修订见 [ADR 0029](adr/0029-use-explicit-candidate-edit-selection-and-continuous-developer-chat.md)。以下为逐项确认的决定及从原草案保留的要求，不把当前 CLI 已有能力或文档完成视为 GUI 已实现。

## Confirmed decisions

- Candidate 由开发者明确初始化或重建，选择已有 Manifest 作为基线；非空时需确认替换。修复使用当前已初始化的 Candidate，没有时提示先初始化。不按 Candidate 或单个文件是否通过校验区分修复权限；历史校验结果可从对话上下文查阅，校验失败不阻止继续编辑。发送消息、开始修复或 New Conversation 均不隐式清空 Candidate。该决定取代此前每次独立修复从 Default 自动重建 Candidate 的设计，需要 GUI 与 CLI 共用的修复入口同步调整；现由 GUI/CLI 共享宿主实现。
- 修复目标由开发者明确选择，支持任意数量的多选与全选，Agent 不自行扩大授权集合。该决定扩展此前单 Component 修复的设计，不因此获得运行中 Working Manifest 接入、自动试跑或发布权限。
- 选择范围是 Candidate 中除 `plan.json` 外的全部已有文件，提供全选；包括候选 `manifest.json` 和 Recovery Rule 源码，不再按 Task/Subworkflow/Step 三种角色过滤。`plan.json` 不因全选而获得编辑权限。候选 Manifest 是可编辑草稿，不能与已有正式 Manifest 的不可变约束混为一谈；完整候选仍须通过现有 Validator。此决定修订 ADR 0028 中“候选 Manifest 不可改”和“Recovery Rule 不可改”的旧范围；现由共享授权机制实现。
- 现有 Agent 文件编辑能力须升级为多文件编辑，由 GUI 与 CLI 共用同一授权机制；继续复用 pi 的编辑能力，并同步调整目标传递、提示词、权限检查、多文件原始/最终快照、Diff 与测试。仅允许修改开发者选中的已有 Candidate 文件，不提供新建或删除 Candidate 文件的工具；`plan.json` 明确只读，不仅依靠提示词或全选列表排除。候选目录外及正式发布物的访问边界保持不变。
- Candidate 已准备但未勾选任何编辑文件时，仍允许发送消息分析问题并使用既定素材工具，禁止编辑 Candidate。需要编辑时提示开发者先选择目标，不自动全选；素材工具仍按已有权限执行，不能把这种模式描述成对全部数据都只读。
- Agent Repair 采用连续对话：同一对话保留此前消息、图片和工具结果，每次用户发送消息启动一轮处理，Agent 最终回答后结束本轮并等待下一次主动发送。允许纯文字发送，图片作为可选附件；共享入口和模型预检不得继续强制要求用户提供 PNG。信息不足时说明缺少什么并结束本轮，不阻塞等待补充；后续用户可主动发送新消息继续。New Conversation 清空聊天上下文但保留 Candidate。
- 人工审批直接通过三个操作完成：查看实际 Diff／校验结果；开发者主动 Publish，由既有服务重新校验并生成新的不可变 Manifest，不自动运行；另行显式设置 Default，不随发布执行。GUI 不增加 `Awaiting Approval → Applied` 状态或独立运行时审批流程。未发布的 Candidate 本身不阻止 New Conversation；正在处理时禁止开启新对话。
- 模型请求上限按每次用户发送消息触发的一轮处理独立计算，下一轮重新计数并保留聊天上下文。GUI 提供持久设置，默认 20、最小 2，复用现有设置校验；自动模型检查消耗的实际请求计入本轮额度。超限结束本轮并保留候选与日志，等待用户主动发送下一条消息，不自动续跑。
- 一个连续对话对应数据目录下按日期/UUID4 分组的一份 Agent Interaction Log，内部逐轮保存用户消息、附件、实际模型请求与回复、工具调用及结果、实际非密钥配置和请求次数、候选变化及结束原因。New Conversation 创建新的交互 ID，旧日志和产物继续保留；GUI 只展示当前对话，不实现历史浏览、检索或恢复。
- 成功从所选 Manifest 重建 Candidate 后自动开启新对话，重新准备候选上下文，原对话和产物保留在旧日志中。若当前已有对话上下文，切换前的确认提示必须说明成功切换后将自动开启新对话，并同时说明非空 Candidate 会被替换。取消或初始化失败时保留原 Candidate 和原对话。Agent 正在处理时禁止重建，需先取消并等待结束；独立 New Conversation 仍不清空 Candidate。
- Capture 人工裁剪以明确取得并固定的预览原图为准：截图、框选、展示裁剪后的 Asset 预览、开发者确认后保存。保存使用同一原图和区域，不隐式重新截图；更新画面须主动再截图。坐标与裁剪基于原始像素，预览缩放不改变语义。确认前不写入 Asset 图片或标签，取消不写入；保存复用现有 Asset 存储、校验和来源记录。该人工交互不改变 Agent `crop_asset` 每次重新截图的语义。
- Runner 所选 Manifest 与 Candidate 基础 Manifest 相互独立：Runner 显式选择只作用于后续执行的 Base Manifest，不修改 Default，不自动初始化或重建 Candidate。未选择时沿用 Default；界面显示本次实际采用的 Manifest ID，即既有 Base Manifest，不引入新的 Manifest 类型。Candidate 的重建仍由独立的明确操作触发。
- Runner 所选 Manifest ID 持久保存在本地，重启 GUI 后恢复，不改变 Default。没有显式选择时使用 Default；保存的选择不可加载时明确提示并禁止启动，直到开发者重新选择或清除选择，不静默回退到其他版本。
- Runner 执行与 Agent 一轮处理互斥。Workflow/Plan 正在运行或暂停时不能启动 Agent；Agent 正在处理时不能启动 Runner。按钮禁用并说明原因，不自动停止另一项活动。Agent 已回答并等待用户主动发送下一条消息时不算忙，允许启动 Runner，保留对话和 Candidate；这不是 Stage 3.5 的暂停任务接管。
- Capture 坐标监测只读且不抢焦点，游戏窗口有效时持续显示与 Runtime 一致的客户区物理像素相对坐标，不要求游戏处于前台；鼠标在客户区外明确显示。窗口消失、最小化或无法唯一定位时停止监测并显示原因，等待手动刷新。仅主动截图按既有规则恢复并置前游戏窗口。窗口识别、DPI 和坐标转换由共享窗口服务提供，GUI 不维护另一套实现。
- Capture 可填写本次待保存 Asset 的完整逻辑名和 tag 列表，支持零个、一个或多个 tag。裁剪预览确认时同时展示逻辑名和标签；确认后复用现有校验及开发者 Asset 保存语义，零个标签存为 `[]`，不改变既有的标签顺序/重复项保留和开发者替换规则。
- 关闭 GUI 时，若 Runner 正在运行/暂停或 Agent 正在处理，提示取消当前任务并退出，也可返回继续。确认退出后沿用取消机制，等输入释放、日志保存和 pi 子进程回收再关闭，等待期间显示正在停止并保持界面响应。切换页面不取消任务；退出不自动 Publish，Candidate 和既有日志保留。
- Runner 正在运行/暂停或 Agent 正在处理时，禁用 Capture 手工截图及裁剪保存并说明原因；已有截图查看、框选/预览和只读坐标监测仍可进行。手工截图/保存进行中也禁止启动 Runner 或 Agent，完成后恢复按钮，不为暂停状态另开例外。实际候选修改/校验期间不能重建或发布正在被使用的 Candidate，互斥由共享宿主管理，不仅靠禁用按钮。
- Capture、Runner、Agent Settings、Agent Repair 四页及上述共享能力调整全部纳入 2026-10-29 前的交付，不延期为后续 GUI 阶段。Developer GUI #330 作为 #329 的原生 blocker；GUI 未按范围完成前，#329 不能认定 TA demo 交付完成。
- 当前不考虑发布或分发包，Stage 4 之后再讨论；打包/分发方案不作为 #330 或 #329 本次验收门槛。后续倾向普通包不携带 Agent、可另有带 Agent 的包，并允许不带 Agent 的安装后续通过配置具备 Agent 能力；这只是未来方向，不在本期实现双包、内置 pi、自动下载或安装机制。当前开发复用既有 pi 接入，不要求普通 Workflow 启动 Agent。当前接入回归基线为 1.4.0；版本不匹配只记录 WARNING 并在 CLI/GUI 提示，不阻止启动，实际版本进入交互日志。
- 多文件 Diff 以选择 Candidate 基础时固定的正式版本为准：基础 Manifest 的 Component ID 映射指向数据目录中的哈希化正式源码，逐文件与当前 Candidate 对比。Manifest 本身使用 UUID，内容哈希用于 Component 源码，不混为同一种标识。候选 `manifest.json` 的实际编辑也纳入审阅；基线须采用既有候选物化表示，不能把正常的 `component_id` → `source_path` 转换当作 Agent 修改。跨多轮和 New Conversation 保留同一基线，直到明确重建 Candidate；不追随 Default 或 Runner 选择变化。Diff 只读展示，不实现合并编辑器。

## Requirements retained from the original draft

- 复用已有 PySide6 GUI 与共享应用服务，不通过执行 CLI 命令实现 GUI，不在界面实现另一套 Agent Loop。耗时操作不阻塞 GUI，普通 Workflow 不依赖 pi 启动。
- Runner 支持 Automation Plan、Task Workflow、Subworkflow、Step；Plan 选择现有配置文件，其他入口按所选 Manifest/角色展示并接收 JSON 参数，复用现有参数契约。保留暂停、接管、恢复、取消、执行结果及 Trace/Ledger 定位，不新增 Plan/代码编辑器或参数表单生成器。
- Agent Settings 提供 Base URL、Model、API Key 和模型请求上限。密钥仅能设置、覆盖或显式清除，界面不读取/显示已有明文，只显示是否设置；普通保存时空输入保留原密钥，认证值不进入日志或配置导出。复用 Windows DPAPI 与 Mac 临时内存密钥边界，不读取或修改其他 pi 实例的个人配置。
- GUI 状态由真实 Host/工具/校验事件驱动，不依靠模型自然语言猜测分析阶段；展示当前工具和实际结果，不做 token 级可视化、虚假审批状态或假操作按钮。
- Open Asset Directory 由既有数据目录与 Asset Library 路径提供，使用系统文件管理器打开；不存在或失败明确提示，不实现文件管理器。

## Implementation scope

- 将现有 PySide6 主界面升级为 Capture、Runner、Agent Settings、Agent Repair 四页，不保留第二套执行/修复路径。CLI 与 GUI 调用相同的应用服务和修复宿主；耗时操作在线程/异步任务中运行，通过真实事件更新 GUI，界面不解析 CLI 输出充当服务调用。
- 同步修改候选生命周期、所选文件集合与编辑权限、提示词、完整候选校验、多文件快照/Diff、可选图片、按轮计数和连续对话日志。每轮使用固定授权集合，Agent 不自行扩大；`plan.json` 由工具权限强制只读，无选择时不开放 Candidate 编辑。
- 继续复用现有 Manifest/Component/Asset 格式、应用注册动作与 pi 工具。Runner/候选基线等 Host 元数据不通过修改正式 Manifest 来保存。未实现的新契约必须明确标为待实现，不让旧单目标 CLI 示例冒充新功能。
- Runner 继续调用现有启动、参数校验和暂停/恢复/停止接口。空的参数输入按空对象交给已有契约；非对象 JSON、格式与签名错误明确展示。Plan 从已有文件读取其各项输入，不叠加另一套 GUI 参数协议。
- 本期只读展示多文件 Diff 与校验结果，不做 IDE、合并编辑器、Workflow 图编辑器、复杂模型预设/发现、历史对话管理、多 Agent 并发、Asset 文件管理器或新存储协议。发布分发不在本期范围。

## Verification

- 自动化检查 GUI/CLI 共享服务的公开行为，覆盖候选替换确认/取消/失败、对话与候选切换、多文件授权与 `plan.json` 只读、零文件选择、累计 Diff、Runner 选择独立与持久化、四种入口/输入、密钥不回显与空值不覆盖、活动互斥和关闭取消。GUI 可用 offscreen 验证状态与事件，不增加测试专用执行器。
- 图片预览测试核对缩放坐标、裁剪像素与保存内容相同，确认前和取消后无素材写入；标签遵循既有规则。Windows 实机验证跨 DPI、窗口移动/尺寸、客户区外、失效后手动刷新、焦点和真实裁剪，不以平台替身代替。
- 涉及真实 pi 进程、工具循环或模型服务的测试必须标记 `pytest.mark.agent`，默认回归跳过；只在本需求相关接入验证中显式使用 `--run-agent-tests` 并选择相关文件。普通回归不附带调用 `pi-probe`，未运行的 Agent 测试不报告通过。
- 真模型/Windows 结果仍需独立证据，尤其 #327 延后的新启动流程/认证及 #326 现场工具实测。GUI 四页和共享修复升级完成后，在 #329 结合真实缺陷验收；本期不增加发布/打包门槛。


## Historical implementation inspection before #330 — 2026-10-23

本节保留实施前旧 CLI 的检查证据，描述的是被本次实现替换的历史行为，不代表当前代码或本次验收。

- `run_repair` / `repair_baseline` 目前只接受 Default Manifest 中已有 Task Workflow、Subworkflow 或 Step 的一个逻辑名，目标固定为对应 `.py` 文件；Recovery Rule 不在这个目标集合中。模型预检成功后仍会重建 Candidate，这与上述新生命周期决定尚未对齐。
- pi 的 `read` / `edit` 均复用现成工具工厂。`read` 对 Candidate 内已有文件不做扩展名过滤；`edit` 在实际 access、read、write 前核对解析后的路径，写入目标必须等于宿主指定的唯一源码文件。
- 路径通过 `realpath` 和目录包含检查，拒绝 Candidate 外路径及解析到外部的符号链接。当前没有对 `plan.json` 的专门拒绝规则；`manifest.json` 不能编辑是单目标限制的结果，并不是候选 Manifest 技术上不可编辑。
- Agent 工具集合不含通用 `write`、文件删除、终端、Publish 或设置 Default。由于编辑路径必须先解析为已有文件，也没有通过现有编辑工具新建文件的入口。宿主初始化、日志写入及受限 Asset 新增是另外的固定操作，不代表 Agent 获得任意文件写入权限。
- Asset 文件通过专用工具访问，新增只走 `crop_asset` 并保留旧图片/旧标签；图片和工具返回保存在宿主控制的交互目录。pi 个人扩展、skills、上下文文件发现及会话保存被关闭，配置使用临时目录。
- `validate` 由宿主调用完整 `ManifestManager.validate()`；候选引用路径受目录校验，模块仍会被导入执行，标准库可导入。禁止生成文件操作、网络、子进程和顶层副作用目前主要是提示词约束，不是操作系统隔离；不能把单文件编辑限制描述为对候选 Python 一切副作用的隔离。
- 原始/最终源码及 Diff 当前按一个目标文件留存，没有通用多文件快照、增删记录或整目录变更授权核查。多选与候选 Manifest 编辑需要同步升级目标传递、权限检查、提示词、产物记录和测试，而不仅是增加 GUI 复选框。
- 现有测试定义覆盖越界读取、外部符号链接，以及拒绝编辑候选 Manifest、其他源码和外部路径；本轮只阅读这些测试，未执行。

现有实现与领域约束参照 [Component Repair](component-repair.md)、[Stage 3](stage-3-agent-assisted-component-repair.md)、[ADR 0028](adr/0028-bound-manual-agent-repair-with-live-observation-and-asset-additions.md)。本次讨论不运行真实 pi、Agent 工具循环、模型服务测试或 pi-probe。


## Implementation status — 2026-10-23

- `developer.py` 与 `ApplicationService.activity()` 提供共享 Candidate 初始化/重建、失败恢复、固定基线、Runner 选择、人工预览保存及活动互斥；`component_repair.py`/`pi_probe.ts` 提供 GUI/CLI 共用多文件授权、零选择、纯文字、逐轮额度、连续上下文和完整候选工具校验。
- `gui.py`/`developer_gui.py` 提供四页、后台服务与真实事件、独立审阅/Publish/Default、关闭取消及等待清理。CLI 使用同一宿主，当前用法见 [修复指南](component-repair.md)。
- Runner 持久选择在重启恢复后先要求刷新核验，再允许启动；失败不回退。Candidate 基线采用初始化时的 `source_path` 物化表示，保存在 Candidate 外的宿主元数据，并在对话产物内留存，不将正常格式转换显示成 Agent 修改。
- 新增普通回归覆盖替换确认/失败恢复、无效草稿继续编辑、固定基线、四页、四类执行输入、共享互斥、关闭取消等待、缩放坐标和固定原图保存；真实 pi + HTTP 替身覆盖多文件/Manifest 编辑、plan.json 拒写、无选择、上下文保留、逐轮额度与取消。命令见修复指南，测试结果与未跑项目在交付记录中分别列出。
- 真模型连续修复、Windows DPI/窗口/焦点/像素保存、GUI DPAPI 实际认证和真实游戏案例仍须独立验收；不能由 offscreen 或 HTTP 替身宣称通过。本 issue 在这些证据补齐前仍不满足全部关闭条件，#329 仍承担最终游戏与 TA 交付验收。

本次执行结果：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q --tb=short` 为 **235 passed, 21 skipped**；显式选择 `--run-agent-tests tests/test_component_repair_agent.py tests/test_pi_probe.py` 为 **16 passed, 4 skipped**，通过项使用真实 pi 和本机 HTTP 替身。4 项真模型/Windows 接入验收因缺少显式模型连接或不在 Windows 而跳过，本机也没有已保存的 Agent 连接设置；未自动选择服务或模型。`git diff --check` 通过，四页已做 offscreen 渲染检查。此前 #325–#327 的历史记录继续保留，但不计入上述新契约验收结果。

后续 pi 1.4.0 兼容修复已按逐项失败即停的流程完成：全套回归 **258 passed、5 skipped**，无临时超时插件。自定义事件通道、可读超时、取消测试退出条件及无效测试 PNG 已修正；详见 [兼容修复记录](pi-1.4-compatibility-review.md)。上述先前 0.86.1 的回归统计为历史记录，真模型和 Windows 验收仍未由本次 HTTP 替身检查替代。
