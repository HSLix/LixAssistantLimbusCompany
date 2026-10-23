---
status: accepted
---

# Store language-aware Assets outside the Component model

Asset ownership, language selection, naming and Candidate/publication instructions in this ADR are superseded by [ADR 0027](0027-resolve-assets-independently-with-optional-priority-tags.md). Component immutability, fresh-crop provenance and the accepted stage boundaries remain in force.


Assets have stable semantic names and no Component IDs. ADR 0024 governs their dedicated per-Manifest external libraries and globally shared image files. Developer edits belong to the Candidate library and require publication to create a new Manifest/library pair. Retained files are unchanged. Images use complete SHA-256 filenames and are never overwritten; identical content is reused.

Language selection, deterministic missing-language fallback, complete hash validation, explicit search regions, NMS, provenance, Trace and the independent Asset Usage Index remain required. Agent screenshot-derived additions follow ADR 0020; retention and deferred maintenance follow ADR 0021. No embedded Manifest Asset mappings or per-Manifest image copies remain.
