---
status: accepted
---

# Isolate only unapproved candidate trials

The main GUI stays on its main thread and Task Workflow orchestration uses one background thread with a non-polling `threading.Condition` Run Gate. Only a structurally valid but not permanently approved candidate Step trial runs in an independent Candidate Runner OS process; the parent owns Trace, files, Manifest state, and review evidence. Cancellation prevents later gated work, wakes pause, and force-terminates an active Candidate Runner without closing the GUI or Target Window. It does not roll back an already selected candidate Working Manifest: the Top-level Execution ends and that state may supply the Capability Proposal. Rollback is reserved for a failed trial followed by another Agent Turn. The subprocess isolates hangs, crashes, and lifetime but is not a security sandbox.
