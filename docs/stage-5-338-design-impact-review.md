# #338 — GUI 同轮人工反馈设计影响审查

2026-11-01 更新：开发者已确认本审查并明确“开始实现”；当前本地交付见[实施记录](stage-5-338-implementation.md)。下文保留实施前源码状态与审查证据，不代表当前差距清单。

2026-11-01。基于[已确认决定](stage-5-338-decisions.md)、Stage 5 规格和 ADR 0034。已检查本地源码、调用链及相关测试源码；本次未执行测试、未启动 pi / 模型 / 游戏，未修改实现。实施须等待开发者确认本审查；关闭 issue 须另等开发者验收确认。

## 设计增量

既有目标是 GUI Construct / Repair 在同轮请求人工答复或操作反馈。此次明确：统一内容与文字输入，不区分请求类型；Confirm 可空答复，和 Skip 分开；普通非模态窗口，不置顶；不设自动超时；关闭 / Esc 为 Skip，取消本轮为终止。旧规格“记录请求类型”被请求内容、选择和答复取代，已同步正式规格。

保持不变：GUI 两种模式可用，CLI / Runtime 不继承；等待保持 Session 和应用活动互斥；反馈不证明游戏状态、不解除人工暂停、不替代安装批准；脱敏、同轮额度、退出清理、中断不重放继续生效。无需新 ADR、术语或存储迁移：CONTEXT.md 的 Human Intervention Request 与 ADR 0034 已覆盖该领域概念，本轮仅细化交互契约。

## 已确认的实施差距与影响

### 1. 工具声明与宿主权限须同时接入

证据：`src/lalc/agent_policy.py:BASE_TOOLS / MODE_TOOLS / ENTRY_TOOLS / allowed_tools` 当前只有基础与知识库工具。`src/lalc/pi_probe.ts` 的工具注册数组、`authorize` 与宿主 `src/lalc/repair_tools.py:RepairTools.call` 的方法表均无人工反馈入口。`RepairConversation.run` 每轮重新计算权限并经环境传给 pi，`configure_session` 校验实际工具集。

影响：应新增一个统一内容参数的工具，只加入 GUI Construct / Repair 交集；模型 Schema 与宿主调用均校验权限及非空请求文本。不把它加入默认 BASE_TOOLS，避免 CLI 等默认消费者意外继承。宿主无 GUI 桥接时应明确失败，不能永久等待或伪造 Skip。历史 GUI 工具记录不能影响 CLI 当前权限。

### 2. 后台工具与 GUI 线程之间缺少可取消反馈桥接

证据：`src/lalc/agent_repair.py:RepairConversation.run` 的 `extension_ui_request` 仅识别内部 validate 与 lalc.tool；后者通过 `asyncio.to_thread(tools.call, ...)` 执行，并在取消后设置 `tools.cancelled`、等待线程收尾。`src/lalc/developer_gui.py:RepairPage.send / show_event` 将日志事件送到 GUI，但没有请求 / 应答桥接。`src/lalc/gui.py:MainWindow.cancel_operation / closeEvent` 已支持取消任务并等待实际清理。

影响：复用现有工具返回路径，增加最小 GUI 桥接；GUI 线程创建普通非模态窗口，后台等待真实响应，取消必须唤醒等待。不得在工具线程创建控件，也不得复用 `TrialDialog` 的模态与不可关闭行为。请求须绑定 Session、轮次及调用身份；只结算一次。取消或结束时使旧请求失效并关闭窗口，迟到 / 重复回调不得写入新请求。主窗口拒绝退出时保留原等待，同意退出时先取消清理。

超时边界：`src/lalc/pi_probe.py:rpc_event` 的 30 秒超时用于就绪 / 配置等待；`RepairConversation.run` 正常轮次直接等待事件。人工等待不应复用该 30 秒配置超时，也不应删除进程清理等已有技术超时；不设人工自动超时不等于屏蔽进程退出或协议错误。

### 3. 既有互斥可复用，批量工具顺序须验证

证据：`RepairConversation.run` 整轮持有 Candidate 锁与 `service.activity("Agent")`；`src/lalc/application.py:ApplicationService.activity / start` 阻止外部运行，但为 Agent 串行试运行保留内部入口。`RepairPage.is_busy / render / update_actions` 和 `MainWindow.launch` 已阻止活动期间切换 / 新建 Session 及手动活动。`tests/test_developer_gui.py:test_async_operation_and_host_busy_state` 检查部分禁用行为。`tests/test_agent_repair_agent.py:test_single_model_response_can_call_multiple_host_tools` 证明一条模型回复可含多个宿主调用。

影响：等待时不释放这些锁，不新增独立后台 Session；窗口非模态不代表应用业务活动解除互斥。宿主需保持逐个处理工具请求，人工反馈返回前不得运行批次中的 trial_run 或其他自动输入。不能只依靠按钮禁用或提示词保证这一点。不得新开模型轮次等待回复；反馈作为当前工具结果返回，沿用原请求计数。

### 4. 日志与恢复应复用工具结果，而非另造用户轮次

证据：`src/lalc/agent_repair.py:RepairLog.record / clean / tool_result` 统一脱敏并保存 / 转发事件；`RepairTools.call` 使用 toolCallId 记录 repair_tool；pi 将结果读回当前工具调用。`src/lalc/developer_session.py:restored_history` 可由 repair_tool / tool_execution_end 补齐已记录结果，未完成调用恢复为 unknown，不自动重放。`tests/test_developer_session.py:test_restart_restores_associations_marks_unknown_and_keeps_evidence` 验证此机制。

影响：请求与反馈沿相同日志和工具结果路径进入当前上下文，保留 confirmed + 空字符串与 skipped 的明确区别。取消走轮次取消流程，不转换成确认或跳过；意外退出不恢复弹窗。若人已确认但结果未成功落盘，仍按既有 unknown 边界处理，不能宣称已获得确认。避免为“请求类型”另建字段或重复保存新的顶层用户消息。GUI 临时回调对象不得写入持久 JSON。

### 5. 共用提示词存在直接冲突

证据：`src/lalc/agent_prompts.py:CORE_PROMPT` 当前要求“信息不足时说明缺少什么并结束本轮”，即使未来工具开放也会抑制同轮反馈。`pi_probe.ts:before_agent_start` 依据实际启用工具生成 Tool Guidance。

影响：改为按实际可用工具请求必要反馈；Skip 不推断完成或授权，可继续独立工作，缺少必要信息则如实报告阻塞。CLI / Runtime 不得被提示为可用 GUI 工具；格式纠正阶段仍禁用所有工具。不扩大反馈到安装确认、Default 修改或通用游戏输入。

## 潜在风险及验证方式

- **取消竞态与挂起**：尚无新增桥接，无法证明取消、Confirm 同时发生、排队信号在轮次结束后才到达时的行为。用可控后台等待验证只结算一次、取消后线程与 pi 回收、旧响应不影响新请求。
- **同响应多工具调用**：现有测试检查所有结果进入下次模型请求，未检查人工等待期间的执行顺序。需批量发起“人工请求 + trial_run / 截图”，确认反馈前后没有重叠执行；同时覆盖等待时用户取消。
- **窗口与焦点**：offscreen 可检查非模态、非置顶、Esc / close、按钮与主窗口退出分支，不能证明 Windows 游戏焦点切换、任务栏找回窗口或打包应用行为。后者由开发者实机验收，不计入本地替身通过。
- **日志敏感内容**：复用脱敏仍应验证答复包含已知密钥时，持久日志、模型上下文及错误反馈均按既有规则处理；不声称任意未知敏感文字都会被自动识别。
- **旧测试不等于新功能验收**：已检查的取消 / 权限 / 恢复测试覆盖基础设施，不覆盖尚未实现的交互；本次未执行这些测试。

## 实施顺序及验收范围

1. 实现一个 GUI 专用工具与参数校验，接入模式 / 入口权限、pi 注册和宿主分发；新增可取消桥接及统一输入窗口，复用既有工具结果和退出清理。具体工具名、内部事件结构由实现选最小一致方案，不增加表单框架或请求分类系统。
2. 更新共用 Prompt、必要的中英 GUI 文案及当前用法（`docs/agent-repair.md`、`docs/developer-gui-design.md`、领域导航和实施切片），记录新能力实际状态与限制。不改历史日志、Candidate、Manifest、Default 或 Runtime 状态机。
3. 普通测试覆盖工具权限 / 输入校验、空确认与 Skip、取消唤醒、重复迟到响应、主窗口退出两分支、Session 恢复不重放、日志脱敏和 GUI 状态。优先扩展 `test_developer_gui.py`、`test_developer_session.py`、`test_repair_tools.py`，必要时新增小型独立交互测试文件。
4. Agent 工具循环测试必须标记 `pytest.mark.agent`，按需显式选择 `test_developer_session_agent.py` 等相关文件并添加 `--run-agent-tests`，验证 GUI 两种模式、CLI 隐藏与实际拒绝、同轮反馈 / 额度 / 历史、批量工具等待及取消。使用真实 pi + 本地服务替身的通过不替代真实模型、Windows 成品或真实游戏验收；普通回归不附带开启 Agent 测试。
5. 实施后提交本地验证记录，等待开发者人工验收。仅收到开发者验收确认后才 close #338；#339 / #340 与 Stage 6 不纳入本票实现。

结论：未发现需要重选架构的阻塞冲突；可在现有工具、Session、日志与活动互斥上完成。待开发者确认本审查后实施，重点是可取消等待与跨轮迟到回调隔离，不能只新增窗口和 Schema。
