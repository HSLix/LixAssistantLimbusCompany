# Domain Docs

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

## Agent changes to Manifests and Assets

Stage 3 permits only independent repair of one existing Component through candidate source and the existing Validator. Runtime Agent Sessions, supervised trials, Agent Asset creation and multi-Component changes belong to Stage 3.5 under ADR 0025.

- Existing Manifest and Asset files are read-only to the Agent, including through generated code or executor requests. Never overwrite, rename, or delete them as part of a repair.
- ADR 0027 replaces the per-Manifest Asset Library. Resolve the full logical name directly to an assets/ directory containing full-hash PNGs and asset-tag.json (hash → tags). Images without a tag entry participate with []; all writers explicitly store [] for new untagged hashes. Language is an ordinary optional tag, and priority_tags uses any-tag overlap with whole-preferred-batch matching before fallback. Read directory/tags anew each match, not at Manifest load or from a cross-call cache. Existing images are never overwritten; tags are replaced by the supplied list, preserving order and duplicates; omitted or empty tags clear prior labels. No Candidate or publish is required for Assets. The one-time old-data disposal is explicitly developer-authorized, not run-end cleanup.
- Do not design Agent repair around editing an old image and then fixing old Manifest hashes; that operation is forbidden. Human editing and management through a future GUI are deferred separately.
- For crop requests, capture the current game anew, crop it, and return the crop for inspection. Do not require an earlier observation ID to remain current or read a saved screenshot file.

See [ADR 0027](../adr/0027-resolve-assets-independently-with-optional-priority-tags.md), historical [ADR 0024](../adr/0024-use-a-dedicated-asset-library-for-each-manifest.md), [ADR 0020](../adr/0020-allow-screenshot-derived-assets-and-explicit-search-regions.md) and [ADR 0021](../adr/0021-retain-created-files-and-defer-resource-maintenance.md).

## Application-owned Trusted Actions

ADR 0023 removes per-Manifest Trusted Action registration. Register actions once in the application and keep `ctx.action()` as the checked call boundary for every Manifest. Preserve caller/phase permissions, observe/control classification, validation, timing, Trace, original errors, and user interruptions. Remove pure forwarding Action files when migrating examples; do not replace them with direct backend calls. Derive the Stage 3 action-list function from application registration and existing signatures/docstrings. The #321 migration is implemented. ADR 0026 permits a new teaching sample without restoring the old examples; ADR 0027 removes Candidate Asset sidecars; new samples contain Components only.
