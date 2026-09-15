# Stage 1: Product and Agent Boundaries

This document records the product contracts fixed before Workflow 2.0, model integration, UI framework selection, or packaging work begins. Later stages may choose implementations, but must not silently weaken these boundaries.

Stage 1 was explicitly reopened to allow an Agent-generated candidate Step to receive a supervised formal runtime trial before permanent approval. This does not remove human approval for permanent Component registration.

## Product boundary

- LALC automates explicitly supported Limbus Company content; it is not a general game-playing Agent.
- A Deterministic Workflow must complete every officially supported task without a model service.
- The only supported interaction environment is a Focused Automation Session, as established by ADR 0001. Cursor-Assisted Background Operation remains experimental.
- Stage 3 provides supervised Agent Runtime Step Recovery and Maintenance only for the current paused Step and its related Assets. Agent-assisted Workflow Drafting, Task Workflow and Subworkflow maintenance, autonomous Capability Expansion, and unattended candidate trials are deferred. Permanent registration still uses the same validation, approval, Manifest, and recovery boundaries.

## Agent lifecycle

The Agent module is disabled on first installation. The user must configure and verify a local or remote model before enabling it. When disabled, Deterministic Workflows continue normally; an Execution Anomaly terminates the task safely after evidence is saved.

When enabled, the Agent does not participate in normal Workflow steps. Runtime Exception Handling starts only after the deterministic executor has exhausted or ruled out every legal deterministic path that could continue the task and produces an Execution Anomaly, including:

- multiple matches or insufficient recognition confidence;
- failure to reach the expected post-action state;
- lack of progress within the allowed checks;
- contradiction between the observed state and the active Workflow constraints.

Deterministic recovery is confined to an interrupted `@step` wrapper. The wrapper keeps its caller's Python frame paused, checks public Recovery Rules, and then resolves and invokes the current Step again through the latest Working Manifest. A second interruption, an unsatisfied Step `condition`, or an incompatible return produces an Execution Anomaly and may start a Runtime Agent Session only while that wrapper remains paused. An `ExecutionInterruption` outside a Step does not restart a Subworkflow or Task Workflow, never starts a Runtime Agent Session, and proceeds directly to Safe Task Termination. Every Task Workflow supplies one final `verify` function whose exact identity, hash, and original inputs bind when that task starts. It runs only after the Task Workflow normally returns a normalized result and decides success from that result and the original inputs. Agent help must first restore the current Step and ordinary Python return chain; it cannot bypass them with an Agent claim or task-level verification. Once the Task Workflow has returned, an invalid root result or unsuccessful final verification is terminal for that call: the executor records `failure` with `failure_code` and `failure_message` without invoking the Agent or starting the same task again.

## Runtime Agent Turns

Each Runtime Agent Turn returns exactly one of three main results: a Working Manifest Update Proposal, `Request Step Recheck`, or a Safe Task Termination recommendation. The Agent cannot return clicks, keystrokes, scrolling, or another direct-action result. It does not execute a Temporary Action Plan in the first version.

Local and remote models share one Agent Adapter contract. The Adapter only transports a self-contained Context Snapshot, normalizes provider errors, and parses one allowed Turn result. It never invokes Trusted Actions or formal Components, writes candidate files, validates or switches a Working Manifest, or decides recovery success and termination. Provider-native tool calling cannot bypass this boundary.

- Candidate executable behavior must be a compatible replacement of the current paused Step and pass the ordinary Loader contract; an Asset-only proposal keeps the existing Step identity.
- Low-level GUI operations remain pre-registered Trusted Actions used by formal Steps and Recovery Rules.
- Every source edit creates a new immutable Component ID and content hash.
- Each Runtime Agent Session has one finite `max_turns` budget. A dispatched model request consumes one Turn even when the response is invalid or the provider fails; source revision requires another Turn.
- A termination recommendation remains advisory; only the executor performs Safe Task Termination.
- A Runtime Agent Session succeeds only through a contract-compatible normal return from a fresh formal invocation of the current Step. This resumes the paused callers but does not decide Task Workflow success.
- Provider, model, System Prompt version, generation parameters, and Agent Adapter version are fixed for one Runtime Agent Session. Configuration changes apply only to a later Session; the first version has no model switching, routing, or fallback.

Safe Task Termination is an executor action that stops only the current Task Workflow and its remaining inputs. It is recorded separately from the Task Workflow's `failure` result and does not become another result category. It does not exit LALC, close the game, perform system shutdown, or stop a containing Automation Plan. The application preserves the failure reason, screenshots, execution history, and current Working Manifest changes, then offers the user a way to add Expert Guidance. A directly started Task Workflow therefore ends, while an Automation Plan records that task's result and proceeds to its next independent item.

User cancellation is a separate executor control signal, not an exception or Execution Anomaly. It stops further input without Deterministic Recovery or Agent. A containing Automation Plan records `status: interrupted` with `reason: user_cancelled` and starts no later item. If a Task Workflow run record already exists, it records `result: failure` with `failure_code: user_cancelled`; if none exists, cancellation creates no Task result. `safe_termination_performed` reflects only whether the executor actually performed that action, not an inferred execution stage. The exact cancellation position remains in Trace. Formal source cannot catch or clear cancellation. A process crash instead records `process_crash` and cannot claim that Safe Task Termination ran.

## Runtime confirmation

The first version supports only Supervised Operation. The user reviews and confirms the complete Working Manifest Update Proposal, including the candidate Step source and every new Asset and mapping, before the executor selects it for formal trial. The review warns that unapproved generated Component code is not securely sandboxed and may access files, networks, processes, and other system APIs. There is no Unattended Operation or persisted operating-policy choice.

## Runtime permissions

The Runtime Agent may:

- read screenshots, recognition results, execution history, active capability definitions, and relevant Expert Guidance;
- generate one formal candidate replacement of the current paused Step with optional related Asset files and mappings, or propose only Asset files and mappings used by the unchanged current Step.

It may not:

- delete or overwrite an existing Workflow, Asset, or code component;
- register a permanent capability without human approval.

The intended Agent interface remains the project Runtime API and Target Window, but the first-version subprocess and minimal AST checks do not enforce that boundary. Generated Python can technically import modules, access files or networks, start processes, change settings, operate outside the Target Window, or attempt dependency installation. The product must describe this accurately as project-internal dynamic Python execution, not as a secure sandbox. Stronger inspection or operating-system isolation is deferred.

## Agent scope boundary

The Agent starts only from an Execution Anomaly while an existing supported Task Workflow remains paused inside its current Step. It may diagnose that execution and propose a compatible replacement of that Step with optional related Assets, or only Asset files and mappings used by the unchanged current Step. It does not modify the active Task Workflow, any Subworkflow, another Step, or a Recovery Rule; accept an unsupported objective; start an independent drafting run; or create a new user-startable Task Workflow.

## Evidence requirements

Model behavior must be shown as concretely as the action permits. A mouse action includes the current screenshot, marked position or region, coordinates, explanation, expected result, and observed result. Keyboard actions show the target, keys, conditions, and result. Workflow, Asset, and code proposals show their new files, differences, rationale, and available validation evidence.

Runtime API and Step wrappers require and record the evidence needed to show targets and verify results. Because first-version unapproved candidate Python is not sandboxed, this guarantee applies to code using those interfaces and is not claimed for arbitrary bypass code; Supervised review exposes that residual risk before every trial.

## Controlled Evolution

A Capability Proposal contains directly generated formal candidate Components or Asset mappings. It references a complete Working Manifest snapshot and the evidence for its verified contents. The review UI computes differences from the base Manifest; the system does not persist a parallel additions-and-deletions model.

The complete current Working Manifest is persisted as it changes so generated capabilities survive an abnormal application exit. Each change is fully written first and becomes visible through one atomic replacement while the executor is paused; Agent generation never exposes a partially written capability set to executing code. When the executor can immediately arrange a legal formal trial call, it retains the complete pre-switch Working Manifest until that call commits or rolls back the replacement. The rollback copy's presence is the sole uncommitted-switch marker; it is not a historical Working Manifest version. A failed or uncertain rollback is a terminal infrastructure error: no further Agent Turn, Component call, or game input is legal until the pre-switch capability snapshot is restored. The application checks for a reviewable current Working Manifest when it starts and when a complete automation task ends. It remains unapproved regardless of whether generation or validation finished.

A Working Manifest may be saved, inspected, and execution-validated before approval. Validation may combine compatible evidence from multiple real attempts when irreversible game progress prevents a clean replay from the beginning. Human runtime confirmation is required before the current run trials its temporary contents. Permanent approval cannot occur while the Top-level Execution is active; only after it ends may the complete verified Working Manifest become a saved Component Manifest. Each Task Workflow run keeps its Execution Trace, Agent Interaction Logs, screenshots, and other detailed evidence in one Run Log Bundle that the common retention policy preserves or removes as a whole.

Automatic maintenance of Task Workflows, Subworkflows, other Steps, and Recovery Rules is outside the first version. No first occurrence automatically creates a public rule.

Executable code remains eligible for bulk approval. The approval UI must mark it in red with a warning symbol and an **Executable Code** label, state how many code proposals are included in the batch, and allow advanced users to inspect file differences. Approved code loads on the next application start. It may only use dependencies already approved and shipped with the application.

## Immutable components, saved manifests, and working manifests

Neither users nor the Agent mutate registered executable Components in place. Every registered Task Workflow, Subworkflow, Step, Recovery Rule, and Trusted Action has an immutable unique Component ID. Editing an eligible Component adds a new ID instead of overwriting existing content or maintaining a separate per-Component version sequence. Assets are not Components: the Manifest records their semantic names, language mappings, relative shared-library paths, and complete content hashes directly.

Each Manifest is one complete document. Its executable mappings resolve stable dotted logical names such as `steps.enter_stage` to immutable Component IDs and load information; dedicated Recovery Rule and Trusted Action mappings support their loading paths; its Asset mapping contains language-specific shared-file references and hashes. Updating an executable capability changes the ID referenced by its stable name without creating an ID-to-ID version chain. A new capability receives a new logical name. Renaming is represented only by the resulting complete Manifest, not by a persisted rename or additions-and-deletions operation.

Python Components use concise docstrings to help the Agent retrieve and understand their behavior. A behavior change updates the docstring in the same source change; the resulting source has a new content hash and Component ID. The first version adds no tag system, separate component documentation, or vector-retrieval layer.

The Component Manifest is the sole saved, versioned, and recoverable unit. Every Top-level Execution starts by copying the active Manifest into one complete durable Working Manifest. A directly started Task Workflow and an Automation Plan with all of its sequential Task Workflows are the two Top-level Execution forms:

- multiple immutable manifests may exist, but exactly one is active;
- the executor resolves every current-run component through its Working Manifest;
- resolution uses the stable logical name as the lookup key and obtains the currently referenced immutable Component ID;
- every Task Workflow, Subworkflow, and Step inside the same Top-level Execution resolves through the same Working Manifest;
- each Task Workflow still writes its own Run Log Bundle and Workflow Run Ledger records;
- structurally valid Agent logic may be organized directly into new immutable candidate Components and enter the Working Manifest for an immediate formal trial, while new Component source and Asset files follow the shared Candidate File Batch lifecycle without mutating the saved base Manifest;
- an update takes effect only at an executor-controlled pause boundary, after a complete replacement has been durably written and atomically selected;
- already-entered Python frames are never hot-patched; subsequent resolution occurs through a fresh invocation;
- only the current Working Manifest is retained; superseded copies are not long-term versions or Trace dependencies;
- the Working Manifest records the complete current set, not an additions-and-deletions log;
- review differences are computed from the base and Working Manifest snapshots;
- at Top-level Execution end the Working Manifest may be discarded, retained for later review, or approved as one complete new immutable Manifest after all of its candidate mappings have acceptable real evidence;
- the interface lists manifests from newest to oldest and marks the active one;
- approving an Agent proposal creates and activates a new manifest from the reviewed Working Manifest snapshot;
- editing and saving a manifest creates and activates a new manifest, leaving the source manifest unchanged;
- enabling an existing manifest only changes the active selection and does not create a copy;
- only an inactive manifest may be deleted, and the sole remaining manifest cannot be deleted;
- deleting a manifest does not automatically delete its Components;
- any Component referenced by a retained manifest or durable Working Manifest must remain available.

Every retained manifest is a Recovery Point. Recovery selects and activates that manifest directly. The system does not preserve or replay an approval undo chain, maintain per-component version histories, or provide a separate single-component rollback function; a user who wants a different component combination edits a manifest and saves the result as a new manifest.

A separate mutable Component Usage Index records each Component's `last_used_at`. The timestamp changes only when a Workflow or Step is entered or a Trusted Action is invoked. Only a Component with no reference from any retained Manifest or durable Working Manifest may become a cleanup candidate. Elapsed time since actual use may identify and order such candidates but cannot override a live reference.

Assets use a separate local Asset Usage Index keyed by logical name, running language, and full content hash. Accepted old Assets are not cleaned automatically; their usage and Manifest references are shown only for later human review. One Top-level Execution may create at most one durable Candidate File Batch, which records only Component source and Asset files actually created by that execution. Reusing an existing identical file does not add a Batch entry.

The complete current Working Manifest is the first version's sole permanent-approval unit. Runtime confirmation and a successful formal trial affect only the current Top-level Execution and never modify the active Component Manifest. Only after that execution ends may the interface review every changed mapping, source, Asset, and item of Validation Coverage for permanent approval. It does not partially approve files or Components. An unwanted or unsupported mapping must first be removed through another complete validated Working Manifest before approval.

Retaining a Working Manifest for review retains its proposals and complete closed Candidate File Batch without reference-based cleanup. Approval first creates, verifies, persists, and activates the new immutable Component Manifest, then removes only Batch files unreferenced by any retained Component Manifest, durable Working Manifest, or rollback copy. Rejection or discard removes the reviewable Working Manifest and proposals, applies the same global reference check to every Batch entry, and deletes the Batch only after resumable cleanup completes. Historical execution alone never keeps a file; Run Log Bundles preserve that evidence.

The first version permits at most one globally pending reviewable Working Manifest and Candidate File Batch. Before another Agent-enabled Top-level Execution starts, the user must approve or discard them. With Agent maintenance disabled, deterministic execution may continue from the active saved Component Manifest but cannot use the pending Working Manifest or create candidate files. The system never automatically discards, merges, or appends a later execution to the pending Batch.

Cleanup is a user-initiated maintenance operation. The application presents candidates but never deletes them because a time threshold elapsed. Immediately before a requested deletion, it recomputes references from retained Manifests and durable Working Manifests; any current reference rejects the deletion. The Agent, background maintenance, and ordinary update flows cannot delete Components automatically.

## Knowledge Library

The Knowledge Library stores non-executable information for later diagnosis. After Safe Task Termination, the application offers a screenshot-annotation and text interface for the user to explain the correct handling. The resulting Expert Guidance becomes available immediately and includes its applicability context and provenance.

Users can inspect, modify, disable, and delete Expert Guidance. It may influence diagnosis and Capability Proposals, but it cannot execute actions, alter the active manifest, or bypass confirmation and approval boundaries.

## Remote model data

Enabling and configuring a remote model means the user authorizes LALC to send the data required for model calls. There is no separate authorization or per-call confirmation. The application explains this behavior in the model configuration interface.

Transmission remains need-based: a call includes only the screenshots, recognition results, history, and Expert Guidance relevant to the current diagnosis. It must not upload the whole Knowledge Library or unrelated logs.

## Locked outcomes

Python-first Workflow source and warned formal trials of unapproved candidate Python are now fixed boundaries. Later work may choose concrete Runtime API details, runner implementation, model providers, prompts, local model packaging, UI framework, and packaging technology. Changing a fixed boundary requires explicitly reopening Stage 1 and updating the relevant ADR rather than treating the change as an implementation detail.
