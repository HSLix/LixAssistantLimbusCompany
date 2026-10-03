---
status: accepted
---

# Run selected Manifest Components through the ordinary executor

The main GUI stays on its main thread and Task Workflow orchestration uses one background thread with a non-polling `threading.Condition` Run Gate. After complete validation and supervised permission for this Top-level Execution, changed Steps, Task Workflows, and Subworkflows in the selected complete Manifest execute through the same ordinary Component path as unchanged ones. No candidate-Step-only process is part of runtime recovery; an entered Workflow frame keeps its original code and locals, while later new Component calls resolve the selected Manifest. Cancellation prevents later gated work and wakes pause without closing the GUI or Target Window. A failed fresh invocation of the current Step pauses for the Agent to choose another retained Manifest ID as its next modification base or to end execution; it does not automatically roll back. Runtime permission does not grant permanent publication, which remains a separate post-execution decision. Ordinary Component execution is not a security sandbox.
