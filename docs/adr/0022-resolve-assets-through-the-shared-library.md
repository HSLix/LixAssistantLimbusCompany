---
status: superseded
superseded_by: 0024
---

# Asset Library ownership

ADR 0024 replaces this withdrawn shared-mapping proposal in full. Use a dedicated immutable published library per Manifest, an editable Candidate library, globally shared images named with complete SHA-256, and publication for every changed library. No global mapping, update-all behavior, short-hash overwrite exception, or local fallback/cache remains. See ADR 0024 for the current requirements.
