---
status: accepted
---

# Treat trial success as permanent-approval evidence

A successful formal trial and Validation Coverage are displayed evidence rather than automatic gates for permanent approval. If a Top-level Execution ends with a current Working Manifest ID that has not already received permanent approval, that current Working Manifest is the sole post-execution Capability Proposal; returning to the Base Manifest or another approved ID skips repeated approval, and earlier intermediate versions are not separately offered for approval. Even when the final Task Workflow `verify` fails, the review shows that failure and its evidence and permits an explicit whole-Manifest approval or rejection. This supersedes the promotion gate in ADR 0007. Structural validation and human approval remain mandatory. Runtime permission for one execution does not change the Default Manifest or grant permanent publication; approval marks that Manifest ID as permanently published rather than creating a duplicate. A separate post-approval window asks whether to set the approved current Working Manifest as Default.
