# LALC Reconstruction Plan

This plan keeps the reconstruction dependency-ordered. Accepted boundaries may change only through an explicit reopening such as the Python-first decision below.

## 2026-10-26 规划记录：已确认排期与待讨论草案

2026-10-26 首次按 grill-with-docs 仅记录；2026-10-27 已完成 Stage 4 grill 与影响审查并接受设计，随后经 #331 补充 grill 和影响审查确认，已在本地实现其 Python Plan 与双窗口闭环；后续票及 Windows 打包验收仍未完成，见[实施记录](stage-4-331-implementation.md)。首次输入为开发者提供的 AI 整理稿，可能含推演或扩写；其内容不因粘贴自动接受。Stage 4 已经后续逐项 grill 并确认，Stage 5/6 未确认内容继续作为讨论材料。

- **已确认：原 Stage 3.5 的完整 Runtime Agent Maintenance 延后至 Stage 6。** 原设计和讨论记录保留，不因改期自动修改执行契约，也不表示已经实现。
- **路线主线：** Stage 4 — Extensible GUI → Stage 5 — Workflow Construction & External Knowledge Transfer → Stage 6 — Runtime Maintenance & Continual Learning。Stage 4 已接受，Stage 5/6 的具体目标、交付和依赖仍待确认；Stage 6 承接原 Stage 3.5 的排期已确定。
- Stage 3 已有 Agent Repair、Developer Candidate、Validate、Developer Policy Publish/独立试运行/Run 日志等能力保留，权限以 ADR 0029–0031 为准。延期不取消这些能力，也不把独立试运行等同于恢复运行中的调用者。实施及验收见 [Stage 3 实施记录](stage-3-implementation-slices.md) 和 [Developer GUI](developer-gui-design.md)。
- Stage 4 重要设计和实现边界已完成 grill，正式接受范围见下文；Stage 5/6 除已确认改期及 Plan Agent 评估方向外仍为后续议题，不顺带定案。

下文 Stage 1–3 保留既有基线；其中 Stage 3.5 均指原阶段名，现排至 Stage 6。旧 Stage 4 范围不直接成为新提案的交付承诺。

## Stage 1: Product and Agent boundaries

Status: accepted and explicitly revised for runtime Agent maintenance and formal trials of unapproved candidate Python.

Locked contracts:

- officially supported objectives run through deterministic Python Workflows without a model;
- Stage 3 permits manual CLI invocation for independent Component repair; only the deterministic executor may invoke runtime recovery in Stage 3.5;
- the Recovery Ladder remains Deterministic Recovery, Agent, then Safe Task Termination;
- permanent capability changes require validation and human approval;
- every Top-level Execution selects one Base Manifest protected from Agent modification explicitly or through the Default Manifest and copies it into one complete durable Working Manifest; its forms are a directly started Task Workflow, Subworkflow, or Step and one Automation Plan with its sequential Task Workflows;
- Agent-generated formal candidate Python may receive a Working Manifest trial before permanent approval only after Supervised runtime confirmation;
- the first version reads and executes verified Components in the main process; TODO after the first release: evaluate moving executor execution into a subprocess, including Context transport, cancellation, and original-error propagation. Current execution is not a security sandbox.

## Stage 2: Python-first Workflow and deterministic execution

Status: architecture and implementation complete under the revised acceptance scope of ADR 0026 (2026-10-22). A real mailbox Workflow and remaining Windows integration/package acceptance are deferred in #317; completion does not claim those scenarios passed.

Confirmed contracts:

Agent runtime references below describe retained Stage 3.5 integration contracts, not Stage 2 implementation or Stage 3 prerequisites (ADR 0025).

- Task Workflow, Subworkflow, and Step are immutable Python Components loaded as ordinary modules after their exact source bytes are verified against their Component IDs;
- exactly one parameterless `@task_workflow`, `@sub_workflow`, or `@step` on each formal entrypoint is the sole component-role source; Manifest, paths, names, and tags do not duplicate or infer `component_kind`;
- each Task Workflow, Subworkflow, and Step has one source file with one decorated execute; only Step may expose a matching optional condition; Task/Subworkflow condition and standalone verify callbacks are rejected;
- formal Task Workflow, Subworkflow, Step, Step condition, Recovery Rule, and every private function in their files contain no `except`; `try/finally` remains available for cleanup, but loaders reject `return`, `break`, `continue`, or `raise` in every `finally` without reachability or rethrow analysis so the original exception propagates naturally;
- each Manifest is one complete document containing executable `logical_name → immutable Component ID` mappings, a `recovery_rules` mapping; Assets resolve independently through logical-name directories and optional tags (ADR 0027), while Trusted Actions are application-registered;
- formal Components call one another only through `ctx.call(logical_name, **arguments)`; it resolves and validates the current Working Manifest entry on every call and stores no Component Ref or implementation cache;
- every `ctx.call()` target is a string literal; before each Working Manifest atomic update, the executor validates every formal target and role permission against the complete resulting candidate Manifest, while runtime validates resolution and role again and records the actual identity;
- every `ctx.call()` in a Task Workflow or Subworkflow source file belongs to that file's single Component, including calls in private or apparently unreachable functions; Step, Step `condition`, and Recovery Rule source may contain no `ctx.call()`, and the loader performs no reachability or branch analysis;
- any complete-Manifest validation error rejects the entire atomic switch and leaves the old Working Manifest active;
- runtime `ctx.call()` rechecks only target resolution and role and records the call; it adds no active-Subworkflow stack, while recursion inside ordinary private Python functions remains an implementation detail;
- dynamic `ctx.call()` targets are invalid; the executor never rewrites, copies, or inlines candidate source to make an invalid call legal;
- formal Component orchestration permits Task Workflow to call Subworkflow or Step and Subworkflow to call only Step, while Step calls no formal Component; ordinary functions inside Component source remain unmodeled implementation details, and complete task composition belongs only to Automation Plan;
- Step condition and Recovery Rule entrypoints never call formal Components; condition and detect use observe only, while recover may also control;
- each Recovery Rule is an immutable Python Component with a module docstring, stable logical name, Component ID, and fixed `detect(ctx) -> bool` plus `recover(ctx) -> None` functions; it has no fourth role decorator and is discovered only from `recovery_rules` rather than through `ctx.call()`;
- the three role decorators only mark role; later executor-owned wrappers use `functools.wraps`, while formal identity remains the logical name and Component ID;
- Python native control flow, local variables, returns, and call stack replace the YAML Step graph, routing tables, Transition objects, variable mappings, and custom Subworkflow stack;
- formal execution uses only ordinary Python returns for Normal Outcome and `ExecutionFailure` for the interruption channel; there is no common Outcome type or output schema;
- non-user execution errors use ExecutionFailure with original traceback and cause chain preserved; user pause, takeover, and cancellation remain separate controls, using UserInterruption only where unwinding is needed; recovery remains owned by the existing execution boundary;
- user cancellation is a control request rather than an ExecutionFailure; internal unwinding may use UserInterruption with cancellation intent retained: it invokes neither recovery nor Agent, stops further input, interrupts a containing Automation Plan without later items, and records `user_cancelled` only when a Task run record already exists; otherwise it creates no Task result, while exact position remains in Trace and `safe_termination_performed` reflects only an action actually taken rather than an inferred stage;
- returned values keep distinct meanings attached through descriptive names or dictionary keys; no value-count rule or frozen result class is mandated, and the current runtime uses JSON-compatible values;
- each formal Task Workflow, Subworkflow, and Step uses a typed `execute(ctx, *, ...)` signature as its sole input contract; only Step may add an optional matching `condition(ctx, *, ...)`, while supported annotations recursively cover JSON scalars, `Literal`, optional values, `list[T]`, and `dict[str, T]`, with JSON-compatible defaults and no independent input schema or `ctx.inputs`;
- arbitrary input classes, Pydantic models, Enum types, sets, tuples, and non-optional unions remain unsupported;
- `ctx` exposes executor-owned invocation, environment, Manifest, Trace, evidence, cancellation, and budget services but no arbitrary mutable fields or shared business dictionary; business data moves only through parameters, returns, and ordinary Python locals;
- formal inputs are normalized and independently copied; saved Step arguments remain unchanged across callee mutation and retries;
- repeated objectives use ordinary Task Workflow loops over one-run Subworkflows; Subworkflow returns update Task Workflow local completion data, and the Task Workflow returns a value matching an explicit, directly JSON-compatible return annotation;
- Task Workflow stays thin but complete: it owns top-level inputs, business order, loops, branches, local aggregation, root result, and ordinary business checking Steps, while recognition and external operations move into useful Step or Subworkflow boundaries without mechanically componentizing ordinary Python decisions;
- business-result verification is recommended inside ordinary Steps; Task has no independent verifier, and success is a normal JSON-compatible return after its Steps;
- root results must match directly JSON-compatible declared types; invalid format reports failure without a separate verification callback;
- the executor fabricates no completion data, progress meaning, or returns; important business checks belong in ordinary Steps before Task return;
- the Agent receives a JSON diagnostic snapshot derived from explicit data and runtime records rather than the live `ctx`; external game state is always re-observed;
- condition is optional and read-only only for Step; false or exceptional evaluation belongs to the whole Step recovery boundary;
- Task and Subworkflow prerequisites are expressed in ordinary Steps; no Workflow entry condition is evaluated;
- Step condition checks before the first and every recovery-controlled fresh invocation; false, uncertainty, or exception produces `ExecutionFailure`, never reaches Workflow as a branch value, and only a later satisfied check permits Step invocation before repeated failure escalates to Agent or Safe Task Termination;
- a Step `condition` accepts the whole observable responsibility range rather than one instantaneous action target, and every Step safely continues from actionable, expected transitional, or completed states using only current observation and original arguments;
- each Python Component uses one module docstring as its sole natural-language description;
- Task Workflow has no final verification callback; result type validation remains mandatory and business checks belong in Steps;
- Request Step Recheck resolves the paused current Step; its condition and execute own their observations and business checks;
- plain `@step` marks the smallest independently observable Python boundary and records identity, arguments, conditions, timing, Trusted Actions, evidence, returns, and interruptions;
- first-version `@step` has no timeout, retry, or policy parameters; expected-result and observed lack-of-progress checks stay in ordinary Python, with no generic progress-event or heartbeat framework;
- a Step confirms each important input, never blindly replays an earlier sequence, directly returns from an already-completed state, waits through expected transitions, and raises `ExecutionFailure` for an unknown or observably stalled state;
- Trusted Actions are shipped or human-approved application callables registered once as `observe` for screenshots, OCR, matching, and state reads or `control` for clicks, input, waits, and other execution operations; formal source invokes their literal logical names through `ctx.action()`, while developer inspection derives descriptions and signatures from their Python source without generated wrappers or duplicate schemas;
- Trusted Action implementations alone may catch low-level exceptions, but must record the original and either return an explicit documented result or re-raise a normalized exception, never silently pass or fabricate success;
- the fixed action matrix allows observe in Task/Subworkflow execute, Step condition, and Rule detect; Step execute and Rule recover allow observe/control;
- candidate loading rejects direct, statically visible Trusted Action violations in formal entrypoints but does not trace private-function call chains; Trusted Action wrappers are the authoritative boundary, rechecking classification and the actual execution role before the action and tracing calls, while Agent code cannot create or replace Trusted Actions during a Top-level Execution;
- `wait` is `control` so Workflow code cannot bypass Trusted Action cancellation handling or Step observation and recovery; there are no component-specific lists, user-defined permissions, allow/deny rules, permission objects, or inheritance;
- a runtime Trusted Action access violation is ExecutionFailure, rejected before action and logged with the offending source line; Step-local failure uses Step recovery and never grants forbidden permissions;
- image-using Trusted Actions resolve full logical-name directories on every match, apply optional priority tag groups, verify full hashes and retain Trace evidence; successful regions are recorded only for reference and never change the caller-selected search region; there is no `ctx.asset()`, Asset Handle or direct Asset path in formal source; language is an ordinary optional tag;
- Assets are shared files protected from Agent modification rather than Components. The Agent may propose new template Assets cropped by the executor from a fresh Target Window screenshot taken for that crop request (ADR 0020); it cannot overwrite, rename, or delete existing Asset files. New immutable source, Assets, and complete Manifests go directly into their normal stores; approval and rejection retain them without cleanup (ADR 0021). A separate Asset Usage Index records last successful use and normalized match region only for reference, without changing the search region.
- Step catches execution failures before caller unwinding; errors elsewhere in Workflow execute are reported without replay;
- public Recovery Rules run only after a Step failure, never by polling or recursive Rule recovery;
- if any Recovery Rule `detect()` raises, the executor stops rule enumeration, records the rule and original exception, and produces an Execution Anomaly without treating it as a non-match, invoking any recovery, or checking later rules; the current Step remains paused for Agent handling or Safe Task Termination;
- if the uniquely selected Recovery Rule `recover()` raises or returns a value other than `None`, the executor records a Recovery Rule execution-contract failure and directly produces an Execution Anomaly; it checks no other rule and does not immediately invoke the current Step, whose wrapper and callers remain paused for Agent handling or Safe Task Termination;
- one shared deterministic recovery procedure checks public Rules and invokes the current Step once before optional Agent escalation;
- Task/Subworkflow are never restarted; Step-external failures use common reporting without replay; Safe Task Termination is explicit, not inferred from a code;
- the caller frame remains paused because the wrapper catches the interruption before unwinding; a successful compatible Step return resumes ordinary Python control flow, while already unwound frames are never reconstructed and paused Workflow frames are never hot-patched;
- a replacement Step may reconnect only through a fresh invocation after atomic Working Manifest selection: it keeps the logical name, `@step` role, every existing parameter and default, and the return contract, while allowing only new keyword-only parameters with JSON-compatible defaults;
- the wrapper supplies a new copy of its saved arguments, and reconnection is forbidden when new required data, changed caller control flow, an out-of-scope environment, indeterminate prior effects, or an incompatible result would be required; such a Component applies only to later valid calls;
- Agent help cannot fabricate completion data or bypass remaining Workflow Steps; failure to restore a compatible Step return ends recovery;
- the first version has no Temporary Action Plan, Temporary Plan Adapter, `plan_id`, direct model-action channel, or independent Agent-code execution contract;
- `max_turns` is the sole Runtime Agent Session budget; a dispatched model request consumes one Turn regardless of valid response, invalid output, or provider failure, while formal Step trials use the Step's ordinary finite-wait and interruption contract;
- verified Components are read and executed in the main process on the application service worker thread, without a subprocess isolation guarantee;
- Task Workflow orchestration remains in a background thread of the GUI process; after complete validation and supervised permission, changed Steps and Workflows run through the ordinary Component path.
- the historical Demo candidate runner is evidence only and does not define the formal runtime recovery path;
- Runtime API and Step wrappers append Traces of actual execution; Agent Interaction Logs retain the complete context and response for every Agent Turn and Trace records the corresponding references;
- Trace records each executed formal Component's stable logical name and actual Component ID;
- each Task Workflow run retains Trace, Agent Interaction Logs, screenshots, and evidence as one Run Log Bundle, while the common retention policy removes only whole bundles;
- a local Workflow Run Ledger retains compact per-invocation outcomes, duration, public deterministic recovery counts, Step reinvocation counts, and Agent intervention counts independently of detailed Trace retention; it has no Subworkflow restart fields;
- Task Workflow and Subworkflow use one Ledger record shape with `workflow_kind = task | sub`;
- both use final `success | failure` results: a Subworkflow succeeds on normal return and otherwise fails without a verifier, while Safe Task Termination is performed and counted only once on the owning Task Workflow rather than duplicated across active Subworkflow records;
- one terminal cause gives the same originating `failure_code` to every active Workflow record unwound by it; ancestors are not rewritten to generic child-failure codes, while messages, parent-call IDs, and Trace identify the actual source and already returned Subworkflows remain successful;
- one Agent invocation is one Trace event but is attributed in Ledger to the owning Task Workflow and its active Subworkflow, if any; already returned and sibling Subworkflows remain unaffected, successful affected spans are Agent-assisted, and application-wide totals use unique Trace events rather than summed Ledger counts;
- public Recovery Rule and Step-reinvocation events use the same span attribution without changing strict success when no Agent intervenes; application-wide totals likewise use unique Trace events rather than sums of overlapping Workflow records;
- irreversible progress permits compatible Trace segments to establish Validation Coverage;
- a first occurrence never creates a public Recovery Rule directly; first-version Agent maintenance cannot modify Recovery Rules;
- formal trials execute only verified Python control flow; permanent review exposes successful-trial and Validation Coverage evidence without using either as an automatic gate, and permanent registration still requires human approval;
- Components remain immutable; saved Manifests cannot be modified by the Agent; the current Working Manifest may change by referencing new identities, stores no additions-and-deletions log, resource deletion, reference scanning, Component Usage Index, and cleanup UI are deferred for future discussion and are not current delivery requirements.
- concise Python docstrings support initial Agent retrieval and change with source hashes and Component IDs; tags, separate component documents, and vector retrieval remain deferred.

Stage 2 will not add Component Ref objects, dynamic `ctx.call()` targets, cross-Component implementation imports, nested Recovery Rule calls, arbitrary Task Workflow recovery entrypoints, a Workflow or input DSL, Pydantic input models, general interpreter, complex AST whitelist, RPC framework, shared mutable child Context, security-sandbox claim, or autonomous permanent registration.

The first version also does not export, inherit, migrate, or persist Task Workflow business state, Python loop positions, or entered frames. It terminates safely or restarts from an observable known point after process failure, deferring explicit Checkpoint/Resume design until cross-process or cross-implementation continuation is required.

Stage 2 closes without further architecture work on persistence formats, a complete failure-code catalogue, or game-specific Safe Task Termination actions. Recovery Rules are enumerated by stable logical-name order without adding a Manifest field. Storage formats and failure codes follow actual implemented paths. Runtime Agent recovery, maintenance trials, and their budgets belong to Stage 3.5. Stage 3 began with independent single-Component CLI repair; ADR 0029 adds Developer GUI and existing-Candidate-file repair before its final demo. Agent-assisted Workflow Drafting and autonomous Capability Expansion are deferred. ADR 0026 records the revised implementation completion boundary.

The accepted implementation baseline is maintained in [Stage 2 Minimum Implementation Slices](stage-2-implementation-slices.md). Workflow 2.0 began on a clean orphan branch; the old branch remains a historical reference and rollback path, not a parallel runtime. ADR 0026 replaces the original mailbox completion gate with foundation acceptance, existing single-capability evidence, crop/tag configuration and a runnable teaching sample. Coordinate display, region selection and real business authoring await GUI developer tools; #317 retains the mailbox and outstanding Windows integration acceptance.

## Stage 3 — Agent-assisted Component Repair

以下保留 Stage 3 早期范围基线；当前实现/权限以 ADR 0029–0031 和实施记录为准，Stage 4 的替代范围以 ADR 0032 为准。旧条款不重新施加自动 Publish/试运行禁令，也不表示后续已实现的 GUI 增量仍未开发。

Status: ADR 0025 and ADR 0028 establish the implemented CLI baseline. [ADR 0029](adr/0029-use-explicit-candidate-edit-selection-and-continuous-developer-chat.md) adds the accepted Developer GUI revision; implementation and final Windows/game acceptance remain pending.

- Deliver Capture, Runner, Agent Settings and Agent Repair before 2026-10-29 using existing PySide6, shared application services and fixed pi integration, without CLI subprocess wrappers or a second Agent loop.
- Explicitly initialize/rebuild Candidate from an existing Manifest, confirming nonempty replacement. Repairs and New Conversation preserve Candidate; successful rebuilding starts a new conversation. Runner's persisted selection only determines its next Base Manifest, independently of Candidate and Default.
- Upgrade shared GUI/CLI repair to all existing Candidate files, including candidate manifest.json and Recovery Rules. plan.json stays read-only; no Agent file creation/deletion. Keep bounded live screenshot/Asset tools and complete candidate validation.
- Continuous chat accepts text with optional images. Each message starts one round, with a persisted request limit (default 20, minimum 2) including model checks; one dated UUID4 interaction log per conversation retains per-round evidence. No model/provider fallback.
- Windows DPAPI secrets stay separate from settings/logs; Mac uses temporary memory. GUI only shows whether a key is set; blank ordinary saves preserve it.
- Cumulative Diff compares against the fixed materialized base and hash source. Developer Publish revalidates and creates an immutable Manifest; setting Default is separate. Agent cannot Publish, run candidates or control the game.
- Human Capture freezes the screenshot, previews the crop with logical name and zero or more tags, and saves that exact crop only after confirmation. Passive coordinates reuse Runtime physical client pixels; missing/minimized/ambiguous windows await manual refresh. Agent crops still capture anew.
- Runner and active Agent rounds exclude each other; manual Capture screenshot/save also excludes active or paused tasks. Host enforces this and safely cancels on confirmed exit. Page changes preserve work.
- Demonstrate a real reproducible before/after repair. Validator success is separate from human game acceptance. Runtime Agent Sessions, Working Manifest integration and recovery stay in Stage 3.5; distribution decisions wait until after Stage 4.

See [Stage 3](stage-3-agent-assisted-component-repair.md), [Developer GUI](developer-gui-design.md) and [implementation slices](stage-3-implementation-slices.md). GUI issue #330 is a prerequisite of the #329 TA demo, not implementation evidence.

## Stage 4 — Extensible User GUI and Python Plan

2026-10-28 User GUI P0 讨论：开发者确认本轮仅做布局/信息层级 P0 改进；建议稿 P1 中尚未实现的信息面板等新增内容移至 Stage 6 之后 TODO，已实现的动态循环列表、Manifest 选择、持久通知及外置页导航保留，P2 忽略。详见[逐项讨论记录](user-gui-p0-layout.md)。本轮 grill 与影响审查已完成并获用户授权实施，P0 已完成本地实现及普通回归（475 passed，53 skipped）；原 #333/#334 相关范围按[审查记录](user-gui-p0-impact-review.md)同步，不将此条解释为全部后续阶段延期。

2026-10-27 #332 更新：外置业务页、共享 provider 设置、即时保存与整应用重载已完成本地实现及自动化验证，见[实施记录](stage-4-332-implementation.md)。#333 双语与语言重载已完成本地实现，已获开发者人工验收确认并关闭 #333（[证据](stage-4-333-implementation.md)）；#334 Windows 打包现场验收仍待完成。

状态（2026-10-27）：grill 及 design-impact-review 已完成并经开发者确认，设计接受；#331 已在本地实现，#332–#334 待实施，验证与限制见[实施记录](stage-4-331-implementation.md)。正式规格集中在 [Stage 4](stage-4-extensible-user-gui.md)，取代此前逐轮草案；架构边界见 [ADR 0032](adr/0032-use-python-plans-and-coexisting-user-developer-guis.md)。

- 每 Manifest 唯一 Python Plan，直接替换 JSON Plan；由 Plan 调用 Task，普通任务失败可继续，取消/环境不可继续/Plan 自身错误结束。Developer Agent 可编辑 Candidate Plan并发布后试运行。
- User Dashboard/General Settings 加外置 Python 页面；任务 ID 对接显式 Plan 支持声明，配置跨 Manifest 共用，重启应用完成重载与语言生效。应用内结果/加载错误通知保留至人工关闭。
- User/Developer 同进程双窗口共享活动互斥和生命周期；User 改 Default，Developer 使用 Selected；删除 Developer Runner 页，保留修复试运行。Agent 配置共享内容、独立选用，仅 User 有启用开关。
- 目标是框架及示例可用，必须通过 Windows 打包版页面逻辑验证。完整业务/内置 Agent 页面构建在 Stage 5，完整 Runtime Maintenance 在 Stage 6。

[影响审查与验证证据](stage-4-design-impact-review.md)；[可独立验证的垂直实施阶段](stage-4-implementation-slices.md)。四个阶段已发布为 [#331](https://github.com/HSLix/LixAssistantLimbusCompany/issues/331) → [#332](https://github.com/HSLix/LixAssistantLimbusCompany/issues/332) → [#333](https://github.com/HSLix/LixAssistantLimbusCompany/issues/333) → [#334](https://github.com/HSLix/LixAssistantLimbusCompany/issues/334)，使用原生阻塞关系。不得把设计接受视为已完成实现。

## Stage 5 提案：Workflow Construction & External Knowledge Transfer

**状态：Planning / Pending Discussion。**

### 候选目标、交付与边界

- 开发者给出业务目标，Agent 参考外部成熟项目和 LALC 实现，协助构建完整 Python Workflow；不要求开放世界自主探索或从零学习全部游戏机制。
- 候选验收目标：一版覆盖旧版本主要业务功能的 Workflow，层级和 ctx.call 边界合理，Asset/业务参数完整，可经 User GUI 配置启动，核心流程实际运行，保留来源、迁移及验证记录，减少手工业务代码编写。覆盖清单与验收标准尚未确定。
- AALC（AhabAssistantLimbusCompany）、Charge-Grinder 等仅为候选只读知识来源；参考业务流程、状态判断、识别、策略和异常处理，迁移后遵守 LALC Component、Trusted Action、Manifest、Asset 和验证规范。许可证及复用限制待核实，不直接执行外部源码。
- 将 Agent Repair 扩成 Workbench 的 Construction Mode 是提案：共享 Candidate、文档/源码检索、Asset、Validate、试跑、日志和发布工具；Repair 聚焦失败和兼容性，Construction 聚焦业务目标，各自 Prompt/Policy 待定。允许创建 Plan/Task/Subworkflow/Step/GUI Page 是权限议题，不能覆盖当前 plan.json 只读及专用新增工具边界。Explore Mode 未定。
- 检索候选：本地只读源码、rg/路径/符号搜索、Git Diff/Commit、图片定位与检查、简短 Pi Skill、可搜索迁移历史。按任务读取最小范围、复用经验、更新时优先看差异，每次扩大范围有信息需求，有充分依据后进入修改和验证。
- 先不引入传统 Embedding RAG/向量数据库也是待讨论倾向；实际定位成本高时再评估 Repo Map、轻量索引、BM25 或 Embedding，均未选型。

### Open Questions

- 外部仓库获取、固定版本/更新、许可证；外部逻辑与 LALC 的对应关系如何低成本保存。
- Pi Skill 触发、Repo Map 价值、成熟 Coding Agent 的按需上下文策略；源码阅读、工具调用和探索范围的成本控制。
- Construction Prompt、工具权限、任务拆分；如何保持 ctx.call 层级及恢复语义。
- 旧功能覆盖清单、游戏状态/策略/后置条件验收；如何衡量外部知识减少开发成本。

## Stage 6（原 Stage 3.5）：Runtime Agent Maintenance

**状态：延期至 Stage 6 已确认；新增设计、名称与验收目标待讨论。**

原 Runtime Agent Session、自动异常接管、监督运行/审批、Working Manifest 试跑、暂停 Step 续接等设计，保留在[原运行时设计文档](stage-3.5-agent-runtime-step-recovery-and-maintenance.md)。ADR 0025 的排期由本次确认更新，既有契约不被 AI 草案覆盖。

草案动机：先积累完整、可长期运行的真实业务 Workflow，再有效验证复杂恢复、嵌套恢复和经验复用。此处记录讨论动机，不宣称已核验业务现状或效果。

### 候选目标、交付与边界

- 在真实业务 Workflow 上验证确定性 Recovery Rule 优先、必要时 Agent Repair、受控 Recheck、恢复原 Workflow 及历史经验复用；预算耗尽或无法安全继续时进入统一失败出口。
- 草案循环：规则恢复后重试，耗尽确定性预算后按启用状态升级 Agent；Agent 分析、修改、Validate、提交 Recheck 后结束本轮，由 Runtime 试跑并保存日志/截图/结果，再决定续接、继续修复或失败。嵌套故障及多轮循环的具体语义尚未接受。
- 候选生命周期为短 Agent Turn + Runtime 持续管理 Repair Process，保留挂起状态和父子恢复关系，避免同步等待嵌套 Recheck 导致死锁。
- 经验检索候选为 Raw Agent Interaction History + grep：保留交互/工具、Candidate Revision、Trace/错误、Recheck/截图引用及最终结果；新轮次获得当前故障及上次必要反馈，按需检索更早历史。暂不承诺复杂摘要、知识图谱或 Embedding。
- 严格区分 Runtime Execution State 与 Agent Experience History；经验检索不能代替保证正确性的确定性执行状态，也没有 grep 效果已被证明的结论。

### Open Questions 与既有契约差异

- 嵌套 ctx.call/父子 Recheck 调度、原 Python 调用栈续接、游戏副作用及安全重试、业务后置条件。
- Candidate Revision、Working Manifest 和运行中代码的绑定/切换；Agent Publish 与正式批准边界。
- 人工接管、暂停/继续、Stop 和自动恢复交互；重试、时间、Token、环境操作预算。
- 历史检索成本和上下文大小、有/无历史效果比较；策略层修复是否及何时纳入。
- 当前只有 Step 是恢复边界，Step/Recovery Rule 不能调用正式 Component；“Component 失败后恢复”“嵌套恢复”不能直接解释成任意层恢复。已进入帧保留原代码/局部值，Recheck 的兼容返回值交回原调用者，不自动证明整个 Workflow 成功。

原文档已有 Recovery Ladder、保留栈恢复、历史检索及 Python Plan 讨论，继续在那里细化，不另建重复的运行时规范。

## 待讨论的阶段依赖与旧范围去向

草案建议 Stage 4 提供页面/设置基础，Stage 5 构建真实业务 Workflow，Stage 6 以其验证运行时维护及经验复用。Stage 4 的实际完成门槛以已接受规格为准；Stage 5/6 的具体业务与恢复细节仍待后续讨论，不扩大 Stage 4 范围。

旧 Stage 4 曾列出的监督源码/提案审批及 Manifest 恢复界面，其运行时部分随原 Stage 3.5 延后至 Stage 6；具体 GUI 交付仍待讨论。原统计界面（成功率、Agent 完成率、恢复分布和耗时）、资源清理/引用扫描/Component Usage Index、分发渠道及首版后的执行器子进程评估仍为待讨论事项；Windows 打包版页面逻辑已明确是 Stage 4 门槛。模型可选、确定性流程不依赖模型的现有产品边界保持。

## 既有 Stage 4 之后的讨论备忘（归属待重审）

- Explore learning and memory of game states, using [Agent S](https://github.com/simular-ai/Agent-S) as a reference. Investigate how experience from observations and execution can be retained and retrieved to help recognize game states and handle similar situations. This is future research after Stage 4, not a prerequisite for Stages 3 or 4 or a commitment to adopt the framework.

### Discussion TODO: Workflow Bundle distribution

Discuss distributing the existing **Capability Bundle** (called Workflow Bundle in this proposal: Manifest, referenced Components, Asset images/tag metadata, and other required resources) as an update resource independent of the LALC application, allowing separate Workflow releases and automatic updates. This is a post-Stage-4 discussion proposal, not an implemented updater or an accepted distribution contract.

- **GitHub Releases as the primary source:** automate attaching a Bundle to an existing Release with [`gh release upload`](https://cli.github.com/manual/gh_release_upload), or maintain a separate Workflow Release version line. GitHub currently requires each release asset to be **under 2 GiB** and documents no fixed bandwidth quota for release downloads; recheck the [release limits](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases#storage-and-bandwidth-quotas) when implementing.
- **Mirror 酱 for distribution in mainland China:** reference [MaaResource](https://github.com/MaaAssistantArknights/MaaResource)'s separate resource release approach; apply for a dedicated Resource ID and automate update-package synchronization with GitHub Actions. The client checks versions and obtains downloads through the API; downloads may require a CDK. Consult the [MirrorChyan integration guide](https://github.com/MirrorChyan/docs) and [uploading action](https://github.com/MirrorChyan/uploading-action) for onboarding and integration details.
- **Quark Drive as a backup channel:** evaluate automated Bundle uploads into a designated folder using an official or third-party CLI; the [official upload reference](https://github.com/quark-clouddrive/quarkclouddrive_offical/blob/main/skills/quarkclouddrive/references/file-upload.md) is an initial reference. Prefer this for backup/manual distribution rather than client automatic updates.

All three channels distribute the same Bundle. The client uses one version, full-hash, and signature verification/import path for immutable Components and resources. Retain historical versions and user-local Manifests, without overwriting existing versions; updates affect only subsequent executions. The suggested implementation order is Bundle export/import first, GitHub automated publishing second, then Mirror 酱 and Quark Drive as needed.

## 既有暂缓项（不自动成为新 Stage 4–6 承诺）

- operating-system sandboxing or stronger dynamic-code inspection;
- complex AST import or API allowlists;
- general Workflow DSL or compiler;
- automatic permanent promotion;
- Agent-assisted Workflow Drafting and Trial;
- Agent maintenance of Task Workflows and Subworkflows;
- autonomous Capability Expansion for unsupported goals;
- Unattended Operation for Agent-generated candidate trials;
- skill-maturity labels and broad autonomous general-computer control.

## Stage 6 之后 TODO — User GUI 后续信息功能

2026-10-28 按开发者在 User GUI P0 讨论中的明确要求记录；不作为当前 Stage 4 交付内容：

- 获取并显示最新 GitHub Release 公告。
- 核实并复用旧版软件声明，不编造声明正文。
- 本地/远端版本比较与 Update (TODO) 入口；不因此承诺实现下载、安装或自动更新器。

动态任务循环列表、Manifest 选择、持久执行通知和外置页导航已实现，继续保留，不列为待重新开发事项。P2 项不加入该 TODO。原 #333 的双语等未被本轮提案覆盖的内容保持原状态，具体票据依赖在本轮影响审查中处理。
