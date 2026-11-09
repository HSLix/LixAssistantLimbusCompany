# 当前状态与文档入口

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

2026-11-06 Developer 新增 Capture 后的 OCR 测试页：独立截图、全图识别、鼠标选区自动重新识别及编号文字对照。设计、影响与验证见 [OCR 测试页记录](ocr-test-page-impact-review.md)，用法见 [OCR](ocr.md#developer-ocr-测试页)；不代表 Windows 或真实游戏验收。

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
| Stage 6 Runtime | 接入及新增设计仍待推进，不继承 Workbench 权限 | [Runtime 契约与 TODO](stage-3.5-agent-runtime-step-recovery-and-maintenance.md) | 本次不宣称已实现 Runtime Agent 闭环 |

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
