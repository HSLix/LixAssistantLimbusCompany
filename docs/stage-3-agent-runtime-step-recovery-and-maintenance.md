# Stage 3: Agent Runtime Step Recovery and Maintenance

Status: architecture accepted. Minimum code experiment planning is next.

Stage 3 tests whether an endpoint Agent can use the structure and evidence of an existing supported Task Workflow to recover its current paused Step and propose a durable replacement of that Step or its related Assets. It does not maintain Task Workflows or Subworkflows, discover a new objective, explore an unsupported task, or draft a new user-startable Task Workflow.

```text
existing supported Task Workflow
→ Execution Anomaly
→ bounded Runtime Agent Session
→ diagnosis and candidate maintenance proposal
→ complete structural validation
→ reversible Working Manifest trial when an immediate legal call exists
→ success and Validation Coverage, or rollback
→ post-execution Capability Proposal and separate whole-Manifest human approval
```

## Confirmed scope

- Normal supported execution remains deterministic and model-free.
- Only an Execution Anomaly caught while an existing supported Task Workflow remains paused inside an `@step` wrapper may start a Runtime Agent Session.
- Step-external interruptions, Task Workflow condition failures, invalid root results, and verifier failures never start a Runtime Agent Session; they record evidence and finish through their existing deterministic failure or Safe Task Termination path.
- Candidate maintenance may replace the current paused Step with optional related Asset files and mappings, or may update only Asset files and mappings used by the unchanged current Step. Asset-only repair creates no replacement Step identity.
- The Agent cannot create or replace Trusted Actions during a Top-level Execution.
- The first version has no Temporary Action Plan, Temporary Plan Adapter, `plan_id`, or direct model-action result. Each Agent Turn returns exactly one Working Manifest Update Proposal, `Request Step Recheck`, or Safe Task Termination recommendation.
- `max_turns` is the only Session budget. A model request consumes its Turn when dispatched, including invalid output and provider failure; editing candidate source requires a later Turn. Formal candidate Step trials consume no extra Turn and use the Step's existing finite-wait and interruption contract.
- Every Agent Turn receives a self-contained Context Snapshot rebuilt from local authoritative state. Correctness never depends on conversation history retained by the model provider; snapshot fields, selection, and serialization remain a later design decision.
- Local and remote models use one Agent Adapter contract. The Adapter transports that snapshot, normalizes provider errors, and parses one allowed Turn result; it cannot perform actions, write files, validate or switch a Working Manifest, invoke formal code, decide recovery success, or use provider-native tool calling to bypass the result contract.
- Provider, model, System Prompt version, generation parameters, and Agent Adapter version are frozen at Runtime Agent Session start. Configuration changes apply only to a later Session; there is no within-Session switching, routing, or fallback.
- A Runtime Agent Session succeeds only when the parent executor obtains a contract-compatible normal return from a fresh formal invocation of the current Step. The paused Python callers then continue normally; the Agent cannot declare Task success, and the Task Workflow's startup-bound verifier remains authoritative.
- A later Step anomaly within the same Top-level Execution creates a new Runtime Agent Session with a fresh `max_turns` while reusing that execution's current Working Manifest and Candidate File Batch.
- The first version supports only Supervised Operation. The complete candidate Step source, Asset files, and mappings require an explicit approve-or-reject decision before Working Manifest selection. Rejection requires user feedback for the next Agent Turn. Approval permits only the current formal trial and does not grant permanent approval.
- Runtime proposal review uses a topmost modal Supervised Review Dialog that disables the main window. It can approve one formal trial, reject only with feedback for the next Agent Turn, or request Cancellation through a separate confirmation; the dialog cannot be dismissed through its close action or Escape key.
- The Demo implements cooperative pause with one `threading.Condition` Run Gate. The executor waits only before a new Trusted Action, Agent Turn, or candidate Step trial; Manifest replacement itself does not wait. A permitted operation finishes even if pause is requested immediately afterward. Resume and stop notify sleeping workers, and stop raises the executor's Cancellation signal. There is no timer polling, forced thread suspension, or asynchronous framework.
- The first version adds no high-risk action taxonomy or per-action confirmation. An approved candidate Step has the same fixed `observe` and `control` Trusted Action access as a normal Step. The Agent has no direct action channel, cannot create Trusted Actions, and cannot bypass the existing system-level cancellation control.
- A successful candidate Step commits the Working Manifest switch only for the current Top-level Execution, ends that Runtime Agent Session, and resumes the paused callers. Permanent whole-Manifest approval is available only after the direct Task Workflow or complete Automation Plan ends.
- Every re-entry uses the existing recovery contract: the parent executor re-observes, formally evaluates the current Working Manifest's current-Step `condition`, and invokes that Step only when the condition permits it. Asset-only repair uses the unchanged Step condition; Step replacement uses the candidate Step condition. The Agent cannot call or substitute for this check.
- Invalid Agent output, structural or compatibility rejection, user rejection with required feedback, an atomic switch that leaves the old Working Manifest authoritative, and a formally failed trial all consume the current Turn and continue to the next Agent Turn when budget remains. Trial failure first restores the old Working Manifest. Any source revision receives a new Component ID and hash; there is no proposal status machine or separate revision loop.
- A failed or uncertain Working Manifest rollback is not part of that loop. It terminates the Top-level Execution and forbids further Agent Turns, Component calls, and game input until the pre-switch capability snapshot is restored; recovery mechanics remain an implementation decision.
- Task Workflow orchestration runs in one background thread under the main GUI process. Only a not-yet-permanently-approved candidate Step formal trial runs in an independent Candidate Runner OS process; the complete Task Workflow is not moved into that process. The parent process owns Trace, candidate files, Manifest state, and review evidence.
- The Architecture Demo adds no general parent-child RPC. A Candidate Runner receives a JSON-compatible Example scenario snapshot, invokes only pre-registered Example Trusted Actions in its process, and returns a JSON-compatible Step result plus action events for the parent to append to Trace. A narrow IPC boundary is deferred until a real Trusted Action must remain in the parent process.
- Main-window stop and Supervised Review Dialog termination use the same Cancellation path: prevent later gated work, wake cooperative pause, force-terminate an active Candidate Runner, and leave the main GUI and Target Window open.
- User Cancellation after a candidate Working Manifest switch does not roll that switch back. The Top-level Execution ends before another Component runs and the selected complete candidate state supplies its Capability Proposal. Rollback occurs only after a failed formal trial when another Agent Turn will continue.
- A Working Manifest switch changes only later Component resolution; it cannot replace an entered Python frame or undo external game actions.
- The proposal is valid only when the parent executor can immediately arrange a legal formal call of the compatible replacement Step; otherwise the Turn result is rejected without switching the Working Manifest.
- The first formal call is the behavioral trial. Success contributes only actually executed behavior to Validation Coverage; failure durably records evidence and restores the previous Working Manifest.
- After Top-level Execution ends, one complete Capability Proposal projected from either the successfully trialled Working Manifest or a structurally valid unselected candidate is the permanent-approval unit. Runtime confirmation does not grant permanent approval.
- Stage 3 defines no universal business-success threshold for permanent approval. The system presents whether a successful formal trial occurred together with the candidate, execution result, Trace, and Validation Coverage; their absence does not disable approval. The supervisor decides whether that evidence is sufficient, while no trial result, Step return, Task Workflow verifier result, or unattended run can grant permanent approval automatically.
- Permanent review uses a topmost modal Capability Approval Dialog that cannot be dismissed without choosing `approve` or `reject`. Approval saves the complete proposal as a new immutable Component Manifest and makes it active only for later Top-level Executions. Rejection leaves the active Manifest unchanged and permits reference-safe cleanup of unreferenced candidate files. Both decisions retain Trace, Agent Interaction Logs, trial status, and the review record.
- One Top-level Execution owns at most one Candidate File Batch for immutable Component source and Asset files actually created during that execution.
- The first version does not implement call-stack recovery, Checkpoint/Resume, or automatic restart from a known state.

## Explicitly deferred

- Agent-assisted Workflow Drafting and Trial;
- new user-startable Task Workflows;
- unsupported user goals and open-ended exploration;
- autonomous Capability Expansion;
- production GUI or CLI design for new Workflow inputs.
- Temporary Action Plans and independent execution of one-off Agent Python.
- Agent changes to Task Workflows, Subworkflows, other Steps, Recovery Rules, or Trusted Actions.
- broader Workflow Maintenance beyond the current paused Step.
- Unattended Operation and persisted runtime-policy selection.

The Stage 3 architecture Grill is closed. Context field selection, serialization, concrete validators, UI behavior, persistence mechanics, and Demo acceptance belong to subsequent implementation and experiment planning rather than this architecture baseline.

Model request timeout remains an Agent Adapter transport concern rather than a Session budget. There is no `plan_timeout`, Session deadline, action budget, or candidate-count budget. Exhausting `max_turns` makes the parent executor perform Safe Task Termination. User cancellation instead follows the existing Cancellation contract immediately, terminates an active Candidate Runner, and starts no further Turn.
