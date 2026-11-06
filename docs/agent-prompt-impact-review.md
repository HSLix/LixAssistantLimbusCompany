# Construct / Repair Prompt 重构影响审查

2026-11-06 后续：SOP 已迁移为 Developer Skills，现行用法见 [Skills](agent-skills.md)，迁移验证见[实施记录](agent-skills-implementation.md)。下文保留原时点的实现及验证证据。

日期：2026-11-01。审查时状态：设计已逐项确认，影响审查完成，Prompt 重构尚未实施。

后续实施已完成，见 [实施记录](agent-prompt-implementation.md)。下文保留审查时的差距证据，不代表实施后的现状。

本报告依据本次讨论和当前工作区源码，不以 Git HEAD 代替当前实现。工作区已有聊天 UI 等未提交改动；后续实施须保留这些改动。此前对 `run_probe()` 的中文 docstring 修改不属于本次重构实现。

## 已确认的设计变化

- 范围：Construct / Repair 及共享扩展中的系统规则；`run_probe()` 保留独立诊断提示词，不加载开发 SOP 或修订结果 JSON 契约。不增加工具，不改变权限和执行能力。
- 结构：Core（角色、核心架构、安全及通用契约）+ Mode（各自目标与权限说明）+ SOP + Tool Guidance；Runtime Context 与用户需求放入用户消息。完整参数 Schema 仍由工具接口提供，不复制进系统提示词。
- SOP：一个随程序发布的 `sop.md`，以 Markdown 分级标题组织 SOP / Construct / Repair / Asset，分别使用 `<construct_sop>`、`<repair_sop>`、`<asset_sop>` 包住正文。三个正文区先留空，文件附开发者填写说明，说明不作为 SOP 正文注入。
- SOP 加载：每条用户消息开始执行时读取一次，轮内固定；Construct 加载 Construct + Asset，Repair 加载 Repair + Asset。缺文件、缺标签或重复标签在模型请求前报错；合法空正文允许使用。不增加 GUI 编辑器、数据目录副本或自动更新服务。
- SOP 是可按任务取舍的流程指导，不能扩大程序权限。模式固定不等于 SOP 全文固定；后续轮次和恢复的 Session 使用当轮读取的内容，不迁移旧历史或自动重放操作。
- 工具概览：复用实际注册工具的名称和简短描述，按模式、入口及本次请求实际启用状态过滤；预检和格式纠正没有开发工具概览。工具定义说明能力，SOP 说明流程，不另建手写描述清单或复杂动态加载机制。
- 内容边界：系统消息承载上述契约；用户消息以 `<runtime_context>` 和 `<user_request>` 区分宿主上下文与用户原文。外部内容留在附件和工具结果中作为参考，不能覆盖系统规则。XML 不参与授权，不据此声称能防止提示词注入。
- 输出：保留通用文本 JSON、`revise_success` / `message`、严格宿主解析和格式纠正，压缩提示并增加 2–3 个典型示例；不用服务商专用 Structured Output API。
- `revise_success`：本轮请求的修订已完成、相关静态校验通过才为 true；纯分析、信息不足、未完成或校验失败为 false。未要求试运行时，完成修订且 Validate 通过可为 true，但须明确未验证游戏行为；明确要求试运行成功时，未执行或失败为 false。此字段仍是模型报告，不替代校验或验收。

## 调用链与影响范围

1. GUI / CLI → `DeveloperSession.conversation()` → `RepairConversation.run()`：恢复历史、计算当前入口权限、准备 Candidate 与附件、记录输入、启动 pi、预检、开发循环、最终 JSON 解析与纠正。
2. `configured_pi()` → `pi_probe.ts`：Python 传入宿主系统提示词；扩展组装实际系统消息，提供工具 Schema、历史和原图、额度通知，并记录实际请求载荷。
3. 原生 read / edit 在 TypeScript 内检查路径和权限；validate 走专用宿主分支；其他开发工具转发 `RepairTools.call()`。Prompt 重构不得绕过任一分支。
4. wheel / Windows 打包：`pyproject.toml`、`LALC.spec`、`scripts/build_windows.py` 显式列出资源；新 SOP 必须同时进入分发与成品资源检查。

## 已确认的差距与文档冲突

| 证据 | 当前情况与影响 | 后续动作 |
| --- | --- | --- |
| `src/lalc/agent_repair.py:SYSTEM_PROMPT / MODE_PROMPTS` | Core、工具能力、跨工具约束和输出要求混在一个大字符串；Mode 只有短前缀，没有 SOP 加载。 | 拆分职责，删重复能力描述，保留安全和必要跨工具约束；增加独立 SOP 文件及加载逻辑。 |
| `RepairConversation.__init__ / run` | 系统提示词在创建对象时固定；每轮只重算权限。与已确认的每轮读取 SOP 不符。 | 将本轮 Prompt 快照放在执行开始、请求之前；校验加载错误，不在同轮预检、工具循环和纠正中重新读文件。 |
| `src/lalc/pi_probe.ts:before_agent_start / registerTool / session_start` | 扩展追加路径及额度规则；工具名称、描述、Schema 在注册处，实际启用清单由宿主白名单和预检状态决定；目前未生成工具概览。 | 从实际注册信息和 active tools 生成简介；纠正时先禁用工具，再生成当前概览。复用既有工具声明，不把 Python 方法 docstring 再维护成第二套描述。 |
| `agent_repair.py:check_model_image` 与 `pi_probe.ts` | 预检复用开发系统提示词，但没有 `LALC_PI_REPAIR_FILES`，扩展当前采用“源码根目录”分支；预检实际禁用工具。 | 明确预检是连接 / 图片检查阶段，不注入开发工具或要求预检输出开发 JSON；保留一次预检计入共享额度的行为。独立 `run_probe()` 不套用开发输出契约。 |
| `RepairConversation.run` 的 prompt 构造 | 仅拼接可编辑文件及用户消息；Manifest 附件被直接追加到用户文本。来源 Manifest 另存 input 日志，没有按新契约组织宿主上下文。 | 使用现有 Session / 基线元数据组织 Candidate、来源 Manifest、参考附件、已有可编辑文件及需求，不读取或执行额外参考源码；空白 Construct 的来源应明确为空。 |
| `RepairConversation.run` 输入与请求日志 | `input.json.system_prompt` 保存 Python 原始提示词，实际载荷还包含 TS 追加内容。 | 记录本轮选中 SOP 的实际正文和宿主 Prompt 快照，继续保留各次实际载荷；明确两者区别，不把原始提示词误称完整请求。 |
| `agent_repair.py:final_answer / final_answer_retry` | 已有严格整段解析、字段类型检查和多次格式纠正；纠正文案重复，成功字段语义没有本次确认的细化。 | 保持解析行为，压缩提示，补典型 true / false 示例；保留业务内容、禁用工具、额度及停止机制。不由布尔字段新增自动验收或执行分支。 |
| `docs/agent-repair.md:170,175`、`docs/developer-gui-design.md:120,125` 对照 `pi_probe.ts:context` 和 `tests/test_agent_repair_agent.py:test_each_request_sees_current_budget_and_next_message_resets` | 文档称动态额度计数进入 system prompt；当前代码在 user 消息中注入并在本轮历史原位保留，测试明确断言 system 中没有动态计数。这是已确认的现有文档漂移。 | 更新当前说明，保留已执行测试数字作为历史证据；不为本次 Prompt 排版把计数移回系统消息。 |
| `pyproject.toml:package-data`、`LALC.spec:datas`、`scripts/build_windows.py:assemble` | 当前只列已有 TS / 图标 / 翻译等资源，新 MD 不会自动成为受检查的运行资源。 | 添加 SOP 打包声明、成品缺失检查及对应测试夹具；说明源码与 Windows 成品编辑位置。 |

## 潜在风险与验证方式

- **工具元数据读取接口**：已检查扩展当前使用 `getAllTools()` / `getActiveTools()`，但尚未执行验证所需名称、描述字段及调用时机。实施时检查本地 pi API 定义，并以真实 pi + 本地 HTTP 替身核对实际载荷；不能只检查拼接字符串。
- **历史消息兼容**：`developer_session.py:restored_history / restore` 恢复已有消息和工具结果，不依赖新 XML 模板。预计无需迁移，但须覆盖“旧历史 + 新一轮模板”、同一 Session 跨入口重新限权、SOP 跨轮改变而历史不改写。
- **缓存**：SOP 改动或实际工具集改变会改变系统前缀，可能减少缓存命中；不承诺命中率。普通工具循环内 SOP 不变，只有预检 / 正式对话 / 格式纠正的实际工具状态需要分别表达。
- **XML 边界**：用户、参考源码及工具输出可能包含同名标签。必须保留消息角色和原文，不把文本标签解释为授权，不用不可信内容拼出新的系统规则。此格式不能证明注入防护有效。
- **安全规则精简**：工具 Schema 未必覆盖所有跨工具关系。仍需保留不可变源码、Candidate 不直接执行、Publish 后显式试运行、Default 不自动改变、素材预览身份及全局影响、Validate 不是沙箱或游戏验收等核心约束。
- **效果证据**：单元测试和替身请求只能证明加载、消息内容和权限行为；不能证明真实模型更遵循 SOP、降低错误率或修复真实游戏行为。真实模型、Windows 成品与真实游戏验收单列。

## 实施顺序与验证

1. 新增 SOP 资源及开发者填写说明，完成空正文、选择、缺失 / 重复标签和每轮快照的普通测试；不填写业务 SOP。
2. 重组 Core / Mode、Runtime Context、输出示例与纠错文案；保留原解析器、Session 历史协议及授权代码。覆盖加载失败在模型请求前退出、空白 Construct、已有 Repair、旧历史续聊和用户原文保留。
3. 在 TS 共享扩展复用实际工具注册信息生成概览，整理共享系统规则；针对预检、正式请求、纠正请求分别验证实际工具定义与概览一致，独立 Probe 保持诊断角色。
4. 补齐 wheel / Windows 资源声明、成品校验和测试夹具；更新 `docs/stage-5-agent-workbench.md` 的 Prompt 契约、`docs/agent-repair.md` 的 SOP 用法及输出语义、`docs/developer-gui-design.md` 的共享 Prompt / 额度说明，包装用法同步 `docs/windows-packaging.md`。
5. 先运行相关普通测试；本次涉及 Agent 接入，可显式选择 `tests/test_agent_repair_agent.py`、`tests/test_pi_probe.py` 和相关 Session Agent 用例，添加 `--run-agent-tests` 验证真实 pi + 本地 HTTP 替身。真模型用例及 `lalc pi-probe` 不自动运行，不把跳过计为通过。

本轮为源码与文档只读检查，仅新增本报告；未运行测试、启动 pi、调用模型或构建 Windows 成品。未发现需要扩大工具权限、改变 Session 存储格式或新增 ADR 的设计要求；此结论不代表上述潜在风险已通过执行验证。
