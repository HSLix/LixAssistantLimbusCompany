# LALC

LALC automates a Windows-native Unity game window during an exclusive focused automation session.

## Language

**Target Window**:
The unique existing Windows desktop window of Limbus Company that LALC selects to observe and operate. No window is selected when discovery finds zero or multiple matching windows.
_Avoid_: Emulator, virtual device

**Focused Automation Session**:
The supported interaction mode in which the Target Window remains restored and owns Windows foreground focus for the duration of automation. The user does not operate other desktop applications during the session.
_Avoid_: Background operation, headless operation, foreground simulation

**Architecture Demo**:
The minimum runnable evidence that established the approximate Agent interaction flow, supervision states, and reusable application skeleton before the formal Stage 2 runtime. Its hard-coded Example execution is a replaceable placeholder, not a parallel product runtime that later slices must preserve.
_Avoid_: Disposable prototype, Stage completion, production application, compatibility runtime

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
A reusable Workflow whose `execute` entrypoint is marked by plain `@sub_workflow`. It combines Steps to complete one local responsibility and returns its result without deciding the whole task's final outcome. A Subworkflow cannot call another Subworkflow. It is not a recovery boundary.
_Avoid_: Task Workflow, shared node

**Step**:
The smallest independently observable and recoverable Python execution boundary, marked by plain `@step`. It must safely continue from any observable actionable, expected transitional, or completed state within its responsibility, without relying on lost state from an earlier invocation; unknown or stalled states produce an Execution Interruption.
_Avoid_: Every low-level action, YAML node

**Deterministic Recovery**:
Executor-controlled handling inside an interrupted `@step` wrapper: inspect public Recovery Rules, run one uniquely matching recovery when available, then resolve the current Step through the latest Working Manifest and invoke it again. Failure produces an Execution Anomaly. It never restarts a Subworkflow or Task Workflow.
_Avoid_: Agent recovery, implicit error jump

**Recovery Rule**:
A formal immutable Python Component that identifies one cross-Workflow external interruption through a read-only `detect(ctx) -> bool` entrypoint and handles it through a `recover(ctx) -> None` entrypoint. It has a stable logical name and Component ID but no role decorator; neither entrypoint invokes another formal Component.
_Avoid_: Error node, task-specific branch, global exception plugin

**Trusted Action**:
An immutable, shipped or human-approved low-level Python operation whose fixed `execute` function is registered once as `observe` or `control` in the Manifest's dedicated `trusted_actions` mapping. `observe` reads screenshots, recognition, or environment state; `control` includes input and execution waits. Formal source calls its literal logical name through `ctx.action()` under the executor's fixed role matrix; runtime dispatch verifies classification, caller role, arguments, and the Manifest-pinned Component ID against the source bytes and records the invocation. An Agent cannot create or replace a Trusted Action during a Top-level Execution, and generated code does not become trusted merely by performing the same operation.
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

**Candidate File Batch**:
The durable ownership record of immutable Component source and Asset files actually created by one Top-level Execution. It is created only when needed, is never reused by another execution, and remains with a retained Working Manifest until approval or discard performs reference-safe final cleanup. Working Manifest mappings decide whether a file is currently usable; the Batch decides whether a file created by that execution must ultimately be retained or removed.
_Avoid_: Manifest diff, staging library, Asset version

**Developer Candidate**:
The one editable complete Manifest draft in a project checkout, containing developer-authored Component source intended for validation and publication. It shares Manifest format and validation rules with runtime proposals but never shares writable storage or ownership with a Top-level Execution's Candidate File Batch.
_Avoid_: Candidate File Batch, partial Manifest, global candidate registry

**Capability Bundle**:
The transport-neutral software-release data package containing one complete retained Component Manifest and every immutable Component and Asset it references. It carries no Default Manifest selection and is distributed as a whole rather than as individual Component updates.
_Avoid_: Developer Candidate, application binary, single-Component package

**Recovery Ladder**:
The fixed escalation order for an interrupted task: exhaust Deterministic Recovery, optionally invoke the Agent through Runtime Exception Handling, and otherwise perform Safe Task Termination.
_Avoid_: Error handler chain, Agent-first recovery

**Run Context**:
The executor-owned interface between formal Components and one execution environment, including component invocation, Target Window access, language, Manifest resolution, Trace, evidence, cancellation, and non-time execution budgets. Business data flows through explicit parameters, returns, and ordinary Python locals rather than mutable Context fields or mutable Component module globals; the Agent receives only a JSON-compatible diagnostic snapshot and never the live Context.
_Avoid_: Global runtime state, mutable Workflow

**Execution Trace**:
The executor-owned chronological record of what one real execution attempt actually did from its entry position. It records actual components, plans, actions, observations, results, evidence, and interruptions for diagnosis, recovery, Agent context, and audit, but does not carry normal Workflow business data or determine task success.
_Avoid_: Candidate Workflow, Agent memory, capability snapshot

**Agent Interaction Log**:
The retained record of one Agent Turn, including the information supplied to the Agent and its complete response. Execution Trace references it when the executor acts on that response.
_Avoid_: Execution Trace, Agent memory

**Agent Adapter**:
The provider boundary that sends one self-contained Context Snapshot to a local or remote model and parses exactly one of the three allowed Agent Turn results. It owns transport and provider-error normalization but never performs actions, writes files, validates or switches a Working Manifest, invokes formal code, or decides recovery and termination.
_Avoid_: Runtime Agent Session, executor

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

**Execution Interruption**:
A raised interruption from a failed condition, a leaf-boundary timeout, an unmet expected result, observed lack of progress, or an execution error. Inside a Step, `@step` catches it before the caller frame unwinds and enters the Recovery Ladder; outside a Step it directly produces an Execution Anomaly. Workflow, Subworkflow, and Step have no overall timeout; only Trusted Actions, the Agent Adapter, and external-process calls impose time limits at their own leaf boundaries.
_Avoid_: Normal Outcome, Execution Anomaly

**Automation Plan**:
User-saved configuration executed from a frozen ordered list of Task Workflow stable logical names and normalized inputs plus a current item index. It is not a Component or Manifest entry and has no execution stack. Before any task starts, the complete configuration must parse, every name must resolve through the initial Working Manifest to a Task Workflow, and every input must bind and normalize successfully. Each list position then becomes one independent best-effort call, including repeated occurrences of the same task; the latest Working Manifest is checked again before that call. The Plan records an ordered per-item result and proceeds without item identities, dependencies, conditions, retries, result mappings, state inheritance, or failure policies. Completing traversal is distinct from every task succeeding; invalid configuration, cancellation, a process failure, or an inability to continue scheduling interrupts the Plan.
_Avoid_: Workflow, Task Workflow

**Top-level Execution**:
One application-service-started execution boundary: a formal Task Workflow, Subworkflow, or Step selected by stable logical name, or one Automation Plan and all of its sequential Task Workflows. Direct Subworkflow and Step entry supports development without creating another run kind; the selected Component keeps its normal role and return contract. The boundary owns exactly one Working Manifest and at most one Candidate File Batch from start through final review or disposal.
_Avoid_: Nested Component call, debug-only executor

**Runtime Exception Handling**:
An optional Agent capability that responds when an existing supported Task Workflow remains paused at an unrecovered Step anomaly. It may request a formal Step recheck, propose changes to Steps, Task Workflows, or Subworkflows in one complete Manifest, or recommend Safe Task Termination. The current Step remains the only continuation point; the Agent does not modify Trusted Actions, Recovery Rules, or Assets in this scope.
_Avoid_: Intelligent recovery, fallback workflow

**Agent Turn**:
One Context Builder and Agent Adapter exchange within a Runtime Agent Session. It records the supplied context and one immutable response for executor handling. A model request consumes the Turn when dispatched, including an invalid response or provider error; later source revision requires another Turn.
_Avoid_: Trusted Action call, Workflow Step

**Runtime Agent Session**:
A sequence of at most `max_turns` Agent Turns started only by an Execution Anomaly caught while an existing supported Task Workflow remains paused inside an `@step` wrapper. Provider, model, System Prompt version, generation parameters, and Agent Adapter version are fixed when the Session starts; there is no within-Session switching or fallback. It succeeds only when the executor obtains a contract-compatible normal return from a fresh formal invocation of the current Step, which resumes the caller without deciding Task Workflow success. A later Step anomaly creates a new Session with a new Turn budget while sharing the Top-level Execution's Working Manifest and Candidate File Batch. An anomaly outside a Step never starts this Session. There is no separate Session deadline, action budget, candidate budget, or plan timeout.
_Avoid_: Independent drafting session, Deterministic Recovery

**Request Step Recheck**:
A Runtime Agent Session request for the executor to re-observe, resolve the interrupted Step through the latest Working Manifest, check compatibility and condition, and invoke it fresh. It is neither an Agent success claim nor permission to replace an entered Python frame.
_Avoid_: Retry command, Workflow resume result

**Execution Anomaly**:
A mismatch, ambiguity, failed expectation, propagated leaf-boundary timeout, observed lack of progress, or execution-contract violation for which the deterministic executor can find no remaining legal path that continues the task. A Trusted Action access violation produces this directly without public Deterministic Recovery. It is the only condition that can trigger Runtime Exception Handling.
_Avoid_: Agent opportunity, normal uncertainty

**Safe Task Termination**:
An executor-performed action that stops only the current Task Workflow and its remaining input while leaving the application, Target Window, and containing Automation Plan running. The Task Workflow's final result is still `failure`; the record separately states that safe termination was performed. It preserves failure evidence and pending changes, and a containing Automation Plan may proceed to its next independent task.
_Avoid_: Application exit, game shutdown, system shutdown

**Cancellation**:
An executor control signal rather than a Component exception. It stops new Trusted Actions and Agent Turns and wakes cooperative pause without closing the main application or Target Window. It interrupts a containing Automation Plan with `reason: user_cancelled` without invoking Deterministic Recovery or Agent. If a Task Workflow run record already exists, that record becomes `failure` with `failure_code: user_cancelled`; otherwise no Task result is created. `safe_termination_performed` reports only whether the executor actually performed that action. Exact cancellation position remains in Trace, and formal source cannot catch or clear the signal.
_Avoid_: Execution Interruption, Execution Anomaly

**Run Result**:
The public application-service completion record for one directly started formal Component. It identifies the entry logical name, Component ID, and role and has `status: success | failure`. Success exposes the Component's normalized normal return as `output`; failure omits `output` and instead carries the executor-owned `failure_code` and `failure_message`. Execution Trace remains separate factual evidence rather than the result-reading API.
_Avoid_: Execution Trace, raw Python return, Agent result

**Start Error**:
The structured synchronous exception raised when an application-service start request cannot legally establish a Run, such as while another Run is active, without a valid selected Component Manifest, for an unresolved or ineligible entry, or with inputs that cannot bind and normalize. It carries a stable `code` and readable `message`; because no Run exists, it allocates no Run ID, emits no Trace, and leaves public run state unchanged.
_Avoid_: Failed Run Result, execution exception, condition failure

**Task Workflow Result**:
The final business result of one considered Task Workflow call after Automation Plan preflight or direct launch: `success` or `failure`. Every considered task that does not complete successfully is `failure`, including one whose `execute()` is not entered because its condition fails or its current Working Manifest binding is incompatible. An executor-owned stable machine-readable `failure_code`, a user-facing `failure_message`, Agent involvement, recovery facts, and whether Safe Task Termination occurred explain how it failed. Components and the Agent supply facts and evidence but cannot choose the final code. Failure location and process remain in Execution Trace rather than a duplicated `failure_stage`. `incomplete` may exist only while the invocation is still open and is not a final result. Initial Automation Plan preflight failure creates no Task Workflow result.
_Avoid_: Automation Plan status, Safe Task Termination, not executed

**Subworkflow Result**:
The Ledger result of one entered Subworkflow call: `success` when it returns normally and `failure` when it exits without a normal return. It has no verifier. Its failure code is executor-owned, while Agent and recovery facts remain separate. Safe Task Termination is recorded once on the owning Task Workflow rather than duplicated on every active Subworkflow.
_Avoid_: Task Workflow final verification, Safe Task Termination count

**Controlled Evolution**:
The human-governed process that turns evidence from Runtime Exception Handling into a structurally validated candidate change and, only after explicit permanent approval, registers it as a reusable system capability. Trial results are review evidence rather than an automatic approval gate.
_Avoid_: Self-modification, automatic evolution

**Capability Expansion**:
A deferred activity in which an Agent explores and constructs support for a previously unsupported objective. Stage 3 may change existing Steps, Task Workflows, and Subworkflows to repair a supported task, but does not draft a new user-startable objective or continue execution across an unwound Workflow frame.
_Avoid_: Runtime Step Recovery, Step Maintenance

Permanent approval is a supervised judgment over one complete Capability Proposal and its recorded evidence. Stage 3 does not encode a universal business-success threshold for that judgment: whether the candidate completed a successful formal trial, Step results, Task Workflow verifier results, Trace, and Validation Coverage are visible evidence, not automatic approval gates or authority. Unattended execution never grants permanent approval.

**Supervised Operation**:
A first-version runtime rule in which every Agent-proposed complete Manifest update requires review and an explicit approve-or-reject decision before its changed Components execute in the current Top-level Execution. Rejection requires user feedback for the next Agent Turn. Approval permits the selected Manifest to run for this execution; it is separate from permanent approval after the execution ends. The system-level stop remains an independent immediate cancellation control.

Changed Steps and Workflows use the ordinary Component execution path and their existing Trusted Action access matrix after runtime confirmation. The first version introduces neither a separate high-risk action taxonomy nor per-action confirmation; safety instead relies on no direct Agent action channel, immutable pre-registered Trusted Actions, complete proposal review, and system-level cancellation.

**Supervised Review Dialog**:
The topmost modal decision boundary for one structurally valid runtime proposal. It blocks all main-window interaction until the supervisor approves one formal trial, rejects with required feedback for a later Agent Turn, or confirms cancellation of the Agent and current Task Workflow; it cannot be dismissed through the window close action or Escape key.
_Avoid_: Editor, notification, permanent approval

The Stage 3 Agent Runtime Step Recovery and Maintenance architecture is accepted. Context field selection, serialization, concrete validators, UI behavior, persistence mechanics, and Demo acceptance are implementation and experiment-planning concerns rather than unresolved architecture decisions.
_Avoid_: Developer mode, manual mode

**Capability Proposal**:
A reviewable post-execution choice of the execution's current Working Manifest when its ID has not already received permanent approval. Earlier attempted Manifests remain saved by ID as history but are not separate approval candidates. Ending on the Base Manifest or another already approved ID skips repeated approval. Otherwise the review shows the Task Workflow's final verification result, including failure reasons, trial evidence, and changes from the Base Manifest. A failed verification does not prevent the user from permanently approving that Working Manifest ID; approval is whole-Manifest.
_Avoid_: File change, patch

**Capability Approval Dialog**:
The topmost modal post-execution decision boundary for one complete Capability Proposal. Approval permanently publishes its retained Manifest ID without changing the Default Manifest; rejection grants no permanent approval, while both outcomes retain the execution, trial, Agent, and review evidence. Selecting the approved Manifest as the Default Manifest is a separate explicit action.
_Avoid_: Supervised Review Dialog, partial approval, runtime confirmation

**Component**:
An immutable Python Task Workflow, Subworkflow, Step, Recovery Rule, or Trusted Action that a Component Manifest may reference. Its Component ID is `sha256:` followed by the SHA-256 of its exact source bytes, with no separate source-hash field. Formal Task Workflow, Subworkflow, Step, condition, verifier, Recovery Rule, and their private source functions contain no `except`; they may use `try/finally` for cleanup, but a `finally` suite contains no `return`, `break`, `continue`, or `raise` that could suppress or replace the active exception. Trusted Actions are the only Components allowed to normalize caught low-level exceptions. Editing changes the Component ID rather than changing existing content.
_Avoid_: Component Revision, mutable component

**Component Logical Name**:
The stable dotted lookup key used by a Manifest, such as `steps.enter_stage`, to map one logical capability slot to one immutable Component ID. It is not a version object or a field embedded in Component source. Different retained Manifest IDs may point the same name to different Component IDs without a per-Component version chain.
_Avoid_: Component ID, version chain

**Component Manifest**:
The sole saved version unit: an immutable, validated complete document identified by a UUID whose executable mappings resolve stable logical names to exact Component IDs, while its Asset mapping resolves semantic names and languages to shared files and hashes. Every Manifest used for an execution attempt is saved by Manifest ID; reusing that Manifest records another attempt in Trace under the same ID. Any saved Manifest, including an intermediate attempt, may be explicitly selected for a later execution regardless of its permanent approval status. Intermediate attempts are not separately offered for post-execution approval; the current Working Manifest is offered only when its ID has not already received permanent approval. Choosing whether to set an approved current Working Manifest as Default is a separate decision.
_Avoid_: Approval history, mutable component list

**Default Manifest**:
The one saved Component Manifest selected for a new Top-level Execution when its start request does not explicitly name another saved Manifest ID. Any saved Manifest ID may be set as Default; choosing one without permanent approval first shows a warning and requires explicit confirmation. Changing it affects only later Runs and neither creates a Manifest nor changes an existing Run's Base or Working Manifest.
_Avoid_: Active Manifest, current Run Manifest

**Base Manifest**:
The saved Component Manifest selected when one Top-level Execution starts, either explicitly by Manifest ID or through the Default Manifest. It is the immutable source from which that Run's Working Manifest is created and remains the comparison base even if the Default Manifest later changes.
_Avoid_: Default Manifest, Working Manifest

**Working Manifest**:
A durable, complete Manifest selected for one Top-level Execution from its Base Manifest or a later validated candidate. A directly started Task Workflow, Subworkflow, or Step owns one execution's selection, and all sequential Task Workflows in an Automation Plan share it. Every complete Manifest used for an attempt is retained with a Manifest ID; a later attempt may be based on any retained attempt. The executor atomically selects the whole candidate only when it can immediately make a legal fresh call of the paused current Step; entered Python frames are never patched. A compatible return commits the whole selection, while a failed trial pauses for the next decision without automatic rollback. A later Step interruption starts recovery at that Step without rolling back an earlier committed selection.
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
