# Runtime Repair 历史展示与发布说明影响审查

## 确认决定

- 历史轮次完成 Recheck 交接时显示「已交回执行器」、提交的 Manifest ID 和父 Run 编号。Run 的执行结果在运行日志查看。父 Run 编号缺失时明确显示未知。
- 进入 Developer GUI 的 Agent Workbench 自动刷新 Session 列表。打开已有 Session 时，在后台读取必要的历史及列表数据，继续优先展示最新轮。
- Workflow Skill 要求每次发布前更新 Candidate Manifest 的 `AdditionalMessage`，概括本版的主要改动。Developer 可直接编辑 Candidate Manifest，Runtime 继续使用发布工具的必填 `summary`。

## 影响与证据

- `RepairConversation.run` 已保存 `executor_handoff`。`RepairPage.show_result_status` 未识别该原因，因此两份共享样本都显示「本轮未完成」。两份样本均关联 Run #348，Trace 中分别有 `sub_workflow.event` 和 `step.wait_battle_end` 的正常重试返回。历史 GUI 只需交接结果和标识，后续执行仍由 Trace 记录。
- 旧样本每轮结果已有 Manifest ID，父 Run ID 在宿主生成的故障说明中。新增交接结果直接保存父 Run ID，旧结果按固定说明格式回读即可。两者都无需打开 Run Trace 或重放操作。
- `RepairPage.open_session` 已在后台展开聊天事件，随后在 GUI 线程恢复时仍重复刷新列表和版本，并在逐条回放中查询服务状态。两份样本在 macOS 离屏回放各低于 0.1 秒。Windows 的具体耗时需在原安装环境复核。样本附带的父 Run Trace 各约 487 MB，打开交接历史无需读取它。
- `validation-and-trial` 已说明 Runtime 的 `summary`，Developer 发布前缺少更新附加信息的步骤。已有 Candidate 编辑权限足够，发布接口和校验门槛沿用现有契约。已初始化的自定义 Skills 需要手动合并随包更新。

## 验证路径

先检查最新轮及旧日志兼容，再检查页面进入与打开会话的刷新行为、已有分页和聊天状态，最后用两份附件核对 Manifest ID 和 Run 编号。原安装上的 Windows 响应时间需实机核对。

## 实施验证

- 两份附件的轮次结果分别恢复出 Manifest `32688f08-1e0f-430a-91cc-b03cac5ff244` 和 `b16fd0b3-031d-4ba8-b6ac-f73023395c6f`，父 Run 均为 #348。macOS 本次读取和摘要生成分别约 31 ms 和 38 ms。
- 相关普通回归 258 项通过。中文窄窗口的工具栏宽度断言失败 2 项，均在改动前的 GUI 源码上复现。
- 真实 pi 与本机模型替身的定向集成测试 1 项通过，确认新交接结果保存父 Run 编号和提交的 Manifest ID。Windows 和真实模型尚未验证。
