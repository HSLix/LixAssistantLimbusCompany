---
status: accepted
---

# Use immutable saved manifests with mutable top-level working manifests

Registered Task Workflows, Subworkflows, Steps, Recovery Rules, and Trusted Actions are immutable Components with unique IDs. Each Manifest is one complete document whose executable mappings resolve stable dotted logical names to immutable Component IDs and load information, while dedicated `recovery_rules` and `trusted_actions` mappings register those distinct loading paths. Every Trusted Action entry also fixes its single `observe` or `control` classification for the executor's non-configurable access matrix. Its `assets` mapping instead records semantic names, languages, shared relative paths, and complete content hashes; Assets have no Component IDs. Editing an eligible executable capability adds a new Component ID and changes the value at the same logical name instead of overwriting content or creating a per-component version sequence. Trusted Actions are shipped or human-approved and cannot be created or replaced by the Agent during a Top-level Execution. Exactly one immutable saved Manifest is active. At Top-level Execution start the system creates one complete durable Working Manifest from it. A directly started Task Workflow owns one; an Automation Plan's sequential Task Workflows share one. The executor resolves all capabilities by logical name through that copy, and eligible Agent changes atomically replace its complete contents. The system stores neither an additions-and-deletions log nor historical Working Manifest versions. Recovery selects an earlier saved Manifest directly instead of replaying approval history.

## Consequences

- The first version executes no Temporary Action Plan. Agent-generated executable behavior must be a structurally valid compatible replacement of the current paused Step and enters only through a complete Working Manifest update and immediate formal trial.
- Later Task Workflows in the same sequential Automation Plan may reuse capabilities added earlier in that Top-level Execution; parallel Task Workflow execution is excluded from the first version.
- The current Working Manifest is persisted so it survives process failure; review differences from its base are derived when needed.
- A Working Manifest update becomes visible only while the executor is paused and can immediately arrange a legal formal trial call. The complete replacement and referenced sources are written and verified before one atomic switch. The prior complete file remains as the sole uncommitted marker until trial success commits or failure rolls back the switch; existing Python frames are never hot-patched.
- A paused Step wrapper retains its logical name, original arguments, and return contract. Re-entry resolves the latest ID at that name; Trace records the name, actual ID, and hash. No replacement chain is required.
- Trace records the formal Components actually executed, with identities, hashes, evidence, and Agent Interaction Log references. It does not retain `working_manifest_hash` or the unused contents of superseded Working Manifests.
- At Top-level Execution end it may be discarded, retained for later review, or approved as one complete new immutable Manifest after its candidate mappings have acceptable evidence. The first version has no partial Component or file approval.
- Approving an Agent Capability Proposal creates and activates a new Manifest; it never mutates the base Manifest.
- Saving a user-edited manifest creates and activates a new manifest. Merely enabling an existing manifest creates nothing new.
- Manifests are shown newest first. Only an inactive, non-sole manifest may be deleted, and deleting it does not automatically delete Components.
- Every retained Manifest is a Recovery Point. Components referenced by a retained Manifest or durable Working Manifest cannot be cleaned up.
- A mutable Component Usage Index records `last_used_at` when a Component is actually executed or read. Only unreferenced Components are cleanup candidates; elapsed time since actual use helps identify or order candidates but never authorizes deletion of a referenced Component.
- Cleanup only presents candidates for user-initiated deletion. It never deletes by elapsed time, and it must recompute all retained-Manifest and durable-Working-Manifest references immediately before deleting.
- Approval history is not a recovery mechanism. Retained Components and manifest snapshots are sufficient.
