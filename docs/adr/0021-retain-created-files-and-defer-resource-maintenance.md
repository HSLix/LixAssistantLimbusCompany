---
status: accepted
---

# Retain created files and defer resource maintenance

2026-10-25：[ADR 0031](0031-preview-agent-crops-and-archive-removed-assets.md) 接受显式 remove_asset 的归档移除例外，保留原图/Tags/截图与恢复元数据；不开放永久删除、通用清理或运行结束自动清理，其余留存边界继续有效。

Persist each new immutable Component source file, screenshot-derived Asset, and complete Manifest directly in its normal store. Keep original and intermediate attempted Manifests by ID. Post-execution review records a human approval or rejection for the current eligible Manifest ID; approval marks that existing ID as permanently approved without duplicating the Manifest or changing the Default. Rejection grants no approval and does not delete any Manifest, source, or Asset. Approval metadata is separate from Manifest content protected from Agent modification. Runtime permission remains a distinct pre-trial decision.

Remove Candidate File Batch ownership records and all approval-, rejection-, cancellation-, or run-end-triggered resource cleanup. Manifest and resource maintenance belongs to a separately scoped future module; this version implements no reference index, garbage collector, or retention/deletion policy. Resource deletion, reference scanning, Component Usage Index, and cleanup UI are deferred for future discussion; earlier detailed maintenance proposals do not commit this version to a policy or interface. Keeping files directly avoids a second ownership lifecycle when both approval outcomes retain attempts and content. This supersedes Batch and cleanup requirements in ADRs 0009 and 0011, the Batch clauses of ADR 0020, and the corresponding implementation slices. Screenshot provenance, complete content hashes, protection of existing Manifest and Asset files from Agent modification, immutable Component source, and existing validation and review boundaries remain required.

Human management and modification of existing Manifest and Asset files may be provided by a future GUI. It is deferred alongside resource maintenance; the Agent remains forbidden from modifying existing Manifest and Asset files. Reference and hash handling for human edits must be designed with that GUI, not assumed to exist now.
