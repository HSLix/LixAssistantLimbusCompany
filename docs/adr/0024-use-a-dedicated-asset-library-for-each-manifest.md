---
status: accepted
---

# Use a dedicated Asset Library mapping file for each Manifest

Each Manifest has its own dedicated Asset Library mapping file, stored outside the Manifest document and hash-addressed Component source. Its content is the former `assets` object: semantic name → language → `{path, sha256}`. The actual image files remain in the existing global Asset file store and may be referenced by different Manifests without copying them.

Recognition resolves an Asset through the library associated with the current Working Manifest and verifies the referenced global file's complete hash. A published Manifest and its dedicated library are retained together and are not edited by the developer CLI. Developers change the Developer Candidate's library and publish to create a new Manifest ID and its own library, even when Component mappings are unchanged. Publishing does not change an existing Run's selection. Changing the selected Working Manifest also selects its associated library. Load the complete mapping into memory with the Manifest, preserving the current execution snapshot behavior; matching does not reread the mapping file. There is no global Asset mapping authority, global-miss fallback, or first-use local cache in this design. The withdrawn optional post-Stage-4 caching TODO is removed rather than implemented.

Duplicate detection is scoped to the library being edited: both semantic name and game language must match. Developer CLI replacement edits only the Developer Candidate's library and requests explicit confirmation; refusal, EOF, or cancellation leaves the old entry and image unchanged. Confirmed replacement saves a PNG named `<semantic-name>-<language>-<complete-sha256>.png` and atomically changes only that candidate library's mapping, retaining old pixels. Identical content reuses the existing file; when the current mapping already references that same content, no replacement is necessary. Remove the previous short-hash collision overwrite exception: existing image files are never overwritten, including by the developer replacement path. Stage 3.5 must reject Agent duplicate-pair additions and require a new name.

This supersedes ADR 0022's single shared mapping file and update-all-Manifests behavior. It changes only Asset mapping ownership: image storage, language selection, explicit detection regions, NMS, crop provenance, Usage Index, hash checks, and original-error propagation remain. Application-owned Trusted Actions remain governed by ADR 0023. The #321 migration extracts Asset mappings into dedicated files.

## Confirmed #321 format transition and repository scope

Switch directly to the new format and explicitly reject old-format Developer Candidates and saved Manifests. Do not provide automatic migration or an explicit migration tool, and do not retain a parallel legacy runtime. Existing stored Manifest and image files are not deleted by the format transition.

The #321 migration deleted the old repository examples under `examples/` rather than migrating them, and moved their regression coverage into test-owned fixtures. ADR 0026 permits a new schema-2 teaching sample under `example/trusted-actions/`; it does not restore those old examples. Candidate and sample libraries are named `asset-library.json`; published libraries remain `asset-libraries/<Manifest ID>.json`.
