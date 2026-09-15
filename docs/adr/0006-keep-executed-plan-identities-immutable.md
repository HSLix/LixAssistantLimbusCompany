---
status: superseded
superseded_by: 0014
---

# Keep Executed Plan Identities Immutable

Every plan identity becomes immutable when execution starts. Execution Trace records the base `manifest_id`, whether a temporary Working Manifest was used, the identities and hashes of Components actually executed, temporary `plan_id` values, Agent Interaction Log references, actions, observations, evidence, and interruption positions. The Agent Interaction Log stores the complete generated Python source and the interaction that produced it. A Temporary Action Plan is not a Component, executes directly through its Adapter, and never enters the Working Manifest. Editing creates a new plan identity and new execution events; rejection changes only plan status, while successful verified logic may separately be reorganized into candidate Components. The system does not retain historical Working Manifest snapshots or `working_manifest_hash`, because diagnosis reconstructs actual execution rather than every capability that was available.

Each Task Workflow run retains its Trace, Agent Interaction Logs, screenshots, and detailed evidence as one Run Log Bundle. The common retention policy keeps or removes the whole bundle, avoiding independent reference lifecycles and dangling Trace references. An optional nullable `source_trace_id` remains soft provenance and does not prevent bundle cleanup. The Workflow Run Ledger survives separately.
