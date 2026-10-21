# Stage 1: Product and Agent Boundaries

This document records the product contracts fixed before Workflow 2.0, model integration, UI framework selection, or packaging work begins. Later stages may choose implementations, but must not silently weaken these boundaries.

Stage 1 was reopened to allow a supervised Agent-proposed complete Manifest to run in the current execution before permanent publication. Runtime permission and permanent approval remain separate.

## Product boundary

- LALC automates explicitly supported Limbus Company content; it is not a general game-playing Agent.
- A Deterministic Workflow must complete every officially supported task without a model service.
- The only supported interaction environment is a Focused Automation Session, as established by ADR 0001. Cursor-Assisted Background Operation remains experimental.
- Stage 3 provides supervised Agent recovery from a paused current Step. One proposal may change Steps, Task Workflows, and Subworkflows together; Trusted Actions and Recovery Rules are outside this Agent modification scope. The Agent may propose new template Assets cropped by the executor from a fresh Target Window screenshot taken for that crop request (ADR 0020); it cannot overwrite, rename, or delete existing Asset files. Agent-assisted drafting of a new objective, autonomous Capability Expansion, and unattended operation remain deferred.

## Agent lifecycle

The Agent module is disabled on first installation. The user must configure and verify a local or remote model before enabling it. When disabled, Deterministic Workflows continue normally; an Execution Anomaly terminates the task safely after evidence is saved.

When enabled, the Agent does not participate in normal Workflow steps. Runtime Exception Handling starts only after the deterministic executor has exhausted or ruled out every legal deterministic path that could continue the task and produces an Execution Anomaly, including:

- multiple matches or insufficient recognition confidence;
- failure to reach the expected post-action state;
- lack of progress within the allowed checks;
- contradiction between the observed state and the active Workflow constraints.

One common invocation mechanism covers Component execute, Step condition, Trusted Actions, and Recovery Rules. Only the whole Step is a recovery boundary: public rules and one fresh invocation may restore its paused caller chain; exhausted recovery may enter Agent handling or explicit termination. Workflow errors outside a Step are reported without replay, and Recovery Rule errors never recursively recover. Task has no entry condition or final verify callback. Business entry and outcome checks are recommended as ordinary Steps. Normal JSON-compatible Task return records success.

## Runtime Agent Turns

Each Runtime Agent Turn returns exactly one of three main results: a Working Manifest Update Proposal, `Request Step Recheck`, or a Safe Task Termination recommendation. The Agent cannot return clicks, keystrokes, scrolling, or another direct-action result. It does not execute a Temporary Action Plan in the first version.

Local and remote models share one Agent Adapter contract. The Adapter only transports a self-contained Context Snapshot, normalizes provider errors, and parses one allowed Turn result. It never invokes Trusted Actions or formal Components, writes candidate files, validates or switches a Working Manifest, or decides recovery success and termination. Provider-native tool calling cannot bypass this boundary.

- Candidate executable behavior may change Steps, Task Workflows, and Subworkflows together; selection requires a compatible fresh call of the paused current Step and complete Manifest validation.
- Low-level GUI operations remain pre-registered Trusted Actions used by formal Steps and Recovery Rules.
- Every source edit creates a new immutable Component ID derived from the exact source bytes.
- Each Runtime Agent Session has one finite `max_turns` budget. A dispatched model request consumes one Turn even when the response is invalid or the provider fails; source revision requires another Turn.
- A termination recommendation remains advisory; only the executor performs Safe Task Termination.
- A Runtime Agent Session succeeds only through a contract-compatible normal return from a fresh formal invocation of the current Step. This resumes the paused callers but does not decide Task Workflow success.
- Provider, model, System Prompt version, generation parameters, and Agent Adapter version are fixed for one Runtime Agent Session. Configuration changes apply only to a later Session; the first version has no model switching, routing, or fallback.

Safe Task Termination is an executor action that stops only the current Task Workflow and its remaining inputs. It is recorded separately from the Task Workflow's `failure` result and does not become another result category. It does not exit LALC, close the game, perform system shutdown, or stop a containing Automation Plan. The application preserves the failure reason, screenshots, execution history, and current Working Manifest changes, then offers the user a way to add Expert Guidance. A directly started Task Workflow therefore ends, while an Automation Plan records that task's result and proceeds to its next independent item.

User pause, takeover, and cancellation are user controls rather than execution failures. An internal `UserInterruption` may unwind an operation when necessary, preserving whether the user requested resumable pause or final cancellation. It stops further input without Deterministic Recovery or Agent. A containing Automation Plan records `status: interrupted` with `reason: user_cancelled` and starts no later item. If a Task Workflow run record already exists, it records `result: failure` with `failure_code: user_cancelled`; if none exists, cancellation creates no Task result. `safe_termination_performed` reflects only whether the executor actually performed that action, not an inferred execution stage. The exact cancellation position remains in Trace. Formal source cannot catch or clear cancellation. A process crash instead records `process_crash` and cannot claim that Safe Task Termination ran.

## Runtime confirmation

The first version supports only Supervised Operation. The user reviews and permits the complete proposed Manifest, including every changed Step and Workflow source, before it executes in the current Top-level Execution. This permission applies to the whole selected Manifest for that execution, including later calls, but does not permanently publish it. Ordinary Component execution is not a security sandbox; there is no Unattended Operation or persisted operating-policy choice.

## Runtime permissions

The Runtime Agent may:

- read screenshots, recognition results, execution history, active capability definitions, and relevant Expert Guidance;
- propose one complete Manifest changing Steps, Task Workflows, or Subworkflows, with reasons for every change; it cannot modify Trusted Actions or Recovery Rules. The Agent may propose new template Assets cropped by the executor from a fresh Target Window screenshot taken for that crop request (ADR 0020); it cannot overwrite, rename, or delete existing Asset files.

It may not:

- delete or overwrite an existing Workflow, Asset, or code component;
- register a permanent capability without human approval.

The intended Agent interface remains the project Runtime API and Target Window, but ordinary Python Component execution and structural validation do not securely confine generated code. Supervised review exposes that residual risk before selecting the complete Manifest. Stronger inspection or operating-system isolation remains deferred.

## Agent scope boundary

The Agent starts only from an Execution Anomaly while an existing supported Task Workflow remains paused inside its current Step. It may diagnose that execution and propose changes to Steps, Task Workflows, and Subworkflows in one complete Manifest. The current Step remains the only continuation point; entered Workflow frames keep their code and locals, and later new calls resolve the selected Manifest. Workflow exceptions outside a Step are reported without cross-Workflow continuation; any Safe Task Termination is an explicitly performed action. The Agent does not modify Trusted Actions or Recovery Rules or create a new user-startable objective in this scope. The Agent may propose new template Assets cropped by the executor from a fresh Target Window screenshot taken for that crop request (ADR 0020); it cannot overwrite, rename, or delete existing Asset files.

## Evidence requirements

Model behavior must be shown as concretely as the action permits. A mouse action includes the current screenshot, marked position or region, coordinates, explanation, expected result, and observed result. Keyboard actions show the target, keys, conditions, and result. Workflow, Asset, and code proposals show their new files, differences, rationale, and available validation evidence.

Runtime API and Step wrappers record the evidence needed to show targets and verify results. Ordinary Component execution is not a security sandbox; supervised review exposes the residual risk before selecting Agent-proposed code.

## Controlled Evolution

A Capability Proposal presents the execution's current Working Manifest ID when that ID has not already received permanent approval, together with its Task result and checking-Step evidence and trial evidence. Returning to the Base Manifest or another already approved ID skips repeated approval. Earlier intermediate attempts remain in history but are not separate approval candidates. The review UI computes differences from the Base Manifest; the system does not persist a parallel additions-and-deletions model.

Every complete Manifest actually used for an attempt is durably retained by Manifest ID, including the initial and intermediate versions. Trying an existing Manifest ID again reuses that ID while Trace records another attempt. A validated proposal becomes visible through one atomic selection while the executor can immediately invoke the paused current Step. If that call fails, execution remains paused without automatic rollback; the Agent may base another proposal on any retained attempt ID or end execution. No Component call or game input occurs while that decision is pending.

A complete Manifest may be inspected and execution-validated before permanent approval. Validation may combine compatible evidence from multiple real attempts when irreversible game progress prevents replay from the beginning. Human runtime permission is required before the current execution uses Agent-proposed content. Permanent approval occurs only after the Top-level Execution ends; it publishes the reviewed retained Manifest ID without automatically changing the Default Manifest. Each Task Workflow run keeps its Trace, Agent Interaction Logs, screenshots, and other evidence in a Run Log Bundle.

Agent modification of Trusted Actions and Recovery Rules is outside this scope. The Agent may propose new template Assets cropped by the executor from a fresh Target Window screenshot taken for that crop request (ADR 0020); it cannot overwrite, rename, or delete existing Asset files. No first occurrence automatically creates a public Recovery Rule.

Executable code remains eligible for whole-Manifest permanent approval. The approval UI must mark it in red with a warning symbol and an **Executable Code** label, state how many source changes are included, and allow advanced users to inspect file differences. Permanent approval records the reviewed Manifest ID and does not alter the Default selection; any saved Manifest ID may be explicitly selected in a later execution. Code may only use dependencies already approved and shipped with the application.

## Immutable components, saved manifests, and working manifests

Neither users nor the Agent mutate registered executable Components in place. Every registered Task Workflow, Subworkflow, Step, Recovery Rule, and Trusted Action has an immutable unique Component ID. Editing an eligible Component adds a new ID instead of overwriting existing content or maintaining a separate per-Component version sequence. Assets are not Components: the Manifest records their semantic names, language mappings, relative shared-library paths, and complete content hashes directly.

Each Manifest is one complete document. Its executable mappings resolve stable dotted logical names such as `steps.enter_stage` to immutable Component IDs; dedicated Recovery Rule and Trusted Action mappings select their validation rules; its Asset mapping contains language-specific shared-file references and hashes. Updating an executable capability changes the ID referenced by its stable name without creating an ID-to-ID version chain. A new capability receives a new logical name. Renaming is represented only by the resulting complete Manifest, not by a persisted rename or additions-and-deletions operation.

Python Components use concise docstrings to help the Agent retrieve and understand their behavior. A behavior change updates the docstring in the same source change; the resulting source has a new Component ID. The first version adds no tag system, separate component documentation, or vector-retrieval layer.

The Component Manifest is the sole saved, versioned, and recoverable unit. Every Top-level Execution selects one retained Base Manifest, explicitly or through the Default Manifest, and copies it into one complete durable Working Manifest. A directly started Task Workflow, Subworkflow, or Step and an Automation Plan with all of its sequential Task Workflows are the Top-level Execution forms:

- multiple saved Manifests protected from Agent modification may exist, but exactly one is the Default used only when a start request does not name another retained Manifest;
- the executor resolves every current-run component through its Working Manifest;
- resolution uses the stable logical name as the lookup key and obtains the currently referenced immutable Component ID;
- every Task Workflow, Subworkflow, and Step inside the same Top-level Execution resolves through the same Working Manifest;
- each Task Workflow still writes its own Run Log Bundle and Workflow Run Ledger records;
- structurally valid Agent logic may change immutable Steps, Task Workflows, and Subworkflows in a complete Manifest for a fresh current-Step call, while new Component source is stored immutably in the shared library without mutating the Base Manifest;
- an update takes effect only at an executor-controlled pause boundary, after a complete replacement has been durably written and atomically selected;
- already-entered Python frames are never hot-patched; subsequent resolution occurs through a fresh invocation;
- every complete Manifest used for an attempt remains retained by Manifest ID; attempts selecting the same Manifest share that ID but have separate Trace events;
- the Working Manifest records the complete current set, not an additions-and-deletions log;
- review differences are computed from the base and Working Manifest snapshots;
- at Top-level Execution end only the current Working Manifest ID is offered for permanent review when it has not already received permanent approval, even if final Task verification failed; returning to the Base Manifest or another approved ID skips repeated approval, and runtime permission and trial evidence never grant permanent publication automatically;
- the interface lists Manifests from newest to oldest and marks the Default one;
- approving an Agent proposal permanently publishes its retained Manifest ID without selecting it as Default;
- editing and publishing a Manifest creates a new Manifest, leaving the source Manifest and Default selection unchanged;
- selecting an existing Manifest as Default creates no copy;
- retained Manifests and their referenced files remain available; deletion and reference-scanning policies are deferred for future discussion, not first-version requirements.

Every retained Manifest is a Recovery Point. Recovery selects that Manifest as the Default directly. The system does not preserve or replay an approval undo chain, maintain per-component version histories, or provide a separate single-component rollback function; a user who wants a different component combination edits a Manifest and publishes the result as a new Manifest.

Component Usage Index is a possible future maintenance feature, deferred for discussion. This version commits to neither its data structure nor collection or cleanup rules. Asset Usage Index remains a separate accepted recognition requirement.

Assets use a separate local Asset Usage Index keyed by logical name, running language, and full content hash. Its latest successful use and evidence references support inspection and never change detection regions. New Agent-proposed templates may only be cropped from a fresh Target Window screenshot taken for that crop request under ADR 0020. New immutable files go directly into their normal libraries; resource maintenance is deferred under ADR 0021.

One retained complete Manifest ID is the first version's permanent-approval unit. Runtime permission and successful trials affect only the current Top-level Execution. After it ends, the interface reviews the selected Manifest, its changes, and Validation Coverage for a separate whole-Manifest decision. Approval does not duplicate the selected Manifest under another ID or change the Default Manifest.

Post-execution review records human approval or rejection for the reviewed Manifest ID separately from its contents protected from Agent modification. Approval marks the existing ID as permanently approved without changing the Default; rejection grants no approval. Both outcomes retain final and intermediate attempted Manifests, source files, Assets, and evidence. Neither outcome triggers resource deletion. Candidate File Batch tracking is removed; resource maintenance is outside this version (ADR 0021).

The first version retains every attempted complete Manifest by ID. Any saved Manifest ID, including one from an unfinished or unapproved attempt, may be explicitly selected by another Top-level Execution. Permanent approval and Default selection remain distinct from permission for one execution.

Any saved Manifest ID may be set as Default. Explicit selection requires no additional confirmation, regardless of permanent approval status; a validation or load failure leaves the existing Default unchanged. Explicitly selecting a saved ID to start one execution does not change the Default.

A process crash preserves attempted Manifests and flushed execution evidence, but does not automatically reopen a post-execution approval dialog on restart. A saved ID from that execution remains explicitly selectable.

Resource deletion, reference scanning, and cleanup UI are deferred for future discussion under ADR 0021. No deletion eligibility rule, reference index, or maintenance interface is committed for this version.

## Knowledge Library

The Knowledge Library stores non-executable information for later diagnosis. After Safe Task Termination, the application offers a screenshot-annotation and text interface for the user to explain the correct handling. The resulting Expert Guidance becomes available immediately and includes its applicability context and provenance.

Users can inspect, modify, disable, and delete Expert Guidance. It may influence diagnosis and Capability Proposals, but it cannot execute actions, alter a retained or Working Manifest, change the Default Manifest, or bypass confirmation and approval boundaries.

## Remote model data

Enabling and configuring a remote model means the user authorizes LALC to send the data required for model calls. There is no separate authorization or per-call confirmation. The application explains this behavior in the model configuration interface.

Transmission remains need-based: a call includes only the screenshots, recognition results, history, and Expert Guidance relevant to the current diagnosis. It must not upload the whole Knowledge Library or unrelated logs.

## Locked outcomes

Python-first Workflow source and warned formal trials of unapproved candidate Python are now fixed boundaries. Later work may choose concrete Runtime API details, runner implementation, model providers, prompts, local model packaging, UI framework, and packaging technology. Changing a fixed boundary requires explicitly reopening Stage 1 and updating the relevant ADR rather than treating the change as an implementation detail.
