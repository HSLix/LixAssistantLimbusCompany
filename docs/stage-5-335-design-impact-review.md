# #335 — CLI Repair Session 设计影响审查

2026-10-31。状态：关键实践边界已逐项确认；开发者已以“开始实现”接受本票审查并授权实施。下文保留审查时的差距，实施结果另见[记录](stage-5-335-implementation.md)。依据 [#335](https://github.com/HSLix/LixAssistantLimbusCompany/issues/335)、[Stage 5 规格](stage-5-agent-workbench.md)、[ADR 0034](adr/0034-extend-developer-agent-with-reviewed-page-drafts.md)及本次讨论。GitHub 票据读取时 OPEN、无评论；本报告不表示产品已实现或验收通过。

## 设计变化与范围

- CLI Repair 从手工 Candidate + 进程内对话，转为数据目录中的独立、持久 Developer Session。创建必须指定已发布 Manifest，恢复必须指定 Session ID；不隐式使用 Default，不迁移旧草稿或日志。模式固定为 Repair。
- 每 Session 独立保存 Candidate、固定基线、消息、附件、工具结果关联及轮次 / 日志；Asset Library、已发布 Manifest、运行记录等仍共享。会话保留、不重建、不删除或自动清理。手工 init / validate / publish / clear 继续操作原 Candidate。
- 本轮补充确认：悬空调用只表示中断、结果未知，不认定未执行或成功，不自动重放。开发者再次发消息后，由 Agent 根据证据与实际状态判断如何继续，不能借此扩大权限。
- 本轮补充确认：CLI 空闲等待输入时释放 Session 锁；每轮执行前重新加锁并读取最新持久状态，执行、工具调用和取消收尾期间保持锁，竞争明确报占用。现有游戏活动互斥不放宽。
- 本轮补充确认：恢复历史不恢复仅存于内存的裁剪预览 ID；旧 ID 明确失效，由 Agent 决定是否重新观察，宿主不自动重做，已保存 Asset 不变。
- #335 交付 CLI 和共用 Session 存储 / 恢复边界；GUI 历史列表、Construct、统一工作台及 GUI 入口迁移由 #336 交付。不在本票加入知识库、人工反馈、页面预览或 Runtime Maintenance。

上述为既有 Stage 5 决定的实践细化，没有另立术语或改变架构取舍，不新增 ADR。

## 已确认的实现差距

### 1. CLI 路由仍依赖手工草稿

证据：`src/lalc/__main__.py:_parser` 的 repair 没有创建来源 / Session ID 参数，`_dispatch` 把 `default_candidate_root` 传给 `run_repair`。`src/lalc/agent_repair.py:run_repair` 直接以该路径创建 DeveloperHost、调用 new_conversation。`src/lalc/developer.py:initialize` 支持隐式 Default，且初始化会创建对话；不能原样用作新 Session 的全部生命周期。

影响：需隔开 Agent Session 与手工 Candidate，明确创建 / 恢复路由，输出 Session ID 供后续续聊；初始化及元数据失败不得破坏其他数据或留下被识别为可用的半成品。复用现有 Manifest 物化与固定基线逻辑，但不让 Session 提供重建操作。

测试影响：`tests/test_cli.py:test_repair_cli_has_no_file_selection_and_dispatches_to_shared_host` 断言 CLI 传入手工 Candidate，须更新为新路由；无旧文件选择参数的断言保留。`tests/test_agent_repair.py` 的手工初始化失败恢复 / 固定基线测试继续有价值，不应全部改成 Session 测试。

### 2. 当前连续对话与日志不足以恢复 Session

证据：`src/lalc/agent_repair.py:RepairConversation.__init__` 新建空 history / RepairLog；`RepairLog.__init__` 新建日期 / UUID 日志目录并令 group=0。`RepairConversation.run` 将用户和 message_end 消息加入内存，在 finally 才保存 context.json。`src/lalc/pi_probe.ts` 的 context hook 直接拼接宿主提供的 history 与当前消息，没有悬空工具调用整理逻辑。

影响：需持久保存 / 恢复会话身份、Repair 模式、来源、历史、轮次与日志关联，并在关键消息 / 工具事件后保存足够的恢复证据。原始日志不改写为成功；提供给模型的历史必须保持调用 / 结果关联，对确无结果者明确记录宿主中断、结果未知。不能仅用旧 context.json 或异常退出后缺失的 result.json 判定操作未发生。

复用 `src/lalc/agent_log.py:LogStore`、read_json / read_events 的去重引用和路径 / 哈希校验；保持 [ADR 0033](adr/0033-deduplicate-agent-logs-with-conversation-local-references.md) 的自包含、脱敏、不裁剪历史边界。缺失或损坏的内容引用明确报错，不能静默丢掉消息后继续。

测试影响：`tests/test_agent_repair_agent.py:test_text_only_and_context_retained` 只在同一对象中运行两轮；不能证明跨进程恢复。需新增关闭后恢复消息 / 多图 / 工具关联、轮次连续，以及工具请求已保存但结果未知的中断用例。

### 3. 恢复后计数重置可能覆盖旧证据

证据：`src/lalc/repair_tools.py:RepairTools.__init__` 设置 sequence=0，call 生成 `tool-{sequence}.json`；image / capture 等产物也使用该编号。`RepairLog.group` 从零开始，run 使用 `round-{group}`。`tests/test_agent_repair_agent.py:test_live_asset_tool_images_retained_across_rounds_without_overwrite` 验证的仍是同一存活对象。

影响：直接把新对象指向旧目录会重用工具文件名或轮目录；恢复须确保轮次和所有产物编号不重复，不能覆盖历史引用对应文件。需验证恢复再调用工具后，原结果、图片、请求和快照字节保持不变。

### 4. 现有锁可复用，但锁内重新加载是新增要求

证据：`src/lalc/developer.py:candidate_lock` 以 Candidate 的真实路径构造 ProcessLock；`RepairConversation.run` 已在 activity("Agent") / candidate_lock 内执行。`src/lalc/application.py:activity` 令 Agent 持有跨进程 game 锁；内部试运行复用已有活动锁。`src/lalc/process_lock.py` 使用操作系统非阻塞文件锁，退出释放且保留锁文件。`tests/test_process_lock.py` 覆盖 game 锁竞争及进程退出释放。

影响：用 Session 身份或其独立 Candidate 绑定统一跨入口锁，在取得锁后重新读取当前历史 / 轮次 / 状态，避免 CLI 空闲后用旧对象覆盖其他入口更新。锁须覆盖恢复、中断标记、执行及取消后的最终落盘；等待 input 不占锁。保留 game 锁，不因不同 Candidate 而开放多 Session 并行操作游戏。锁竞争不得消耗轮次、请求或创建假的运行结果。

测试影响：增加同 Session 真实进程竞争、空闲后另一入口推进再续聊、异常退出释放及锁内读取最新状态；现有 game 锁用例继续保留。

### 5. 恢复不恢复旧权限和现场句柄

证据：`src/lalc/repair_tools.py:REPAIR_TOOLS` / call、`src/lalc/agent_repair.py:RepairConversation.run` 的 validate 分支和 `src/lalc/pi_probe.ts` 的 read / edit / setActiveTools 构成实际权限路径；read / edit 不经过 RepairTools.call。当前没有 Construct 或 GUI 专用工具。`RepairTools.previews` 只在内存保存，crop_asset 检查其中的 preview_id。

影响：CLI 加载时拒绝 Construct 或无效模式，恢复后继续使用当前 CLI Repair 权限，不从历史工具记录恢复授权。#336 扩展模式工具时沿用该入口边界，不能只靠 Prompt 或 RepairTools.call 过滤。重建工具对象时保留旧预览失效语义，给出明确反馈；不为恢复预览而重新截图。工具序号需恢复，预览对象不恢复，两者不能混为一体。

## 潜在风险与实施验证

- **中断位置影响协议**：模型请求、宿主副作用、宿主结果与 pi toolResult 分属不同事件，不能只测正常轮结束。需覆盖多调用中部分有结果、全部无结果及副作用已发生但返回未保存；验证不重放、无悬空关联、无伪成功，原始证据仍可读取。
- **中途退出与文件写入**：追加事件可能留下尾部不完整记录，创建也可能留下未提交目录。需针对进程退出的读写边界测试，区分不完整尾部与真正历史损坏，不把一般解析失败转成静默删历史的授权；不承诺断电后未保存数据恢复。
- **跨入口兼容尚待 GUI 交付**：本票先检查共用存储契约和入口拒绝；真实 GUI→CLI→GUI 操作随 #336 验收，不能在 #335 提前报通过。共享 DeveloperHost / RepairConversation 的变更仍需检查既有 GUI 不回归。
- **磁盘与共享副作用**：Session 长期保留会增长磁盘；恢复不撤销已发布 Manifest 或共享 Asset 变化，也不恢复游戏现场。当前接受此边界，不加入清理、回滚或环境快照功能。

## 建议实施及验证顺序

1. 新增最小共用 Session 存储：显式来源创建、Repair 模式、独立 Candidate / 固定基线、稳定 ID 与日志关联，创建失败隔离；保护路径边界及手工数据。
2. 接通 CLI 创建 / 按 ID 恢复，建议使用互斥的 `repair --from <Manifest ID>` / `repair --session <Session ID>`，保留 --problem、--chat、附件及当前模型设置。创建时显示 ID，模型请求失败后仍可继续使用已创建 Session。不增加无关命令或通用存储框架。
3. 在锁内恢复最新状态，接通关键事件持久化、中断整理、连续编号及失效预览反馈；沿用现有发布、显式版本试运行和取消收尾路径。
4. 完成不调用 Agent 的 Session / CLI / 锁 / 日志测试，并检查共享宿主影响；再显式选择带 agent 标记的真实 pi + 本地 HTTP 替身测试，验证恢复后的实际载荷、工具循环及权限拒绝。真实模型、Windows 成品和真实游戏证据单独记录，未执行不计通过。
5. 同步 README、docs/agent-repair.md 的当前 CLI 示例及 Stage 5 实施状态；历史证据保持原意。开发者确认实现及验收结果后，才更新并关闭 #335。

本轮只阅读源码、测试与文档并记录决策 / 审查；未运行测试、模型、pi-probe 或游戏，未修改产品代码，未发布评论或关闭 issue。未发现阻止本票实施的设计冲突。
