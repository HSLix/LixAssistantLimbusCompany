---
status: accepted
---

# Limit first-version Agent maintenance to Supervised Operation

ADR 0020 supersedes only the blanket exclusion of Asset additions below: new templates may be cropped from real game screenshots and proposed through the complete Manifest review path. Existing Asset files remain immutable.

Every first-version Working Manifest Update Proposal requires human review and an explicit approve-or-reject decision before its changed Steps or Workflows execute. Explicitly selecting an already saved Manifest ID at execution start runs it directly and is not a new Agent proposal. Rejection requires user feedback and starts the next Agent Turn when budget remains. Approval permits the complete selected Manifest to execute in the current Top-level Execution, including later calls after the current Step returns; it does not publish the Manifest permanently or change the Default Manifest. `Request Step Recheck` and a Safe Task Termination recommendation require no source confirmation because they introduce no candidate executable content. Whole-Manifest permanent approval is unavailable until the execution ends.

Unattended Operation and persisted runtime-policy selection are deferred until real maintenance trials show that endpoint-model proposals are reliable enough to justify automatic execution of unapproved code. Ordinary Component execution is not a security sandbox, so each supervised review exposes the complete candidate content and residual risk. The first version adds no high-risk action taxonomy or per-action confirmation: after runtime approval, changed Components use the same fixed Trusted Action access matrix as other Components of their roles. The Agent still has no direct action channel and cannot modify Trusted Actions or Recovery Rules. The Agent may propose new template Assets cropped by the executor from a fresh Target Window screenshot taken for that crop request (ADR 0020); it cannot overwrite, rename, or delete existing Asset files. The system-level stop remains a separate immediate cancellation control rather than a proposal decision.
