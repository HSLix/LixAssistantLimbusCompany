# Stage 2: Python-first Workflow and Execution Contract

This document records the Workflow 2.0 contracts confirmed during Stage 2. Python expresses task control flow; the deterministic executor owns cross-cutting execution, Trace, recovery, Agent invocation, and termination.

Status: accepted and complete. Implementation details do not reopen this contract unless they contradict a locked boundary below.

## Component hierarchy

- A Task Workflow is a user-startable Python root function that completes one supported objective and owns the final task outcome.
- A Subworkflow is a reusable Python function that combines Steps and other Subworkflows for one local flow responsibility. Direct and indirect recursion are invalid.
- A Step is the smallest independently observable Python execution boundary, marked by plain `@step`. It may combine several Trusted Actions such as screenshot, template matching, click, and verification.
- Trusted Actions are immutable shipped or human-approved low-level operations registered once as `observe` or `control`. Screenshots, template matching, OCR, and state reads are `observe`; click, keyboard input, and execution waits are `control`. They are registered separately from Steps and cannot be created or replaced by the Agent during a Top-level Execution.
- A Task Workflow is not called by another Workflow. Automation Plan composes complete Task Workflows.
- Workflow remains only the collective term for Task Workflow and Subworkflow.
- First-version Automation Plans execute Task Workflows sequentially using one best-effort policy: each listed task receives at most one fresh call, its result never blocks later items, and parallel Task Workflow execution and concurrent Working Manifest modification are unsupported.

The architecture has no global node pool, YAML Step graph, Outcome routing table, Transition objects, custom variable-mapping language, or custom Subworkflow call stack.

The role of each Workflow or Step executable through `ctx.call()` comes only from exactly one parameterless entrypoint decorator:

```python
@task_workflow
def execute(...): ...

@sub_workflow
def execute(...): ...

@step
def execute(...): ...
```

The decorators carry no timeout, retry, or other execution policy. These Manifest entries do not repeat `component_kind`, and the loader never infers role from a directory, filename, logical-name prefix, or tag. It first verifies the referenced source hash, then parses and validates exactly one role decorator, and finally binds the stable logical name supplied by the Manifest. Recovery Rules are not `ctx.call()` targets and therefore do not add a fourth role decorator; their dedicated Manifest mapping supplies their identity and fixed entrypoints.

`@task_workflow` marks a user-startable root, binds its exact `verify`, establishes the Run Log Bundle, and writes Workflow Run Ledger data. `@sub_workflow` records calls and returns and writes the same Ledger record shape; nested calls use only the ordinary Python call stack, and the Subworkflow is not a recovery or restart boundary. `@step` establishes detailed Trace and catches `ExecutionInterruption` before the caller frame unwinds.

Formal Task Workflow, Subworkflow, Step, `condition`, `verify`, Recovery Rule, and every ordinary private function in their source files may contain no `except` clause. Candidate loading rejects any such AST node without analyzing the caught type, reachability, or whether it re-raises. `try/finally` without `except` remains legal for cleanup, but the loader rejects every `return`, `break`, `continue`, or `raise` inside a `finally` suite without analyzing reachability or whether a raise is a bare rethrow. A legal `finally` completes cleanup and lets the original exception propagate naturally; if cleanup itself raises, the wrapper records the complete Python exception chain, including the original. This is a source-wide structural rule, not an exception-catching permission model.

Formal Components make every cross-Component call through the Context API:

```python
result = ctx.call("steps.enter_stage", stage_name=stage_name)
```

`ctx.call()` stores no Component ID, function object, cache, or reference lifecycle. At each invocation the executor resolves the stable logical name through the current Working Manifest, verifies the target identity, source hash, role, and bound arguments, invokes it through the appropriate role wrapper, and records the resolved logical name, Component ID, and hash. Direct imports of another Workflow or Step implementation are invalid. Ordinary Python inside a Component source remains an implementation detail. Standard-library calls and Trusted Actions are not cross-Component calls and do not use this API.

Formal source imports a Trusted Action from the shipped Runtime API and calls it as an ordinary Python function; the first version does not add `ctx.action()`. The Manifest's dedicated `trusted_actions` mapping pins each exposed action name to its immutable Component ID, source location, hash, callable entrypoint, and one fixed `observe` or `control` classification. Candidate loading rejects direct, statically visible use inside `execute()`, `condition()`, `verify()`, `detect()`, or `recover()` that violates the fixed matrix below. It does not build a private-function call graph or determine which formal entrypoint may eventually invoke a private function. The action wrapper is therefore the authoritative boundary: before an action occurs, it repeats classification and actual execution-role checks, rejecting indirect violations, and records actual arguments, normalized results, duration, and evidence in Trace. Trusted Action references cannot change in a Working Manifest, so Python import caching cannot select a replacement during the run.

Every `ctx.call()` target in formal source must be a string literal. Before every Working Manifest atomic update, the system parses Task Workflow and Subworkflow source from the complete resulting candidate Manifest, extracts every formal target, validates target existence and caller-to-target role, and checks the complete directed Subworkflow graph for direct or indirect cycles. Every `ctx.call()` anywhere in one Task Workflow or Subworkflow source file, including inside an ordinary private function, belongs to that file's single formal Component and participates in these checks even when the function or branch appears unreachable. Any `ctx.call()` anywhere in a Step source, Task Workflow or Step `condition`, Task Workflow `verify`, or Recovery Rule source is structurally invalid. A Subworkflow definition containing `condition` or `verify` is invalid regardless of its contents. The loader does not analyze function reachability, constant branches, or the eventual caller of a private function.

Any validation error rejects the entire switch and leaves the old Working Manifest active; a cycle report includes its complete path for Agent or developer revision. Runtime `ctx.call()` repeats only target resolution and role validation and records the actual target identity. It maintains no active-Subworkflow stack, recursion guard, or nesting-depth limit because every selected Working Manifest has already passed complete cycle validation. An unresolved or invalid target raises `ExecutionInterruption`. The executor never removes a cycle by inlining, copying, or rewriting source; revised source receives a new content hash and Component ID and passes loading again. The first version has no Component Ref object, reference cache, generated binding, or cache-invalidation mechanism. Working Manifest is the only component mapping structure. Recursion among ordinary private Python functions remains an implementation detail; any resulting exception follows the normal execution-error path.

Dynamic targets such as `ctx.call(target_name)`, `ctx.call(f"subworkflows.{name}")`, and `ctx.call(config["workflow"])` are invalid because their targets and cycles cannot be checked reliably before loading.

The formal Component orchestration matrix is:

```text
User or Automation Plan → Task Workflow
Task Workflow           → Subworkflow or Step
Subworkflow              → Subworkflow or Step
Step                     → no formal Component
```

A Task Workflow never calls another Task Workflow; complete tasks are composed only by Automation Plan. A Subworkflow may call another Subworkflow only when the complete directed call graph remains acyclic. A Step never uses `ctx.call()` and remains the leaf observable and recovery boundary. `condition()` and Task Workflow `verify()` never call a formal Component. First-version Recovery Rule `detect()` and `recover()` likewise never call formal Components, avoiding nested recovery. Trusted Actions are ordinary Runtime API calls governed separately by the fixed matrix below, so permitted `observe` calls from Workflow code are not formal Component orchestration. Ordinary functions inside any of these source files are not architectural entities and receive no separate identity, protocol, or recovery semantics.

Trusted Action access is not configurable. The executor owns one fixed matrix:

```text
Task Workflow or Subworkflow execute → observe
Task Workflow or Step condition      → observe
Step execute                          → observe or control
Task Workflow verify                 → none
Recovery Rule detect                 → observe
Recovery Rule recover                → observe or control
```

`wait` is classified as `control` even though it does not directly mutate the game, because arbitrary Workflow waiting would bypass the Step's observation, deadline, and recovery boundary. There are no component-specific action lists, user-defined permissions, allow/deny rules, independent permission objects, inheritance, or repeated per-Workflow configuration.

Load-time Trusted Action checking is intentionally incomplete and only catches obvious direct violations. A private function has no architectural role of its own, so the loader neither propagates permissions through private calls nor rejects a candidate merely because it cannot prove every indirect path safe. If a restricted entrypoint reaches a disallowed action through such a function, the Trusted Action wrapper deterministically rejects the call before performing the action. This does not create a separate permission or helper model.

A runtime Trusted Action access violation is an execution-contract error in source or invocation, not an external-environment interruption. The wrapper therefore produces an `Execution Anomaly` directly and never checks public Recovery Rules. The Agent may prepare a corrected candidate replacement of the current Step only when its `@step` wrapper still owns a paused caller and a fresh invocation can satisfy the established input, return, and safe-continuation contracts. A violation outside a Step starts no Runtime Agent Session; the current Task Workflow records `failure`, and the executor performs Safe Task Termination. A violation during Task Workflow `verify()` records `failure` at the verification stage and likewise receives no Agent rescue. A violation in Recovery Rule `detect()` or `recover()` leaves the current Step paused, allowing an Agent-proposed replacement of that Step before the executor attempts it again. None of these paths reconstructs an unwound frame, hot-patches a Workflow frame, or changes the verifier bound at task start.

All three role decorators use `functools.wraps` so ordinary Python metadata remains useful for inspection and debugging. Formal identity and Trace never depend on that metadata: logical name, Component ID, and content hash remain authoritative.

## Formal Workflow definition and loading

Task Workflows, Subworkflows, and Steps are ordinary `.py` source files. Each formal executable Component exposes:

- one concise module docstring, used by the Agent as the Component's sole natural-language description;
- one typed Python entrypoint, `execute(ctx, *, ...)`, whose keyword-only parameters are the sole input contract;
- verified Python source.

Task Workflow and Step may additionally expose an optional `condition(ctx, *, ...) -> bool`, which accepts the same bound parameters and uses only trusted observation and recognition APIs. Subworkflow exposes only `execute` and cannot define `condition`. Each Task Workflow, Subworkflow, or Step occupies exactly one source file, and that file contains exactly one decorated `execute` entrypoint. Its module docstring, allowed role-specific callable, source-local result classes, and ordinary implementation functions belong to that same Component. Multiple formal Components never share one source file, so editing one cannot change another Component's source hash or identity. File and directory names remain storage details and do not establish role or logical name.

A Task Workflow additionally requires an explicit JSON-compatible return annotation and `verify(ctx, result, *, ...) -> bool`. The `result` annotation exactly matches the Task Workflow return annotation, and the keyword-only parameters match `execute`. At Task Workflow start, the executor binds that exact verifier identity, content hash, and normalized original-input snapshot for the lifetime of the task. The verifier compares only an independent copy of that original input with the validated Task Workflow result; it does not read Trace, re-observe the game, call formal Components, change external state, or maintain counters. No Working Manifest change can alter the current task's bound success standard. Subworkflows and Steps do not expose a separate final verifier; they verify their own expected results before returning.

The Agent reads the module docstring and signatures by parsing source without importing or executing it. The docstring is ordinary source: changing behavior requires updating it, and the resulting content hash and Component ID change together. Manifest entries do not copy it. Function comments may explain implementation details but do not form another Component description. The first version has no independent `description` or `inputs` field, tags, separate component documentation, or vector index.

Task Workflows, Subworkflows, and Steps pass values through ordinary keyword arguments to `ctx.call()`. Their first-version input annotations recursively support `str`, `int`, `float`, `bool`, `None`, `Literal[...]`, `T | None`, `list[T]`, and `dict[str, T]`, where every nested `T` follows the same rules. Defaults must normalize to JSON as well. Arbitrary classes, Pydantic models, Enum types, sets, tuples, and unions other than optional values are invalid input contracts. The UI and Agent inspect signatures for names, types, defaults, and choices; no separate input DSL or Schema is introduced.

The loader validates annotation shapes. At Task Workflow start, the executor normalizes and retains an immutable original-input snapshot and supplies the function an independent value copy. At every `ctx.call()`, it binds and validates the actual keyword arguments, normalizes them, records them in Trace, and supplies the callee an independent copy rather than shared mutable container references. A component may mutate its received list or dictionary only within that invocation. The `@step` wrapper retains its own normalized boundary snapshot and creates another fresh copy for each invocation. After a Task Workflow normally returns, the executor validates that result against its declared return annotation and normalizes it before supplying `verify` an independent result copy plus inputs copied from the startup snapshot. An invalid or non-normalizable root result produces an Execution Anomaly without invoking `verify`. Return values continue through the existing Normal Outcome contract without adding immutable collection types. Formal Components never read `ctx.inputs`.

The optional read-only `condition` contract belongs only to Task Workflow and Step. A Task Workflow checks it before launch and records `failure` when it is not satisfied, even though `execute()` is never entered. A Step checks it before its first invocation and before every recovery-controlled fresh invocation; any non-satisfied result prevents entry and is handled by its `@step` wrapper. For a Step, the predicate decides whether the observed environment remains anywhere within that Step's responsibility, including expected transition and already-completed states, rather than requiring one instantaneous button or action target to be visible. Every condition may take screenshots, match templates, or run OCR, but cannot click, type, or otherwise change external state. The executor evaluates it once against a fresh observation at the applicable boundary and never polls it continuously.

For a Step, returning `False`, producing uncertain recognition, or raising during condition evaluation means it is not currently enterable and produces an `ExecutionInterruption` inside the Step wrapper. The Workflow never receives a false Step-condition value and cannot skip that Step to continue later control flow. The wrapper checks public Deterministic Recovery, captures a new observation, evaluates the condition again, and invokes the Step only when it is satisfied. A repeated false, uncertain, or exceptional evaluation produces an Execution Anomaly and proceeds to Agent or Safe Task Termination.

For a Task Workflow entry, a normal `False` records `failure_code: task_condition_not_satisfied` without invoking `execute()` or the Agent. An exception records `failure_code: task_condition_check_failed` without starting a Runtime Agent Session. In both cases `safe_termination_performed` is false because Task execution never started. A containing Automation Plan proceeds to its next item, while a direct launch ends.

Task Workflow `condition()` only decides whether the task may start; it does not restore the environment to an acceptable entry. A recoverable prerequisite such as returning to the main menu belongs in the Task Workflow's first Step, whose observation, control, verification, and interruption then use the ordinary Step recovery ladder. A Subworkflow's required environment recognition and entry protection likewise belong to its first relevant Step. The absence of an allowed `condition` means execution may be attempted from any observed state, not that success is guaranteed. Starting screenshots stay in Execution Trace evidence; a reusable visual constraint must become an approved Asset used by `condition`. There is no Subworkflow entry recovery, safe-reentry contract, Condition Expression, condition DSL, expression tree, or supported-scope model.

### Step continuation contract

A Step need not be reversible or strictly idempotent, but every invocation must safely continue from the current observation and original bound arguments. Its ordinary Python code distinguishes four situations without exposing a formal state model:

1. in an actionable state, perform only an action not yet confirmed;
2. in an expected transitional state such as loading, battle animation, or a skill sequence, wait and continue observing without repeating input;
3. in an already-completed state, verify the result and return the contract-compatible value directly;
4. in an unknown or non-progressing state, raise `ExecutionInterruption` after the reasonable deadline implemented inside that Component.

Every important input is followed by observation that confirms whether it took effect. A fresh invocation never blindly replays an earlier input sequence and never depends on local variables lost with the earlier invocation; it reconstructs all continuation decisions from the current environment and original arguments. If the Step cannot determine which effects already occurred or reconstruct the return value its paused caller requires, it is too broad and must be divided differently.

Internal loops, repeated observations, and deadline calculations remain ordinary Python. The first version adds no explicit State or Transition objects, Step retry settings, or general progress events.

The saved Component Manifest is one complete document. Its ordinary executable Component mappings resolve stable dotted logical names to entries containing at least `component_id`, `source_path`, `source_hash`, and `entrypoint`. A dedicated `recovery_rules` mapping resolves each Recovery Rule logical name to `component_id`, source path and hash, plus the fixed `detect` and `recover` entrypoints. A dedicated `trusted_actions` mapping pins each Runtime API action exposed to formal code and marks it once as `observe` or `control`. Its `assets` mapping directly records language-specific relative paths and complete content hashes rather than Component IDs. These mappings are not `component_kind` fields, filename conventions, or logical-name-prefix inference. Logical names are Manifest keys, not content embedded in source or Asset files.

At Top-level Execution start the Manifest is copied into a complete durable Working Manifest. A directly started Task Workflow owns that copy; all sequential Task Workflows in one Automation Plan share it. Formal execution resolves by logical name, verifies the referenced identity and source hash, and then uses the standard Python module-loading mechanism. It does not repeatedly `exec()` stored source strings. Components and saved Manifests remain immutable; an Agent edit creates a new Component ID and changes the Working Manifest value at the same logical name until approval creates a new saved Manifest. This applies equally to Recovery Rules: changing `detect` or `recover` creates a new Component ID and atomically replaces the rule mapping. No ID-to-ID version chain is stored.

## Asset resolution and local storage

There is no generic `ctx.asset()` or Asset object. A Trusted Action that needs an image receives a stable logical Asset name without language or extension and owns resolution, language selection, hash verification, matching, and Trace recording:

```python
match_asset(ctx, "ui/popup/confirm")
```

Formal and temporary Python do not embed an Asset Library path. `match_asset()` reads `ctx.game_language`, resolves the logical name through the current Working Manifest, and loads the selected relative file from the shared local Asset Library after verifying its complete hash. Every image declares its capture language even when it appears language-neutral; the first version has no `general` entry.

The physical path preserves the logical directory hierarchy and uses `<semantic-name>-<language>-<short-hash>.<extension>`. The short hash defaults to the first 12 characters of the complete hash and is lengthened on collision. The extension belongs only to the physical file. For example:

```yaml
assets:
  ui/popup/confirm:
    zh:
      path: ui/popup/confirm-zh-a31f28c47d20.png
      sha256: a31f28c47d20...
```

If the running language has no mapping, `match_asset()` tries every other language entry under the same logical Asset. At least one candidate must reach the configured threshold; the highest score wins without requiring a minimum gap from the second score because all candidates declare the same semantic meaning. Exact score ties use stable path order. If no candidate reaches the threshold, the action raises `ExecutionInterruption`.

Trace records the running language, source language, actual relative path, complete hash, score, and normalized match region. A successful cross-language result may be used immediately. Only after the current Step ultimately succeeds may the executor atomically add an alias for the running language to the current Working Manifest; the alias points to the same path and hash. This update occurs at the safe Step boundary, not inside `match_asset()`.

The mutable Asset Usage Index is outside the Manifest and is keyed by logical name, running language, and complete hash. It updates `last_used_at` only when an image successfully matches and actually participates in a decision, and retains only the latest successful normalized match region. Matching searches near that region first, expands progressively on failure, and finally searches the entire Target Window content area; the remembered region is an optimization, never an applicability constraint.

The Agent may add immutable Component source and Asset files during a run but may not overwrite, rename, or delete an existing file. A new Asset is written directly into the corresponding Asset Library directory using a temporary suffix in that same directory followed by an atomic rename; there is no staging library. Every file actually created by one Top-level Execution is appended to its single durable Candidate File Batch with `kind`, relative path, and complete content hash. Reusing an existing identical file adds no entry.

```json
{
  "run_id": "run-123",
  "state": "active",
  "files": ["ui/popup/confirm-zh-a31f28c47d20.png"]
}
```

When the Working Manifest is retained for review, its proposals and complete closed Candidate File Batch remain without reference-based cleanup. After whole-Manifest approval, rejection, or disposal, the system recomputes references from every retained Component Manifest, durable Working Manifest, and rollback copy, then deletes only unreferenced files created by that Batch. Cleanup is resumable and the Batch is deleted only after it completes. The first version never automatically removes accepted old Assets and never uses historical execution alone as a file-retention reason.

## Python execution model

Python provides parameters, local variables, `if`, loops, returns, Task Workflow and Subworkflow calls, and the ordinary call stack. A normal return is the Normal Outcome channel; raising `ExecutionInterruption` leaves ordinary control flow and enters the executor's interruption channel. There is no common `Outcome` class, output routing table, or result schema.

Formal Components never catch exceptions. Every exception reaches the applicable wrapper and is recorded with its original detail in Trace. A Step wrapper normalizes an exception from Step `condition` or `execute` into `ExecutionInterruption` and enters Deterministic Recovery, Agent, then Safe Task Termination. An exception outside a Step directly produces an Execution Anomaly and Safe Task Termination without starting a Runtime Agent Session. A verifier exception records Task Workflow `failure`, for example with `failure_code: verify_failed`, and receives no Agent rescue because the Task frame has ended. A case that is legitimately ignorable must be represented by an explicit ordinary Trusted Action result and normal Python branching rather than a caught exception, default success, or silent continuation.

User cancellation is not an exception and never enters either path. It is an executor control signal checked by wrappers and Trusted Actions before further input and invokes neither public Recovery Rules nor Agent. It prevents new Trusted Actions, Agent Turns, and candidate trials, wakes a cooperatively paused task, and force-terminates an active Candidate Runner process without closing the main application or Target Window. A containing Automation Plan records `status: interrupted` with `reason: user_cancelled` and starts no later item. If a Task Workflow run record already exists, it records `result: failure` with `failure_code: user_cancelled`; if no such record exists, cancellation creates no Task result. Active Subworkflow records, when present, close under the normal shared-cause rule. `safe_termination_performed` reports only whether the executor actually performed Safe Task Termination and is never inferred from whether cancellation occurred during resolution, input checking, `condition`, or `execute`. The exact position remains solely in Trace. Formal source cannot catch, suppress, or clear the signal. A process crash records `failure_code: process_crash` when a Task record exists and cannot claim completed Safe Task Termination.

Trusted Actions are the exception: their shipped or human-approved implementations may catch low-level library or operating-system exceptions. They must record the original exception and either return an explicit documented Normal Outcome or re-raise a normalized exception for the calling wrapper. They cannot silently pass, fabricate success, or hide the original evidence.

A Step or Subworkflow with one result returns an ordinary JSON-compatible value. It may return a two-item tuple only when both positions have stable, unambiguous meaning. Three or more fixed results use a named result class defined in that Component's source, normally `@dataclass(frozen=True)`; this class is not a Component or Manifest entry, and every field must normalize to JSON-compatible data. A result with genuinely dynamic mapping semantics may be a dictionary.

Named results use a structural contract. Callers read `result.field_name` and cannot import the result class or depend on its class name, module path, object identity, or `isinstance()` checks. The contract consists only of field names, annotations, and documented meaning. `ctx.call()` returns the actual frozen dataclass instance in the same process, without creating another result-object layer, while the executor normalizes its fields for Trace. A replacement implementation remains compatible when that structure and meaning remain unchanged even though its Python class identity is new. Code needing dynamic keys or extensible structure uses a dictionary instead of a shared result-class Component.

A Step or Subworkflow may use the richer return forms above, but a Task Workflow root result is limited to the same recursively JSON-compatible scalar, list, and string-keyed dictionary forms allowed by formal input annotations. It cannot return a tuple or source-local named result. The Task Workflow maintains completion data through local variables and ordinary returns from its Subworkflows and Steps, then returns a value matching its explicit return annotation. The executor validates and normalizes that value and supplies it with the startup-bound original inputs to the required `verify`; only the exact boolean value `True` records `result: success`. An invalid result, `False`, or a verifier exception records `result: failure` with a stable machine-readable `failure_code` and user-facing `failure_message`. Because its call stack has already ended, the executor neither invokes the Agent nor starts that Task Workflow again. `verify` performs no new observation, and Workflow code must not use a boolean or ambiguous dictionary merely to bypass its result contract. Failure location and process remain in Trace; the Ledger has no `failure_stage`. Safe Task Termination belongs only to the executor: it is a recorded action, not a Workflow return value or a fourth final result category.

Only the executor assigns the final `failure_code`. It maintains the codes as ordinary internal constants rather than a configurable registry, Manifest data, or Component-provided vocabulary. Workflow code, wrappers, Recovery Rules, Trusted Actions, and the Agent provide exceptions, observations, messages, and evidence; the executor maps those facts to the final code. Published code meanings are stable and may only be extended, never renamed or reused. An unclassified failure uses `execution_failed`, while its complete original detail remains in Trace and `failure_message`; a dedicated code is added later only when program logic or health statistics actually need it. The Agent cannot select or override the final classification.

## Automation Plan execution

Automation Plan is user-saved configuration, not a Component or Component Manifest entry. Its complete executable structure is one ordered `items` list. Each item contains only a Task Workflow stable logical name and its explicit input dictionary:

```yaml
items:
  - task: tasks.claim_daily_reward
    inputs: {}
  - task: tasks.run_mirror_dungeon
    inputs:
      run_count: 3
      team_names: [team_a, team_b]
```

The same Task Workflow may occur more than once, and each occurrence is an independent call. Its list position identifies it within that Plan execution; there is no separate `item_id`. Item-level `condition`, retry, dependency, failure policy, result mapping, or other execution fields are invalid. Eligibility remains the selected Task Workflow's own `condition`, and inputs remain governed by its Python signature.

Before invoking any Task Workflow, the executor performs one complete preflight against the Working Manifest created for this Top-level Execution. It checks only:

1. the Plan file and its `items` structure parse successfully;
2. every `task` logical name resolves to an existing Task Workflow;
3. every `inputs` dictionary binds to that Task Workflow's signature, passes its declared type constraints, and normalizes successfully.

Preflight collects and reports every error rather than stopping at the first one. If any check fails, no Task Workflow is invoked and the Automation Plan records `interrupted` with reason `invalid_plan`. A corrected configuration requires a new Plan execution. Preflight does not evaluate any Task Workflow `condition`, observe environmental eligibility, predict success, inspect task dependencies, or test compatibility between adjacent tasks.

After successful preflight, Automation Plan retains only the frozen ordered logical names and normalized inputs plus the current item index. It has no Python execution stack. Immediately before each item, the executor resolves its logical name again through the latest Working Manifest, rechecks that it is a Task Workflow, and validates the frozen input against the current implementation. A compatible implementation becomes a completely new Task Workflow call and binds its own current `verify`. A missing name, changed role, or incompatible input records `result: failure` with `failure_code: working_manifest_incompatible` and proceeds without Agent intervention, Working Manifest rollback, or another full preflight. The current implementation's `condition` is then evaluated. A normal false records `task_condition_not_satisfied` without Agent; an exception records `task_condition_check_failed` without starting a Runtime Agent Session. Either failure then advances the Plan.

Automation Plan uses one fixed best-effort sequential policy. Each listed Task Workflow is considered once in order and records only `success` or `failure`. If its entry `condition` is satisfied or absent, the executor creates a fresh call with that item's inputs, call stack, original-input snapshot, and bound verifier. If the entry condition fails or Working Manifest incompatibility prevents entry, the item still records `failure` even though `execute()` is not invoked. Agent involvement, recovery, and Safe Task Termination remain separate facts rather than result categories. There is no task dependency graph, retry of the same Task Workflow, `continue_on_failure`, configurable failure policy, or supervised-versus-unattended branch. A directly started Task Workflow has no next item and naturally ends after its result is recorded.

Automation Plan has no `verify()` and does not reinterpret its Task Workflow results as one business success predicate. After successful preflight and consideration of every listed item, its scheduling status is `completed` even when some items record `failure`. It also produces an ordered item summary containing each Task Workflow logical name, normalized input, result, duration, and Run ID. Invalid initial preflight records `status: interrupted` with `reason: invalid_plan`, creates no Task Workflow result, invokes no Task Workflow condition, and contributes to no Workflow success statistics; corrected configuration requires a new Plan execution. User cancellation records `status: interrupted` with `reason: user_cancelled`, terminates the active task when one exists, and starts no later item. Process failure or another executor failure that prevents further scheduling likewise marks the Plan `interrupted`. Workflow reliability and Agent-recovery statistics remain properties of individual Task Workflow Ledger records; the first version defines no Automation Plan success rate or Agent recovery path.

Workflow code cannot invoke the Agent. An `ExecutionInterruption` raised inside a Step is caught by its `@step` wrapper, which captures the current Step, bound arguments, observations, outputs, and evidence and synchronously enters executor-controlled recovery. The caller's Workflow or Subworkflow frame remains paused inside the wrapper call and never unwinds. An interruption outside a Step directly produces an Execution Anomaly.

Step boundaries are selected for independent Trace and verification value rather than for every low-level action. A recognition-action-verification sequence may be one Step; a larger reusable local procedure becomes a Subworkflow.

In the first version, `@step` only marks a function as an executor-visible boundary:

```python
@step
def enter_stage(ctx, *, stage_name: str):
    ...
```

Its wrapper records Step identity and actual arguments, `condition` result, start and end time, invoked Trusted Actions, observations and verification evidence, normalized return or `ExecutionInterruption`, and actual duration. The decorator has no timeout, retry, or other execution-policy parameters. Expected-result verification and lack-of-progress checks remain ordinary Python code and raise `ExecutionInterruption` when execution cannot continue or be verified. The first version has no generic progress event or heartbeat mechanism.

## Run Context

Each Task Workflow run receives an executor-provided Run Context that connects formal Components to runtime services: `ctx.call()`, Target Window access, current game language, Working Manifest resolution, Trace and evidence recording, cancellation, and overall budgets. Its internal state belongs only to the executor, role wrappers, and Trusted Actions. Formal Components cannot add or arbitrarily modify Context fields, and the API exposes no `ctx.state`, shared business dictionary, or other implicit cross-Component data channel.

Business data moves through named call parameters and ordinary returns. A complete task dictionary is not passed through layers for callees to search, and there is no generic business-state `update()` API. Task Workflow loop positions, intermediate results, and configuration remain ordinary Python local variables, lists, or dictionaries. If a Subworkflow needs to influence later scheduling, it returns a suggestion and the Task Workflow decides whether to update its own local state. External game state is re-observed through Trusted Actions rather than inferred from an in-memory marker; when it cannot be identified reliably, formal code may deliberately return the game to a known start before continuing. The first version has no child Context, Context cloning, or Context merge mechanism.

Task Workflow remains thin but complete: it interprets top-level inputs, arranges business order, loops, and branches, aggregates Step and Subworkflow returns in ordinary locals, returns its JSON-compatible root result, and supplies the fixed verifier bound at its own start. Recognition, input, waiting, and result confirmation are pushed down where useful, but a few lines of ordinary business logic do not mechanically require another Component. The first version exposes no general Task Workflow state export, inheritance, or resume method. Local counts, selected teams, loop positions, and intermediate results cannot migrate to a replacement Task Workflow or become mutable shared Context state.

```python
@task_workflow
def execute(ctx, *, run_count: int, team_names: list[str]) -> dict[str, int]:
    ctx.call("steps.exit_active_mirror_dungeon_if_needed")
    completed_count = 0

    for index in range(run_count):
        completed = ctx.call(
            "subworkflows.run_mirror_dungeon",
            team_name=team_names[index % len(team_names)],
        )
        if completed:
            completed_count += 1

    return {"completed_count": completed_count}


def verify(
    ctx,
    result: dict[str, int],
    *,
    run_count: int,
    team_names: list[str],
) -> bool:
    return result["completed_count"] == run_count
```

Here the Task Workflow represents the complete repeated objective, while `subworkflows.run_mirror_dungeon` completes one run. `run_count`, `team_names`, `index`, and the selected team are explicit business data. If a current Step interrupts, the surrounding Python loop frame remains paused; successful Step recovery continues that round without repeating completed earlier rounds. Whether a Mirror Dungeon is active is determined from the environment, and an unrecognizable selected team causes a deliberate exit and restart from configured input rather than reliance on hidden Context state. No loop node, shared state store, or state machine is needed.

The Context Builder supplies the Agent only a JSON-compatible diagnostic snapshot assembled from current runtime information, explicit parameters, returned results, observations, Trace, and the base `manifest_id`. The Agent never receives or modifies the live Run Context. Candidate executable source is handled only through the formal Component Loader and Working Manifest trial path.

Trace is executor-maintained evidence for diagnosis, recovery, Agent context, and audit; formal Workflow logic and `verify` do not read it as a business-data channel. Task completion data instead moves through normal Step and Subworkflow returns into Task Workflow local variables and its final result. The executor never fabricates a Subworkflow return, accepts an Agent-reported count as task data, or emits a generic progress event. If the bound `verify` returns false or raises, the task is not successful. The first version does not persist or reconstruct lost Python frames, loop indices, or local variables after a process crash. A crashed execution performs Safe Task Termination or starts again from an observable known point; persistent Checkpoints are deferred until cross-process continuation becomes an explicit requirement.

## Execution Trace

Formal Workflow execution and recovery use the same append-only Trace vocabulary. Runtime API and Step wrappers write Trace entries as work occurs, so evidence already flushed remains after a crash or timeout. Trace proves what actually executed; it does not preserve the complete temporary capability set that was available but unused.

A Trace header stores the base `manifest_id`, normalized parameters, Context summary, actual entrypoint, and whether a temporary Working Manifest was used. Events record every formal Component actually executed by logical name, Component ID, and content hash. Agent events reference the Agent Interaction Log containing the supplied context and complete response. Executed Recovery Rules and other Components likewise record logical name, identity, content hash, and necessary evidence. Asset matching events instead record logical name, running and source languages, relative path, complete hash, score, and normalized region. Later events record screenshots and recognition, Trusted Actions, Step boundaries, verification, interruptions, recovery results, and final outputs. Large evidence is stored separately and referenced by `evidence_id`.

For an interrupted Step, Trace explicitly records the initial interruption, public Recovery Rule matches and execution result, every fresh Step invocation, Agent involvement and Agent Interaction Log references, Working Manifest trial results, the final compatible return or repeated interruption, Safe Task Termination when applicable, and the elapsed duration of each stage.

Trace also records every Task Workflow normalized final result, the startup-bound input supplied to its fixed verifier, and the verifier's return or exception. Final verification occurs only after a normal Task Workflow return. The Ledger derives strict success when that verification succeeds without any Agent invocation and Agent-assisted success when it succeeds after Agent help restored the ordinary return chain.

Every executed source is immutable. Editing creates a new Component identity and new execution events. Trace management groups attempts by scanning recorded identities, and any reverse index is derived. A formal Component may optionally hold a nullable, soft `source_trace_id`.

One Task Workflow run stores its Execution Trace, Agent Interaction Logs, screenshots, and other detailed evidence in a single Run Log Bundle. The common log-retention policy keeps or removes that bundle as a whole, so Trace references never require independent reference counting and cannot outlive their Agent logs or evidence. `source_trace_id` remains a nullable soft provenance link and may become unresolved after its bundle expires. The Workflow Run Ledger is outside the bundle and retains compact health records independently.

## Workflow Run Ledger and health metrics

The application maintains a local Workflow Run Ledger separate from Components, Manifests, and Run Log Bundles. It appends one compact record for every Task Workflow and entered Subworkflow call. Ledger records remain available for long-term health analysis after the common log-retention policy removes detailed run bundles.

Each record contains at least:

- record, Task run, Workflow call, and optional parent-call identities;
- exact Workflow logical name, Component ID, and `manifest_id`;
- `workflow_kind = task | sub`, derived from the role decorator, and a normalized input summary;
- start time, end time, and elapsed duration;
- final `result: success | failure` for Task Workflow and entered Subworkflow calls; an open record may temporarily use `incomplete`, which is never final;
- for failures, executor-owned stable machine-readable `failure_code` and user-facing `failure_message`, plus separate facts such as Agent involvement and whether Safe Task Termination was performed; failure location and process remain in Trace rather than a Ledger `failure_stage`;
- public Recovery Rule attempts and successful public recoveries;
- Step reinvocation attempts and successful Step reinvocations;
- Agent invocations, Working Manifest trials, and successful Agent-assisted recoveries;
- optional related `trace_id` values as soft references.

For a successful Task Workflow, **strict success** means the complete objective finished from beginning to end without Agent involvement; any amount of successful deterministic recovery is allowed. **Agent-assisted success** means the objective finished after at least one Agent invocation. These are derived success classifications, not additional `result` values. A Subworkflow has no verifier: a normal return records `success`, while an exception, unwind, or termination before a normal return records `failure` with an executor-owned code. Within a successful Subworkflow span, no Agent involvement is strict success and any Agent help is Agent-assisted success.

Safe Task Termination is performed and counted once at the owning Task Workflow. Active Subworkflow records closed by that task termination record `failure` and retain their parent-call and Trace links, but do not duplicate `safe_termination_performed`; Agent and recovery counts still describe what occurred within each Subworkflow span.

When one terminal cause unwinds an active nested call chain, every affected Subworkflow and the owning Task Workflow record the same executor-assigned `failure_code`. The executor does not translate ancestor records to generic codes such as `child_workflow_failed` or `descendant_failed`. Each `failure_message` may identify the originating child logical name, while Trace and parent-call identities locate the exact source. Subworkflows that already returned normally keep their successful records.

Agent attribution is span-based. One actual Agent invocation produces one Trace event. When Workflow Ledger records are finalized, the owning Task Workflow and every still-active ancestor Subworkflow whose call span contains that event each record the invocation and therefore classify a later success as Agent-assisted. A Subworkflow that had already returned, and sibling calls outside that active chain, are unaffected. These per-Workflow counts support health analysis of each Component but are not additive: application-wide Agent invocation totals are derived from unique Trace events, never by summing nested Workflow Ledger records.

Public Recovery Rule attempts and results, plus Step reinvocations and results, use the same span attribution. Each actual operation is one Trace event and is reflected in the owning Task Workflow and every active ancestor Subworkflow whose call span contains it; already returned and sibling calls are unaffected. Deterministic recovery alone never changes a successful span from strict to Agent-assisted. Per-Workflow counts show how much each Component depends on recovery, while application-wide recovery and reinvocation totals come from unique Trace events rather than sums of overlapping Ledger records.

Per exact Workflow Component ID, the application derives at least:

- total invocations and counts by final result;
- strict success rate and Agent-assisted completion rate, each divided by finalized invocations and excluding only calls that are still running;
- average elapsed duration overall and split by strict versus Agent-assisted success;
- total and average public deterministic recoveries and Step reinvocations;
- total and average Agent invocations and Working Manifest trials.

A condition failure is attributed to the resolved Task Workflow Component ID because its bound condition is part of that Component. A post-preflight `working_manifest_incompatible` item is always recorded in the Automation Plan item result, but contributes to a per-Component success rate only when the executor can still resolve an actual Task Workflow Component ID. A missing name or non-Task role is therefore not attributed to any Workflow Component. Initial `invalid_plan` preflight failure creates no item or Workflow Ledger result at all.

The Ledger stores raw compact records; summaries are recomputed views rather than authoritative counters. A new immutable Workflow Component ID starts its own statistics. Health data may be shown to users or supplied to the Agent when reviewing improvement opportunities, but it never automatically edits, promotes, disables, or deletes a Workflow.

The Ledger has no Subworkflow restart count or restart-related field because the first version never restarts a Subworkflow.

## Agent candidate trial

The first version executes no Temporary Action Plan and provides no direct model-action channel. Agent-generated executable behavior must be a compatible formal replacement of the current paused Step and enter only through a complete Working Manifest replacement and formal Loader validation. An Asset-only proposal may instead retain the current Step identity and update only Asset files and mappings that Step uses. An already-entered Python frame is never hot-patched; either form takes effect only through the executor-controlled fresh Step invocation that trials the resulting mapping set.

A Working Manifest update is legal only while the Top-level Execution's executor has paused further input at an interruption or Agent-planning boundary and can immediately arrange a legal formal call of the resulting current Step. The update may replace that Step with optional related Assets or may change only Asset files and mappings used by the unchanged Step. Otherwise the Proposal is invalid for the first version and no trial transaction begins. The parent writes and records new immutable files, validates identities, hashes, every formal call target, role permission, and Subworkflow cycle against the complete candidate Manifest, retains the complete pre-switch Working Manifest, then atomically selects the candidate. An unapproved candidate Step runs in an independent Candidate Runner process while the parent owns Trace, files, and Manifest state. A successful trial commits the switch. A failed trial restores the pre-switch Working Manifest only when execution will continue to another Agent Turn. User Cancellation instead terminates an active Candidate Runner and ends the Top-level Execution without rolling back an already selected candidate; that complete candidate state remains available for the post-execution Capability Proposal. A failed or uncertain required rollback is terminal and permits no further Agent Turn, Component call, or game input until the pre-switch snapshot is restored. Executing code never observes a partial capability set. Existing Python frames and external game state continue unchanged, and rollback cannot undo external actions.

Candidate formal source receives all ordinary structural, signature, call-graph, role-permission, identity, and hash checks. Formal execution retains the existing process and lifecycle boundaries, but those boundaries are not a security sandbox. Supervised Operation exposes the complete proposal and residual risk before every selection. The first version has no Unattended Operation; stronger code inspection or operating-system isolation remains future work.

If the user terminates the Top-level Execution while a structurally valid proposal awaits runtime confirmation, the candidate is never selected for execution but may be retained with its Candidate File Batch for one post-execution Capability Proposal. That proposal projects the complete candidate Manifest without changing the ended execution's Working Manifest.

## Result and recovery boundary

Normal returns stay inside Python control flow. An `ExecutionInterruption` crosses into the deterministic executor, which alone applies:

```text
Deterministic Recovery
→ Agent, when enabled
→ Safe Task Termination
```

The Agent cannot invoke itself or perform a control action directly. The parent executor alone interprets one of the three Agent Turn results and decides whether to recheck the Step, validate and trial a Working Manifest proposal, continue another bounded Turn, or perform Safe Task Termination.

### Public exception timing

Public cross-Workflow exceptions are represented by immutable Recovery Rule Components in the current Working Manifest, initially copied unchanged from the active Component Manifest. Each rule occupies one Python module with a concise module docstring and exactly the fixed `detect(ctx) -> bool` and `recover(ctx) -> None` entrypoints. It has a stable logical name, Component ID, and content hash, but no role decorator and is not callable through `ctx.call()`. The executor enumerates rules only from the Manifest's dedicated `recovery_rules` mapping, using stable logical-name order without adding an ordering field to the Manifest.

The executor checks Recovery Rules only after an `ExecutionInterruption` is caught by an `@step` wrapper. It does not check them continuously, after successful actions, or for an interruption outside a Step.

An `Execution Anomaly` raised directly by a Trusted Action wrapper for an access violation also bypasses this process. When it occurs in a Recovery Rule, the current Step wrapper remains paused and control moves directly to the Agent layer or Safe Task Termination.

The wrapper stops further input, keeps its caller frame paused, captures a fresh observation, and begins one deterministic recovery attempt.

The deterministic sequence is:

1. evaluate applicable `detect(ctx)` entrypoints against the same fresh observation; if any detection raises, stop enumeration immediately, record that Recovery Rule and the original exception in Trace, and produce an Execution Anomaly without running any `recover(ctx)` or checking later rules;
2. if multiple rules match, stop as ambiguous and produce an Execution Anomaly;
3. if exactly one rule matches, invoke its `recover(ctx)` and capture another fresh observation; if none matches, continue without public recovery;
4. use the paused wrapper's stable logical name to resolve the current Step again through the latest Working Manifest and evaluate its fresh `condition`;
5. invoke the Step once with the original bound arguments;
6. if it returns a contract-compatible value, return that value from the still-active wrapper to the paused caller;
7. if it interrupts again, cannot be entered, or returns an incompatible value, produce an Execution Anomaly and continue through the Agent layer or Safe Task Termination.

A detection exception is therefore never treated as a non-match. The current Step wrapper and every caller frame remain paused while control moves directly to the Agent layer. The Agent may propose a compatible replacement of the current Step before the executor attempts it again; it cannot create or modify a Recovery Rule in the first version. If Agent handling is unavailable or unsuccessful, the executor performs Safe Task Termination. Continuing with later rules would hide a formal exception and make recovery depend on rule enumeration order.

If the uniquely selected `recover(ctx)` raises or returns any value other than `None`, the executor records the rule identity plus the original exception or invalid return and directly produces an Execution Anomaly. It does not evaluate another rule and does not immediately invoke the current Step because the failed recovery may already have changed the external environment. The Step wrapper and all callers remain paused while the Agent re-observes and plans; unavailable or unsuccessful Agent handling leads to Safe Task Termination.

There are no Step or Subworkflow retry settings, counters, or restart stages. Deterministic Recovery only attempts public recovery followed by one fresh current-Step invocation. A Subworkflow composes Steps or acyclic Subworkflows, records its call and return, and contributes Ledger data; it is never a recovery boundary. When a nested Subworkflow's Step interrupts, the Step wrapper keeps every ordinary caller frame paused, and a compatible recovery result returns naturally through the existing Python chain without restarting or reconstructing any Subworkflow.

If an `ExecutionInterruption` occurs outside a Step, no Step, Subworkflow, or Task Workflow is restarted. The executor immediately produces an Execution Anomaly and performs Safe Task Termination without starting a Runtime Agent Session. Code that may change game state, require verification, or plausibly interrupt should therefore run inside an explicit `@step` boundary.

`Request Step Recheck` asks the executor to capture a fresh observation, resolve the current Step through the latest Working Manifest, and evaluate its fresh `condition`. A true or absent condition permits one invocation with the original arguments. Selecting a candidate Working Manifest likewise requires an immediate legal formal invocation of the compatible replacement Step. A compatible return resumes the paused caller so the Subworkflow and Task Workflow can update their normal local data and eventually return a trustworthy task result. Another interruption, an incompatible return, or a false or uncertain condition returns to Agent diagnosis within the overall budget. The Agent cannot declare task success; inability to restore a compatible Step return leads to another Turn or Safe Task Termination.

Only after the Task Workflow itself reaches a normal return does the executor normalize that task result and call the verifier bound at task start with the original inputs. `True` records `success`, classified as strict or Agent-assisted according to whether the Agent was invoked earlier. An invalid root result, `False`, or a verifier exception records `failure` immediately with its `failure_code` and `failure_message`; there is no remaining Step boundary through which the Agent could create a trustworthy replacement result, so the executor does not invoke it or retry the Task Workflow. There is no Agent-triggered early final verification and no executor-owned success unwind that skips remaining Workflow actions. A containing Automation Plan records this terminal task result and starts its next item as an independent call.

### Paused Step replacement compatibility

A replacement Step may return to the original paused caller only through one entirely new invocation resolved from a Working Manifest that the executor atomically selected while input was paused. Before invocation, the executor verifies the new source, Component ID, content hash, stable logical name, and `@step` role. This replaces no active Python frame: the original `@step` wrapper still owns the paused caller frame.

The new `execute` retains every original parameter's name, annotation, required status, and default value. It may add keyword-only parameters only when each has a JSON-compatible default; the current invocation omits them and therefore uses those new defaults. It cannot add a required parameter or depend on data that only changed upstream control flow could supply. The wrapper builds a new argument copy from its pre-interruption normalized snapshot.

The replacement's `condition` must confirm that the current environment remains within its responsibility, including actionable, expected transitional, or already-completed states. Its implementation follows the normal safe-continuation contract: observe which effects occurred, send only unconfirmed input, wait through transitions, return directly from verified completion, and never depend on local variables from the interrupted invocation.

The return category and meaning remain compatible with the original call. A two-item tuple retains both positional meanings; a source-local named result retains its structural field names, annotations, and meanings without requiring the same class identity; a dynamic dictionary still satisfies the caller's expected semantics; and the actual result must normalize successfully. The first version adds no interface-version or compatibility-level system.

Changing the original parameter contract, adding a required parameter, changing the return contract, leaving the Step's responsibility, losing the ability to determine prior effects, or failing to reconstruct the required return makes the Working Manifest Update Proposal invalid for this first-version Runtime Agent Session. The current task proceeds to another Agent Turn or Safe Task Termination. Task Workflow, Subworkflow, other-Step, and Recovery Rule changes are likewise invalid Agent outputs rather than inactive proposals.

Automation Plan never clears an active Task Workflow or transfers its business state to a replacement. If that task cannot continue through its existing Step recovery boundary, it eventually fails or terminates safely and the Plan advances its index. Cross-Task continuation would require an explicit future Checkpoint/Resume design with state, compatibility, and external-environment semantics; it is not hidden in the first-version invocation model.

This order is fixed by the executor, not selected by the Agent. One Agent Turn may produce a Working Manifest Update Proposal, `Request Step Recheck`, or a Safe Task Termination recommendation; it does not choose when to verify, claim success, or select another Workflow entrypoint.

This does not restore a previously unwound stack: the `@step` wrapper caught the interruption synchronously, so its caller frame never left the stack. Agent work must return through that wrapper and the ordinary Python callers; it cannot create a third public outcome or jump directly to Task Workflow success. Already unwound frames are never reconstructed, and an executing or paused Workflow frame is never hot-patched. A changed Workflow is available only to later new calls.

## Validation under irreversible progress

Candidate validation does not require replay from the task beginning. If candidate A advances irreversible game state and fails, candidate B receives new immutable Component identities and executes from the earliest changed or unvalidated position that remains applicable.

Evidence from earlier traces may be reused only for identical Step or Subworkflow source with unchanged effective inputs, a successful expected result, compatible boundary observations, and no changed upstream value that invalidates the later segment. Changed or affected code must execute again.

Formal trials execute only verified Python control flow. Unobserved new branches must be omitted or raise `ExecutionInterruption` until a later real occurrence is traced. Calls to an already registered Subworkflow require validation of the new call and return boundary, not redundant validation of its unchanged internals. For permanent approval, structural validity is mandatory and the review displays successful-trial and Validation Coverage evidence, but their absence does not disable approval. Human approval remains mandatory before new Python source enters a Component Manifest.

## Component retention and cleanup

Normal creation, editing, and approval only add immutable Components. A Component remains protected while referenced by a retained Manifest or durable Working Manifest. Only unreferenced Components may become cleanup candidates.

The Component Usage Index records `last_used_at` when a Workflow or Step is entered or a Trusted Action is invoked. Elapsed time only orders candidates. The user initiates deletion, and the system recomputes all references immediately beforehand. The Agent and background maintenance never delete Components automatically.

Asset cleanup is separate. The Asset Usage Index displays long-unused hashes, latest match regions, and Manifest references for future human review but does not delete accepted old files. Candidate File Batch cleanup after approval, rejection, or discard is reference-safe final disposition of files created by that Top-level Execution, not automatic Asset maintenance.

## Agent-stage support boundary

Stage 2 supplies Python component loading, the runner subprocess, JSON Context exchange, Trace, the local Workflow Run Ledger, interruption capture, deterministic recovery hooks, and validation evidence. It does not add a Workflow DSL, custom interpreter, security sandbox, general event platform, or autonomous permanent registration.

Stage 2 is closed without fixing storage formats and directory layouts, exhaustively enumerating failure codes, or prescribing one game action for every Safe Task Termination. Those are direct implementation choices driven by actual slices. Agent Adapter, Context Builder, Runtime Agent Sessions, Agent Turns, Runtime Exception Handling orchestration, paused-Step reconnection, maintenance trials, and runtime recovery budgets belong to Stage 3. Agent-assisted Workflow Drafting and autonomous Capability Expansion are deferred.
