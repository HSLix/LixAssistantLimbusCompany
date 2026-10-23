# LALC Reconstruction Plan

This plan keeps the reconstruction dependency-ordered. Accepted boundaries may change only through an explicit reopening such as the Python-first decision below.

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

Stage 2 closes without further architecture work on persistence formats, a complete failure-code catalogue, or game-specific Safe Task Termination actions. Recovery Rules are enumerated by stable logical-name order without adding a Manifest field. Storage formats and failure codes follow actual implemented paths. Runtime Agent recovery, maintenance trials, and their budgets belong to Stage 3.5. Stage 3 independently validates single-Component repair through a manual CLI. Agent-assisted Workflow Drafting and autonomous Capability Expansion are deferred. ADR 0026 records the revised implementation completion boundary.

The accepted implementation baseline is maintained in [Stage 2 Minimum Implementation Slices](stage-2-implementation-slices.md). Workflow 2.0 began on a clean orphan branch; the old branch remains a historical reference and rollback path, not a parallel runtime. ADR 0026 replaces the original mailbox completion gate with foundation acceptance, existing single-capability evidence, crop/tag configuration and a runnable teaching sample. Coordinate display, region selection and real business authoring await GUI developer tools; #317 retains the mailbox and outstanding Windows integration acceptance.

## Stage 3 — Agent-assisted Component Repair

Status: accepted scope under ADR 0025, revised by ADR 0028; implementation and model-backed acceptance pending.

- Manually start an independent CLI with one existing Component, game screenshots, exception information, and necessary context.
- Prefer pi through a Python-hosted subprocess and dedicated restricted tools; validate the first integration on Mac, then pin the same version for Mac and Windows. Use Default Manifest to rebuild Developer Candidate before repair, replacing any existing draft only after the source and target have been checked.
- Output complete candidate Component source, its Diff, and validation results; retain the model inputs, tool operations, and final outputs for the entire CLI invocation.
- Reuse Developer Candidate / ManifestManager for subsequent human-reviewed Publish. Never overwrite formal Components, existing Manifests/images or old hash-to-tag entries, automatically publish, or modify Default Manifest.
- Limit the first version to one existing Component. Permit dedicated live screenshot and fresh-crop Asset addition tools; duplicate logical-name/hash pairs retain the original image and tags. No Runtime Agent Session, automatic anomaly takeover, game controls, multi-Component editing, automatic real-game trial, or runtime continuation.
- LALC owns saved endpoint/model configuration and a configurable request limit, default 20. Windows stores named secrets with DPAPI; Mac development uses transient in-memory secrets. Check image support, fix the selected model per invocation and do not fall back to another provider/model.
- Retain Agent Interaction Logs in the data directory grouped by date and UUID4, including actual context/images, model and tool exchanges, final candidate/Diff/validation, effective non-secret configuration, request count and end reason. Missing information ends the invocation with an explanatory final answer; failures and cancellation retain artifacts.
- Demonstrate at least one reproducible before/after repair case. Human-run behavior verification is separate from Validator success and from the repair CLI.

The accepted scope and acceptance evidence are in [Stage 3 — Agent-assisted Component Repair](stage-3-agent-assisted-component-repair.md).

The confirmed six implementation slices and native issue dependencies are in [Stage 3 Implementation Slices](stage-3-implementation-slices.md). Publication is complete; implementation and model-backed/Windows acceptance remain pending.

## Stage 3.5 — Agent Runtime Step Recovery and Maintenance

Status: deferred. ADR 0025 transfers the prior Stage 3 runtime architecture here without requiring it for the Stage 3 experiment.

Runtime Agent Recovery, Runtime Agent Sessions, automatic anomaly takeover, supervised execution and approval, complete Working Manifest trials, paused-Step reconnection, Working Manifest integration and multi-Component evolution belong here. This stage reuses the independent screenshot, bounded Asset addition and interaction-log capabilities of Stage 3 (ADR 0028). The prior accepted runtime boundaries, including #310/#311, are retained in [Stage 3.5](stage-3.5-agent-runtime-step-recovery-and-maintenance.md). The Recovery Ladder revision remains a discussion TODO rather than an accepted implementation change.

## Stage 4: Application structure, UI, and packaging

Status: planned.

- CLI and desktop UI call the same application and execution services;
- TODO: a developer coordinate display shows the physical client-pixel mouse position relative to the Target Window in real time, using the same coordinate system as screenshots, crop regions, and click inputs; mark positions outside the client area explicitly. This is a future GUI aid, not a change to the current coordinate-input crop API.
- the UI exposes task execution, Agent configuration, supervised Step and Workflow source review, proposal review, and Manifest recovery;
- TODO for future discussion: resource deletion, reference scanning, Component Usage Index, and cleanup UI; no maintenance policy or UI is committed for this version.
- the UI exposes per-Workflow strict success rate, Agent-assisted completion, recovery breakdown, and average duration from the local Workflow Run Ledger;
- a packaging spike verifies main-process immutable module loading, external assets, and Trace persistence; TODO after the first release: evaluate moving executor execution into a subprocess and the required Context transport, cancellation, and original-error propagation;
- packaged formal automation must remain usable without a model.

## TODO after Stage 4

- Explore learning and memory of game states, using [Agent S](https://github.com/simular-ai/Agent-S) as a reference. Investigate how experience from observations and execution can be retained and retrieved to help recognize game states and handle similar situations. This is future research after Stage 4, not a prerequisite for Stages 3 or 4 or a commitment to adopt the framework.

### Discussion TODO: Workflow Bundle distribution

Discuss distributing the existing **Capability Bundle** (called Workflow Bundle in this proposal: Manifest, referenced Components, Asset images/tag metadata, and other required resources) as an update resource independent of the LALC application, allowing separate Workflow releases and automatic updates. This is a post-Stage-4 discussion proposal, not an implemented updater or an accepted distribution contract.

- **GitHub Releases as the primary source:** automate attaching a Bundle to an existing Release with [`gh release upload`](https://cli.github.com/manual/gh_release_upload), or maintain a separate Workflow Release version line. GitHub currently requires each release asset to be **under 2 GiB** and documents no fixed bandwidth quota for release downloads; recheck the [release limits](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases#storage-and-bandwidth-quotas) when implementing.
- **Mirror 酱 for distribution in mainland China:** reference [MaaResource](https://github.com/MaaAssistantArknights/MaaResource)'s separate resource release approach; apply for a dedicated Resource ID and automate update-package synchronization with GitHub Actions. The client checks versions and obtains downloads through the API; downloads may require a CDK. Consult the [MirrorChyan integration guide](https://github.com/MirrorChyan/docs) and [uploading action](https://github.com/MirrorChyan/uploading-action) for onboarding and integration details.
- **Quark Drive as a backup channel:** evaluate automated Bundle uploads into a designated folder using an official or third-party CLI; the [official upload reference](https://github.com/quark-clouddrive/quarkclouddrive_offical/blob/main/skills/quarkclouddrive/references/file-upload.md) is an initial reference. Prefer this for backup/manual distribution rather than client automatic updates.

All three channels distribute the same Bundle. The client uses one version, full-hash, and signature verification/import path for immutable Components and resources. Retain historical versions and user-local Manifests, without overwriting existing versions; updates affect only subsequent executions. The suggested implementation order is Bundle export/import first, GitHub automated publishing second, then Mirror 酱 and Quark Drive as needed.

## Explicitly deferred

- operating-system sandboxing or stronger dynamic-code inspection;
- complex AST import or API allowlists;
- general Workflow DSL or compiler;
- automatic permanent promotion;
- Agent-assisted Workflow Drafting and Trial;
- Agent maintenance of Task Workflows and Subworkflows;
- autonomous Capability Expansion for unsupported goals;
- Unattended Operation for Agent-generated candidate trials;
- skill-maturity labels and broad autonomous general-computer control.
