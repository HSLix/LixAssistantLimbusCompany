# Agent 临时原始输出与取消自动推理预检：实施记录

2026-11-01。已按[确认决定](agent-raw-output-decisions.md)和[实施前影响审查](agent-raw-output-impact-review.md)完成本地实施。

## 行为

- Construct / Repair 聊天记录内，在本轮用户消息之后、Agent 工具与回答之前显示状态行。状态文字作为原始输出的折叠标题，每条模型消息默认收起，可随时展开 / 收起；展开内容随聊天记录滚动。底部不再提供独立原始输出面板或可见状态栏。
- 展示接口实际提供的文字、thinking、工具名称及尚未完成的 JSON 参数；完整消息按轮次保留，最终回答后仍可折叠查看；续聊不覆盖旧轮次。取消、错误或空闲收尾只清除未完成缓冲。每轮默认收起，同轮保留用户选择。
- pi 1.4.0 的 RPC `message_update` 只有内容块增量，不带完整消息快照。`RepairLog.stream` 按 contentIndex 累积，再以现有规则脱敏通知 GUI；正式完整消息照常保存。临时增量不逐片落盘、不进入模型上下文；完整生成过程从已有 message_end 记录恢复。
- GUI 将原始内容转义为只读纯文字，与状态行一起呈现在 Agent 回复顶部；50ms 合并展开内容绘制，收起时只更新临时缓冲，沿用聊天查看较早内容时保留滚动位置的规则。取消 / 退出后拒绝排队的流式通知，终止时停表并清空。
- GUI / CLI 共用正式循环不再调用独立推理预检；第一份正式请求编号为 1，格式纠正仍计入本轮额度。原图直接进入正式请求并保持跨工具 / 重试 / 续聊的原始字节和顺序。
- 设置页原有手动连接 / 模型状态检查未改动，仍只读取模型列表 / 状态；配置和图片元数据校验、工具白名单、请求上限、禁用自动重试、取消及 pi 请求前唯一回退保持。
- 删除无调用者的自动推理预检函数及其扩展分支 / 测试替身逻辑，同步更新相关请求数、前缀断言、文档和中英翻译。没有新增依赖、配置、Session 格式或历史迁移。

## 验证

相关普通回归：

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_raw_output.py tests/test_agent_diagnostics.py tests/test_developer_gui.py tests/test_workbench_status.py tests/test_agent_repair.py tests/test_agent_settings.py tests/test_pi_startup.py
```

**170 passed, 1 skipped**。覆盖折叠选择、连续内容、未完成工具参数、纯文本、结束 / 取消 / 退出 / 重试清理、排队事件拒绝、历史隔离、累计脱敏、手动检查及启动回退。

相关显式 Agent 回归，真实 pi + 本机 HTTP 替身：

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -x --run-agent-tests tests/test_agent_repair_agent.py tests/test_developer_session_agent.py
```

**76 passed, 4 skipped**。覆盖文字 / thinking / 工具增量在 message_end 前到达且不落盘、无独立推理预检、一次直接回答只发一次请求、预算重置 / 硬上限、格式纠正、工具权限、图片原字节、多轮前缀、错误与取消、GUI / CLI Session 及人工反馈。

默认收起 / 展开界面已通过 offscreen 截图目检：本机临时产物 `/tmp/lalc-raw-collapsed.png` 与 `/tmp/lalc-raw-expanded.png`。该检查替代 macOS offscreen 下无法使用的原生标题栏调用，不证明 Windows 实机表现。

## 检查限制

- 初次 Agent 测试因环境禁止本机监听未能建立服务，允许本机替身服务后重跑；一次普通检查与 Agent 检查并行争用项目的游戏互斥锁，最终均串行通过。中间失败不计通过。
- 普通全量回归曾在约 43% 后持续无输出，已终止；未取得最终报告，阻塞原因未确定，因此不声称全量回归通过。最终上述相关文件串行通过。
- 未调用真实模型、构建 Windows 成品或执行游戏现场验收。跳过项不计通过；等待开发者现场试用确认。


## 布局纠正后的验证

2026-11-01 用户提供截图后，改为内联折叠状态行。只修改 GUI 呈现，未改变 Agent 事件或预检行为。

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_raw_output.py tests/test_repair_chat.py tests/test_workbench_status.py tests/test_chat_ui.py tests/test_developer_gui.py
```

**105 passed**。新增验证同轮用户消息 → 状态 / 原始内容 → 工具 → 最终回答的顺序，以及折叠默认值、状态替换、终止清理与历史隔离。默认收起、展开、完成三种界面已目检，本机临时截图为 `/tmp/lalc-inline-raw-collapsed.png`、`/tmp/lalc-inline-raw-expanded.png`、`/tmp/lalc-inline-raw-finished.png`。未重跑 Agent 集成或全量回归，未执行 Windows 实机验收。


## 最终回答后保留生成过程

最新用户决定替代结束清空：每轮折叠区包含该轮所有完整模型消息的文字 / thinking / 工具名称与参数，回答完成后仍保留；实时增量单独显示，完整消息到达后提交一次，避免重叠。新一轮使用独立折叠区。完成后的内部刷新保留已选展开状态，主动重开历史默认收起。取消或报错丢弃未完成增量，保留之前完整消息。

复用原有脱敏、去重的 message_end 事件重建，无需新增存储或迁移，不更改模型上下文。仅修改 GUI 与历史呈现，未改变 Agent 进程协议。

相关 GUI 回归采用上一节相同命令：**107 passed**，包含新增的最终回答保留、同轮多条消息、后续轮次独立展开、历史重开及取消时保留已完成内容检查。未重跑 Agent 集成、全量回归或 Windows 实机验收。
