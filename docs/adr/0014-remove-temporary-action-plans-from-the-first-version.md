---
status: accepted
supersedes: [0006, 0008]
---

# Remove Temporary Action Plans from the first version

The first-version Runtime Agent cannot emit or execute a Temporary Action Plan and has no direct model-action channel. Every Agent Turn returns exactly one Working Manifest Update Proposal, `Request Step Recheck`, or Safe Task Termination recommendation. A proposal may change Steps, Task Workflows, or Subworkflows and must pass complete Manifest validation. The executor selects the complete Manifest for an immediate legal fresh call of the paused current Step; changed Components then use their ordinary execution path. Trusted Actions, Recovery Rules, and Assets are outside the Agent modification scope.

This removes the Temporary Plan Adapter, `plan_id`, plan-specific AST contract, plan timeout, plan execution Trace, and independent one-off Agent Python runner from the first version. It narrows the endpoint model's task to modifying existing structured automation instead of exploring and self-validating temporary behavior. Agent-proposed Python remains non-sandboxed and requires Supervised review and confirmation before selection for the current execution; permanent publication remains separately human-approved after execution.
