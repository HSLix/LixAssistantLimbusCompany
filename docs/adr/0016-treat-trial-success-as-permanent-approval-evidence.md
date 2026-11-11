---
status: superseded by ADR-0040
---

# Treat trial success as permanent-approval evidence

2026-11-11 已替代：开发者确认删除运行后永久批准流程，不再设置 Capability Proposal／批准窗口或额外永久批准状态。完整校验、不可变发布、运行选择与正常结束后的自动 Default 选择按 [ADR 0040](0040-share-run-state-and-reuse-agent-sessions-for-runtime-repair.md) 执行；下文仅保留历史决定。

A successful formal trial and Validation Coverage are displayed evidence rather than automatic gates for permanent approval. If a Top-level Execution ends with a current Working Manifest ID that has not already received permanent approval, that current Working Manifest is the sole post-execution Capability Proposal; returning to the Base Manifest or another approved ID skips repeated approval, and earlier intermediate versions are not separately offered for approval. Even when the Task Workflow or a business checking Step fails, the review shows that failure and its evidence and permits an explicit whole-Manifest approval or rejection. This supersedes the promotion gate in ADR 0007. Structural validation and human approval remain mandatory. Runtime permission for one execution does not change the Default Manifest or grant permanent publication; approval marks that Manifest ID as permanently published rather than creating a duplicate. A separate post-approval window asks whether to set the approved current Working Manifest as Default.
