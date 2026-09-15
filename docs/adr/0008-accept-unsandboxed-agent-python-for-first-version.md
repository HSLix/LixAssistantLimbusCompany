---
status: superseded
superseded_by: 0014
---

# Accept Un-sandboxed Agent Python for the First Version

The first version permits immutable Agent-generated Python to execute before permanent approval in both Supervised and Unattended Operation. A runner subprocess, timeout, JSON Context boundary, minimal structural validation, and append-only Trace provide failure and lifecycle isolation, but they do not prevent file, network, process, system-API, or off-target access. Structural validation rejects any `except` in a Temporary Action Plan while permitting `try/finally`; it also rejects `return`, `break`, `continue`, or `raise` inside `finally`, so the active exception reaches the Adapter rather than being suppressed or replaced explicitly. The application therefore warns users accurately instead of claiming a sandbox; stronger inspection and operating-system isolation are deferred so the first Agent-capability loop can remain small. Permanent Component registration still requires validation and human approval.
