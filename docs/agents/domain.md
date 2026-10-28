# Domain Docs

2026-10-27 Fluent GUI：User/Developer 已正式迁到完整 FluentWindow，固定页/外置页及三页开发工具使用 Fluent 导航；原有共享服务、即时保存、单一编辑入口和重载边界保持。当前操作与验证见[迁移记录](../fluent-gui-migration.md)。


How engineering skills should consume this repository’s domain documentation.

## Before exploring, read these

- `CONTEXT.md` at the repository root.
- `CONTEXT-MAP.md` if it exists; it points to context-specific `CONTEXT.md` files.
- Relevant ADRs under `docs/adr/`.

If these files do not exist, proceed silently. Domain-modeling workflows create them lazily when terminology or architectural decisions are resolved.

## File structure

This repository uses a single-context layout:

```
/
├── CONTEXT.md
├── docs/
│   └── adr/
├── src/
│   └── lalc/
├── tests/

```

`CONTEXT.md` records the shared domain language and boundaries. System-wide architectural decisions belong under `docs/adr/`.

## Use the glossary’s vocabulary

When an output names a domain concept—in an issue title, proposal, hypothesis, or test name—use the term defined in `CONTEXT.md`.

If the required concept is missing, reconsider whether the term belongs to the project or record the gap for domain modeling.

## Flag ADR conflicts

If proposed work contradicts an existing ADR, surface the conflict explicitly instead of silently overriding the decision.

## Stage 4 accepted target versus current implementation

[ADR 0032](../adr/0032-use-python-plans-and-coexisting-user-developer-guis.md) and the [Stage 4 specification](../stage-4-extensible-user-gui.md) are the accepted target: one immutable Python Automation Plan per Manifest, Plan→Task result boundaries, coexisting User/Developer windows and shared activity ownership, editable Candidate Python Plan, and no independent Developer Runner page. JSON Plan execution is replaced without compatibility; old immutable data is not rewritten. Shared settings pages remain outside Manifest/Agent writes. The source implements the #331 Python Plan and coexisting-window slice; see [implementation evidence](../stage-4-331-implementation.md). The #332 external pages and per-provider shared Agent settings are implemented locally; see [#332 evidence](../stage-4-332-implementation.md). The #333 bilingual GUI and language reload are implemented locally and have passed developer manual acceptance; #333 is closed; see [#333 evidence](../stage-4-333-implementation.md). GUI component wording follows one shared startup language; specific diagnostics retain their original language. Only User General Settings edits the language, and external pages may opt in while legacy pages retain their text. Developer owns the only Agent settings editor while its window is open; User regains editing after saved handoff. Windows packaged acceptance remains pending. The Stage 2/3 descriptions below are historical where superseded: plan.json read-only and four-page descriptions are not current requirements. Do not claim Windows packaged acceptance is complete.

## Agent changes to Manifests and Assets

ADR 0033 changes only new Agent Interaction Log storage: conversation-local, lossless content references with a self-contained directory. Preserve full live GUI events and model/tool transport, relative reference boundaries, hash checks and redaction. Old logs remain untouched; do not add a history viewer, automatic migration or context pruning as part of this change. See [log design](../agent-interaction-log-design.md).

ADR 0030 supersedes the Developer Agent automatic Publish/execution prohibition below: Developer Policy may publish complete immutable versions and trial explicitly selected saved Manifest IDs through the existing executor, then inspect Run logs. Trial results return to the same round; they do not grant runtime permanent approval or change Default. GUI trials use a modal log window without requesting game focus. Runtime Policy is deferred to Stage 6 (formerly Stage 3.5); only the schedule changed. Candidate file and Asset protection below still applies.

Stage 3 originally implemented independent single-Component repair. ADR 0029 now accepts Developer GUI and shared multi-file repair: explicit Candidate initialization, all existing Candidate files (including candidate manifest.json and Recovery Rules), existing Python Plan editing under ADR 0032, dedicated Candidate creation tools, no generic creation/deletion, continuous conversations and manual review/Publish. The shared host and current three-page Developer GUI implement these changes; see the Developer GUI design for automated versus pending real-model/Windows acceptance. ADR 0028's live screenshot and bounded Asset additions remain. Runtime Agent Sessions, Working Manifest integration and supervised runtime trials are deferred to Stage 6 (formerly Stage 3.5).

- Existing published Manifests, formal source, images and old hash-to-tag entries remain read-only to the Agent, including through generated code or executor requests. ADR 0031 permits only the dedicated remove_asset archive path to remove an active Asset image and its local tag entry; it never permits overwriting old image bytes or general deletion. The editable Candidate manifest is distinct from a published Manifest. The dedicated crop tool may add a new image and its tag entry under ADR 0028.
- ADR 0027 replaces the per-Manifest Asset Library. Resolve the full logical name directly to an assets/ directory containing full-hash PNGs and asset-tag.json (hash → tags). Images without a tag entry participate with []; all writers explicitly store [] for new untagged hashes. Language is an ordinary optional tag, and priority_tags uses any-tag overlap with whole-preferred-batch matching before fallback. Read directory/tags anew each match, not at Manifest load or from a cross-call cache. Existing images are never overwritten; tags are replaced by the supplied list, preserving order and duplicates; omitted or empty tags clear prior labels. No Candidate or publish is required for Assets. The one-time old-data disposal is explicitly developer-authorized, not run-end cleanup.
- Do not design Agent repair around editing an old image and then fixing old Manifest hashes; that operation is forbidden. Human GUI crop confirmation is accepted in ADR 0029; a general Asset manager remains out of scope.
- ADR 0031: preview_crop captures the game anew, returns crop-boundary and clean crop images plus same-image matches, and retains a conversation-scoped preview_id. crop_asset(preview_id) saves those exact original pixels without recapturing; the Workflow Trusted Action observe.crop_asset retains its fresh-capture behavior. game_screenshot also returns a separate 40px grid image; overlays never enter crops, matching or archived original screenshots. remove_asset captures a fresh clean screenshot and archives the original image, tags and removal metadata before removing the active image/local tag relation; other Logical Names are unaffected.
- ADR 0028 narrows Agent crop permissions: an existing logical-name/hash pair reuses its image and original tags, even when new tags are requested. Adding a new hash may add its tag entry without changing existing entries. Developer crop/tag tools retain ADR 0027's tag-replacement semantics. ADR 0029 supersedes the prior automatic Default-to-Candidate reset and single-target write limits: initialize/rebuild explicitly, preserve Candidate across rounds and New Conversation, and enforce the per-round existing-file boundary with the existing Python Plan editable under ADR 0032. The implemented increment permits only add_component / add_recovery_rule to create and register Candidate source from filename, logical_name and source; successful additions join the same round edit boundary, while arbitrary creation and deletion remain forbidden. Source/Manifest changes must succeed together; full validation, Publish and Default remain separate.

See [ADR 0027](../adr/0027-resolve-assets-independently-with-optional-priority-tags.md), historical [ADR 0024](../adr/0024-use-a-dedicated-asset-library-for-each-manifest.md), [ADR 0020](../adr/0020-allow-screenshot-derived-assets-and-explicit-search-regions.md) and [ADR 0021](../adr/0021-retain-created-files-and-defer-resource-maintenance.md).

## Application-owned Trusted Actions

ADR 0023 removes per-Manifest Trusted Action registration. Register actions once in the application and keep `ctx.action()` as the checked call boundary for every Manifest. Preserve caller/phase permissions, observe/control classification, validation, timing, Trace, original errors, and user interruptions. Remove pure forwarding Action files when migrating examples; do not replace them with direct backend calls. Derive the Stage 3 action-list function from application registration and existing signatures/docstrings. The #321 migration is implemented. ADR 0026 permits a new teaching sample without restoring the old examples; ADR 0027 removes Candidate Asset sidecars; new samples contain Components only.
