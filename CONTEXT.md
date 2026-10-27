# LALC

LALC automates a Windows-native Unity game window during an exclusive focused automation session.

## Language

**Target Window**:
The unique existing Windows desktop window of Limbus Company that LALC selects to observe and operate. No window is selected when discovery finds zero or multiple matching windows.
_Avoid_: Emulator, virtual device

**Focused Automation Session**:
The supported interaction mode in which the Target Window remains restored and owns Windows foreground focus while automation is acting. Physical user takeover suspends automation until the user explicitly resumes it.
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
The collective name for Python-first Task Workflows and Subworkflows. Each has a module docstring, a typed execute entrypoint, and verified immutable source; normal Python calls through Steps provide business behavior and recovery.
_Avoid_: Global node pool, workflow component

**Task Workflow**:
A user-startable root Workflow marked by `@task_workflow`. It organizes Subworkflows and Steps, maintains completion data in ordinary local values, and returns a JSON-compatible result. Entry checks and verification are ordinary Step responsibilities, not separate Task callbacks. A normal contract-valid return records success.
_Avoid_: Root node, top-level Subworkflow

**Subworkflow**:
A reusable Workflow whose `execute` entrypoint is marked by plain `@sub_workflow`. It combines Steps to complete one local responsibility and returns its result without deciding the whole task's final outcome. A Subworkflow cannot call another Subworkflow. It is not a recovery boundary.
_Avoid_: Task Workflow, shared node

**Step**:
The smallest independently observable and recoverable Python execution boundary, marked by plain `@step`. It must safely continue from any observable actionable, expected transitional, or completed state within its responsibility, without relying on lost state from an earlier invocation; unknown or stalled states produce an Execution Failure.
_Avoid_: Every low-level action, YAML node

**Deterministic Recovery**:
Executor-controlled handling inside an interrupted `@step` wrapper: inspect public Recovery Rules, run one uniquely matching recovery when available, then resolve the current Step through the latest Working Manifest and invoke it again. Failure produces an Execution Anomaly. It never restarts a Subworkflow or Task Workflow.
_Avoid_: Agent recovery, implicit error jump

**Recovery Rule**:
A formal immutable Python Component that identifies one cross-Workflow external interruption through a read-only `detect(ctx) -> bool` entrypoint and handles it through a `recover(ctx) -> None` entrypoint. It has a stable logical name and Component ID but no role decorator; neither entrypoint invokes another formal Component.
_Avoid_: Error node, task-specific branch, global exception plugin

**Trusted Action**:
A shipped or human-approved low-level Python operation registered by the application once as `observe` or `control` and shared by all Manifests. Formal source calls its literal logical name through `ctx.action()` under the executor's fixed permission matrix, validation, timing, and Trace; the Agent cannot create, replace, or reclassify it, and a Manifest does not select its implementation.
_Avoid_: Step, Agent-generated function, unrestricted Python call

**Asset**:
A stable semantic resource name identifying a group of template images in the shared Asset Library, independent of a Component Manifest. Images have complete content hashes and optional descriptive tags; language is an ordinary optional tag. It is not a Component and has no Component ID, language or file extension in its logical name.
_Avoid_: Asset Component, image version, absolute resource path

**Asset Library**:
The shared collection of template images grouped by Asset logical name, with optional hash-to-tag metadata for each group. Every image in a group is a matching candidate; absent metadata means an empty tag list, not an unavailable image. Optional priority tags select a preferred group by any-tag overlap; a match in that group excludes the remaining templates, otherwise all remaining templates are considered. Changes become visible to the next matching invocation, including within the same Run, without publishing or selecting a Manifest.
_Avoid_: Manifest attachment, staging library

**Asset Usage Index**:
Mutable local Asset metadata summarizing the latest non-empty detection results, actual template identities and evidence references for developer and Agent inspection, independently of the Manifest and execution logs, without determining future search regions.
_Avoid_: Component Usage Index, Asset Manifest

**Developer Candidate**:
The one editable complete Manifest draft in a project checkout, explicitly initialized or rebuilt by the developer for validation and publication. Repair and conversation changes preserve the current draft; the Agent may edit its existing Python Automation Plan and other authorized files and register new Component or Recovery Rule source through dedicated additions, while formal source remains immutable. Runtime proposals share the Manifest format and validation rules but use separate runtime storage.
_Avoid_: Partial Manifest, global candidate registry

**Agent-assisted Component Repair**:
A developer-initiated conversation that develops and repairs a Developer Candidate under Developer Policy, using the developer’s objective, game observations and retained execution evidence. It may edit the Candidate Automation Plan, but does not take over a paused runtime caller or edit shared GUI settings pages.
_Avoid_: Runtime Agent Session, automatic recovery, Capability Expansion

**Developer Policy**:
The Agent's authority to iteratively develop a Developer Candidate, validate and publish immutable versions, run explicitly selected saved versions, and inspect their actual results within one developer-authorized conversation round. Publication is separate from runtime permanent approval and Default selection.
_Avoid_: Runtime Policy, runtime recovery

**Asset Crop Preview**:
A retained observation tying a proposed Asset name, tags and crop region to exact original game pixels, with visual aids and same-image matching evidence. Saving that preview creates or reuses the corresponding Asset without observing the game again; a preview alone is not an active Asset.
_Avoid_: Candidate Asset Store, confirmed game-state detector

**Removed Asset Archive**:
A retained record of an explicitly removed Asset image, its original logical name, hash and tags, the reason and time, and the original game screenshot observed at removal. It preserves recovery evidence while the removed image and its tag relation no longer participate in the active Asset Library.
_Avoid_: Permanent deletion, Discard Index, separate Asset Library

**Developer Trial**:
An independent Top-level Execution of an explicitly selected saved Manifest and entry, undertaken to test a developer change and return actual evidence to the developing Agent. It does not resume a paused runtime caller or prove the developer's full objective has been completed.
_Avoid_: Runtime Step Recheck, Candidate execution

**Runtime Policy**:
The Agent's runtime maintenance responsibility governed by Stage 6 (formerly Stage 3.5), distinct from developer-directed iterative development. Its paused-caller recovery and supervision contracts do not follow from Developer Trial permission.
_Avoid_: Developer Policy

**Capability Bundle**:
The transport-neutral software-release data package containing one complete retained Component Manifest, immutable Component source and the Asset metadata and images needed by the distributed capabilities. It carries no Default Manifest selection and is distributed as a whole rather than as individual Component updates.
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
The retained record of information supplied to an Agent, its tool operations and results, and its outputs. A continuous developer conversation groups its user messages and model/tool exchanges into one record with per-round outcomes; runtime Agent Turns are referenced by Execution Trace when the executor acts on a response.
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
A normal Python return from a formal Component after its own contract has been satisfied. Returned data keeps distinct values associated with descriptive names or keys; a Task Workflow returns directly JSON-compatible data, with meaningful outcome checks recommended in ordinary Steps before normal return.
_Avoid_: Execution Failure, Outcome routing table

**Execution Failure**:
A non-user error that makes the current task impossible or inappropriate to continue. It retains its original diagnostic evidence; its handling depends on the owning execution boundary rather than a chain of exception categories.
_Avoid_: User Interruption, normal negative detection

**User Interruption**:
A user-originated request to pause, take over, or cancel automation. Pause and takeover may resume explicitly, while cancellation ends execution; neither is a task execution error.
_Avoid_: Execution Failure, automatic recovery

**Automation Plan**:
The unique immutable Python orchestration Component owned by a Component Manifest, distinct from a Task Workflow. It calls Task Workflows using configured repetition counts and settings; ordinary Task failures are recorded and may be followed by further calls, while cancellation, an unrecoverable environment failure or a Plan error ends the execution.
_Avoid_: JSON task list, arbitrary script path, Task Workflow

**Top-level Execution**:
One application-service-started execution of a Manifest’s unique Automation Plan or a directly selected Task Workflow, Subworkflow, or Step. It owns one Working Manifest and retains actual calls, results and attempted versions; a Plan’s traversal completion is distinct from every Task succeeding.
_Avoid_: Nested Component call, debug-only executor

**Runtime Exception Handling**:
An optional Agent capability that responds when an existing supported Task Workflow remains paused at an unrecovered Step anomaly. It may request a formal Step recheck, propose changes to Steps, Task Workflows, or Subworkflows in one complete Manifest, or recommend Safe Task Termination. It may also propose new template Assets cropped from a fresh Target Window screenshot taken for that crop request. The current Step remains the only continuation point; the Agent does not modify existing Asset files, Trusted Actions, or Recovery Rules.
_Avoid_: Intelligent recovery, fallback workflow

**Agent Turn**:
One Context Builder and Agent Adapter exchange within a Runtime Agent Session. It records the supplied context and one immutable response for executor handling. A model request consumes the Turn when dispatched, including an invalid response or provider error; later source revision requires another Turn.
_Avoid_: Trusted Action call, Workflow Step

**Runtime Agent Session**:
A sequence of at most `max_turns` Agent Turns started only by an Execution Anomaly caught while an existing supported Task Workflow remains paused inside an `@step` wrapper. Provider, model, System Prompt version, generation parameters, and Agent Adapter version are fixed when the Session starts; there is no within-Session switching or fallback. It succeeds only when the executor obtains a contract-compatible normal return from a fresh formal invocation of the current Step, which resumes the caller without deciding Task Workflow success. A later Step anomaly creates a new Session with a new Turn budget while sharing the Top-level Execution's Working Manifest. An anomaly outside a Step never starts this Session. There is no separate Session deadline, action budget, candidate budget, or plan timeout.
_Avoid_: Independent drafting session, Deterministic Recovery

**Request Step Recheck**:
A Runtime Agent Session request for the executor to re-observe, resolve the interrupted Step through the latest Working Manifest, check compatibility and condition, and invoke it fresh. It is neither an Agent success claim nor permission to replace an entered Python frame.
_Avoid_: Retry command, Workflow resume result

**Execution Anomaly**:
A mismatch, ambiguity, failed expectation, observed lack of progress, or execution-contract violation for which the deterministic executor can find no remaining legal path that continues the task. A Step-local Trusted Action access violation follows the same recovery boundary as other Execution Failures; recovery never grants a forbidden operation. It is the only condition that can trigger Runtime Exception Handling.
_Avoid_: Agent opportunity, normal uncertainty

**Safe Task Termination**:
An executor-performed action that stops only the current Task Workflow and its remaining input while leaving the application, Target Window, and containing Automation Plan running. The Task Workflow's final result is still `failure`; the record separately states that safe termination was performed. It preserves failure evidence and pending changes, and a containing Automation Plan may proceed to its next independent task.
_Avoid_: Application exit, game shutdown, system shutdown

**Cancellation**:
A User Interruption that ends execution rather than reporting a Component failure. It stops new Trusted Actions and Agent Turns and wakes cooperative pause without closing the main application or Target Window. It interrupts a containing Automation Plan with `reason: user_cancelled` without invoking Deterministic Recovery or Agent. If a Task Workflow run record already exists, that record becomes `failure` with `failure_code: user_cancelled`; otherwise no Task result is created. `safe_termination_performed` reports only whether the executor actually performed that action. Exact cancellation position remains in Trace, and formal source cannot catch or clear the signal.
_Avoid_: Execution Failure, Execution Anomaly

**Run Result**:
The public application-service completion record for one directly started formal Component. It identifies the entry logical name, Component ID, and role and has `status: success | failure`. Success exposes the Component's normalized normal return as `output`; failure omits `output` and instead carries the originating `failure_code` and `failure_message` with their meaning preserved. Execution Trace remains separate factual evidence rather than the result-reading API.
_Avoid_: Execution Trace, raw Python return, Agent result

**Start Error**:
The structured synchronous exception raised when an application-service start request cannot legally establish a Run, such as while another Run is active, without a valid selected Component Manifest, for an unresolved or ineligible entry, or with inputs that cannot bind and normalize. It carries a stable `code` and readable `message`; because no Run exists, it allocates no Run ID, emits no Trace, and leaves public run state unchanged.
_Avoid_: Failed Run Result, execution exception, condition failure

**Task Workflow Result**:
The final business result of one considered Task Workflow call within an Automation Plan or direct launch: `success` or `failure`. Every considered task that does not complete successfully is `failure`, including one whose `execute()` is not entered because its condition fails or its current Working Manifest binding is incompatible. A stable machine-readable `failure_code` propagated from its source, a user-facing `failure_message`, Agent involvement, recovery facts, and whether Safe Task Termination occurred explain how it failed. Errors pass upward without intermediate layers changing their meaning; diagnostics retain the original cause and traceback. Failure location and process remain in Execution Trace rather than a duplicated `failure_stage`. `incomplete` may exist only while the invocation is still open and is not a final result. A rejected Plan start or a Plan failure before any Task is considered creates no Task Workflow result.
_Avoid_: Automation Plan status, Safe Task Termination, not executed

**Subworkflow Result**:
The Ledger result of one entered Subworkflow call: `success` when it returns normally and `failure` when it exits without a normal return. It has no verifier. Its failure code preserves the originating error meaning, while Agent and recovery facts remain separate. Safe Task Termination is recorded once on the owning Task Workflow rather than duplicated on every active Subworkflow.
_Avoid_: Task Workflow callback verification, Safe Task Termination count

**Controlled Evolution**:
The human-governed process that turns evidence from Runtime Exception Handling into a structurally validated candidate change and, only after explicit permanent approval, registers it as a reusable system capability. Trial results are review evidence rather than an automatic approval gate.
_Avoid_: Self-modification, automatic evolution

**Capability Expansion**:
A deferred activity in which an Agent explores and constructs support for a previously unsupported objective. Runtime repair may change existing Steps, Task Workflows, and Subworkflows to repair a supported task, but does not draft a new user-startable objective or continue execution across an unwound Workflow frame.
_Avoid_: Runtime Step Recovery, Step Maintenance

Permanent approval is a supervised judgment over one complete Capability Proposal and its recorded evidence. Runtime approval does not encode a universal business-success threshold for that judgment: whether the candidate completed a successful formal trial, Step results, Task Workflow results and checking-Step evidence, Trace, and Validation Coverage are visible evidence, not automatic approval gates or authority. Unattended execution never grants permanent approval.

**Supervised Operation**:
A first-version runtime rule in which every Agent-proposed complete Manifest update requires review and an explicit approve-or-reject decision before its changed Components execute in the current Top-level Execution. Rejection requires user feedback for the next Agent Turn. Approval permits the selected Manifest to run for this execution; it is separate from permanent approval after the execution ends. The system-level stop remains an independent immediate cancellation control.

Changed Steps and Workflows use the ordinary Component execution path and their existing Trusted Action access matrix after runtime confirmation. The first version introduces neither a separate high-risk action taxonomy nor per-action confirmation; safety instead relies on no direct Agent action channel, immutable pre-registered Trusted Actions, complete proposal review, and system-level cancellation.

**Supervised Review Dialog**:
The topmost modal decision boundary for one structurally valid runtime proposal. It blocks all main-window interaction until the supervisor approves one formal trial, rejects with required feedback for a later Agent Turn, or confirms cancellation of the Agent and current Task Workflow; it cannot be dismissed through the window close action or Escape key.
_Avoid_: Editor, notification, permanent approval

**Capability Proposal**:
A reviewable post-execution choice of the execution's current Working Manifest when its ID has not already received permanent approval. Earlier attempted Manifests remain saved by ID as history but are not separate approval candidates. Ending on the Base Manifest or another already approved ID skips repeated approval. Otherwise the review shows the Task Workflow's final result and checking-Step evidence, including failure reasons, trial evidence, and changes from the Base Manifest. A failed verification does not prevent the user from permanently approving that Working Manifest ID; approval is whole-Manifest.
_Avoid_: File change, patch

**Capability Approval Dialog**:
The topmost modal post-execution decision boundary for one complete Capability Proposal. Approval permanently publishes its retained Manifest ID without changing the Default Manifest; rejection grants no permanent approval, while both outcomes retain the Manifests, Component source, Assets, execution, trial, Agent, and review evidence without triggering resource deletion. Selecting the approved Manifest as the Default Manifest is a separate explicit action.
_Avoid_: Supervised Review Dialog, partial approval, runtime confirmation

**Component**:
An immutable Python Automation Plan, Task Workflow, Subworkflow, Step, or Recovery Rule referenced by a Component Manifest. Its identity is the hash of its exact source; application-registered Trusted Actions and shared GUI settings pages are not Manifest source Components.
_Avoid_: Component Revision, mutable component

**Component Logical Name**:
The stable dotted lookup key used by a Manifest, such as `steps.enter_stage`, to map one logical capability slot to one immutable Component ID. It is not a version object or a field embedded in Component source. Different retained Manifest IDs may point the same name to different Component IDs without a per-Component version chain.
_Avoid_: Component ID, version chain

**Component Manifest**:
The saved version unit for formal Components: a validated complete document protected from Agent modification identified by a UUID whose executable mappings resolve stable logical names to exact Component IDs. Assets are resolved independently through the shared Asset Library, and Trusted Actions are registered by the application. Every Manifest used for an execution attempt is saved by Manifest ID; reusing that Manifest records another attempt in Trace under the same ID. Any saved Manifest, including an intermediate attempt, may be explicitly selected for a later execution regardless of its permanent approval status. Intermediate attempts are not separately offered for post-execution approval; the current Working Manifest is offered only when its ID has not already received permanent approval. Choosing whether to set an approved current Working Manifest as Default is a separate decision.
_Avoid_: Approval history, mutable component list

**Default Manifest**:
The one saved Component Manifest selected for a new Top-level Execution when its start request does not explicitly name another saved Manifest ID. Any saved Manifest ID may be set as Default; explicit selection requires no additional confirmation, regardless of permanent approval status. Changing it affects only later Runs and neither creates a Manifest nor changes an existing Run's Base or Working Manifest.
_Avoid_: Active Manifest, current Run Manifest

**Base Manifest**:
The saved Component Manifest selected when one Top-level Execution starts, either explicitly by Manifest ID or through the Default Manifest. It is the source protected from Agent modification from which that Run's Working Manifest is created and remains the comparison base even if the Default Manifest later changes.
_Avoid_: Default Manifest, Working Manifest

**Working Manifest**:
A durable, complete Manifest selected for one Top-level Execution from its Base Manifest or a later validated candidate. A directly started Task Workflow, Subworkflow, or Step owns one execution's selection, and all sequential Task Workflows in an Automation Plan share it. Every complete Manifest used for an attempt is retained with a Manifest ID; a later attempt may be based on any retained attempt. The executor atomically selects the whole candidate only when it can immediately make a legal fresh call of the paused current Step; entered Python frames are never patched. A compatible return commits the whole selection, while a failed trial pauses for the next decision without automatic rollback. A later Step interruption starts recovery at that Step without rolling back an earlier committed selection.
_Avoid_: Component Manifest, Pending Change Set, manifest diff

**Component Usage Index**:
A possible future housekeeping index, deferred for discussion alongside resource deletion, reference scanning, and cleanup UI. This version defines no data structure, collection rules, or deletion authority for it. It is separate from the accepted Asset Usage Index used by recognition.
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


**User GUI**:
The user-facing application interface for configuring and running the Default Manifest’s unique Automation Plan, distinct from developer-directed repair and trial.
_Avoid_: Developer Runner, independent runtime

**Developer GUI**:
The developer-facing interface for observation, Agent settings and Candidate repair/trial, sharing execution ownership with the User GUI while retaining its own selected Manifest.
_Avoid_: User GUI, concurrent executor

**Workflow Settings Page**:
A shared business-settings page independent of a Manifest that may contribute repetition tasks identified by stable task IDs. The selected Plan explicitly declares supported task IDs; page identity and task identity are distinct from Component logical names.
_Avoid_: Manifest Component, automatic form schema
