# #338 — GUI 同轮人工反馈实施记录

2026-11-01。开发者确认[关键决定](stage-5-338-decisions.md)和[影响审查](stage-5-338-design-impact-review.md)后明确“开始实现”。已本地交付，尚待开发者人工验收；#338 保持打开，不将自动检查计为开发者验收。

## 使用与边界

GUI Construct / Repair 的 Agent 均可调用 `request_feedback(message)`，展示希望与用户 / 开发者交互的内容或意图。只有一个文字输入组件，不区分提问或人工操作类型，不增加选项表单、反馈图片或操作成功勾选框。

- 普通非模态窗口不置顶，可切换游戏；不设自动超时。等待期间保持应用活动与 Session 锁，禁止切换 / 新建 Session，也不执行后续试运行或自动输入。
- Confirm 可直接空答复，工具结果为 `{"status": "confirmed", "text": ""}`；有文字则返回实际文字。Skip / 关闭 / Esc 返回 `{"status": "skipped", "text": ""}`，不把未提交输入当作答复。
- 取消本轮结束当前轮次，唤醒并作废等待；主窗口退出仍先询问是否取消，拒绝退出则保留等待，同意则等待实际清理后退出。已经完成的旧反馈窗口不能取消后续工作。
- 人的答复不证明游戏目标达成，不隐式恢复暂停，也不批准页面安装或永久授权。Agent 按需要再用现有截图工具观察；跳过后继续独立工作或说明缺少必要信息，不反复追问同一跳过事项。
- 请求内容及结果沿现有工具调用链按 Session / 轮次 / toolCallId 记录，使用既有脱敏；结果返回当前上下文，不开启新轮次或重置请求额度。跨入口恢复保留历史，CLI 不因此获得新工具权限。
- 应用意外退出后未完成调用沿用 unknown / interrupted 语义，不自动恢复弹窗或重放；确认尚未落盘时不补造确认。

## 实现范围

`agent_policy.py` 将工具加入 GUI 两种模式交集，默认基础工具 / CLI 不变；`pi_probe.ts` 注册单一 message 参数的工具，并保持模型声明与实际调用权限检查。Runtime 未接入，不继承 GUI 授权。

`RepairConversation.run` 每轮接收 GUI 回调，在既有串行宿主调用及取消收尾路径内等待；`RepairTools.request_feedback` 校验非空请求与 GUI 桥接，复用标准工具结果、日志和错误返回。`human_feedback.FeedbackRequest` 使用线程事件与锁实现一次结算，绑定会话、轮次与调用序号，结束后迟到答复无效。

`MainWindow.feedback_requested` 把请求交给 GUI 线程，`RepairPage.show_feedback` 拒绝结束 / 退出 / 其他 Session 的请求，`FeedbackDialog` 提供内容、可空输入、确认 / 跳过 / 取消。窗口轮询请求结束以关闭，不把该轮询当作人工超时。已补中英翻译、输入可访问名称及文字换行。

共用 Prompt 已调整为按实际工具权限请求反馈，保留最终格式纠正时禁用工具。未新增依赖，未迁移旧数据，不改 Manifest / Default / Runtime 状态机，不实现 #339 / #340 页面能力。

## 验证

普通检查：

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_human_feedback.py tests/test_developer_gui.py tests/test_gui_language.py tests/test_agent_repair.py tests/test_developer_session.py tests/test_repair_tools.py tests/test_agent_prompts.py tests/test_knowledge.py tests/test_developer_policy.py
```

串行运行 **179 passed**。随后补充“已完成旧窗口不能取消后续工作”的检查及窗口可访问文案，重跑 `tests/test_human_feedback.py tests/test_gui_language.py`：**36 passed**。两次覆盖有重叠，不相加；最终普通检查涉及 180 个不同用例，未运行全量回归。覆盖空确认 / 文字 / Skip / close / Esc、无模态 / 非置顶、主窗口退出两分支、两处取消出口、取消唤醒、重复 / 迟到回调、跨 Session 请求拒绝、中断 unknown 不重放、CLI 权限及日志脱敏。

新增真实 pi + 本地 HTTP 服务替身反馈专项：`tests/test_developer_session_agent.py -k feedback --run-agent-tests` 为 **9 passed, 14 deselected**，覆盖 GUI 两种模式、同轮请求计数及上下文、CLI 隐藏与实际拒绝、批量人工请求先于试运行、取消回收与实际 GUI 信号 / 空确认链路。

受影响 Agent 回归：

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --run-agent-tests -q tests/test_developer_session_agent.py tests/test_agent_repair_agent.py -k 'not real_model and not windows and not unloaded_model and not deepseek_thinking_survives_tools_and_next_round'
```

串行 **59 passed, 9 deselected**；排除项为真实模型 / Windows / unloaded_model 等 5 项，以及缺少 `probe` fixture 的 4 个既有 DeepSeek 用例，均不计通过。最初检查受本机服务监听权限限制，未执行；允许本机测试监听后反馈专项通过。一次扩大检查被并行普通检查争用全局游戏锁干扰（56 passed、3 failed、4 fixture errors），已停止受影响的普通测试进程并改为串行重跑，得到上述结果；未修改互斥策略以绕过测试。

最后补充取消后排队请求不得弹窗的检查，重跑人工反馈与语言专项仍为 **36 passed**。未修复与本票无关的旧 DeepSeek fixture 缺口。

中文窗口已用 offscreen 渲染并人工检查内容、输入、按钮与换行；翻译资源已编译，`git diff --check` 检查通过。

## 待开发者人工验收

1. 在 Construct / Repair 分别让 Agent 请求人工反馈，输入文字或完成游戏操作后空确认，观察同轮继续。
2. 分别用 Skip、Esc、关闭反馈窗跳过；等待时切换游戏，检查无并行自动输入，且不能切换 / 新建 Session。
3. 分别从反馈窗口和工作台取消，再测试主窗口拒绝退出 / 确认退出；重启后检查中断历史且无自动弹窗或重放。

本地服务替身不代表真实模型行为；offscreen 不代表 Windows 原生 / 成品窗口焦点或真实游戏验收。本票尚未调用真实模型、操作真实游戏或验证 Windows 成品，4 项缺失 fixture 的既有 DeepSeek 测试仍是维护缺口。开发者确认后再记录反馈并关闭 #338。
