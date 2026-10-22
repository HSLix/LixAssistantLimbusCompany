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
- ADR 0024 gives each Manifest its own external Asset Library mapping file, using the former `assets` object structure. Actual image files remain in the global store; do not copy images per Manifest or implement a global mapping/cache fallback. Duplicate detection is scoped to that library and requires both semantic name and language to match. Developer replacement requires confirmation; Stage 3.5 Agent duplicate-pair additions are rejected. Developer edits affect only the Candidate library and require publish; image filenames use complete SHA-256 and existing images are never overwritten. The #321 migration implements this contract.
- Do not design Agent repair around editing an old image and then fixing old Manifest hashes; that operation is forbidden. Human editing and management through a future GUI are deferred separately.
- For crop requests, capture the current game anew, crop it, and return the crop for inspection. Do not require an earlier observation ID to remain current or read a saved screenshot file.

See [ADR 0024](../adr/0024-use-a-dedicated-asset-library-for-each-manifest.md), [ADR 0020](../adr/0020-allow-screenshot-derived-assets-and-explicit-search-regions.md) and [ADR 0021](../adr/0021-retain-created-files-and-defer-resource-maintenance.md).

## Application-owned Trusted Actions

ADR 0023 removes per-Manifest Trusted Action registration. Register actions once in the application and keep `ctx.action()` as the checked call boundary for every Manifest. Preserve caller/phase permissions, observe/control classification, validation, timing, Trace, original errors, and user interruptions. Remove pure forwarding Action files when migrating examples; do not replace them with direct backend calls. Derive the Stage 3 action-list function from application registration and existing signatures/docstrings. Current code migration is pending.
