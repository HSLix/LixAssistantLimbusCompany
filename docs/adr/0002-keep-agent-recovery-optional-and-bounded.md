---
status: accepted
---

# Keep Agent recovery optional and bounded

Lix Assistant keeps normal automation deterministic and independent of any model. The Agent is an optional module invoked only after an Execution Anomaly pauses a supported task; it may diagnose evidence and execute a run-scoped Temporary Action Plan, but it cannot turn that plan into a permanent capability without later human approval. This preserves a model-free product path while still allowing novel runtime states to be handled.

## Consequences

- Supervised Operation confirms each complete plan once; a plan produced by a new diagnosis requires new confirmation.
- Unattended Operation may execute plans automatically, but every incident has a finite attempt budget and may end earlier through Safe Task Termination.
- A Step's optional Python `condition` checks whether it may be entered without changing external state; every Step verifies its expected result and records inspectable evidence. Missing critical evidence blocks execution.
- Runtime Agent plans are intended to use the shipped Runtime API, but first-version generated Python is not securely confined to it. Supervised Operation exposes source; Unattended Operation accepts the warned residual risk. The Agent may update the current Working Manifest, while saved-Manifest mutation and permanent registration without human approval remain forbidden.
- Agent-generated permanent capabilities remain isolated until approval. Capability Expansion for unsupported game objectives is a separate, user-initiated Stage 3 activity whose temporary execution follows the selected operating policy; it is not part of Runtime Exception Handling or formal task execution.
