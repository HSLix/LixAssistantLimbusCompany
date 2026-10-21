# LALC Reconstruction Plan

This plan keeps the reconstruction dependency-ordered. Accepted boundaries may change only through an explicit reopening such as the Python-first decision below.

## Stage 1: Product and Agent boundaries

Status: accepted and explicitly revised for runtime Agent maintenance and formal trials of unapproved candidate Python.

Locked contracts:

- officially supported objectives run through deterministic Python Workflows without a model;
- only the deterministic executor may invoke the optional Agent;
- the Recovery Ladder remains Deterministic Recovery, Agent, then Safe Task Termination;
- permanent capability changes require validation and human approval;
- every Top-level Execution selects one Base Manifest protected from Agent modification explicitly or through the Default Manifest and copies it into one complete durable Working Manifest; its forms are a directly started Task Workflow, Subworkflow, or Step and one Automation Plan with its sequential Task Workflows;
- Agent-generated formal candidate Python may receive a Working Manifest trial before permanent approval only after Supervised runtime confirmation;
- the first version reads and executes verified Components in the main process; TODO after the first release: evaluate moving executor execution into a subprocess, including Context transport, cancellation, and original-error propagation. Current execution is not a security sandbox.

## Stage 2: Python-first Workflow and deterministic execution

Status: accepted and complete. Further changes require explicitly reopening the Stage 2 contract.

Confirmed contracts:

- Task Workflow, Subworkflow, and Step are immutable Python Components loaded as ordinary modules after their exact source bytes are verified against their Component IDs;
- exactly one parameterless `@task_workflow`, `@sub_workflow`, or `@step` on each formal entrypoint is the sole component-role source; Manifest, paths, names, and tags do not duplicate or infer `component_kind`;
- each Task Workflow, Subworkflow, and Step has one source file with one decorated execute; only Step may expose a matching optional condition; Task/Subworkflow condition and standalone verify callbacks are rejected;
- formal Task Workflow, Subworkflow, Step, Step condition, Recovery Rule, and every private function in their files contain no `except`; `try/finally` remains available for cleanup, but loaders reject `return`, `break`, `continue`, or `raise` in every `finally` without reachability or rethrow analysis so the original exception propagates naturally;
- each Manifest is one complete document containing executable `logical_name → immutable Component ID` mappings, dedicated `recovery_rules` and `trusted_actions` mappings, and an `assets` mapping from semantic name and language to shared relative path plus complete hash;
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
- Trusted Actions are immutable shipped or human-approved Components registered once as `observe` for screenshots, OCR, matching, and state reads or `control` for clicks, input, waits, and other execution operations; formal source invokes their literal logical names through `ctx.action()`, while developer inspection derives descriptions and signatures from their Python source without generated wrappers or duplicate schemas;
- Trusted Action implementations alone may catch low-level exceptions, but must record the original and either return an explicit documented result or re-raise a normalized exception, never silently pass or fabricate success;
- the fixed action matrix allows observe in Task/Subworkflow execute, Step condition, and Rule detect; Step execute and Rule recover allow observe/control;
- candidate loading rejects direct, statically visible Trusted Action violations in formal entrypoints but does not trace private-function call chains; Trusted Action wrappers are the authoritative boundary, rechecking classification and the actual execution role before the action and tracing calls, while Agent code cannot create or replace Trusted Actions during a Top-level Execution;
- `wait` is `control` so Workflow code cannot bypass Trusted Action cancellation handling or Step observation and recovery; there are no component-specific lists, user-defined permissions, allow/deny rules, permission objects, or inheritance;
- a runtime Trusted Action access violation is ExecutionFailure, rejected before action and logged with the offending source line; Step-local failure uses Step recovery and never grants forbidden permissions;
- image-using Trusted Actions accept semantic Asset names and internally resolve the game language, Working Manifest path and hash, fallback language and Trace evidence; successful regions are recorded only for reference and never change the caller-selected search region; there is no `ctx.asset()`, Asset Handle, language-neutral Asset, or direct Asset path in formal source;
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

Stage 2 closes without further architecture work on persistence formats, a complete failure-code catalogue, or game-specific Safe Task Termination actions. Recovery Rules are enumerated by stable logical-name order in implementation without adding a Manifest field. Storage layout and formats use the most direct local representation when implementation reaches them; failure codes are added only for real execution paths; each vertical slice supplies the concrete safe action appropriate to its supported game state. Runtime Agent recovery, maintenance trials, and their budgets belong to Stage 3. Agent-assisted Workflow Drafting and autonomous Capability Expansion are deferred. The immediate next activity is planning the minimum implementation slices and their acceptance order.

The accepted implementation baseline is maintained in [Stage 2 Minimum Implementation Slices](stage-2-implementation-slices.md). Workflow 2.0 begins on a clean orphan branch in this repository; the old branch remains the historical reference and rollback path rather than a runtime that the new code must coexist with. The first real Task Workflow is selected when that slice begins, using mailbox collection as the initial smallest candidate.

## Stage 3: Agent Runtime Step Recovery and Maintenance

Status: architecture accepted, including the #310 and #311 decisions. Agent runtime implementation remains future work.

- only an Execution Anomaly caught while an existing supported Task Workflow remains paused inside an `@step` wrapper starts a bounded Runtime Agent Session;
- local and remote models implement one Agent Adapter contract that only transports a self-contained Context Snapshot, normalizes provider failures, and parses one allowed Turn result; it never performs actions, writes files, changes a Manifest, invokes formal code, or decides recovery and termination;
- the Agent may propose one complete Manifest changing Steps, Task Workflows, or Subworkflows, with reasons for each change; Trusted Action, Recovery Rule, and new-objective changes are outside the current scope; The Agent may propose new template Assets cropped by the executor from a fresh Target Window screenshot taken for that crop request (ADR 0020); it cannot overwrite, rename, or delete existing Asset files.
- new source files, screenshot-derived Assets, and complete attempted Manifests are saved directly in their normal stores; review records approval or rejection without deleting files;
- a complete candidate Working Manifest is atomically selected only when the executor can immediately arrange a legal formal trial call;
- the first fresh current-Step call supplies behavior evidence; success commits the whole selected Manifest for later calls, while failure leaves the execution paused for another Agent choice or termination without automatic rollback;
- an entered Python frame is never replaced, and Manifest rollback cannot undo external game actions;
- after Top-level Execution ends, only its current Working Manifest is presented as the Capability Proposal when its ID has not already received permanent approval, including when final Task verification failed; returning to the Base Manifest or another approved ID skips repeated approval, and intermediate attempts are not separately reviewed;
- permanent approval has no universal business-success threshold in Stage 3: the system presents whether a successful formal trial occurred together with the candidate and recorded evidence, while the supervisor decides whether it is sufficient; no trial result, Step result, Task result and checking-Step evidence, or unattended run can approve automatically;
- a topmost modal Capability Approval Dialog requires exactly one whole-proposal approve-or-reject decision: approval marks the reviewed Manifest ID as permanently published, rejection grants no permanent approval, and both retain execution and review evidence; after approval, a separate window asks whether to set the approved current Working Manifest as Default;
- `max_turns` is the only Runtime Agent Session budget; there is no Session deadline, action budget, candidate budget, or plan timeout;
- every Agent Turn uses a self-contained Context Snapshot rebuilt from local authoritative state and never depends on provider-retained conversation history; detailed context selection remains undecided;
- provider, model, System Prompt version, generation parameters, and Agent Adapter version are fixed for each Runtime Agent Session, with no within-Session model switching, routing, or fallback;
- a Runtime Agent Session succeeds only through a compatible normal return from a fresh formal invocation of the current Step; the Task Workflow then continues its remaining ordinary Steps, and a later Step anomaly creates a new Session with a fresh `max_turns` while sharing the Top-level Execution's Working Manifest and retained immutable files;
- the first version supports only Supervised Operation: every complete proposal is reviewed and confirmed before trial, while unattended trial and persisted operating-policy selection are deferred;
- proposal confirmation is an explicit approve-or-reject decision; rejection requires feedback for the next Agent Turn, while the existing system stop remains a separate immediate cancellation control;
- a topmost modal Supervised Review Dialog blocks main-window interaction until the supervisor approves one trial, rejects with feedback, or confirms Cancellation; its close action and Escape key cannot bypass the decision;
- the cooperative Run Gate uses `threading.Condition` without polling and waits before new Trusted Actions or Agent Turns; Manifest selection does not wait, and pause never interrupts an operation already permitted to start;
- changed Steps and Workflows use their ordinary role-based Trusted Action access after runtime permission; Stage 3 adds neither a high-risk action taxonomy nor per-action confirmation;
- runtime permission lets the complete selected Manifest execute in the current Top-level Execution; permanent whole-Manifest publication is a separate decision after that execution ends and does not change the Default selection;
- invalid output, rejected validation, user rejection with feedback, a non-activating switch failure, or a failed current-Step call proceeds to the next Agent Turn when budget remains; a failed call pauses without automatic rollback, and the Agent may base the next attempt on any retained Manifest ID;
- main-window stop and review-window termination share one Cancellation path that wakes cooperative pause, prevents later gated work, and leaves the GUI and Target Window open;
- Cancellation after Manifest selection ends the Top-level Execution without automatically changing the last selected Manifest;
- every complete Manifest used for an attempt is durably retained by Manifest ID; an existing Manifest reused in another attempt keeps that ID while Trace distinguishes attempts;
- Agent-assisted Workflow Drafting and autonomous Capability Expansion remain explicitly deferred.

The Stage 3 architecture Grill is closed. The detailed accepted baseline is [Stage 3 Agent Runtime Step Recovery and Maintenance](stage-3-agent-runtime-step-recovery-and-maintenance.md). Context fields, validators, UI behavior, persistence mechanics, and Demo acceptance are intentionally left to the next minimum code experiment plan.

## Stage 4: Application structure, UI, and packaging

Status: planned.

- CLI and desktop UI call the same application and execution services;
- the UI exposes task execution, Agent configuration, supervised Step and Workflow source review, proposal review, and Manifest recovery;
- TODO for future discussion: resource deletion, reference scanning, Component Usage Index, and cleanup UI; no maintenance policy or UI is committed for this version.
- the UI exposes per-Workflow strict success rate, Agent-assisted completion, recovery breakdown, and average duration from the local Workflow Run Ledger;
- a packaging spike verifies main-process immutable module loading, external assets, and Trace persistence; TODO after the first release: evaluate moving executor execution into a subprocess and the required Context transport, cancellation, and original-error propagation;
- packaged formal automation must remain usable without a model.

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
