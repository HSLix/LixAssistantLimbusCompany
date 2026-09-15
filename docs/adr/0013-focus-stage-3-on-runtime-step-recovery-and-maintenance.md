---
status: accepted
supersedes: 0012
---

# Focus Stage 3 on Runtime Step Recovery and Maintenance

Stage 3 starts the Agent only from an Execution Anomaly caught while an existing supported Task Workflow remains paused inside an `@step` wrapper. Step-external interruptions and terminal Task Workflow checks do not start a Runtime Agent Session. At the paused boundary, the Agent may diagnose the run and propose a compatible replacement of the current Step with optional related Assets, or only Asset files and mappings used by the unchanged current Step. Task Workflow, Subworkflow, other-Step, Recovery Rule, and Trusted Action changes are excluded from the first-version Runtime Agent Session.

Agent-assisted Workflow Drafting, Task Workflow and Subworkflow maintenance, and autonomous Capability Expansion are explicitly deferred. They require broader exploration, self-validation, or generalization beyond the intended first-version endpoint model. Stage 3 first proves that constrained repair of the current paused Step is useful and feasible.
