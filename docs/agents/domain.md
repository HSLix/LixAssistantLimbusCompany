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
└── examples/
```

`CONTEXT.md` records the shared domain language and boundaries. System-wide architectural decisions belong under `docs/adr/`.

## Use the glossary’s vocabulary

When an output names a domain concept—in an issue title, proposal, hypothesis, or test name—use the term defined in `CONTEXT.md`.

If the required concept is missing, reconsider whether the term belongs to the project or record the gap for domain modeling.

## Flag ADR conflicts

If proposed work contradicts an existing ADR, surface the conflict explicitly instead of silently overriding the decision.

## Agent changes to Manifests and Assets

- Existing Manifest and Asset files are read-only to the Agent, including through generated code or executor requests. Never overwrite, rename, or delete them as part of a repair.
- To adapt a template, create a new Asset and a new complete candidate Manifest pointing to its path and hash. Changing mappings in that new candidate does not modify an existing Manifest or its Asset files.
- Do not design Agent repair around editing an old image and then fixing old Manifest hashes; that operation is forbidden. Human editing and management through a future GUI are deferred separately.
- For crop requests, capture the current game anew, crop it, and return the crop for inspection. Do not require an earlier observation ID to remain current or read a saved screenshot file.

See [ADR 0020](../adr/0020-allow-screenshot-derived-assets-and-explicit-search-regions.md) and [ADR 0021](../adr/0021-retain-created-files-and-defer-resource-maintenance.md).
