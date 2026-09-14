# Stage 3: Agent Python and Capability Expansion Scope

Stage 3 adds optional intelligence on top of the Python-first deterministic executor. It contains Runtime Exception Handling and user-initiated Capability Expansion.

## Runtime Exception Handling

Runtime Exception Handling begins only after the executor produces an Execution Anomaly: either an interrupted `@step` cannot continue after public recovery and one fresh Step invocation, or an `ExecutionInterruption` occurs outside a Step and has no deterministic recovery boundary.

```text
Execution Anomaly
→ Agent receives the ordinary Trace, a Run Context snapshot, and relevant evidence
→ Agent returns immutable Python source with execute(ctx), or recommends Safe Task Termination
→ Temporary Plan Adapter executes it in a runner subprocess under Supervised or Unattended Operation
→ parent validates outputs and revalidates formal execution
```

An Agent termination recommendation is advisory. Only the executor decides and performs Safe Task Termination.

For an anomaly originating inside `@step`, the wrapper and its caller frame remain paused during Agent work. After every normally completed Temporary Action Plan, the executor re-observes, resolves the current Step through the latest Working Manifest, and evaluates its `condition`. The original or replacement Step may return to the paused caller only when its input and return contracts remain compatible with the original call site. The ordinary Subworkflow and Task Workflow return chain must then complete and produce the task result; only afterward does the executor invoke the exact `verify` bound at Task Workflow start with that normalized result and the original inputs. The Agent cannot modify that success standard, fabricate the result, or trigger an early success unwind. A modified Workflow never replaces the paused frame and applies only to later calls. If the current Step cannot restore a compatible return, the executor continues bounded Agent diagnosis or performs Safe Task Termination.

Runtime Exception Handling ends when the Task Workflow call stack ends. If the root result is invalid or the bound verifier does not return `True`, that task records `result: failure` with `failure_code` and `failure_message`, without another Agent invocation or retry. Safe Task Termination is recorded separately as an executor action and likewise ends only that Task Workflow. A containing Automation Plan continues its fixed best-effort sequence with the next independent task under the same Working Manifest.

The Agent cannot invoke itself, mutate a saved Manifest, or register a permanent capability. Temporary Action Plans execute directly through the Adapter and never enter a Manifest. While the executor is paused, the Agent may organize verified logic into candidate Components; the executor persists, verifies, and atomically selects the resulting complete Working Manifest before a fresh invocation. Unattended execution is explicitly risk-bearing because the subprocess is not a security sandbox.

## Capability Expansion

Capability Expansion begins only from an explicit user goal for an unsupported objective. It follows the current operating policy rather than requiring source review in every session.

```text
User goal
→ retrieve and reuse registered Python Workflows
→ compose registered Python Components where sufficient
→ generate an immutable Python Temporary Action Plan where necessary
→ store the complete source in the Agent Interaction Log
→ execute it directly through the Adapter and record its plan and log references in Trace
→ revise with a new plan_id when interrupted
→ establish Validation Coverage from compatible real traces
→ organize only verified logic into candidate Components and verified resources into Asset mappings
→ obtain human approval for permanent registration
→ create and activate a new Component Manifest
```

Temporary code may execute before approval; formal registration may not. An unchanged successful plan can supply the Python source for a Capability Proposal and may be referenced by an optional `source_trace_id`. A formal Component becomes permanently available only after validation and human approval. Assets are not Components: newly generated files remain governed by their Top-level Execution's Asset Batch until rejection rolls them back or an approved Manifest safely references them.

Irreversible progress may require evidence from several immutable plans. Old evidence applies only to unchanged source, inputs, and compatible state boundaries. Unobserved branches are not promoted as supported code.

Runtime exception learning follows a fixed local-to-public sequence: the first successful Temporary Action Plan is incorporated into a candidate version of the current Workflow as an ordinary local Python handling branch. It cannot directly create a public Recovery Rule. When another Workflow later encounters a compatible real exception, exhausts public deterministic recovery, and invokes the Agent, that branch may be reused and validated in the new context. Success creates a public Recovery Rule and a rebuilt original Workflow without the duplicate branch through one atomic Working Manifest replacement. The second Workflow is rebuilt only if it fails to propagate `ExecutionInterruption` correctly.

## Shared foundations

Both Agent activities use:

- one local or remote Agent Adapter contract;
- Python-first Task Workflows, Subworkflows, and Steps;
- `ctx.call(logical_name, **arguments)` as the only formal cross-Component invocation path, resolved through the current Working Manifest;
- the runner subprocess and Temporary Plan Adapter, which hides JSON transport behind Normal Outcome and `ExecutionInterruption`;
- Temporary Action Plan source contains no `except`, may use `try/finally`, and exposes every exception to its Adapter; expected alternatives use explicit ordinary results or a later plan identity;
- the shipped Runtime API for perception, input, wait, and verification;
- append-only Execution Traces, Agent Interaction Logs, and evidence retained together as one Run Log Bundle per Task Workflow run;
- Workflow Run Ledger summaries for identifying unreliable or recovery-heavy Workflows;
- the active Component Manifest as the base and a complete Working Manifest for current-run executable mappings and language-specific Asset references;
- the Knowledge Library and relevant Expert Guidance;
- Working Manifest review, validation, human approval, and new-Manifest activation.

Agent retrieval initially uses component names, signatures, concise Python docstrings, and source. Docstrings change with behavior and therefore participate in the same content hash and Component identity. Tags, separate component documents, and vector retrieval are deferred.

The Working Manifest belongs to the Top-level Execution. A directly started Task Workflow owns it alone; all Task Workflows in a first-version sequential Automation Plan share it, so later tasks may retrieve and reuse temporary capabilities established earlier in the same execution.

They differ in trigger and goal: Runtime Exception Handling continues an existing supported task, while Capability Expansion develops a possible future task capability.

## First vertical slice

The first slice should prove one small GUI learning loop:

1. Given a small Runtime API, the Agent produces and runs a Python `execute(ctx)` plan for one objective.
2. Runtime wrappers record actually executed Components, actions, observations, validation, interruption, and outputs in Trace; the Agent Interaction Log retains the full generated source.
3. If the plan fails after irreversible progress, a new plan continues from the current state and compatible Trace segments provide Validation Coverage.
4. Only verified Python control flow enters a Capability Proposal.
5. Human approval creates a Manifest-backed formal Python Workflow.
6. A later formal run completes without model decisions unless it reaches a new Execution Anomaly.

Evaluation compares fixed script, pure Agent Python, and Agent plus registered reusable Python Workflow using strict success, Agent-assisted success, model calls, steps, latency, interruption, and separated deterministic-versus-Agent recovery behavior. The same measures feed the local Workflow Run Ledger.
