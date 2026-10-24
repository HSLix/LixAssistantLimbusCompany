---
status: accepted
supersedes: 0025 and 0028 (independent repair lifecycle and edit scope only)
---

# Use existing Candidate files and continuous developer chat

2026-10-23 确认：Developer GUI 四页纳入 Stage 3，须在 2026-10-29 前完成，作为 #329 的前置。为允许多轮开发而不丢失草稿，Candidate 改为由开发者从已有 Manifest 明确初始化/重建，非空时确认替换；修复和 New Conversation 不清空 Candidate。重建成功开启新对话，取消或失败保留原草稿和上下文。Runner 选择只决定后续执行的 Base Manifest，与 Candidate 基线和 Default 独立。

2026-10-23 的显式文件选择授权由以下 2026-10-24 决定替代。

2026-10-24 修订：取消 selected files 设置及 CLI 文件参数/`--all`。Agent 每轮可尝试修改 Candidate 内全部已有文件（含候选 `manifest.json`、Recovery Rule），`plan.json` 始终只读；不开放新建、删除、重命名、符号链接、目录外或正式源码写入。宿主按轮开始时的已有文件冻结边界，工具检查与结束快照共同执行约束。文件是否被 Manifest 引用、是否通过校验均不决定编辑权限；临时测试文件不新增警告，不自动登记 Component，新增 Component 接口留待后续。手动 Validate 在已有对话中立即写入 `context.json` 和事件日志，成功/失败在聊天区各只显示一次，失败保留详情入口；尚无对话时不隐式创建对话。此规则覆盖首次发送前、发送后和 New Conversation 后。

GUI/CLI 共用 pi 编辑工具与宿主检查。候选 Manifest 是可编辑草稿，正式 Manifest/源码及既有图片、旧标签仍按原约束保护；新增 Asset 继续只走 ADR 0028 的现场裁剪工具。完整候选校验和人工 Diff 审阅承担扩大编辑范围后的检查，不能把 Validator 当作操作系统沙箱或游戏行为证明。

同一对话保留上下文，每条用户消息触发一轮，允许纯文字和可选图片。请求上限按轮计算，默认 20、最小 2，自动模型检查消耗计入额度；每个对话使用一个按日期/UUID4 分组的交互目录，逐轮留存输入、工具、结果、配置与产物。人工审批直接通过 Diff/校验、主动 Publish 和独立设置 Default 完成，没有运行时 `Awaiting Approval → Applied` 流程。Diff 以初始化时固定的基础 Manifest 及哈希源码为准，跨 New Conversation 不更换基线。

Capture 人工裁剪必须预览并确认，保存框选时那张原图，不隐式重截；Agent 裁剪仍每次新截图。Runner 与 Agent 一轮处理互斥，手工截图/保存也与活动任务互斥，暂停仍占用；被动坐标与已有图片预览可继续。此决定不引入 Runtime Agent Recovery、Working Manifest 衔接、自动试跑或自动发布。发布分发推迟到 Stage 4 之后，不以包内携带 pi 或双包方案作为本期验收要求。

详见 [Developer GUI](../developer-gui-design.md)。四页与共享宿主已按此决定实现；自动化、真模型及 Windows 验收状态见设计文档，不能将代码完成视为全部验收完成。
