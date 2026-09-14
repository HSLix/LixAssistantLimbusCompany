# Stage 1: Product and Agent Boundaries

This document records the product contracts fixed before Workflow 2.0, model integration, UI framework selection, or packaging work begins. Later stages may choose implementations, but must not silently weaken these boundaries.

Stage 1 was explicitly reopened to allow Agent-generated Python to execute before permanent approval under Supervised or warned Unattended Operation. This does not remove human approval for permanent Component registration.

## Product boundary

- Lix Assistant automates explicitly supported Limbus Company content; it is not a general game-playing Agent.
- A Deterministic Workflow must complete every officially supported task without a model service.
- The only supported interaction environment is a Focused Automation Session, as established by ADR 0001. Cursor-Assisted Background Operation remains experimental.
- Capability Expansion is included in Stage 3 as a separate, user-initiated activity for developing support for previously unsupported objectives. Its temporary execution follows the selected operating policy; permanent registration still uses the same validation, approval, Manifest, and recovery boundaries.

## Agent lifecycle

The Agent module is disabled on first installation. The user must configure and verify a local or remote model before enabling it. When disabled, Deterministic Workflows continue normally; an Execution Anomaly terminates the task safely after evidence is saved.

When enabled, the Agent does not participate in normal Workflow steps. Runtime Exception Handling starts only after the deterministic executor has exhausted or ruled out every legal deterministic path that could continue the task and produces an Execution Anomaly, including:

- no matching Workflow;
- multiple matches or insufficient recognition confidence;
- failure to reach the expected post-action state;
- lack of progress within the allowed checks;
- contradiction between the observed state and the active Workflow constraints.

Deterministic recovery is confined to an interrupted `@step` wrapper. The wrapper keeps its caller's Python frame paused, checks public Recovery Rules, and then resolves and invokes the current Step again through the latest Working Manifest. A second interruption, an unsatisfied Step `condition`, or an incompatible return produces an Execution Anomaly. An `ExecutionInterruption` outside a Step does not restart a Subworkflow or Task Workflow and proceeds directly to the Agent or Safe Task Termination. Every Task Workflow supplies one final `verify` function whose exact identity, hash, and original inputs bind when that task starts. It runs only after the Task Workflow normally returns a normalized result and decides success from that result and the original inputs. A completed Temporary Action Plan must first restore the current Step and ordinary Python return chain; it cannot bypass them with an Agent claim or task-level verification. Once the Task Workflow has returned, an invalid root result or unsuccessful final verification is terminal for that call: the executor records `failure` with `failure_code` and `failure_message` without invoking the Agent or starting the same task again.

## Temporary Action Plans

Runtime Exception Handling may generate a Temporary Action Plan as Python source containing one `execute(ctx)` entrypoint. The plan may use the shipped Runtime API for screenshots, recognition, Target Window input, waits, conditions, validation, and bounded retries. Like formal source, it may contain no `except`; it may use `try/finally`, and every escaping exception is recorded and normalized by its Adapter.

- Step and Runtime API wrappers record applicability, operations, and verification evidence when used.
- A failed expectation stops the remaining steps and returns the incident to diagnosis.
- A new diagnosis creates a new plan; it is not an extension of an earlier authorization.
- Once a plan has been executed, its identity and complete source in the Agent Interaction Log are immutable. Any edit creates a new plan identity.
- Each incident has a finite diagnosis and execution budget. The concrete limit belongs to Workflow 2.0 configuration and evaluation.
- The Agent may recommend Safe Task Termination before the budget is exhausted when completion is no longer reasonable; only the executor performs it.

Safe Task Termination is an executor action that stops only the current Task Workflow and its remaining inputs. It is recorded separately from the Task Workflow's `failure` result and does not become another result category. It does not exit Lix Assistant, close the game, perform system shutdown, or stop a containing Automation Plan. The application preserves the failure reason, screenshots, execution history, and current Working Manifest changes, then offers the user a way to add Expert Guidance. A directly started Task Workflow therefore ends, while an Automation Plan records that task's result and proceeds to its next independent item.

User cancellation is a separate executor control signal, not an exception or Execution Anomaly. It stops further input without Deterministic Recovery or Agent. A containing Automation Plan records `status: interrupted` with `reason: user_cancelled` and starts no later item. If a Task Workflow run record already exists, it records `result: failure` with `failure_code: user_cancelled`; if none exists, cancellation creates no Task result. `safe_termination_performed` reflects only whether the executor actually performed that action, not an inferred execution stage. The exact cancellation position remains in Trace. Formal source cannot catch or clear cancellation. A process crash instead records `process_crash` and cannot claim that Safe Task Termination ran.

## Operating policies

The Agent has two global operating policies, not per-action allowlists:

- **Supervised Operation**: the user reviews and confirms the complete immutable Python source once before it runs. A replacement source receives a new `plan_id` and requires another confirmation.
- **Unattended Operation**: Agent-generated Python runs without source review or confirmation. The interface must warn that the runner subprocess is not a security sandbox and that generated code may access files, networks, processes, and other system APIs.

The Agent module defaults to Supervised Operation when first enabled. A user may switch to Unattended Operation only after acknowledging the warning, and the application persists that choice. While the Agent is enabled, the home page clearly shows and allows changing the current policy and risk status. When it is disabled, the home page reports that state rather than presenting either policy as active.

## Runtime permissions

The Runtime Agent may:

- read screenshots, recognition results, execution history, active capability definitions, and relevant Expert Guidance;
- choose an existing Workflow or invoke a registered trusted action;
- generate and execute Python Temporary Action Plans according to the active operating policy;
- organize verified temporary logic into candidate Workflow, Step, or Recovery Rule Components, add verified Asset files and mappings, and atomically update the current Working Manifest.

It may not:

- delete or overwrite an existing Workflow, Asset, or code component;
- register a permanent capability without human approval.

The intended Agent interface remains the project Runtime API and Target Window, but the first-version subprocess and minimal AST checks do not enforce that boundary. Generated Python can technically import modules, access files or networks, start processes, change settings, operate outside the Target Window, or attempt dependency installation. The product must describe this accurately as project-internal dynamic Python execution, not as a secure sandbox. Stronger inspection or operating-system isolation is deferred.

## Capability Expansion boundary

Capability Expansion starts only from an explicit user goal in its own session. It is not triggered by a formal Task Workflow and is not an extension of Runtime Exception Handling. Temporary execution follows Supervised or Unattended Operation.

Within that session, the Agent follows `reuse → compose → explore`: it first reuses registered Python Workflows and Components, then generates a run-scoped Python Temporary Action Plan when existing capabilities are insufficient. The Adapter executes that plan directly under the selected operating policy. The Agent may collect traces, organize verified logic into candidate Components in the Working Manifest, and generate a Capability Proposal, but it cannot mutate a saved Component Manifest, register a permanent capability, or turn the exploratory session into a formally supported run.

Every discovered capability uses the same durable Working Manifest, validation, human approval, Manifest creation, and activation process as a proposal derived from Runtime Exception Handling.

## Evidence requirements

Model behavior must be shown as concretely as the action permits. A mouse action includes the current screenshot, marked position or region, coordinates, explanation, expected result, and observed result. Keyboard actions show the target, keys, conditions, and result. Workflow, Asset, and code proposals show their new files, differences, rationale, and available validation evidence.

Runtime API and Step wrappers require and record the evidence needed to show targets and verify results. Because first-version Agent Python is not sandboxed, this guarantee applies to code using those interfaces and is not claimed for arbitrary bypass code; Unattended Operation explicitly accepts that residual risk.

## Controlled Evolution

A successful Temporary Action Plan may be assembled into a Capability Proposal. The proposal references a complete Working Manifest snapshot and the evidence for its verified contents. The review UI computes its differences from the base Manifest; the system does not persist a parallel additions-and-deletions model.

The complete current Working Manifest is persisted as it changes so generated capabilities survive an abnormal application exit. Each change is fully written first and becomes visible through one atomic replacement while the executor is paused; Agent generation never exposes a partially written capability set to executing code. The prior file is only a short-lived rollback artifact and is removed after a successful replacement. The system does not retain a W1/W2 history. The application checks for a reviewable current Working Manifest when it starts and when a complete automation task ends. It remains unapproved regardless of whether generation or validation finished.

A Working Manifest may be saved, inspected, and execution-validated before approval. Validation may combine compatible evidence from multiple real attempts when irreversible game progress prevents a clean replay from the beginning. Human approval is always required before its verified contents are saved as a formal Component Manifest, but the current run may execute its temporary contents under the selected Agent operating policy. Each Task Workflow run keeps its Execution Trace, Agent Interaction Logs, screenshots, and other detailed evidence in one Run Log Bundle that the common retention policy preserves or removes as a whole.

Unknown exception handling follows one fixed evolution path. The first successful Temporary Action Plan is incorporated only into a new candidate version of the affected Workflow as an ordinary local Python handling branch, even when the exception appears global. The branch may call Steps or Subworkflows and must use deterministic recognition, actions, and result verification. Failure or an unverifiable result raises `ExecutionInterruption`. If another Workflow later reaches a compatible real occurrence, fails to match existing public Recovery Rules, and invokes the Agent, the Agent may reuse that logic there. Only after it succeeds in the second Workflow does the system create a public Recovery Rule and rebuild the original candidate Workflow to remove the duplicated branch. The second Workflow changes only when its source must otherwise be corrected to expose the failure through the formal execution contract. All required reference changes enter the shared Working Manifest through one atomic replacement.

Executable code remains eligible for bulk approval. The approval UI must mark it in red with a warning symbol and an **Executable Code** label, state how many code proposals are included in the batch, and allow advanced users to inspect file differences. Approved code loads on the next application start. It may only use dependencies already approved and shipped with the application.

## Immutable components, saved manifests, and working manifests

Neither users nor the Agent mutate registered executable Components in place. Every registered Task Workflow, Subworkflow, Step, Recovery Rule, and Trusted Action has an immutable unique Component ID. Editing an eligible Component adds a new ID instead of overwriting existing content or maintaining a separate per-Component version sequence. Assets are not Components: the Manifest records their semantic names, language mappings, relative shared-library paths, and complete content hashes directly.

Each Manifest is one complete document. Its executable mappings resolve stable dotted logical names such as `steps.enter_stage` to immutable Component IDs and load information; dedicated Recovery Rule and Trusted Action mappings support their loading paths; its Asset mapping contains language-specific shared-file references and hashes. Updating an executable capability changes the ID referenced by its stable name without creating an ID-to-ID version chain. A new capability receives a new logical name. Renaming is represented only by the resulting complete Manifest, not by a persisted rename or additions-and-deletions operation.

Python Components use concise docstrings to help the Agent retrieve and understand their behavior. A behavior change updates the docstring in the same source change; the resulting source has a new content hash and Component ID. The first version adds no tag system, separate component documentation, or vector-retrieval layer.

The Component Manifest is the sole saved, versioned, and recoverable unit. Every Top-level Execution starts by copying the active Manifest into one complete durable Working Manifest. A directly started Task Workflow is one Top-level Execution; an Automation Plan and all of its sequential Task Workflows form one Top-level Execution:

- multiple immutable manifests may exist, but exactly one is active;
- the executor resolves every current-run component through its Working Manifest;
- resolution uses the stable logical name as the lookup key and obtains the currently referenced immutable Component ID;
- every Task Workflow, Subworkflow, and Step inside the same Top-level Execution resolves through the same Working Manifest;
- each Task Workflow still writes its own Run Log Bundle and Workflow Run Ledger records;
- verified Agent logic may update the Working Manifest only after being organized into new immutable candidate Components, while verified Asset files and language mappings follow the separate Asset Batch lifecycle, without mutating the saved base Manifest;
- an update takes effect only at an executor-controlled pause boundary, after a complete replacement has been durably written and atomically selected;
- already-entered Python frames are never hot-patched; subsequent resolution occurs through a fresh invocation;
- only the current Working Manifest is retained; superseded copies are not long-term versions or Trace dependencies;
- the Working Manifest records the complete current set, not an additions-and-deletions log;
- review differences are computed from the base and Working Manifest snapshots;
- at Top-level Execution end the Working Manifest may be discarded, retained for later review, or have only its verified contents approved and saved as a new immutable Manifest;
- the interface lists manifests from newest to oldest and marks the active one;
- approving an Agent proposal creates and activates a new manifest from the reviewed Working Manifest snapshot;
- editing and saving a manifest creates and activates a new manifest, leaving the source manifest unchanged;
- enabling an existing manifest only changes the active selection and does not create a copy;
- only an inactive manifest may be deleted, and the sole remaining manifest cannot be deleted;
- deleting a manifest does not automatically delete its Components;
- any Component referenced by a retained manifest or durable Working Manifest must remain available.

Every retained manifest is a Recovery Point. Recovery selects and activates that manifest directly. The system does not preserve or replay an approval undo chain, maintain per-component version histories, or provide a separate single-component rollback function; a user who wants a different component combination edits a manifest and saves the result as a new manifest.

A separate mutable Component Usage Index records each Component's `last_used_at`. The timestamp changes only when a Workflow or Step is entered or a Trusted Action is invoked. Only a Component with no reference from any retained Manifest or durable Working Manifest may become a cleanup candidate. Elapsed time since actual use may identify and order such candidates but cannot override a live reference.

Assets use a separate local Asset Usage Index keyed by logical name, running language, and full content hash. Accepted old Assets are not cleaned automatically; their usage and Manifest references are shown only for later human review. Files newly added during one Top-level Execution are instead tracked in a durable Asset Batch so rejection can roll back that run's additions without treating the rollback as maintenance.

Cleanup is a user-initiated maintenance operation. The application presents candidates but never deletes them because a time threshold elapsed. Immediately before a requested deletion, it recomputes references from retained Manifests and durable Working Manifests; any current reference rejects the deletion. The Agent, background maintenance, and ordinary update flows cannot delete Components automatically.

## Knowledge Library

The Knowledge Library stores non-executable information for later diagnosis. After Safe Task Termination, the application offers a screenshot-annotation and text interface for the user to explain the correct handling. The resulting Expert Guidance becomes available immediately and includes its applicability context and provenance.

Users can inspect, modify, disable, and delete Expert Guidance. It may influence diagnosis and Capability Proposals, but it cannot execute actions, alter the active manifest, or bypass confirmation and approval boundaries.

## Remote model data

Enabling and configuring a remote model means the user authorizes Lix Assistant to send the data required for model calls. There is no separate authorization or per-call confirmation. The application explains this behavior in the model configuration interface.

Transmission remains need-based: a call includes only the screenshots, recognition results, history, and Expert Guidance relevant to the current diagnosis. It must not upload the whole Knowledge Library or unrelated logs.

## Locked outcomes

Python-first Workflow source and warned dynamic Agent Python are now fixed boundaries. Later work may choose concrete Runtime API details, runner implementation, model providers, prompts, local model packaging, UI framework, and packaging technology. Changing a fixed boundary requires explicitly reopening Stage 1 and updating the relevant ADR rather than treating the change as an implementation detail.
