# pi 收尾聚合事件：设计与影响审查

2026-11-09，开发者经逐项讨论确认以下设计，随后授权实施。

## 接受设计

- 原行为：stdout／stderr 单行超过 16 MiB 均立即失败，stdout 完整解析后入队。
- 新行为：仅当行首明确识别出顶层 `type: "agent_end"`，分块消费到换行，不解析、不保存其 messages／willRetry；正常和超大事件均仅记录类型、实际字节数及负载省略标记。
- 普通事件保留 16 MiB 限制。未在受限行首识别出类型时，不猜测、不扫描正文；普通解析仍允许不同字段顺序，超限则失败。
- 超限诊断包含通道、确认的类型或 unknown、已读取字节数下界、上限、最近成功事件及原因，不包含原始正文。
- 省略事件未读到换行即 EOF，仍为通信错误；完整省略后必须继续等待 agent_settled，未收到而退出仍失败。完成与取消沿用现有业务判断，不因 agent_end 提前完成。

## 证据与影响

官方 v1.5.0 的 [agent-loop.ts](https://github.com/earendil-works/pi/blob/v1.5.0/packages/agent/src/agent-loop.ts) 将模型消息和工具结果累积到 newMessages，结束时发送 agent_end.messages；[agent-session.ts](https://github.com/earendil-works/pi/blob/v1.5.0/packages/coding-agent/src/core/agent-session.ts) 保留 messages 并添加 willRetry；[json-event.ts](https://github.com/earendil-works/pi/blob/v1.5.0/packages/coding-agent/src/modes/json-event.ts) 不裁剪该事件，RPC 将其序列化为单行。

确认的实现差距：`PiProcess._read` 在识别类型前执行统一大小检查；`AgentRepair.run` 先通过 RepairLog.record 保存所有非流式事件，但仅从 message_end 更新最终答复、从 agent_settled 判断完成，不消费 agent_end 的 messages／willRetry。已有逐条消息日志继续保留证据，聚合事件仅保留接收记录。

调用链：pi RPC stdout → PiProcess._read → events 队列 → pi_probe.rpc_session 缓冲 → AgentRepair.run → RepairLog.record。stderr 保持独立读取且不应用 agent_end 省略规则。进程复用、权限、工具、额度、会话存储及模型参数均不改。

潜在风险：现场超限行在解析前已被拒绝，不能证明它就是 agent_end；本次修复针对已由上游源码确认的可达路径。行首识别依赖已核对的 v1.5.0 序列化顺序，未来字段顺序变化将退回普通受限处理，不误判正文里的类型。省略模式不验证被丢弃的完整 JSON，适用对象仅为宿主持有的 pi 输出。

## 实施顺序与验证边界

1. 读取层增加有界分块消费与脱敏诊断；保留业务完成判断。
2. 文档明确聚合负载省略和版本边界，不新增领域术语或 ADR：这是局部可逆的协议适配，不改变 Stage 5 架构。
3. 使用内存字节流验证普通／超大 agent_end、后续 settled、截断、未知与关键事件超限、stderr、类型误判与分块边界；模拟进程验证没有 settled 的退出仍失败。

## 实施与验证

已在 `src/lalc/pi_process.py` 完成行首识别、64 KiB 分块消费、接收标记及超限／截断诊断；不变更 AgentRepair 的完成或取消策略。`tests/test_pi_process.py` 新增 12 项内存流／模拟进程检查，其中超大负载实际超过 16 MiB，流替身还断言单次读取申请不超过 64 KiB。`tests/test_agent_repair_agent.py` 新增真实 pi 接收标记与逐条证据保留检查。

默认针对性回归：

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_pi_process.py tests/test_pi_startup.py tests/test_agent_repair.py tests/test_raw_output.py tests/test_pi_resources.py
```

80 passed。此前无 offscreen 的扩展检查在 macOS qframelesswindow 创建窗口时退出 139，不记为通过；上述命令重跑正常退出。

真实 pi／本机 HTTP 模型替身检查（与默认回归分开执行）：

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --run-agent-tests -q tests/test_agent_repair_agent.py -k 'agent_end_is_logged or text_only_and_context_retained or cancel_reaps_process or transport_error_preserves'
```

7 passed，39 deselected；覆盖真实结束事件、跨轮上下文、取消及连接／响应体异常。首次受限环境无法绑定本机测试服务，7 项均 setup error；允许本地服务后上述检查通过。未运行整个 Agent 集合；超大事件由内存流验证，不宣称真实 pi 超大图片场景已重现。`git diff --check` 通过。

未执行真实模型、Windows 成品或游戏验收；现场超限事件身份仍未由原始行证明。`agent_settled.aborted` 在读取层测试中原样保留，业务取消策略沿用现状，本次不新增基于该字段的完成策略。
