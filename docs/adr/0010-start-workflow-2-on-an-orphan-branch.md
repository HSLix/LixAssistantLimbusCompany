---
status: accepted
---

# Start Workflow 2.0 on an orphan branch

Workflow 2.0 starts from a clean orphan branch in the existing repository instead of being rebuilt inside the legacy runtime or moved to a new repository. The old branch preserves history, business knowledge, Assets, and an emergency rollback path, while the orphan branch selectively brings over accepted documents and still-valid evidence without carrying `TaskNode`, the global registry, JSON node graphs, legacy Pipelines, handler registration, shared task state, error nodes, or a dual-runtime compatibility layer. Keeping one repository preserves Issues and makes old resources easy to inspect; using an orphan branch prevents that convenience from becoming an obligation to retain the architecture being replaced.

## Consequences

Business behavior is re-expressed as Task Workflows, Subworkflows, and Steps rather than copied and renamed. Assets, models, and Windows interaction conclusions move only after inspection. Rollback means running the preserved old branch, not switching between two runtimes inside the new application.
