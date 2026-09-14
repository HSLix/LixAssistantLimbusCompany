# Lix Assistant

Lix Assistant automates a Windows-native Unity game window during an exclusive focused automation session.

## Language

**Target Window**:
The Windows desktop window owned by the Unity game that Lix Assistant observes and operates.
_Avoid_: Emulator, virtual device

**Focused Automation Session**:
The supported interaction mode in which the Target Window remains restored and owns Windows foreground focus for the duration of automation. The user does not operate other desktop applications during the session.
_Avoid_: Background operation, headless operation, foreground simulation

**Cursor-Assisted Background Operation**:
A rejected interaction mode that leaves focus on another application but temporarily moves the physical cursor to operate the Target Window.
_Avoid_: Background operation

**Deterministic Workflow**:
An automation path for officially supported game content that can complete without an Agent or model service. When it encounters an unsupported state, it stops safely and preserves diagnostic evidence.
_Avoid_: Basic workflow, non-AI workflow

**Workflow**:
The collective name for Python-first Task Workflows and Subworkflows, which share a module docstring, a typed Python `execute(ctx, *, ...)` signature, and verified source. A Task Workflow may additionally define `condition` and must define `verify`; a Subworkflow exposes only `execute`. Cross-Component calls use `ctx.call(logical_name, **arguments)`, which resolves through the current Working Manifest. Workflow is not a separately registered component type.
_Avoid_: Global node pool, workflow component

**Task Workflow**:
A user-startable root Workflow whose `execute` entrypoint is marked by plain `@task_workflow`. It maintains completion data through ordinary Python returns and produces a directly JSON-compatible final result; its required `verify` is the sole authority that compares that result with the original inputs to decide success.
_Avoid_: Root node, top-level Subworkflow

**Subworkflow**:
A reusable Workflow whose `execute` entrypoint is marked by plain `@sub_workflow`. It combines Steps and other non-recursive Subworkflows to complete one local responsibility and returns its result without deciding the whole task's final outcome. Nested execution uses the ordinary Python call stack, while loading rejects every direct or indirect Subworkflow call cycle. It is not a recovery boundary.
_Avoid_: Task Workflow, shared node

**Step**:
The smallest independently observable and recoverable Python execution boundary, marked by plain `@step`. It must safely continue from any observable actionable, expected transitional, or completed state within its responsibility, without relying on lost state from an earlier invocation; unknown or stalled states produce an Execution Interruption.
_Avoid_: Every low-level action, YAML node

**Deterministic Recovery**:
Executor-controlled handling inside an interrupted `@step` wrapper: inspect public Recovery Rules, run one uniquely matching recovery when available, then resolve the current Step through the latest Working Manifest and invoke it again. Failure produces an Execution Anomaly. It never restarts a Subworkflow or Task Workflow.
_Avoid_: Agent recovery, implicit error jump

**Recovery Rule**:
A formal immutable Python Component that identifies one cross-Workflow external interruption through a read-only `detect(ctx) -> bool` entrypoint and handles it through a `recover(ctx) -> None` entrypoint. It has a stable logical name, Component ID, and content hash, but no role decorator; neither entrypoint invokes another formal Component.
_Avoid_: Error node, task-specific branch, global exception plugin

**Trusted Action**:
An immutable, shipped or human-approved low-level Python operation registered once as `observe` or `control` in the Manifest's dedicated `trusted_actions` mapping. `observe` reads screenshots, recognition, or environment state; `control` includes input and execution waits. Formal source imports and calls it as an ordinary function under the executor's fixed role matrix; its wrapper verifies classification, caller role, Manifest-pinned identity, and hash and records the invocation. An Agent cannot create or replace a Trusted Action during a Top-level Execution, and generated code does not become trusted merely by performing the same operation.
_Avoid_: Step, Agent-generated function, unrestricted Python call

**Asset**:
A stable semantic resource name whose Manifest entry maps each recorded game language to one relative Asset Library path and complete content hash. It is not a Component, has no Component ID, and has no language or file extension in its logical name.
_Avoid_: Asset Component, image version, absolute resource path

**Asset Library**:
The shared local store of immutable Asset files used by all Manifests. Manifests reference these files by relative path and complete content hash rather than copying them.
_Avoid_: Manifest attachment, staging library

**Asset Usage Index**:
Mutable local Asset metadata keyed by logical name, running game language, and complete content hash. It records the most recent successful use and match region but is not part of a Manifest.
_Avoid_: Component Usage Index, Asset Manifest

**Asset Batch**:
The durable rollback record of Asset Library files added by one Top-level Execution. It survives interruption until those files are safely referenced by an approved Manifest or completely removed after rejection.
_Avoid_: Staging library, Asset version

**Recovery Ladder**:
The fixed escalation order for an interrupted task: exhaust Deterministic Recovery, optionally invoke the Agent through Runtime Exception Handling, and otherwise perform Safe Task Termination.
_Avoid_: Error handler chain, Agent-first recovery

**Run Context**:
The executor-owned interface between formal Components and one Task Workflow's execution environment, including component invocation, Target Window access, language, Working Manifest resolution, Trace, evidence, cancellation, and budgets. Business data flows through explicit parameters, returns, and ordinary Python locals rather than mutable fields on the Context; Agent Python receives only a JSON-compatible snapshot and never the live Context.
_Avoid_: Global runtime state, mutable Workflow

**Execution Trace**:
The executor-owned chronological record of what one real execution attempt actually did from its entry position. It records actual components, plans, actions, observations, results, evidence, and interruptions for diagnosis, recovery, Agent context, and audit, but does not carry normal Workflow business data or determine task success.
_Avoid_: Candidate Workflow, Agent memory, capability snapshot

**Agent Interaction Log**:
The retained record of one Agent diagnosis or planning interaction, including the information supplied to the Agent, its response, and the complete generated Python source. Execution Trace references it when the resulting temporary plan actually runs.
_Avoid_: Execution Trace, Agent memory

**Run Log Bundle**:
The single retention unit for one Task Workflow run, containing its Execution Trace, Agent Interaction Logs, screenshots, and other detailed evidence. The common log-retention policy keeps or removes the bundle as a whole; only the compact Workflow Run Ledger survives independently.
_Avoid_: Workflow Run Ledger, independent evidence lifecycle

**Workflow Run Ledger**:
A durable local history of compact Task Workflow and Subworkflow invocation records used to evaluate reliability, recovery dependence, and duration even after detailed Execution Traces are cleaned. It is mutable operational data, not part of a Component or Component Manifest.
_Avoid_: Execution Trace, Component Usage Index, Workflow definition

**Validation Coverage**:
Evidence that every required segment of a candidate plan has succeeded, assembled from one or more compatible Execution Traces when irreversible progress prevents a clean replay from the beginning. Reused evidence applies only to unchanged content and inputs whose recorded boundary states connect.
_Avoid_: Mandatory end-to-end replay, assumed prefix validity

**Normal Outcome**:
A normal Python return from a formal Component after its own contract has been satisfied. A frozen named result is interpreted structurally through its fields rather than by Python class identity; a Task Workflow instead returns directly JSON-compatible data, which is verified against its original inputs before becoming success.
_Avoid_: Execution Interruption, Outcome routing table

**Temporary Plan Adapter**:
The parent-side boundary that supplies a JSON Context snapshot to a Temporary Action Plan subprocess, validates and normalizes its JSON-compatible return, records Trace data, and converts subprocess exceptions, invalid results, and timeouts into `ExecutionInterruption`. The plan itself knows no transport envelope.
_Avoid_: Temporary Action Plan, Workflow result type

**Execution Interruption**:
A raised interruption from a failed condition, timeout, unmet expected result, lack of progress, or execution error. Inside a Step, `@step` catches it before the caller frame unwinds and enters the Recovery Ladder; outside a Step it directly produces an Execution Anomaly.
_Avoid_: Normal Outcome, Execution Anomaly

**Automation Plan**:
User-saved configuration executed from a frozen ordered list of Task Workflow stable logical names and normalized inputs plus a current item index. It is not a Component or Manifest entry and has no execution stack. Before any task starts, the complete configuration must parse, every name must resolve through the initial Working Manifest to a Task Workflow, and every input must bind and normalize successfully. Each list position then becomes one independent best-effort call, including repeated occurrences of the same task; the latest Working Manifest is checked again before that call. The Plan records an ordered per-item result and proceeds without item identities, dependencies, conditions, retries, result mappings, state inheritance, or failure policies. Completing traversal is distinct from every task succeeding; invalid configuration, cancellation, a process failure, or an inability to continue scheduling interrupts the Plan.
_Avoid_: Workflow, Task Workflow

**Top-level Execution**:
One user-started execution boundary: either a directly started Task Workflow or one Automation Plan and all of its sequential Task Workflows. It owns exactly one shared Working Manifest from start through final review or disposal.
_Avoid_: Task Workflow call, Subworkflow call

**Runtime Exception Handling**:
An optional Agent capability that responds when deterministic execution no longer satisfies its expected state or progress. It produces a visible Temporary Action Plan to recover the current task without making that plan a permanent system capability.
_Avoid_: Intelligent recovery, fallback workflow

**Execution Anomaly**:
A mismatch, ambiguity, failed expectation, timeout, lack of progress, or execution-contract violation for which the deterministic executor can find no remaining legal path that continues the task. A Trusted Action access violation produces this directly without public Deterministic Recovery. It is the only condition that can trigger Runtime Exception Handling.
_Avoid_: Agent opportunity, normal uncertainty

**Safe Task Termination**:
An executor-performed action that stops only the current Task Workflow and its remaining input while leaving the application, Target Window, and containing Automation Plan running. The Task Workflow's final result is still `failure`; the record separately states that safe termination was performed. It preserves failure evidence and pending changes, and a containing Automation Plan may proceed to its next independent task.
_Avoid_: Application exit, game shutdown, system shutdown

**Cancellation**:
An executor control signal rather than a Component exception. It stops new input and interrupts a containing Automation Plan with `reason: user_cancelled` without invoking Deterministic Recovery or Agent. If a Task Workflow run record already exists, that record becomes `failure` with `failure_code: user_cancelled`; otherwise no Task result is created. `safe_termination_performed` reports only whether the executor actually performed that action. Exact cancellation position remains in Trace, and formal source cannot catch or clear the signal.
_Avoid_: Execution Interruption, Execution Anomaly

**Task Workflow Result**:
The final business result of one considered Task Workflow call after Automation Plan preflight or direct launch: `success` or `failure`. Every considered task that does not complete successfully is `failure`, including one whose `execute()` is not entered because its condition fails or its current Working Manifest binding is incompatible. An executor-owned stable machine-readable `failure_code`, a user-facing `failure_message`, Agent involvement, recovery facts, and whether Safe Task Termination occurred explain how it failed. Components and the Agent supply facts and evidence but cannot choose the final code. Failure location and process remain in Execution Trace rather than a duplicated `failure_stage`. `incomplete` may exist only while the invocation is still open and is not a final result. Initial Automation Plan preflight failure creates no Task Workflow result.
_Avoid_: Automation Plan status, Safe Task Termination, not executed

**Subworkflow Result**:
The Ledger result of one entered Subworkflow call: `success` when it returns normally and `failure` when it exits without a normal return. It has no verifier. Its failure code is executor-owned, while Agent and recovery facts remain separate. Safe Task Termination is recorded once on the owning Task Workflow rather than duplicated on every active Subworkflow.
_Avoid_: Task Workflow final verification, Safe Task Termination count

**Temporary Action Plan**:
A run-scoped Python plan with one `execute(ctx)` entrypoint, executed directly by the Temporary Plan Adapter in a runner subprocess from a JSON-compatible context snapshot. Its source contains no `except`, though `try/finally` is allowed; escaping exceptions are recorded and normalized by the Adapter. It is not a Component and never enters the Working Manifest. Once executed, its `plan_id` and source are immutable; changing it creates a new plan identity.
_Avoid_: Component, Formal Workflow, sandboxed code

**Controlled Evolution**:
The human-governed process that turns evidence from Runtime Exception Handling into a tested candidate change and, only after approval, registers it as a reusable system capability.
_Avoid_: Self-modification, automatic evolution

**Capability Expansion**:
A separate, user-initiated activity in which the Agent may reuse, compose, or explore Python capabilities to propose support for a previously unsupported game objective. Temporary execution follows the selected operating policy, while permanent registration still requires human approval.
_Avoid_: Recovery, autonomous exploration

**Supervised Operation**:
An operating policy in which each immutable Agent Python plan requires source review and confirmation before execution. It is intended for developing, inspecting, and refining automation capabilities.
_Avoid_: Developer mode, manual mode

**Unattended Operation**:
An operating policy in which Agent-generated Python plans may execute without prior review despite not being securely sandboxed, while permanent capabilities still require later human approval.
_Avoid_: Safe sandbox, full trust

**Capability Proposal**:
A reviewable proposal to promote the verified contents of a durable Working Manifest snapshot into a new saved Component Manifest. Its displayed changes are computed against the base Manifest rather than stored as a separate additions-and-deletions structure.
_Avoid_: File change, patch

**Component**:
An immutable, uniquely identified Python Task Workflow, Subworkflow, Step, Recovery Rule, or Trusted Action that a Component Manifest may reference. Formal Task Workflow, Subworkflow, Step, condition, verifier, Recovery Rule, and their private source functions contain no `except`; they may use `try/finally` for cleanup, but a `finally` suite contains no `return`, `break`, `continue`, or `raise` that could suppress or replace the active exception. Trusted Actions are the only Components allowed to normalize caught low-level exceptions. Editing adds a new component ID rather than changing existing content.
_Avoid_: Component Revision, mutable component

**Component Logical Name**:
The stable dotted lookup key used by a Manifest, such as `steps.enter_stage`, to map one logical capability slot to one immutable Component ID. It is not a version object or a field embedded in Component source. A Working Manifest may point the same name to a compatible replacement ID without maintaining an ID-to-ID history.
_Avoid_: Component ID, version chain

**Component Manifest**:
The sole saved version unit: an immutable, validated complete document whose executable mappings resolve stable logical names to exact Component IDs and load information, while its Asset mapping resolves semantic names and languages to shared files and hashes. Multiple manifests may be retained, but exactly one is active and supplies the base snapshot for every automation run.
_Avoid_: Approval history, mutable component list

**Working Manifest**:
A durable, complete copy created from the active Component Manifest for one Top-level Execution. A directly started Task Workflow owns one; all sequential Task Workflows in an Automation Plan share one. The executor resolves their Components through this copy, and verified Agent logic may be organized into new candidate Components that update it. Temporary Action Plans never enter it. An update becomes visible only while the executor is paused and only by atomically replacing the complete file; an entered Python frame is never patched. The system retains only the current Working Manifest. The replaced file exists only long enough to recover a failed switch and is removed after a successful switch. At Top-level Execution end the current copy is discarded, retained for review, or has its verified contents saved after human approval under a new immutable Component Manifest ID.
_Avoid_: Component Manifest, Pending Change Set, manifest diff

**Component Usage Index**:
Mutable housekeeping metadata that records when each Component was last actually executed or read so unreferenced cleanup candidates can be reviewed by elapsed time. It never grants permission to delete a Component that still has a valid reference.
_Avoid_: Component Manifest, deletion authority

**Recovery Point**:
A retained Component Manifest that can be selected to restore its complete capability set. Recovery loads the selected manifest directly rather than replaying or undoing earlier approvals.
_Avoid_: Undo chain, single-component rollback

**Knowledge Library**:
The managed collection of non-executable information available to the Agent when diagnosing game states and preparing plans or proposals.
_Avoid_: Agent memory, capability library

**Expert Guidance**:
User-authored, immediately available knowledge that combines annotated visual evidence, handling instructions, and applicability information. It can guide diagnosis but cannot execute actions or bypass approval boundaries.
_Avoid_: Workflow, executable memory
