# Lix Assistant Reconstruction Plan

This plan keeps the reconstruction dependency-ordered. Accepted boundaries may change only through an explicit reopening such as the Python-first decision below.

## Stage 1: Product and Agent boundaries

Status: accepted and explicitly revised for Capability Expansion and dynamic Agent Python.

Locked contracts:

- officially supported objectives run through deterministic Python Workflows without a model;
- only the deterministic executor may invoke the optional Agent;
- the Recovery Ladder remains Deterministic Recovery, Agent, then Safe Task Termination;
- permanent capability changes require validation and human approval;
- every Top-level Execution copies the active immutable Component Manifest into one complete durable Working Manifest; a direct Task Workflow owns one, while all sequential Task Workflows in an Automation Plan share one;
- Agent-generated Python may execute before permanent approval under Supervised or warned Unattended Operation;
- first-version subprocess execution is explicitly not a security sandbox, and stronger enforcement is deferred.

## Stage 2: Python-first Workflow and deterministic execution

Status: accepted and complete. Further changes require explicitly reopening the Stage 2 contract.

Confirmed contracts:

- Task Workflow, Subworkflow, and Step are immutable Python Components loaded as ordinary modules from Manifest-fixed paths and hashes;
- exactly one parameterless `@task_workflow`, `@sub_workflow`, or `@step` on each formal entrypoint is the sole component-role source; Manifest, paths, names, and tags do not duplicate or infer `component_kind`;
- each Task Workflow, Subworkflow, or Step occupies one Python file with exactly one decorated `execute`; Task Workflow and Step may also contain their optional `condition`, Task Workflow contains its required `verify`, while Subworkflow exposes only `execute`; result classes and ordinary implementation code remain in the same file and no file contains multiple formal Components;
- formal Task Workflow, Subworkflow, Step, condition, verifier, Recovery Rule, every private function in their files, and Temporary Action Plans contain no `except`; `try/finally` remains available for cleanup, but loaders reject `return`, `break`, `continue`, or `raise` in every `finally` without reachability or rethrow analysis so the original exception propagates naturally;
- each Manifest is one complete document containing executable `logical_name → immutable Component ID and load information` mappings, dedicated `recovery_rules` and `trusted_actions` mappings, and an `assets` mapping from semantic name and language to shared relative path plus complete hash;
- formal Components call one another only through `ctx.call(logical_name, **arguments)`; it resolves and validates the current Working Manifest entry on every call and stores no Component Ref or implementation cache;
- every `ctx.call()` target is a string literal; before each Working Manifest atomic update, the executor validates every formal target, role permission, and Subworkflow cycle against the complete resulting candidate Manifest, while runtime validates resolution and role again and records the actual identity;
- every `ctx.call()` in a Task Workflow or Subworkflow source file belongs to that file's single Component, including calls in private or apparently unreachable functions; Step, `condition`, `verify`, and Recovery Rule source may contain no `ctx.call()`, and the loader performs no reachability or branch analysis;
- any complete-graph validation error rejects the entire atomic switch and leaves the old Working Manifest active; a detected cycle reports its complete path;
- runtime `ctx.call()` rechecks only target resolution and role and records the call; it adds no active-Subworkflow stack, recursion guard, or nesting-depth limit, while recursion inside ordinary private Python functions remains an implementation detail;
- dynamic `ctx.call()` targets are invalid, and the executor never resolves a cycle by rewriting, copying, or inlining candidate source;
- formal Component orchestration permits Task Workflow to call Subworkflow or Step and Subworkflow to call an acyclic Subworkflow or Step, while Step calls no formal Component; nested Subworkflows use the ordinary Python call stack, ordinary functions inside Component source remain unmodeled implementation details, and complete task composition belongs only to Automation Plan;
- `condition`, Task Workflow `verify`, and Recovery Rule callables never call formal Components; conditions and verifiers are read-only, and Recovery Rules remain leaves to prevent nested recovery;
- each Recovery Rule is an immutable Python Component with a module docstring, stable logical name, Component ID, content hash, and fixed `detect(ctx) -> bool` plus `recover(ctx) -> None` entrypoints; it has no fourth role decorator and is discovered only from `recovery_rules` rather than through `ctx.call()`;
- the three role decorators use `functools.wraps`, while formal identity remains the logical name, Component ID, and content hash;
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
- Agent Python receives a JSON snapshot derived from explicit data and runtime records rather than the live `ctx`; external game state is always re-observed, with deliberate return to a known start when it cannot be identified reliably;
- `condition` is optional and read-only only for Task Workflow and Step: a normal false Task condition records `task_condition_not_satisfied` without Agent, while an exception produces Execution Anomaly and may let Agent repair only later capability before the current non-retried item records `task_condition_check_failed`; neither case starts execution or performs Safe Task Termination;
- Task Workflow condition only grants launch permission and never restores its entry state; recoverable prerequisites belong in its first Step, while Subworkflow entry recognition likewise belongs to its first relevant Step;
- Step condition checks before the first and every recovery-controlled fresh invocation; false, uncertainty, or exception produces `ExecutionInterruption`, never reaches Workflow as a branch value, and only a later satisfied check permits Step invocation before repeated failure escalates to Agent or Safe Task Termination;
- a Step `condition` accepts the whole observable responsibility range rather than one instantaneous action target, and every Step safely continues from actionable, expected transitional, or completed states using only current observation and original arguments;
- each Python Component uses one module docstring as its sole natural-language description;
- every Task Workflow requires a matching `verify(ctx, result, *, ...) -> bool`; its exact identity, hash, and original inputs bind at Task start so Agent changes cannot alter the current success standard;
- after every normally completed Temporary Action Plan, the executor re-observes and tries to restore the current paused Step first; final verification occurs only after the ordinary Python call chain produces a normal Task Workflow result;
- plain `@step` marks the smallest independently observable Python boundary and records identity, arguments, conditions, timing, Trusted Actions, evidence, returns, and interruptions;
- first-version `@step` has no timeout, retry, or policy parameters; expected-result and lack-of-progress checks stay in ordinary Python, with no generic progress-event or heartbeat framework;
- a Step confirms each important input, never blindly replays an earlier sequence, directly returns from an already-completed state, waits through expected transitions, and raises `ExecutionInterruption` only after an internally enforced reasonable deadline for unknown or stalled states;
- Trusted Actions are immutable shipped or human-approved Components registered once as `observe` for screenshots, OCR, matching, and state reads or `control` for clicks, input, waits, and other execution operations; they are imported and called as ordinary functions with no `ctx.action()` API;
- Trusted Action implementations alone may catch low-level exceptions, but must record the original and either return an explicit documented result or re-raise a normalized exception, never silently pass or fabricate success;
- the executor hard-codes one action matrix: Task Workflow and Subworkflow `execute`, plus Task Workflow and Step `condition`, may use `observe`; Step `execute`, Recovery Rule `recover`, and Temporary Action Plan may use both; Recovery Rule `detect` may use `observe`; Task Workflow `verify` uses none;
- candidate loading rejects direct, statically visible Trusted Action violations in formal entrypoints but does not trace private-function call chains; Trusted Action wrappers are the authoritative boundary, rechecking classification and the actual execution role before the action and tracing calls, while Agent code cannot create or replace Trusted Actions during a Top-level Execution;
- `wait` is `control` so Workflow code cannot bypass Step observation, deadlines, and recovery; there are no component-specific lists, user-defined permissions, allow/deny rules, permission objects, or inheritance;
- a runtime Trusted Action access violation is an execution-contract error that is rejected before the action and directly produces an Execution Anomaly without public recovery; Agent repair can rescue the current call only when a Step wrapper remains paused, while a Step-external violation cannot reconnect the failed Workflow frame and a verifier violation is terminal for that task;
- image-using Trusted Actions accept semantic Asset names and internally resolve the game language, Working Manifest path and hash, fallback language, prior successful region, and Trace evidence; there is no `ctx.asset()`, Asset Handle, language-neutral Asset, or direct Asset path in formal source;
- Assets are shared immutable files rather than Components: Agent additions are append-only within the run, tracked by a durable Asset Batch for crash-safe approval or rejection rollback, while a separate Asset Usage Index stores last successful use and normalized match region without automatically cleaning accepted old files;
- `@step` catches its own `ExecutionInterruption` before the caller frame unwinds and enters the executor-owned Recovery Ladder; an interruption outside a Step produces an Execution Anomaly directly;
- public Recovery Rules run only inside an interrupted `@step` wrapper; successful actions and Step-external interruptions do not trigger public-rule polling;
- if any Recovery Rule `detect()` raises, the executor stops rule enumeration, records the rule and original exception, and produces an Execution Anomaly without treating it as a non-match, invoking any recovery, or checking later rules; the current Step remains paused for Agent handling or Safe Task Termination;
- if the uniquely selected Recovery Rule `recover()` raises or returns a value other than `None`, the executor records a Recovery Rule execution-contract failure and directly produces an Execution Anomaly; it checks no other rule and does not immediately invoke the current Step, whose wrapper and callers remain paused for Agent handling or Safe Task Termination;
- deterministic recovery exists only inside the interrupted `@step` wrapper: check public Recovery Rules, resolve the current Step through the latest Working Manifest, and invoke it once before Agent escalation;
- Subworkflows and Task Workflows are never restarted; an interruption outside a Step produces an Execution Anomaly directly;
- the caller frame remains paused because the wrapper catches the interruption before unwinding; a successful compatible Step return resumes ordinary Python control flow, while already unwound frames are never reconstructed and paused Workflow frames are never hot-patched;
- a replacement Step may reconnect only through a fresh invocation after atomic Working Manifest selection: it keeps the logical name, `@step` role, every existing parameter and default, and the return contract, while allowing only new keyword-only parameters with JSON-compatible defaults;
- the wrapper supplies a new copy of its saved arguments, and reconnection is forbidden when new required data, changed caller control flow, an out-of-scope environment, indeterminate prior effects, or an incompatible result would be required; such a Component applies only to later valid calls;
- Agent help cannot fabricate completion data or bypass remaining Workflow actions through an early task-level verifier; inability to restore a compatible Step return continues Agent planning or causes Safe Task Termination;
- Agent plans execute as immutable single-entry Python source in a runner subprocess; a Temporary Plan Adapter owns JSON transport and converts the plan's ordinary JSON-compatible return or subprocess failure into the same two execution channels;
- the runner provides failure and lifecycle isolation but not security isolation;
- Runtime API and Step wrappers append Traces of actual execution; Agent Interaction Logs retain complete generated Python source and Trace records the corresponding references;
- Trace records each executed formal Component's stable logical name, actual Component ID, and content hash;
- each Task Workflow run retains Trace, Agent Interaction Logs, screenshots, and evidence as one Run Log Bundle, while the common retention policy removes only whole bundles;
- a local Workflow Run Ledger retains compact per-invocation outcomes, duration, public deterministic recovery counts, Step reinvocation counts, and Agent intervention counts independently of detailed Trace retention; it has no Subworkflow restart fields;
- Task Workflow and Subworkflow use one Ledger record shape with `workflow_kind = task | sub`;
- both use final `success | failure` results: a Subworkflow succeeds on normal return and otherwise fails without a verifier, while Safe Task Termination is performed and counted only once on the owning Task Workflow rather than duplicated across active Subworkflow records;
- one terminal cause gives the same executor-owned `failure_code` to every active Workflow record unwound by it; ancestors are not rewritten to generic child-failure codes, while messages, parent-call IDs, and Trace identify the actual source and already returned Subworkflows remain successful;
- one Agent invocation is one Trace event but is attributed in Ledger to the owning Task Workflow and every active ancestor Subworkflow whose call span contains it; already returned and sibling Subworkflows remain unaffected, successful affected spans are Agent-assisted, and application-wide totals use unique Trace events rather than summed nested Ledger counts;
- public Recovery Rule and Step-reinvocation events use the same span attribution without changing strict success when no Agent intervenes; application-wide totals likewise use unique Trace events rather than sums of overlapping Workflow records;
- irreversible progress permits compatible Trace segments to establish Validation Coverage;
- unknown exception handling evolves through a fixed sequence: successful temporary plan, ordinary local Python handling branch in candidate Workflow A', compatible real validation in Workflow B, then public Recovery Rule plus rebuilt Workflow A'' without the duplicate branch;
- a first occurrence never creates a public Recovery Rule directly, and Workflow B changes only if its source must be corrected to expose the failure through the formal execution contract;
- only verified Python control flow may be promoted, and permanent registration still requires human approval;
- Components and saved Manifests remain immutable; the current Working Manifest may change by referencing new identities, stores no additions-and-deletions log, and cleanup remains reference-safe and user initiated.
- concise Python docstrings support initial Agent retrieval and change with source hashes and Component IDs; tags, separate component documents, and vector retrieval remain deferred.

Stage 2 will not add Component Ref objects, dynamic `ctx.call()` targets, cross-Component implementation imports, nested Recovery Rule calls, arbitrary Task Workflow recovery entrypoints, a Workflow or input DSL, Pydantic input models, general interpreter, complex AST whitelist, RPC framework, shared mutable child Context, security-sandbox claim, or autonomous permanent registration.

The first version also does not export, inherit, migrate, or persist Task Workflow business state, Python loop positions, or entered frames. It terminates safely or restarts from an observable known point after process failure, deferring explicit Checkpoint/Resume design until cross-process or cross-implementation continuation is required.

Stage 2 closes without further architecture work on persistence formats, a complete failure-code catalogue, or game-specific Safe Task Termination actions. Recovery Rules are enumerated by stable logical-name order in implementation without adding a Manifest field. Storage layout and formats use the most direct local representation when implementation reaches them; failure codes are added only for real execution paths; each vertical slice supplies the concrete safe action appropriate to its supported game state. Agent budgets and Capability Expansion remain Stage 3 responsibilities. The immediate next activity is planning the minimum implementation slices and their acceptance order.

The accepted implementation baseline is maintained in [Stage 2 Minimum Implementation Slices](stage-2-implementation-slices.md). Workflow 2.0 begins on a clean orphan branch in this repository; the old branch remains the historical reference and rollback path rather than a runtime that the new code must coexist with. The first real Task Workflow is selected when that slice begins, using mailbox collection as the initial smallest candidate.

## Stage 3: Agent adapters and capability learning

Status: planned; Runtime Exception Handling and Capability Expansion are both in scope.

- local and remote models implement one Agent Adapter contract;
- the Agent receives relevant Trace, Context snapshot, evidence, formal Components, and Expert Guidance;
- it returns immutable `execute(ctx)` Python source or recommends Safe Task Termination; only the executor performs termination;
- Temporary Action Plan source contains no `except`, may use `try/finally`, and exposes every exception to the Adapter; expected alternatives use explicit Trusted Action results or a later plan with a new identity;
- Supervised Operation confirms source; warned Unattended Operation runs without confirmation;
- the child imports the shipped Runtime API directly and records an independent append-only Trace;
- Temporary Action Plans are not Components and execute directly through the Adapter without entering the Working Manifest; Trace records their actual order and Agent Interaction Log references;
- only verified temporary logic organized into candidate Workflow, Step, or Recovery Rule Components, together with verified Asset files or mappings, may update the Working Manifest;
- Working Manifest changes are fully written and atomically selected only at executor-controlled pause boundaries; they never hot-patch an entered Python frame, and successfully superseded Working Manifest files are not retained as historical versions;
- first-version Automation Plans execute Task Workflows sequentially and do not support concurrent Working Manifest modification;
- after direct launch or successful Automation Plan preflight, every considered Task Workflow final result is only `success` or `failure`; a failed condition or post-preflight incompatibility is still `failure` even when `execute()` is not entered, with executor-owned stable `failure_code`, user-facing `failure_message`, Agent and recovery facts, and Safe Task Termination recorded separately, while failure position remains in Trace, no `failure_stage` exists, and `incomplete` is only an open-record state;
- failure codes are ordinary executor constants whose published meanings only extend and never change; Components and Agent output cannot choose them, and unclassified cases use `execution_failed` while full detail remains in Trace and the message;
- Automation Plan uses one best-effort policy: every listed Task Workflow is considered once, and its `success` or `failure` result never blocks later items;
- Automation Plan is user-saved configuration rather than a Component or Manifest entry; it contains only an ordered list of Task Workflow stable logical names and explicit input dictionaries, permits duplicate tasks as independent calls, and uses list position instead of a separate item identity;
- before any task starts, Automation Plan performs one full preflight against its initial Working Manifest: parse the complete Plan structure, resolve every name to a Task Workflow, and bind, type-check, and normalize every input; it collects all errors, and any failure records `interrupted: invalid_plan` without invoking a task;
- preflight does not run Task Workflow conditions, inspect environmental eligibility or dependencies, predict success, or test adjacency compatibility;
- after preflight the Plan retains a frozen ordered list plus current index and no execution stack; before each item it re-resolves the latest Task Workflow, revalidates frozen inputs, runs the current condition, and records `failure_code: working_manifest_incompatible` when a Working Manifest change prevents a fresh compatible call;
- an active Task Workflow always keeps its entered frame, locals, loop position, and remaining control flow; replacements apply only to later fresh calls, while subsequent `ctx.call()` operations continue resolving the latest compatible callees;
- an invalid Task Workflow result or unsuccessful final verifier records `failure` with structured explanation and is terminal for that call without Agent rescue or retry; Safe Task Termination is a separate executor action, not a result category, and ends only the current Task Workflow while a containing Automation Plan proceeds with its next independent item;
- the first version has no item-level condition, retry, result mapping, task dependency graph, configurable failure policy, `continue_on_failure`, or supervised-versus-unattended execution branch; a directly started Task Workflow simply ends after its result is recorded;
- Automation Plan has no verifier or aggregate business-success predicate: after successful preflight, finishing traversal records `completed` plus an ordered per-task summary regardless of individual outcomes, while invalid preflight, cancellation, process failure, or inability to continue scheduling records `interrupted`;
- reliability rates and Agent-recovery statistics remain per-Workflow Ledger data; Automation Plan has neither its own success rate nor an Agent recovery path;
- interrupted plans return to bounded parent-controlled diagnosis and receive a new `plan_id` when revised;
- compatible traces may validate a plan across irreversible progress;
- at Top-level Execution end the Working Manifest may be discarded or retained for review; only validation and human approval can save verified contents as a new active Manifest.

The first vertical slice demonstrates Agent Python execution, Trace, interruption and revision, evidence-based promotion, approval, and later model-free formal execution on one small GUI objective.

## Stage 4: Application structure, UI, and packaging

Status: planned.

- CLI and desktop UI call the same application and execution services;
- the UI exposes task execution, Agent configuration, source review, the Unattended risk warning, proposal review, Manifest recovery, and cleanup;
- the UI exposes per-Workflow strict success rate, Agent-assisted completion, recovery breakdown, and average duration from the local Workflow Run Ledger;
- a packaging spike verifies ordinary module loading, runner subprocess creation, external assets, and Trace persistence;
- packaged formal automation must remain usable without a model.

## Explicitly deferred

- operating-system sandboxing or stronger dynamic-code inspection;
- complex AST import or API allowlists;
- general Workflow DSL or compiler;
- automatic permanent promotion;
- skill-maturity labels and broad autonomous general-computer control.
