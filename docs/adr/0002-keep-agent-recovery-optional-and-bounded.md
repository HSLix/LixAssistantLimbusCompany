---
status: accepted
---

# Keep Agent recovery optional and bounded

LALC keeps normal automation deterministic and independent of any model. The Agent is an optional module invoked only after an Execution Anomaly leaves an existing supported task paused inside a Step; it may diagnose evidence and propose a formal candidate maintenance change, but permanent capability still requires later human approval. This preserves a model-free product path while allowing bounded repair of known automation.

## Consequences

- Supervised Operation confirms each complete Working Manifest Update Proposal before formal trial.
- Every incident has one `max_turns` budget and may end earlier through Safe Task Termination. A model request consumes its Turn when dispatched, including invalid output or provider failure; there is no separate Session deadline, action budget, candidate budget, or plan timeout.
- A Step's optional Python `condition` checks whether it may be entered without changing external state; every Step verifies its expected result and records inspectable evidence. Missing critical evidence blocks execution.
- Candidate Components are intended to use the shipped Runtime API, but first-version generated Python is not securely confined to it. Supervised Operation exposes the complete proposal and residual risk before every trial. Unattended Operation, saved-Manifest mutation, and permanent registration without human approval remain forbidden.
- Agent-generated permanent changes remain isolated until approval. Stage 3 repairs and maintains existing supported Task Workflows only; Agent-assisted Workflow Drafting and autonomous Capability Expansion are deferred.
- Each Agent Turn is self-contained from local authoritative state and does not rely on conversation history retained by the model provider.
- Local and remote models share one Agent Adapter that owns transport, provider-error normalization, and result parsing only. Execution, file writes, Manifest changes, formal invocation, recovery, and termination remain executor responsibilities.
- One Runtime Agent Session freezes its provider, model, System Prompt version, generation parameters, and Adapter version. Configuration changes apply only to later Sessions; no model switching or fallback occurs within the active Session.
- Runtime Agent success means only that a fresh compatible current-Step invocation returned normally and resumed its paused callers. It cannot declare Task Workflow success; a later Step anomaly creates a new bounded Session within the same Top-level Execution.
