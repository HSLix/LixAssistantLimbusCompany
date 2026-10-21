---
status: superseded
supersedes: 0005
superseded_by: 0013
---

# Limit Stage 3 to Agent-assisted Workflow Drafting and Trial

Historical record only: the design below is superseded, including its process-isolation or file-batch assumptions. Current Components are read and executed in the main process; files are retained directly without batch ownership. TODO after the first release: evaluate moving executor execution into a subprocess (ADRs 0017 and 0021).

Stage 3 starts one Workflow Drafting Run, the third Top-level Execution form, from a developer-defined GUI objective, fixed business inputs, and a known observable state. It owns one Agent Session, Working Manifest, and optional Candidate File Batch but has no aggregate Task Workflow Result. The Agent may execute a real trajectory and produce a Workflow Draft, but it does not choose product inputs, invent business policy, design production GUI or CLI mappings, or claim unobserved branches. A developer, optionally assisted by AI, revises the draft into formal candidate Components. Every source change receives new immutable identities and requires a formal Working Manifest trial; only compatible real evidence contributes to Validation Coverage.

This replaces the broader Stage 3 Capability Expansion decision in ADR 0005. Autonomous discovery and construction of unsupported goals remains deferred. Stage 3.5 later attaches the proven Adapter, drafting, trial, and approval foundations to Runtime Recovery and Workflow Maintenance.
