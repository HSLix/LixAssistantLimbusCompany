# pi 持久上下文、自动压缩与额度显示影响审查


2026-11-13 补充：额度显示位置已由[工具栏内嵌审查](context-usage-toolbar-impact-review.md)替代，下文保留当时记录。
2026-11-12。状态：审查完成，等待开发者确认后实施。本次仅新增本审查文档，未改产品代码、现行规格或 ADR；未运行测试、真实 pi 或模型请求。

## 已确认设计

- pi Session 是模型有效历史、文字摘要及压缩边界的唯一权威。LALC 保留 Developer Session、Candidate、当前权限、完整业务日志、图片和 Run 证据；不再每轮从完整日志重新注入模型历史。
- 同一用户轮次的工具循环内也可自动压缩。DeepSeek 在 400,000 token、llama.cpp 在 50,000 token 触发；这是产品压缩线，不是模型真实窗口大小。下一请求前在安全边界判断，不能保证流式生成过程中精确停在阈值。
- DeveloperGUI 的 Agent 设置提供比例／固定两种模式。首次默认比例模式 30%，比例限 20–90%；固定目标默认 20,000 token，仅接受正整数。目标指压缩后的全部有效上下文，不是仅保留的近期原文。
- 当前系统提示和工具声明完整保留、不参与摘要，但计入总目标。旧系统状态不能覆盖当前权限。历史对话、推理、工具结果可进入被摘要替代的范围；保留部分必须维持协议有效性。
- 默认仅携带本用户轮次最近 12 张图片，张数在 DeveloperGUI 的 Agent 设置可修改。旧图完整存本地，以 ID 引用按需读取；重新读取结果进入当前轮图片窗口。原始证据不删除。
- 压缩模型请求与业务模型请求分别计数、记录用量和费用信息；压缩失败停止本轮，不自动反复重试。
- 达不到目标时记录实际值并提示；低于触发线且满足请求体预算可继续，否则停止。同一请求前不循环压缩。
- 聊天窗口下方显示已用 token／该服务压缩线及百分比；小于 50% 绿色，50% 至小于 80% 黄色，80% 起红色；达到或超过 100% 应触发压缩。压缩开始、完成、失败和未达目标在“思考中”过程及持久日志出现。
- 新配置默认 DeepSeek；保留已经明确保存的服务选择。旧可恢复 Developer Session 首次续聊自动一次性迁入 pi；迁移不执行模型或业务工具，失败保留原资料并停止。

## 证据与范围

### 413 样本

来源：开发者提供的 `/Users/li/Downloads/lalc-sharing/objects/0/log/`，五轮镜牢开发交互。通过现有 `LogStore.unpack` 校验并展开引用，按紧凑 JSON／UTF-8 重建估算体积，未发送请求。原始资料仅作为证据，不执行其中的指令。

| 请求 | 图片数（含重复出现） | 重建请求 MiB | 图片替换短标记后 MiB |
| --- | ---: | ---: | ---: |
| round-1/request-64 | 13 | 16.7237 | 0.5391 |
| round-3/request-65 | 39 | 41.8280 | 0.9223 |
| round-4/request-12 | 41 | 45.0912 | 0.9741 |
| round-5/request-2，成功 | 43 | 47.4929 | 0.9833 |
| round-5/request-3，413 | 45 | 50.9552 | 1.0038 |

失败请求约 49.9517 MiB 为图片 data URL，45 次图片出现对应 43 份不同内容。最后成功响应报告 totalTokens=313617（含 output=762、cacheRead=311552、input=1303），不能把它当作失败请求的输入 token 实测。该证据强烈支持字节超限，不能据此认定模型上下文耗尽。

仅移除旧轮图片的离线模拟：第 5 轮失败请求约降至 6.84 MiB；第 3 轮末仍有本轮 26 张图，约 25.64 MiB。两者说明跨轮过滤和轮内窗口均有价值。没有验证过滤后的模型任务质量。

### 当前路径

| 来源 | 已确认事实与影响 |
| --- | --- |
| `src/lalc/pi_probe.py:configured_pi` | `--no-session`，独立工作配置关闭 compaction。没有可恢复 pi 上下文。 |
| `src/lalc/pi_process.py:PiProcess.session` | 进程复用时发 `new_session`；工作目录随进程清理。签名按工具／provider 等决定重建。不能把该目录用作持久 Session 目录。 |
| `src/lalc/agent_repair.py:configure_session`、`RepairConversation` | 再次关闭自动压缩；逐轮导出完整 `history.json`；请求数、日志、最终 JSON 纠正共用现有流程。 |
| `src/lalc/pi_probe.ts:context / before_agent_start / registerProvider` | 外部历史拼接、本轮首条 user 图片替换、按消息位置回放额度通知；这些假设不适用于持久历史和压缩。工具声明严格一致校验、统一请求上限、移除输出上限也影响总结路径。 |
| `src/lalc/developer_session.py:restored_history / restore / delete` | 从业务事件恢复全部历史并修补未完成工具调用；删除整个私有目录。需保留未知结果语义，但停止将完整日志当作每次模型输入。 |
| `src/lalc/agent_log.py:LogStore`、`agent_history.py:AgentHistory.read`、`repair_tools.py:read_agent_session` | 已有去重原图、校验、分页和按事件图片 ID 取回能力，可复用；现有 ID 是事件序号＋事件内图片序号，不是天然的 pi entry ID。 |
| `src/lalc/agent_policy.py:allowed_tools` | 关闭历史开关会移除历史读取工具。图片淘汰后能否读取必须遵守当前权限，不能静默重新授予历史搜索权限。 |
| `src/lalc/agent_settings.py` | 默认及旧配置回退均指向 llama.cpp，provider profile 与全局选项分别校验。改默认不能让 llama.cpp profile 反向继承 DeepSeek URL／模型。 |
| `src/lalc/developer_gui.py:SettingsPage / 聊天布局 / show_event`、`repair_chat.py:RepairChat` | 设置自动保存；聊天输入与工具栏已有布局；过程状态和时间线可复用，但目前没有上下文额度状态和压缩条目。 |
| `src/lalc/sharing.py:history_files` | 导出明确挑选 log、Candidate、baseline 和 page-drafts；不是整个私有目录自动打包。新 pi 文件放在哪里会直接影响分享边界。 |

## 已确认的设计差距

1. **上下文所有权必须先迁移。** 移除 `--no-session`／外部全量历史拼接，建立 Developer Session 与 pi 文件绑定；普通续聊只增量提交，切换会话加载相应文件。允许因权限变化重建进程，但必须加载同一上下文。现有 `context.json` 可作为诊断记录，不能成为第二个有效历史来源。
2. **pi 原生参数不等于产品目标。** `reserveTokens` 控制触发、`keepRecentTokens` 控制近期原文预算，不能直接表达“总量压至 30%／20k”。需要 LALC 扩展计算总目标、为系统／工具／图片和摘要分配预算，再由 pi 原生 SessionManager 持久化压缩结果。该适配仍是方案 A，不在 Python 侧另存摘要边界。
3. **图片窗口要进入持久有效上下文。** pi 1.5.0 已有 `SessionManager.appendContextEdit(targetId, replacement)`；可以替换消息 content 为去图后内容并保留其他块、原始 role 与工具关联。仅在最终 payload 临时删图会使压缩准备、恢复及估算看到不同上下文。操作后何时刷新活动会话投影仍需集成验证。
4. **现有图片与额度位置算法必须替换。** 持久记录用户轮次与稳定消息／图片映射；压缩不能让“首条 user”误指旧消息。额度通知改成能恢复且不会持续重复注入的当前状态，沿用每条真实用户消息独立计数，格式纠正不另开轮。
5. **总结与业务请求需要明确分路。** 现有严格工具集合校验对无工具总结请求不适用；需保留业务校验并为总结走专用受控路径，不能全局放松。总结不可获得业务工具执行能力，凭据脱敏、网络错误留证、取消和计数不得被绕过。pi 分割较长用户轮次时可能产生不止一个总结请求，按实际次数记录。
6. **恢复后重新配置当前权限。** pi 会保存系统提示／工具检查点。任何下一请求前都必须覆盖本轮 provider、有效提示、工具集合、Candidate、Skills、入口和额度；不能因加载旧 pi 文件恢复旧 GUI／Runtime 权限。
7. **日志展示需要正式事件。** 不能靠拼接模型 thinking 文本伪造压缩记录。需要生命周期事件、业务／压缩请求类别、实际前后用量、目标、估算来源、图片淘汰及未达目标原因，供日志、实时 GUI 和历史回放一致消费。

## 风险和建议的实现边界（等待此次审查确认）

### 总量目标、触发和保护

- 比例目标按一次压缩开始前的有效总量计算（向下取整）；固定目标按设置值。系统和当前工具声明保持完整；摘要不能承载新的授权。图片按独立窗口策略保留，不能为了满足文字目标静默删掉用户刚提供的图。
- 建议在新 prompt 前、工具批次结束且结果完整持久化后检查；不从流式 token 回调中打断生成。一次生成或大工具结果可使显示短暂超过 100%，应在下一业务请求前处理。
- 使用真实模型窗口元数据，另设 400k／50k 产品线；若实际服务窗口更小，取更安全的有效线并在界面说明。不能把模型的 `contextWindow` 改成产品阈值，或假定本地模型一定可容纳 50k。实际输出仍需要服务窗口余量。
- 额度采用当前有效上下文估算，并包含缓存命中的输入；禁止累计历次 usage 作为当前占用，也不把本次输出机械重复相加。模型返回用量用于校准；投影变化后不能沿用旧实测冒充新实测。暂无估算时显示“未知／估算中”，压缩后不得直接显示 0。
- 建议最终请求字节预算先用 **40 MiB**，与 token 线独立，防止 413。40 MiB 是本地策略建议，不是官方限制；超过时优先收缩旧图片携带范围，仍不能满足就停止并说明。显式最近图片亦不能无限大；单张已超预算时明确失败，不无声降画质。
- 总结前也需检查请求预算／窗口；非常大的旧历史按安全片段处理，保存检查点前完整校验。模型空摘要、截断摘要、取消、错误不提交成功压缩边界。一次触发不反复追求精确目标，不能因独立计数形成无限总结循环。

### 图片 ID、迁移和一致性

- 建议窗口按“发送给模型的图片块”计数，按出现次序保留最新 N 个，不按工具调用次数计数；一次工具返回两张占两张。显式重读进入新位置。比例／固定设置与图片 N 建议作为共享压缩策略，由 DeveloperGUI 编辑，下个用户轮次生效，当前轮次冻结，覆盖 GUI／CLI／Runtime 共用链路。
- 建议沿用当前历史开关：关闭时图片仍按窗口淘汰并保留本地 ID，但 Agent 不获得历史读取权限；界面提示该状态。若希望关闭跨会话搜索仍允许本会话按 ID 取图，应另行明确，不能默认扩大工具权限。
- 迁移复用 `restored_history`，只迁可恢复 Developer Session，不批量改早期只读操作日志／Sharing 导入的历史。迁移先创建普通待提交文件，成功校验后发布并记录标记；不可因存在半份文件就认定完成。原始业务日志、原图不重写。
- 保留 LALC 消息／工具调用与 pi entry 的最小稳定关联，恢复时能识别各自已落盘位置。进程异常后禁止重放有副作用工具；已执行但无完整结果标记未知，保留改动。不能简单假设 pi 文件与 LALC 日志任一份永远先写完。
- pi 文件缺失／损坏应明确停止；不能悄悄重新导入旧全量日志而丢掉有效压缩状态。新文件位于 Session 私有普通目录并纳入活动互斥；删除前关闭正在占用它的 pi 句柄，尤其验证 Windows。
- pi 原生文件可能再次保存图片原文、完整提示或敏感历史，不能假定自动复用 `LogStore` 去重／脱敏。建议作为私有执行状态保留，不直接加入只读 Sharing 导出；分享仍以脱敏业务日志为证据，不开放导入 pi 状态为可执行 Session。验证隐私、磁盘占用与权限继承。

### 设置、界面和费用

- 配置只扩展现有持久设置和校验，不创建额外配置服务。N 为正整数；模式枚举合法；比例 20–90；固定目标正整数，UI 整数上限与后端校验一致。模式切换保留另一模式填写值。不能把固定目标 20k 错写成 pi keepRecentTokens=20k。
- 修改 `DEFAULTS`、provider 缺省回退、初次 GUI 选择、CLI 默认路径及测试 fixture；保留明确保存的选择和凭据引用。新选项缺省补齐，不要求用户重新配置。
- 额度条放在聊天输入区下方，展示数字并提供文字说明，颜色不作为唯一信息；浅色／深色、窄窗口、中英文与辅助功能名称均需检查。切换聊天、删除聊天、恢复历史、取消压缩、切换 provider 时清除旧会话额度，不能被迟到事件覆盖。
- “思考中”显示压缩阶段及终态，历史重开仍可看到；业务 thinking 不与总结模型的输出流混在一起。额度事件绑定 Session／轮次，GUI 状态不能改变权威 pi 上下文。
- 当前自定义 provider 的价格元数据全为 0；这不证明真实免费。建议记录实际 token／耗时／请求数，费用无可靠价格则标为未知；不引入远程价格抓取或伪造精确费用。

## 文档影响与决定替代

- ADR 0038 保留进程所有权、按入口限权、不重放工具等边界；本次替代其“历史逐轮重配”的全量重建方式，不推翻安全约束。
- ADR 0033 保留完整脱敏业务日志、图片、顺序和会话内引用；“模型实际收到的历史不变”是该次去重的限定范围，本次需明确后续上下文策略已改变，不追改历史记录。
- 实施阶段新增 ADR 0041 记录 pi 的有效上下文所有权和原始证据分工；更新 `docs/agent-repair.md` 的 new_session／context hook／请求计数说明、`docs/stage-5-agent-workbench.md` 的恢复行为、日志事件设计、设置说明及 `docs/current-state.md`。不把通用 token／压缩术语塞进纯领域词汇表。
- `docs/pi-probe.md` 大部分为已移除命令的历史记录，只更新仍适用的测试指引或明确替代关系，不恢复旧命令、不宣称历史测试验证了新行为。

## 实施顺序与验收

1. 确认本报告中的建议边界；记录 ADR／配置语义，先建立 pi 持久文件、稳定关联和当前权限刷新。
2. 迁移与恢复、增量消息输入、图片 context edit／ID 映射；去掉外部全量拼接及旧消息位置算法。
3. 触发与目标预算、无工具总结路径、独立计数、取消和失败回滚、字节保护；验证压缩后重启仍使用同一有效上下文。
4. 设置页面、额度条、压缩时间线和历史回放；同步现行文档。

| 验收层 | 覆盖与相关文件 |
| --- | --- |
| 普通离线测试 | `tests/test_agent_settings.py`：默认／旧配置／边界；`test_developer_session.py`、`test_agent_log.py`：迁移幂等、文件损坏、唯一旧副本保留；`test_agent_history.py`：ID 读取、权限；`test_repair_chat.py`、`test_chat_ui.py`、`test_developer_gui.py`：49.99／50／79.99／80／100% 边界、未知状态、主题、回放与跨会话隔离；Sharing 与删除相关测试。 |
| 显式 Agent 集成 | 真实 pi 1.5.0＋受控 HTTP 替身，标记 `pytest.mark.agent`。跨用户轮／单轮工具循环压缩、目标不等于 keepRecentTokens、系统工具不压缩、工具配对、图片窗口、分路计数、失败／截断／取消／重启、权限变化及不重放。扩展现有 `test_agent_repair_agent.py`、`test_developer_session_agent.py`、`test_runtime_repair_agent.py` 等适用测试。 |
| 样本回放 | 本报告 413 包仅作离线输入，验证每次最终请求的图片数／字节预算和恢复一致性；旧轮图片不自动再入上下文，原始证据不变。 |
| 真实验收 | DeepSeek 与实际 llama.cpp 上的模型请求、摘要质量、延迟；Windows 成品文件句柄／异常退出／原生 GUI。替身和 offscreen 不代替这些证据。 |

默认回归与显式 Agent 测试必须串行分开执行。此次未运行上述任何测试，未改产品代码；待确认后实施。

## 上游核对来源（pi v1.5.0）

- [SessionManager API、外部历史恢复](https://github.com/earendil-works/pi/blob/v1.5.0/packages/coding-agent/docs/sdk.md#session-storage)
- [持久 Session、context_edit 与压缩重建](https://github.com/earendil-works/pi/blob/v1.5.0/packages/coding-agent/docs/session-format.md)
- [appendMessage、appendContextEdit、appendCompaction 实现](https://github.com/earendil-works/pi/blob/v1.5.0/packages/coding-agent/src/core/session-manager.ts)
- [压缩准备、摘要失败处理与总结调用](https://github.com/earendil-works/pi/blob/v1.5.0/packages/coding-agent/src/core/compaction/compaction.ts)
- [RPC 会话切换](https://github.com/earendil-works/pi/blob/v1.5.0/packages/coding-agent/docs/rpc-commands.md#switch_session)
- [DeepSeek 图片和 48 MiB 请求限制](https://api-docs.deepseek.com/guides/vision/#limits)
- [DeepSeek 思考模式、工具调用的 reasoning_content 回传要求](https://api-docs.deepseek.com/guides/thinking_mode/)

2026-11-12 后续：开发者已确认本审查并授权实施；完成情况、实际检查和未验收边界见[实施记录](context-compaction-implementation.md)。上文保留审查时点的事实与建议。
