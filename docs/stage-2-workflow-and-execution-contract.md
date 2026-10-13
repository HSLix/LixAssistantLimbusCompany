# Stage 2: Python-first Workflow and Execution Contract

This document records the Workflow 2.0 contracts confirmed during Stage 2. Python expresses task control flow; the deterministic executor owns cross-cutting execution, Trace, recovery, Agent invocation, and termination.

Status: accepted and complete. Implementation details do not reopen this contract unless they contradict a locked boundary below.

## Component hierarchy

- A Task Workflow is a user-startable Python root function that completes one supported objective and owns the final task outcome.
- A Subworkflow is a reusable Python function that combines Steps for one local flow responsibility. It cannot call another Subworkflow.
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

The decorators only mark roles and carry no registry, timeout, retry, or other execution policy. These Manifest entries do not repeat `component_kind`, and the loader never infers role from a directory, filename, logical-name prefix, or tag. It first verifies the exact source bytes against the Component ID, then parses and validates exactly one role decorator, and finally binds the stable logical name supplied by the Manifest. Recovery Rules are not `ctx.call()` targets and therefore do not add a fourth role decorator; their dedicated Manifest mapping supplies their identity while their entrypoints remain fixed as `detect` and `recover`.

`@task_workflow`, `@sub_workflow`, and `@step` mark their source functions only. Executor-owned wrappers later bind the Task Workflow's exact `verify`, establish Trace and Ledger behavior, and catch `ExecutionInterruption` at the Step boundary before the caller frame unwinds. A Subworkflow call uses the ordinary Python call stack, and the Subworkflow is not a recovery or restart boundary.

Formal Task Workflow, Subworkflow, Step, `condition`, `verify`, Recovery Rule, and every ordinary private function in their source files may contain no `except` clause. Candidate loading rejects any such AST node without analyzing the caught type, reachability, or whether it re-raises. `try/finally` without `except` remains legal for cleanup, but the loader rejects every `return`, `break`, `continue`, or `raise` inside a `finally` suite without analyzing reachability or whether a raise is a bare rethrow. A legal `finally` completes cleanup and lets the original exception propagate naturally; if cleanup itself raises, the wrapper records the complete Python exception chain, including the original. This is a source-wide structural rule, not an exception-catching permission model.

Formal Components make every cross-Component call through the Context API:

```python
result = ctx.call("steps.enter_stage", stage_name=stage_name)
```

`ctx.call()` stores no Component ID, function object, cache, or reference lifecycle. At each invocation the executor resolves the stable logical name through the current Working Manifest, verifies the Component ID against the source bytes together with the role and bound arguments, invokes it through the appropriate role wrapper, and records the resolved logical name and Component ID. Direct imports of another Workflow or Step implementation are invalid. Ordinary Python inside a Component source remains an implementation detail. Standard-library calls and Trusted Actions are not cross-Component calls and do not use this API.

Formal source invokes a Trusted Action through `ctx.action(logical_name, **arguments)`. Its target is a string literal resolved through the Manifest's dedicated `trusted_actions` mapping, which pins each action name to its immutable Component ID and one fixed `observe` or `control` classification; the implementation entrypoint is always `execute`. Python source and its typed `execute` signature are the sole action-contract authority. Developers inspect the Candidate Manifest, module docstrings, and signatures directly; the first version exposes no action-discovery command or Run Context discovery method. Candidate loading rejects dynamic action targets and direct, statically visible use anywhere in the source file that violates the fixed matrix below. It does not build a private-function call graph or determine which formal entrypoint may eventually invoke a private function. Runtime action dispatch is therefore the authoritative boundary: before an action occurs, it repeats target, classification, actual execution-role, and argument checks, rejecting indirect violations, and records actual arguments, normalized results, duration, and evidence in Trace. Trusted Action references cannot change in the first-version Runtime Agent Session.

Every `ctx.call()` target in formal source must be a string literal. Before every Working Manifest atomic update, the system parses Task Workflow and Subworkflow source from the complete resulting candidate Manifest, extracts every formal target, validates target existence and caller-to-target role, including rejection of Subworkflow-to-Subworkflow calls. Every `ctx.call()` anywhere in one Task Workflow or Subworkflow source file, including inside an ordinary private function, belongs to that file's single formal Component and is checked even when the function or branch appears unreachable. Any `ctx.call()` anywhere in a Step source, Task Workflow or Step `condition`, Task Workflow `verify`, or Recovery Rule source is structurally invalid. A Subworkflow definition containing `condition` or `verify` is invalid regardless of its contents. The loader does not analyze function reachability, constant branches, or the eventual caller of a private function.

Any validation error rejects the entire switch and leaves the old Working Manifest active. Runtime `ctx.call()` repeats target resolution and role validation and records the actual target identity. It maintains no active-Subworkflow stack. An unresolved or invalid target raises `ExecutionInterruption`. Revised source changes its Component ID and passes loading again. The first version has no Component Ref object, reference cache, generated binding, or cache-invalidation mechanism. Working Manifest is the only component mapping structure. Recursion among ordinary private Python functions remains an implementation detail; any resulting exception follows the normal execution-error path.

Dynamic targets such as `ctx.call(target_name)`, `ctx.call(f"subworkflows.{name}")`, and `ctx.call(config["workflow"])` are invalid because their targets and roles cannot be checked reliably before loading.

The formal Component orchestration matrix is:

```text
Application service direct start → Task Workflow, Subworkflow, or Step
Automation Plan                  → Task Workflow
Task Workflow                    → Subworkflow or Step
Subworkflow                      → Step
Step                             → no formal Component
```

A direct application-service start selects one Task Workflow, Subworkflow, or Step by stable logical name and supplies its explicit inputs. It uses the Default Manifest unless the developer explicitly selects another saved Manifest ID, which becomes that Run's Base Manifest without changing the Default. Selection does not require that ID to have prior permanent approval. This is an ordinary Top-level Execution through the same executor and Trace path, not a separate debug run type. It does not make a Subworkflow or Step user-startable product functionality and does not synthesize a missing caller frame.

A Task Workflow never calls another Task Workflow; complete tasks are composed only by Automation Plan. A Subworkflow cannot call another Subworkflow in the first version. A Step never uses `ctx.call()` and remains the leaf observable and recovery boundary. `condition()` and Task Workflow `verify()` never call a formal Component. First-version Recovery Rule `detect()` and `recover()` likewise never call formal Components, avoiding nested recovery. Trusted Actions are `ctx.action()` calls governed separately by the fixed matrix below, so permitted `observe` calls from Workflow code are not formal Component orchestration. Ordinary functions inside any of these source files are not architectural entities and receive no separate identity, protocol, or recovery semantics.

Trusted Action access is not configurable. The executor owns one fixed matrix:

```text
Task Workflow or Subworkflow execute → observe
Task Workflow or Step condition      → observe
Step execute                          → observe or control
Task Workflow verify                 → none
Recovery Rule detect                 → observe
Recovery Rule recover                → observe or control
```

`wait` is classified as `control` even though it does not directly mutate the game, because arbitrary Workflow waiting would bypass the Trusted Action's cancellation and timeout boundary and the Step's observation and recovery boundary. There are no component-specific action lists, user-defined permissions, allow/deny rules, independent permission objects, inheritance, or repeated per-Workflow configuration.

Load-time Trusted Action checking is intentionally incomplete and only catches obvious direct violations. A private function has no architectural role of its own, so the loader neither propagates permissions through private calls nor rejects a candidate merely because it cannot prove every indirect path safe. If a restricted entrypoint reaches a disallowed action through such a function, the Trusted Action wrapper deterministically rejects the call before performing the action. This does not create a separate permission or helper model.

A runtime Trusted Action access violation is an execution-contract error in source or invocation, not an external-environment interruption. The wrapper therefore produces an `Execution Anomaly` directly and never checks public Recovery Rules. The Agent may propose changed Steps or Workflows only when the current `@step` wrapper still owns a paused caller and a fresh current-Step invocation can satisfy the established input, return, and safe-continuation contracts. A violation outside a Step starts no Runtime Agent Session; the current Task Workflow records `failure`, and the executor performs Safe Task Termination. A violation during Task Workflow `verify()` records `failure` at the verification stage and likewise receives no Agent rescue. A violation in Recovery Rule `detect()` or `recover()` leaves the current Step paused, allowing an Agent-proposed complete Manifest before the executor attempts the current Step again. None of these paths reconstructs an unwound frame, hot-patches a Workflow frame, or changes the verifier bound at task start.

Role decorators only mark their functions. Executor-owned wrappers use `functools.wraps` so ordinary Python metadata remains useful for inspection and debugging. Formal identity and Trace never depend on that metadata: the logical name and Component ID remain authoritative.

## Formal Workflow definition and loading

Task Workflows, Subworkflows, and Steps are ordinary `.py` source files. Each formal executable Component exposes:

- one concise module docstring, used by the Agent as the Component's sole natural-language description;
- one typed Python entrypoint, `execute(ctx, *, ...)`, whose keyword-only parameters are the sole input contract;
- verified Python source.

Task Workflow and Step may additionally expose an optional `condition(ctx, *, ...) -> bool`, which accepts the same bound parameters and uses only trusted observation and recognition APIs. Subworkflow exposes only `execute` and cannot define `condition`. Each Task Workflow, Subworkflow, or Step occupies exactly one source file, and that file contains exactly one decorated `execute` entrypoint. Its module docstring, allowed role-specific callable, source-local result classes, and ordinary implementation functions belong to that same Component. Multiple formal Components never share one source file, so editing one cannot leave another Component ID unchanged while altering its behavior. File and directory names remain storage details and do not establish role or logical name.

A Task Workflow additionally requires an explicit JSON-compatible return annotation and `verify(ctx, result, *, ...) -> bool`. The `result` annotation exactly matches the Task Workflow return annotation, and the keyword-only parameters match `execute`. At Task Workflow start, the executor binds that exact Component ID, verifier, and normalized original-input snapshot for the lifetime of the task. The verifier compares only an independent copy of that original input with the validated Task Workflow result; it does not read Trace, re-observe the game, call formal Components, change external state, or maintain counters. No Working Manifest change can alter the current task's bound success standard. Subworkflows and Steps do not expose a separate final verifier; they verify their own expected results before returning.

The Agent reads the module docstring and signatures by parsing source without importing or executing it. The docstring is ordinary source: changing it changes the Component ID. Manifest entries do not copy it. Function comments may explain implementation details but do not form another Component description. The first version has no independent `description` or `inputs` field, tags, separate component documentation, or vector index.

Task Workflows, Subworkflows, and Steps pass values through ordinary keyword arguments to `ctx.call()`. Their first-version input annotations recursively support `str`, `int`, `float`, `bool`, `None`, `Literal[...]`, `T | None`, `list[T]`, and `dict[str, T]`, where every nested `T` follows the same rules. Defaults must normalize to JSON as well. Runtime validation is strict: `str`, `bool`, and `int` accept only their exact Python types; `float` accepts an exact `int` or `float` and normalizes either to `float`; `bool` never counts as an integer; `Literal` matches both exact type and value; dictionaries require string keys; and non-finite floating-point values are rejected. No other coercion is performed, so strings never become numbers and an integral float never becomes an integer. Arbitrary classes, Pydantic models, Enum types, sets, tuples, and unions other than optional values are invalid input contracts. The UI and Agent inspect signatures for names, types, defaults, and choices; no separate input DSL or Schema is introduced.

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
4. in an unknown or non-progressing state, raise `ExecutionInterruption` from observed evidence or propagate a timeout from the responsible Trusted Action leaf boundary.

Every important input is followed by observation that confirms whether it took effect. A fresh invocation never blindly replays an earlier input sequence and never depends on local variables lost with the earlier invocation; it reconstructs all continuation decisions from the current environment and original arguments. If the Step cannot determine which effects already occurred or reconstruct the return value its paused caller requires, it is too broad and must be divided differently.

Internal loops and repeated observations remain ordinary Python. Workflow, Subworkflow, and Step have no overall timeout. The first version adds no explicit State or Transition objects, Step retry settings, or general progress events.

The saved Component Manifest is one complete document with `schema_version`, UUID `manifest_id`, `components`, `recovery_rules`, `trusted_actions`, and `assets`. Its ordinary executable and Recovery Rule entries contain only `component_id`; Trusted Action entries additionally contain `classification`. The fixed entrypoints are `execute` for Task Workflow, Subworkflow, Step, and Trusted Action; optional `condition` and required Task Workflow `verify` follow their role contracts; Recovery Rule uses `detect` and `recover`. A saved Manifest contains no source path, source hash, or configurable entrypoint. The loader derives formal source from `components/<sha256>.py` and verifies its exact bytes against the ID. Logical names are Manifest keys made from one or more case-sensitive Python identifiers separated by `.`. The loader does not rewrite them, treats lowercase only as a convention, requires uniqueness across the three executable mappings, and never derives role from a name. In #308, `assets` is required and must be an empty object; the later Asset slice will replace that temporary restriction with its complete entry validation.

A developer candidate Manifest has no `manifest_id` and lets each executable entry contain either an existing `component_id` or a `source_path`, never both. Source paths are relative to that candidate Manifest's directory and may not escape it. Saving validates the complete candidate, computes missing IDs, copies exact source bytes into the formal component directory, and emits a saved Manifest containing only IDs. Multiple logical names may reuse one ID, but aliases of one Trusted Action ID must retain one classification.

Publishing validates and loads the complete candidate, then writes immutable Component files and the saved Manifest without changing `manifests/default.json`. Selecting a Default Manifest is a separate explicit operation that validates and loads any saved ID before atomically replacing that pointer; an ID without permanent approval first requires a warning and explicit confirmation. A failed publish, failed Default selection, or declined confirmation leaves the previous Default selected. Immutable files already written but not referenced by a retained Manifest remain available for later reference-based cleanup; publishing does not try to delete them as rollback. Unexpected exceptions during validation, load, publishing, or Default selection are logged at `error` with their traceback and failing phase. Expected validation rejection is returned through the structured validation result and is not logged as a system exception.

At Top-level Execution start, the selected Base Manifest becomes the initial complete Working Manifest and is durably retained by Manifest ID. Every complete Manifest actually used for an attempt is likewise retained by Manifest ID; repeating identical content reuses its ID and records another attempt in Trace. Formal execution resolves by logical name and verifies source bytes against the Component ID. An Agent may change Steps, Task Workflows, and Subworkflows, but not Trusted Actions, Recovery Rules, or Assets in this scope. Changed Components use the ordinary loading and execution path after complete validation and supervised permission. An entered Python frame retains its original implementation and locals; later new calls resolve through the selected complete Manifest.

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

The Agent may add immutable source files for changed Steps, Task Workflows, and Subworkflows during a run but may not overwrite, rename, or delete existing Component files. It does not create or change Assets, Trusted Actions, or Recovery Rules in this scope. Every file actually created by one Top-level Execution is appended to its durable Candidate File Batch with its relative path and complete content hash. Reusing identical source adds no entry.

```json
{
  "run_id": "run-123",
  "state": "active",
  "files": ["ui/popup/confirm-zh-a31f28c47d20.png"]
}
```

When attempted Manifests are retained for review, their proposals and complete closed Candidate File Batch remain without reference-based cleanup. After whole-Manifest approval or rejection, the system recomputes references from every retained Manifest and Capability Proposal, then deletes only unreferenced files created by that Batch. Cleanup is resumable and the Batch is deleted only after it completes. The first version never automatically removes accepted old Assets; a retained attempted Manifest is a real source reference, while Trace alone is not.

## Python execution model

Python provides parameters, local variables, `if`, loops, returns, Task Workflow and Subworkflow calls, and the ordinary call stack. A normal return is the Normal Outcome channel; raising `ExecutionInterruption` leaves ordinary control flow and enters the executor's interruption channel. There is no common `Outcome` class, output routing table, or result schema.

Formal Components never catch exceptions. Every exception reaches the applicable wrapper and is recorded with its original detail in Trace. A Step wrapper normalizes an exception from Step `condition` or `execute` into `ExecutionInterruption` and enters Deterministic Recovery, Agent, then Safe Task Termination. An exception outside a Step directly produces an Execution Anomaly and Safe Task Termination without starting a Runtime Agent Session. A verifier exception records Task Workflow `failure`, for example with `failure_code: verify_failed`, and receives no Agent rescue because the Task frame has ended. A case that is legitimately ignorable must be represented by an explicit ordinary Trusted Action result and normal Python branching rather than a caught exception, default success, or silent continuation.

User cancellation is not an exception and never enters either path. It is an executor control signal checked by wrappers and Trusted Actions before further input and invokes neither public Recovery Rules nor Agent. It prevents new Trusted Actions and Agent Turns and wakes a cooperatively paused task without closing the main application or Target Window. A containing Automation Plan records `status: interrupted` with `reason: user_cancelled` and starts no later item. If a Task Workflow run record already exists, it records `result: failure` with `failure_code: user_cancelled`; if no such record exists, cancellation creates no Task result. Active Subworkflow records close under the normal shared-cause rule. `safe_termination_performed` reports only whether the executor actually performed Safe Task Termination. The exact position remains in Trace. Formal source cannot catch, suppress, or clear the signal. A process crash cannot claim completed Safe Task Termination.

Trusted Actions are the exception: their shipped or human-approved implementations may catch low-level library or operating-system exceptions. They must record the original exception and either return an explicit documented Normal Outcome or re-raise a normalized exception for the calling wrapper. They cannot silently pass, fabricate success, or hide the original evidence.

Timeout ownership stays at the three leaf boundaries that can safely stop their own work. A Trusted Action implements timing and Cancellation checks around its own library calls or wait loop and raises the ordinary normalized timeout exception only after that work has stopped. The Agent Adapter owns its model-request timeout and cancellation, while an external-process launcher owns waiting for and terminating its process before raising. The Workflow Executor never places an arbitrary Python Component call in a background thread and pretends to terminate it: it only records the leaf exception in Trace and propagates it through the existing recovery or terminal-failure path. Timeout values are leaf implementation configuration, not Workflow input, Manifest data, `ctx.call()` policy, or another runtime state machine.

A Step or Subworkflow with one result returns an ordinary JSON-compatible value. It may return a two-item tuple only when both positions have stable, unambiguous meaning. Three or more fixed results use a named result class defined in that Component's source, normally `@dataclass(frozen=True)`; this class is not a Component or Manifest entry, and every field must normalize to JSON-compatible data. A result with genuinely dynamic mapping semantics may be a dictionary.

Named results use a structural contract. Callers read `result.field_name` and cannot import the result class or depend on its class name, module path, object identity, or `isinstance()` checks. The contract consists only of field names, annotations, and documented meaning. `ctx.call()` returns the actual frozen dataclass instance in the same process, without creating another result-object layer, while the executor normalizes its fields for Trace. A replacement implementation remains compatible when that structure and meaning remain unchanged even though its Python class identity is new. Code needing dynamic keys or extensible structure uses a dictionary instead of a shared result-class Component.

A Step or Subworkflow may use the richer return forms above, but a Task Workflow root result is limited to the same recursively JSON-compatible scalar, list, and string-keyed dictionary forms allowed by formal input annotations. It cannot return a tuple or source-local named result. The Task Workflow maintains completion data through local variables and ordinary returns from its Subworkflows and Steps, then returns a value matching its explicit return annotation. The executor validates and normalizes that value and supplies it with the startup-bound original inputs to the required `verify`; only the exact boolean value `True` records `result: success`. An invalid result, `False`, or a verifier exception records `result: failure` with a stable machine-readable `failure_code` and user-facing `failure_message`. Because its call stack has already ended, the executor neither invokes the Agent nor starts that Task Workflow again. `verify` performs no new observation, and Workflow code must not use a boolean or ambiguous dictionary merely to bypass its result contract. Failure location and process remain in Trace; the Ledger has no `failure_stage`. Safe Task Termination belongs only to the executor: it is a recorded action, not a Workflow return value or a fourth final result category.

Every directly started Task Workflow, Subworkflow, or Step completes through one public Run Result. It records the entry logical name, actual Component ID, and role. A successful result exposes the normalized normal return as `output`; a failed result omits `output` and carries `failure_code` and `failure_message`. Task Workflow success additionally requires its startup-bound verifier to return exactly `True`; Subworkflow and Step success require only a contract-valid Normal Outcome. Callers read `output` from the Run Result rather than extracting a return from Trace.

Only the executor assigns the final `failure_code`. It maintains the codes as ordinary internal constants rather than a configurable registry, Manifest data, or Component-provided vocabulary. Workflow code, wrappers, Recovery Rules, Trusted Actions, and the Agent provide exceptions, observations, messages, and evidence; the executor maps those facts to the final code. Published code meanings are stable and may only be extended, never renamed or reused. An unclassified failure uses `execution_failed`, while its complete original detail remains in Trace and `failure_message`; a dedicated code is added later only when program logic or health statistics actually need it. The Agent cannot select or override the final classification.

## Automation Plan execution

Automation Plan is configuration saved by the user outside LALC, not a Component or Component Manifest entry. The first version starts an existing Plan file through the CLI; LALC does not edit or save Plan files. The file uses JSON, consistent with existing CLI input and Manifest files. Its complete executable structure is one ordered `items` list. Each item contains only a Task Workflow stable logical name and its explicit input dictionary:

```json
{
  "items": [
    {"task": "tasks.claim_daily_reward", "inputs": {}},
    {"task": "tasks.run_mirror_dungeon", "inputs": {"run_count": 3, "team_names": ["team_a", "team_b"]}}
  ]
}
```

The same Task Workflow may occur more than once, and each occurrence is an independent call. Its list position identifies it within that Plan execution; there is no separate `item_id`. Item-level `condition`, retry, dependency, failure policy, result mapping, or other execution fields are invalid. Eligibility remains the selected Task Workflow's own `condition`, and inputs remain governed by its Python signature.

One Automation Plan execution has one Run ID. All of its Task Workflow items belong to that Run and share its Working Manifest and Trace; list position identifies the Plan item, while each actual Workflow invocation has its own run-local `call_id`. The Run ID shown in each item summary is therefore the same Plan Run ID.

Before invoking any Task Workflow, the executor performs one complete preflight against the Working Manifest created for this Top-level Execution. It checks only:

1. the Plan file and its `items` structure parse successfully;
2. every `task` logical name resolves to an existing Task Workflow;
3. every `inputs` dictionary binds to that Task Workflow's signature, passes its declared type constraints, and normalizes successfully.

Preflight collects and reports every error rather than stopping at the first one. If any check fails, no Task Workflow is invoked and the Automation Plan records `interrupted` with reason `invalid_plan`. A corrected configuration requires a new Plan execution. Preflight does not evaluate any Task Workflow `condition`, observe environmental eligibility, predict success, inspect task dependencies, or test compatibility between adjacent tasks.

After successful preflight, Automation Plan retains only the frozen ordered logical names and normalized inputs plus the current item index. It has no Python execution stack. Immediately before each item, the executor resolves its logical name again through the latest Working Manifest, rechecks that it is a Task Workflow, and validates the frozen input against the current implementation. A compatible implementation becomes a completely new Task Workflow call and binds its own current `verify`. A missing name, changed role, or incompatible input records `result: failure` with `failure_code: working_manifest_incompatible` and proceeds without Agent intervention, Working Manifest rollback, or another full preflight. The current implementation's `condition` is then evaluated. A normal false records `task_condition_not_satisfied` without Agent; an exception records `task_condition_check_failed` without starting a Runtime Agent Session. Either failure then advances the Plan.

Automation Plan uses one fixed best-effort sequential policy. Each listed Task Workflow is considered once in order and records only `success` or `failure`. If its entry `condition` is satisfied or absent, the executor creates a fresh call with that item's inputs, call stack, original-input snapshot, and bound verifier. If the entry condition fails or Working Manifest incompatibility prevents entry, the item still records `failure` even though `execute()` is not invoked. Agent involvement, recovery, and Safe Task Termination remain separate facts rather than result categories. There is no task dependency graph, retry of the same Task Workflow, `continue_on_failure`, configurable failure policy, or supervised-versus-unattended branch. A directly started Task Workflow has no next item and naturally ends after its result is recorded.

Automation Plan has no `verify()` and does not reinterpret its Task Workflow results as one business success predicate. After successful preflight and consideration of every listed item, its scheduling status is `completed` even when some items record `failure`. It also produces an ordered item summary containing each Task Workflow logical name, normalized input, result, duration, and Run ID. Invalid initial preflight records `status: interrupted` with `reason: invalid_plan`, creates no Task Workflow result, invokes no Task Workflow condition, and contributes to no Workflow success statistics; corrected configuration requires a new Plan execution. User cancellation records `status: interrupted` with `reason: user_cancelled`, terminates the active task when one exists, and starts no later item. Process failure or an inability to persist Trace or Workflow Run Ledger records interrupts the Plan, stops the active Task Workflow if one exists, and starts no later item. Workflow reliability and Agent-recovery statistics remain properties of individual Task Workflow Ledger records; the first version defines no Automation Plan success rate or Agent recovery path.

Workflow code cannot invoke the Agent. An `ExecutionInterruption` raised inside a Step is caught by its `@step` wrapper, which captures the current Step, bound arguments, observations, outputs, and evidence and synchronously enters executor-controlled recovery. The caller's Workflow or Subworkflow frame remains paused inside the wrapper call and never unwinds. An interruption outside a Step directly produces an Execution Anomaly.

Step boundaries are selected for independent Trace and verification value rather than for every low-level action. A recognition-action-verification sequence may be one Step; a larger reusable local procedure becomes a Subworkflow.

In the first version, `@step` only marks a function as an executor-visible boundary:

```python
@step
def enter_stage(ctx, *, stage_name: str):
    ...
```

Its wrapper records Step identity and actual arguments, `condition` result, start and end time, invoked Trusted Actions, observations and verification evidence, normalized return or `ExecutionInterruption`, and actual duration. The decorator has no timeout, retry, or other execution-policy parameters. Expected-result verification and lack-of-progress checks remain ordinary Python code and raise `ExecutionInterruption` when execution cannot continue or be verified. The first version has no generic progress event or heartbeat mechanism.

## Focused observation for Issue #314

The application provides `lalc connect` to find, validate, and report an already-running Limbus Company Target Window. Discovery succeeds only when exactly one window matches and its identity and usable client area validate; zero or multiple matches produce an explicit error. The command does not launch the game or choose an ambiguous match. An explicit connect attempts to restore and foreground the unique window once, waits at most one second for asynchronous foreground activation, then verifies actual foreground ownership and client-area validity. A focus timeout reports the native request's return value and the actual foreground window identity; failure is reported without a focus-stealing loop or game control input. CLI errors preserve exception types and the original exception chain. APIs such as `SetForegroundWindow` that do not document extended error codes are reported by their return values rather than unrelated last-error values.

A successful connect captures the client area, saves that exact image as PNG, and writes its window identity, image path, and screenshot dimensions to a text log file. It neither displays the image nor provides a CLI log viewer; a future GUI log viewer may display it. This diagnostic connection allocates no Run ID and writes no Workflow Run Ledger record. Ordinary Workflow observation still keeps images in memory unless saving is explicitly requested, in which case evidence is saved as PNG; real Runs record their window, screenshot, and refresh events in their own Trace.

The CLI process does not persist a window handle or keep a session alive after it exits. Each later `lalc run` that uses real Windows observation discovers and validates the window again through the same application service, then owns its Focused Automation Session for that Run. The historical `master` and `windows-interaction-lab` branches use the title `LimbusCompany` and class `UnityWndClass`; confirm the owning process identity and these window properties on Windows before treating them as the production selector.

The Focused Automation Session for a Run holds its current screenshot in memory. Workflow code explicitly calls an `observe` Trusted Action to capture a new client-area screenshot, replacing the current one; recognition and explicit evidence saving use the screenshot held by that session. Raw image objects do not cross `ctx.action()` or enter JSON Run results and Trace. Those boundaries carry only JSON-compatible observation metadata, recognition results, and evidence references linked to the captured image.

Before observation or later control, the Windows input layer checks that the selected Target Window still exists, is visible and restored, has a usable client area, and truly owns foreground focus. It owns Per-Monitor DPI awareness, client-area coordinates, and `ClientToScreen` conversion where needed. Capture uses the established `PrintWindow` client-area path. Focus loss invalidates the current screenshot; after focus is regained, a new capture and renewed decision are required before control. Fake platform checks and supervised Windows acceptance use the same application-service entry, and a real Run records window checks, capture, and refresh results in Trace.

## User takeover and manual Resume for Issue #315

Physical user takeover stops new control input, releases held input, invalidates the current screenshot, and interrupts the current Step with an unknown action outcome. Its wrapper retains the Workflow caller frames and enters `paused_by_user`. This interruption bypasses automatic Recovery Rules and Agent recovery; ordinary execution interruptions retain their existing recovery path. The interrupted action is neither queued nor replayed.

The GUI brings the pause notice forward once, without a modal dialog or persistent always-on-top behavior. It explains that user takeover interrupted the current Step and displays that Step's module description and whether it declares an entry `condition`. Step authors describe any manual preparation in the existing module docstring; no separate condition-description schema is introduced. Without a condition, the notice explains that Resume restarts the current Step from its entrypoint.

Explicit manual Resume waits for a quiet input boundary, confirms Target Window foreground focus, refreshes observation, and evaluates the current Step's existing condition with its retained original parameters. A false or exceptional condition check keeps the Run paused and reports the reason. A passing condition permits a fresh invocation of the same Step; absent a condition, fresh invocation is permitted directly. Resume never continues the interrupted Step frame or starts the next Step in its place. Step implementations retain their existing responsibility to handle observable partial or completed effects safely within their own scope.

Takeover, release, pause, Resume checks, and fresh invocation belong in Trace. Errors reported upward retain their explanatory message, original exception chain, and complete Python traceback, rather than only a string summary.

Steps decide when to acquire and refresh screenshots for their business decisions. The input layer checks input ownership, Target Window identity, usable client area, and actual foreground focus before each control action; it imposes neither a screenshot age limit nor mandatory recapture after every input. Screenshots invalidated by takeover, focus loss, or window changes cannot be reused. Resume still refreshes observation before Step re-entry, while avoiding stale business decisions during ordinary execution remains the Step's responsibility.

The initial control scope is `click`, `key_press`, `drag`, and `wait`. Click and drag use synthetic touch without moving the physical mouse cursor; key press uses ordinary foreground key down/up and supports at least Esc, P, and Enter. Drag supplies the long-action takeover acceptance path. Wait remains responsive to takeover, pause, and cancellation. These operations share input-ownership checks and held-input release handling; text entry, key combinations, and a separate long-press operation are outside this slice.

A held-input release failure prohibits further control and terminates the Run, including later Automation Plan items. The application reports `input_release_failed` with the complete exception chain and traceback; it never claims successful release or completed safe termination, and Resume cannot reuse that session.

If physical takeover is detected at a Workflow observation boundary with no active Step, the executor pauses before entering that observation call. Manual Resume confirms quiet input, focus and fresh observation, then permits that pending read-only call; it neither restarts a previously returned Step nor unwinds the Workflow frame. The notice explicitly distinguishes this boundary from restarting an interrupted Step.

## Run Context

Each direct Component run receives an executor-provided Run Context that connects formal Components to runtime services: `ctx.call()`, Target Window access, current game language, Manifest resolution, Trace and evidence recording, cancellation, and non-time execution budgets. Its internal state belongs only to the executor, role wrappers, and Trusted Actions. Formal Components cannot add or arbitrarily modify Context fields, and the API exposes no `ctx.state`, shared business dictionary, or other implicit cross-Component data channel. Formal Components likewise keep no mutable module-global business state: a Task Workflow owns run-local control state in ordinary Python locals, Components exchange business data only through copied explicit parameters and normal returns, and the current game state is learned again through Trusted Actions.

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

Formal Workflow execution and recovery use the same append-only Trace vocabulary. Runtime API and Step wrappers write Trace entries as work occurs, so evidence already flushed remains after a crash or a leaf-boundary timeout. Trace proves what actually executed; it does not preserve the complete temporary capability set that was available but unused.

A Trace header stores the base `manifest_id`, normalized parameters, Context summary, directly started Component logical name, Component ID and role, and whether a temporary Working Manifest was used. Events record every formal Component actually executed by logical name and Component ID. Agent events reference the Agent Interaction Log containing the supplied context and complete response. Executed Recovery Rules and other Components likewise record logical name, Component ID, and necessary evidence. Asset matching events instead record logical name, running and source languages, relative path, complete hash, score, and normalized region. Later events record screenshots and recognition, Trusted Actions, Step boundaries, verification, interruptions, recovery results, and final outputs. Large evidence is stored separately and referenced by `evidence_id`.

The core paired vocabulary is `run_started`/`run_finished`, `component_started` with `component_returned` or `component_failed`, `trusted_action_started` with `trusted_action_returned` or `trusted_action_failed`, and Task-only `verification_started` with `verification_returned` or `verification_failed`. Every event carries its monotonic `sequence`, UTC `recorded_at`, and integer `run_id`. Component and Trusted Action calls receive a run-local increasing `call_id` plus nullable `parent_call_id`; this distinguishes repeated calls and preserves actual nesting even when a crash leaves no closing event. Component events record `logical_name`, immutable `component_id`, role, and copied normalized `inputs`; Trusted Action events additionally record their fixed classification. Because the Component ID already has the form `sha256:<digest>`, Trace stores no duplicate source-hash field.

Normal closing events record the actual normalized `return_value` and a monotonic-clock `duration_ms`. Failure events instead preserve the exception type, message, and complete Python exception chain or traceback together with duration. Task verification records the normalized root result and startup-bound original inputs, then its exact boolean return or exception. `return_value` is a factual call result and does not imply Run success; only a successful `run_finished` and public Run Result expose the accepted final `output`.

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

When one terminal cause unwinds an active nested call chain, the active Subworkflow, if any, and the owning Task Workflow record the same executor-assigned `failure_code`. The executor does not translate ancestor records to generic codes such as `child_workflow_failed` or `descendant_failed`. Each `failure_message` may identify the originating child logical name, while Trace and parent-call identities locate the exact source. Subworkflows that already returned normally keep their successful records.

Agent attribution is span-based. One actual Agent invocation produces one Trace event. The owning Task Workflow records it; the active Subworkflow also records it when its call span contains that event. A later success in either affected span is Agent-assisted. A Subworkflow that had already returned, and sibling calls outside that active chain, are unaffected. These per-Workflow counts support health analysis of each Component but are not additive: application-wide Agent invocation totals are derived from unique Trace events, never by summing overlapping Workflow Ledger records.

Public Recovery Rule attempts and results, plus Step reinvocations and results, use the same span attribution. Each actual operation is one Trace event and is reflected in the owning Task Workflow and its active Subworkflow, if any; already returned and sibling calls are unaffected. Deterministic recovery alone never changes a successful span from strict to Agent-assisted. Per-Workflow counts show how much each Component depends on recovery, while application-wide recovery and reinvocation totals come from unique Trace events rather than sums of overlapping Ledger records.

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

The first version executes no Temporary Action Plan and provides no direct model-action channel. An Agent proposal may change Steps, Task Workflows, and Subworkflows together in one complete Manifest; Trusted Actions, Recovery Rules, and Assets remain outside this scope. Selection requires complete validation, supervised permission for the current execution, and an immediate legal fresh invocation of the paused current Step. Changed Components then run through the ordinary Component path; entered Python frames are not patched.

A Working Manifest update is legal only while the Top-level Execution is paused at a current Step that can be invoked immediately and compatibly. The executor validates all identities, hashes, formal call targets, roles, and signatures in the complete candidate Manifest, then atomically selects that complete Manifest. Every complete Manifest used for an attempt remains durable under its Manifest ID. A compatible current-Step return commits the whole selection for later calls; failure pauses execution for an Agent decision without automatic rollback. The Agent may base another complete candidate on any retained attempt Manifest ID or end execution. No further Component call or game input occurs while that decision is pending. Later Step failure is a new interruption at that Step and does not roll back an earlier committed selection. Runtime permission does not grant permanent publication after the Top-level Execution ends.

Candidate formal source receives all ordinary structural, signature, call-target, role-permission, identity, and hash checks. Formal execution retains the existing process and lifecycle boundaries, but those boundaries are not a security sandbox. Supervised Operation exposes the complete proposal and residual risk before every selection. The first version has no Unattended Operation; stronger code inspection or operating-system isolation remains future work.

If the user terminates the Top-level Execution while a structurally valid proposal awaits runtime confirmation, the candidate is never selected for execution and is not the post-execution Capability Proposal. Only a current Working Manifest whose ID has not already received permanent approval can enter post-execution approval; the candidate and any created source files follow the reference-safe Candidate File Batch cleanup contract.

## Result and recovery boundary

Normal returns stay inside Python control flow. An `ExecutionInterruption` crosses into the deterministic executor, which alone applies:

```text
Deterministic Recovery
→ Agent, when enabled
→ Safe Task Termination
```

The Agent cannot invoke itself or perform a control action directly. The parent executor alone interprets one of the three Agent Turn results and decides whether to recheck the Step, validate and trial a Working Manifest proposal, continue another bounded Turn, or perform Safe Task Termination.

### Public exception timing

Public cross-Workflow exceptions are represented by immutable Recovery Rule Components in the current Working Manifest, initially copied unchanged from the Run's Base Manifest. Each rule occupies one Python module with a concise module docstring and exactly the fixed `detect(ctx) -> bool` and `recover(ctx) -> None` functions. It has a stable logical name and Component ID, but no role decorator and is not callable through `ctx.call()`. The executor enumerates rules only from the Manifest's dedicated `recovery_rules` mapping, using stable logical-name order without adding an ordering field to the Manifest.

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

A detection exception is therefore never treated as a non-match. The current Step wrapper and every caller frame remain paused while control moves directly to the Agent layer. The Agent may propose a complete validated Manifest changing Steps or Workflows before the executor retries the current Step; it cannot modify a Recovery Rule in this scope. If Agent handling is unavailable or unsuccessful, the executor performs Safe Task Termination. Continuing with later rules would hide a formal exception and make recovery depend on rule enumeration order.

If the uniquely selected `recover(ctx)` raises or returns any value other than `None`, the executor records the rule identity plus the original exception or invalid return and directly produces an Execution Anomaly. It does not evaluate another rule and does not immediately invoke the current Step because the failed recovery may already have changed the external environment. The Step wrapper and all callers remain paused while the Agent re-observes and plans; unavailable or unsuccessful Agent handling leads to Safe Task Termination.

There are no Step or Subworkflow retry settings, counters, or restart stages. Deterministic Recovery only attempts public recovery followed by one fresh current-Step invocation. A Subworkflow composes Steps, records its call and return, and contributes Ledger data; it is never a recovery boundary. When a nested Subworkflow's Step interrupts, the Step wrapper keeps every ordinary caller frame paused, and a compatible recovery result returns naturally through the existing Python chain without restarting or reconstructing any Subworkflow.

If an `ExecutionInterruption` occurs outside a Step, no Step, Subworkflow, or Task Workflow is restarted. The executor immediately produces an Execution Anomaly and performs Safe Task Termination without starting a Runtime Agent Session. Code that may change game state, require verification, or plausibly interrupt should therefore run inside an explicit `@step` boundary.

`Request Step Recheck` asks the executor to capture a fresh observation, resolve the current Step through the latest Working Manifest, and evaluate its fresh `condition`. A true or absent condition permits one invocation with the original arguments. Selecting a candidate Working Manifest likewise requires an immediate legal formal invocation of the compatible current Step. A compatible return resumes the paused caller so the Subworkflow and Task Workflow can update their normal local data and eventually return a trustworthy task result. Another interruption, an incompatible return, or a false or uncertain condition returns to Agent diagnosis within the overall budget. The Agent cannot declare task success; inability to restore a compatible Step return leads to another Turn or Safe Task Termination.

Only after the Task Workflow itself reaches a normal return does the executor normalize that task result and call the verifier bound at task start with the original inputs. `True` records `success`, classified as strict or Agent-assisted according to whether the Agent was invoked earlier. An invalid root result, `False`, or a verifier exception records `failure` immediately with its `failure_code` and `failure_message`; there is no remaining Step boundary through which the Agent could create a trustworthy replacement result, so the executor does not invoke it or retry the Task Workflow. There is no Agent-triggered early final verification and no executor-owned success unwind that skips remaining Workflow actions. A containing Automation Plan records this terminal task result and starts its next item as an independent call.

### Paused Step replacement compatibility

A replacement Step may return to the original paused caller only through one entirely new invocation resolved from a Working Manifest that the executor atomically selected while input was paused. Before invocation, the executor verifies the source against the Component ID together with the stable logical name and `@step` role. This replaces no active Python frame: the original `@step` wrapper still owns the paused caller frame.

The new `execute` retains every original parameter's name, annotation, required status, and default value. It may add keyword-only parameters only when each has a JSON-compatible default; the current invocation omits them and therefore uses those new defaults. It cannot add a required parameter or depend on data that only changed upstream control flow could supply. The wrapper builds a new argument copy from its pre-interruption normalized snapshot.

The replacement's `condition` must confirm that the current environment remains within its responsibility, including actionable, expected transitional, or already-completed states. Its implementation follows the normal safe-continuation contract: observe which effects occurred, send only unconfirmed input, wait through transitions, return directly from verified completion, and never depend on local variables from the interrupted invocation.

The return category and meaning remain compatible with the original call. A two-item tuple retains both positional meanings; a source-local named result retains its structural field names, annotations, and meanings without requiring the same class identity; a dynamic dictionary still satisfies the caller's expected semantics; and the actual result must normalize successfully. The first version adds no interface-version or compatibility-level system.

Changing the paused Step's original parameter contract, adding a required parameter, changing its return contract, leaving its responsibility, losing the ability to determine prior effects, or failing to reconstruct its required return prevents reconnection. The current task then proceeds to another Agent Turn or Safe Task Termination. Changes to other Steps, Task Workflows, and Subworkflows may be selected together but affect only later new calls; Trusted Action, Recovery Rule, and Asset changes are outside the Agent modification scope.

Automation Plan never clears an active Task Workflow or transfers its business state to a replacement. If that task cannot continue through its existing Step recovery boundary, it eventually fails or terminates safely and the Plan advances its index. Cross-Task continuation would require an explicit future Checkpoint/Resume design with state, compatibility, and external-environment semantics; it is not hidden in the first-version invocation model.

This order is fixed by the executor, not selected by the Agent. One Agent Turn may produce a Working Manifest Update Proposal, `Request Step Recheck`, or a Safe Task Termination recommendation; it does not choose when to verify, claim success, or select another Workflow entrypoint.

This does not restore a previously unwound stack: the `@step` wrapper caught the interruption synchronously, so its caller frame never left the stack. Agent work must return through that wrapper and the ordinary Python callers; it cannot create a third public outcome or jump directly to Task Workflow success. Already unwound frames are never reconstructed, and an executing or paused Workflow frame is never hot-patched. A changed Workflow is available only to later new calls.

## Validation under irreversible progress

Candidate validation does not require replay from the task beginning. If candidate A advances irreversible game state and fails, candidate B may use any retained attempted Manifest as its modification base, but recovery still makes a fresh call of the paused current Step from the observable current state.

Evidence from earlier traces may be reused only for identical Step or Subworkflow source with unchanged effective inputs, a successful expected result, compatible boundary observations, and no changed upstream value that invalidates the later segment. Changed or affected code must execute again.

Formal trials execute only verified Python control flow. Unobserved new branches must be omitted or raise `ExecutionInterruption` until a later real occurrence is traced. Calls to an already registered Subworkflow require validation of the new call and return boundary, not redundant validation of its unchanged internals. For permanent approval, structural validity is mandatory and the review displays successful-trial and Validation Coverage evidence, but their absence does not disable approval. Agent-proposed Python source requires supervised runtime permission before execution and separate human approval before permanent publication.

## Component retention and cleanup

Normal creation, editing, and approval only add immutable Components. A Component remains protected while referenced by a retained Manifest or durable Working Manifest. Only unreferenced Components may become cleanup candidates.

The Component Usage Index records `last_used_at` when a Workflow or Step is entered or a Trusted Action is invoked. Elapsed time only orders candidates. The user initiates deletion, and the system recomputes all references immediately beforehand. The Agent and background maintenance never delete Components automatically.

Asset cleanup is separate. The Asset Usage Index displays long-unused hashes, latest match regions, and Manifest references for future human review but does not delete accepted old files. Candidate File Batch cleanup after approval, rejection, or discard is reference-safe final disposition of files created by that Top-level Execution, not automatic Asset maintenance.

## Agent-stage support boundary

Stage 2 supplies Python component loading, the runner subprocess, JSON Context exchange, Trace, the local Workflow Run Ledger, interruption capture, deterministic recovery hooks, and validation evidence. It does not add a Workflow DSL, custom interpreter, security sandbox, general event platform, or autonomous permanent registration.

Stage 2 is closed without fixing storage formats and directory layouts, exhaustively enumerating failure codes, or prescribing one game action for every Safe Task Termination. Those are direct implementation choices driven by actual slices. Agent Adapter, Context Builder, Runtime Agent Sessions, Agent Turns, Runtime Exception Handling orchestration, paused-Step reconnection, maintenance trials, and runtime recovery budgets belong to Stage 3. Agent-assisted Workflow Drafting and autonomous Capability Expansion are deferred.
