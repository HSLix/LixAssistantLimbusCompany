# Stage 3: Agent Runtime Step Recovery and Maintenance

Status: architecture accepted, including the #310 and #311 decisions. Agent runtime implementation remains future work.

An Agent may help an existing supported Task Workflow only after an Execution Anomaly leaves its current Step wrapper paused. It may propose changes to Steps, Task Workflows, and Subworkflows in one complete Manifest, with reasons for the changes. Trusted Actions and Recovery Rules are outside this Agent modification scope. The Agent may propose new template Assets cropped by the executor from a fresh Target Window screenshot taken for that crop request (ADR 0020); it cannot overwrite, rename, or delete existing Asset files. Normal supported execution remains deterministic and model-free.

```text
existing supported Task Workflow
→ Execution Anomaly inside its paused Step
→ bounded Runtime Agent Session
→ complete candidate Manifest and structural validation
→ supervised permission for this execution
→ atomic selection and fresh invocation of the current Step
→ compatible return commits the whole selection, or failure pauses for another choice
→ post-execution review for separate permanent publication
```

## Confirmed scope

- Workflow execution errors outside Step, invalid root results, and Recovery Rule failures do not create new recovery boundaries. Task has no entry condition or final verifier; authors implement business checks in Steps. Agent sessions and Manifest trials remain limited to a paused Step with live callers.
- Each Agent Turn returns exactly one Working Manifest Update Proposal, `Request Step Recheck`, or Safe Task Termination recommendation. There is no Temporary Action Plan or direct model-action channel.
- `max_turns` is the Session budget. A dispatched model request consumes a Turn even when its response is invalid or its provider fails. Provider, model, System Prompt version, generation parameters, and Agent Adapter version remain fixed within the Session.
- An invalid Agent result, failed structural or compatibility check, or user rejection consumes the current Turn. Rejection requires feedback before another Turn when budget remains. Source revision receives a new immutable Component ID; there is no proposal status machine or separate revision loop.
- The Agent Adapter transports one self-contained Context Snapshot and parses one Turn result. It does not execute actions, write files, validate or select a Manifest, invoke Components, or decide recovery and termination.
- The Agent may propose several changes to the allowed Component roles in one complete Manifest. Every mapping, source identity, formal call, role, and signature must pass complete validation before selection. Prompt guidance asks for a narrow change and a reason for each edit; the exact proposal format remains to be designed.
- A proposal may be selected only while the executor can immediately make a legal, compatible fresh invocation of the paused current Step. The executor retains the existing Python caller frames and their locals. Changed Workflow implementations apply to later new calls; they never replace an entered frame.
- A user who explicitly selects an already saved Manifest ID to start an execution runs that Manifest directly. Supervised Operation requires review and explicit permission for each new complete Manifest update proposed by the Agent during that execution, before its changed code executes. That permission applies to the complete selected Manifest for this execution, including later calls; it neither permanently publishes the Manifest nor changes the Default Manifest.
- The Supervised Review Dialog is topmost and modal. It blocks main-window interaction until the supervisor approves the complete proposal for this execution, rejects it with feedback, or confirms Cancellation; its close action and Escape key cannot bypass that decision. `Request Step Recheck` and Safe Task Termination recommendations introduce no candidate source and require no source confirmation.
- After selection, changed Steps, Task Workflows, and Subworkflows execute through the ordinary Component path with their ordinary Trusted Action permissions. The first current-Step call is the behavioral trial. A compatible return commits the whole selected Manifest and resumes paused callers; the Task Workflow continues its remaining Steps and succeeds only on a normal compatible return.
- If that current-Step call fails, execution remains paused. The Agent may select any durably retained attempt Manifest ID as the basis for another modification and trial, or end the execution. No automatic rollback occurs. A later Step failure after a successful return is a new interruption at that Step and leaves the committed Manifest selected.
- Every complete Manifest used for an attempt is durably saved with a Manifest ID, including the original and intermediate versions. Intermediate attempts remain available as history after execution, without separate user approval. Trying an existing Manifest again uses its existing ID and records another attempt in Trace. The Agent's Context Snapshot supplies the available IDs within its context budget; the exact context format remains to be designed.
- Ordinary Component execution is not a security sandbox. The supervisor sees the complete proposed change and residual risk before granting runtime permission. The Agent cannot directly call Trusted Actions or modify their implementations or Recovery Rules. The Agent may propose new template Assets cropped by the executor from a fresh Target Window screenshot taken for that crop request (ADR 0020); it cannot overwrite, rename, or delete existing Asset files.
- Cancellation prevents later gated work and wakes a cooperative pause without closing the GUI or Target Window. It neither enters recovery nor automatically changes the last selected Manifest.
- The GUI remains on its main thread and Task Workflow orchestration stays in one background thread. Its `threading.Condition` Run Gate waits without polling before new Trusted Actions or Agent Turns; a permitted operation finishes even if Pause is requested immediately afterward. Stop and review-window termination use the same Cancellation path.
- Runtime permission and successful trial are evidence for the separate post-execution approval decision. Saving an intermediate attempt as history does not permanently approve it, but any saved Manifest ID may be explicitly selected in a later execution. Once the current Working Manifest is approved, its permanent approval is not repeated merely because it is selected in another execution.
- If execution ends with a current Working Manifest ID that has not already received permanent approval, only that current Working Manifest is submitted for post-execution approval. Returning to the Base Manifest or another already approved ID skips repeated approval; earlier intermediate versions remain in attempt history but are not separate approval candidates. The review shows the final Task Workflow result and explicit checking-Step evidence, failure reasons when present, Trace, and Validation Coverage; failed verification does not block human approval. The topmost modal Capability Approval Dialog requires an explicit whole-proposal approve-or-reject decision. After approval, another window asks whether to set the approved current Working Manifest as Default. Trial and review evidence remain available under their retention policy.
- A process crash before post-execution approval preserves attempted Manifest IDs and flushed evidence but does not automatically reopen an approval dialog on restart. Any saved ID remains explicitly selectable. Independently, explicitly setting any saved ID as Default requires no additional confirmation, regardless of permanent approval status.
- New immutable source files and screenshot-derived Assets are stored directly in their normal libraries, while attempted Manifests remain available by ID. Post-execution approval and rejection retain files; resource maintenance is deferred, with no Candidate File Batch (ADRs 0020 and 0021).

## Deferred

- Agent-assisted Workflow Drafting for a new objective, unsupported goals, and autonomous Capability Expansion.
- Agent-initiated Component editing outside an active task is a separate future workflow, not part of the #310/#311 runtime path.
- Cross-Workflow continuation, frame reconstruction, and Checkpoint/Resume; revisit them only when a real case shows why current-Step recovery cannot complete a task.
- Continuing after an already returned Task would require a separate continuation contract. Current execution never reconstructs its caller frame or replays the completed Workflow.
- Unattended Operation, a high-risk action taxonomy, and direct model actions.
- Concrete Agent proposal and Context Snapshot formats, persistence paths, and UI details.
- TODO for Stage 3: define the Agent request/response path for requesting a fresh screenshot crop, receiving and inspecting the cropped Asset image, and then submitting repair code and a complete candidate Manifest. Specify how these exchanges fit the three allowed final Turn results and consume `max_turns`; Stage 2 supplies only deterministic cropping/storage and an inspectable image reference, without a model service.

The current Step is the only recovery continuation point. Changed Workflow code applies to later ordinary calls. Task has no entry-condition or final-verifier callback; business checking Steps use ordinary recovery.

Model requests have no automatic elapsed-time interruption. Cancellation remains an explicit control request and the Adapter propagates actual provider failures with their original diagnostics. There is no Session deadline, action budget, candidate budget, or plan timeout. Exhausting the existing `max_turns` budget makes the parent executor perform Safe Task Termination; user Cancellation starts no further Turn.
