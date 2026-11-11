---
status: accepted
---

# 共享 RunState，并以现有 Agent Session 完成运行时修复

2026-11-11 开发者逐项确认：Stage 6 的恢复边界扩展到 Plan、Task Workflow、Subworkflow、Step 各自的执行失败。框架保留仍在等待的调用者，修复后重新调用失败入口，实际返回仅交付一次；不恢复失败帧内部代码行，也不把下层修复终止当作外层调度错误再次修复。业务代码自行决定重新进入时如何继续。

为保留必要配置和进度，执行器为一次 Run 持有共享、仅在内存中的 RunState，正式 Plan 的 `task_repetitions`、`settings` 参数迁入 `ctx.run_state`，不保留旧 Plan 参数兼容层。业务代码（包括 Recovery Rule detect/recover）可直接修改业务状态，即时共享且失败不回滚；普通调用参数仍保留独立快照。RunState 不自动回写用户配置，不支持进程退出后续跑。框架维护的连续恢复计数对业务代码只读；Agent 只获得查看工具，无直接修改工具或权限。

Runtime 使用现有 Repair Session、Candidate、固定基线、对话、工具循环和日志，以介入时 Working Manifest 初始化，程序组织故障 Prompt 和执行反馈。Recheck 交回 Runtime 控制权，不递归新建 Agent 会话；多轮修复共用恢复会话请求额度，默认 `max_requests=50`。Run 结束后同一 Session 可在 Developer GUI 接续，已结束 Run 的状态与执行权不会复活。相比另建 Runtime Session／Repair Process，这保持单一会话机制，但必须调整现有活动互斥和每轮预算清零的实现。

取消新修复版本执行前的人工审批；先填写 `AdditionalMessage` 简述问题，完整校验并 Publish，再选择已保存 Manifest 进行当前失败入口的 Recheck。允许新增／修改 Manifest Recovery Rule，不授权修改内置规则、Trusted Actions 或删除资源。非必要不修改调用约定作为 Skill 建议，宿主不强制修复前后签名／返回类型一致；普通参数绑定、返回校验及角色关系检查保留。Runtime 不开放独立 trial_run，不执行可变 Candidate。

每次恢复先检测一轮规则：唯一匹配执行 recover；歧义或规则自身普通错误反馈 Agent。普通失败时零匹配交 Agent，Recheck 前零匹配直接执行修复入口；再次失败仍进入同一恢复流程。连续 recover 成功次数默认上限 10，在 User GUI 可查看修改；Step 正常返回或真正交由 Agent 介入时清零。内置崩溃恢复计入同一计数，取消每 Run 最多自动重启一次的独立限制，重启失败等不可继续环境错误仍终止。请求额度耗尽时当前 Task 返回 `status=failure`，Plan 决定后续调度；Plan 自身无法修复则结束 Run。

User GUI 提供默认开启的“运行成功后自动使用修复版本”选项。2026-11-11 开发者反馈修订：只在 Plan 正常结束、清理及必要记录成功后，以最终 Working Manifest 更新 Default，再显示切换成功提示；替代此前无论结果都更新的决定。Plan 仅须 `status=completed`，不要求 `all_tasks_succeeded=true`，即使包含最终失败的 Task 也可切换；直接 Component Run 须 `status=success`。取消、Plan 中断、直接 Component 失败或收尾故障不自动切换。Publish 本身仍不修改 Default，Developer Agent 不因此获得设置 Default 的工具。

Runtime 可复用只读知识库／Skills／历史及关联日志。Developer GUI 的历史检索总开关默认开启，覆盖所有 Agent 模式／入口；User GUI 的 Runtime 人工反馈开关默认关闭。两者下一轮生效，每次工具调用检查该轮固定权限，不动态重读设置；关闭历史访问不清除已读上下文或停止记录日志。

开发者最终撤销专用素材反向引用工具及配套文件方案；本阶段不新增 Component 调用图、正向／反向引用工具，也不在 Publish 或查询时生成依赖分析文件。Agent 通过现有素材查看、Manifest 成员和源码读取定位引用，避免为非必要查询维护额外索引。

## 替代范围与限制

本 ADR 在上述范围内替代 ADR 0004／0013 的 Step-only 恢复、0014 的独立三类最终 Turn 结果与规则不可改约束、0015／0017／0018 的执行前审批和硬性续接兼容要求、0032 的 Plan 错误直接结束阶段限制、0034 的 Session／权限相关旧约束，以及 0039 的每 Run 一次重启限制。普通 Component 执行、不可变保存、Trusted Actions 权限、取消／接管、原始诊断与必要持久化失败终止仍保留。源码执行不具备安全沙箱保证。

开发者后续确认删除 ADR 0016 的运行后永久批准流程，不保留独立批准窗口／状态门槛；Validate、Publish、执行选择与 Default 更新职责分开，其他开发页面审批保留。所有 Run（含直接 Component 与 Developer Trial）在启动边界初始化 RunState；连续恢复上限和自动使用修复版本选项在 Run 开始固定，历史／人工反馈开关仍下一轮生效。剩余范围见[影响审查](../stage-6-design-impact-review.md)。本 ADR 记录接受的目标设计，不表示源码、真实模型、Windows 或游戏验收已完成。

完整需求和决定来源见 [Stage 6](../stage-3.5-agent-runtime-step-recovery-and-maintenance.md#2026-11-11-设计讨论已确认边界)。

## 实施时补充确认

所有启动入口的 `use_saved_config` 默认为 True，读取保存的页面配置和启用任务次数；False 才使用显式 RunState 初始数据，省略为空。Developer 独立试运行不启动 Runtime Agent，失败交回原 Developer Agent。Default 写入失败保留已完成的执行结果和旧 Default，另行通知。重启恢复达到统一上限且 Agent 未启用或无法介入时终止整个 Run，无需额外确认游戏退出。

旧已发布 Manifest 允许只读、校验路径和源码哈希后复制为修复草稿；复制不导入或执行代码。修改旧 Plan 签名并完整校验后才能重新发布，仍不提供旧参数兼容层。实施及验证见[Stage 6 记录](../stage-6-implementation.md)。
