# 当前状态与文档入口

截至 2026-11-05；#317 取消及验收归属已按开发者本轮确认和关闭评论更新；本次核对源码 `7e4b309072e2a360f87b497d878340c4a936b25e` 的干净工作树及 GitHub Issues。本文集中记录状态与阅读入口，不替代规格或 ADR。后续状态变化在本页更新，实施过程和验证结果写入对应记录，不在每个入口追加同一份时间线。README 只负责基础介绍、部署和协议，不承担阶段状态维护。

2026-11-06 页面试用修订：移除页面草稿新增／替换元数据，同一草稿可反复修改并经预览批准覆盖同名正式页；安装成功弹窗提供取消或等待当前操作清理后重启。详见 [Stage 5](stage-5-agent-workbench.md#人工确认与覆盖)，未进行 Windows 实机验收。

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
| OCR／版本历史／Prompt | 已本地接入，具体限制分别记录 | [OCR](ocr.md)、[版本历史](game-version-history.md)、[Prompt 与 SOP](agent-repair.md#prompt-与-sop) | [OCR 记录](ocr-integration-impact-review.md)、[版本记录](game-version-session-implementation.md)、[Prompt 记录](agent-prompt-implementation.md) |
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
