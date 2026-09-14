# Stage 2 Minimum Implementation Slices

Status: accepted baseline.

Workflow 2.0 starts from a clean orphan branch in this repository. The old branch remains intact as historical reference and emergency rollback; the new branch does not run beside, wrap, or remain compatible with the legacy runtime. This plan implements the accepted Stage 2 contract without reopening storage formats, exhaustively designing failure codes, or generalizing game-specific termination. Each slice must pass its acceptance checks before the next slice begins.

## Migration boundary

Migrate selectively:

- accepted architecture documents and ADRs;
- business-flow knowledge and observed game-state decisions, rewritten as Task Workflows, Subworkflows, and Steps;
- image, model, and other Assets that remain valid after inspection;
- conclusions already established by the Windows foreground-interaction experiments.

Do not migrate:

- `TaskNode` or `TASK_REGISTRY`;
- JSON node graphs or either legacy Pipeline;
- `TaskExecution.register()` or its handler registry;
- shared mutable task parameters, special routing nodes, or error nodes created for the old architecture;
- any compatibility adapter whose only purpose is to let both runtimes coexist.

Old business code is behavioral reference, not source to copy and rename.

## Slice 1: Clean project skeleton

Create the smallest installable Python project on the orphan branch, with one source package, one test package, and only dependencies required by the first pure execution slices. Bring over the accepted domain documents and ADRs without carrying legacy runtime modules.

Acceptance:

- a clean checkout installs and imports the new package;
- the test command succeeds with one smoke test;
- no legacy Workflow, Pipeline, registry, node configuration, frontend, packaged runtime, model, or image is present merely for compatibility;
- Windows-only dependencies are not required by the pure core test suite.

## Slice 2: Component loading and complete-manifest validation

Implement the three role decorators, immutable Component identity and source-hash verification, typed signature inspection, Manifest loading, and source-wide structural validation. Use test-only Component modules and Manifests.

Acceptance:

- one valid Task Workflow, Subworkflow, Step, Recovery Rule, and Trusted Action mapping load successfully;
- invalid hashes, role decorators, signatures, dynamic `ctx.call()` targets, illegal caller roles, unresolved targets, Subworkflow cycles, forbidden `except`, and forbidden `finally` control flow are rejected before execution;
- a rejected candidate leaves the previously selected Working Manifest unchanged;
- tests require no GUI, recognition model, network, or game process.

## Slice 3: Complete Task Workflow with fake Trusted Actions

Implement Run Context, `ctx.call()`, role wrappers, input normalization and copy boundaries, Task/Subworkflow/Step calls, an in-process Trace sink, root-result normalization, and the task-start-bound verifier. Use fake `observe` and `control` Trusted Actions to run a whole deterministic task.

Acceptance:

- a test Task Workflow calls a Subworkflow and Step and completes without Agent involvement;
- the final JSON-compatible result is verified against the immutable original inputs;
- Trace records actual logical names, Component IDs, hashes, arguments, actions, returns, and timings in order;
- mutable inputs changed by a callee do not mutate the caller, saved Step arguments, or verifier inputs;
- false or exceptional verification records terminal failure and does not request Agent handling.

## Slice 4: Step recovery closure

Implement `ExecutionInterruption`, the paused `@step` wrapper, Recovery Rule evaluation, one fresh Step invocation, Execution Anomaly production, and a replaceable Agent/Safe-Termination boundary without implementing an Agent.

Acceptance:

- zero, one, and multiple matching Recovery Rules follow the accepted paths;
- `detect()` exception stops enumeration immediately;
- `recover()` exception or non-`None` return directly produces Execution Anomaly, tries no other rule, and does not immediately invoke the Step;
- a successful recovery invokes the current Step once and returns its compatible result through the still-live Task/Subworkflow call chain;
- repeated interruption, failed Step condition, incompatible return, and Step-external interruption reach the anomaly boundary without restarting a Workflow;
- Trace and Ledger attribution distinguish public recovery, Step reinvocation, Agent-boundary entry, and actual Safe Task Termination.

## Slice 5: Working Manifest

Implement durable Working Manifest creation, complete-file validation, atomic replacement, rollback on failed switching, and fresh resolution after a switch. Drive replacement through a test executor hook rather than an Agent.

Acceptance:

- a valid replacement changes only later `ctx.call()` resolution and fresh Step invocations;
- an entered Task Workflow or Subworkflow frame retains its implementation and locals;
- a compatible replacement Step reconnects using a new copy of the saved arguments;
- incompatible inputs, required new parameters, changed return contracts, or unsafe current state prevent reconnection;
- any complete-manifest validation failure preserves the old Working Manifest.

## Slice 6: Automation Plan and Workflow Run Ledger

Implement full Plan preflight, frozen ordered items, invocation-time Working Manifest revalidation, best-effort traversal, cancellation, compact Task/Subworkflow Ledger records, and derived health views. Choose the simplest local persistence representation at implementation time.

Acceptance:

- initial parse, name, role, and input errors are reported together as `interrupted: invalid_plan` before any task starts;
- after valid preflight, every item is considered once and a failed item does not block the next;
- later items resolve through the current shared Working Manifest and incompatible items record failure without retry;
- cancellation stops later items and creates a Task failure only when its run record already exists;
- strict versus Agent-assisted success, durations, public recovery, Step reinvocation, and Agent counts derive from factual records without double-counting nested spans.

## Slice 7: Asset capability

Implement only the Asset behavior required by a real image-matching Trusted Action: Manifest resolution, hash verification, current-language selection, deterministic cross-language fallback, Usage Index update after successful use, Trace evidence, and Asset Batch rollback for files created by the execution.

Acceptance:

- formal and temporary callers provide only a stable semantic Asset name;
- matching verifies the selected file and records language, source language, score, region, path, and full hash;
- fallback and equal-score selection are deterministic;
- a successful Step may add a verified language alias at an atomic Working Manifest boundary;
- rejected or abandoned run-added files are removed through resumable Asset Batch cleanup without touching accepted old Assets.

## Slice 8: First real game task

Select the smallest existing objective that still proves independent end-to-end automation. The initial candidate is mailbox collection because it exercises entry preparation, observation, repeated claiming, completion recognition, exit, ordinary returns, and final verification without first importing Luxcavation combat or Mirror Dungeon complexity. Its old implementation supplies behavior and state knowledge only.

Acceptance:

- recorded or fake observations cover the task's normal, already-completed, expected-transition, and unknown-state paths without real input;
- a supervised Windows run completes the supported objective, returns to its accepted end state, produces a trustworthy JSON result, and passes its fixed verifier without Agent involvement;
- interruption preserves evidence and follows the Stage 2 recovery boundary rather than recreating the legacy global error-node path;
- the new project completes the task independently; rollback means returning to the preserved old branch, not invoking a legacy runtime from the new branch.

## Order and completion rule

```text
clean project skeleton
→ Component and Manifest loading
→ complete Task Workflow with fake Trusted Actions
→ Step recovery closure
→ Working Manifest
→ Automation Plan and Ledger
→ Asset capability
→ first real game task
```

Stage 2 implementation is complete only after Slice 8 passes its pure tests and supervised Windows acceptance. Agent budget configuration, a real Agent Adapter, Runtime Exception Handling orchestration, and Capability Expansion remain Stage 3 work.
