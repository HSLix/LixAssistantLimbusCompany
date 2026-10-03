# LALC Reconstruction Plan

This plan keeps the reconstruction dependency-ordered. Accepted boundaries may change only through an explicit reopening such as the Python-first decision below.

## Stage 1: Product and Agent boundaries

Status: accepted and explicitly revised for runtime Agent maintenance and formal trials of unapproved candidate Python.

Locked contracts:

- officially supported objectives run through deterministic Python Workflows without a model;
- only the deterministic executor may invoke the optional Agent;
- the Recovery Ladder remains Deterministic Recovery, Agent, then Safe Task Termination;
- permanent capability changes require validation and human approval;
- every Top-level Execution selects one immutable Base Manifest explicitly or through the Default Manifest and copies it into one complete durable Working Manifest; its forms are a directly started Task Workflow, Subworkflow, or Step and one Automation Plan with its sequential Task Workflows;
- Agent-generated formal candidate Python may receive a Working Manifest trial before permanent approval only after Supervised runtime confirmation;
- first-version subprocess execution is explicitly not a security sandbox, and stronger enforcement is deferred.

## Stage 2: Python-first Workflow and deterministic execution

Status: accepted and complete. Further changes require explicitly reopening the Stage 2 contract.

Confirmed contracts:

- Task Workflow, Subworkflow, and Step are immutable Python Components loaded as ordinary modules after their exact source bytes are verified against their Component IDs;
- exactly one parameterless `@task_workflow`, `@sub_workflow`, or `@step` on each formal entrypoint is the sole component-role source; Manifest, paths, names, and tags do not duplicate or infer `component_kind`;
- each Task Workflow, Subworkflow, or Step occupies one Python file with exactly one decorated `execute`; Task Workflow and Step may also contain their optional `condition`, Task Workflow contains its required `verify`, while Subworkflow exposes only `execute`; result classes and ordinary implementation code remain in the same file and no file contains multiple formal Components;
- formal Task Workflow, Subworkflow, Step, condition, verifier, Recovery Rule, and every private function in their files contain no `except`; `try/finally` remains available for cleanup, but loaders reject `return`, `break`, `continue`, or `raise` in every `finally` without reachability or rethrow analysis so the original exception propagates naturally;
- each Manifest is one complete document containing executable `logical_name → immutable Component ID` mappings, dedicated `recovery_rules` and `trusted_actions` mappings, and an `assets` mapping from semantic name and language to shared relative path plus complete hash;
- formal Components call one another only through `ctx.call(logical_name, **arguments)`; it resolves and validates the current Working Manifest entry on every call and stores no Component Ref or implementation cache;
- every `ctx.call()` target is a string literal; before each Working Manifest atomic update, the executor validates every formal target and role permission against the complete resulting candidate Manifest, while runtime validates resolution and role again and records the actual identity;
- every `ctx.call()` in a Task Workflow or Subworkflow source file belongs to that file's single Component, including calls in private or apparently unreachable functions; Step, `condition`, `verify`, and Recovery Rule source may contain no `ctx.call()`, and the loader performs no reachability or branch analysis;
- any complete-Manifest validation error rejects the entire atomic switch and leaves the old Working Manifest active;
- runtime `ctx.call()` rechecks only target resolution and role and records the call; it adds no active-Subworkflow stack, while recursion inside ordinary private Python functions remains an implementation detail;
- dynamic `ctx.call()` targets are invalid; the executor never rewrites, copies, or inlines candidate source to make an invalid call legal;
- formal Component orchestration permits Task Workflow to call Subworkflow or Step and Subworkflow to call only Step, while Step calls no formal Component; ordinary functions inside Component source remain unmodeled implementation details, and complete task composition belongs only to Automation Plan;
- `condition`, Task Workflow `verify`, and Recovery Rule callables never call formal Components; conditions and verifiers are read-only, and Recovery Rules remain leaves to prevent nested recovery;
- each Recovery Rule is an immutable Python Component with a module docstring, stable logical name, Component ID, and fixed `detect(ctx) -> bool` plus `recover(ctx) -> None` functions; it has no fourth role decorator and is discovered only from `recovery_rules` rather than through `ctx.call()`;
- the three role decorators only mark role; later executor-owned wrappers use `functools.wraps`, while formal identity remains the logical name and Component ID;
- Python native control flow, local variables, returns, and call stack replace the YAML Step graph, routing tables, Transition objects, variable mappings, and custom Subworkflow stack;
- formal execution uses only ordinary Python returns for Normal Outcome and `ExecutionInterruption` for the interruption channel; there is no common Outcome type or output schema;
- all formal exceptions reach their wrapper and Trace: Step exceptions normalize into the existing recovery ladder, Step-external exceptions directly produce Execution Anomaly, and verifier exceptions record Task failure without Agent rescue; ignorable cases use explicit ordinary results rather than caught exceptions;
- user cancellation is an executor control signal rather than an exception: it invokes neither recovery nor Agent, stops further input, interrupts a containing Automation Plan without later items, and records `user_cancelled` only when a Task run record already exists; otherwise it creates no Task result, while exact position remains in Trace and `safe_termination_performed` reflects only an action actually taken rather than an inferred stage;
- fixed results of three or more values use a source-local frozen named result with JSON-normalizable fields and a structural field contract; callers use field access and never import or inspect the result class, while genuinely dynamic mappings use dictionaries;
- each formal Task Workflow, Subworkflow, and Step uses a typed `execute(ctx, *, ...)` signature as its sole input contract; only Task Workflow and Step may add an optional matching `condition(ctx, *, ...)`, while supported annotations recursively cover JSON scalars, `Literal`, optional values, `list[T]`, and `dict[str, T]`, with JSON-compatible defaults and no independent input schema or `ctx.inputs`;
- arbitrary input classes, Pydantic models, Enum types, sets, tuples, and non-optional unions remain unsupported;
- `ctx` exposes executor-owned invocation, environment, Manifest, Trace, evidence, cancellation, and budget services but no arbitrary mutable fields or shared business dictionary; business data moves only through parameters, returns, and ordinary Python locals;
- formal call inputs are normalized and passed as independent copies; the executor retains immutable startup and Step-boundary snapshots so local list or dictionary mutation cannot affect callers, retries, or the bound Task verifier;
- repeated objectives use ordinary Task Workflow loops over one-run Subworkflows; Subworkflow returns update Task Workflow local completion data, and the Task Workflow returns a value matching an explicit, directly JSON-compatible return annotation;
- Task Workflow stays thin but complete: it owns top-level inputs, business order, loops, branches, local aggregation, root result, and final verifier, while recognition and external operations move into useful Step or Subworkflow boundaries without mechanically componentizing ordinary Python decisions;
- the task-start-bound `verify(ctx, result, *, ...)` compares only that normalized result with the original input snapshot; it does not read Trace, observe the game, maintain counters, or call formal Components;
- the verifier's `result` annotation exactly matches the Task Workflow return annotation; a tuple, source-local named result, annotation mismatch, or non-normalizable root return produces an Execution Anomaly before verification, and only the exact boolean `True` marks success;
- the executor assigns no progress meaning to Trace or Agent claims, fabricates no return records, and marks no task successful when its bound verifier is false or raises;
- the Agent receives a JSON diagnostic snapshot derived from explicit data and runtime records rather than the live `ctx`; external game state is always re-observed;
- `condition` is optional and read-only only for Task Workflow and Step: a normal false Task condition records `task_condition_not_satisfied` without Agent, while an exception records `task_condition_check_failed`; neither case starts execution, starts a Runtime Agent Session, or performs Safe Task Termination;
- Task Workflow condition only grants launch permission and never restores its entry state; recoverable prerequisites belong in its first Step, while Subworkflow entry recognition likewise belongs to its first relevant Step;
- Step condition checks before the first and every recovery-controlled fresh invocation; false, uncertainty, or exception produces `ExecutionInterruption`, never reaches Workflow as a branch value, and only a later satisfied check permits Step invocation before repeated failure escalates to Agent or Safe Task Termination;
- a Step `condition` accepts the whole observable responsibility range rather than one instantaneous action target, and every Step safely continues from actionable, expected transitional, or completed states using only current observation and original arguments;
- each Python Component uses one module docstring as its sole natural-language description;
- every Task Workflow requires a matching `verify(ctx, result, *, ...) -> bool`; its exact identity, hash, and original inputs bind at Task start so Agent changes cannot alter the current success standard;
- `Request Step Recheck` makes the executor re-observe and try to restore the current paused Step; final verification occurs only after the ordinary Python call chain produces a normal Task Workflow result;
- plain `@step` marks the smallest independently observable Python boundary and records identity, arguments, conditions, timing, Trusted Actions, evidence, returns, and interruptions;
- first-version `@step` has no timeout, retry, or policy parameters; expected-result and observed lack-of-progress checks stay in ordinary Python, with no generic progress-event or heartbeat framework;
- a Step confirms each important input, never blindly replays an earlier sequence, directly returns from an already-completed state, waits through expected transitions, and raises `ExecutionInterruption` for an unknown or observably stalled state or propagates a timeout from a Trusted Action leaf boundary;
- Trusted Actions are immutable shipped or human-approved Components registered once as `observe` for screenshots, OCR, matching, and state reads or `control` for clicks, input, waits, and other execution operations; formal source invokes their literal logical names through `ctx.action()`, while developer inspection derives descriptions and signatures from their Python source without generated wrappers or duplicate schemas;
- Trusted Action implementations alone may catch low-level exceptions, but must record the original and either return an explicit documented result or re-raise a normalized exception, never silently pass or fabricate success;
- the executor hard-codes one action matrix: Task Workflow and Subworkflow `execute`, plus Task Workflow and Step `condition`, may use `observe`; Step `execute` and Recovery Rule `recover` may use both; Recovery Rule `detect` may use `observe`; Task Workflow `verify` uses none;
- candidate loading rejects direct, statically visible Trusted Action violations in formal entrypoints but does not trace private-function call chains; Trusted Action wrappers are the authoritative boundary, rechecking classification and the actual execution role before the action and tracing calls, while Agent code cannot create or replace Trusted Actions during a Top-level Execution;
- `wait` is `control` so Workflow code cannot bypass Trusted Action cancellation and timeout handling or Step observation and recovery; there are no component-specific lists, user-defined permissions, allow/deny rules, permission objects, or inheritance;
- a runtime Trusted Action access violation is an execution-contract error that is rejected before the action and directly produces an Execution Anomaly without public recovery; Agent repair can rescue the current call only when a Step wrapper remains paused, while a Step-external violation cannot reconnect the failed Workflow frame and a verifier violation is terminal for that task;
- image-using Trusted Actions accept semantic Asset names and internally resolve the game language, Working Manifest path and hash, fallback language, prior successful region, and Trace evidence; there is no `ctx.asset()`, Asset Handle, language-neutral Asset, or direct Asset path in formal source;
- Assets are shared immutable files rather than Components; Agent modification of Assets is outside the current repair scope. Agent-created Step and Workflow source is append-only within one Top-level Execution and belongs to its durable Candidate File Batch; a separate Asset Usage Index stores last successful use and normalized match region.
- `@step` catches its own `ExecutionInterruption` before the caller frame unwinds and enters the executor-owned Recovery Ladder; an interruption outside a Step produces an Execution Anomaly directly;
- public Recovery Rules run only inside an interrupted `@step` wrapper; successful actions and Step-external interruptions do not trigger public-rule polling;
- if any Recovery Rule `detect()` raises, the executor stops rule enumeration, records the rule and original exception, and produces an Execution Anomaly without treating it as a non-match, invoking any recovery, or checking later rules; the current Step remains paused for Agent handling or Safe Task Termination;
- if the uniquely selected Recovery Rule `recover()` raises or returns a value other than `None`, the executor records a Recovery Rule execution-contract failure and directly produces an Execution Anomaly; it checks no other rule and does not immediately invoke the current Step, whose wrapper and callers remain paused for Agent handling or Safe Task Termination;
- deterministic recovery exists only inside the interrupted `@step` wrapper: check public Recovery Rules, resolve the current Step through the latest Working Manifest, and invoke it once before Agent escalation;
- Subworkflows and Task Workflows are never restarted; an interruption outside a Step produces an Execution Anomaly and Safe Task Termination directly without starting a Runtime Agent Session;
- the caller frame remains paused because the wrapper catches the interruption before unwinding; a successful compatible Step return resumes ordinary Python control flow, while already unwound frames are never reconstructed and paused Workflow frames are never hot-patched;
- a replacement Step may reconnect only through a fresh invocation after atomic Working Manifest selection: it keeps the logical name, `@step` role, every existing parameter and default, and the return contract, while allowing only new keyword-only parameters with JSON-compatible defaults;
- the wrapper supplies a new copy of its saved arguments, and reconnection is forbidden when new required data, changed caller control flow, an out-of-scope environment, indeterminate prior effects, or an incompatible result would be required; such a Component applies only to later valid calls;
- Agent help cannot fabricate completion data or bypass remaining Workflow actions through an early task-level verifier; inability to restore a compatible Step return continues Agent diagnosis or causes Safe Task Termination;
- the first version has no Temporary Action Plan, Temporary Plan Adapter, `plan_id`, direct model-action channel, or independent Agent-code execution contract;
- `max_turns` is the sole Runtime Agent Session budget; a dispatched model request consumes one Turn regardless of valid response, invalid output, or provider failure, while formal Step trials use the Step's ordinary finite-wait and interruption contract;
- the runner provides failure and lifecycle isolation but not security isolation;
- Task Workflow orchestration remains in a background thread of the GUI process; after complete validation and supervised permission, changed Steps and Workflows run through the ordinary Component path.
- the historical Demo candidate runner is evidence only and does not define the formal runtime recovery path;
- Runtime API and Step wrappers append Traces of actual execution; Agent Interaction Logs retain the complete context and response for every Agent Turn and Trace records the corresponding references;
- Trace records each executed formal Component's stable logical name and actual Component ID;
- each Task Workflow run retains Trace, Agent Interaction Logs, screenshots, and evidence as one Run Log Bundle, while the common retention policy removes only whole bundles;
- a local Workflow Run Ledger retains compact per-invocation outcomes, duration, public deterministic recovery counts, Step reinvocation counts, and Agent intervention counts independently of detailed Trace retention; it has no Subworkflow restart fields;
- Task Workflow and Subworkflow use one Ledger record shape with `workflow_kind = task | sub`;
- both use final `success | failure` results: a Subworkflow succeeds on normal return and otherwise fails without a verifier, while Safe Task Termination is performed and counted only once on the owning Task Workflow rather than duplicated across active Subworkflow records;
- one terminal cause gives the same executor-owned `failure_code` to every active Workflow record unwound by it; ancestors are not rewritten to generic child-failure codes, while messages, parent-call IDs, and Trace identify the actual source and already returned Subworkflows remain successful;
- one Agent invocation is one Trace event but is attributed in Ledger to the owning Task Workflow and its active Subworkflow, if any; already returned and sibling Subworkflows remain unaffected, successful affected spans are Agent-assisted, and application-wide totals use unique Trace events rather than summed Ledger counts;
- public Recovery Rule and Step-reinvocation events use the same span attribution without changing strict success when no Agent intervenes; application-wide totals likewise use unique Trace events rather than sums of overlapping Workflow records;
- irreversible progress permits compatible Trace segments to establish Validation Coverage;
- a first occurrence never creates a public Recovery Rule directly; first-version Agent maintenance cannot modify Recovery Rules;
- formal trials execute only verified Python control flow; permanent review exposes successful-trial and Validation Coverage evidence without using either as an automatic gate, and permanent registration still requires human approval;
- Components and saved Manifests remain immutable; the current Working Manifest may change by referencing new identities, stores no additions-and-deletions log, and cleanup remains reference-safe and user initiated.
- concise Python docstrings support initial Agent retrieval and change with source hashes and Component IDs; tags, separate component documents, and vector retrieval remain deferred.

Stage 2 will not add Component Ref objects, dynamic `ctx.call()` targets, cross-Component implementation imports, nested Recovery Rule calls, arbitrary Task Workflow recovery entrypoints, a Workflow or input DSL, Pydantic input models, general interpreter, complex AST whitelist, RPC framework, shared mutable child Context, security-sandbox claim, or autonomous permanent registration.

The first version also does not export, inherit, migrate, or persist Task Workflow business state, Python loop positions, or entered frames. It terminates safely or restarts from an observable known point after process failure, deferring explicit Checkpoint/Resume design until cross-process or cross-implementation continuation is required.

Stage 2 closes without further architecture work on persistence formats, a complete failure-code catalogue, or game-specific Safe Task Termination actions. Recovery Rules are enumerated by stable logical-name order in implementation without adding a Manifest field. Storage layout and formats use the most direct local representation when implementation reaches them; failure codes are added only for real execution paths; each vertical slice supplies the concrete safe action appropriate to its supported game state. Runtime Agent recovery, maintenance trials, and their budgets belong to Stage 3. Agent-assisted Workflow Drafting and autonomous Capability Expansion are deferred. The immediate next activity is planning the minimum implementation slices and their acceptance order.

The accepted implementation baseline is maintained in [Stage 2 Minimum Implementation Slices](stage-2-implementation-slices.md). Workflow 2.0 begins on a clean orphan branch in this repository; the old branch remains the historical reference and rollback path rather than a runtime that the new code must coexist with. The first real Task Workflow is selected when that slice begins, using mailbox collection as the initial smallest candidate.

## Stage 3: Agent Runtime Step Recovery and Maintenance

Status: architecture under revision for #310 and #311.

- only an Execution Anomaly caught while an existing supported Task Workflow remains paused inside an `@step` wrapper starts a bounded Runtime Agent Session;
- local and remote models implement one Agent Adapter contract that only transports a self-contained Context Snapshot, normalizes provider failures, and parses one allowed Turn result; it never performs actions, writes files, changes a Manifest, invokes formal code, or decides recovery and termination;
- the Agent may propose one complete Manifest changing Steps, Task Workflows, or Subworkflows, with reasons for each change; Trusted Action, Recovery Rule, Asset, and new-objective changes are outside the current scope;
- candidate files use new immutable identities and hashes and belong to the current Top-level Execution's Candidate File Batch;
- a complete candidate Working Manifest is atomically selected only when the executor can immediately arrange a legal formal trial call;
- the first fresh current-Step call supplies behavior evidence; success commits the whole selected Manifest for later calls, while failure leaves the execution paused for another Agent choice or termination without automatic rollback;
- an entered Python frame is never replaced, and Manifest rollback cannot undo external game actions;
- after Top-level Execution ends, only its current Working Manifest is presented as the Capability Proposal when its ID has not already received permanent approval, including when final Task verification failed; returning to the Base Manifest or another approved ID skips repeated approval, and intermediate attempts are not separately reviewed;
- permanent approval has no universal business-success threshold in Stage 3: the system presents whether a successful formal trial occurred together with the candidate and recorded evidence, while the supervisor decides whether it is sufficient; no trial result, Step result, Task verifier result, or unattended run can approve automatically;
- a topmost modal Capability Approval Dialog requires exactly one whole-proposal approve-or-reject decision: approval marks the reviewed Manifest ID as permanently published, rejection grants no permanent approval, and both retain execution and review evidence; after approval, a separate window asks whether to set the approved current Working Manifest as Default;
- `max_turns` is the only Runtime Agent Session budget; there is no Session deadline, action budget, candidate budget, or plan timeout;
- every Agent Turn uses a self-contained Context Snapshot rebuilt from local authoritative state and never depends on provider-retained conversation history; detailed context selection remains undecided;
- provider, model, System Prompt version, generation parameters, and Agent Adapter version are fixed for each Runtime Agent Session, with no within-Session model switching, routing, or fallback;
- a Runtime Agent Session succeeds only through a compatible normal return from a fresh formal invocation of the current Step; the Task Workflow then continues toward its unchanged bound verifier, and a later Step anomaly creates a new Session with a fresh `max_turns` while sharing the Top-level Execution's Working Manifest and Candidate File Batch;
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
- the UI exposes task execution, Agent configuration, supervised Step and Workflow source review, proposal review, Manifest recovery, and cleanup;
- the UI exposes per-Workflow strict success rate, Agent-assisted completion, recovery breakdown, and average duration from the local Workflow Run Ledger;
- a packaging spike verifies ordinary module loading, runner subprocess creation, external assets, and Trace persistence;
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
