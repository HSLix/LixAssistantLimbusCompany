# Domain Docs

本仓库采用单一领域上下文。工程技能先读根目录 `CONTEXT.md`，再按[当前状态与文档入口](../current-state.md)选择相关规格、ADR、用法及证据。若存在 `CONTEXT-MAP.md`，按其指向补读；目前的单上下文结构不要求新增该文件。

## 文档分工

- `CONTEXT.md` 记录共享术语与领域边界；输出中的领域概念沿用其命名。
- `docs/adr/` 记录架构决定与取舍；相关规格记录可检查的需求。
- 当前状态集中在 `docs/current-state.md`；不要在本指南反复追加功能更新或复制完整规格。
- 讨论、影响审查、阶段拆分和实施验证记录保留各自时点。不能把历史代码差距直接当作当前缺陷，也不能把已接受设计当作已实现或已验收。
- 以明确接受、适用范围和替代关系确定权威；新日期或现有代码不自动推翻 ADR。权威未明时显式报告冲突，不自行改写需求。

## 关键阅读路径

| 改动范围 | 必读入口 |
| --- | --- |
| Workflow、Plan、执行与恢复 | [开发教程](../developer-workflow-tutorial.md)、[Stage 4](../stage-4-extensible-user-gui.md)、ADR 0023／0026／0032；Runtime 另见 [Stage 6](../stage-3.5-agent-runtime-step-recovery-and-maintenance.md) |
| Workbench、Session、权限及页面审批 | [Stage 5](../stage-5-agent-workbench.md)、[Agent 用法](../agent-repair.md)、ADR 0034／0036 |
| Asset、截图、裁剪与归档 | ADR 0027–0031、[Agent 素材用法](../agent-repair.md#agent-素材预览与归档) |
| Sharing、页面资源、容量与暂存 | [Sharing](../sharing.md)、ADR 0036／0037 |
| 外部参考搜索、版本同步、pi／codesearch 生命周期 | [外部搜索](../external-code-search.md)、ADR 0038 |
| 日志与游戏版本历史 | [运行日志页](../user-run-logs.md)、[日志设计](../agent-interaction-log-design.md)、[版本历史](../game-version-history.md)、ADR 0033／0035 |
| Windows 构建与验收 | [打包说明](../windows-packaging.md)、[当前状态](../current-state.md) |

## 跨范围边界

- 已发布 Manifest 和正式源码保持不可变；Candidate、Default 与运行中的 Working Manifest 职责不同。Publish 与 Default 选择分开。
- Assets 独立于 Manifest；旧图像不覆盖，Agent 删除仅走开发策略已授权的专用归档路径。Runtime 无删除权限，不继承 Workbench 工具。
- Trusted Actions 由应用登记，经 `ctx.action()` 保留权限、校验、Trace、错误与中断边界，不能改为直接后端调用。
- Session 的固定模式、来源与草稿独立于手工 Candidate；历史附件及日志不构成授权。页面安装仍需专用人工审批。
- 测试遵守根目录 `AGENTS.md` 和 [pi 测试规则](../pi-probe.md)。实现、测试存在、执行通过与真实环境验收分别报告。

出现相抵触的决定时，先列出双方来源与具体影响；只在已有明确替代决定时同步现行文档，保留历史理由及证据。
