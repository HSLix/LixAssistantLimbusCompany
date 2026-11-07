# 运行窗口日志

2026-11-07，经逐项讨论确认后完成影响审查并实施。这里指正式运行和 Agent 试运行共用的运行窗口，不改变独立 Logs 历史页。

## 已确认设计

- 单条按时间追加的日志流，每条用 Info／Warning／Error 色块，显示等级、逻辑名和对应信息。无逻辑名的整体状态显示“运行”；深浅主题均保留明确等级文字。
- 仅展示非 Debug 的 `component_log` 及开始、暂停、恢复、停止请求、结束和执行异常状态。不提供 Debug 开关，不展示 Trusted Action 明细或窗口检查等内部诊断。
- 业务消息保留原文，不解释为 HTML。异常正文显示状态及简短原因，完整异常栈和原始字段通过“查看详情”打开并可复制，不再次追加到主日志。
- 原始 Trace 完整保留。暂停、恢复、停止及暂停后提示用户的行为沿用现有控制路径。阅读旧消息时不强制滚到末尾，位于末尾时继续跟随追加。

## 影响审查

旧行为是 `TrialDialog.render` 把全部 Trace 转成 JSON 输出，业务日志同时输出摘要和 JSON，暂停时再输出异常栈。新行为仅改变 GUI 投影。

确认影响：

- `src/lalc/gui.py` 的正式运行入口和 Developer 入口都创建 `developer_gui.TrialDialog`，因此共用一次修改，不新增执行路径。
- `application.py` 已记录 run_started／run_paused／run_resumed／run_cancel_requested／run_finished；`runtime.py` 已记录 paused_by_user／input_resumed／input_resume_rejected 等，无需扩展 Trace 数据契约。
- `developer_gui.py` 新增明确的展示事件集合，过滤 Debug 和内部事件；使用现有 TextBrowser 显示色块，现有 ErrorDialog 展示详情。
- `tests/test_developer_gui.py`、`tests/test_input_control.py` 原先要求主日志包含 JSON／异常栈，需要随已确认设计更新。GUI 中英文翻译资源同步。
- `run_logs.py`／`run_log_gui.py` 的历史页、Sharing 导出、Agent 读取日志、执行器权限和持久化不变，无数据迁移。

潜在风险：富文本显示必须转义日志内容并禁止外部链接；长时间运行仍会累积窗口日志，本次不引入分页。结束后窗口仍按原流程关闭，最终结果由原有通知／Agent 工具结果承接。

## 验证边界

针对性测试覆盖展示过滤、旧业务日志默认 Info、状态映射、原文转义、详情完整性、重复刷新、Trace 不变、暂停焦点及控制行为、中英文资源。离屏预览检查等级色块和详情入口。实际执行结果由本次交付记录报告，不把离屏测试视为 Windows 或真实游戏验收。

本次已执行：Developer GUI 48 passed；输入控制及 GUI 语言 52 passed，正式运行入口 11 passed、2 skipped。三套测试串行退出，合计 111 passed、2 skipped；`git diff --check` 通过。浅色／深色离屏截图已检查。未运行 Agent 测试、全量回归、Windows 实机或真实游戏验收。
