# Domain Docs

2026-11-02 验收状态：开发者明确确认 #339 通过，已按 completed 关闭；#340 保持 OPEN，等待开发者 Windows 实验验证后另行确认。此前“两票待验收 / 一起关闭”状态由本条替代；不表示 Windows 成品或真实游戏已验收。见[当前记录](../page-review-tabs-implementation.md)。

2026-11-02 页面审批试用修订：拟安装页加载 / 接口 / 注册失败不显示审批，直接把错误返回同轮 Agent 修正；成功才显示默认 Proposed 的 Current / Proposed / Review 三 Tab，切换保留页面实例与独立试填。Review 集中呈现 Agent 总结、ID 与版本，三操作和人工快照安装保持。见[决定](../stage-5-339-340-decisions.md#2026-11-02-试用反馈后的修订讨论)及[修订记录](../page-review-tabs-implementation.md)。此前双栏 / 失败留窗规则为历史。

2026-11-02 #339 / #340 合并本地实施：Construct 专属 Session 单文件页面草稿、双页应用级模态预览及人工固定版本安装已接入。配置及 Plan 影响由 Agent 总结，宿主不固定检验配置兼容、不自动 submit；两侧配置仅内存，安装不导入试填、不改 Default、不自动重载。两票待开发者验收，见[决定](../stage-5-339-340-decisions.md)及[实施记录](../stage-5-339-340-implementation.md)。下文页面待实现描述为历史状态。

2026-11-01 临时原始输出：每条模型消息生成时，在本轮用户消息后、Agent 工具 / 回答前显示默认收起的内联临时区，状态文字作为折叠标题，可展开查看文字、接口返回的 thinking 和生成中的工具名称 / 参数；完整生成过程按轮次保留，最终回答后仍可展开 / 收起，重开历史从已有完整消息恢复且默认收起；取消或错误只清除未完成的流式缓冲。每轮强制连接 / 图片推理预检已取消，正式请求从第 1 次计数，图片直接随正式请求发送；GUI 设置页手动连接 / 模型状态检查保留（读取模型列表，不请求推理）。发送前配置 / 图片能力校验及格式纠正额度保持。下文预检要求和历史验证记录以本条现行规则为准。见[决定](agent-raw-output-decisions.md)、[影响审查](agent-raw-output-impact-review.md)。

2026-11-01 #338 本地实施：GUI Construct / Repair 已有统一文字人工反馈工具与非模态窗口，空确认与跳过区分，无自动超时；取消唤醒等待，旧回调失效，同轮额度 / Session 日志保持。CLI / Runtime 不继承；开发者简单验证通过，#338 已按 completed 关闭，见[实施记录](../stage-5-338-implementation.md)。下文“#338 待实现”保留为历史状态。

2026-11-01 游戏版本历史：每轮不可变观测、按游戏版本 / Steam Build ID 组合检索、跨入口只读历史工具已接入；旧历史不导入，Unknown 不代表可推断版本。独立 pi-probe 已删除；本地验证及限制见[实施记录](../game-version-session-implementation.md)，用法见[用法](../game-version-history.md)及 [ADR 0035](../adr/0035-associate-agent-history-with-per-round-game-observations.md)。

2026-11-01 #337 本地实施：GUI 两种模式已可只读检索 / 查看数据目录知识库及受控 Git 内容，目录入口在缺失时创建空目录。列目录不 fetch，首次内容访问才尝试；系统 Git 不可用跳过记日志，CLI / Runtime 不继承。当前用法及验证边界见[实施记录](../stage-5-337-implementation.md)；#337 已经开发者人工验收通过并关闭。下文“#337 待实现”保留为历史状态。

2026-11-01 OCR：observe.ocr 使用已有有效截图；game_screenshot 在原图/网格之外附同图完整 OCR JSON，OCR 故障可保留截图并返回 ocr_error，取消/窗口失效不降级。暂不支持韩文。接口与验证边界见 [OCR 用法](../ocr.md)及[影响审查](../ocr-integration-impact-review.md)。

2026-10-31 #336 本地实施：GUI 已接入独立 Construct / Repair Session 工作台、历史续聊及多 Manifest 参考 / 共享只读工具；模式与来源在首条消息提交时固定。删除 Developer GUI 人工运行入口，Agent 试运行完整保留。当前用法及验收限制见[实施记录](../stage-5-336-implementation.md)；#336 等待开发者验收，#337–#340 与 Stage 6 仍待实现。下文旧重建 / Runner 用法仅为历史实现描述。

2026-10-31 Manifest 参考补充（#336 待实现）：GUI 附件可多选已发布版本，参考重点写在消息；GUI Construct / Repair 与 CLI Repair 均可只读查看任意已发布 Manifest，无须先附加。附件为上下文信息，不是授权清单；查看不导入 / 执行源码，不改草稿来源或任何运行版本选择。Runtime Repair 白名单已明确包含该只读能力，实际接入留 Stage 6。见[专项影响审查](../stage-5-manifest-reference-impact-review.md)。

2026-10-31 #335 本地实施：CLI Repair 已使用独立持久 Session，按明确 Manifest 创建或按 Session ID 恢复，空闲输入不占锁，中断不重放；手工 Candidate 不受 CLI Agent 接管。GUI Session 接入仍待 #336，其余 Stage 5 增量待实现；见[实施记录](../stage-5-335-implementation.md)。下文待实现描述为完整阶段目标。

2026-10-31 Stage 5 已确认、待实现：Developer GUI 统一为 Agent 工作台，Construct / Repair 按 Session 固定模式并分别提供初始 Prompt 与工具白名单；GUI 两种模式均可请求人工答复或操作反馈，页面构建仅 Construct 提供。每 Session 独立持久保存 Candidate、固定基线、聊天和页面草稿，不重建、不自动删除；CLI Repair 与 GUI 共用 Session 存储，按入口限权，不再使用手工 Candidate。Developer GUI 的 Manifest 选择及人工运行入口删除，不提供“应用到 User GUI”快捷设置；User GUI 普通启动保持，Agent 的显式版本试运行和日志能力完整保留。页面采用同进程应用级模态双栏对比，锁住其他 LALC 窗口，配置仅内存，由人确认预览版本后安装；不做自动版本冲突检测。见 [Stage 5 规格](../stage-5-agent-workbench.md)、[ADR 0034](../adr/0034-extend-developer-agent-with-reviewed-page-drafts.md)及[影响审查](../stage-5-design-impact-review.md)。下文现有用法与历史证据不表示新能力已实现。

2026-10-31 外部知识库目标（待实现）：数据目录中的 Git / 非 Git 资料供 GUI 两种模式只读查阅。每轮首次访问仓库自动尝试一次 fetch，可显式 fetch，每次尝试后 status；以当前分支 upstream 的前后提交报告更新，无 upstream / detached HEAD 报告不确定。受控工具限 diff / show / fetch / log，不更新工作区，不授予通用终端或编辑权限；CLI 不自动继承 GUI 新授权，Runtime 保持 Stage 6 边界。详见[版本语义](../stage-5-agent-workbench.md#外部知识与-git-内容的版本语义)。

2026-10-27 Fluent GUI：User/Developer 已正式迁到完整 FluentWindow，固定页/外置页及三页开发工具使用 Fluent 导航；原有共享服务、即时保存、单一编辑入口和重载边界保持。当前操作与验证见[迁移记录](../fluent-gui-migration.md)。


How engineering skills should consume this repository’s domain documentation.

## Before exploring, read these

- `CONTEXT.md` at the repository root.
- `CONTEXT-MAP.md` if it exists; it points to context-specific `CONTEXT.md` files.
- Relevant ADRs under `docs/adr/`.

If these files do not exist, proceed silently. Domain-modeling workflows create them lazily when terminology or architectural decisions are resolved.

## File structure

This repository uses a single-context layout:

```
/
├── CONTEXT.md
├── docs/
│   └── adr/
├── src/
│   └── lalc/
├── tests/

```

`CONTEXT.md` records the shared domain language and boundaries. System-wide architectural decisions belong under `docs/adr/`.

## Use the glossary’s vocabulary

When an output names a domain concept—in an issue title, proposal, hypothesis, or test name—use the term defined in `CONTEXT.md`.

If the required concept is missing, reconsider whether the term belongs to the project or record the gap for domain modeling.

## Flag ADR conflicts

If proposed work contradicts an existing ADR, surface the conflict explicitly instead of silently overriding the decision.

## Stage 4 accepted target versus current implementation

2026-10-30 当前状态：#334、#329、#323、#312 已按开发者试用反馈及明确收尾决定关闭；完整验收未补齐，未验证项目不计通过。见[关闭记录](../stage-3-4-closure-2026-10-30.md)。历史继续由这些 issue 等待完整验收的状态由本次决定替代。

2026-10-30 #334：接受 Windows x64 本地构建双 ZIP、业务数据与程序分离、成品 Candidate 归入用户数据；源码开发保留项目草稿。默认随包 pi 优先，仅请求前的限定故障可回退一次；不因预检后又启动进程而重开回退。Agent 回归不调用真实模型，Windows 真实模型验证不属于本票。当前[本地实施](../stage-4-334-implementation.md)不等于 Windows 成品验收，构建／验收见[说明](../windows-packaging.md)。

[ADR 0032](../adr/0032-use-python-plans-and-coexisting-user-developer-guis.md) and the [Stage 4 specification](../stage-4-extensible-user-gui.md) are the accepted target: one immutable Python Automation Plan per Manifest, Plan→Task result boundaries, coexisting User/Developer windows and shared activity ownership, editable Candidate Python Plan, and no independent Developer Runner page. JSON Plan execution is replaced without compatibility; old immutable data is not rewritten. Shared settings pages remain outside Manifest/Agent writes. The source implements the #331 Python Plan and coexisting-window slice; see [implementation evidence](../stage-4-331-implementation.md). The #332 external pages and per-provider shared Agent settings are implemented locally; see [#332 evidence](../stage-4-332-implementation.md). The #333 bilingual GUI and language reload are implemented locally and have passed developer manual acceptance; #333 is closed; see [#333 evidence](../stage-4-333-implementation.md). GUI component wording follows one shared startup language; specific diagnostics retain their original language. Only User General Settings edits the language, and external pages may opt in while legacy pages retain their text. Developer owns the only Agent settings editor while its window is open; User regains editing after saved handoff. Windows packaged acceptance remains pending. The Stage 2/3 descriptions below are historical where superseded: plan.json read-only and four-page descriptions are not current requirements. Do not claim Windows packaged acceptance is complete.

## Agent changes to Manifests and Assets

ADR 0033 changes only new Agent Interaction Log storage: conversation-local, lossless content references with a self-contained directory. Preserve full live GUI events and model/tool transport, relative reference boundaries, hash checks and redaction. Old logs remain untouched; do not add a history viewer, automatic migration or context pruning as part of this change. See [log design](../agent-interaction-log-design.md).

ADR 0030 supersedes the Developer Agent automatic Publish/execution prohibition below: Developer Policy may publish complete immutable versions and trial explicitly selected saved Manifest IDs through the existing executor, then inspect Run logs. Trial results return to the same round; they do not grant runtime permanent approval or change Default. GUI trials use a modal log window without requesting game focus. Runtime Policy is deferred to Stage 6 (formerly Stage 3.5); only the schedule changed. Candidate file and Asset protection below still applies.

Stage 3 originally implemented independent single-Component repair. ADR 0029 now accepts Developer GUI and shared multi-file repair: explicit Candidate initialization, all existing Candidate files (including candidate manifest.json and Recovery Rules), existing Python Plan editing under ADR 0032, dedicated Candidate creation tools, no generic creation/deletion, continuous conversations and manual review/Publish. The shared host and current three-page Developer GUI implement these changes; see the Developer GUI design for automated versus pending real-model/Windows acceptance. ADR 0028's live screenshot and bounded Asset additions remain. Runtime Agent Sessions, Working Manifest integration and supervised runtime trials are deferred to Stage 6 (formerly Stage 3.5).

- Existing published Manifests, formal source, images and old hash-to-tag entries remain read-only to the Agent, including through generated code or executor requests. ADR 0031 permits only the dedicated remove_asset archive path to remove an active Asset image and its local tag entry; it never permits overwriting old image bytes or general deletion. The editable Candidate manifest is distinct from a published Manifest. The dedicated crop tool may add a new image and its tag entry under ADR 0028.
- ADR 0027 replaces the per-Manifest Asset Library. Resolve the full logical name directly to an assets/ directory containing full-hash PNGs and asset-tag.json (hash → tags). Images without a tag entry participate with []; all writers explicitly store [] for new untagged hashes. Language is an ordinary optional tag, and priority_tags uses any-tag overlap with whole-preferred-batch matching before fallback. Read directory/tags anew each match, not at Manifest load or from a cross-call cache. Existing images are never overwritten; tags are replaced by the supplied list, preserving order and duplicates; omitted or empty tags clear prior labels. No Candidate or publish is required for Assets. The one-time old-data disposal is explicitly developer-authorized, not run-end cleanup.
- Do not design Agent repair around editing an old image and then fixing old Manifest hashes; that operation is forbidden. Human GUI crop confirmation is accepted in ADR 0029; a general Asset manager remains out of scope.
- ADR 0031: preview_crop captures the game anew, returns crop-boundary and clean crop images plus same-image matches, and retains a conversation-scoped preview_id. crop_asset(preview_id) saves those exact original pixels without recapturing; the Workflow Trusted Action observe.crop_asset retains its fresh-capture behavior. game_screenshot also returns a separate 40px grid image; overlays never enter crops, matching or archived original screenshots. remove_asset captures a fresh clean screenshot and archives the original image, tags and removal metadata before removing the active image/local tag relation; other Logical Names are unaffected.
- ADR 0028 narrows Agent crop permissions: an existing logical-name/hash pair reuses its image and original tags, even when new tags are requested. Adding a new hash may add its tag entry without changing existing entries. Developer crop/tag tools retain ADR 0027's tag-replacement semantics. ADR 0029 supersedes the prior automatic Default-to-Candidate reset and single-target write limits: initialize/rebuild explicitly, preserve Candidate across rounds and New Conversation, and enforce the per-round existing-file boundary with the existing Python Plan editable under ADR 0032. The implemented increment permits only add_component / add_recovery_rule to create and register Candidate source from filename, logical_name and source; successful additions join the same round edit boundary, while arbitrary creation and deletion remain forbidden. Source/Manifest changes must succeed together; full validation, Publish and Default remain separate.

See [ADR 0027](../adr/0027-resolve-assets-independently-with-optional-priority-tags.md), historical [ADR 0024](../adr/0024-use-a-dedicated-asset-library-for-each-manifest.md), [ADR 0020](../adr/0020-allow-screenshot-derived-assets-and-explicit-search-regions.md) and [ADR 0021](../adr/0021-retain-created-files-and-defer-resource-maintenance.md).

## Application-owned Trusted Actions

ADR 0023 removes per-Manifest Trusted Action registration. Register actions once in the application and keep `ctx.action()` as the checked call boundary for every Manifest. Preserve caller/phase permissions, observe/control classification, validation, timing, Trace, original errors, and user interruptions. Remove pure forwarding Action files when migrating examples; do not replace them with direct backend calls. Derive the Stage 3 action-list function from application registration and existing signatures/docstrings. The #321 migration is implemented. ADR 0026 permits a new teaching sample without restoring the old examples; ADR 0027 removes Candidate Asset sidecars; new samples contain Components only.
