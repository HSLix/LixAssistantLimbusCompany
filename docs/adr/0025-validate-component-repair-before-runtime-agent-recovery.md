---
status: accepted
supersedes: 0013 (Stage 3 scope only)
---

# Validate Component repair before Runtime Agent Recovery

后续 [ADR 0029](0029-use-explicit-candidate-edit-selection-and-continuous-developer-chat.md) 将 Developer GUI、显式候选生命周期、多文件授权与连续对话纳入独立修复；本 ADR 的单 Component 范围不再约束该新需求。运行中 Working Manifest 衔接、自动接管和正式运行时试跑仍属于 Stage 3.5。

2026-10-23 修订：[ADR 0028](0028-bound-manual-agent-repair-with-live-observation-and-asset-additions.md) 允许 Stage 3 使用实时截图和受限的现场裁剪新增 Asset 工具，并明确从 Default Manifest 重建 Developer Candidate。下文“不新增 Asset”的历史范围由其取代，运行时恢复仍留给 Stage 3.5。

为尽快验证 Agent 自主修复 Component 的可行性，Stage 3 改为 **Agent-assisted Component Repair**：独立 CLI 由人工指定一个已有 Component，提供截图、异常和必要上下文；Agent 通过 Deep Agents 或类似 SDK 阅读源码、局部编辑并复用现有 Validator 迭代，输出完整候选源码、Diff 和验证结果。保留一次 CLI 调用的模型输入、工具操作和最终输出日志，并以至少一个可复现案例证明修复解决原问题。后续人工通过既有 Developer Candidate / ManifestManager 发布；Agent 不覆盖正式源码、修改已有 Manifest 或 Default Manifest，不自动 Publish。

Stage 3 不实现 Runtime Agent Session、自动异常接管、新增 Asset、多组件编辑、自动实机试运行或运行时恢复。原 ADR 0013 的运行时恢复设计及 ADR 0015/0016/0018 等配套监督、试运行和审批约束移交 Stage 3.5；ADR 0020/0024 中的 Agent Asset 创建也只在 Stage 3.5 启用。现有确定性执行、不可变身份、Asset 管理和发布边界不变。本次显式替换阶段范围，不把既有运行时设计或讨论 TODO 当作 Stage 3 的实现前置条件，也不表示这些功能已实现。

详见 [Stage 3](../stage-3-agent-assisted-component-repair.md) 与 [Stage 3.5](../stage-3.5-agent-runtime-step-recovery-and-maintenance.md)。
