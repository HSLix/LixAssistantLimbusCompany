---
status: accepted
---

# Register Trusted Actions once in the application

The application owns one registration of shipped or human-approved Trusted Action callables, shared by every Manifest. Remove the per-Manifest `trusted_actions` mapping and Action source Components whose only purpose is forwarding arguments to application functions. Workflow code keeps literal-name calls such as `ctx.action("observe.capture_screen")`; it does not call native input or screenshot backends directly. Existing application functions can be registered directly, without a separate pass-through file for each Manifest.

Moving registration must preserve the executor's observe/control classification, caller/phase permission matrix, input and output validation, pause/takeover/cancellation behavior, per-call timing, Trace, and original-error propagation. Agent code cannot create, replace, reclassify, or bypass the registered actions. Available actions depend on the application registration rather than the selected Manifest; a Manifest switch does not switch the action implementation.

Every formal Run establishes its Focused Automation Session at startup: connect and focus the Target Window and start physical input monitoring before formal Component execution. Stop monitoring and clean up the session at Run end, including observation-only Runs. An Automation Plan shares one session and monitor for its whole Run. Do not condition monitoring on Manifest entries, registered control actions, reachable calls, or the first observation/control operation. All formal Runs require an available Target Window; calculation-only regression tests use a platform test double. Preserve takeover, explicit manual Resume, input ownership, and held-input release behavior. The diagnostic `connect` command remains separate from a formal Run.

TODO for Stage 3: provide a function that lists available actions from that registration, including logical name, signature, required parameters/defaults, observe/control classification, and existing callable/module docstrings so developers and the Agent can inspect names and usage like a tool list. Do not maintain duplicate handwritten descriptions. This listing is an inspection capability, not an Agent registration or mutation interface.

This supersedes per-Manifest Trusted Action registration, source-Component loading, and equality requirements in ADRs 0003 and 0004 and the corresponding Stage 2/3 contracts. Formal Workflow and Recovery Rule Component identity requirements remain. Asset resolution is separately governed by ADR 0024: each Manifest has a dedicated external mapping file and the actual image files remain globally shared. The #321 migration updates runtime, validation, packaging and test-owned fixtures. Old repository examples were removed rather than migrated; ADR 0026 permits a new teaching sample using application actions.
