# Agent 的 Run 可见范围与大页面更新影响审查

2026-11-21 确认。内置 Agent 始终可查询本 Session 发起的试运行，Runtime Repair Session 还可查询触发自身介入的 Run，后续在工作台打开同一个 Session 时仍可查询。Agent Settings 的「允许查看其他 Run 的日志」默认开启，为 GUI 和 Runtime Repair 入口开放其他本机 Run。CLI 仅使用上述归属范围。按可见集合分页、搜索，并在读取 Trace、统计、原图或标注图之前检查权限。

- `RepairTools` 的 Run 工具此前直接使用本地 Trace 目录。列表、搜索和按 ID 读取要共享可见范围。设置缺失时使用开启默认值，下一轮 Agent 读取设置时生效。历史 Agent 对话检索有独立开关，远程 MCP 有独立授权，人工 Logs 页和导入日志也各自沿用现有入口。
- `ApplicationService.start` 以前只写入试运行标记。新增试运行的宿主 Session ID，并在创建 Runtime Repair Session 时记录父 Run。旧试运行可由同 Session 的 `trial_started` 关联，旧 Runtime Repair 可由 Trace 的 `agent_invoked` 关联。无法确定归属的旧 Run 仅在允许查看其他 Run 的入口可见。
- `RepairLog.stream` 每个工具参数分片都累计、脱敏并向界面发送完整前缀，界面的过程预览只使用文字和思考块。合成的 25 万字符分片产生了 1,954 次通知，累计约 2.44 亿字符。停止推送工具参数分片，保留完整工具调用和独立的详情。验证大源码 `page_update` 在启用实时通知时完整落盘，并检查一次工具调用的分片量不会放大成 GUI 事件。
- `TrialDialog` 以文字展示带截图引用的日志，图片预览由历史页异步解码并预留行高。离屏检查追加 20 条截图日志、跨过 300 条裁剪边界，以及主动上滚回看，均维持预期位置。将带截图的情形纳入现有回归。

验证顺序为普通权限／GUI 回归，再串行执行真实 pi 与本机替身的专项测试。Windows 成品与真实模型的交互性能另行验证。
