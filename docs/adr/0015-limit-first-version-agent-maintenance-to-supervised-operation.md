---
status: accepted
---

# Limit first-version Agent maintenance to Supervised Operation

Every first-version Working Manifest Update Proposal requires human review and an explicit approve-or-reject decision before its candidate Step, Asset files, and mappings enter a formal trial. Rejection requires user feedback and starts the next Agent Turn when budget remains. Approval permits only the current formal trial. `Request Step Recheck` and a Safe Task Termination recommendation require no source confirmation because they introduce no candidate executable content. Runtime confirmation affects only the current Top-level Execution; whole-Manifest permanent approval is unavailable until that execution ends.

Unattended Operation and persisted runtime-policy selection are deferred until real maintenance trials show that endpoint-model proposals are reliable enough to justify automatic execution of unapproved code. Formal execution isolation is still not a security sandbox, so each supervised review exposes the candidate content and residual risk. The first version adds no high-risk action taxonomy or per-action confirmation: after approval, the candidate Step uses the same fixed Trusted Action access matrix as a normal Step. The Agent still has no direct action channel and cannot create Trusted Actions. The system-level stop remains a separate immediate cancellation control rather than a proposal decision.
