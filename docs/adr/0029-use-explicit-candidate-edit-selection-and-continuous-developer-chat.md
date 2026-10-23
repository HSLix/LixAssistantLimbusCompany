---
status: accepted
supersedes: 0025 and 0028 (independent repair lifecycle and edit scope only)
---

# Use explicit Candidate edit selection and continuous developer chat

2026-10-23 确认：Developer GUI 四页纳入 Stage 3，须在 2026-10-29 前完成，作为 #329 的前置。为允许多轮开发而不丢失草稿，Candidate 改为由开发者从已有 Manifest 明确初始化/重建，非空时确认替换；修复和 New Conversation 不清空 Candidate。重建成功开启新对话，取消或失败保留原草稿和上下文。Runner 选择只决定后续执行的 Base Manifest，与 Candidate 基线和 Default 独立。

独立修复从单 Component 改为显式多文件授权，GUI/CLI 共用 pi 编辑工具与宿主检查。全选覆盖 Candidate 中除 `plan.json` 外的已有文件，包括候选 `manifest.json` 与 Recovery Rule 源码；不开放新建、删除或任意目录访问。无文件选择时仍可分析并使用已有素材工具，但不能编辑 Candidate。候选 Manifest 是可编辑草稿，正式 Manifest/源码及既有图片、旧标签仍按原约束保护；新增 Asset 继续只走 ADR 0028 的现场裁剪工具。完整候选校验和人工 Diff 审阅承担扩大编辑范围后的检查，不能把 Validator 当作操作系统沙箱或游戏行为证明。

同一对话保留上下文，每条用户消息触发一轮，允许纯文字和可选图片。请求上限按轮计算，默认 20、最小 2，自动模型检查消耗计入额度；每个对话使用一个按日期/UUID4 分组的交互目录，逐轮留存输入、工具、结果、配置与产物。人工审批直接通过 Diff/校验、主动 Publish 和独立设置 Default 完成，没有运行时 `Awaiting Approval → Applied` 流程。Diff 以初始化时固定的基础 Manifest 及哈希源码为准，跨 New Conversation 不更换基线。

Capture 人工裁剪必须预览并确认，保存框选时那张原图，不隐式重截；Agent 裁剪仍每次新截图。Runner 与 Agent 一轮处理互斥，手工截图/保存也与活动任务互斥，暂停仍占用；被动坐标与已有图片预览可继续。此决定不引入 Runtime Agent Recovery、Working Manifest 衔接、自动试跑或自动发布。发布分发推迟到 Stage 4 之后，不以包内携带 pi 或双包方案作为本期验收要求。

详见 [Developer GUI](../developer-gui-design.md)。四页与共享宿主已按此决定实现；自动化、真模型及 Windows 验收状态见设计文档，不能将代码完成视为全部验收完成。
