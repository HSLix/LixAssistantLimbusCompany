---
status: accepted
---

# Run selected Manifest Components through the ordinary executor

2026-11-11 局部替代：取消执行前人工批准，恢复入口扩展到 Plan／Workflow／Step；同进程普通执行、调用者帧不替换及无安全沙箱保证保留。 见 [ADR 0040](0040-share-run-state-and-reuse-agent-sessions-for-runtime-repair.md)。下文保留原决定，不代表新设计已实现。

The main GUI stays on its main thread and Task Workflow orchestration uses one background thread with a non-polling `threading.Condition` Run Gate. After complete validation and supervised permission for this Top-level Execution, changed Steps, Task Workflows, and Subworkflows in the selected complete Manifest execute through the same ordinary Component path as unchanged ones. No candidate-Step-only process is part of runtime recovery; an entered Workflow frame keeps its original code and locals, while later new Component calls resolve the selected Manifest. Cancellation prevents later gated work and wakes pause without closing the GUI or Target Window. A failed fresh invocation of the current Step pauses for the Agent to choose another retained Manifest ID as its next modification base or to end execution; it does not automatically roll back. Runtime permission does not grant permanent publication, which remains a separate post-execution decision. Components are read and executed in the main process; ordinary execution is not a security sandbox. TODO after the first release: evaluate moving executor execution into a subprocess, including Context transport, cancellation, and original-error propagation.
