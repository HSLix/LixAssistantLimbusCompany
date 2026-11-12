# LALC

LALC automates a Windows-native Unity game window during an exclusive focused automation session.

## Language

**Business Settings Page**:
A user-installed, trusted GUI page that owns configuration under a stable page ID, independently of any Manifest. It may register multiple Loop Tasks or only provide shared settings. A disabled page retains its identity, tasks and configuration while contributing no active task choices.
_Avoid_: Manifest Component, unreviewed generated page, untrusted plugin

**Loop Task**:
A Dashboard repetition choice identified by a stable task ID registered by a Business Settings Page and explicitly supported by an Automation Plan. Its ID is distinct from the page ID and Component logical name; support declares configuration compatibility rather than successful execution.
_Avoid_: Task Workflow, page ID, Component logical name

**Target Window**:
The unique existing Windows desktop window of Limbus Company that LALC selects to observe and operate. No window is selected when discovery finds zero or multiple matching windows.
_Avoid_: Emulator, virtual device

**Focused Automation Session**:
The supported interaction mode in which the Target Window remains restored and owns Windows foreground focus while automation is acting. Physical user takeover suspends automation until the user explicitly resumes it.
_Avoid_: Background operation, headless operation, foreground simulation

**User Activity Wait**:
A temporary yield to physical user activity in another application before automation acquires the Target Window's foreground focus. It continues automatically when focus is available or the required idle interval has elapsed, independently of a manual pause.
_Avoid_: User takeover, manual pause, background operation

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
The collective name for Python-first Task Workflows and Subworkflows. Each has an execute docstring (falling back to a module docstring), a typed execute entrypoint, and verified immutable source; normal Python calls through Steps provide business behavior and recovery.
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
Executor-controlled handling at a failed Plan, Workflow or Step entry: detect applicable Recovery Rules, execute a unique match, then freshly invoke the interrupted entry while retaining its callers. Consecutive successful rule recoveries are bounded and reset on a normal Step return or Agent intervention; user interruptions and unrecoverable environments retain their separate handling.
_Avoid_: Agent recovery, implicit error jump

**Recovery Rule**:
A deterministic rule that identifies one cross-Workflow external interruption through an observe-only detection phase and handles it through a recovery phase; Stage 6 permits both phases to read and mutate Run State. Manifest-defined rules are immutable Python Components with `detect(ctx) -> bool` and `recover(ctx) -> None`, a stable logical name and Component ID but no role decorator; neither entrypoint invokes another formal Component.
_Avoid_: Error node, task-specific branch, global exception plugin

**Built-in Recovery Rule**:
An application-owned Recovery Rule shared by every Manifest. The game-crash rule handles a confirmed exit of the bound game process before business recovery, while preserving the current Step as the only continuation boundary and respecting user takeover.
_Avoid_: Manifest Component, Runtime Agent, automatic task replay

**Trusted Action**:
A shipped or human-approved low-level Python operation registered by the application once as `observe` or `control` and shared by all Manifests. Formal source calls its literal logical name through `ctx.action()` under the executor's fixed permission matrix, validation, timing, and Trace; the Agent cannot create, replace, or reclassify it, and a Manifest does not select its implementation.
Observation includes cooperative waiting without game input; it does not imply an immediate return.
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
The temporary editable staging workspace for a complete Manifest draft, used to prepare, validate and publish changes. It is neither the authoritative source of released capabilities nor the Working Manifest of an active execution; unpublished contents remain drafts.
_Avoid_: Formal source repository, released Manifest, active Working Manifest, global candidate registry

**Agent Workbench**:
The unified developer-directed workspace for constructing, extending and repairing Workflows and their business settings pages using explicitly authorized LALC Agent tools. Each development Session owns its Candidate and a Construct or Repair mode fixed when its first user message is submitted, with mode-specific tool permissions and initial instructions; the workspace remains distinct from Runtime Policy.
_Avoid_: Unrestricted coding agent, Runtime Agent Session, shared global Agent Candidate

**Developer Session**:
A persistent, resumable Agent conversation with its own Candidate, fixed comparison baseline, page drafts where authorized, and a fixed Construct or Repair mode. Stage 6 uses the same Session for runtime Repair initialized from the active Manifest and subsequent developer continuation; the current entry determines tool authority, and retaining the conversation does not retain a live Run. Its display title is initialized from the first user request and remains fixed unless manually renamed; the title does not define its identity. Deleting a Session removes its private conversation and unpublished drafts while preserving independently published or installed capabilities.
_Avoid_: Separate runtime session store, model request, global Candidate

**Manifest Reference Attachment**:
A message-level pointer to one or more published Manifests suggested as reference material, with optional focus described in the message. It is contextual information rather than a read-access grant, a Candidate source selection, or an execution request.
_Avoid_: Manifest access whitelist, Candidate initialization, trial selection

**Developer Skill**:
A reusable set of procedural guidance and read-only reference material for LALC developer work. It grants no authority or independent execution capability; operations remain governed by Developer Policy and the available tools.
_Avoid_: Executable plugin, permission grant, Workflow Component

**External Knowledge Library**:
The collection of reference repositories, documents and images readable by permitted developer Agent modes without permission to edit the reference content. Git reference repositories are replaceable copies of their upstream versions; synchronization may replace their local content, while user-authored material belongs outside those repositories.
_Avoid_: Developer Candidate, editable project source, runtime state

**Page Draft**:
A proposed complete Business Settings Page created from scratch or copied from an existing page for review. It has no effect on the installed page until a developer approves the previewed version for installation.
_Avoid_: Manifest Component, installed page, preview configuration

**Page Package**:
The source and page-owned resources that together form one complete distributable Business Settings Page version. Its resources are part of the reviewed and replaced version; private user settings remain separate.
_Avoid_: Manifest Component, installed configuration, shared Asset Library

**Page Preview**:
A human comparison of the current installed Business Settings Page, when present, and one proposed Page Package version, each using independent disposable configuration. Approval applies only to the previewed package version and does not adopt trial configuration.
_Avoid_: Workflow trial, formal page installation, business acceptance

**Human Intervention Request**:
An Agent request for information or a human operation needed to continue the current development round. The reply reports an answer or actual operation outcome rather than proving the target state, and skipping grants no authorization or completion claim.
_Avoid_: Runtime approval, automatic authorization, page installation approval

**Agent-assisted Component Repair**:
The developer-initiated repair capability for Workflows and Assets under its bounded tool and edit permissions, provided within the unified Agent Workbench. Sharing its infrastructure with Runtime Policy does not itself grant authority to resume a paused caller.
_Avoid_: Agent Workbench, automatic runtime recovery, unrestricted coding agent

**Developer Policy**:
The Agent's authority to develop a Developer Candidate and page drafts using approved reference material, validate and publish immutable Workflow versions, run explicitly selected saved versions, and inspect results within a developer-authorized round. Page installation requires human review; publication is separate from runtime permanent approval and Default selection.
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
The Agent's runtime maintenance responsibility governed by Stage 6 (formerly Stage 3.5), distinct from developer-directed work. It has no deletion tools or deletion authority and does not inherit Workbench permissions; other repair changes and paused-caller integration remain subject to the Stage 6 contract.
_Avoid_: Developer Policy, full Repair tool set, Workbench tool set

**Sharing Package**:
A distributable selection of complete Workflows, independent Asset groups, Page Packages and external Agent history. Each selected object retains its own identity and import behavior; the package carries no Default selection, active Session authority or permission to execute.
_Avoid_: Capability Bundle, full backup, executable Session archive

**Recovery Ladder**:
The fixed escalation order for an interrupted task: exhaust Deterministic Recovery, optionally invoke the Agent through Runtime Exception Handling, and otherwise perform Safe Task Termination.
_Avoid_: Error handler chain, Agent-first recovery

**Run Context**:
The executor-owned interface between formal Components and one execution environment, including component invocation, Target Window access, language, Manifest resolution, Trace, evidence, cancellation, and non-time execution budgets. Business data flows through explicit parameters, returns, and ordinary Python locals, with Stage 6 introducing explicitly shared Run State; this does not permit arbitrary mutable Context fields or Component module globals, and the Agent never receives the live Context.
_Avoid_: Global runtime state, mutable Workflow

**Run State**:
The mutable runtime configuration and business progress shared within one Top-level Execution; direct business-code mutations are immediately visible and survive a failing call without rollback, while framework-maintained recovery counters are read-only to business code. Business meaning and updates belong to formal code; the state ends with the execution and is not persisted for resumption or inherited by a new execution.
_Avoid_: User settings, Python stack snapshot, persistent checkpoint

**Execution Trace**:
The executor-owned chronological record of what one real execution attempt actually did from its entry position. It records actual components, plans, actions, observations, results, evidence, and interruptions for diagnosis, recovery, Agent context, and audit, but does not carry normal Workflow business data or determine task success.
The live running window is a bounded presentation of this record; removing an entry from that presentation does not remove execution evidence.
_Avoid_: Candidate Workflow, Agent memory, capability snapshot

**Agent Interaction Log**:
The complete reconstructable record of information supplied to an Agent, its tool operations and results, and its outputs. Each continuous developer conversation is an independent, self-contained retention unit with per-round outcomes; compact content references preserve the evidence rather than summarize or alter the model context, while runtime Agent Turns are referenced by Execution Trace when the executor acts on a response.
_Avoid_: Execution Trace, Agent memory

**Game Version Observation**:
A point-in-time observation of the local game's version identifiers associated with one Agent conversation round or independent diagnostic operation. Historical observations remain distinct, so a continuing Session can be associated with multiple observed versions.
_Avoid_: Session version, memory validity verdict, latest game version

**Game Version Group**:
The distinct pair of observed in-game version and Steam Build ID used to locate Agent history. Missing identifiers remain missing; a group with neither identifier is Unknown, and a group's latest observation does not update other groups associated with the same Session.
_Avoid_: Game version alone, Steam build alone, history validity

**Agent History Index**:
A rebuildable directory of Agent conversations and rounds associated with recorded Game Version Observations. It locates retained evidence without replacing the self-contained Agent Interaction Log or creating version observations for unobserved history.
_Avoid_: Agent memory, authoritative interaction log, automatic history migration

**Agent Adapter**:
The model-provider transport boundary used by the shared Agent conversation and tool loop. It normalizes provider errors but does not own formal Component execution, Working Manifest selection or recovery outcomes; Runtime hands execution back to the executor through Recheck.
_Avoid_: Separate runtime Agent framework, executor

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
Agent-assisted repair of a failed Plan, Task Workflow, Subworkflow or Step through the shared Repair Session, initialized from the active Manifest. It may edit permitted Candidate content and publish immutable versions for executor-owned Recheck of the failed entry; it grants no independent trial, deletion, direct Run State mutation, Trusted Action modification or arbitrary frame resumption.
_Avoid_: Intelligent recovery, fallback workflow

**Agent Turn**:
One model request and response within an Agent conversation round, consuming request budget when dispatched, including invalid responses or provider failures. A round may contain several requests and tools; Runtime recovery shares a request allowance across its rounds rather than resetting on Recheck feedback.
_Avoid_: Agent conversation round, Trusted Action call, Workflow Step

**Runtime Agent Session**:
The existing Repair Session used from a runtime entry with program-organized fault context and execution feedback, rather than a separate Session implementation. Its recovery rounds share one request budget; after the Run ends the same saved conversation can continue through the Developer GUI without reviving the former Run or its state.
_Avoid_: Recursive Agent session, parallel runtime session store

**Request Step Recheck**:
The historical Step-only name for a Runtime Recheck request. Stage 6 uses Recheck for the currently failed Plan, Workflow or Step entry rather than introducing a separate Step execution mechanism.
_Avoid_: Independent trial, arbitrary entry selection

**Recheck**:
An Agent handoff asking the executor to freshly invoke the current failed entry through the selected immutable Working Manifest, using original call-argument snapshots and current shared Run State after the applicable rule recovery. It returns the actual result to waiting callers once, or ends the Run on a normal top-level Plan return; it is not an Agent success claim.
_Avoid_: Developer Trial, line-level resume, new Run

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
The historical process of registering repaired capabilities through a separate permanent human approval. Stage 6 retires this extra approval gate and uses validated immutable publication and explicit execution/Default selection instead.
_Avoid_: Runtime execution success, page installation approval

**Capability Expansion**:
A deferred activity in which an Agent explores and constructs support for a previously unsupported objective. Runtime repair may change existing Steps, Task Workflows, and Subworkflows to repair a supported task, but does not draft a new user-startable objective or continue execution across an unwound Workflow frame.
_Avoid_: Runtime Step Recovery, Step Maintenance

The historical permanent-approval model is retired in Stage 6; immutable publication, execution selection and Default selection remain distinct.

**Supervised Operation**:
The historical runtime policy requiring human approval of each executable repair proposal before it runs. Stage 6 replaces this gate with validated immutable publication and automatic executor-controlled Recheck; explicit cancellation and other independently required approvals remain.
_Avoid_: Runtime human feedback, page installation approval

**Supervised Review Dialog**:
The historical modal approve-or-reject UI for a runtime repair proposal. It is not a Stage 6 execution gate and is distinct from the retained Developer page-review UI.
_Avoid_: Runtime notification, page preview, human feedback request

**Capability Proposal**:
The historical post-execution proposal of a complete Working Manifest for permanent approval. Stage 6 removes this separate proposal lifecycle; published Manifest versions and their execution evidence remain available.
_Avoid_: Runtime Recheck, published Manifest

**Capability Approval Dialog**:
The historical post-execution permanent-approval dialog, removed from the Stage 6 workflow. This removal does not remove Developer page preview and installation approval.
_Avoid_: Page preview, Default switch notification

**Component**:
An immutable Python Automation Plan, Task Workflow, Subworkflow, Step, or Recovery Rule referenced by a Component Manifest. Its identity is the hash of its exact source; application-registered Trusted Actions and shared GUI settings pages are not Manifest source Components.
_Avoid_: Component Revision, mutable component

**Component Logical Name**:
The stable dotted lookup key used by a Manifest, such as `steps.enter_stage`, to map one logical capability slot to one immutable Component ID. It is not a version object or a field embedded in Component source. Different retained Manifest IDs may point the same name to different Component IDs without a per-Component version chain.
_Avoid_: Component ID, version chain

**Component Manifest** (中文界面：工作流版本):
The saved version unit for formal Components: a validated complete document protected from Agent modification identified by a UUID whose executable mappings resolve stable logical names to exact Component IDs. Assets are resolved independently through the shared Asset Library, and Trusted Actions are registered by the application. Every Manifest used for an execution attempt is saved by Manifest ID; reusing that Manifest records another attempt in Trace under the same ID. Any saved Manifest, including an intermediate attempt, may be explicitly selected for a later execution regardless of its permanent approval status. Publication, selection for the current Run and Default selection are distinct operations; Stage 6 may update Default to the final Working Manifest under its User setting when the Plan completes normally, even if individual Tasks failed; cancellation, Plan interruption and completion failures do not qualify.
_Avoid_: Approval history, mutable component list

**Default Manifest**:
The one saved Component Manifest selected for a new Top-level Execution when its start request does not explicitly name another saved Manifest ID. Any saved Manifest ID may be set as Default; explicit selection requires no additional confirmation, regardless of permanent approval status. Changing it affects only later Runs and neither creates a Manifest nor changes an existing Run's Base or Working Manifest.
_Avoid_: Active Manifest, current Run Manifest

**Base Manifest**:
The saved Component Manifest selected when one Top-level Execution starts, either explicitly by Manifest ID or through the Default Manifest. It is the source protected from Agent modification from which that Run's Working Manifest is created and remains the comparison base even if the Default Manifest later changes.
_Avoid_: Default Manifest, Working Manifest

**Working Manifest**:
The complete saved Manifest currently selected for one Top-level Execution, shared by its sequential tasks and recovery attempts. Selection changes future Component resolutions without replacing entered Python frames; failed attempts retain the selected version and evidence without automatic rollback.
_Avoid_: Default Manifest, mutable Candidate, manifest diff

**Component Usage Index**:
A possible future housekeeping index, deferred for discussion alongside resource deletion, reference scanning, and cleanup UI. This version defines no data structure, collection rules, or deletion authority for it. It is separate from the accepted Asset Usage Index used by recognition.
_Avoid_: Component Manifest, deletion authority

**Recovery Point**:
The interrupted Plan, Workflow or Step invocation whose entry can be freshly called while its callers remain waiting. It identifies a live execution boundary, not a retained Manifest version or a durable process-restart checkpoint.
_Avoid_: Saved Manifest ID, arbitrary source line, persistent checkpoint

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
The developer-facing interface for observation, Agent settings and Session-based development, including Agent-requested trials. It shares execution ownership with the User GUI and provides no separate manual Manifest run entry.
_Avoid_: User GUI, concurrent executor

**Workflow Settings Page**:
A shared business-settings page independent of a Manifest that may contribute repetition tasks identified by stable task IDs. The selected Plan explicitly declares supported task IDs; page identity and task identity are distinct from Component logical names.
_Avoid_: Manifest Component, automatic form schema

**Imported Run Log**:
A read-only copy of one execution Trace and its referenced screenshot evidence from another log package. It preserves the source Run number and event times but has an independent local import identity; it neither consumes a local Run number nor restores execution or grants source authority. Repeated imports remain separate records.
_Avoid_: Local Run, restored Run, Agent Session
