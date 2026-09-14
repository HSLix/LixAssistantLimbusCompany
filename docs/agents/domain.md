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
├── lalc_frontend/
└── lalc_backend/
```

`CONTEXT.md` records the shared domain language and boundaries. System-wide architectural decisions belong under `docs/adr/`.

## Use the glossary’s vocabulary

When an output names a domain concept—in an issue title, proposal, hypothesis, or test name—use the term defined in `CONTEXT.md`.

If the required concept is missing, reconsider whether the term belongs to the project or record the gap for domain modeling.

## Flag ADR conflicts

If proposed work contradicts an existing ADR, surface the conflict explicitly instead of silently overriding the decision.
