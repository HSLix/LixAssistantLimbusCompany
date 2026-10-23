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

`@task_workflow`, `@sub_workflow`, and `@step` mark source roles only. One executor invocation mechanism establishes Trace, timing, frames, output validation, and error propagation. Only the Step wrapper adds deterministic recovery; no Task entry-condition or final-verifier callback exists.

Formal Task Workflow, Subworkflow, Step, Step `condition`, Recovery Rule, and every ordinary private function in their source files may contain no `except` clause. Candidate loading rejects any such AST node without analyzing the caught type, reachability, or whether it re-raises. `try/finally` without `except` remains legal for cleanup, but the loader rejects every `return`, `break`, `continue`, or `raise` inside a `finally` suite without analyzing reachability or whether a raise is a bare rethrow. A legal `finally` completes cleanup and lets the original exception propagate naturally; if cleanup itself raises, the wrapper records the complete Python exception chain, including the original. This is a source-wide structural rule, not an exception-catching permission model.

Formal Components make every cross-Component call through the Context API:

```python
result = ctx.call("steps.enter_stage", stage_name=stage_name)
```

`ctx.call()` stores no Component ID, function object, cache, or reference lifecycle. At each invocation the executor resolves the stable logical name through the current Working Manifest, validates the role and bound arguments against its verified loaded implementation, invokes it through the appropriate role wrapper, and records the resolved logical name and Component ID. Source bytes are verified when that Manifest is loaded, including at a legal runtime switch; subsequent calls reuse the immutable implementation without per-call disk reads or rehashing. Direct imports of another Workflow or Step implementation are invalid. Ordinary Python inside a Component source remains an implementation detail. Standard-library calls and Trusted Actions are not cross-Component calls and do not use this API.

Formal source calls literal `ctx.action(logical_name, **arguments)` names resolved through application registration shared by validation and runtime dispatch. The registration owns the callable and fixed observe/control classification. Its Python signature, defaults and docstrings define its contract. Runtime dispatch checks actual caller/phase permissions, validates inputs and outputs, records timing and Trace, and preserves original exceptions and user interruptions. The Agent cannot register, replace or reclassify actions. Stage 3 action listing derives from this registration without duplicate descriptions.

Every `ctx.call()` target in formal source must be a string literal. Before every Working Manifest atomic update, the system parses Task Workflow and Subworkflow source from the complete resulting candidate Manifest, extracts every formal target, validates target existence and caller-to-target role, including rejection of Subworkflow-to-Subworkflow calls. Every `ctx.call()` anywhere in one Task Workflow or Subworkflow source file, including inside an ordinary private function, belongs to that file's single formal Component and is checked even when the function or branch appears unreachable. Any `ctx.call()` anywhere in a Step source, Step `condition` or Recovery Rule source is structurally invalid. A Subworkflow definition containing `condition` or `verify` is invalid regardless of its contents. The loader does not analyze function reachability, constant branches, or the eventual caller of a private function.

Any validation error rejects the entire switch and leaves the old Working Manifest active. Runtime `ctx.call()` repeats target resolution and role validation and records the actual target identity. It maintains no active-Subworkflow stack. An unresolved or invalid target raises `ExecutionFailure`. Revised source changes its Component ID and passes loading again. The first version has no Component Ref object, reference cache, generated binding, or cache-invalidation mechanism. Working Manifest is the only component mapping structure. Recursion among ordinary private Python functions remains an implementation detail; any resulting exception follows the normal execution-error path.

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

Task calls only Subworkflow or Step; Subworkflow calls only Step; Step and its condition call no formal Component. Recovery Rule entrypoints are also leaves. Trusted Actions are separate literal ctx.action calls under the fixed role matrix. Ordinary private functions have no separate role, identity, or recovery policy.

Trusted Action access is not configurable. The executor owns one fixed matrix:

```text
Task Workflow or Subworkflow execute → observe
Step condition                       → observe
Step execute                          → observe or control

Recovery Rule detect                 → observe
Recovery Rule recover                → observe or control
```

`wait` is classified as `control` even though it does not directly mutate the game, because arbitrary Workflow waiting would bypass the Trusted Action's cancellation boundary and the Step's observation and recovery boundary. There are no component-specific action lists, user-defined permissions, allow/deny rules, independent permission objects, inheritance, or repeated per-Workflow configuration.

Load-time Trusted Action checking is intentionally incomplete and only catches obvious direct violations. A private function has no architectural role of its own, so the loader neither propagates permissions through private calls nor rejects a candidate merely because it cannot prove every indirect path safe. If a restricted entrypoint reaches a disallowed action through such a function, the Trusted Action wrapper deterministically rejects the call before performing the action. This does not create a separate permission or helper model.

A runtime Trusted Action access violation is an `ExecutionFailure` and is rejected before the forbidden operation. Diagnostics name the caller Component, execution phase, attempted function or action, and violated restriction. The full traceback retains the offending source file and call line even when a private helper made the call. No separate permission-error conversion tier is required. Existing role restrictions remain, and a Step-local ExecutionFailure enters Step recovery; repair still needs a paused Step and a compatible new invocation. An external Workflow failure cannot reconstruct an ended frame.

Role decorators only mark their functions. Executor-owned wrappers use `functools.wraps` so ordinary Python metadata remains useful for inspection and debugging. Formal identity and Trace never depend on that metadata: the logical name and Component ID remain authoritative.

## Formal Workflow definition and loading

Task Workflows, Subworkflows, and Steps are ordinary `.py` source files. Each formal executable Component exposes:

- one concise module docstring, used by the Agent as the Component's sole natural-language description;
- one typed Python entrypoint, `execute(ctx, *, ...)`, whose keyword-only parameters are the sole input contract;
- verified Python source.

Only Step may additionally expose an optional read-only condition with the same bound parameters as execute. Task Workflow and Subworkflow expose execute only and cannot declare condition or verify. Legacy declarations are rejected with a clear migration message. Each formal Component occupies exactly one source file with one decorated execute and a module docstring; private helpers belong to that Component. Paths and filenames do not establish roles.

Task Workflow requires a directly JSON-compatible return annotation. A normal, contract-valid return is success; the executor does not attach a separate business verifier. Authors should check entry requirements and meaningful final outcomes in ordinary Steps. Such checks use the same Step recovery, permissions, Trace, and input-copying rules as all other business actions. The recommendation does not add an executor-enforced check callback.

The Agent reads the module docstring and signatures by parsing source without importing or executing it. The docstring is ordinary source: changing it changes the Component ID. Manifest entries do not copy it. Function comments may explain implementation details but do not form another Component description. The first version has no independent `description` or `inputs` field, tags, separate component documentation, or vector index.

Task Workflows, Subworkflows, and Steps pass values through ordinary keyword arguments to `ctx.call()`. Their first-version input annotations recursively support `str`, `int`, `float`, `bool`, `None`, `Literal[...]`, `T | None`, `list[T]`, and `dict[str, T]`, where every nested `T` follows the same rules. Defaults must normalize to JSON as well. Runtime validation is strict: `str`, `bool`, and `int` accept only their exact Python types; `float` accepts an exact `int` or `float` and normalizes either to `float`; `bool` never counts as an integer; `Literal` matches both exact type and value; dictionaries require string keys; and non-finite floating-point values are rejected. No other coercion is performed, so strings never become numbers and an integral float never becomes an integer. Arbitrary classes, Pydantic models, Enum types, sets, tuples, and unions other than optional values are invalid input contracts. The UI and Agent inspect signatures for names, types, defaults, and choices; no separate input DSL or Schema is introduced.

The loader validates annotation shapes. Startup and ctx.call bind defaults, validate and normalize inputs, retain independent boundary snapshots, and supply callees independent copies. Each Step retry uses a fresh copy of its original normalized arguments. Normal returns are validated and copied before reaching callers. Task root output is directly JSON-compatible and exposed as output; no verifier receives a separate result/input snapshot. Formal Components never read ctx.inputs.

The optional read-only condition belongs only to Step. It checks before first entry and each fresh recovery-controlled invocation, using trusted observation and recognition. It recognizes the responsibility range, including expected transitions and already-completed states. It obtains required observations explicitly and is never continuously polled by the executor.

For a Step, returning `False`, producing uncertain recognition, or raising during condition evaluation means it is not currently enterable and produces an `ExecutionFailure` inside the Step wrapper. The Workflow never receives a false Step-condition value and cannot skip that Step to continue later control flow. The wrapper checks public Deterministic Recovery, evaluates the condition again, and invokes the Step only when it is satisfied; observation acquisition belongs to the condition and Step. A repeated false, uncertain, or exceptional evaluation produces an Execution Anomaly and proceeds to Agent or Safe Task Termination.

Task Workflow has no entry condition. Recoverable entry checks belong in its first relevant Step. Plan preflight still validates structure, names, roles, and inputs before any Task starts.

A recoverable prerequisite such as returning to the main menu belongs in a Task Workflow's or Subworkflow's first relevant Step. That Step owns observation, control, business checks, and ordinary Step recovery, and may expose an optional read-only `condition`. Reusable visual constraints use approved Assets within that Step. There is no Task/Subworkflow entry condition, separate entry recovery, Condition Expression, condition DSL, expression tree, or supported-scope model.

### Step continuation contract

A Step need not be reversible or strictly idempotent, but every invocation must safely continue from the current observation and original bound arguments. Its ordinary Python code distinguishes four situations without exposing a formal state model:

1. in an actionable state, perform only an action not yet confirmed;
2. in an expected transitional state such as loading, battle animation, or a skill sequence, wait and continue observing without repeating input;
3. in an already-completed state, verify the result and return the contract-compatible value directly;
4. in an unknown or non-progressing state, raise `ExecutionFailure` from observed evidence.

Every important input is followed by observation that confirms whether it took effect. A fresh invocation never blindly replays an earlier input sequence and never depends on local variables lost with the earlier invocation; it reconstructs all continuation decisions from the current environment and original arguments. If the Step cannot determine which effects already occurred or reconstruct the return value its paused caller requires, it is too broad and must be divided differently.

Internal loops and repeated observations remain ordinary Python. Workflow, Subworkflow, and Step have no overall timeout. The first version adds no explicit State or Transition objects, Step retry settings, or general progress events.

A developer candidate Manifest has no `manifest_id` and lets each executable entry contain either an existing `component_id` or a `source_path`, never both. Source paths are relative to that candidate Manifest's directory and may not escape it. Saving validates the complete candidate, computes missing IDs, copies exact source bytes into the formal component directory, and emits a saved Manifest containing only IDs. Multiple logical names may reuse one ID, but aliases of one Trusted Action ID must retain one classification.

Publishing completes static validation, stores immutable Component files, and loads formal implementations from those hash files before saving the complete Manifest; it never changes `manifests/default.json` or reuses a Developer Candidate module as the formal implementation. Selecting a Default Manifest is a separate explicit operation that validates and loads any saved ID before atomically replacing that pointer; explicit selection requires no additional confirmation, regardless of permanent approval status. A failed publish or failed Default selection leaves the previous Default selected. Immutable files already written but not referenced by a retained Manifest remain available for later reference-based cleanup; publishing does not try to delete them as rollback. Unexpected exceptions during validation, load, publishing, or Default selection are logged at `error` with their traceback and failing phase. Expected validation rejection is returned through the structured validation result and is not logged as a system exception.

At Top-level Execution start, the selected Base Manifest becomes the initial complete Working Manifest and is durably retained by Manifest ID. Every complete Manifest actually used for an attempt is likewise retained by Manifest ID; repeating identical content reuses its ID and records another attempt in Trace. Formal execution resolves by logical name through implementations whose source bytes were verified when the selected Manifest was loaded. An Agent may change Steps, Task Workflows, and Subworkflows and propose screenshot-derived Asset additions under ADR 0020, but may not modify existing Asset files, Trusted Actions, or Recovery Rules. Changed Components use the ordinary loading and execution path after complete validation and supervised permission. An entered Python frame retains its original implementation and locals; later new calls resolve through the selected complete Manifest.

## Asset resolution and local storage

ADR 0027 decouples Assets from Component Manifests. An Asset logical name identifies one complete directory under the shared assets/ root; images are named by complete SHA-256, and asset-tag.json in that directory maps hashes to tag lists. All valid images are candidates, including ones absent from the tag map (treated as []). Language is an ordinary optional tag, not an implicit selection rule. Formal source passes logical names, never native paths, through observe Trusted Actions.

Each match reads the directory and tag map afresh, fixes its own candidate/tag snapshot, and uses the current explicitly captured client image. priority_tags defaults to None; None or [] matches all templates. Any-tag overlap forms the preferred group. The whole group is matched; any qualifying result excludes the remaining group. If it has no qualifying result, all remaining templates are matched. Results from the selected batch are jointly sorted by score, position and hash, with configurable cross-template NMS (default enabled, IoU 0.5). Output contains actual template path/hash/tags, pixel and normalized regions, scores and observation identity. Missing logical names, hash mismatch, image decoding or malformed tag metadata are errors preserving original diagnostics, never empty detection results. An existing empty directory or no qualifying detection returns [].

The application retains game_language as Run Context and Trace configuration; it never automatically turns it into priority_tags. Search uses the caller's explicit client-pixel region or the full client area, with no Usage Index-driven region changes. Native-size BGR template matching and its existing scoring remain; OCR and custom-model recognition are deferred.

Every matching call rereads candidate names and tags, including inside one Run; there is no cross-call cache or Manifest Asset snapshot. Adding templates or tags becomes visible to the next call without publish or set-default. A Working Manifest switch changes code only. Actual template hashes/tags and preferred conditions are retained in Trace. The independent asset-usage.json records the latest non-empty returned batch per logical name, including template provenance and Run/Trace/observation references; empty results do not update it, and a later Step failure does not undo successful matching metadata. Observation references do not guarantee saved screenshot pixels.

crop_asset always acquires a new Target Window screenshot and saves its crop with actual observation/region provenance. Existing image bytes are immutable; identical content reuses the same hash path. Optional tags append and deduplicate in stable order. Crop and add-asset write [] for new untagged hashes and never clear existing tags when omitted. add-asset accepts only an existing local crop with valid provenance/hash/decoding, writes only tag metadata and does not require Candidate or game access. No external image import, generated template or resource-cleanup service is introduced.

The current primitives are ctx.match_asset(logical_name, priority_tags=None, region=None, threshold=0.9, nms=True, nms_iou_threshold=0.5) and ctx.crop_asset(logical_name, region=..., tags=None), gated by observe actions. A Step cannot bypass these gates. Raw pixels do not cross Component result boundaries; results contain JSON-compatible metadata. Crop/match return contracts explicitly include tag lists.

Agent Asset creation remains Stage 3.5, not the current independent Stage 3 Component repair. Future creation can affect the next match without a Manifest trial, but never grants overwrite/delete authority over existing images or Components. Manifest approval still concerns executable capability and does not publish an Asset mapping. ADR 0021 retention remains in force; the developer-authorized one-time disposal of obsolete Asset data for ADR 0027 is not automatic run-end cleanup.

## Python execution model

Python provides parameters, local variables, `if`, loops, returns, Task Workflow and Subworkflow calls, and the ordinary call stack. A normal return is the Normal Outcome channel; raising `ExecutionFailure` leaves ordinary control flow and enters the executor's interruption channel. There is no common `Outcome` class, output routing table, or result schema.

Formal Components never catch exceptions. Shared invocation handling records all errors, including already normalized ExecutionFailure, before propagating them without changing their original meaning. Raw errors are wrapped once with an explicit cause and complete traceback. Step condition/execute errors reach the whole Step recovery boundary. Workflow execution outside a Step and Recovery Rule failures use the same diagnostic mechanism but create no replay or recursive recovery boundary.

User pause, physical takeover, and cancellation are control requests rather than task errors. Ordinary Pause cooperates with the Run Gate; where unwinding is necessary, the runtime uses `UserInterruption` with the original intent retained. Pause and takeover permit explicit manual Resume; cancellation prevents subsequent actions and Plan items and is never silently converted to pause. User signals bypass automatic recovery and Agent handling. A cancelled Task with an existing record still closes with `failure_code: user_cancelled`; absent a Task record, cancellation creates no Task result. `safe_termination_performed` reflects only an action actually performed. These controls cannot be swallowed by formal source.

Trusted Actions are the exception: their shipped or human-approved implementations may catch low-level library or operating-system exceptions. They must record the original exception and either return an explicit documented Normal Outcome or re-raise a normalized exception for the calling wrapper. They cannot silently pass, fabricate success, or hide the original evidence.

Execution does not impose elapsed-time cutoffs at any layer, including Trusted Actions, focus acquisition, input-monitor startup/shutdown, manual Resume, model requests, and external-process calls. Waiting alone never raises a timeout interruption. Explicit user cancellation and actual operating-system or library failures remain meaningful; cooperative waits check cancellation without an expiry deadline. Action durations and polling intervals describe intended behavior rather than failure limits. The executor never claims to have terminated a blocked native operation merely because time passed.

Return values associate distinct values with their meanings through descriptive field names or dictionary keys, avoiding ambiguous positional tuples and accidental value swaps. There is no fixed value-count threshold, mandatory frozen dataclass, or dedicated result-class framework. JSON-compatible scalars, lists, and dictionaries remain the current implementation path; dictionaries may represent fixed named results as well as dynamic mappings.

Replacement compatibility preserves the data required by the caller: names, value types, and documented meanings. It does not depend on a result object's Python class identity and introduces no separate named-class comparison system. Ordinary result validation still applies; semantic correctness remains part of implementation, review, and meaningful tests.

Task Workflow root results remain recursively JSON-compatible scalars, lists, and string-keyed dictionaries matching the declared return annotation. Task success means normal return after all scheduled Steps and root-format validation. Meaningful business verification is recommended in ordinary Steps before returning. There is no required verify function, verifier identity binding, verifier permission row, verification event family, or separate verification retry.

Every directly started Task Workflow, Subworkflow, or Step completes through one public Run Result. It records the entry logical name, actual Component ID, and role. A successful result exposes the normalized normal return as `output`; a failed result omits `output` and carries `failure_code` and `failure_message`. Task Workflow, Subworkflow, and Step success require a contract-valid Normal Outcome; business checking remains in ordinary Steps. Callers read `output` from the Run Result rather than extracting a return from Trace.

Errors propagate upward from the operation that produced them without intermediate layers changing their meaning. An existing `ExecutionFailure` keeps its code, message, complete traceback, and cause/context chain; an unnormalized exception may be wrapped once with an explicit cause. Wrappers may add caller and execution-phase evidence but must not reinterpret the cause as a generic child failure, user cancellation, or completed Safe Task Termination. Codes remain ordinary implementation constants with stable meanings, not a configurable registry or a claim that the executor can independently prove whether an error really occurred. Correctly reporting an error at its source is a code-authoring and review responsibility. An unclassified failure uses `execution_failed`, with its original diagnostics retained. Recovery decisions use the active execution boundary and lifecycle state rather than treating a reporting code as proof that an action was performed.

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

After successful preflight, Plan retains frozen ordered logical names and inputs and a current index. Before each item it resolves the latest Working Manifest and validates role and inputs again. Incompatibility records working_manifest_incompatible and advances. Otherwise it starts the Task directly, with no Task condition or verifier. Task normal return or final failure determines that item; errors cannot replay a Task or transfer its business state to another one.

Automation Plan uses fixed best-effort sequential scheduling. Each listed Task is considered once; ordinary Task failure advances to the next independent item. Root-format failure is failure, and a normal compatible return is success. Agent, recovery, and actual termination facts remain separate. Cancellation, input-release failure, infrastructure persistence failure, or fatal failure interrupts scheduling. Plan has no task-level retry, condition, dependency, result mapping, or verifier.

Plan does not reinterpret Task results as an aggregate business-success predicate. Completing traversal records completed even if some items failed. Its ordered summary includes task, normalized input, result, duration, and Run ID. Invalid preflight creates no Task records. Cancellation and inability to continue safely interrupt Plan and start no later item. An ordinary failure does not itself end Plan.

Workflow code cannot invoke the Agent. An `ExecutionFailure` raised inside a Step is caught by its `@step` wrapper, which captures the current Step, bound arguments, observations, outputs, and evidence and synchronously enters executor-controlled recovery. The caller's Workflow or Subworkflow frame remains paused inside the wrapper call and never unwinds. Errors outside a Step have no Workflow replay continuation.

Step boundaries are selected for independent Trace and verification value rather than for every low-level action. A recognition-action-verification sequence may be one Step; a larger reusable local procedure becomes a Subworkflow.

In the first version, `@step` only marks a function as an executor-visible boundary:

```python
@step
def enter_stage(ctx, *, stage_name: str):
    ...
```

Its wrapper records Step identity and actual arguments, `condition` result, start and end time, invoked Trusted Actions, observations and verification evidence, normalized return or `ExecutionFailure`, and actual duration. The decorator has no timeout, retry, or other execution-policy parameters. Expected-result verification and lack-of-progress checks remain ordinary Python code and raise `ExecutionFailure` when execution cannot continue or be verified. The first version has no generic progress event or heartbeat mechanism.

## Focused observation for Issue #314

The application provides `lalc connect` to find, validate, and report an already-running Limbus Company Target Window. Discovery succeeds only when exactly one window matches and its identity and usable client area validate. The command does not launch the game or choose an ambiguous match. An explicit connect restores and requests foreground activation once, then waits for actual focus without repeated activation or an elapsed-time cutoff. A Run can cancel cooperative focus waiting; standalone connect can be interrupted from the terminal. Disappearance of the Target Window and native operation errors remain errors with original diagnostics.

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

Task Workflow remains thin but complete: it interprets top-level inputs, arranges business order, loops, and branches, aggregates Step and Subworkflow returns in ordinary locals, returns its JSON-compatible root result, with meaningful outcome checks expressed as ordinary Steps. Recognition, input, waiting, and result confirmation are pushed down where useful, but a few lines of ordinary business logic do not mechanically require another Component. The first version exposes no general Task Workflow state export, inheritance, or resume method. Local counts, selected teams, loop positions, and intermediate results cannot migrate to a replacement Task Workflow or become mutable shared Context state.

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


```

Here the Task Workflow represents the complete repeated objective, while `subworkflows.run_mirror_dungeon` completes one run. `run_count`, `team_names`, `index`, and the selected team are explicit business data. If a current Step interrupts, the surrounding Python loop frame remains paused; successful Step recovery continues that round without repeating completed earlier rounds. Whether a Mirror Dungeon is active is determined from the environment, and an unrecognizable selected team causes a deliberate exit and restart from configured input rather than reliance on hidden Context state. No loop node, shared state store, or state machine is needed.

The Context Builder supplies the Agent only a JSON-compatible diagnostic snapshot assembled from current runtime information, explicit parameters, returned results, observations, Trace, and the base `manifest_id`. The Agent never receives or modifies the live Run Context. Candidate executable source is handled only through the formal Component Loader and Working Manifest trial path.

Trace is executor-maintained evidence for diagnostics, recovery, Agent context, and audit, not a normal business-data channel. Business data uses parameters, local variables, and returns. Authors should verify important outcomes in Steps. There is no standalone final verifier or fabricated progress event. Crash recovery does not reconstruct Python frames; Checkpoint/Resume remains deferred.

## Execution Trace

Formal Workflow execution and recovery use the same append-only Trace vocabulary. Runtime API and Step wrappers write Trace entries as work occurs, so evidence already flushed remains after a crash. Trace proves what actually executed; it does not preserve the complete temporary capability set that was available but unused.

A Trace header stores the base `manifest_id`, normalized parameters, Context summary, directly started Component logical name, Component ID and role, and whether a temporary Working Manifest was used. Events record every formal Component actually executed by logical name and Component ID. Agent events reference the Agent Interaction Log containing the supplied context and complete response. Executed Recovery Rules and other Components likewise record logical name, Component ID, and necessary evidence. Asset matching events instead record logical name, running and source languages, relative path, complete hash, score, and normalized region. Later events record screenshots and recognition, Trusted Actions, Step boundaries, verification, interruptions, recovery results, and final outputs. Large evidence is stored separately and referenced by `evidence_id`.

The core paired vocabulary is run_started/run_finished and component, condition, trusted_action, and recovery_rule invocation events. The common invocation helper records started with returned, evaluated, failed, or interrupted as appropriate. There is no standalone verification event family. Each event includes sequence, UTC time, Run ID, and relevant call_id/parent_call_id, logical name, Component ID, role, phase, and copied inputs. Component IDs already include their source hash.

Normal closing events record the actual normalized return_value and monotonic duration_ms. Failure events record original type, message, full traceback and cause/context chain, including already normalized ExecutionFailure. User interruptions record their original intent without inventing output. A Component return is a factual call result; only final successful run_finished exposes accepted Run output.

For an interrupted Step, Trace explicitly records the initial interruption, public Recovery Rule matches and execution result, every fresh Step invocation, Agent involvement and Agent Interaction Log references, Working Manifest trial results, the final compatible return or repeated interruption, Safe Task Termination when applicable, and the elapsed duration of each stage.

Trace records each Task normal return or failure and every explicit validation Step. Successful Tasks are strict without Agent calls and Agent-assisted when Agent help restored a normal Step return chain.

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
- for failures, stable machine-readable `failure_code` propagated with its original meaning and user-facing `failure_message`, plus separate facts such as Agent involvement and whether Safe Task Termination was performed; failure location and process remain in Trace rather than a Ledger `failure_stage`;
- public Recovery Rule attempts and successful public recoveries;
- Step reinvocation attempts and successful Step reinvocations;
- Agent invocations, Working Manifest trials, and successful Agent-assisted recoveries;
- optional related `trace_id` values as soft references.

For a successful Task Workflow, **strict success** means the complete objective finished from beginning to end without Agent involvement; any amount of successful deterministic recovery is allowed. **Agent-assisted success** means the objective finished after at least one Agent invocation. These are derived success classifications, not additional `result` values. A Subworkflow has no verifier: a normal return records `success`, while an exception, unwind, or termination before a normal return records `failure` with an executor-owned code. Within a successful Subworkflow span, no Agent involvement is strict success and any Agent help is Agent-assisted success.

Safe Task Termination is performed and counted once at the owning Task Workflow. Active Subworkflow records closed by that task termination record `failure` and retain their parent-call and Trace links, but do not duplicate `safe_termination_performed`; Agent and recovery counts still describe what occurred within each Subworkflow span.

When one terminal cause unwinds an active nested call chain, the active Subworkflow, if any, and the owning Task Workflow record the same originating `failure_code`. The executor does not translate ancestor records to generic codes such as `child_workflow_failed` or `descendant_failed`. Each `failure_message` may identify the originating child logical name, while Trace and parent-call identities locate the exact source. Subworkflows that already returned normally keep their successful records.

Agent attribution is span-based. One actual Agent invocation produces one Trace event. The owning Task Workflow records it; the active Subworkflow also records it when its call span contains that event. A later success in either affected span is Agent-assisted. A Subworkflow that had already returned, and sibling calls outside that active chain, are unaffected. These per-Workflow counts support health analysis of each Component but are not additive: application-wide Agent invocation totals are derived from unique Trace events, never by summing overlapping Workflow Ledger records.

Public Recovery Rule attempts and results, plus Step reinvocations and results, use the same span attribution. Each actual operation is one Trace event and is reflected in the owning Task Workflow and its active Subworkflow, if any; already returned and sibling calls are unaffected. Deterministic recovery alone never changes a successful span from strict to Agent-assisted. Per-Workflow counts show how much each Component depends on recovery, while application-wide recovery and reinvocation totals come from unique Trace events rather than sums of overlapping Ledger records.

Per exact Workflow Component ID, the application derives at least:

- total invocations and counts by final result;
- strict success rate and Agent-assisted completion rate, each divided by finalized invocations and excluding only calls that are still running;
- average elapsed duration overall and split by strict versus Agent-assisted success;
- total and average public deterministic recoveries and Step reinvocations;
- total and average Agent invocations and Working Manifest trials.

A post-preflight `working_manifest_incompatible` item is always recorded in the Automation Plan item result, but contributes to a per-Component success rate only when the executor can still resolve an actual Task Workflow Component ID. A missing name or non-Task role is therefore not attributed to any Workflow Component. Initial `invalid_plan` preflight failure creates no item or Workflow Ledger result at all.

The Ledger stores raw compact records; summaries are recomputed views rather than authoritative counters. A new immutable Workflow Component ID starts its own statistics. Health data may be shown to users or supplied to the Agent when reviewing improvement opportunities, but it never automatically edits, promotes, disables, or deletes a Workflow.

The Ledger has no Subworkflow restart count or restart-related field because the first version never restarts a Subworkflow.

## Agent candidate trial

The first version executes no Temporary Action Plan and provides no direct model-action channel. An Agent proposal may change Steps, Task Workflows, and Subworkflows together in one complete Manifest and include screenshot-derived Asset additions under ADR 0020; existing Asset files, Trusted Actions, and Recovery Rules remain unchanged. Selection requires complete validation, supervised permission for the current execution, and an immediate legal fresh invocation of the paused current Step. Changed Components then run through the ordinary Component path; entered Python frames are not patched.

A Working Manifest update is legal only while the Top-level Execution is paused at a current Step that can be invoked immediately and compatibly. The executor validates all identities, hashes, formal call targets, roles, and signatures in the complete candidate Manifest, then atomically selects that complete Manifest. Every complete Manifest used for an attempt remains durable under its Manifest ID. A compatible current-Step return commits the whole selection for later calls; failure pauses execution for an Agent decision without automatic rollback. The Agent may base another complete candidate on any retained attempt Manifest ID or end execution. No further Component call or game input occurs while that decision is pending. Later Step failure is a new interruption at that Step and does not roll back an earlier committed selection. Runtime permission does not grant permanent publication after the Top-level Execution ends.

Candidate formal source receives all ordinary structural, signature, call-target, role-permission, identity, and hash checks. Formal execution retains the existing process and lifecycle boundaries, but those boundaries are not a security sandbox. Supervised Operation exposes the complete proposal and residual risk before every selection. The first version has no Unattended Operation; stronger code inspection or operating-system isolation remains future work.

If the user terminates the Top-level Execution while a structurally valid proposal awaits runtime confirmation, the candidate is never selected for execution and is not the post-execution Capability Proposal. Only a current Working Manifest whose ID has not already received permanent approval can enter post-execution approval; the candidate and any created files remain stored without approval or automatic deletion, as specified by ADR 0021.

## Result and recovery boundary

Normal returns stay inside Python control flow. An `ExecutionFailure` crosses into the deterministic executor, which alone applies:

```text
Deterministic Recovery
→ Agent, when enabled
→ Safe Task Termination
```

The Agent cannot invoke itself or perform a control action directly. The parent executor alone interprets one of the three Agent Turn results and decides whether to recheck the Step, validate and trial a Working Manifest proposal, continue another bounded Turn, or perform Safe Task Termination.

### Public exception timing

Public cross-Workflow exceptions are represented by immutable Recovery Rule Components in the current Working Manifest, initially copied unchanged from the Run's Base Manifest. Each rule occupies one Python module with a concise module docstring and exactly the fixed `detect(ctx) -> bool` and `recover(ctx) -> None` functions. It has a stable logical name and Component ID, but no role decorator and is not callable through `ctx.call()`. The executor enumerates rules only from the Manifest's dedicated `recovery_rules` mapping, using stable logical-name order without adding an ordering field to the Manifest.

The executor checks Recovery Rules only after a Step condition/execute failure, through one shared recovery procedure. It does not continuously poll, run after success, recursively recover Rule errors, or handle user signals through game recovery. Only a paused Step permits Agent or Manifest-trial continuation. Task has no condition/verifier callback and no additional recovery scope.

A Step-local Trusted Action access violation raises ExecutionFailure and uses this same Step recovery path. A failure while a Recovery Rule itself runs still ends that deterministic recovery attempt; permissions remain unchanged.

The wrapper stops further input, keeps its caller frame paused, and begins one deterministic recovery attempt. It does not prescribe screenshots: detection, recovery, condition, and Step implementations explicitly obtain any observations they need.

The deterministic sequence is:

1. evaluate applicable `detect(ctx)` entrypoints; if any detection raises, stop enumeration immediately, record that Recovery Rule and the original exception in Trace, and produce an Execution Anomaly without running any `recover(ctx)` or checking later rules;
2. if multiple rules match, stop as ambiguous and produce an Execution Anomaly;
3. if exactly one rule matches, invoke its `recover(ctx)`; if none matches, continue without public recovery;
4. use the paused wrapper's stable logical name to resolve the current Step again through the latest Working Manifest and evaluate its fresh `condition`;
5. invoke the Step once with the original bound arguments;
6. if it returns a contract-compatible value, return that value from the still-active wrapper to the paused caller;
7. if it interrupts again, cannot be entered, or returns an incompatible value, produce an Execution Anomaly and continue through the Agent layer or Safe Task Termination.

A detection exception is therefore never treated as a non-match. The current Step wrapper and every caller frame remain paused while control moves directly to the Agent layer. The Agent may propose a complete validated Manifest changing Steps or Workflows before the executor retries the current Step; it cannot modify a Recovery Rule in this scope. If Agent handling is unavailable or unsuccessful, the executor performs Safe Task Termination. Continuing with later rules would hide a formal exception and make recovery depend on rule enumeration order.

If the uniquely selected `recover(ctx)` raises or returns any value other than `None`, the executor records the rule identity plus the original exception or invalid return and directly produces an Execution Anomaly. It does not evaluate another rule and does not immediately invoke the current Step because the failed recovery may already have changed the external environment. The Step wrapper and all callers remain paused while the Agent re-observes and plans; unavailable or unsuccessful Agent handling leads to Safe Task Termination.

There are no Step or Subworkflow retry settings, counters, or restart stages. Deterministic Recovery only attempts public recovery followed by one fresh current-Step invocation. A Subworkflow composes Steps, records its call and return, and contributes Ledger data; it is never a recovery boundary. When a nested Subworkflow's Step interrupts, the Step wrapper keeps every ordinary caller frame paused, and a compatible recovery result returns naturally through the existing Python chain without restarting or reconstructing any Subworkflow.

An ExecutionFailure in Task/Subworkflow execute outside a Step is recorded and reported without replaying that Workflow or starting an Agent Session. Recovery routing uses the active Step boundary and lifecycle state, not a failure-code string. Safe Task Termination must be explicitly performed and recorded.

`Request Step Recheck` asks the executor to resolve the current Step through the latest Working Manifest and evaluate its current `condition`; that condition and the Step own any observation they need. A true or absent condition permits one invocation with the original arguments. Selecting a candidate Working Manifest likewise requires an immediate legal formal invocation of the compatible current Step. A compatible return resumes the paused caller so the Subworkflow and Task Workflow can update their normal local data and eventually return a trustworthy task result. Another interruption, an incompatible return, or a false or uncertain condition returns to Agent diagnosis within the overall budget. The Agent cannot declare task success; inability to restore a compatible Step return leads to another Turn or Safe Task Termination.

A Task Workflow normal return is validated against its declared JSON-compatible type and records success. Invalid format or an exception records failure, with no independent verifier or Task retry. Authors are advised to place meaningful business checks in Steps before return; those checks share ordinary Step recovery. A containing Plan advances after an ordinary Task failure.

### Paused Step replacement compatibility

A replacement Step may return to the original paused caller only through one entirely new invocation resolved from a Working Manifest that the executor atomically selected while input was paused. Loading the selected Manifest verifies its source against the Component ID; invocation checks the stable logical name and `@step` role against that verified implementation. This replaces no active Python frame: the original `@step` wrapper still owns the paused caller frame.

The new `execute` retains every original parameter's name, annotation, required status, and default value. It may add keyword-only parameters only when each has a JSON-compatible default; the current invocation omits them and therefore uses those new defaults. It cannot add a required parameter or depend on data that only changed upstream control flow could supply. The wrapper builds a new argument copy from its pre-interruption normalized snapshot.

The replacement's `condition` must confirm that the current environment remains within its responsibility, including actionable, expected transitional, or already-completed states. Its implementation follows the normal safe-continuation contract: observe which effects occurred, send only unconfirmed input, wait through transitions, return directly from verified completion, and never depend on local variables from the interrupted invocation.

The return category and meaning remain compatible with the original call. Descriptive names keep the required values associated with their meanings, and the result must satisfy ordinary normalization and the caller's data contract. There is no tuple-position compatibility policy, mandatory result class, Python class-identity check, or separate interface-version system.

Changing the paused Step's original parameter contract, adding a required parameter, changing its return contract, leaving its responsibility, losing the ability to determine prior effects, or failing to reconstruct its required return prevents reconnection. The current task then proceeds to another Agent Turn or Safe Task Termination. Changes to other Steps, Task Workflows, and Subworkflows may be selected together but affect only later new calls; Trusted Action, Recovery Rule, and existing Asset file changes are outside the Agent modification scope; screenshot-derived Asset additions follow ADR 0020.

Automation Plan never clears an active Task Workflow or transfers its business state to a replacement. If that task cannot continue through its existing Step recovery boundary, it eventually fails or terminates safely and the Plan advances its index. Cross-Task continuation would require an explicit future Checkpoint/Resume design with state, compatibility, and external-environment semantics; it is not hidden in the first-version invocation model.

This order is fixed by the executor, not selected by the Agent. One Agent Turn may produce a Working Manifest Update Proposal, `Request Step Recheck`, or a Safe Task Termination recommendation; it does not choose when to verify, claim success, or select another Workflow entrypoint.

This does not restore a previously unwound stack: the `@step` wrapper caught the interruption synchronously, so its caller frame never left the stack. Agent work must return through that wrapper and the ordinary Python callers; it cannot create a third public outcome or jump directly to Task Workflow success. Already unwound frames are never reconstructed, and an executing or paused Workflow frame is never hot-patched. A changed Workflow is available only to later new calls.

## Validation under irreversible progress

Candidate validation does not require replay from the task beginning. If candidate A advances irreversible game state and fails, candidate B may use any retained attempted Manifest as its modification base, but recovery still makes a fresh call of the paused current Step from the observable current state.

Evidence from earlier traces may be reused only for identical Step or Subworkflow source with unchanged effective inputs, a successful expected result, compatible boundary observations, and no changed upstream value that invalidates the later segment. Changed or affected code must execute again.

Formal trials execute only verified Python control flow. Unobserved new branches must be omitted or raise `ExecutionFailure` until a later real occurrence is traced. Calls to an already registered Subworkflow require validation of the new call and return boundary, not redundant validation of its unchanged internals. For permanent approval, structural validity is mandatory and the review displays successful-trial and Validation Coverage evidence, but their absence does not disable approval. Agent-proposed Python source requires supervised runtime permission before execution and separate human approval before permanent publication.

## Resource maintenance boundary

Manifest, Component source, and Asset files remain in their normal stores through execution and review. Approval records the reviewed Manifest ID as permanently approved; rejection grants no approval. Neither outcome deletes files. Retention policies, deletion, reference scanning, and other resource maintenance belong to a separately scoped future module and are not implemented in this version (ADR 0021). The Asset Usage Index provides observational metadata rather than deletion authority.

## Agent-stage support boundary

Stage 2 loads verified immutable Python Components in the main process and executes them on the application service worker thread. It supplies Trace, the local Workflow Run Ledger, interruption capture, deterministic recovery hooks, and validation evidence. There is currently no runner subprocess or inter-process JSON Context exchange. TODO after the first release: evaluate moving executor execution into a subprocess, including Context transport, cancellation, and original-error propagation; no isolation guarantee is implied by the current implementation. It does not add a Workflow DSL, custom interpreter, security sandbox, general event platform, or autonomous permanent registration.

Stage 2 is closed without fixing storage formats and directory layouts, exhaustively enumerating failure codes, or prescribing one game action for every Safe Task Termination. Those are direct implementation choices driven by actual slices. Agent Adapter, Context Builder, Runtime Agent Sessions, Agent Turns, Runtime Exception Handling orchestration, paused-Step reconnection, maintenance trials, and runtime recovery budgets belong to Stage 3.5. Agent-assisted Workflow Drafting and autonomous Capability Expansion are deferred.


## Interaction and fatal error reporting

The interaction layer logs exceptions and displays an ordinary error dialog with visible, selectable original traceback and a copy action. GUI start, pause/resume/stop failures and completed unsuccessful Runs use this path. Cancellation remains user control rather than an error popup. CLI logs errors and prints original diagnostics to stderr; it does not start a GUI.

Otherwise unhandled errors reaching the outer application boundary are fatal. Main-thread/GUI callback exceptions and unhandled worker-thread errors are logged and dispatched to the GUI thread. A large fatal dialog states in Chinese and English that the application cannot continue, and that the original information below can be copied and reported to the developer. Closing it exits with failure. A fatal worker or cleanup result is terminal and prohibits another Run. Prior task failures and cleanup errors remain visible together. Persistent application logs use `logs/lalc.log` in the application data directory, alongside independent Run Trace evidence. CLI prints the same bilingual fatal explanation and original error to stderr instead of opening a window.


The lifecycle owner covers GUI import, Qt initialization, callbacks, background-thread error reporting, and shutdown in the same process. Closing the GUI requests cooperative cancellation and waits for its worker's input release and completion. A shutdown failure still changes the application exit status to failure. If a fatal error occurs before a window exists, the owner creates the report when possible or writes the bilingual message and complete traceback to stderr.

Error payloads use failure_message and traceback, without exception_type or exception_message. The complete traceback includes original type and cause/context evidence. Manifest validation continues to use its code/message fields with optional traceback.

Fatal Plan completion preserves status interrupted, reason, items, and previous_result containing the unmodified original Plan result; fatal_errors retains shutdown or other fatal diagnostics. A direct Run instead uses its ordinary failure status and failure_code. A later persistence error may add its own reason and diagnostics without discarding either the original result or task list.

A pause/takeover raised inside a Workflow observe call is handled before its Workflow caller unwinds, using the same manual Resume checks as a pre-call interruption. Resume repeats only that read-only observation with a new call ID; it does not replay previously returned Steps. The outer Run and Plan boundaries recognize only cancel intent as user cancellation.

## Current Manifest, Asset, and Run boundaries

The current Manifest format is schema version 2. Candidate documents contain exactly `schema_version`, `components`, and `recovery_rules`; saved documents also contain UUID `manifest_id`. Entries resolve source paths or Component IDs in a Candidate and only Component IDs after publication. Trusted Actions are application-registered callables, not Manifest Components. Candidate and saved Manifests reject embedded `assets` and `trusted_actions`, version 1, and other legacy formats without migration.

Candidate and saved Manifests have no Asset sidecar. init/validate/publish/load operate on Components and Recovery Rules only. Assets and per-logical-name tags live independently under assets/, and matching verifies image bytes at use time. Old Asset layouts and dedicated libraries are discarded and recreated, with no migration or fallback.

Manifest loading and Working Manifest switching do not access Assets. Each matching invocation directly reads its logical-name directory and tags as described above; no per-Manifest mapping, cross-Manifest synchronization or cross-call cache exists.

Developer crop and add-asset append stable deduplicated tag lists in asset-tag.json. New hashes coexist rather than replacing a same-language slot. Tags are ordinary optional descriptions; no input prompt selects or overwrites an image. Full-hash paths never overwrite different bytes. Future Agent permission remains limited to creation, without overwrite of existing images.

Every formal Run connects and focuses the Target Window and starts physical input monitoring before Component execution, including observation-only and calculation-only Runs. One Automation Plan shares a session and monitor. Cleanup stops monitoring and releases owned input. Calculation-only tests use platform doubles. Diagnostic `connect` remains separate and creates no Run. Old examples were removed; regression behavior is retained in test-owned fixtures. ADR 0026 permits the new schema-2 teaching sample under `example/trusted-actions/` and removes the real mailbox completion gate.


## Revised Stage 2 acceptance and crop registration

ADR 0026 closes Stage 2 around deterministic foundations and existing single-capability evidence, plus crop registration and the teaching sample. The mailbox Workflow and outstanding Windows integration/package checks remain deferred in #317. Stage completion does not imply those checks passed.

`add-asset <name> --image <crop-image-path> [--tags tag ...]` appends tags to a verified local crop. It does not connect to the game, require Candidate, publish or change Default. With no tag input, a new record is [] and existing tags are retained. crop-asset independently captures and stores an image with optional tags. No candidate/asset-library.json or asset-libraries/<Manifest ID>.json is created or read.
