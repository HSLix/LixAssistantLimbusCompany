---
status: accepted
supersedes: 0012
---

# Focus Stage 3 on Runtime Step Recovery and Maintenance

Stage 3 starts the Agent only from an Execution Anomaly caught while an existing supported Task Workflow remains paused inside an `@step` wrapper. Step-external interruptions and terminal Task Workflow checks do not start a Runtime Agent Session. At the paused boundary, the Agent may propose a complete Manifest changing Steps, Task Workflows, or Subworkflows, with reasons for each change; Trusted Actions, Recovery Rules, and Assets are outside this modification scope. The resulting Manifest is selected together, but recovery still requires a compatible fresh invocation of the paused current Step. Entered Workflow frames retain their original code and locals; changed Workflow code applies to later new calls. A later Step interruption starts a new recovery at that Step.

Agent-assisted Workflow Drafting for a new objective and autonomous Capability Expansion remain deferred. Cross-Workflow continuation after a Step-external failure is also deferred until a real case shows why current-Step recovery cannot complete the task.
