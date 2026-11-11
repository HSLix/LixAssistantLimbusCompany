---
status: accepted
supersedes: 0012
---

# Focus Stage 3 on Runtime Step Recovery and Maintenance

2026-11-11 局部替代：运行时 Step-only 维护边界由按失败归属恢复替代；恢复时仍不替换已进入的调用者帧。 见 [ADR 0040](0040-share-run-state-and-reuse-agent-sessions-for-runtime-repair.md)。下文保留原决定，不代表新设计已实现。

ADR 0025 moves the runtime recovery, supervised trial, and Agent Asset creation scope described here to Stage 3.5. Current Stage 3 is independent single-Component repair; these runtime contracts are not its prerequisites.

ADR 0020 supersedes only the blanket exclusion of Asset additions below: new templates may be cropped from real game screenshots and proposed through the complete Manifest review path. Existing Asset files remain immutable.

Stage 3 starts the Agent only from an Execution Anomaly caught while an existing supported Task Workflow remains paused inside an `@step` wrapper. Step-external interruptions and terminal Task Workflow checks do not start a Runtime Agent Session. At the paused boundary, the Agent may propose a complete Manifest changing Steps, Task Workflows, or Subworkflows, with reasons for each change; Trusted Actions and Recovery Rules are outside this modification scope. The Agent may propose new template Assets cropped by the executor from a fresh Target Window screenshot taken for that crop request (ADR 0020); it cannot overwrite, rename, or delete existing Asset files. The resulting Manifest is selected together, but recovery still requires a compatible fresh invocation of the paused current Step. Entered Workflow frames retain their original code and locals; changed Workflow code applies to later new calls. A later Step interruption starts a new recovery at that Step.

Agent-assisted Workflow Drafting for a new objective and autonomous Capability Expansion remain deferred. Cross-Workflow continuation after a Step-external failure is also deferred until a real case shows why current-Step recovery cannot complete the task.
