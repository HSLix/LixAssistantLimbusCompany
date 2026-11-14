# 当前状态与文档入口

2026-11-14：SIFT 新增正式 `observe.match_feature`，复用当前截图、observe 权限、正式素材校验、统一 NMS、Trace 和非空使用索引；调试与正式最小内点比例默认 0.4，NMS IoU 默认 0.4。见[影响审查与验证](sift-trusted-action-impact-review.md)和[用法](developer-workflow-tutorial.md#sift-特征匹配)。普通针对性回归 201 passed。已有数据目录的 workflow-conventions Skill 不自动覆盖，需人工合并新增指导。Windows／真实游戏尚未验收。

2026-11-13：Agent 常驻提示及 `read` 工具说明明确 Skill 正文和附图统一使用 `read` 与绝对路径，`knowledge_*` 仅访问外部知识库；知识库读取分开报告文件缺失／非普通文件和超过 2 MiB。见[影响审查与验证](skill-image-read-impact-review.md)。针对性普通回归 42 passed；未运行真实 pi／模型、Windows 或游戏验收。

2026-11-13：Developer 聊天使用折叠附件托盘，待发送与已发送附件均显示在对应正文上方；支持图片预览、完整 UUID 提示、待发送逐项删除，以及多附件两行有界滚动。历史恢复复用留存原图，缺失图片显示占位。见[交互规格](stage-5-agent-workbench.md#聊天附件托盘)及[影响审查和实施证据](chat-attachment-tray-impact-review.md)。普通定向回归 113 passed；未运行全量、真实 Agent、Windows 或游戏验收。

2026-11-13：上下文用量移入输入框工具栏附件按钮旁，使用紧凑图标与文本，删除输入框下方独立进度条；保留压缩阈值、颜色分级及 token 悬停说明，未知回退为“上下文 —”并清除旧提示。见[影响审查及实施](context-usage-toolbar-impact-review.md)。聊天及语言普通定向回归 54 passed，已检查明暗主题及未知状态离屏截图；未运行全量、真实 Agent、Windows 或游戏验收。

2026-11-12：Sharing 与单次运行日志的导出／导入统一双进度窗口：整体文件计数、当前文件名与字节进度，明确准备、ZIP 写入、解压及安装阶段；提交／收尾成功后才显示整体完成。规格见[Sharing](sharing.md)。相关普通回归 176 passed；扩展检查发现既有默认 Skill 清单遗漏 `limbuscompany-knowledge` 的一项失败，核对 HEAD 后从最终回归排除。已检查中英文及明暗主题的离屏窗口；未运行真实 Agent、Windows 成品或游戏验收。

2026-11-12：聊天贴底改为持续跟随状态，工具更新、延迟排版及计时刷新沿用该状态；轮次结束耗时随结果和事件保存，历史无记录则不显示。相关普通回归 189 passed，范围和验收边界见[专项记录](chat-scroll-and-duration-implementation.md)。

2026-11-12：根据镜牢入口开发日志复盘修订默认 Agent 指导：局部修改分段试跑、稳定后补完整路径，每次运行前明确起点和期望并在结束后核对；通常采用十秒左右到十几秒超时后交给 Recovery Rule，不要求正常轮询检测错误弹窗。Task／Subworkflow 可先观测状态再进入子步骤，现有 observe／control 权限不变。补充中文直接编辑、准确类型示例及按需 OCR 指导，见[开发教程](developer-workflow-tutorial.md)与[默认规范](../src/lalc/skills/workflow-conventions/SKILL.md)。仅修改指导和工具说明；已有数据目录 Skills 不自动覆盖，需人工合并。

2026-11-14：原生聚焦从单次请求后持续等待，改为最多请求 10 次、间隔 1 秒；最后一次也保留 1 秒异步激活等待，仍未成为实际前台则报 WindowError，带目标／前台句柄及最后请求结果。用户活动等待、接管、暂停、取消及窗口失效边界保持；覆盖手动连接、Run、试运行和游戏重启共用入口。见[开发教程](developer-workflow-tutorial.md)及[影响记录](cursor-parking-and-log-copy-impact-review.md)。

2026-11-14：截图鼠标归位改为最多三次尝试，失败记录 Warning 并继续观察；截图后反复重新进入也设三次上限。新增移动坐标、窗口／桌面及鼠标裁剪诊断；User GUI 历史日志块支持行内复制全文及标准复制快捷键。设计与验证边界见[影响记录](cursor-parking-and-log-copy-impact-review.md)。此前“右下角无空间就失败”的行为已被本决定替代；接管、焦点及窗口错误边界保留。

2026-11-12：游戏截图默认受控归位鼠标：客户区内鼠标移到窗口右下角外 8 像素，接管后丢弃本次观察，Run 手动恢复后重新检测；`auto_park_cursor=False` 可关闭。手动截图增加接管监测并保留失焦即失败的边界；当时右下角无桌面空间时明确失败（已由 2026-11-14 决定替代）。用法与限制见[开发教程](developer-workflow-tutorial.md#匹配规则)，核心回归见 `tests/test_capture_cursor.py`。相关普通回归 289 passed；另有既存 PNG／AVIF 文件名断言不符的一项测试，单独执行失败后从最终回归排除。未运行真实 pi／模型、Windows 与游戏验收。

2026-11-12：日志诊断改进已本地实施：Run 图片使用 AVIF 65 / speed 8 / 默认色度采样，仅 Match 取消自动截图；Agent Run 元数据、过滤与跨 Run 关键词搜索、共享知识库开关、本轮静态当地时间，以及工具摘要／工作计时、日志滚动与短数组格式同步更新。相关普通回归 366 passed、1 skipped；真实 pi + 本地 HTTP 替身 3 passed。Windows 成品、真实模型和游戏未验收，见[决策](log-diagnostics-decisions.md)与[影响审查及验证](log-diagnostics-impact-review.md)。

2026-11-12：Session 页面增加可复制的完整 UUID；Sharing 导出列表补充 Workflow 附加信息、Session 标题和修改时间，并对齐历史会话顺序。已通过相关 82 项测试；Windows 原生显示未验收，见[决定、影响审查与验证](session-sharing-display-impact-review.md)。

2026-11-11：开发者面板的会话标题首次初始化后固定；历史会话增加悬停子设置、持久重命名及确认后彻底删除，忙碌及清理期间禁用入口。设计、故障边界与验证见[专项审查](session-management-impact-review.md)。

2026-11-11：移除 User GUI 打开开发界面的用途提醒，中文名统一为“开发者面板”；运行记录左侧每批显示 10 条、滚动追加，后台仍扫描时间目录。设计与验证见[专项记录](developer-panel-run-list-impact-review.md)。

2026-11-11 Stage 6 已完成本地实施：RunState、Plan／Workflow／Step 各自恢复、同一 Repair Session 的 Publish → Recheck 循环、开关与结束时 Default 选择已接线。Plan 正常结束即可自动使用最终 Working Manifest，不要求所有 Task 成功。设计见[影响审查](stage-6-design-impact-review.md)、[ADR 0040](adr/0040-share-run-state-and-reuse-agent-sessions-for-runtime-repair.md)，接口、迁移及验证边界见[实施记录](stage-6-implementation.md)。未创建 tickets；Windows、真实模型与游戏尚未验收。

2026-11-11 Developer GUI 打开期间，User GUI 的 User Agent 启用开关保持可用，仅具体 Agent 配置表单冻结；交接保存及关闭后重读共享值保持。影响与验证见[专项记录](user-agent-toggle-design-impact-review.md)。

2026-11-09 Sharing 增加完整 Skills 目录分享和默认不选导入，Asset 树简化选择，两处目录树仅默认展开顶层。边界及验证见[专项记录](skills-sharing-impact-review.md)。

2026-11-09 pi 读取层省略已识别 `agent_end` 的重复聚合负载，仅保留接收标记与字节数；普通事件保留 16 MiB 限制与具体诊断，继续等待 `agent_settled`。设计、影响与验证见[专项记录](pi-agent-end-impact-review.md)。

2026-11-09 Developer GUI 增加详情复制反馈、日志中性文案、持久化 Skills 目录入口及每轮思考／工具折叠时间线。接受交互、影响与验证见[专项记录](developer-process-timeline-impact-review.md)；Windows 原生与真实模型／游戏尚未验收。

2026-11-08 修复取消 Run 后 Developer 截图与窗口调整被旧取消状态阻断：正常及异常收尾在输入清理后释放 Run gate，保留运行／暂停期间的排他与取消边界。设计、影响及本地回归见[专项记录](developer-capture-cancellation-impact-review.md)；Windows 与真实游戏尚未验收。

2026-11-08 页面多任务、人工确认启停与 Session 来源显示已完成本地实施及相关回归；Windows、真实模型与游戏尚未验收，见[设计与影响审查](page-tasks-and-availability-design-impact-review.md)。


2026-11-08 运行界面性能增量：状态与日志分离、百毫秒合并更新、运行弹窗最近 300 条及按相关变化刷新设置／版本，完整 Trace 与传输格式保留。设计、影响及本地验证见[高频日志专项记录](run-ui-performance-design-impact-review.md)。Windows 与真实游戏响应尚未验收。

2026-11-08 日志增量：单日志 ZIP 导入导出、来源分类及中英文名称和时间展示，见[设计与影响审查](run-log-sharing.md)。Windows 原生验收未完成。

2026-11-08 本地 GUI 增量：工作流版本卡片、固定发布时间与说明、历史选择和任务次数限宽，见[接受设计、影响审查与验证](gui-workflow-versions.md)。未完成 Windows 原生验收。

2026-11-07 Component 说明改为 execute docstring 优先、模块 docstring 兼容回退；Recovery Rule 保留模块说明要求。影响和验证见[专项记录](component-description-impact-review.md)。

2026-11-07 输入所有权策略修订：游戏前台的客户区点击／滚轮及键盘按下才触发接管，Ctrl+Alt+P 全局暂停。失焦／最小化改为其他应用连续空闲十秒后自动聚焦；明确开始运行与手动恢复免等十秒。等待写入 Info 日志，长动作失焦先释放后重入当前 Step。设计、影响和验证见[专项记录](input-ownership-design-impact-review.md)；Windows 与真实游戏尚未验收。

2026-11-07 `control.wait` 改为 `observe.wait`，所有允许 observe 的调用阶段均可使用；旧名称不保留兼容别名，旧源码需通过 Candidate 改名并重新发布。设计、影响与验证见[专项记录](observe-wait-design-impact-review.md)。

2026-11-07 新增 `control.restart_game` 与对所有 Manifest 生效的内置游戏崩溃恢复规则：确认绑定进程退出后，在当前 Step 边界每次 Run 最多自动重启一次，保留调用者并重新绑定窗口；关闭、等待、启动及绑定过程进入用户运行日志。设计、影响和本地验证见[游戏重启记录](game-restart-design.md)、[ADR 0039](adr/0039-recover-game-process-exit-with-a-built-in-rule.md)。Windows 与真实游戏尚未验收；不代表 Stage 6 Agent 闭环实现。

2026-11-06 User GUI 新增按需加载的运行日志页，支持级别／全文／图片筛选、阅读锚点、长文本折叠和截图标注；共用执行器自动保留 Trusted Action Debug。设计、影响与限制见[运行日志页](user-run-logs.md)，不代表 Windows 或真实游戏验收。

2026-11-06 Developer SOP 迁入数据目录 Skills，采用 pi 原生元数据发现、按需只读加载和每轮固定副本；原 SOP 已在内容承接后移除。用法见 [Developer Skills](agent-skills.md)，设计及验证见[实施记录](agent-skills-implementation.md)；不代表真实模型、Windows 成品或游戏验收。

2026-11-06 Developer 在 Capture 下方新增模板匹配调试页：增量素材树、整组／单图选择、独立固定截图及真实参数匹配，不写运行使用索引。设计、影响审查与用法见[模板匹配调试页](template-match-lab.md)；Windows 与真实游戏待验收。

2026-11-06 pi 接入及 Windows 打包资源基线更新为 1.5.0；具体兼容检查和默认回归的已知示例失败见 [pi 1.5.0 记录](pi-1.5-compatibility.md)。不代表 Windows 成品、真实模型或游戏验收。

2026-11-06 Developer 新增 Capture 后的 OCR 测试页：独立截图、全图识别、鼠标选区自动重新识别及编号文字对照。设计、影响与验证见 [OCR 测试页记录](ocr-test-page-impact-review.md)，用法见 [OCR](ocr.md#developer-识别调试页)；不代表 Windows 或真实游戏验收。

2026-11-06 Agent 指导修订：明确业务 Step 完成确认、完整匹配返回及歧义处理、centerxy 优先调用、页面与 Plan 支持任务接线、Task 详细成败日志；通用指导与示例更新，不新增 Validator 业务检查。决策、影响及本轮验证见[审查记录](agent-step-guidance-impact-review.md)，不代表真实模型或游戏验收。

截至 2026-11-05；#317 取消及验收归属已按开发者本轮确认和关闭评论更新；本次核对源码 `7e4b309072e2a360f87b497d878340c4a936b25e` 的干净工作树及 GitHub Issues。本文集中记录状态与阅读入口，不替代规格或 ADR。后续状态变化在本页更新，实施过程和验证结果写入对应记录，不在每个入口追加同一份时间线。README 只负责基础介绍、部署和协议，不承担阶段状态维护。

2026-11-06 页面试用修订：移除页面草稿新增／替换元数据，同一草稿可反复修改并经预览批准覆盖同名正式页；本轮 Agent 结束且清理完成后，仅当本轮实际安装过页面时统一弹一次重启提示，提供取消或现在重启。详见 [Stage 5](stage-5-agent-workbench.md#人工确认与覆盖)，未进行 Windows 实机验收。

2026-11-06 本地增量：非 Session 开发操作日志改写入 `developer-operations/`，旧 `agent-interactions/` 保持可检索和导出；知识库更新跳过普通资料链接并报告 `excluded_links`，Git 元数据链接仍拒绝。当前用法见 [Agent 日志](agent-repair.md)与[外部搜索](external-code-search.md)；不代表 Windows 或真实远端／模型验收。

## 文档职责与权威

- [CONTEXT](../CONTEXT.md)：统一术语与领域边界。
- 已接受规格与 [ADR](adr/)：需求、约束与取舍；只在明确声明的范围内被后续决定替代。代码和较新日期本身不构成替代授权。
- 当前用法：操作方法与现行接口，见下表。
- `*-decisions.md`：讨论及确认来源；提议、否决和接受须按原文区分。
- `*-impact-review.md`：审查当时的影响与差距，不是当前缺陷清单。
- `*-implementation*.md`、验证报告与阶段拆分：对应时点的实施和证据；原清单未勾选不自动表示现今缺失，历史通过也不自动证明当前版本。
- [重建规划](reconstruction-plan.md)：阶段依赖与待讨论方向；旧阶段基线保留为历史，不覆盖下表现行契约。

## 实现、议题与验收

| 范围 | 当前状态 | 现行契约／用法 | 实施与验收证据 |
| --- | --- | --- | --- |
| Stage 2 确定性执行 | 按 ADR 0026 的修订范围完成；#317 已取消并关闭，不再等待单独邮箱验收 | [开发教程](developer-workflow-tutorial.md)、[ADR 0026](adr/0026-close-stage-2-without-a-real-game-workflow.md) | [阶段记录](stage-2-implementation-slices.md)、[#317 取消决定](https://github.com/HSLix/LixAssistantLimbusCompany/issues/317#issuecomment-6652564769)；当前验收由 #340 推进，不据取消补造通过结果 |
| Stage 3／4 开发与 GUI | #331–#334 均 CLOSED；#329／#323／#312 已按开发者收尾决定关闭 | [Stage 4 规格](stage-4-extensible-user-gui.md)、[Agent 用法](agent-repair.md) | [关闭记录](stage-3-4-closure-2026-10-30.md)；关闭不等于完整验收 |
| Stage 5 工作台 | #335–#339 CLOSED；#340 OPEN，本地已实现，等待开发者 Windows 实验及另行确认 | [Stage 5 规格](stage-5-agent-workbench.md)、[ADR 0034](adr/0034-extend-developer-agent-with-reviewed-page-drafts.md) | [Session](stage-5-335-implementation.md)、[工作台](stage-5-336-chat-ui-implementation.md)、[知识库](stage-5-337-implementation.md)、[反馈](stage-5-338-implementation.md)、[三 Tab 与 #339 验收](page-review-tabs-implementation.md) |
| Sharing／完整页面包 | 本地接入四类对象导入导出、页面资源及按可用资源检查 | [Sharing](sharing.md)、[ADR 0036](adr/0036-share-selected-objects-and-install-complete-page-packages.md)、[ADR 0037](adr/0037-budget-sharing-against-available-resources.md) | [实施记录](sharing-implementation-progress.md)；大文件、Windows、真实模型等边界按原记录分别验收 |
| 外部搜索／进程复用 | 本地接入 literal／hybrid、A/B 文件与索引切换、宿主级 pi／codesearch 复用 | [外部搜索](external-code-search.md)、[ADR 0038](adr/0038-use-versioned-reference-search-and-reusable-agent-processes.md) | [实施记录](external-code-search-implementation.md)；Windows、真实远端／模型与大仓库待验 |
| Windows 双包 | 构建逻辑已支持 with-agent／without-agent；不是成品现场通过 | [打包与验收](windows-packaging.md) | [#334 历史记录](stage-4-334-implementation.md)、[当前资源增量](external-code-search-implementation.md) |
| OCR／版本历史／Prompt | 已本地接入，具体限制分别记录 | [OCR](ocr.md)、[版本历史](game-version-history.md)、[Prompt 与 Skills](agent-repair.md#prompt-与-skills) | [OCR 记录](ocr-integration-impact-review.md)、[版本记录](game-version-session-implementation.md)、[Skills 记录](agent-skills-implementation.md) |
| Stage 6 Runtime | 新设计已接受并完成影响审查，待反馈／实施；复用 Session，按入口限权 | [Runtime 契约与 TODO](stage-3.5-agent-runtime-step-recovery-and-maintenance.md) | 本次不宣称已实现 Runtime Agent 闭环 |

## 必须保留的边界

- GUI Construct／Repair、CLI Repair 依据模式和入口重新计算权限；知识库与人工反馈只授 GUI，页面构建只授 GUI Construct。历史消息不是授权。
- Session 持有自己的 Candidate 与固定基线；手工 Candidate 独立。Developer GUI 没有人工版本选择／运行入口；Agent 可显式试运行已发布版本。Publish 不改 Default。
- 页面审批为 Current／Proposed／Review 三 Tab；拟安装页加载失败直接返回 Agent。批准绑定完整代码与资源快照，试填不落正式配置，安装不自动重载。Sharing 人工跳过 Review 的例外不授予 Agent 同等权限。
- Git 参考副本允许 ADR 0038 的受控 A/B 更新；Agent 不获得参考资料编辑或通用终端权限。列目录不触发同步。文件和索引成功后共同切换，失败保留可用 A 并报告。
- pi／codesearch 按需启动、跨轮复用、宿主退出关闭；pi 中途故障不重放工具。每轮权限、历史与额度重新配置；强制推理预检已取消。
- 普通回归默认跳过 Agent；按需显式 Agent 测试与普通回归串行。替身、真实模型、Windows 成品与游戏验收分开报告，未执行项不计通过。独立 `lalc pi-probe` 已删除，[旧文档](pi-probe.md)仅保留历史与测试规则。
- `.generated/external-search-validation/` 和相关实验代码、资源、成功／失败结果按原确认要求保留，不因本次文档维护清理。

本次复检与维护证据见[一致性审计](architecture-consistency-audit-2026-11-05.md)。

2026-11-09：已接受普通工作目录／文件权限继承及直接导出 ZIP 边界，保留清理、事务和导入 Review；设计与实施验证见[专项记录](ordinary-work-directories-impact-review.md)。

2026-11-12：pi 持久有效上下文、按比例／固定目标压缩、每轮图片窗口、DeepSeek 缺省选择及聊天额度提示已本地实现；设计见 [ADR 0041](adr/0041-let-pi-own-effective-agent-context.md)，验证与限制见 [实施记录](context-compaction-implementation.md)。

2026-11-14：开发者模板匹配与 OCR 合并为“识别调试”，顶部切换，共用固定截图、分别保留选区与结果；截图不自动执行，框选结束自动处理。素材保存页继续独立。设计、影响及本地验证见[合并记录](recognition-lab-impact-review.md)；Windows 与真实游戏未验收。

2026-11-14：识别调试新增 SIFT 特征匹配标签，支持单图／整组多实例查找、按内点数排序及可调预处理、SIFT、几何验证和 NMS 参数；暂不注册 Trusted Action。设计、实现及验证限制见 [SIFT 记录](feature-match-lab-impact-review.md)，全图效果仍有漏检与定位不准风险，不沿用固定区域实验的准确率结论。
