---
status: accepted
supersedes: 0029 (Developer Agent automatic Publish and execution prohibition only)
---

# Developer Policy uses Publish and trial tools

2026-10-25：Developer Agent 负责按开发者 prompt 和游戏状态持续开发，与 Stage 3.5 的运行中维护分开。一次用户消息授权本轮自主修改、完整校验、Publish、试运行和查日志；试运行返回实际结果后可继续开发，不是 Runtime Policy 的终结式控制权交接。复用现有发布、执行和 Trace，无需新增并行执行器或运行时 Policy 实现。

Publish 保存完整不可变 Manifest 及内容哈希源码，不授予运行时永久批准、不改变 Default；试运行必须显式指定已保存的 Manifest ID，修改 Candidate 后须重新 Publish。支持 Candidate 内只读 JSON Plan 或 Task Workflow、Subworkflow、Step 入口及输入。启动拒绝不创建 Run ID；实际运行的结果必带 Run ID。两个只读工具分别列出可用 Run ID、按指定 ID 分段查看 Trace 和引用截图，不增加内容搜索。

GUI 试运行使用模态日志子窗口阻止操作 Developer GUI，显示时不主动抢游戏焦点，不要求系统级置顶；仅提供日志、暂停/恢复及停止。人工暂停或接管只能人工恢复。正常结束、失败、停止后关闭窗口，将结果交回当前 Agent 工具调用并沿用本轮额度。停止只终止本次运行，提示“用户主动停止了本次运行，建议总结并等待用户的下个指示”，不新增工具限制；取消本轮则停止当前试运行、等待输入释放和日志收尾，再回收 Agent。

Candidate 生命周期、固定 Diff 基线、plan.json 只读、受限编辑/新增和既有图片标签保护保持 ADR 0027–0029 的约束。Runtime Policy 及 plan.py 参数化循环/恢复接续不纳入本次实现。
