# Stage 2 Minimum Implementation Slices

Status: accepted baseline.

Workflow 2.0 starts from a clean orphan branch in this repository. The old branch remains intact as historical reference and emergency rollback; the new branch does not run beside, wrap, or remain compatible with the legacy runtime. This plan implements the accepted Stage 2 contract without reopening storage formats, exhaustively designing failure codes, or generalizing game-specific termination. The original dependency order is retained; ADR 0026 revises the final completion gate below.

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

The Architecture Demo remains historical evidence for the approximate Agent interaction flow and supervision-state transitions. Later slices may reuse its application skeleton where the behavior matches, but replace its hard-coded Example execution instead of preserving a parallel Demo runtime or compatibility loader. The formal Stage 2 `components/` and `manifests/` directories accept only the new complete format.

Old business code is behavioral reference, not source to copy and rename.

## Slice 1: Clean project skeleton

Create the smallest installable Python project on the orphan branch, with one source package, one test package, and only dependencies required by the first pure execution slices. Bring over the accepted domain documents and ADRs without carrying legacy runtime modules.

Acceptance:

- a clean checkout installs and imports the new package;
- the test command succeeds with one smoke test;
- no legacy Workflow, Pipeline, registry, node configuration, frontend, packaged runtime, model, or image is present merely for compatibility;
- Windows-only dependencies are not required by the pure core test suite.

## Slice 2: Component loading and complete-manifest validation

Implement three role-only decorators with no registry or execution behavior, SHA-256 Component IDs verified against exact source bytes, typed signature inspection, Manifest loading, and source-wide structural validation. Use test-only Component modules and Manifests.

Acceptance:

- a trusted developer candidate may mix existing `component_id` entries with new `source_path` entries; saving computes missing IDs, copies exact source bytes to `components/<sha256>.py`, and produces a saved Manifest containing no source paths;
- candidate source paths are relative to the candidate Manifest directory and cannot escape it through absolute paths, parent traversal, or symbolic links;
- Asset storage is independent (ADR 0027); Candidate and saved Manifests require no Asset sidecar, and embedded Asset mappings remain rejected;
- a candidate Manifest cannot provide `manifest_id`; publishing generates the UUID used by the saved file without changing the Default Manifest;
- publishing and selecting the Default Manifest are separate operations; publishing writes immutable files and a saved Manifest, while explicit Default selection atomically replaces `manifests/default.json` only after the retained Manifest validates and loads;
- unexpected exceptions during Manifest validation, load, publishing, or Default selection are logged at `error` with the failing phase and traceback, while ordinary validation rejection is returned as structured validation errors;
- one valid Task Workflow, Subworkflow, Step, Recovery Rule, and application-registered Trusted Action callable load successfully;
- fixed functions are execute for Workflow/Step Components; Trusted Actions use their registered callable signatures, optional matching condition only for Step, and detect/recover for Recovery Rules; Task condition and independent verify callbacks are rejected;
- invalid Component IDs or source mismatches, role decorators, signatures, dynamic `ctx.call()` targets, illegal caller roles (including Subworkflow-to-Subworkflow calls), unresolved targets, forbidden `except`, and forbidden `finally` control flow are rejected before execution;
- Task Workflow, Subworkflow, Step, and Recovery Rule source rejects relative imports, project-local helpers, and direct Component imports; only Trusted Actions may additionally use application dependencies fixed by the shipped environment;
- validation reports all independently determinable errors with stable codes and source locations when available, without cascading errors after a failed prerequisite;
- duplicate JSON keys, unknown fields, missing required fields, and wrong field types are rejected rather than ignored or corrected;
- logical names consist of one or more case-sensitive Python identifiers separated by `.`, are not rewritten or used to infer role, and are unique across `components` and `recovery_rules`;
- multiple Component logical names may reuse one Component ID; Trusted Action classification is fixed by application registration;
- a rejected candidate publishes nothing and leaves the Default Manifest unchanged;
- tests require no GUI, recognition model, network, or game process.

## Slice 3: Complete Task Workflow with fake Trusted Actions

Implement Run Context, `ctx.call()`, `ctx.action()`, role wrappers, input normalization and copy boundaries, Task/Subworkflow/Step calls, an append-only Trace sink, root-result normalization, and business checks in ordinary Steps. The shared asynchronous application-service start accepts the stable logical name and inputs of any Task Workflow, Subworkflow, or Step and optionally one retained Manifest ID while using the same executor and Trace path. Use fake `observe` and `control` Trusted Actions to run a whole deterministic task.

For this slice, `start()` captures either the explicitly selected retained Manifest or the Default Manifest as its Base Manifest, and every Component call resolves through the captured in-memory Manifest, while Trusted Actions use the application registration. Changing the Default affects later implicit starts only. Durable Working Manifest creation, safe-boundary replacement, immediate current-run visibility, and retained attempt history remain Slice 5 responsibilities; a failed current-Step trial does not automatically roll back.

Production code implements only the common Trusted Action dispatch boundary behind `ctx.action()`: application registration lookup and classification checks, role authorization, copied arguments, invocation, and Trace recording. The concrete `fake_*` names, callables, and behavior used by this slice live only in the test fixture. Real shipped Trusted Actions are added with their actual observation and control slices rather than preserving Demo-only fake actions.

The same slice supplies the minimum developer loop required to author this model-free Workflow rather than relying on hand-built storage internals. Each project checkout has one fixed, Git-ignored `candidate/` Developer Candidate containing one complete editable `manifest.json` draft and its developer-authored Component source. The directory is flat in this slice: generated source uses `<logical_name>.py` beside `manifest.json`, and the Manifest records that relative filename without inferring identity or role from it. The globally unique Component logical-name rule prevents generated source filename collisions. Asset images and tag metadata live independently in the shared store, not in Developer Candidate (ADR 0027).

The existing services provide the developer loop without a separate `DeveloperService`. `ManifestManager` initializes, validates, publishes, lists, loads, and selects the Default Manifest; `ApplicationService.start(..., manifest_id=None)` runs an entry from the Default or an explicitly selected Base Manifest. The CLI only parses arguments, formats results, and owns the interactive `clear` confirmation. GUI and tests reuse those same services rather than a parallel facade.

Initialization materializes every executable entry from the selected retained Manifest as a flat editable `<logical_name>.py` source and writes one complete `manifest.json` whose executable entries use those relative `source_path` values. Developers use their normal editor to add, update, remove, or rename source files and Manifest mappings; application-registered Trusted Action docstrings and Python signatures define their contracts; the project supplies no per-Component editing, action-discovery, or automatic source-rewriting commands. Publishing hashes every source again, so unchanged bytes retain the same Component ID.

The Developer Candidate and runtime proposals share Manifest formats and validation rules but do not share editable storage. Agent-created immutable Component source is stored directly in the Component Library; complete attempted Manifests remain durable by Manifest ID. Approval and rejection retain those files without cleanup (ADR 0021). A later explicit operation may materialize an ended Run's proposal into an empty Developer Candidate for human revision; it never merges with or overwrites an existing developer draft. Issue #309 implements only the Developer Candidate boundary. The Agent never receives the full developer interface and cannot use developer cleanup to affect runtime files.

The existing `lalc` executable is the sole human entrypoint. With no arguments it continues to start the GUI; developer operations use only the flat subcommands `init`, `validate`, `publish`, `clear`, `run`, `run-plan`, `connect`, `crop-asset`, `tag-asset`, `data-dir`, `list-manifests`, and `set-default`. `init`, `validate`, `publish`, and `clear` are the entire Developer Candidate lifecycle; there are no `add`, `update`, `remove`, `rename`, `list-actions`, or `describe-action` commands. A project checkout uses them from the project root through `uv run lalc ...`, while an installed package uses `lalc ...`. There is no separate developer executable, nested command framework, HTTP service, plugin layer, Manifest editor, or capability-discovery API. Each subcommand delegates to the same ordinary Python services used by the GUI and tests.

`init` creates `candidate/` only when that fixed directory is absent or empty; existing contents reject initialization without overwrite or merge and the error points to `lalc clear`. By default it materializes the Default Manifest; `--from <manifest-id>` selects another retained Manifest without changing the Default. If no Manifest has ever been published, plain `init` creates an empty complete schema-2 draft and its empty library. If retained Manifests exist but the Default pointer is missing, malformed, or unresolved, `init` creates nothing, lists the available retained Manifest IDs, and tells the developer to run `lalc set-default <manifest-id>` before retrying. It never repairs or changes the Default itself.

`clear` shows the fixed candidate path, warns that every file below it will be removed, and requires an interactive confirmation before deleting the whole Developer Candidate. Cancellation and non-interactive input delete nothing. No force flag, alternate deletion target, selective cleanup, or automatic pre-initialization cleanup exists in the first version.

Successful `publish` leaves the complete Developer Candidate untouched. It reports the new Manifest ID and shows the corresponding explicit `run --manifest`, `set-default`, and optional `clear` commands. Developers may inspect or edit the same draft and publish again; only `clear` removes their editable files. Every successful publication receives a fresh Manifest ID even when its complete content matches a retained Manifest. Unchanged source bytes reuse their content-addressed Component IDs; the system adds no whole-Manifest deduplication scan or unchanged-candidate rejection.

`validate` executes the same complete validation and load pipeline that `publish` executes before writing, including importing every Developer Candidate module in the main process. It writes no immutable Component or Manifest, allocates no Manifest ID, and changes no Default selection. Agent-proposed source later requires complete validation and explicit supervised permission before it uses the ordinary Component execution path; this developer command does not grant that permission.

`run <logical-name>` uses the Default Manifest, while `--manifest <manifest-id>` selects another retained Base Manifest without changing the Default. Mutually exclusive `--inputs '<json-object>'` and `--inputs-file <path>` supply one complete JSON object; omission supplies `{}` and no `key=value` coercion exists. The command may start a Task Workflow, Subworkflow, or Step. It calls the asynchronous `ApplicationService.start()` and waits through the service's public observation boundary rather than invoking the synchronous Executor directly. Completion prints the Run Result JSON to standard output and leaves detailed Trace in its JSONL artifact without first-version live streaming. Exit status is `0` only for Run success and `1` for command rejection, synchronous start rejection, or a started Run that finishes in failure. `Ctrl-C` requests the existing cooperative Stop, waits for safe completion, and exits `1` rather than killing the Workflow thread.

`list-manifests [-n COUNT]` is the read-only discovery entrypoint required by `run --manifest`, `set-default`, and Default repair. Without importing Components or changing state, it orders retained Manifests by local file modification time from newest to oldest and displays at most the positive integer `COUNT`, defaulting to `9`. The first output line reports the displayed and total counts and tells the developer that `-n` changes the limit. The table lists each displayed Manifest ID, saved file time, and counts by Manifest section. After the table, a separate final line reports the Default Manifest ID; a missing or invalid pointer is reported there rather than marked inside the table. No `created_at` schema field or alternate JSON output is added. `init` reuses the same listing when retained Manifests exist but the Default pointer is unusable.

`set-default <manifest-id>` revalidates source hashes and completely loads the retained Manifest before atomically replacing `manifests/default.json`. Selecting the current Default is a successful no-op. The command remains legal while a Run is active because that Run keeps its captured Base Manifest; only later implicit starts use the new Default. The explicit command needs no additional confirmation and prints the resulting Default ID. Invalid identity, validation failure, or load failure exits `1` and leaves the prior Default unchanged.

The new terminology and storage replace the development-only Active Manifest format directly. Only `manifests/default.json`, public `default_manifest_id`, and captured `base_manifest_id` exist. The implementation ignores an old `active.json` and provides no migration, fallback read, compatibility field, or dual write; test and development data are initialized again under the accepted format.

Every CLI command uses only exit status `0` for success and `1` for any unsuccessful request, including invalid arguments, validation rejection, user-cancelled cleanup, Run failure, or unexpected system failure. Success and data go to standard output; failure reasons go to standard error. Validation and publication report every independently determinable structured validation error with its stable code, logical name, source position, and message. An exception reaching CLI interaction is logged and shown with its complete original traceback and cause chain on stderr. Structured validation rejection remains concise when it has no underlying exception.

Issue #309 stops at local Developer Candidate management, Local Publish into the user's runtime data directory, and model-free Run. Software distribution later packages one complete retained Manifest, every immutable Component and the needed Asset image/tag files as a transport-neutral Capability Bundle. Bundle export, import, signing, downloading, GitHub Release, Mirror, and cloud-drive delivery are outside this slice; no individual Component distribution format is introduced.

The application service is the only public execution boundary. It owns asynchronous orchestration, the single-active-run rule, Run ID allocation, the captured Manifest, public state, pause/resume/stop, Trace persistence, and the final Run Result. One internal synchronous Workflow Executor owns the ordinary Python call stack, Run Context, role wrappers, input boundaries, Component and Trusted Action dispatch, verification, and emission of Trace events back to the service. The Executor creates no thread, writes no artifact, allocates no Run ID, exposes no public API, and is never invoked directly by acceptance tests.

Before accepting `start(entry, inputs, manifest_id=None)`, the service synchronously rejects an already-active run, an unavailable selected or Default Manifest, an unresolved or ineligible entry logical name, signature binding errors, invalid input types, and inputs that cannot be normalized to independent JSON-compatible copies. An accepted request returns its positive integer Run ID. Rejection instead raises a dedicated structured `StartError` carrying only a stable `code` and readable `message`; it allocates no Run ID, starts no thread, emits no Trace, and leaves public run state unchanged. After a Run ID is allocated and `run_started` is emitted, every later termination is represented by that Run's success or failure result rather than `StartError`.

Input normalization follows the declared recursive annotation without a schema library or general coercion layer. Exact `str`, `bool`, and `int` types remain distinct; `float` alone accepts an exact integer and normalizes it to a floating-point value; `Literal` requires matching type and value; dictionaries require string keys; and `NaN` or infinity is rejected. Every accepted boundary value is round-tripped into an independent JSON-compatible copy before it is recorded or passed onward.

The public service state contains only `phase: idle | running | finished`, orthogonal `paused`, `pause_info`, `resume_pending`, `default_manifest_id`, the captured `base_manifest_id`, `working_manifest_id`, ordered `attempted_manifest_ids`, `run_id`, resolved entry identity and role in `entry`, final `result`, and ordered in-memory `trace`. An accepted start moves `idle` or `finished` directly to `running` before its worker starts; completion moves it to `finished`. Pause does not invent another phase, and Stop does not invent a `stopping` phase while cancellation is still being processed. A synchronously rejected start leaves the previous public state intact. Starting a later accepted run replaces the previous run-specific state. Architecture Demo Agent fields and compatibility states are not retained; the old Demo remains reference material only.

Callers observe asynchronous execution only through the application service's `state` snapshot and `wait_for(predicate)`. Both return independent copies of the public state. `wait_for()` has no timeout parameter and blocks until its predicate matches; it neither changes nor cancels the Run. This is the same observation surface used by GUI code and automated tests, with no Future, event-subscription layer, or test-only execution API.

Pause, Resume, and Stop are idempotent cooperative controls. Pause blocks before the next Component or Trusted Action boundary without interrupting an active Python instruction and records `run_paused`; Resume clears the gate, wakes the worker, and records `run_resumed`. Stop records `run_cancel_requested`, sets irreversible Cancellation, and wakes a paused worker; the next Component or Trusted Action boundary ends the Run with `failure_code: user_cancelled` without Recovery or Agent involvement. Calls made while no Run is active have no effect. Formal Workflow threads are never force-killed or given asynchronous exceptions, and a finished Run always exposes `paused: false`.

No execution layer, Trusted Action, Agent Adapter, or external-process launcher introduces an elapsed-time failure cutoff. Explicit user cancellation and actual operation errors still propagate; polling intervals and requested action durations are not expiry policies.

The shared Trusted Action dispatcher records each invocation with its logical name, observe/control classification, copied input parameters, run-local call identity, and elapsed monotonic `duration_ms`. Success records the normalized actual return value; failure records the complete original exception chain; user interruption records its cancel, pause, or takeover intent without fabricating an output. Individual action implementations do not duplicate this timer. These records are observations only and never terminate a call because of its duration.

Each start allocates one positive integer Run ID from a persistent single-writer sequence beginning at `1`. Allocation advances the stored number atomically before run artifacts are created; a crash may leave a gap, but an allocated number is never reused even after old evidence is deleted. The first version permits only one application-service writer per data directory and adds no cross-process allocation lock. Every Trace event is appended in order both to the application service's public in-memory state and to `traces/<run_id>.jsonl`; GUI and automated tests inspect the public state, while JSONL preserves already-written evidence after a process failure. Run Log Bundle retention, Workflow Run Ledger, and evidence cleanup remain later-slice work.

Acceptance:

- a test Task Workflow calls a Subworkflow and Step and completes without Agent involvement;
- the final result is validated against its JSON-compatible return annotation, with business checks expressed as ordinary Steps and exposed as the successful Run Result's `output`;
- Trace records actual logical names, Component IDs, arguments, actions, returns, and timings in order;
- paired start/return-or-failure events retain run-local call IDs and parent IDs, so repeated and incomplete calls remain distinguishable;
- mutable inputs changed by a callee do not mutate the caller, saved Step arguments, or saved Step inputs;
- business checks are implemented as ordinary Steps; Task success is a normal JSON-compatible return, with no standalone verification callback or retry path;
- changing the Default Manifest during a run does not change that Run's later resolutions; a later implicit start uses the new Default, while an explicit start uses its selected retained Manifest without changing the Default;
- `lalc init` materializes one selected retained Manifest into the flat `candidate/` Developer Candidate; after ordinary file editing, `lalc validate` checks that complete draft and `lalc publish` creates an immutable Manifest without changing the Default;
- no per-Component CLI editing command exists; developers add, update, remove, or rename ordinary candidate files and Manifest mappings with their normal filesystem and editor tools, while `lalc clear` is the only whole-candidate cleanup command and requires confirmation;
- a developer can run an eligible logical name against the published Manifest and then explicitly select it as Default through public project-root tooling backed by the same services as the application;
- formal source invokes literal action names through `ctx.action()` and Python source remains the sole contract; developers inspect the application registration, callable docstrings, and signatures directly, with no per-Manifest action source or duplicate handwritten action schema.

## Slice 4: Step recovery closure

Use one invocation helper for Component execute, Step condition, Trusted Actions, and Recovery Rules, and one Step recovery procedure. Raw and normalized errors both get full diagnostics; only raw errors need normalization. Rules never recursively recover. Workflow errors outside Step are reported without replay, and failure-code strings never prove Safe Task Termination.

Acceptance:

- zero, one, and multiple matching Recovery Rules follow the accepted paths;
- `detect()` exception stops enumeration immediately;
- `recover()` exception or non-`None` return directly produces Execution Anomaly, tries no other rule, and does not immediately invoke the Step;
- a successful recovery invokes the current Step once and returns its compatible result through the still-live Task/Subworkflow call chain;
- repeated interruption, failed Step condition, incompatible return, and Step-external interruption reach the anomaly boundary without restarting a Workflow;
- Trace and Ledger attribution distinguish public recovery, Step reinvocation, Agent-boundary entry, and actual Safe Task Termination.

## Slice 5: Working Manifest

Implement durable retention of every complete Manifest used for an attempt, complete-file validation, atomic selection, and fresh resolution after a switch. Reusing an existing Manifest keeps its Manifest ID while Trace records another attempt. A failed current-Step call pauses for an explicit next choice or termination; it does not automatically roll back. Drive replacement through a test-controlled executor entry rather than an Agent.

Acceptance:

- a valid replacement changes only later `ctx.call()` resolution and fresh Step invocations;
- an entered Task Workflow or Subworkflow frame retains its implementation and locals;
- one selected Manifest may change Steps, Task Workflows, and Subworkflows together; later new calls resolve all of its changes through the ordinary Component path;
- a compatible replacement Step reconnects using a new copy of the saved arguments;
- incompatible inputs, required new parameters, changed return contracts, or unsafe current state prevent reconnection;
- any complete-manifest validation failure preserves the old Working Manifest; a failed trial leaves every attempted Manifest available by ID for the next choice.

## Slice 6: Automation Plan and Workflow Run Ledger

Implement full Plan preflight, frozen ordered items, invocation-time Working Manifest revalidation, best-effort traversal, cancellation, compact Task/Subworkflow Ledger records, and derived health views. Choose the simplest local persistence representation at implementation time.

Acceptance:

- initial parse, name, role, and input errors are reported together as `interrupted: invalid_plan` before any task starts;
- after valid preflight, every item is considered once and a failed item does not block the next;
- later items resolve through the current shared Working Manifest and incompatible items record failure without retry;
- cancellation stops later items and creates a Task failure only when its run record already exists;
- strict versus Agent-assisted success, durations, public recovery, Step reinvocation, and Agent counts derive from factual records without double-counting nested spans.

## Slice 7: Asset capability, revised by ADR 0027

Assets resolve independently of Component Manifests. Complete logical names map to folders of full-SHA-256 PNGs; asset-tag.json maps hashes to optional ordinary tags. Missing metadata means [], not an unavailable template. Crop/tag-asset writers replace tags with the supplied list; missing or empty tags store [] and clear the old labels. Existing image files never change, fresh screenshot provenance and complete hashes remain required.

Every match rereads directory and tags once, then fixes its own candidates. Any-tag overlap forms the preferred group; match that whole group, and only if no result qualifies match every remaining template. None/[] means all templates. Combine the selected batch, apply optional cross-template NMS (default IoU 0.5) and deterministic score ordering. Explicit regions and full client coordinates, original error propagation and independent latest-nonempty Usage Index remain required. Unknown logical names and malformed/hash/decoding errors are not converted into empty matches.

New images/tags are visible on the next match in the same Run, without publish, Manifest switching or cross-call caching. Observe Trusted Actions preserve permission checks, argument/result normalization and Trace. Existing game_language configuration is Context only, not implicit tag preference. No OCR/model provider or current Stage 3 Asset permission is introduced.

Tests cover optional metadata, multiple preferred templates, early batch exclusion of remaining image reads, fallback, multi-template NMS, full tag replacement and clearing, same-Run changes, immutable hash paths, fresh crops/provenance, full error chains and Component publication independent of damaged Assets.

## Revised Stage 2 completion — ADR 0026

The original Slice 8 required a real mailbox Task Workflow. The developer explicitly removed that completion gate on 2026-10-22: real business authoring depends on GUI development tools such as client-coordinate display and region selection. The mailbox and remaining Windows integration/package acceptance are deferred in #317, not reported as passed.

Stage 2 completes with Slice 1–7 implementation and evidence, including #310 Step Recovery, #311 Working Manifest and #313 Automation Plan/Ledger acceptance, plus:

- `tag-asset` registers an existing local crop in the shared Asset tag metadata, checking provenance, identity, hash and image decoding; tags replace the prior list and Assets require no Candidate or publish; it does not connect to the game or import external images. Existing images remain immutable; tag updates replace the full list without confirmation.
- ADR 0027 removes all Candidate and saved Manifest Asset sidecars. Old Asset layouts and dedicated libraries are discarded and recreated, not migrated.
- `example/workflow/` supplies a complete schema-2 Manifest, three Component levels and all seven application action calls. The default task captures and waits; controls have explicit independent entrypoints, and matching requires an image in its logical-name directory, without publishing Assets.
- Regression runs through the public application service and checks Trace/Ledger, crop/tag replacements and immediate detection without re-publication. Existing separate Windows observation/control/Asset evidence stays attributed to its actual scope; platform doubles do not prove remaining Windows integration.

The original dependency order remains skeleton → Manifest → fake Workflow → Step Recovery → Working Manifest → Plan/Ledger → Assets. A real Agent Adapter and runtime recovery remain Stage 3.5 work; Stage 3 independently validates Component repair. No GUI developer tools, mailbox implementation or Windows package acceptance are added to this revised completion gate.

## Current format and lifecycle

Manifest schema 2 contains components and recovery_rules, with manifest_id after publication. Embedded assets/trusted_actions and legacy schemas remain rejected. Trusted Actions are application-owned; Assets use the independent layout of ADR 0027, not a Manifest sidecar. Every formal Run connects/focuses and monitors input before Component execution, and one Plan shares that session. Old examples remain removed; tests own their fixtures and the new example/workflow sample contains only formal code/config, without an Asset mapping file.
