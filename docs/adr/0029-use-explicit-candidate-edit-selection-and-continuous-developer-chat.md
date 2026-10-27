---
status: accepted
supersedes: 0025 and 0028 (independent repair lifecycle and edit scope only)
---

# Use existing Candidate files and continuous developer chat

2026-10-27：后续 [ADR 0032](0032-use-python-plans-and-coexisting-user-developer-guis.md) 接受每 Manifest 唯一 Python Plan、同进程双 GUI 和 Candidate Plan 编辑/已发布试运行，按其列明范围替代本文的旧 Plan/GUI 边界；本文其余决定及历史实施证据保留，Stage 4 尚未实现。

2026-10-25：下文禁止 Developer Agent 自动 Publish/试运行的部分由 [ADR 0030](0030-developer-policy-publish-and-trial-tools.md) 替代，其余候选、编辑、素材及对话边界继续有效。

2026-10-23 确认：Developer GUI 四页纳入 Stage 3，须在 2026-10-29 前完成，作为 #329 的前置。为允许多轮开发而不丢失草稿，Candidate 改为由开发者从已有 Manifest 明确初始化/重建，非空时确认替换；修复和 New Conversation 不清空 Candidate。重建成功开启新对话，取消或失败保留原草稿和上下文。Runner 选择只决定后续执行的 Base Manifest，与 Candidate 基线和 Default 独立。

2026-10-23 的显式文件选择授权由以下 2026-10-24 决定替代。

2026-10-24 修订：取消 selected files 设置及 CLI 文件参数/`--all`。Agent 每轮可尝试修改 Candidate 内全部已有文件（含候选 `manifest.json`、Recovery Rule），`plan.json` 始终只读；当时不开放新建、删除、重命名、符号链接、目录外或正式源码写入；新建限制由下述专用工具增量修订。宿主按轮开始时的已有文件冻结边界，工具检查与结束快照共同执行约束。文件是否被 Manifest 引用、是否通过校验均不决定编辑权限；临时测试文件不新增警告，不自动登记 Component，新增 Component 接口当时留待后续，现由下述增量纳入范围。手动 Validate 在已有对话中立即写入 `context.json` 和事件日志，成功/失败在聊天区各只显示一次，失败保留详情入口；尚无对话时不隐式创建对话。此规则覆盖首次发送前、发送后和 New Conversation 后。

GUI/CLI 共用 pi 编辑工具与宿主检查。候选 Manifest 是可编辑草稿，正式 Manifest/源码及既有图片、旧标签仍按原约束保护；新增 Asset 继续只走 ADR 0028 的现场裁剪工具。完整候选校验和人工 Diff 审阅承担扩大编辑范围后的检查，不能把 Validator 当作操作系统沙箱或游戏行为证明。

同一对话保留上下文，每条用户消息触发一轮，允许纯文字和可选图片。请求上限按轮计算，默认 20、最小 2，自动模型检查消耗计入额度；每个对话使用一个按日期/UUID4 分组的交互目录，逐轮留存输入、工具、结果、配置与产物。人工审批直接通过 Diff/校验、主动 Publish 和独立设置 Default 完成，没有运行时 `Awaiting Approval → Applied` 流程。Diff 以初始化时固定的基础 Manifest 及哈希源码为准，跨 New Conversation 不更换基线。

Capture 人工裁剪必须预览并确认，保存框选时那张原图，不隐式重截；Agent 裁剪仍每次新截图。Runner 与 Agent 一轮处理互斥，手工截图/保存也与活动任务互斥，暂停仍占用；被动坐标与已有图片预览可继续。此决定不引入 Runtime Agent Recovery、Working Manifest 衔接、自动试跑或自动发布。发布分发推迟到 Stage 4 之后，不以包内携带 pi 或双包方案作为本期验收要求。

详见 [Developer GUI](../developer-gui-design.md)。四页与共享宿主已按此决定实现；自动化、真模型及 Windows 验收状态见设计文档，不能将代码完成视为全部验收完成。


## 2026-10-24 专用新增工具与图片附件修订

允许 Agent 通过 add_component / add_recovery_rule 专用工具提供 filename、logical_name、source，创建 Candidate Python 源码并在 manifest.json 的 components / recovery_rules 登记。文件与登记必须一起成功或回退；拒绝覆盖、重名、越界及受保护文件。工具成功创建的文件同轮即可继续编辑，并进入快照、Diff 和上下文；不开放通用新建、删除或重命名，不自动登记已有临时文件，也不自动执行或发布。该决定以可检查的专用新增路径取代全面禁止新建文件。

用户图片附件改为任意数量与实际图片 MIME，不再仅限单张 PNG；服务拒绝格式或载荷走正常错误流程，不自动删图、分批或转码重试。预检整组附件仍计一次请求。共享 Asset Library 的 PNG 契约不变。

Capture 增加默认 1280×720 客户区物理像素的手动窗口尺寸调整，保持位置、层叠顺序和焦点，受活动互斥约束；新增 Recovery Rule 教学示例，复用现有确定性恢复。以上不引入运行时 Agent Recovery 或游戏自动验收。详细边界及检查见 [Developer GUI 增量要求](../developer-gui-design.md)。这些增量已实现；自动化记录与 Windows/真实模型/真实游戏验收分开列示。Capture 同时提供固定原图像素的 5× 框选放大预览，不改变裁剪坐标和保存内容。
